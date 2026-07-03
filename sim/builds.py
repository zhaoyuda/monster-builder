# 典型流派配装 —— 用于烟雾测试评审报告里的"疑似退化流派"
# 约束按推荐默认:Q1 硬约束 Σ能量需求 ≤ 躯干供能;价格记账供参考(各流派 1600-1800,大致等价)
from .engine import Monster
from .parts import make


def build(name, torso, heads=(), hands=(), legs=(), tails=()):
    m = Monster(
        name=name,
        torso=make(torso),
        heads=[make(n, i + 1) for i, n in enumerate(heads)],
        hands=[make(n, i + 1) for i, n in enumerate(hands)],
        legs=[make(n, i + 1) for i, n in enumerate(legs)],
        tails=[make(n, i + 1) for i, n in enumerate(tails)],
    )
    used, supply = m.energy_used(), m.torso.supply
    assert used <= supply, f"{name}: 能量超限 {used}>{supply}"
    return m


ARCHETYPES = {
    # 均衡流:头手腿俱全
    "均衡流": lambda: build("均衡流", "有些肌肉的躯干",
                            heads=["新手头"], hands=["猛爪", "强力爪"],
                            legs=["猛腿", "新手腿"], tails=["猛尾"]),
    # 多头流:评审疑似超模——没人主动打我的头,我的头 50% 直击对方躯干
    "多头流": lambda: build("多头流", "有些肌肉的躯干",
                            heads=["猛头", "顶撞头", "新手头"]),
    # 无头流:免疫眩晕;对面头的攻击 100% 进躯干(E4 回退)
    "无头流": lambda: build("无头流", "有些肌肉的躯干",
                            hands=["猛爪", "强力爪", "小手手"],
                            legs=["猛腿", "粗腿"]),
    # 踢腿流:放弃先攻/闪避,纯输出腿堆满
    "踢腿流": lambda: build("踢腿流", "有些肌肉的躯干",
                            legs=["踢腿", "踢腿", "踢腿", "踢腿", "踢腿"]),
    # 耗材手流:末位放最便宜的新手手当格挡耗材盾
    "耗材手流": lambda: build("耗材手流", "有些肌肉的躯干",
                              heads=["猛头"], hands=["强力爪", "强力爪", "新手手"],
                              legs=["新手腿"]),
    # 肉盾流:大躯干 + 高血部件磨死对面
    "肉盾流": lambda: build("肉盾流", "稍微长大的躯干",
                            heads=["肿头"], hands=["小手手"], legs=["粗腿"]),
}


def roster():
    return {name: fn() for name, fn in ARCHETYPES.items()}
