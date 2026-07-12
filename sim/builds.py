# 典型流派配装 —— 用于烟雾测试评审报告里的"疑似退化流派"
# 装配约束(Akun 2026-07-03 拍板):
#   Q1 能量硬约束:Σ能量需求 ≤ 躯干供能(超了不能行动)
#   Q2 槽位:所有躯干自带 1头 / 2手 / 2腿;头部插槽 +1 头位,四肢插槽 +1 手/腿/尾位
#   ⚠️ 待核实(已提 Q9):基础躯干是否自带尾巴位?此处按"尾巴占四肢/尾巴位"的字面理解验证
from .engine import Monster
from .parts import make


def build(name, torso, heads=(), hands=(), legs=(), tails=(), slots=()):
    m = Monster(
        name=name,
        torso=make(torso),
        heads=[make(n, i + 1) for i, n in enumerate(heads)],
        hands=[make(n, i + 1) for i, n in enumerate(hands)],
        legs=[make(n, i + 1) for i, n in enumerate(legs)],
        tails=[make(n, i + 1) for i, n in enumerate(tails)],
        slots=[make(n, i + 1) for i, n in enumerate(slots)],
    )
    validate(m)
    return m


def validate(m: Monster):
    # 槽位类型:零件必须装进对应类型的槽
    for part, want in ([(m.torso, "torso")]
                       + [(p, "head") for p in m.heads]
                       + [(p, "hand") for p in m.hands]
                       + [(p, "leg") for p in m.legs]
                       + [(p, "tail") for p in m.tails]
                       + [(p, "slot") for p in m.slots]):
        assert part.kind == want, f"{m.name}: 「{part.name}」({part.kind})装错槽位(应为 {want})"
    # PVE 专属件不可用于玩家配装
    for part in [m.torso, *m.heads, *m.hands, *m.legs, *m.tails]:
        assert not part.pve, f"{m.name}: 「{part.name}」是 PVE 专属敌方部件,玩家不可用"
    # Q1 能量硬约束
    used, supply = m.energy_used(), m.torso.supply
    assert used <= supply, f"{m.name}: 能量超限 {used}>{supply}"
    # Q2 槽位约束
    head_slots = 1 + sum(1 for s in m.slots if s.name == "头部插槽")
    limb_slots = 4 + sum(1 for s in m.slots if s.name == "四肢插槽")  # 手+腿+尾共用(见 Q9)
    assert len(m.heads) <= head_slots, f"{m.name}: 头槽超限 {len(m.heads)}>{head_slots}"
    n_limbs = len(m.hands) + len(m.legs) + len(m.tails)
    assert n_limbs <= limb_slots, f"{m.name}: 四肢槽超限 {n_limbs}>{limb_slots}"
    return m


ARCHETYPES = {
    # 均衡流:头手腿俱全(尾巴占位 → 补 1 四肢插槽)
    "均衡流": lambda: build("均衡流", "有些肌肉的躯干",
                            heads=["新手头"], hands=["猛爪", "强力爪"],
                            legs=["猛腿", "新手腿"], tails=["猛尾"],
                            slots=["四肢插槽"]),
    # 多头流:评审疑似超模——没人主动打我的头,我的头 50% 直击对方躯干
    "多头流": lambda: build("多头流", "有些肌肉的躯干",
                            heads=["猛头", "顶撞头", "新手头"],
                            slots=["头部插槽", "头部插槽"]),
    # 无头流:免疫眩晕;对面头的攻击 100% 进躯干(E4 回退)
    "无头流": lambda: build("无头流", "有些肌肉的躯干",
                            hands=["猛爪", "强力爪", "小手手"],
                            legs=["猛腿", "粗腿"],
                            slots=["四肢插槽"]),
    # 踢腿流:放弃先攻/闪避,纯输出腿堆满
    "踢腿流": lambda: build("踢腿流", "有些肌肉的躯干",
                            legs=["踢腿", "踢腿", "踢腿", "踢腿", "踢腿"],
                            slots=["四肢插槽"]),
    # 耗材手流:末位放最便宜的新手手当格挡耗材盾(1头3手1腿 = 4 四肢位,刚好不超)
    "耗材手流": lambda: build("耗材手流", "有些肌肉的躯干",
                              heads=["猛头"], hands=["强力爪", "强力爪", "新手手"],
                              legs=["新手腿"]),
    # 肉盾流:大躯干 + 高血部件磨死对面
    "肉盾流": lambda: build("肉盾流", "稍微长大的躯干",
                            heads=["肿头"], hands=["小手手"], legs=["粗腿"]),
}


def roster():
    return {name: fn() for name, fn in ARCHETYPES.items()}
