# battle(a, b, seed) —— 纯函数战斗引擎
#
# 规则来源:
#   design/02-combat.md(Akun v2 战斗手册)+ Q1-Q17 拍板(design/06-decisions.md)
#   工程默认 E1-E8(随机种子、100回合上限、伤害取整、无头回退、末位存活手、即时死亡、平局、插件不可被攻击)
#   机制件/插件落地细节:Q17(a-i)+ 机制工程默认(05 页 Q19,待 Akun 扫)
# 所有待 Akun 拍板的点都做成 RuleConfig 开关,方便 A/B 模拟。
import copy
import math
import random
from dataclasses import dataclass, field, asdict

from .parts import Part, PLUGINS, CATALOG

# 机制常量(Akun 零件表数值)
BURN_DMG = 2      # 灼烧:2 点/回合(喷火头,持续 3 回合,刷新)
TEAR_DMG = 2      # 撕裂:2 点/回合(撕裂爪 5 回合 / 尖刺皮肤 2 回合,刷新)
BURN_ROUNDS = 3
GRAB_ROUNDS = 5   # 抓握手:敌方接下来 5 个回合闪避为 0
SPORE_ROUNDS = 2  # 芽孢:槽位空 2 个整回合后长出新手(Q17b)
POISON_DMG = 3      # 中毒:3 点/回合 + 攻击力 -1(喷毒头,持续 2 回合,刷新;Akun 2026-07-22)
POISON_ROUNDS = 2
POISON_ATKDOWN = 1
ENTANGLE_ROUNDS = 5  # 触手缠绕:双方 5 回合不能攻击/格挡,每回合各扣 5 血(Q22j)
ENTANGLE_DMG = 5
SHOCK_DODGE = 0.05   # 震撼腿:敌方全队闪避 -5%,2 回合刷新不叠加(Q22n)
SHOCK_ROUNDS = 2
RESIST_SKIN = {"fire": "耐火皮肤", "poison": "耐毒皮肤", "ice": "耐冰皮肤"}   # 躯干插件:对应伤害 -50%+免疫状态(全身,Q19d/Q22q)
RESIST_TAIL = {"fire": "火蜥蜴尾巴", "poison": "毒蛇尾巴", "ice": "冰虫尾巴"}  # 尾巴插件:对应伤害 -20%(可与皮肤叠乘)


@dataclass
class RuleConfig:
    initiative_mode: str = "per_round"   # per_round=每回合重掷(v2 原文倾向) / once=开局掷一次(评审建议 A/B 项)
    head_vs_head_prob: float = 0.5       # 头攻击:50% 打头
    block_prob: float = 0.20             # 手部格挡概率
    block_mult: float = 0.80             # 格挡后伤害倍率(转给末位存活手)
    dodge_leg_slots: int = 2             # 只有腿1、腿2 提供闪避
    round_limit: int = 100               # E2
    stun_scope: str = "all"              # all=全队下回合不攻击(Q8) / heads=仅头不攻击(备选 A/B)
    legs_attack: bool = True             # False=腿默认不攻击(Codex 语法调整 A/B 项)
    command_mode: str = "battle"         # Q12 方案A(已拍板):每回合指挥点池,手腿出手各耗 1 点,
                                         #   池空则该肢体本回合不攻击(仍可被打/闪避/格挡)。头不耗点。
    crit_mult: float = 2.0               # 暴击伤害倍率(Akun 定了各头暴击率,倍率暂 2x;1.0=关闭暴击)
    block_overflow: bool = False         # 格挡溢出提案(耗材手流修法A,待 Akun):格挡手血量不够时,
                                         #   吃不下的伤害继续打原目标——废掉"1血手吞整发重击"
    status_slots: str = "multi"          # multi=异常状态可共存(现行) / single=每部件仅一个状态栏位,
                                         #   新状态顶掉旧状态(Akun Q19b 候选方案,A/B 用)


