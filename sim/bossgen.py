# 称霸荒野 · Boss/中途怪候选生成器(Q18b:Akun 说"首批 BOSS 池可以先模拟一批出来看看")
#   python3 -m sim.bossgen [--seed 7]
# 中途怪:各预算档随机采样 → 按"对同档玩家参照池的胜率"落在目标带筛选(中途怪目标 35-55%)。
# 关底 Boss:手写骨架(一 Boss 一机制个性,IP 恶搞名由 Akun 定)× 变体 → 同法标定给他挑。
# ⚠️ 预算曲线/胜率目标带均为工程默认(待定),Akun 可直接改本文件顶部常量。
import argparse
import random
from collections import Counter

from .engine import RuleConfig, battle
from .meta import (HEADS, HANDS, LEGS, TAILS, TORSOS, MECH_HEADS, MECH_HANDS,
                   _entry, build, label)

# 荒野关预算曲线(工程默认待定):(关名, 敌方预算, 玩家参照预算, 是否用机制件池)
TIERS = [
    ("荒野1", 700, 800, False),
    ("荒野2", 1000, 1100, False),
    ("荒野3", 1300, 1400, True),
    ("荒野4", 1600, 1700, True),
    ("荒野5", 2000, 2000, True),
]
MID_BAND = (0.35, 0.55)     # 中途怪目标胜率带(对同档玩家:略亏->略强,可连打)
BOSS_BAND = (0.60, 0.85)    # 关底 Boss 目标带(要有压迫感但可解)
REF_N = 30                  # 玩家参照池大小
GAMES_PER_REF = 16          # 每个参照对手打几局(两方向各半)
CAND_N = 120                # 每档采样候选数

# 关底 Boss 骨架(机制个性;名字是 Akun 的 IP 恶搞方向,最终由他定)
# 每只给 2-3 个预算变体,标定后由 Akun 挑强度
BOSS_SKELETONS = {
    "弟斯拉(喷火巨兽)": [
        dict(torso="有些肌肉的躯干", torso_plugin="耐火皮肤",
             heads=["喷火头"], hands=["猛爪", "猛爪"], legs=["猛腿"], tails=["猛尾"]),
        dict(torso="有些肌肉的躯干", torso_plugin="耐火皮肤",
             heads=["喷火头"], hands=["强力爪", "猛爪"], legs=["猛腿", "猛腿"], tails=["猛尾"]),
    ],
    "新栗欧克(三头龙)": [
        dict(torso="有些肌肉的躯干", torso_plugin="",
             heads=["肿头", "肿头", "顶撞头"], hands=[], legs=["新手腿"], tails=[]),
        dict(torso="有些肌肉的躯干", torso_plugin="",
             heads=["肿头", "顶撞头", "顶撞头"], hands=["新手手"], legs=[], tails=[]),
    ],
    "银刚(巨臂猿)": [
        dict(torso="有些肌肉的躯干", torso_plugin="",
             heads=["新手头"], hands=["抓握手", "强力爪", "强力爪"], legs=["新手腿"], tails=[]),
        dict(torso="有些肌肉的躯干", torso_plugin="尖刺皮肤",
             heads=["猛头"], hands=[("抓握手", "骨盾"), "强力爪", "强力爪"], legs=[], tails=[]),
    ],
}


def sample_spec(rng, budget, mech, lo_ratio=0.8):
    """按预算窗口 [budget*lo_ratio, budget] 拒绝采样一个合法配装(meta.gen_spec 的预算参数化版)。"""
    heads_pool = HEADS + (MECH_HEADS if mech else [])
    hands_pool = HANDS + (MECH_HANDS if mech else [])
    while True:
        torso = rng.choice(TORSOS)
        n_heads = rng.choice([0, 1, 1, 1, 2])
        n_hands = rng.randint(0, 4)
        n_legs = rng.randint(0, 4)
        n_tails = rng.choice([0, 0, 0, 1])
        if not 1 <= n_hands + n_legs + n_tails + n_heads <= 7:
            continue
        if mech:
            tp = rng.choice(["", "", "普通能量核心", "耐火皮肤", "尖刺皮肤", "普通能量核心"]) \
                if rng.random() < 0.5 else ""
        else:
            tp = "普通能量核心" if rng.random() < 0.25 else ""
        spec = dict(
            torso=torso, torso_plugin=tp,
            heads=sorted((_entry(rng, rng.choice(heads_pool), "head", mech) for _ in range(n_heads)), key=str),
            hands=sorted((_entry(rng, rng.choice(hands_pool), "hand", mech) for _ in range(n_hands)), key=str),
            legs=sorted((_entry(rng, rng.choice(LEGS), "leg", mech) for _ in range(n_legs)), key=str),
            tails=sorted(rng.choice(TAILS) for _ in range(n_tails)),
        )
        m = build(spec)
        if m.energy_used() > m.supply_total():
            continue
        if not budget * lo_ratio <= m.price_total() <= budget:
            continue
        return spec


