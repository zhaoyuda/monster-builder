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
# 机制件与插件(--variant mech 时进入采样池;Q17 机制引擎 2026-07-15)
MECH_HEADS = ["喷火头"]
MECH_HANDS = ["抓握手", "长有芽孢的手"]
PLUGINS_BY_KIND = {
    "head": ["头顶角质层", "头顶尖刺"],
    "hand": ["骨盾", "胶质瘤", "爆裂腺体", "撕裂爪"],
    "leg":  ["肾上腺素", "爆裂腺体", "碎骨锥"],
    "torso": ["耐火皮肤", "尖刺皮肤", "普通能量核心"],
}
PLUGIN_PROB = 0.35   # 每个部件挂插件的采样概率(躯干单独 0.5)

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
    # —— 腿灭绝专项(2026-07-18):腿在所有既往变体前十平均 0.0-0.4,找哪个杠杆能救回来 ——
    elif variant == "init_once":
        return RuleConfig(initiative_mode="once")      # W2 遗留 A/B:先攻只掷一次,先手更值钱
    elif variant == "dodge_all":
        return RuleConfig(dodge_leg_slots=99)          # 全部腿都提供闪避(现行只有腿1、腿2)
    elif variant == "legmob":
        # 机动性免费:腿价回落到纯公式价(10*攻+2*血),先攻/闪避溢价 40/30 清零
        for name, s in CATALOG.items():
            if s.get("kind") == "leg" and s.get("price", 0) > 0 and not name.startswith("装饰"):
                s["price"] = 10 * s.get("atk", 0) + 2 * s.get("hp", 0)
    elif variant == "leg50":
        # 清算价探针:腿半价——如果这样腿还进不了前十,问题就不在价格层
        for name, s in CATALOG.items():
            if s.get("kind") == "leg" and s.get("price", 0) > 0 and not name.startswith("装饰"):
                s["price"] = round(s["price"] * 0.5)
    elif variant == "leg_hunt":
        # 结构修法:腿的索敌 腿→手(打光回退默认)。边际对照里踢腿 0.4%→38%,双踢腿 44.9%
        for name, s in CATALOG.items():
            if s.get("kind") == "leg" and s.get("atk", 0) > 0:
                s["hunts"] = "hand"
    elif variant == "leg_fix":
        # 组合:腿打手 + 机动溢价清零(温和降价)——结构修法之后价格才有意义
        for name, s in CATALOG.items():
            if s.get("kind") == "leg" and s.get("price", 0) > 0 and not name.startswith("装饰"):
                s["hunts"] = "hand"
                s["price"] = 10 * s.get("atk", 0) + 2 * s.get("hp", 0)
    elif variant == "mech_status1":
        # Q19b A/B(Akun 2026-07-21 反问):异常状态单栏位(新顶旧) vs 共存(现行)
        # 采样池同 mech(插件挂载),规则改 status_slots=single
        return RuleConfig(status_slots="single")
    elif variant == "batch2_tent_rand":
        # A/B:触手战吼旧口径(全池随机)vs Akun 2026-07-27 拍板的「优先缠手」(现行默认)
        TORSOS.extend(["强能躯干", "臃肿的躯干"])
        LEGS.extend(["闪避腿", "高鞭腿", "连环腿", "黏腿", "震撼腿"])
        MECH_HEADS.extend(["喷毒头", "喷冰头", "伸缩头", "蓄力头"])
        MECH_HANDS.extend(["刺拳手", "触手", "蓄力拳", "残像拳"])
        PLUGINS_BY_KIND["head"] = PLUGINS_BY_KIND["head"] + ["头槌"]
        PLUGINS_BY_KIND["hand"] = PLUGINS_BY_KIND["hand"] + ["认真一拳"]
        PLUGINS_BY_KIND["leg"] = PLUGINS_BY_KIND["leg"] + ["先守后攻"]
        PLUGINS_BY_KIND["torso"] = PLUGINS_BY_KIND["torso"] + ["耐毒皮肤", "耐冰皮肤"]
        PLUGINS_BY_KIND["tail"] = ["火蜥蜴尾巴", "毒蛇尾巴", "冰虫尾巴"]
        return RuleConfig(entangle_prefer_hand=False)
    elif variant == "batch2a":
        # Akun 2026-07-22 第二批纯数值件探针:新躯干×2(⚠️ 臃肿指挥4=敏感参数)+ 闪避腿
        TORSOS.extend(["强能躯干", "臃肿的躯干"])
        LEGS.append("闪避腿")
    elif variant in ("pos1", "pos2", "pos3"):
        # 站位原型 A/B(2026-08-11,设计套路报告 E 条;未拍板,demo 未接入):
        #   pos1 = 对位索敌(同类随机 → 攻击者槽位对位,确定性)
        #   pos2 = pos1 + 前位守护(1 号位存活手拦截指向头/躯干的单体攻击)
        #   pos3 = pos2 + 攻击标签(触手/抓握手=bypass 无视守护;连环腿=break 优先拆守护者)
        # 零件池逐行同 batch2(07-29 教训:A/B 变体必须逐行复制基准池)
        TORSOS.extend(["强能躯干", "臃肿的躯干"])
        LEGS.extend(["闪避腿", "高鞭腿", "连环腿", "黏腿", "震撼腿"])
        MECH_HEADS.extend(["喷毒头", "喷冰头", "伸缩头", "蓄力头"])
        MECH_HANDS.extend(["刺拳手", "触手", "蓄力拳", "残像拳"])
        PLUGINS_BY_KIND["head"] = PLUGINS_BY_KIND["head"] + ["头槌"]
        PLUGINS_BY_KIND["hand"] = PLUGINS_BY_KIND["hand"] + ["认真一拳"]
        PLUGINS_BY_KIND["leg"] = PLUGINS_BY_KIND["leg"] + ["先守后攻"]
        PLUGINS_BY_KIND["torso"] = PLUGINS_BY_KIND["torso"] + ["耐毒皮肤", "耐冰皮肤"]
        PLUGINS_BY_KIND["tail"] = ["火蜥蜴尾巴", "毒蛇尾巴", "冰虫尾巴"]
        if variant == "pos3":
            CATALOG["触手"]["ptag"] = "bypass"
            CATALOG["抓握手"]["ptag"] = "bypass"
            CATALOG["连环腿"]["ptag"] = "break"
        return RuleConfig(positional=True, guard_front=(variant != "pos1"))
    elif variant == "batch2":
        # 第二批全量(机制件+插件都进池;尾巴上的头因需配对尾巴暂不进随机池,单独手测)
        TORSOS.extend(["强能躯干", "臃肿的躯干"])
        LEGS.extend(["闪避腿", "高鞭腿", "连环腿", "黏腿", "震撼腿"])
        MECH_HEADS.extend(["喷毒头", "喷冰头", "伸缩头", "蓄力头"])
        MECH_HANDS.extend(["刺拳手", "触手", "蓄力拳", "残像拳"])
        PLUGINS_BY_KIND["head"] = PLUGINS_BY_KIND["head"] + ["头槌"]
        PLUGINS_BY_KIND["hand"] = PLUGINS_BY_KIND["hand"] + ["认真一拳"]
        PLUGINS_BY_KIND["leg"] = PLUGINS_BY_KIND["leg"] + ["先守后攻"]
        PLUGINS_BY_KIND["torso"] = PLUGINS_BY_KIND["torso"] + ["耐毒皮肤", "耐冰皮肤"]
        PLUGINS_BY_KIND["tail"] = ["火蜥蜴尾巴", "毒蛇尾巴", "冰虫尾巴"]
    return RuleConfig()


