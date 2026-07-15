# 随机配装元游戏研究:固定预算采样合法配装 → 两阶段淘汰 → 顶层构成分析
# 目的:替代"手捏流派"评估平衡改动(2026-07-12 诊断:手捏流派五连误判)
#   python3 -m sim.meta --variant baseline
# 2026-07-15 起 baseline = Akun 新零件表(躯干指挥 2/3/3、价 350/700/700、供能 30/60/80)
#   变体:muscle2(肌肉躯干指挥 3→2,即 meta 报告原推荐 2/3/2)/ atk15 / hand125 / combo
import argparse
import random
from collections import Counter

from .engine import Monster, RuleConfig, battle
from .parts import make, CATALOG

HEADS = ["新手头", "猛头", "顶撞头", "肿头"]
HANDS = ["新手手", "猛爪", "强力爪", "小手手"]
LEGS = ["新手腿", "猛腿", "鞭腿", "灵活的腿", "踢腿"]
TAILS = ["新手尾巴", "猛尾"]
TORSOS = ["新手躯干", "稍微长大的躯干", "有些肌肉的躯干"]

BUDGET = 1800
MIN_PRICE = 1500          # 只研究"把预算基本花完"的配装,避免便宜垫底货污染统计
SAMPLE = 1200
STAGE1_GAMES = 80
TOP_N = 40
STAGE2_GAMES = 60         # 每对(两个方向各半,抵消 A/B 侧噪声)


def apply_variant(variant):
    """按变体重定价/改规则。返回 RuleConfig。"""
    if variant == "atk15":
        # 现行公式(Akun 2026-07-15):价 = 10*攻 + 2*血 + 5*供能 + 机动溢价(先攻/闪避)
        # 变体:攻击系数 10 → 15(攻击会滚雪球,血不会——诊断报告的价格层修法)
        for name, s in CATALOG.items():
            base_old = 10 * s.get("atk", 0) + 2 * s.get("hp", 0) + 5 * s.get("supply", 0)
            premium = s.get("price", 0) - base_old
            if s.get("price", 0) > 0:
                s["price"] = 15 * s.get("atk", 0) + 2 * s.get("hp", 0) + 5 * s.get("supply", 0) + premium
    elif variant == "hand125":
        for name, s in CATALOG.items():
            if s.get("kind") == "hand" and s.get("price", 0) > 0:
                s["price"] = round(s["price"] * 1.25)
    elif variant == "muscle2":
        CATALOG["有些肌肉的躯干"]["command"] = 2   # Akun 2/3/3 → meta 报告原推荐 2/3/2
    elif variant == "combo":
        CATALOG["有些肌肉的躯干"]["command"] = 2
        for name, s in CATALOG.items():
            if s.get("kind") == "hand" and s.get("price", 0) > 0:
                s["price"] = round(s["price"] * 1.25)
    return RuleConfig()


def gen_spec(rng):
    """拒绝采样一个合法(能量/槽位/预算)且花钱 ≥ MIN_PRICE 的配装。"""
    while True:
        torso = rng.choice(TORSOS)
        n_heads = rng.choice([0, 1, 1, 1, 2])
        n_hands = rng.randint(0, 4)
        n_legs = rng.randint(0, 4)
        n_tails = rng.choice([0, 0, 0, 1])   # 尾巴独立位,限 1(Akun 2026-07-15)
        n_core = rng.choice([0, 0, 0, 1])    # 普通能量核心(供能+20,限 1)
        if not 1 <= n_hands + n_legs + n_tails + n_heads <= 7:
            continue
        spec = dict(
            torso=torso,
            heads=sorted(rng.choice(HEADS) for _ in range(n_heads)),
            hands=sorted(rng.choice(HANDS) for _ in range(n_hands)),
            legs=sorted(rng.choice(LEGS) for _ in range(n_legs)),
            tails=sorted(rng.choice(TAILS) for _ in range(n_tails)),
            core=n_core,
        )
        m = build(spec)
        if m.energy_used() > m.supply_total():
            continue
        if not MIN_PRICE <= m.price_total() <= BUDGET:
            continue
        return spec


