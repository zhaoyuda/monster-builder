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
        # 存活腿 + 插件尾巴提供先攻(尾巴不可被攻击,恒有效)
        return (sum(l.initiative for l in self.legs if l.alive())
                + sum(t.initiative for t in self.tails))

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
        victim.burn = victim.tear = None
        victim.stunned_part = victim.stun_part_next = False
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

    def after_damage(round_no, attacker: Part, atk_key, victim: Part, def_key, dmg):
        """命中造成伤害后的状态施加(灼烧/撕裂/碎骨锥/尖刺皮肤)。挂给实际受伤者(含格挡手)。"""
        if dmg <= 0:
            return
        if attacker.fire and victim.alive() and victim.plugin != "耐火皮肤":
            victim.burn = dict(left=BURN_ROUNDS, src=attacker, src_key=atk_key)
            log(round_no, "status", side=def_key, part=victim.label, status="burn",
                rounds=BURN_ROUNDS, by=attacker.label)
        if attacker.plugin == "撕裂爪" and victim.alive():
            victim.tear = dict(left=PLUGINS["撕裂爪"]["tear_rounds"], src=attacker, src_key=atk_key)
            log(round_no, "status", side=def_key, part=victim.label, status="tear",
                rounds=PLUGINS["撕裂爪"]["tear_rounds"], by=attacker.label)
        if attacker.plugin == "碎骨锥" and victim.alive() and victim.kind != "torso":
            if rng.random() < PLUGINS["碎骨锥"]["stun_prob"]:
                victim.stun_part_next = True
                log(round_no, "part_stun_set", side=def_key, part=victim.label, by=attacker.label)
        if victim.kind == "torso" and victim.plugin == "尖刺皮肤" and attacker.alive():
            attacker.tear = dict(left=PLUGINS["尖刺皮肤"]["tear_rounds"], src=victim, src_key=def_key)
            log(round_no, "status", side=atk_key, part=attacker.label, status="tear",
                rounds=PLUGINS["尖刺皮肤"]["tear_rounds"], by=victim.label)

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

    def strike(round_no, atk_key, attacker: Part, target: Part, extra=False):
        """单次打击结算:闪避→抓握→暴击→角质层→格挡→伤害→状态→击破。"""
        def_key = enemy_key(atk_key)
        defender = sides[def_key]
        # 1) 闪避(全身共享,实时计算;被抓握则清零)
        dv = 0.0 if round_no <= zero_until[def_key] else defender.dodge_total(cfg)
        if dv > 0 and rng.random() < dv:
            log(round_no, "dodge", side=atk_key, attacker=attacker.label,
                target=target.label, dodge=round(dv, 2), extra=extra)
            return
        # 1.2) 抓握手:第一次命中不造成伤害,敌方 5 回合闪避清零(闪避掉不消耗"第一次")
        if attacker.grab and not attacker.grab_used:
            attacker.grab_used = True
            zero_until[def_key] = round_no + GRAB_ROUNDS
            log(round_no, "grab", side=atk_key, attacker=attacker.label,
                target=target.label, rounds=GRAB_ROUNDS)
            return
        dmg = attacker.atk
        # 1.5) 暴击(仅 crit>0 的部件掷骰;角质层生效期间宿主头不暴击)
        eff_crit = 0.0 if attacker.keratin > 0 else attacker.crit
        crit = False
        if eff_crit > 0 and cfg.crit_mult > 1.0 and rng.random() < eff_crit:
            crit = True
            dmg = math.floor(dmg * cfg.crit_mult)
        # 1.8) 头顶角质层:替宿主头承受攻击(整次吸收,无伤害无状态),2 次后失效
        if target.kind == "head" and target.keratin > 0:
            target.keratin -= 1
            log(round_no, "absorb", side=atk_key, attacker=attacker.label,
                target=target.label, left=target.keratin)
            return
        # 2) 格挡:头/躯干被攻击 + 有存活手 → 20%,伤害×80% 转末位存活手(E5;骨盾再×80%)
        blockers = [h for h in defender.hands if h.alive()]
        if target.kind in ("head", "torso") and blockers and rng.random() < cfg.block_prob:
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
            return
        # 3) 正常结算(E6 即时死亡;耐火皮肤:宿主躯干火焰伤害减半)
        fireproof = attacker.fire and target.plugin == "耐火皮肤" and dmg > 0
        if fireproof:
            dmg = max(1, math.floor(dmg * 0.5))
        target.hp -= dmg
        log(round_no, "hit", side=atk_key, attacker=attacker.label,
            target=target.label, dmg=dmg, target_hp=max(target.hp, 0),
            crit=crit, extra=extra, fireproof=fireproof)
        after_damage(round_no, attacker, atk_key, target, def_key, dmg)
        if not target.alive():
            handle_break(round_no, target, def_key, attacker, atk_key)

    def resolve(round_no, atk_key, attacker: Part):
        defender = sides[enemy_key(atk_key)]
        target = choose_target(attacker.kind, defender, attacker.hunts)
        strike(round_no, atk_key, attacker, target)
        # 喷火头(Q17a):额外随机攻击 1 个目标(任意存活部件,尽量避开主目标),独立结算
        if attacker.fire and not winner and attacker.alive():
            pool = [p for p in (defender.torso, *defender.heads, *defender.hands, *defender.legs)
                    if p.alive() and p is not target]
            if pool:
                strike(round_no, atk_key, attacker, rng.choice(pool), extra=True)

    def tick_dots(round_no):
        """回合末 DoT 结算:灼烧/撕裂直接掉部件血(不可闪避/格挡),双方同时结算(E7 平局适用)。"""
        for k in ("A", "B"):
            for p in sides[k].all_parts():
                for status_name, dmg_val in (("burn", BURN_DMG), ("tear", TEAR_DMG)):
                    st = getattr(p, status_name)
                    if st is None or not p.alive():
                        continue
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

    def tick_regen(round_no):
        for k in ("A", "B"):
            if not regen[k]:
                continue
            amount = PLUGINS["胶质瘤"]["heal"] * len(regen[k])
            healed, hparts = heal_side(k, amount)
            if healed > 0:
                log(round_no, "regen", side=k, heal=amount, healed=healed, parts=hparts)
            regen[k] = [r - 1 for r in regen[k] if r - 1 > 0]

    round_no = 0
    for round_no in range(1, cfg.round_limit + 1):
        # 先攻(Q4:P(A先) = A先攻/(A+B);双 0 → 50/50)
        ia, ib = a.initiative_total(), b.initiative_total()
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
            for who, part in _interleave(fp, sp):
                atk_key = first_key if who == "first" else second_key
                if (winner or skip[atk_key] or not part.alive()
                        or part.stunned_part or (part.atk <= 0 and not part.grab)):
                    continue
                if cfg.command_mode == "battle" and kind in ("leg", "hand"):
                    if cmd_pool[atk_key] <= 0:
                        log(round_no, "no_command", side=atk_key, part=part.label)
                        continue
                    cmd_pool[atk_key] -= 1
                # 多段攻击(如猛犸象头"双击"):每段独立结算目标/闪避/格挡,整体只耗 1 指挥点
                for _ in range(part.hits):
                    if winner or not part.alive():
                        break
                    resolve(round_no, atk_key, part)
            if winner:
                break
        # 回合末:DoT 结算 → 胶质瘤回复(死斗中不再结算)
        if not winner:
            tick_dots(round_no)
        if not winner:
            tick_regen(round_no)
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
