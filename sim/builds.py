# 典型流派配装 —— 用于烟雾测试评审报告里的"疑似退化流派"
# 装配约束(Akun 2026-07-03 拍板;2026-07-15 插件表更新;Q17e 插件规则):
#   Q1 能量硬约束:Σ能量需求 ≤ 供能(躯干 + 能量核心插件)
#   Q2 槽位:所有躯干自带 1头 / 4四肢(手+腿);头部插槽 +1 头位,四肢插槽 +1 手/腿位
#   Q9(已答):尾巴是独立位,不占四肢槽;数量上限未定,暂按 1
#   Q17e:插件随宿主、每个部件最多 1 个插件、躯干插件也限 1(普通能量核心/耐火皮肤/尖刺皮肤竞争同一位)
# 部件写法:"猛爪" 或 ("猛爪", "骨盾")(带插件);躯干插件用 torso_plugin=
from .engine import Monster
from .parts import make, PLUGINS


def _mk(entry, i):
    if isinstance(entry, (tuple, list)):
        name, plugin = entry
        return make(name, i + 1, plugin)
    return make(entry, i + 1)


def build(name, torso, heads=(), hands=(), legs=(), tails=(), slots=(), torso_plugin=""):
    m = Monster(
        name=name,
        torso=make(torso, 0, torso_plugin),
        heads=[_mk(n, i) for i, n in enumerate(heads)],
        hands=[_mk(n, i) for i, n in enumerate(hands)],
        legs=[_mk(n, i) for i, n in enumerate(legs)],
        tails=[_mk(n, i) for i, n in enumerate(tails)],   # 尾巴支持插件(属性尾巴,2026-07-22)
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
    # PVE 专属件 / 衍生件(芽孢长出来的手)不可直接装配
    for part in [m.torso, *m.heads, *m.hands, *m.legs, *m.tails]:
        assert not part.pve, f"{m.name}: 「{part.name}」是 PVE 专属敌方部件,玩家不可用"
        assert not part.derived, f"{m.name}: 「{part.name}」是战斗中长出的衍生部件,不可直接装配"
    # Q17e 插件:位置匹配(每部件限 1 由 Part.plugin 单字段天然保证;躯干限 1 同理)
    for part in m.all_parts():
        if part.plugin:
            pos = PLUGINS[part.plugin]["pos"]
            assert part.kind in pos, \
                f"{m.name}: 插件「{part.plugin}」只能装在 {'/'.join(pos)},不能装在「{part.name}」({part.kind})"
    # Q1 能量硬约束(供能 = 躯干 + 能量核心插件)
    used, supply = m.energy_used(), m.supply_total()
    assert used <= supply, f"{m.name}: 能量超限 {used}>{supply}"
    # Q2 槽位约束;尾巴独立位不占四肢槽(Q9)
    head_slots = 1 + sum(1 for s in m.slots if s.name == "头部插槽")
    limb_slots = 4 + sum(1 for s in m.slots if s.name == "四肢插槽")
    assert len(m.heads) <= head_slots, f"{m.name}: 头槽超限 {len(m.heads)}>{head_slots}"
    n_limbs = len(m.hands) + len(m.legs)
    assert n_limbs <= limb_slots, f"{m.name}: 四肢槽超限 {n_limbs}>{limb_slots}"
    assert len(m.tails) <= 1, f"{m.name}: 尾巴独立位暂限 1 条(上限待 Akun 定)"
    # 旧版兼容:普通能量核心已改为躯干插件,不能再塞 slots(make 会直接报错,这里兜底)
    assert not any(s.name == "普通能量核心" for s in m.slots), \
        f"{m.name}: 普通能量核心是躯干插件,用 torso_plugin= 挂载"
    return m


ARCHETYPES = {
    # 均衡流:头手腿尾俱全(尾巴独立位,不再占四肢槽)
    "均衡流": lambda: build("均衡流", "有些肌肉的躯干",
                            heads=["新手头"], hands=["猛爪", "强力爪"],
                            legs=["猛腿", "新手腿"], tails=["猛尾"]),
    # 多头流:评审疑似超模——没人主动打我的头,我的头 50% 直击对方躯干
    "多头流": lambda: build("多头流", "有些肌肉的躯干",
                            heads=["猛头", "顶撞头", "新手头"],
                            slots=["头部插槽", "头部插槽"]),
    # 无头流:免疫眩晕;对面头的攻击 100% 进躯干(E4 回退)
    "无头流": lambda: build("无头流", "有些肌肉的躯干",
                            hands=["猛爪", "强力爪", "小手手"],
                            legs=["猛腿", "灵活的腿"],
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
                            heads=["肿头"], hands=["小手手"], legs=["灵活的腿"]),
    # 机制流:喷火 AOE + 抓握控闪避 + 芽孢重生 + 插件(Q17 机制引擎验证用)
    "机制流": lambda: build("机制流", "有些肌肉的躯干", torso_plugin="尖刺皮肤",
                            heads=["喷火头"],
                            hands=[("抓握手", "爆裂腺体"), ("长有芽孢的手", "胶质瘤")],
                            legs=[("新手腿", "碎骨锥")]),
    # 第二批试验流:Akun 2026-07-22 新零件橱窗(喷毒部位AOE+触手战吼+蓄力+机制腿+属性尾巴)
    "第二批试验流": lambda: build("第二批试验流", "强能躯干",
                                  heads=["喷毒头"],
                                  hands=["触手", ("蓄力拳", "认真一拳")],
                                  legs=["连环腿", "震撼腿"],
                                  tails=[("猛尾", "冰虫尾巴")]),
}


def roster():
    return {name: fn() for name, fn in ARCHETYPES.items()}