def _entry(rng, name, kind, mech):
    """按概率给部件挂一个位置合法的插件;返回 "名" 或 (名, 插件)。"""
    if mech and kind in PLUGINS_BY_KIND and rng.random() < PLUGIN_PROB:
        return (name, rng.choice(PLUGINS_BY_KIND[kind]))
    return name


def gen_spec(rng, mech=False):
    """拒绝采样一个合法(能量/槽位/预算)且花钱 ≥ MIN_PRICE 的配装。"""
    heads_pool = HEADS + (MECH_HEADS if mech else [])
    hands_pool = HANDS + (MECH_HANDS if mech else [])
    while True:
        torso = rng.choice(TORSOS)
        n_heads = rng.choice([0, 1, 1, 1, 2])
        n_hands = rng.randint(0, 4)
        n_legs = rng.randint(0, 4)
        n_tails = rng.choice([0, 0, 0, 1])   # 尾巴独立位,限 1(Akun 2026-07-15)
        if not 1 <= n_hands + n_legs + n_tails + n_heads <= 7:
            continue
        if mech:
            tp = rng.choice(["", "", "普通能量核心", "耐火皮肤", "尖刺皮肤", "普通能量核心"]) \
                if rng.random() < 0.5 else ""
        else:
            tp = "普通能量核心" if rng.random() < 0.25 else ""   # 旧口径:1/4 概率带核心
        spec = dict(
            torso=torso, torso_plugin=tp,
            heads=sorted((_entry(rng, rng.choice(heads_pool), "head", mech) for _ in range(n_heads)),
                         key=str),
            hands=sorted((_entry(rng, rng.choice(hands_pool), "hand", mech) for _ in range(n_hands)),
                         key=str),
            legs=sorted((_entry(rng, rng.choice(LEGS), "leg", mech) for _ in range(n_legs)),
                        key=str),
            tails=sorted((_entry(rng, rng.choice(TAILS), "tail", mech) for _ in range(n_tails)),
                         key=str),
        )
        m = build(spec)
        if m.energy_used() > m.supply_total():
            continue
        if not MIN_PRICE <= m.price_total() <= BUDGET:
            continue
        return spec