def build(spec):
    n_limbs = len(spec["hands"]) + len(spec["legs"])   # 尾巴不占四肢槽
    slots = (["头部插槽"] * max(0, len(spec["heads"]) - 1)
             + ["四肢插槽"] * max(0, n_limbs - 4)
             + ["普通能量核心"] * spec.get("core", 0))
    return Monster(
        name=label(spec),
        torso=make(spec["torso"]),
        heads=[make(n, i + 1) for i, n in enumerate(spec["heads"])],
        hands=[make(n, i + 1) for i, n in enumerate(spec["hands"])],
        legs=[make(n, i + 1) for i, n in enumerate(spec["legs"])],
        tails=[make(n, i + 1) for i, n in enumerate(spec["tails"])],
        slots=[make(n, i + 1) for i, n in enumerate(slots)],
    )


def label(spec):
    def grp(names):
        c = Counter(names)
        return "+".join(f"{n}x{k}" if k > 1 else n for n, k in sorted(c.items()))
    bits = [spec["torso"].replace("的躯干", "").replace("躯干", "")]
    for key in ("heads", "hands", "legs", "tails"):
        if spec[key]:
            bits.append(grp(spec[key]))
    if spec.get("core"):
        bits.append("能量核心")
    return "|".join(bits)


def dedupe(specs):
    seen, out = set(), []
    for s in specs:
        k = label(s)
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def comp_stats(specs):
    n = len(specs)
    headless = sum(1 for s in specs if not s["heads"]) / n
    hand_major = sum(1 for s in specs
                     if len(s["hands"]) > len(s["legs"]) + len(s["tails"])) / n
    return (f"无头 {headless:.0%},手占多数 {hand_major:.0%},"
            f"平均 头{sum(len(s['heads']) for s in specs)/n:.1f}"
            f"/手{sum(len(s['hands']) for s in specs)/n:.1f}"
            f"/腿{sum(len(s['legs']) for s in specs)/n:.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline",
                    choices=["baseline", "muscle2", "atk15", "hand125", "combo"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    cfg = apply_variant(args.variant)
    rng = random.Random(args.seed)
    specs = dedupe([gen_spec(rng) for _ in range(SAMPLE)])
    mons = [build(s) for s in specs]
    n = len(specs)
    print(f"# 变体 {args.variant}:{n} 个去重合法配装(预算 {MIN_PRICE}-{BUDGET})")
    print(f"样本构成:{comp_stats(specs)}")

    # 阶段1:每个配装打 STAGE1_GAMES 场随机对手
    wins = [0.0] * n
    battle_id = 0
    for i in range(n):
        for _ in range(STAGE1_GAMES):
            j = rng.randrange(n - 1)
            j = j if j < i else j + 1
            rep = battle(mons[i], mons[j], seed=battle_id)
            battle_id += 1
            wins[i] += 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
    order = sorted(range(n), key=lambda i: -wins[i])
    top = order[:TOP_N]

    # 阶段2:前 TOP_N 循环赛(双方向)
    score = {i: 0.0 for i in top}
    for a in top:
        for b in top:
            if a >= b:
                continue
            for g in range(STAGE2_GAMES // 2):
                rep = battle(mons[a], mons[b], seed=battle_id); battle_id += 1
                score[a] += 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
                score[b] += 1.0 if rep["winner"] == "B" else (0.5 if rep["winner"] == "draw" else 0.0)
                rep = battle(mons[b], mons[a], seed=battle_id); battle_id += 1
                score[b] += 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
                score[a] += 1.0 if rep["winner"] == "B" else (0.5 if rep["winner"] == "draw" else 0.0)
    games_each = (TOP_N - 1) * STAGE2_GAMES
    final = sorted(top, key=lambda i: -score[i])

    print(f"\n## 决赛圈前 10(共 {TOP_N} 进入循环赛,每人 {games_each} 局)")
    print("| # | 配装 | 决赛胜率 | 价 | 头/手/腿 |")
    print("|---|---|---|---|---|")
    for rank, i in enumerate(final[:10], 1):
        s = specs[i]
        print(f"| {rank} | {label(s)} | {score[i]/games_each:.0%} | {mons[i].price_total()} "
              f"| {len(s['heads'])}/{len(s['hands'])}/{len(s['legs'])} |")
    print(f"\n决赛圈 40 强构成:{comp_stats([specs[i] for i in top])}")
    print(f"决赛圈前 10 构成:{comp_stats([specs[i] for i in final[:10]])}")


if __name__ == "__main__":
    main()