def winrate_vs_pool(spec, pool, cfg, seed0):
    """候选对参照池的平均胜率(两方向各半抵消先后手噪声)。"""
    mon = build(spec)
    wins = games = 0
    for j, ref in enumerate(pool):
        rmon = build(ref)
        for g in range(GAMES_PER_REF):
            seed = seed0 + j * 1000 + g
            if g % 2 == 0:
                rep = battle(mon, rmon, seed=seed, cfg=cfg)
                wins += rep["winner"] == "A"
            else:
                rep = battle(rmon, mon, seed=seed, cfg=cfg)
                wins += rep["winner"] == "B"
            games += 1
    return wins / games


def sig(spec):
    """构成签名(用于多样性去重):躯干+头手腿数目+是否带机制件。"""
    mech_bits = any(isinstance(e, (tuple, list)) for e in
                    [*spec["heads"], *spec["hands"], *spec["legs"]]) or spec.get("torso_plugin")
    return (spec["torso"], len(spec["heads"]), len(spec["hands"]), len(spec["legs"]),
            bool(mech_bits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    cfg = RuleConfig()

    print("# 称霸荒野 · 候选标定(seed=%d;胜率=对同档玩家参照池,50%%=势均力敌)\n" % args.seed)

    for tier, ebud, pbud, mech in TIERS:
        pool = [sample_spec(rng, pbud, mech) for _ in range(REF_N)]
        cands, seen = [], set()
        for _ in range(CAND_N):
            s = sample_spec(rng, ebud, mech)
            k = label(s)
            if k in seen:
                continue
            seen.add(k)
            cands.append(s)
        rated = [(winrate_vs_pool(s, pool, cfg, args.seed * 10000), s) for s in cands]
        in_band = [(w, s) for w, s in rated if MID_BAND[0] <= w <= MID_BAND[1]]
        in_band.sort(key=lambda x: abs(x[0] - 0.45))
        picked, used_sig = [], set()
        for w, s in in_band:
            if sig(s) in used_sig:
                continue
            used_sig.add(sig(s))
            picked.append((w, s))
            if len(picked) >= 6:
                break
        print(f"## {tier}(敌方预算 {ebud} vs 玩家 {pbud};池内命中带 {len(in_band)}/{len(cands)})")
        print("| 候选 | 价 | 对玩家胜率 |")
        print("|---|---|---|")
        for w, s in picked:
            print(f"| {label(s)} | {build(s).price_total()} | {w:.0%} |")
        print()

    print("## 关底 Boss 骨架标定(对玩家 2000 参照池;目标带 %d%%-%d%%)" %
          (BOSS_BAND[0] * 100, BOSS_BAND[1] * 100))
    pool = [sample_spec(rng, 2000, True) for _ in range(REF_N)]
    print("| Boss | 变体 | 价 | 对玩家胜率 | 带内? |")
    print("|---|---|---|---|---|")
    for name, variants in BOSS_SKELETONS.items():
        for i, s in enumerate(variants):
            s.setdefault("tails", [])
            m = build(s)
            if m.energy_used() > m.supply_total():
                print(f"| {name} | v{i+1} ⚠️ 能量超限 | {m.price_total()} | - | - |")
                continue
            w = winrate_vs_pool(s, pool, cfg, args.seed * 20000 + i)
            band = "✅" if BOSS_BAND[0] <= w <= BOSS_BAND[1] else "❌"
            print(f"| {name} | v{i+1}:{label(s)} | {m.price_total()} | {w:.0%} | {band} |")


if __name__ == "__main__":
    main()