def _mk(entry, i):
    if isinstance(entry, (tuple, list)):
        return make(entry[0], i + 1, entry[1])
    return make(entry, i + 1)


def build(spec):
    n_limbs = len(spec["hands"]) + len(spec["legs"])   # 尾巴不占四肢槽
    slots = (["头部插槽"] * max(0, len(spec["heads"]) - 1)
             + ["四肢插槽"] * max(0, n_limbs - 4))
    return Monster(
        name=label(spec),
        torso=make(spec["torso"], 0, spec.get("torso_plugin", "")),
        heads=[_mk(n, i) for i, n in enumerate(spec["heads"])],
        hands=[_mk(n, i) for i, n in enumerate(spec["hands"])],
        legs=[_mk(n, i) for i, n in enumerate(spec["legs"])],
        tails=[_mk(n, i) for i, n in enumerate(spec["tails"])],   # 尾巴支持插件(属性尾巴,2026-07-22)
        slots=[make(n, i + 1) for i, n in enumerate(slots)],
    )


def label(spec):
    def one(e):
        return f"{e[0]}·{e[1]}" if isinstance(e, (tuple, list)) else e
    def grp(names):
        c = Counter(one(n) for n in names)
        return "+".join(f"{n}x{k}" if k > 1 else n for n, k in sorted(c.items()))
    bits = [spec["torso"].replace("的躯干", "").replace("躯干", "")]
    if spec.get("torso_plugin"):
        bits[0] += f"·{spec['torso_plugin']}"
    for key in ("heads", "hands", "legs", "tails"):
        if spec[key]:
            bits.append(grp(spec[key]))
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
    def n_plugged(s):
        return (sum(1 for e in [*s["heads"], *s["hands"], *s["legs"]]
                    if isinstance(e, (tuple, list)))
                + (1 if s.get("torso_plugin") else 0))
    return (f"无头 {headless:.0%},手占多数 {hand_major:.0%},"
            f"平均 头{sum(len(s['heads']) for s in specs)/n:.1f}"
            f"/手{sum(len(s['hands']) for s in specs)/n:.1f}"
            f"/腿{sum(len(s['legs']) for s in specs)/n:.1f}"
            f"/插件{sum(n_plugged(s) for s in specs)/n:.1f}")


