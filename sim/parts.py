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
    pve: bool = False  # PVE 专属敌方部件,不可用于玩家配装(builds.validate 拦截)
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
    # 头(供能消耗型,倾向攻击;command=指挥点供给;crit=暴击率(本体)
    #    数值:Akun 2026-07-15 零件表(顶撞头指挥 1→2、肿头暴击 8%→6%)
    "新手头":   dict(kind="head", atk=10, hp=50,  energy=10, command=2, crit=0.0,  price=200),
    "猛头":     dict(kind="head", atk=20, hp=100, energy=20, command=2, crit=0.08, price=400),
    "顶撞头":   dict(kind="head", atk=25, hp=75,  energy=20, command=2, crit=0.10, price=400),
    "肿头":     dict(kind="head", atk=15, hp=125, energy=20, command=3, crit=0.06, price=400),
    # ⚠️ 喷火头(AOE+灼烧)——机制引擎未支持,暂不入目录(见 05 页 Wave2 专项)
    # 手(攻防平衡,可格挡)
    "新手手":   dict(kind="hand", atk=5,  hp=25,  energy=5,  price=100),
    "猛爪":     dict(kind="hand", atk=10, hp=50,  energy=10, price=200),
    "强力爪":   dict(kind="hand", atk=13, hp=35,  energy=10, price=200),
    "小手手":   dict(kind="hand", atk=7,  hp=65,  energy=10, price=200),
    # ⚠️ 抓握手(闪避清零)/ 长有芽孢的手(死后重生)——机制引擎未支持,暂不入目录
    # 腿(提供先攻/闪避;踢腿无先攻无闪避,按 Q6 推荐视为故意)
    "新手腿":   dict(kind="leg",  atk=3,  hp=20,  energy=5,  initiative=1, dodge=0.05, price=100),
    "猛腿":     dict(kind="leg",  atk=6,  hp=50,  energy=10, initiative=2, dodge=0.05, price=200),
    "鞭腿":     dict(kind="leg",  atk=8,  hp=40,  energy=10, initiative=2, dodge=0.05, price=200),
    "灵活的腿": dict(kind="leg",  atk=4,  hp=60,  energy=10, initiative=2, dodge=0.07, price=200),  # 原「粗腿」,Akun 2026-07-15 改名
    "踢腿":     dict(kind="leg",  atk=10, hp=50,  energy=10, initiative=0, dodge=0.0,  price=200),
    # 躯干(供能来源,血空即败;command=基础指挥点——无头时的"脊髓反射"底线)
    # Akun 2026-07-15 拍板:基础指挥 2/3/3(采纳 meta 报告方向),价格按新公式(1供能=5价)350/700/700,供能 30/60/80
    "新手躯干":       dict(kind="torso", atk=0, hp=100, supply=30, command=2, price=350),
    "稍微长大的躯干": dict(kind="torso", atk=0, hp=200, supply=60, command=3, price=700),
    "有些肌肉的躯干": dict(kind="torso", atk=0, hp=150, supply=80, command=3, price=700),
    # 插件(E8:不可被攻击,不入目标池;尾巴为独立位,不占四肢槽——Akun 2026-07-15「位置:尾巴(独立)」)
    "新手尾巴": dict(kind="tail", atk=0, hp=0, initiative=1, price=20),
    "猛尾":     dict(kind="tail", atk=0, hp=0, initiative=2, price=40),
    "四肢插槽": dict(kind="slot", atk=0, hp=0, price=30),   # +1 手/腿位(Q2)
    "头部插槽": dict(kind="slot", atk=0, hp=0, price=50),   # +1 头位(Q2)
    "普通能量核心": dict(kind="slot", atk=0, hp=0, supply=20, price=100),  # 身体插件:供能+20;暂限每躯干 1 个
    # 装饰件(PVE 起始装,Q13;Akun 2026-07-15 血量 10→0:纯摆设,不可当肉墙——Q16 的回答)
    "装饰手":   dict(kind="hand", atk=0, hp=0, energy=0, price=0),
    "装饰腿":   dict(kind="leg",  atk=0, hp=0, energy=0, initiative=0, dodge=0.0, price=0),
    # PVE 专属敌方部件(03-pve 前三关;Akun 2026-07-15:恐兽改剑齿虎,爪 攻5→2/血25→50)
    "鹿躯干":     dict(kind="torso", atk=0, hp=50,  supply=99, command=99, pve=True, price=0),
    "猛犸象头":   dict(kind="head",  atk=2, hp=75,  hits=2, pve=True, price=0),   # 双击:2 攻 ×2 次
    "猛犸象躯干": dict(kind="torso", atk=0, hp=200, supply=99, command=99, pve=True, price=0),
    "剑齿虎头":   dict(kind="head",  atk=5, hp=100, pve=True, price=0),
    "剑齿虎躯干": dict(kind="torso", atk=0, hp=100, supply=99, command=99, pve=True, price=0),
    "剑齿虎爪":   dict(kind="hand",  atk=2, hp=50,  pve=True, price=0),
    # 机制件原型(Q15 提案,数值未定价,仅供模拟验证;Akun 拍板后再进零件表)
    "猎臂头":     dict(kind="head",  atk=15, hp=75, energy=20, command=2, hunts="hand", price=400),
}


def make(name: str, slot: int = 0) -> Part:
    spec = CATALOG.get(name)
    if spec is None:
        raise KeyError(f"未知零件「{name}」——检查拼写,或 sim/parts.py CATALOG 是否与零件表同步")
    return Part(name=name, max_hp=spec["hp"], slot=slot,
                **{k: v for k, v in spec.items() if k != "hp"}, hp=spec["hp"])