@dataclass
class Monster:
    name: str
    torso: Part
    heads: list = field(default_factory=list)
    hands: list = field(default_factory=list)
    legs: list = field(default_factory=list)
    tails: list = field(default_factory=list)
    slots: list = field(default_factory=list)   # 四肢插槽/头部插槽:只占预算、扩槽位,不参战

    def parts_of(self, kind: str) -> list:
        return {"head": self.heads, "hand": self.hands, "leg": self.legs}[kind]

    def all_parts(self) -> list:
        return [self.torso, *self.heads, *self.hands, *self.legs]

    def dodge_total(self, cfg: RuleConfig) -> float:
        # 只有腿槽 1..dodge_leg_slots 提供闪避;腿死闪避即时失效
        return sum(l.dodge for l in self.legs[: cfg.dodge_leg_slots] if l.alive())

    def initiative_total(self) -> int:
        # 存活腿 + 插件尾巴提供先攻(尾巴不可被攻击,恒有效);
        # 头也计入(三只喷头 先攻-1,Q22b);冰虫尾巴插件 +1
        return (sum(l.initiative for l in self.legs if l.alive())
                + sum(t.initiative for t in self.tails)
                + sum(h.initiative for h in self.heads if h.alive())
                + sum(PLUGINS[t.plugin].get("initiative", 0) for t in self.tails if t.plugin))

    def command_supply(self) -> int:
        # 躯干基础指挥 + 存活头的指挥(头死指挥点即时消失 → 下回合肢体行动力下降)
        return self.torso.command + sum(h.command for h in self.heads if h.alive())

    def energy_used(self) -> int:
        return sum(p.energy for p in self.all_parts() if p.kind != "torso") \
            + sum(t.energy for t in self.tails)

    def supply_total(self) -> int:
        # 躯干供能 + 供能类插件(普通能量核心——躯干"身体"位插件)
        return (self.torso.supply
                + sum(s.supply for s in self.slots)
                + sum(PLUGINS[p.plugin].get("supply", 0) for p in self.all_parts() if p.plugin))

    def price_total(self) -> int:
        return (sum(p.price for p in self.all_parts())
                + sum(t.price for t in self.tails)
                + sum(s.price for s in self.slots)
                + sum(PLUGINS[p.plugin]["price"] for p in self.all_parts() if p.plugin))


def _interleave(first_parts, second_parts):
    """A1,B1,A2,B2...,多出的部分按槽位序接在后面(02-combat 结算顺序)。"""
    seq = []
    n = max(len(first_parts), len(second_parts))
    for i in range(n):
        if i < len(first_parts):
            seq.append(("first", first_parts[i]))
        if i < len(second_parts):
            seq.append(("second", second_parts[i]))
    return seq


