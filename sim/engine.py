# battle(a, b, seed) —— 纯函数战斗引擎
#
# 规则来源:
#   design/02-combat.md(Akun v2 战斗手册)
#   design/05-open-questions.md 的推荐默认:Q4 先攻概率骰 / Q7 集中攻击独立随机 / Q8 眩晕全队停手
#   工程默认 E1-E8(随机种子、100回合上限、伤害取整、无头回退、末位存活手、即时死亡、平局、插件不可被攻击)
# 所有待 Akun 拍板的点都做成 RuleConfig 开关,方便 A/B 模拟。
import copy
import math
import random
from dataclasses import dataclass, field, asdict

from .parts import Part


@dataclass
class RuleConfig:
    initiative_mode: str = "per_round"   # per_round=每回合重掷(v2 原文倾向) / once=开局掷一次(评审建议 A/B 项)
    head_vs_head_prob: float = 0.5       # 头攻击:50% 打头
    block_prob: float = 0.20             # 手部格挡概率
    block_mult: float = 0.80             # 格挡后伤害倍率(转给末位存活手)
    dodge_leg_slots: int = 2             # 只有腿1、腿2 提供闪避
    round_limit: int = 100               # E2
    stun_scope: str = "all"              # all=全队下回合不攻击(Q8 推荐) / heads=仅头不攻击(备选 A/B)
    legs_attack: bool = True             # False=腿默认不攻击(Codex 语法调整 A/B 项)


@dataclass
class Monster:
    name: str
    torso: Part
    heads: list = field(default_factory=list)
    hands: list = field(default_factory=list)
    legs: list = field(default_factory=list)
    tails: list = field(default_factory=list)

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

    def energy_used(self) -> int:
        return sum(p.energy for p in self.all_parts() if p.kind != "torso") \
            + sum(t.energy for t in self.tails)

    def price_total(self) -> int:
        return sum(p.price for p in self.all_parts()) + sum(t.price for t in self.tails)


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
    winner = None
    first_key_locked = None  # initiative_mode=once 时锁定

    def log(round_no, etype, **kw):
        events.append(dict(round=round_no, type=etype, **kw))

    def enemy_key(k):
        return "B" if k == "A" else "A"

    def check_end(atk_key):
        nonlocal winner
        if not sides[enemy_key(atk_key)].torso.alive():
            winner = atk_key

    def choose_target(kind, defender):
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

    def resolve(round_no, atk_key, attacker: Part):
        def_key = enemy_key(atk_key)
        defender = sides[def_key]
        target = choose_target(attacker.kind, defender)
        # 1) 闪避(全身共享,实时计算)
        dv = defender.dodge_total(cfg)
        if dv > 0 and rng.random() < dv:
            log(round_no, "dodge", side=atk_key, attacker=attacker.label,
                target=target.label, dodge=round(dv, 2))
            return
        dmg = attacker.atk
        # 2) 格挡:头/躯干被攻击 + 有存活手 → 20%,伤害×80% 转末位存活手(E5)
        blockers = [h for h in defender.hands if h.alive()]
        if target.kind in ("head", "torso") and blockers and rng.random() < cfg.block_prob:
            blocker = max(blockers, key=lambda h: h.slot)
            bdmg = max(1, math.floor(dmg * cfg.block_mult)) if dmg > 0 else 0
            blocker.hp -= bdmg
            log(round_no, "block", side=atk_key, attacker=attacker.label,
                target=target.label, blocker=blocker.label, dmg=dmg, taken=bdmg,
                blocker_hp=max(blocker.hp, 0))
            if not blocker.alive():
                log(round_no, "break", side=def_key, part=blocker.label, kind="hand")
            return
        # 3) 正常结算(E6 即时死亡)
        target.hp -= dmg
        log(round_no, "hit", side=atk_key, attacker=attacker.label,
            target=target.label, dmg=dmg, target_hp=max(target.hp, 0))
        if not target.alive():
            log(round_no, "break", side=def_key, part=target.label, kind=target.kind)
            if target.kind == "head":
                stun_next[def_key] = True
                log(round_no, "stun_set", side=def_key)
            if target.kind == "torso":
                check_end(atk_key)

    round_no = 0
    for round_no in range(1, cfg.round_limit + 1):
        # 先攻(Q4 推荐:P(A先) = A先攻/(A+B);双 0 → 50/50)
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

        # 眩晕消费:本回合停手,标记清空(本回合再破头会重新标记到下回合)
        skip = {k: stun_next[k] for k in ("A", "B")}
        for k in ("A", "B"):
            if skip[k]:
                log(round_no, "stunned", side=k)
            stun_next[k] = False

        phases = ["leg", "hand", "head"] if cfg.legs_attack else ["hand", "head"]
        for kind in phases:
            fp = [p for p in sides[first_key].parts_of(kind) if p.alive()]
            sp = [p for p in sides[second_key].parts_of(kind) if p.alive()]
            for who, part in _interleave(fp, sp):
                atk_key = first_key if who == "first" else second_key
                if winner or skip[atk_key] or not part.alive() or part.atk <= 0:
                    continue
                resolve(round_no, atk_key, part)
            if winner:
                break
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
        "final": {k: [dict(name=p.label, hp=max(p.hp, 0), max_hp=p.max_hp)
                      for p in m.all_parts()] for k, m in sides.items()},
        "config": asdict(cfg),
        "seed": seed,
    }