def diversity_stats(specs):
    """多样性 KPI(2026-07-22 起进报告):衡量顶层是否被单一形态/单一零件统治。
    - 形态数:不同 (头,手,腿,尾) 数目组合的种数——越多说明可行流派越多
    - 零件种数 / 依赖度:去插件后用到的不同零件名数,以及最高频零件的出现率(接近 100% = 全场都靠它)"""
    n = len(specs)
    shapes = {(len(s["heads"]), len(s["hands"]), len(s["legs"]), len(s["tails"]))
              for s in specs}
    def names(s):
        out = [s["torso"]]
        for key in ("heads", "hands", "legs", "tails"):
            for e in s[key]:
                out.append(e[0] if isinstance(e, (tuple, list)) else e)
        return out
    cnt = Counter()
    for s in specs:
        for name in set(names(s)):   # 每配装计一次,量的是"多少配装依赖它"
            cnt[name] += 1
    top_part, top_n = cnt.most_common(1)[0] if cnt else ("-", 0)
    return (f"形态 {len(shapes)} 种,零件 {len(cnt)} 种,"
            f"最依赖件 {top_part}({top_n}/{n} 配装)")


def cycle_stats(top, pair_win, games):
    """非传递性 KPI:决赛圈里有多少「A 克 B、B 克 C、C 克 A」的三元环。

    为什么要量这个:流派(archetype)的定义不是「有几种配装能赢」,而是
    「有几条互相克制的取胜路径」。如果强度是一条全序链(谁都打得过下面的、
    打不过上面的),那多样性只是次优解的排队,玩家最终只会抄第一名——
    炉石那种「快攻克后期、后期克中速、中速克快攻」的手感来自环,不来自排名。

    判定:A 对 B 胜率 > DOM 视为「A 克 B」;数有向三元环。
    附带给出「决定性对局占比」(明显克制的对子有多少),环少但决定性对局也少
    = 大家互相五五开(平但无个性),和全序是两种不同的病。"""
    DOM = 0.60
    beats = {a: set() for a in top}
    decisive = 0
    pairs = 0
    for a in top:
        for b in top:
            if a >= b:
                continue
            pairs += 1
            wr = pair_win[(a, b)] / games
            if wr > DOM:
                beats[a].add(b); decisive += 1
            elif wr < 1 - DOM:
                beats[b].add(a); decisive += 1
    cycles = 0
    for a in top:
        for b in beats[a]:
            for c in beats[b]:
                if a in beats[c]:
                    cycles += 1
    cycles //= 3   # 每个环被三个起点各数一次
    # 光看环的绝对个数会骗人:随便一张随机胜负图都有一堆环。基准是"完全随机"——
    # 三条边都分出胜负的三角形里,随机情况下 1/4 是环。观测/随机 = 非传递指数:
    # 0% = 纯全序(一条强度链,只有一个维度),100% = 强度关系完全无法排序。
    tri = 0
    for a in top:
        for b in top:
            for c in top:
                if a < b < c and all(x in beats[y] or y in beats[x]
                                     for x, y in ((a, b), (b, c), (a, c))):
                    tri += 1
    idx = cycles / (0.25 * tri) if tri else 0.0
    return (f"三元克制环 {cycles} 个 / 有效三角 {tri} 个 → 非传递指数 {idx:.0%},"
            f"决定性对局 {decisive}/{pairs}({decisive/pairs:.0%},判定线 >{DOM:.0%})")


