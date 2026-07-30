# run 经济模拟:升本(躯干进化)值不值,第几战开始划算
#
#   python3 -m sim.run_sim --games 40
#
# 背景:Akun Q18d 点名「让AI来设计模拟」躯干进化的档位数值。护栏(已定):升本不加血。
# 数值提案在 engine.TORSO_TIERS(I→II 300:+15供能+1四肢槽;II→III 550:+15供能+1头槽+1指挥)。
#
# 实验设计 —— 等财富对撞:
#   升本的代价和收益都发生在同一个预算里(升本花掉的钱就买不了零件),所以判断"值不值"
#   最干净的做法不是打 PVE,而是让**同样有钱**的两个玩家对打:一个升了本、一个没升。
#   赢面 >50% = 这个财富档位上升本划算。财富曲线直接取 demo 里「称霸荒野」的真实数值。
#
# 采样口径与 meta.py 一致(第二批全量零件池),只是预算随战次变化、并给 Monster 打上 tier。
import argparse
import random

from . import meta
from .engine import Monster, RuleConfig, TORSO_TIERS, battle
from .parts import make, PLUGINS

# 「称霸荒野」真实财富曲线(design/play/index.html:起始 800,五场荒野各 +300,第 6 场是关底 Boss)
WEALTH = [
    ("第1战 荒野1", 800),
    ("第2战 荒野2", 1100),
    ("第3战 荒野3", 1400),
    ("第4战 荒野4", 1700),
    ("第5战 荒野5", 2000),
    ("第6战 Boss", 2300),
]
SAMPLE = 600        # 每个(财富, 档位)采样配装数
TOP_N = 8           # 各自取前 N 名互打,避免"一个冠军"的噪声
QUAL_GAMES = 24     # 海选:同池内互打场次
CROSS_GAMES = 40    # 决赛:跨档位每对场次(两个方向各半,抵消先后手)


# 候选升本数值方案(--table)。第一轮实测:sol 方案在所有财富档都是纯亏(见报告),
# 病因=真正卡住玩家的是**指挥点**不是槽位/供能,而 sol 方案刻意不给 II 指挥。
# 后续方案沿两条轴调:① 给不给指挥 ② 价格向公式价(1供能=5价、四肢插槽=30)靠拢。
TIER_TABLES = {
    # sol 第六轮原案
    "sol": {1: dict(price=0, supply=0, limb=0, head=0, command=0),
            2: dict(price=300, supply=15, limb=1, head=0, command=0),
            3: dict(price=550, supply=15, limb=0, head=1, command=1)},
    # 只把价格降到公式价附近,仍不给指挥 —— 隔离"是不是纯粹太贵"
    "cheap": {1: dict(price=0, supply=0, limb=0, head=0, command=0),
              2: dict(price=110, supply=15, limb=1, head=0, command=0),
              3: dict(price=200, supply=15, limb=0, head=1, command=1)},
    # 两档都给指挥,价格中档 —— 隔离"是不是必须给指挥"
    "cmd": {1: dict(price=0, supply=0, limb=0, head=0, command=0),
            2: dict(price=300, supply=15, limb=1, head=0, command=1),
            3: dict(price=550, supply=15, limb=0, head=1, command=1)},
    # 给指挥 + 价格贴公式(指挥按"约等于一件中档零件"计) —— 候选正式方案
    "cmd_cheap": {1: dict(price=0, supply=0, limb=0, head=0, command=0),
                  2: dict(price=200, supply=15, limb=1, head=0, command=1),
                  3: dict(price=350, supply=15, limb=0, head=1, command=1)},
    # 等级门专用(配 --gate):升本本身只给最小容量,价值全部来自"商店能出现更好的零件"
    "gate": {1: dict(price=0, supply=0, limb=0, head=0, command=0),
             2: dict(price=200, supply=15, limb=1, head=0, command=1),
             3: dict(price=350, supply=15, limb=0, head=1, command=1)},
}


def upgrade_cost(tier):
    return sum(TORSO_TIERS[t]["price"] for t in range(2, tier + 1))


def build_tiered(spec, tier):
    """按 meta 的口径造怪,但带升本档位:升本送的槽位可以少买插槽件。"""
    tb = {"limb": 0, "head": 0}
    for t in range(2, tier + 1):
        tb["limb"] += TORSO_TIERS[t]["limb"]
        tb["head"] += TORSO_TIERS[t]["head"]
    n_limbs = len(spec["hands"]) + len(spec["legs"])
    slots = (["头部插槽"] * max(0, len(spec["heads"]) - 1 - tb["head"])
             + ["四肢插槽"] * max(0, n_limbs - 4 - tb["limb"]))
    m = Monster(
        name=f"T{tier}·{meta.label(spec)}",
        torso=make(spec["torso"], 0, spec.get("torso_plugin", "")),
        heads=[meta._mk(n, i) for i, n in enumerate(spec["heads"])],
        hands=[meta._mk(n, i) for i, n in enumerate(spec["hands"])],
        legs=[meta._mk(n, i) for i, n in enumerate(spec["legs"])],
        tails=[meta._mk(n, i) for i, n in enumerate(spec["tails"])],
        slots=[make(n, i + 1) for i, n in enumerate(slots)],
        tier=tier,
    )
    return m