def battle(a: Monster, b: Monster, seed=0, cfg: RuleConfig = None, rng=None) -> dict:
    """纯函数:同 (a, b, seed, cfg) 必得同一战报。rng 参数仅供单测注入脚本化随机。"""
    cfg = cfg or RuleConfig()
    rng = rng or random.Random(seed)
    a, b = copy.deepcopy(a), copy.deepcopy(b)   # 不改动调用方对象,保持纯函数
    sides = {"A": a, "B": b}
    events = []
    stun_next = {"A": False, "B": False}
    zero_until = {"A": 0, "B": 0}    # 抓握手:该方闪避清零至此回合(含)
    regen = {"A": [], "B": []}       # 胶质瘤:激活中的回复计数器(每个 = 剩余回合数)
    shock_left = {"A": 0, "B": 0}    # 震撼腿:该方全队闪避 -5% 的剩余回合(刷新不叠加,Q22n)
    winner = None                    # "A" / "B" / "draw"
    first_key_locked = None          # initiative_mode=once 时锁定

    # 运行时状态初始化(角质层充能;其余字段 Part 默认值已就位)
    for m in (a, b):
        for p in m.all_parts():
            if p.plugin == "头顶角质层":
                p.keratin = PLUGINS["头顶角质层"]["absorbs"]

    def log(round_no, etype, **kw):
        events.append(dict(round=round_no, type=etype, **kw))

    def enemy_key(k):
        return "B" if k == "A" else "A"

    def update_winner():
        nonlocal winner
        a_dead, b_dead = not a.torso.alive(), not b.torso.alive()
        if a_dead and b_dead:
            winner = "draw"          # E7:同一次结算双躯干归零 → 平局
        elif a_dead:
            winner = "B"
        elif b_dead:
            winner = "A"

    def heal_side(key, amount, exclude=None):
        """回复该方所有存活部件;返回 (总回复量, [(部件, 新血量), ...]) 供事件流/UI 同步血条。"""
        m, healed, parts = sides[key], 0, []
        for p in m.all_parts():
            if p is exclude or not p.alive():
                continue
            gain = min(amount, p.max_hp - p.hp)
            p.hp += gain
            healed += gain
            if gain > 0:
                parts.append(dict(part=p.label, hp=p.hp))
        return healed, parts

    def handle_break(round_no, victim: Part, vic_key, killer: Part, killer_key):
        """部件击破的统一结算:眩晕/胜负/芽孢/插件死亡触发。killer 可为 None(来源已死)。"""
        log(round_no, "break", side=vic_key, part=victim.label, kind=victim.kind)
        victim.burn = victim.tear = victim.poison = None
        victim.stunned_part = victim.stun_part_next = False
        if victim.entangled_left > 0:   # 被缠部件死亡 → 触手(或对方)立即解脱(Q22j)
            partner = victim.entangle_partner
            victim.entangled_left = 0
            victim.entangle_partner = None
            if partner is not None and partner.alive():
                partner.entangled_left = 0
                partner.entangle_partner = None
                log(round_no, "entangle_end", side=enemy_key(vic_key), part=partner.label, freed=True)
        if victim.kind == "head":
            stun_next[vic_key] = True
            log(round_no, "stun_set", side=vic_key)
        if victim.kind == "torso":
            update_winner()
        if victim.spore:   # Q17b:芽孢标记占原槽位,空 2 回合后长出新手
            victim.spore_wait = SPORE_ROUNDS
            log(round_no, "spore_set", side=vic_key, part=victim.label)
        plug = victim.plugin
        if plug == "胶质瘤":
            regen[vic_key].append(PLUGINS["胶质瘤"]["rounds"])
            log(round_no, "regen_start", side=vic_key, part=victim.label,
                heal=PLUGINS["胶质瘤"]["heal"], rounds=PLUGINS["胶质瘤"]["rounds"])
        elif plug == "肾上腺素":
            healed, hparts = heal_side(vic_key, PLUGINS["肾上腺素"]["heal"], exclude=victim)
            log(round_no, "adrenaline", side=vic_key, part=victim.label,
                healed=healed, parts=hparts)
        elif plug == "爆裂腺体" and killer is not None and killer.alive():
            gdmg = PLUGINS["爆裂腺体"]["dmg"]
            killer.hp -= gdmg
            log(round_no, "gland", side=vic_key, part=victim.label,
                target=killer.label, dmg=gdmg, target_hp=max(killer.hp, 0))
            if not killer.alive():   # 级联:被炸死的部件照常走击破结算
                handle_break(round_no, killer, killer_key, None, vic_key)

    def resist_skin(key, dtype):
        """耐×皮肤(躯干插件)护全身(Q19d/Q22q):对应伤害减半+免疫对应状态。"""
        t = sides[key].torso
        return t.alive() and t.plugin == RESIST_SKIN.get(dtype)

    def resist_mult(key, dtype):
        """属性伤害的全身减免倍率:皮肤 ×0.5 与属性尾巴 ×0.8 叠乘(工程默认)。"""
        if dtype == "phys":
            return 1.0
        m = 0.5 if resist_skin(key, dtype) else 1.0
        if any(t.plugin == RESIST_TAIL.get(dtype) for t in sides[key].tails):
            m *= 0.8
        return m

    def tail_bonus(key, field):
        """属性尾巴的全队增益(火蜥蜴 burn_bonus / 毒蛇 poison_bonus / 冰虫 freeze_bonus)。"""
        return sum(PLUGINS[t.plugin].get(field, 0) for t in sides[key].tails if t.plugin)

    def _single_slot_clear(part, keep):
        if cfg.status_slots == "single":   # 单状态栏位:新状态顶掉旧状态(Q19b A/B)
            for s in ("burn", "tear", "poison"):
                if s != keep:
                    setattr(part, s, None)

    def set_burn(part, val):
        part.burn = val
        _single_slot_clear(part, "burn")

    def set_tear(part, val):
        part.tear = val
        _single_slot_clear(part, "tear")

    def set_poison(part, val):
        part.poison = val
        _single_slot_clear(part, "poison")

    def eff_atk(part):
        """当前有效攻击力:中毒期间 -atkdown(最低 0),到期自动恢复(实时计算)。"""
        atk = part.atk
        if part.poison:
            atk -= part.poison.get("atkdown", POISON_ATKDOWN)
        return max(0, atk)

    def after_damage(round_no, attacker: Part, atk_key, victim: Part, def_key, dmg):
        """命中造成伤害后的状态施加(灼烧/中毒/冻结/撕裂/碎骨锥/尖刺皮肤/高鞭腿/震撼腿)。
        挂给实际受伤者(含格挡手)。"""
        if dmg <= 0:
            return
        if attacker.dtype == "fire" and victim.alive() and not resist_skin(def_key, "fire"):
            set_burn(victim, dict(left=BURN_ROUNDS, dmg=BURN_DMG + tail_bonus(atk_key, "burn_bonus"),
                                  src=attacker, src_key=atk_key))
            log(round_no, "status", side=def_key, part=victim.label, status="burn",
                rounds=BURN_ROUNDS, by=attacker.label)
        if attacker.dtype == "poison" and victim.alive() and not resist_skin(def_key, "poison"):
            pb = tail_bonus(atk_key, "poison_bonus")
            set_poison(victim, dict(left=POISON_ROUNDS, dmg=POISON_DMG + pb,
                                    atkdown=POISON_ATKDOWN + pb, src=attacker, src_key=atk_key))
            log(round_no, "status", side=def_key, part=victim.label, status="poison",
                rounds=POISON_ROUNDS, by=attacker.label)
        if attacker.freeze_prob > 0 and victim.alive() and victim.kind != "torso" \
                and not resist_skin(def_key, "ice"):
            if rng.random() < attacker.freeze_prob + tail_bonus(atk_key, "freeze_bonus"):
                victim.stun_part_next = True    # 冻结=部件级 1 回合不行动(同碎骨锥,Q22e)
                log(round_no, "status", side=def_key, part=victim.label, status="freeze",
                    rounds=1, by=attacker.label)
        if attacker.plugin == "撕裂爪" and victim.alive():
            set_tear(victim, dict(left=PLUGINS["撕裂爪"]["tear_rounds"], src=attacker, src_key=atk_key))
            log(round_no, "status", side=def_key, part=victim.label, status="tear",
                rounds=PLUGINS["撕裂爪"]["tear_rounds"], by=attacker.label)
        if attacker.plugin == "碎骨锥" and victim.alive() and victim.kind != "torso":
            if rng.random() < PLUGINS["碎骨锥"]["stun_prob"]:
                victim.stun_part_next = True
                log(round_no, "part_stun_set", side=def_key, part=victim.label, by=attacker.label)
        if victim.kind == "torso" and victim.plugin == "尖刺皮肤" and attacker.alive():
            set_tear(attacker, dict(left=PLUGINS["尖刺皮肤"]["tear_rounds"], src=victim, src_key=def_key))
            log(round_no, "status", side=atk_key, part=attacker.label, status="tear",
                rounds=PLUGINS["尖刺皮肤"]["tear_rounds"], by=victim.label)
        if victim.revenge_head and victim.alive():   # 高鞭腿:被打中 → 下次攻击改打头(Q22k)
            victim.revenge_pending = True
        if attacker.shock:   # 震撼腿(Q22n):敌方全队闪避 -5%,2 回合,刷新不叠加
            shock_left[def_key] = SHOCK_ROUNDS
            log(round_no, "status", side=def_key, part=victim.label, status="shock",
                rounds=SHOCK_ROUNDS, by=attacker.label)

    def choose_target(kind, defender, hunts=""):
        # 目标偏好(Q15 机制件原型):优先打指定部位,打光回退本类默认规则
        if hunts:
            pool = [p for p in defender.parts_of(hunts) if p.alive()]
            if pool:
                return rng.choice(pool)
        if kind == "leg":
            pool = [p for p in defender.legs if p.alive()]
            return rng.choice(pool) if pool else defender.torso
        if kind == "hand":
            pool = [p for p in defender.hands if p.alive()]
            return rng.choice(pool) if pool else defender.torso
        # head:50% 打头(无存活头则回退躯干 E4),否则躯干
        pool = [p for p in defender.heads if p.alive()]
        if rng.random() < cfg.head_vs_head_prob and pool:
            return rng.choice(pool)
        return defender.torso

    def strike(round_no, atk_key, attacker: Part, target: Part, extra=False, counter=False):
        """单次打击结算:闪避→抓握→暴击→角质层→格挡→伤害→状态→击破。
        返回结果串("dodge"/"grab"/"absorb"/"block"/"hit")供连环腿/黏腿判定。"""
        def_key = enemy_key(atk_key)
        defender = sides[def_key]
        # 1) 闪避(全身共享,实时计算;被抓握则清零;震撼腿 debuff -5%)
        dv = 0.0 if round_no <= zero_until[def_key] else defender.dodge_total(cfg)
        if shock_left[def_key] > 0:
            dv = max(0.0, dv - SHOCK_DODGE)
        if dv > 0 and rng.random() < dv:
            log(round_no, "dodge", side=atk_key, attacker=attacker.label,
                target=target.label, dodge=round(dv, 2), extra=extra)
            # 先守后攻(Q22o):指向该腿的攻击被闪掉 → 该腿立即反击攻击者(反击不再触发反击)
            if (not counter and target.kind == "leg" and target.plugin == "先守后攻"
                    and target.alive() and attacker.alive() and not winner):
                strike(round_no, def_key, target, attacker, counter=True)
            return "dodge"
        # 1.2) 抓握手:第一次命中不造成伤害,敌方 5 回合闪避清零(闪避掉不消耗"第一次")
        if attacker.grab and not attacker.grab_used:
            attacker.grab_used = True
            zero_until[def_key] = round_no + GRAB_ROUNDS
            log(round_no, "grab", side=atk_key, attacker=attacker.label,
                target=target.label, rounds=GRAB_ROUNDS)
            return "grab"
        dmg = eff_atk(attacker)   # 中毒降攻实时生效(Q22d)
        # 1.5) 暴击(仅 crit>0 的部件掷骰;角质层生效期间宿主头不暴击;
        #      蓄力件偶数回合必暴击、残像拳同目标必暴击——均无视角质层压制,Q22g/h)
        eff_crit = 0.0 if attacker.keratin > 0 else attacker.crit
        crit = False
        if cfg.crit_mult > 1.0:
            if (attacker.charge and round_no % 2 == 0) \
                    or (attacker.afterimage and attacker.last_target is target):
                crit = True
            elif eff_crit > 0 and rng.random() < eff_crit:
                crit = True
        if crit:
            mult = cfg.crit_mult
            if attacker.plugin == "认真一拳":   # 暴击倍率 2.0→2.5(Q22p)
                mult += PLUGINS["认真一拳"]["crit_mult_bonus"]
            dmg = math.floor(dmg * mult)
        # 1.6) 伸缩头(Q22f):奇数回合造成伤害 ×1.25,偶数 ×0.75(向下取整,最小 1)
        if attacker.stretch and dmg > 0:
            dmg = max(1, math.floor(dmg * (1.25 if round_no % 2 == 1 else 0.75)))
        # 1.8) 头顶角质层:替宿主头承受攻击(整次吸收,无伤害无状态),2 次后失效
        if target.kind == "head" and target.keratin > 0:
            target.keratin -= 1
            log(round_no, "absorb", side=atk_key, attacker=attacker.label,
                target=target.label, left=target.keratin)
            return "absorb"
        # 2) 格挡:头/躯干被攻击 + 有存活手 → 20%,伤害×80% 转末位存活手(E5;骨盾再×80%)
        #    喷头/尾巴头的攻击不可被格挡(Q22a);被缠绕的手不能格挡(Q22j)
        blockers = [h for h in defender.hands if h.alive() and h.entangled_left <= 0]
        if (not attacker.noblock and target.kind in ("head", "torso")
                and blockers and rng.random() < cfg.block_prob):
            blocker = max(blockers, key=lambda h: h.slot)
            bdmg = max(1, math.floor(dmg * cfg.block_mult)) if dmg > 0 else 0
            bone = blocker.plugin == "骨盾"
            if bone and bdmg > 0:
                bdmg = max(1, math.floor(bdmg * PLUGINS["骨盾"]["block_mult"]))
            overflow = 0
            if cfg.block_overflow and bdmg > blocker.hp:
                overflow = bdmg - blocker.hp
                bdmg = blocker.hp
            blocker.hp -= bdmg
            log(round_no, "block", side=atk_key, attacker=attacker.label,
                target=target.label, blocker=blocker.label, dmg=dmg, taken=bdmg,
                blocker_hp=max(blocker.hp, 0), crit=crit, overflow=overflow, bone=bone)
            after_damage(round_no, attacker, atk_key, blocker, def_key, bdmg)
            if not blocker.alive():
                handle_break(round_no, blocker, def_key, attacker, atk_key)
            if overflow > 0:
                target.hp -= overflow
                log(round_no, "hit", side=atk_key, attacker=attacker.label,
                    target=target.label, dmg=overflow, target_hp=max(target.hp, 0),
                    crit=False, overflow=True)
                after_damage(round_no, attacker, atk_key, target, def_key, overflow)
                if not target.alive():
                    handle_break(round_no, target, def_key, attacker, atk_key)
            return "block"
        # 3) 正常结算(E6 即时死亡;属性伤害全身减免:耐×皮肤 ×0.5、属性尾巴 ×0.8 叠乘)
        rm = resist_mult(def_key, attacker.dtype)
        resisted = rm < 1.0 and dmg > 0
        if resisted:
            dmg = max(1, math.floor(dmg * rm))
        # 伸缩头挨打(Q22f):奇数回合受到伤害 ×1.25,偶数 ×0.75
        if target.stretch and dmg > 0:
            dmg = max(1, math.floor(dmg * (1.25 if round_no % 2 == 1 else 0.75)))
        target.hp -= dmg
        log(round_no, "hit", side=atk_key, attacker=attacker.label,
            target=target.label, dmg=dmg, target_hp=max(target.hp, 0),
            crit=crit, extra=extra, fireproof=resisted and attacker.dtype == "fire",
            resist=attacker.dtype if resisted else "")
        after_damage(round_no, attacker, atk_key, target, def_key, dmg)
        if not target.alive():
            handle_break(round_no, target, def_key, attacker, atk_key)
        return "hit"

    def resolve(round_no, atk_key, attacker: Part):
        defender = sides[enemy_key(atk_key)]
        # 喷毒头(Q22c):攻击除躯干外随机 1 个部位的所有部件;都没有 → 打躯干
        if attacker.aoe_pos:
            kinds = [k for k in ("head", "hand", "leg")
                     if any(p.alive() for p in defender.parts_of(k))]
            if kinds:
                targets = [p for p in defender.parts_of(rng.choice(kinds)) if p.alive()]
                for t in targets:
                    if winner or not attacker.alive():
                        break
                    strike(round_no, atk_key, attacker, t)
            else:
                strike(round_no, atk_key, attacker, defender.torso)
            return
        # 高鞭腿(Q22k):被打中后下一次攻击改打敌方头(无存活头则回退默认),打完清标记
        if attacker.revenge_pending:
            attacker.revenge_pending = False
            heads = [h for h in defender.heads if h.alive()]
            target = rng.choice(heads) if heads else choose_target(attacker.kind, defender, attacker.hunts)
        # 黏腿(Q22m):锁定中且目标存活 → 固定打它
        elif attacker.sticky and attacker.lock_target is not None and attacker.lock_target.alive():
            target = attacker.lock_target
        else:
            target = choose_target(attacker.kind, defender, attacker.hunts)
        outcome = strike(round_no, atk_key, attacker, target)
        if attacker.sticky:
            attacker.lock_target = None if outcome == "dodge" else target
        if attacker.afterimage:
            attacker.last_target = target   # 残像拳:记录主攻目标(Q22h)
        # 喷火头/喷冰头:额外随机攻击 1 个目标(任意存活部件,尽量避开主目标),独立结算
        if attacker.extra_target and not winner and attacker.alive():
            pool = [p for p in (defender.torso, *defender.heads, *defender.hands, *defender.legs)
                    if p.alive() and p is not target]
            if pool:
                strike(round_no, atk_key, attacker, rng.choice(pool), extra=True)

    def combo_resolve(round_no, atk_key, part: Part):
        """连环腿(Q22l):同目标连打 3 段(各自判闪避/格挡),3 段全未被闪避且目标存活 → 补第 4 段。"""
        defender = sides[enemy_key(atk_key)]
        target = choose_target(part.kind, defender, part.hunts)
        dodged, landed = False, 0
        for _ in range(3):
            if winner or not part.alive() or not target.alive():
                break
            if strike(round_no, atk_key, part, target) == "dodge":
                dodged = True
            landed += 1
        if landed == 3 and not dodged and not winner and part.alive() and target.alive():
            strike(round_no, atk_key, part, target)

    def tick_dots(round_no):
        """回合末 DoT 结算:灼烧/撕裂/中毒直接掉部件血(不可闪避/格挡),双方同时结算(E7 平局适用)。"""
        for k in ("A", "B"):
            for p in sides[k].all_parts():
                for status_name, base_dmg in (("burn", BURN_DMG), ("tear", TEAR_DMG),
                                              ("poison", POISON_DMG)):
                    st = getattr(p, status_name)
                    if st is None or not p.alive():
                        continue
                    dmg_val = st.get("dmg", base_dmg)   # 属性尾巴增益在施加时已算入
                    p.hp -= dmg_val
                    log(round_no, "dot_tick", side=k, part=p.label, status=status_name,
                        dmg=dmg_val, part_hp=max(p.hp, 0))
                    st["left"] -= 1
                    if st["left"] <= 0:
                        setattr(p, status_name, None)
                    if not p.alive():
                        src, src_key = st["src"], st["src_key"]
                        handle_break(round_no, p, k,
                                     src if (src is not None and src.alive()) else None, src_key)
        update_winner()

    def tick_entangle(round_no):
        """缠绕结算(Q22j):双方被缠部件各扣 5 血(不可闪避/格挡,可致死),倒计时;一方死另一方立即解脱。"""
        for k in ("A", "B"):
            for p in [*sides[k].heads, *sides[k].hands, *sides[k].legs]:
                if p.entangled_left <= 0 or not p.alive():
                    continue
                p.hp -= ENTANGLE_DMG
                p.entangled_left -= 1
                log(round_no, "entangle_tick", side=k, part=p.label,
                    dmg=ENTANGLE_DMG, part_hp=max(p.hp, 0), left=p.entangled_left)
                partner = p.entangle_partner
                if not p.alive():
                    p.entangled_left = 1   # 让 handle_break 走"死亡解缠"分支(解自己+放走对方)
                    handle_break(round_no, p, k,
                                 partner if (partner is not None and partner.alive()) else None,
                                 enemy_key(k))
                elif p.entangled_left <= 0:
                    log(round_no, "entangle_end", side=k, part=p.label, freed=False)
                    p.entangle_partner = None
        update_winner()

    def tick_regen(round_no):
        for k in ("A", "B"):
            if not regen[k]:
                continue
            amount = PLUGINS["胶质瘤"]["heal"] * len(regen[k])
            healed, hparts = heal_side(k, amount)
            if healed > 0:
                log(round_no, "regen", side=k, heal=amount, healed=healed, parts=hparts)
            regen[k] = [r - 1 for r in regen[k] if r - 1 > 0]

    # 触手战吼(Q22j):开战时(回合 0)每只触手随机缠绕一个敌方非躯干存活部件,不可闪避;
    # 双方 5 回合不能攻击/格挡,每回合末各扣 5 血;任一方死亡即解除
    for key in ("A", "B"):
        for tent in sides[key].hands:
            if not tent.tentacle or not tent.alive():
                continue
            ek = enemy_key(key)
            pool = [p for p in (*sides[ek].heads, *sides[ek].hands, *sides[ek].legs)
                    if p.alive() and p.entangled_left <= 0]
            if not pool:
                pool = [p for p in (*sides[ek].heads, *sides[ek].hands, *sides[ek].legs) if p.alive()]
            if not pool:
                continue
            victim = rng.choice(pool)
            tent.entangled_left = victim.entangled_left = ENTANGLE_ROUNDS
            tent.entangle_partner, victim.entangle_partner = victim, tent
            log(0, "entangle", side=key, part=tent.label, target=victim.label, rounds=ENTANGLE_ROUNDS)

    round_no = 0
    for round_no in range(1, cfg.round_limit + 1):
        # 先攻(Q4:P(A先) = A先攻/(A+B);双 0 → 50/50;喷头 -1 可能压出负数,截到 0)
        ia, ib = max(0, a.initiative_total()), max(0, b.initiative_total())
        if cfg.initiative_mode == "once" and first_key_locked:
            first_key = first_key_locked
        else:
            p_a = ia / (ia + ib) if (ia + ib) > 0 else 0.5
            first_key = "A" if rng.random() < p_a else "B"
            if cfg.initiative_mode == "once":
                first_key_locked = first_key
        second_key = enemy_key(first_key)
        log(round_no, "round_start", first=first_key, init_a=ia, init_b=ib)

        # 芽孢重生(Q17b):倒计时在回合开始走,归 0 的下回合长出「芽孢长出来的手」满血登场
        for k in ("A", "B"):
            for p in sides[k].hands:
                if p.spore_wait < 0:
                    continue
                if p.spore_wait == 0:
                    spec = CATALOG["芽孢长出来的手"]
                    p.name = "芽孢长出来的手"
                    p.atk, p.hp, p.max_hp = spec["atk"], spec["hp"], spec["hp"]
                    p.energy = spec.get("energy", 0)
                    p.spore, p.derived, p.plugin = False, True, ""   # 插件随原宿主消失(Q17e)
                    p.crit, p.grab, p.fire = 0.0, False, False
                    p.grab_used = False
                    p.dtype, p.extra_target, p.aoe_pos, p.noblock = "phys", False, False, False
                    p.freeze_prob, p.stretch, p.charge, p.afterimage = 0.0, False, False, False
                    p.tentacle, p.hits = False, 1
                    p.spore_wait = -1
                    log(round_no, "spore_grow", side=k, part=p.label, hp=p.hp)
                else:
                    p.spore_wait -= 1

        # 整队眩晕消费:本回合停手,标记清空(本回合再破头会重新标记到下回合)
        skip = {k: stun_next[k] for k in ("A", "B")}
        for k in ("A", "B"):
            if skip[k]:
                log(round_no, "stunned", side=k)
            stun_next[k] = False

        # 部件级眩晕消费(碎骨锥,Q17d):与整队眩晕叠加只算眩晕(不重复记事件)
        for k in ("A", "B"):
            for p in [*sides[k].heads, *sides[k].hands, *sides[k].legs]:
                p.stunned_part = p.stun_part_next
                p.stun_part_next = False
                if p.stunned_part and p.alive() and not skip[k]:
                    log(round_no, "part_stunned", side=k, part=p.label)

        # 指挥点池(Q12 方案A):回合开始按「躯干基础+存活头」结算,手腿出手各耗 1 点
        cmd_pool = {k: sides[k].command_supply() for k in ("A", "B")}
        if cfg.command_mode == "battle":
            log(round_no, "command", cmd_a=cmd_pool["A"], cmd_b=cmd_pool["B"])

        phases = ["leg", "hand", "head"] if cfg.legs_attack else ["hand", "head"]
        for kind in phases:
            fp = [p for p in sides[first_key].parts_of(kind) if p.alive()]
            sp = [p for p in sides[second_key].parts_of(kind) if p.alive()]
            if kind == "head":
                # 尾巴上的头(Q22i):头阶段最后行动——双方普通头打完,再轮双方尾巴头
                seq = (_interleave([p for p in fp if not p.tail_head],
                                   [p for p in sp if not p.tail_head])
                       + _interleave([p for p in fp if p.tail_head],
                                     [p for p in sp if p.tail_head]))
            else:
                seq = _interleave(fp, sp)
            for who, part in seq:
                atk_key = first_key if who == "first" else second_key
                if (winner or skip[atk_key] or not part.alive()
                        or part.stunned_part or part.entangled_left > 0
                        or (part.atk <= 0 and not part.grab)):
                    continue
                if part.charge and round_no % 2 == 1:   # 蓄力件:奇数回合蓄力,不攻击不耗指挥(Q22g)
                    log(round_no, "charging", side=atk_key, part=part.label)
                    continue
                if cfg.command_mode == "battle" and kind in ("leg", "hand"):
                    if cmd_pool[atk_key] <= 0:
                        log(round_no, "no_command", side=atk_key, part=part.label)
                        continue
                    cmd_pool[atk_key] -= 1
                if part.combo3:   # 连环腿:特殊多段,整体耗 1 指挥点(Q22l)
                    combo_resolve(round_no, atk_key, part)
                    continue
                # 多段攻击(如猛犸象头"双击"/刺拳手):每段独立结算目标/闪避/格挡,整体只耗 1 指挥点
                for _ in range(part.hits):
                    if winner or not part.alive():
                        break
                    resolve(round_no, atk_key, part)
            if winner:
                break
        # 回合末:缠绕 → DoT 结算 → 胶质瘤回复(死斗中不再结算);震撼腿 debuff 递减
        if not winner:
            tick_entangle(round_no)
        if not winner:
            tick_dots(round_no)
        if not winner:
            tick_regen(round_no)
        for k in ("A", "B"):
            if shock_left[k] > 0:
                shock_left[k] -= 1
        if winner:
            break

    # 超时判定(E2):按躯干剩余血量百分比
    result = winner
    if result is None:
        pa = a.torso.hp / a.torso.max_hp
        pb = b.torso.hp / b.torso.max_hp
        result = "A" if pa > pb else ("B" if pb > pa else "draw")
        log(round_no, "timeout", torso_pct_a=round(pa, 3), torso_pct_b=round(pb, 3))

    return {
        "winner": result,                      # "A" / "B" / "draw"
        "winner_name": {"A": a.name, "B": b.name}.get(result, "平局"),
        "rounds": round_no,
        "events": events,
        "final": {k: [dict(name=p.label, hp=max(p.hp, 0), max_hp=p.max_hp, plugin=p.plugin)
                      for p in m.all_parts()] for k, m in sides.items()},
        "config": asdict(cfg),
        "seed": seed,
    }
