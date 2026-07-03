# 零件目录 —— 数据与 design/01-assembly.md 一一对应,改零件表后同步这里
# 字段:kind, atk 攻击力, hp 血量, energy 能量需求, supply 供能, initiative 先攻, dodge 闪避, price 价格
from dataclasses import dataclass


@dataclass
class Part:
    name: str
    kind: str          # head / hand / leg / torso / tail
    atk: int
    hp: int
    max_hp: int
    energy: int = 0    # 能量需求
    supply: int = 0    # 供能(仅躯干)
    initiative: int = 0
    dodge: float = 0.0
    price: int = 0
    slot: int = 0      # 同类内槽位编号,从 1 开始

    def alive(self) -> bool:
        return self.hp > 0

    @property
    def label(self) -> str:
        cn = {"head": "头", "hand": "手", "leg": "腿", "torso": "躯干", "tail": "尾"}[self.kind]
        if self.kind == "torso":
            return f"{self.name}"
        return f"{self.name}({cn}{self.slot})"


CATALOG = {
    # 头(供能消耗型,倾向攻击)
    "新手头":   dict(kind="head", atk=10, hp=50,  energy=10, price=200),
    "猛头":     dict(kind="head", atk=20, hp=100, energy=20, price=400),
    "顶撞头":   dict(kind="head", atk=25, hp=75,  energy=20, price=400),
    "肿头":     dict(kind="head", atk=15, hp=125, energy=20, price=400),
    # 手(攻防平衡,可格挡)
    "新手手":   dict(kind="hand", atk=5,  hp=25,  energy=5,  price=100),
    "猛爪":     dict(kind="hand", atk=10, hp=50,  energy=10, price=200),
    "强力爪":   dict(kind="hand", atk=13, hp=35,  energy=10, price=200),
    "小手手":   dict(kind="hand", atk=7,  hp=65,  energy=10, price=200),
    # 腿(提供先攻/闪避;踢腿无先攻无闪避,按 Q6 推荐视为故意)
    "新手腿":   dict(kind="leg",  atk=3,  hp=20,  energy=5,  initiative=1, dodge=0.05, price=100),
    "猛腿":     dict(kind="leg",  atk=6,  hp=50,  energy=10, initiative=2, dodge=0.05, price=200),
    "鞭腿":     dict(kind="leg",  atk=8,  hp=40,  energy=10, initiative=2, dodge=0.05, price=200),
    "粗腿":     dict(kind="leg",  atk=4,  hp=60,  energy=10, initiative=2, dodge=0.07, price=200),
    "踢腿":     dict(kind="leg",  atk=10, hp=50,  energy=10, initiative=0, dodge=0.0,  price=200),
    # 躯干(供能来源,血空即败)
    "新手躯干":       dict(kind="torso", atk=0, hp=100, supply=30, price=400),
    "稍微长大的躯干": dict(kind="torso", atk=0, hp=200, supply=40, price=800),
    "有些肌肉的躯干": dict(kind="torso", atk=0, hp=150, supply=50, price=800),
    # 插件(E8:不可被攻击,不入目标池)
    "新手尾巴": dict(kind="tail", atk=0, hp=0, initiative=1, price=20),
    "猛尾":     dict(kind="tail", atk=0, hp=0, initiative=2, price=40),
}


def make(name: str, slot: int = 0) -> Part:
    spec = CATALOG[name]
    return Part(name=name, max_hp=spec["hp"], slot=slot,
                **{k: v for k, v in spec.items() if k != "hp"}, hp=spec["hp"])