# 零件等级(用户提案:升本同时提高商店可出现的配件等级)。价格天然分档,不用 Akun 重新定表:
#   T1 ≤100(新手件) T2 ≤250(普通手/腿) T3 ≤400(普通头) T4 ≥550(机制头)
def part_tier(name):
    pr = meta.CATALOG[name]["price"]
    return 1 if pr <= 100 else 2 if pr <= 250 else 3 if pr <= 400 else 4


MAX_PART_TIER = {1: 2, 2: 3, 3: 4}    # 本级 → 商店最高可出现的零件等级


def _pools():
    return (meta.HEADS + meta.MECH_HEADS, meta.HANDS + meta.MECH_HANDS,
            meta.LEGS, meta.TAILS, meta.TORSOS)


def gen_spec_budget(rng, room, tier, gate=False):
    """增量式采购采样:先挑买得起的躯干,再一件件加零件直到钱花光/收手。

    meta.gen_spec 是「先随机生成再按价格拒收」,在 run 的低预算档(500-800)拒收率极高
    (实测 20s 才采出 40 个)。run 模拟要跑 6 个财富档 × 3 个档位,必须换增量采样。
    """
    heads_p, hands_p, legs_p, tails_p, torsos_p = _pools()
    if gate:   # 等级门:本级不够高的零件根本不会出现在货架上
        cap = MAX_PART_TIER[tier]
        heads_p = [n for n in heads_p if part_tier(n) <= cap] or heads_p[:1]
        hands_p = [n for n in hands_p if part_tier(n) <= cap]
        legs_p = [n for n in legs_p if part_tier(n) <= cap]
    tb = {"limb": 0, "head": 0}
    for t in range(2, tier + 1):
        tb["limb"] += TORSO_TIERS[t]["limb"]
        tb["head"] += TORSO_TIERS[t]["head"]

    aff_torsos = [t for t in torsos_p if meta.CATALOG[t]["price"] <= room - 100]
    if not aff_torsos:
        return None
    spec = dict(torso=rng.choice(aff_torsos), torso_plugin="",
                heads=[], hands=[], legs=[], tails=[])
    left = room - meta.CATALOG[spec["torso"]]["price"]
    if rng.random() < 0.35 and left >= 100:
        spec["torso_plugin"] = rng.choice(["普通能量核心", "耐火皮肤", "尖刺皮肤",
                                           "耐毒皮肤", "耐冰皮肤"])
        left -= PLUGINS[spec["torso_plugin"]]["price"]

    def cur():
        return build_tiered(spec, tier)

    for _ in range(12):
        if rng.random() < 0.10:
            break
        n_limbs = len(spec["hands"]) + len(spec["legs"])
        opts = []
        if len(spec["heads"]) < 1 + tb["head"] + 1:      # 允许最多再买 1 个头部插槽
            opts.append(("heads", heads_p))
        if n_limbs < 4 + tb["limb"] + 2:                 # 允许最多再买 2 个四肢插槽
            opts += [("hands", hands_p), ("legs", legs_p)]
        if not spec["tails"]:
            opts.append(("tails", tails_p))
        rng.shuffle(opts)
        added = False
        for key, pool in opts:
            cands = [c for c in pool if meta.CATALOG[c]["price"] <= left]
            if not cands:
                continue
            name = rng.choice(cands)
            kind = {"heads": "head", "hands": "hand", "legs": "leg", "tails": "tail"}[key]
            entry = meta._entry(rng, name, kind, True)
            spec[key].append(entry)
            m2 = cur()
            if (m2.energy_used() > m2.supply_total()
                    or m2.price_total() > room + upgrade_cost(tier)):
                spec[key].pop()
                continue
            left = room + upgrade_cost(tier) - m2.price_total()
            added = True
            break
        if not added:
            break
    if not (spec["heads"] or spec["hands"] or spec["legs"]):
        return None
    for key in ("heads", "hands", "legs", "tails"):
        spec[key] = sorted(spec[key], key=str)
    return spec


def sample_pool(rng, wealth, tier, n=SAMPLE, gate=False):
    """采样 n 个「该档位下合法、且把钱基本花完」的配装。升本费已计入 price_total。"""
    floor = int(wealth * 0.85)
    room = wealth - upgrade_cost(tier)
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < n * 40:
        tries += 1
        spec = gen_spec_budget(rng, room, tier, gate)
        if spec is None:
            continue
        m = build_tiered(spec, tier)
        if m.energy_used() > m.supply_total():
            continue
        if not floor <= m.price_total() <= wealth:
            continue
        if m.name in seen:
            continue
        seen.add(m.name)
        out.append((spec, m))
    return out


