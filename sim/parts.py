# 零件目录 —— 数据与 design/01-assembly.md 一一对应,改零件表后同步这里
# 字段:kind, atk 攻击力, hp 血量, energy 能量需求, supply 供能, initiative 先攻, dodge 闪避, price 价格
#       command 指挥点供给(躯干/头;Q12 提案数值,待 Akun 拍板——仅 command_mode≠off 时生效)
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
    command: int = 0   # 指挥点供给(躯干基础值 / 头提供;手腿出手各耗 1 点)
    crit: float = 0.0  # 暴击率(仅对本部件自己的攻击生效;Akun 2026-07-07 拍板,倍率待定默认 2x)
    hits: int = 1      # 每回合攻击次数(猛犸象头"双击"=2;每次独立结算目标/闪避/格挡,语义待 Akun 确认)
    hunts: str = ""    # 目标偏好(Q15 机制件原型):"hand"=优先打对方存活的手,打光回退本类默认规则
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
    # 头(供能消耗型,倾向攻击;command=指挥点供给——方案A已拍板,单头数值待调;
    #    crit=暴击率(本体),Akun 2026-07-07 填入零件表)
    "新手头":   dict(kind="head", atk=10, hp=50,  energy=10, command=2, crit=0.0,  price=200),
    "猛头":     dict(kind="head", atk=20, hp=100, energy=20, command=2, crit=0.08, price=400),
    "顶撞头":   dict(kind="head", atk=25, hp=75,  energy=20, command=1, crit=0.10, price=400),
    "肿头":     dict(kind="head", atk=15, hp=125, energy=20, command=3, crit=0.08, price=400),
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
    # 躯干(供能来源,血空即败;command=基础指挥点——无头时的"脊髓反射"底线,大躯干略高回应 Q11)
    # 数值经参数扫描定为 3/4/3:普通配装(1头+4肢)完全感觉不到指挥约束,只有无头/极端堆量被惩罚
    "新手躯干":       dict(kind="torso", atk=0, hp=100, supply=30, command=3, price=500),  # Q3 按公式修正
    "稍微长大的躯干": dict(kind="torso", atk=0, hp=200, supply=40, command=4, price=800),
    "有些肌肉的躯干": dict(kind="torso", atk=0, hp=150, supply=50, command=3, price=800),
    # 插件(E8:不可被攻击,不入目标池)
    "新手尾巴": dict(kind="tail", atk=0, hp=0, initiative=1, price=20),
    "猛尾":     dict(kind="tail", atk=0, hp=0, initiative=2, price=40),
    "四肢插槽": dict(kind="slot", atk=0, hp=0, price=30),   # +1 手/腿/尾位(Q2)
    "头部插槽": dict(kind="slot", atk=0, hp=0, price=50),   # +1 头位(Q2)
    # 装饰件(PVE 起始装,Q13;数值为 Yuda 默认,待 Akun 核)
    "装饰手":   dict(kind="hand", atk=0, hp=10, energy=0, price=0),
    "装饰腿":   dict(kind="leg",  atk=0, hp=10, energy=0, initiative=0, dodge=0.0, price=0),
    # PVE 专属敌方部件(03-pve 前三关,Akun 2026-07-07 设计;不入玩家目录,不受装配约束)
    "鹿躯干":     dict(kind="torso", atk=0, hp=50,  supply=99, command=99, price=0),
    "猛犸象头":   dict(kind="head",  atk=2, hp=75,  hits=2, price=0),   # 双击:2 攻 ×2 次
    "猛犸象躯干": dict(kind="torso", atk=0, hp=200, supply=99, command=99, price=0),
    "恐兽头":     dict(kind="head",  atk=5, hp=100, price=0),
    "恐兽躯干":   dict(kind="torso", atk=0, hp=100, supply=99, command=99, price=0),
    "恐兽爪":     dict(kind="hand",  atk=5, hp=25,  price=0),
    # 机制件原型(Q15 提案,数值未定价,仅供模拟验证;Akun 拍板后再进零件表)
    "猎臂头":     dict(kind="head",  atk=15, hp=75, energy=20, command=2, hunts="hand", price=400),
}


def make(name: str, slot: int = 0) -> Part:
    spec = CATALOG[name]
    return Part(name=name, max_hp=spec["hp"], slot=slot,
                **{k: v for k, v in spec.items() if k != "hp"}, hp=spec["hp"])
