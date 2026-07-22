# 零件目录 —— 数据与 design/01-assembly.md 一一对应,改零件表后同步这里
# 字段:kind, atk 攻击力, hp 血量, energy 能量需求, supply 供能, initiative 先攻, dodge 闪避, price 价格
#       command 指挥点供给(躯干/头;Q12 方案A,已拍板)
#       fire 火焰攻击(喷火头:额外目标+灼烧) / grab 抓握(首次攻击改施加闪避清零) / spore 芽孢(死后留标记重生)
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
    crit: float = 0.0  # 暴击率(仅对本部件自己的攻击生效;Akun 2026-07-07 拍板,倍率暂 2x)
    hits: int = 1      # 每回合攻击次数(猛犸象头"双击"=2;每次独立结算目标/闪避/格挡)
    hunts: str = ""    # 目标偏好(Q15 机制件原型):"hand"=优先打对方存活的手,打光回退本类默认规则
    # ---- 伤害类型与第二批机制(Akun 2026-07-22 零件表;实现细则=Q22)----
    dtype: str = "phys"      # 伤害类型:phys/fire/poison/ice(词条表;耐性皮肤/属性尾巴按类型减伤)
    extra_target: bool = False  # 喷火头/喷冰头:额外随机攻击 1 个目标(避开主目标)
    aoe_pos: bool = False    # 喷毒头:攻击除躯干外随机 1 个部位的所有部件,无目标则打躯干(Q22c)
    noblock: bool = False    # 该部件的攻击不可被格挡(三喷头/尾巴上的头,Q22a)
    freeze_prob: float = 0.0  # 喷冰头:命中后冻结概率(冻结=该部件 1 回合不行动,Q22e)
    stretch: bool = False    # 伸缩头:奇数回合造成/受到伤害 ×1.25,偶数 ×0.75(直接攻击,Q22f)
    charge: bool = False     # 蓄力头/蓄力拳:奇数回合不攻击(不耗指挥),偶数回合必暴击(Q22g)
    afterimage: bool = False  # 残像拳:与自己上次攻击目标相同 → 必暴击(Q22h)
    tentacle: bool = False   # 触手:战吼缠绕(开战随机缠敌方非躯干件,双方 5 回合停手停格挡+每回合 5 伤,Q22j)
    tail_head: bool = False  # 尾巴上的头:骑尾巴占其插件位,头阶段最后行动,算头(眩晕/目标池),Q22i
    revenge_head: bool = False  # 高鞭腿:被打中后下一次攻击改打敌方头(一次性,Q22k)
    combo3: bool = False     # 连环腿:同目标连打 3 段,全中再补 1 段,整体耗 1 指挥(Q22l)
    sticky: bool = False     # 黏腿:命中(未被闪避)锁定目标,被闪避或目标死亡才重选(Q22m)
    shock: bool = False      # 震撼腿:命中后敌方全队闪避 -5%,2 回合刷新不叠加(Q22n)
    fire: bool = False   # (兼容旧字段)喷火头=dtype fire+extra_target;新代码请用 dtype
    grab: bool = False   # 抓握手:第一次命中不造成伤害,敌方 5 回合闪避为 0
    spore: bool = False  # 长有芽孢的手:被击破后留芽孢标记,空 2 回合长出"芽孢长出来的手"(Q17b)
    derived: bool = False  # 衍生部件(芽孢长出来的手):不可直接装配,只能战斗中长出
    plugin: str = ""   # 挂载的插件名(Q17e:插件无血量随宿主生效,每部件限 1;见 PLUGINS)
    pve: bool = False  # PVE 专属敌方部件,不可用于玩家配装(builds.validate 拦截)
    price: int = 0
    slot: int = 0      # 同类内槽位编号,从 1 开始
    # ---- 以下为战斗运行时状态,battle() 内部维护,装配时不用管 ----
    burn: dict = None      # 灼烧 {"left": 剩余回合, "src": 来源部件}(每回合掉 2 部件血,刷新不叠加)
    tear: dict = None      # 撕裂 同上(撕裂爪 5 回合 / 尖刺皮肤 2 回合)
    poison: dict = None    # 中毒 {"left", "dmg", "atkdown", "src", "src_key"}(掉血+降攻,刷新不叠加)
    last_target: object = None   # 残像拳:上一次攻击的目标
    revenge_pending: bool = False  # 高鞭腿:被击中标记,下次攻击改打头
    lock_target: object = None   # 黏腿:锁定中的目标
    entangled_left: int = 0      # 触手缠绕剩余回合(>0 时不能攻击/格挡)
    entangle_partner: object = None  # 缠绕配对的另一方部件
    stun_part_next: bool = False   # 碎骨锥:下回合本部件不能行动(与整队眩晕叠加只算眩晕,Q17d)
    stunned_part: bool = False
    grab_used: bool = False        # 抓握手的"第一次攻击"是否已命中(闪避掉不消耗)
    keratin: int = 0               # 头顶角质层剩余吸收次数(生效期间宿主头不暴击)
    spore_wait: int = -1           # 芽孢倒计时(-1=无;击破时置 2,归 0 后下回合长出新手)

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
    #    数值:Akun 2026-07-15 零件表
    "新手头":   dict(kind="head", atk=10, hp=50,  energy=10, command=2, crit=0.0,  price=200),
    "猛头":     dict(kind="head", atk=20, hp=100, energy=20, command=2, crit=0.08, price=400),
    "顶撞头":   dict(kind="head", atk=25, hp=75,  energy=20, command=2, crit=0.10, price=400),
    "肿头":     dict(kind="head", atk=15, hp=125, energy=20, command=3, crit=0.06, price=400),
    # 喷火头(Q17a + Akun 2026-07-22 补:先攻-1、无法格挡):火焰伤害,额外随机攻击 1 个目标,
    #   对受到伤害的目标挂"灼烧"(2 点/回合 ×3 回合,已灼烧则刷新)
    "喷火头":   dict(kind="head", atk=15, hp=100, energy=30, command=2, crit=0.0, price=550,
                     fire=True, dtype="fire", extra_target=True, noblock=True, initiative=-1),
    # ---- 第二批头(Akun 2026-07-22,细则 Q22)----
    "喷毒头":   dict(kind="head", atk=14, hp=100, energy=30, command=2, crit=0.0, price=550,
                     dtype="poison", aoe_pos=True, noblock=True, initiative=-1),
    "喷冰头":   dict(kind="head", atk=15, hp=100, energy=30, command=2, crit=0.0, price=550,
                     dtype="ice", extra_target=True, noblock=True, freeze_prob=0.25, initiative=-1),
    "伸缩头":   dict(kind="head", atk=20, hp=100, energy=20, command=2, crit=0.08, price=400, stretch=True),
    "蓄力头":   dict(kind="head", atk=20, hp=100, energy=20, command=2, crit=0.0,  price=400, charge=True),
    "尾巴上的头": dict(kind="head", atk=19, hp=100, energy=20, command=1, crit=0.10, price=400,
                       tail_head=True, noblock=True),
    # 手(攻防平衡,可格挡)
    "新手手":   dict(kind="hand", atk=5,  hp=25,  energy=5,  price=100),
    "猛爪":     dict(kind="hand", atk=10, hp=50,  energy=10, price=200),
    "强力爪":   dict(kind="hand", atk=13, hp=35,  energy=10, price=200),
    "小手手":   dict(kind="hand", atk=7,  hp=65,  energy=10, price=200),
    # 抓握手:第一次攻击命中时不造成伤害,敌方接下来 5 回合闪避为 0
    "抓握手":   dict(kind="hand", atk=10, hp=50,  energy=10, grab=True, price=200),
    # 长有芽孢的手(Q17b):被击破后原槽位留"芽孢"标记(无血/不可被攻击/不可格挡),
    #   空 2 个回合后长出"芽孢长出来的手"
    "长有芽孢的手":   dict(kind="hand", atk=7, hp=30, energy=10, spore=True, price=250),
    "芽孢长出来的手": dict(kind="hand", atk=8, hp=30, energy=10, derived=True, price=0),
    # ---- 第二批手(Akun 2026-07-22,细则 Q22)----
    "刺拳手":   dict(kind="hand", atk=5,  hp=50, energy=10, hits=2, price=200),
    "触手":     dict(kind="hand", atk=5,  hp=65, energy=10, tentacle=True, price=210),
    "蓄力拳":   dict(kind="hand", atk=10, hp=55, energy=10, charge=True, price=200),
    "残像拳":   dict(kind="hand", atk=8,  hp=45, energy=10, afterimage=True, price=210),
    # 腿(提供先攻/闪避;踢腿无先攻无闪避,按 Q6 拍板为故意)
    "新手腿":   dict(kind="leg",  atk=3,  hp=20,  energy=5,  initiative=1, dodge=0.05, price=100),
    "猛腿":     dict(kind="leg",  atk=6,  hp=50,  energy=10, initiative=2, dodge=0.05, price=200),
    "鞭腿":     dict(kind="leg",  atk=8,  hp=40,  energy=10, initiative=2, dodge=0.05, price=200),
    "灵活的腿": dict(kind="leg",  atk=4,  hp=60,  energy=10, initiative=2, dodge=0.07, price=200),  # 原「粗腿」,Akun 2026-07-15 改名
    "踢腿":     dict(kind="leg",  atk=10, hp=50,  energy=10, initiative=0, dodge=0.0,  price=200),
    "闪避腿":   dict(kind="leg",  atk=8,  hp=45,  energy=10, initiative=2, dodge=0.12, price=200),  # Akun 2026-07-22 第二批(纯数值件)
    # ---- 第二批机制腿(Akun 2026-07-22,细则 Q22)----
    "高鞭腿":   dict(kind="leg",  atk=10, hp=40,  energy=10, initiative=2, dodge=0.05, price=200, revenge_head=True),
    "连环腿":   dict(kind="leg",  atk=3,  hp=45,  energy=10, initiative=2, dodge=0.05, price=200, combo3=True),
    "黏腿":     dict(kind="leg",  atk=8,  hp=50,  energy=10, initiative=2, dodge=0.05, price=200, sticky=True),
    "震撼腿":   dict(kind="leg",  atk=7,  hp=50,  energy=10, initiative=2, dodge=0.05, price=200, shock=True),
    # 躯干(供能来源,血空即败;command=基础指挥点——无头时的"脊髓反射"底线)
    # Akun 2026-07-15 拍板:基础指挥 2/3/3,价格按新公式(1供能=5价)350/700/700,供能 30/60/80
    "新手躯干":       dict(kind="torso", atk=0, hp=100, supply=30, command=2, price=350),
    "稍微长大的躯干": dict(kind="torso", atk=0, hp=200, supply=60, command=3, price=700),
    "有些肌肉的躯干": dict(kind="torso", atk=0, hp=150, supply=80, command=3, price=700),
    # Akun 2026-07-22 第二批(053a9a0)。⚠️ 臃肿的躯干基础指挥 4 触碰敏感参数(无头流),入库即探针
    "强能躯干":       dict(kind="torso", atk=0, hp=145, supply=90, command=3, price=750),
    "臃肿的躯干":     dict(kind="torso", atk=0, hp=300, supply=60, command=4, price=850),
    # 尾巴(独立位不占四肢槽,Q9 暂限 1;E8:不可被攻击)
    "新手尾巴": dict(kind="tail", atk=0, hp=0, initiative=1, price=20),
    "猛尾":     dict(kind="tail", atk=0, hp=0, initiative=2, price=40),
    # 扩槽件(只占预算、扩槽位,不参战)
    "四肢插槽": dict(kind="slot", atk=0, hp=0, price=30),   # +1 手/腿位(Q2)
    "头部插槽": dict(kind="slot", atk=0, hp=0, price=50),   # +1 头位(Q2)
    # 装饰件(PVE 起始装,Q13;Akun 2026-07-15 血量 0:纯摆设,不可当肉墙——Q16 的回答)
    "装饰手":   dict(kind="hand", atk=0, hp=0, energy=0, price=0),
    "装饰腿":   dict(kind="leg",  atk=0, hp=0, energy=0, initiative=0, dodge=0.0, price=0),
    # PVE 专属敌方部件(03-pve 前三关)
    "鹿躯干":     dict(kind="torso", atk=0, hp=50,  supply=99, command=99, pve=True, price=0),
    "猛犸象头":   dict(kind="head",  atk=2, hp=75,  hits=2, pve=True, price=0),   # 双击:2 攻 ×2 次
    "猛犸象躯干": dict(kind="torso", atk=0, hp=200, supply=99, command=99, pve=True, price=0),
    "剑齿虎头":   dict(kind="head",  atk=5, hp=100, pve=True, price=0),
    "剑齿虎躯干": dict(kind="torso", atk=0, hp=100, supply=99, command=99, pve=True, price=0),
    "剑齿虎爪":   dict(kind="hand",  atk=2, hp=50,  pve=True, price=0),
    # 机制件原型(Q15 提案,数值未定价,仅供模拟验证;Akun 拍板后再进零件表)
    "猎臂头":     dict(kind="head",  atk=15, hp=75, energy=20, command=2, hunts="hand", price=400),
}