def _duel(a, b, games, seed0):
    wa = 0
    for g in range(games):
        # 一半局交换先后手,抵消侧偏
        x, y = (a, b) if g % 2 == 0 else (b, a)
        r = battle(x, y, seed=seed0 + g, cfg=meta_cfg)
        if r["winner"] == ("A" if g % 2 == 0 else "B"):
            wa += 1
    return wa


def qualify(pool, seed0):
    """池内随机对打海选,取胜场前 TOP_N。"""
    rng = random.Random(seed0)
    score = [0] * len(pool)
    for i, (_, m) in enumerate(pool):
        for g in range(QUAL_GAMES):
            j = rng.randrange(len(pool))
            if j == i:
                continue
            r = battle(m, pool[j][1], seed=seed0 + i * 1000 + g, cfg=meta_cfg)
            if r["winner"] == "A":
                score[i] += 1
    order = sorted(range(len(pool)), key=lambda i: -score[i])[:TOP_N]
    return [pool[i] for i in order]


def cross(top_hi, top_lo, seed0):
    """跨档位互打,返回高档位一方的胜率。"""
    wins = tot = 0
    for i, (_, hi) in enumerate(top_hi):
        for j, (_, lo) in enumerate(top_lo):
            wins += _duel(hi, lo, CROSS_GAMES, seed0 + (i * 100 + j) * 1000)
            tot += CROSS_GAMES
    return wins / tot


def shape(specs):
    n = len(specs)
    return (f"头{sum(len(s['heads']) for s, _ in specs)/n:.1f}"
            f"/手{sum(len(s['hands']) for s, _ in specs)/n:.1f}"
            f"/腿{sum(len(s['legs']) for s, _ in specs)/n:.1f}")


def hand_major(specs):
    n = len(specs)
    return sum(1 for s, _ in specs
               if len(s["hands"]) > len(s["legs"]) + len(s["tails"])) / n


meta_cfg = RuleConfig()


def main():
    global meta_cfg
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="batch2")
    ap.add_argument("--tiers", default="1,2,3")
    ap.add_argument("--gate", action="store_true",
                    help="等级门模式:升本同时解锁更高等级的零件(用户提案)")
    ap.add_argument("--table", default="sol", choices=sorted(TIER_TABLES),
                    help="升本数值方案(见 TIER_TABLES)")
    args = ap.parse_args()
    TORSO_TIERS.clear()
    TORSO_TIERS.update(TIER_TABLES[args.table])
    print(f"# 升本数值方案:{args.table} = {TIER_TABLES[args.table]}")
    meta_cfg = meta.apply_variant(args.variant)
    tiers = [int(t) for t in args.tiers.split(",")]

    print(f"# 升本回本窗口模拟(变体 {args.variant})")
    print(f"# 每档采样 {SAMPLE} 配装 → 海选前 {TOP_N} → 跨档 {TOP_N}×{TOP_N}×{CROSS_GAMES} 局")
    print(f"# 升本费:II={upgrade_cost(2)} III={upgrade_cost(3)}(计入配装总价)\n")

    tops = {}
    for label, wealth in WEALTH:
        row = {}
        for t in tiers:
            if upgrade_cost(t) > wealth - 400:      # 升完本连一套像样的零件都买不起,视为不可选
                continue
            rng = random.Random(7 + t * 13)
            pool = sample_pool(rng, wealth, t, gate=args.gate)
            if len(pool) < TOP_N * 2:
                continue
            row[t] = qualify(pool, seed0=1000 * t + wealth)
        tops[label] = row

        bits = []
        for t in sorted(row):
            bits.append(f"T{t}(n={len(row[t])} {shape(row[t])} 手多数{hand_major(row[t]):.0%})")
        print(f"{label}  预算 {wealth}  " + "  ".join(bits))

    print("\n## 等财富对撞:升本方胜率(>50% = 这个财富档升本划算)\n")
    print("| 战次 | 预算 | II vs I | III vs II | III vs I |")
    print("|---|---|---|---|---|")
    for label, wealth in WEALTH:
        row = tops[label]
        def cell(hi, lo):
            if hi not in row or lo not in row:
                return "—"
            w = cross(row[hi], row[lo], seed0=wealth * 7 + hi * 31 + lo)
            mark = " ✅" if w > 0.55 else (" ❌" if w < 0.45 else "")
            return f"{w:.0%}{mark}"
        print(f"| {label} | {wealth} | {cell(2,1)} | {cell(3,2)} | {cell(3,1)} |")


if __name__ == "__main__":
    main()