def bt_residual(top, pair_win, games, iters=300):
    """一维性 KPI(sol 2026-08-01 建议,取代裸环计数当主指标):
    用 Bradley-Terry 单强度模型拟合决赛圈对战矩阵,看平均残差(百分点)。
    残差 ≈ 噪声底 → 胜负几乎完全被「一条强度链」解释(P1 病:只有强弱没有克制);
    残差显著高于噪声底 → 存在单一强度讲不通的克制结构。
    噪声底 = 就算世界真是一维的,二项抽样也会留下的期望残差 sqrt(2p(1-p)/(πn))。"""
    import math
    s = {i: 1.0 for i in top}
    w = {i: 0.0 for i in top}
    for (a, b), pw in pair_win.items():
        w[a] += pw
        w[b] += games - pw
    for _ in range(iters):
        new = {}
        for i in top:
            denom = sum(games / (s[i] + s[j]) for j in top if j != i)
            new[i] = (w[i] / denom) if (denom and w[i] > 0) else 1e-6
        g = sum(new.values()) / len(new)
        s = {i: v / g for i, v in new.items()}
    resid, noise = [], []
    for (a, b), pw in pair_win.items():
        p_obs = pw / games
        p_hat = s[a] / (s[a] + s[b])
        resid.append(abs(p_obs - p_hat))
        noise.append(math.sqrt(2 * p_hat * (1 - p_hat) / (math.pi * games)))
    return (f"BT 单强度模型平均残差 {100*sum(resid)/len(resid):.1f}pp"
            f"(纯一维噪声底 ≈{100*sum(noise)/len(noise):.1f}pp)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline",
                    choices=["baseline", "muscle2", "atk15", "hand125", "combo", "mech",
                             "init_once", "dodge_all", "legmob", "leg50", "leg_hunt", "leg_fix",
                             "mech_status1", "batch2a", "batch2", "batch2_tent_rand",
                             "pos1", "pos2", "pos3"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    cfg = apply_variant(args.variant)
    rng = random.Random(args.seed)
    mech = args.variant in ("mech", "mech_status1", "batch2", "batch2_tent_rand",
                            "pos1", "pos2", "pos3")
    specs = dedupe([gen_spec(rng, mech) for _ in range(SAMPLE)])
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
            rep = battle(mons[i], mons[j], seed=battle_id, cfg=cfg)
            battle_id += 1
            wins[i] += 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
    order = sorted(range(n), key=lambda i: -wins[i])
    top = order[:TOP_N]

    # 阶段2:前 TOP_N 循环赛(双方向)
    score = {i: 0.0 for i in top}
    pair_win = {}
    for a in top:
        for b in top:
            if a >= b:
                continue
            pw = 0.0
            for g in range(STAGE2_GAMES // 2):
                rep = battle(mons[a], mons[b], seed=battle_id, cfg=cfg); battle_id += 1
                ga = 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
                score[a] += ga; score[b] += 1.0 - ga; pw += ga
                rep = battle(mons[b], mons[a], seed=battle_id, cfg=cfg); battle_id += 1
                gb = 1.0 if rep["winner"] == "A" else (0.5 if rep["winner"] == "draw" else 0.0)
                score[b] += gb; score[a] += 1.0 - gb; pw += 1.0 - gb
            pair_win[(a, b)] = pw
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
    print(f"决赛圈 40 强多样性:{diversity_stats([specs[i] for i in top])}")
    print(f"决赛圈前 10 多样性:{diversity_stats([specs[i] for i in final[:10]])}")
    print(f"决赛圈 40 强非传递性:{cycle_stats(top, pair_win, STAGE2_GAMES)}")
    print(f"决赛圈前 10 非传递性:{cycle_stats(final[:10], pair_win, STAGE2_GAMES)}")
    print(f"决赛圈 40 强一维性:{bt_residual(top, pair_win, STAGE2_GAMES)}")


if __name__ == "__main__":
    main()