# 插件目录(Akun 2026-07-15 零件表;Q17e:插件无血量、随宿主生效、装配期自由拆装、每部件限 1)
#   pos:可挂载的宿主类型;数值字段是该插件的机制参数,引擎读取
#   ⚠️ 普通能量核心也是"身体"位插件 → 与耐火皮肤/尖刺皮肤竞争躯干唯一插件位
PLUGINS = {
    "头顶角质层": dict(pos=("head",), price=60, absorbs=2),           # 替头挡 2 次攻击,生效期间该头不暴击
    "头顶尖刺":   dict(pos=("head",), price=20, crit_bonus=0.05),     # 宿主头暴击率 +5%
    "骨盾":       dict(pos=("hand",), price=50, block_mult=0.80),     # 宿主手格挡成功时,承受伤害再 ×80%
    "胶质瘤":     dict(pos=("hand",), price=40, heal=2, rounds=5),    # 宿主手被破后,其他部位每回合回 2 血 ×5 回合
    "肾上腺素":   dict(pos=("leg",),  price=40, heal=5),              # 宿主腿被破后,其他部位立即回 5 血
    "爆裂腺体":   dict(pos=("hand", "leg"), price=60, dmg=40),        # 宿主手/腿被破后,对破坏者造成 40 伤害
    "耐火皮肤":   dict(pos=("torso",), price=50),                     # 宿主(躯干)火焰伤害 -50%,免疫灼烧
    "撕裂爪":     dict(pos=("hand",), price=50, atk_delta=-2, tear_rounds=5),  # 宿主手 -2 攻,命中挂撕裂 2/回合 ×5
    "碎骨锥":     dict(pos=("leg",),  price=40, stun_prob=0.5),       # 宿主腿命中后 50% 使被击中部件下回合不能行动
    "尖刺皮肤":   dict(pos=("torso",), price=30, tear_rounds=2),      # 宿主(躯干)受伤时,对攻击部件挂撕裂 2/回合 ×2
    "普通能量核心": dict(pos=("torso",), price=100, supply=20),       # 供能 +20
    # ---- 第二批插件(Akun 2026-07-22,细则 Q22)----
    "耐毒皮肤":   dict(pos=("torso",), price=50),                     # 毒素伤害 -50%,免疫中毒(全身,Q22q)
    "耐冰皮肤":   dict(pos=("torso",), price=50),                     # 冰冻伤害 -50%,免疫冻结(全身,Q22q)
    "火蜥蜴尾巴": dict(pos=("tail",), price=40, burn_bonus=2),        # 全队灼烧+2/回合;全身火伤 -20%;与尾巴头互斥
    "毒蛇尾巴":   dict(pos=("tail",), price=40, poison_bonus=1),      # 全队中毒+1/回合、降攻+1;全身毒伤 -20%;互斥同上
    "冰虫尾巴":   dict(pos=("tail",), price=40, freeze_bonus=0.15, initiative=1),  # 冻结+15%、先攻+1;冰伤-20%;互斥同上
    "先守后攻":   dict(pos=("leg",),  price=25),                      # 指向宿主腿的攻击被闪避后,该腿立即反击 1 次(Q22o)
    "头槌":       dict(pos=("head",), price=50, atk_delta=4),         # 宿主头 +4 攻
    "认真一拳":   dict(pos=("hand",), price=30, crit_mult_bonus=0.5), # 宿主手暴击倍率 2.0→2.5(Q22p)
}


def make(name: str, slot: int = 0, plugin: str = "") -> Part:
    spec = CATALOG.get(name)
    if spec is None:
        if name in PLUGINS:
            raise KeyError(f"「{name}」是插件,不能当独立零件——用 plugin= 挂到宿主部件上")
        raise KeyError(f"未知零件「{name}」——检查拼写,或 sim/parts.py CATALOG 是否与零件表同步")
    p = Part(name=name, max_hp=spec["hp"], slot=slot,
             **{k: v for k, v in spec.items() if k != "hp"}, hp=spec["hp"])
    if plugin:
        pspec = PLUGINS.get(plugin)
        if pspec is None:
            raise KeyError(f"未知插件「{plugin}」——检查拼写或 PLUGINS 是否与零件表同步")
        p.plugin = plugin
        p.atk = max(0, p.atk + pspec.get("atk_delta", 0))   # 撕裂爪 -2 攻
        p.crit = p.crit + pspec.get("crit_bonus", 0.0)      # 头顶尖刺 +5%
    return p


def plugin_price(name: str) -> int:
    return PLUGINS[name]["price"] if name else 0
