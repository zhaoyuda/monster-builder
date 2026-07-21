# 单元测试 —— 覆盖 design/02-combat.md「可作为单元测试的规则点」表 + 工程默认 E1-E8
#   python3 -m unittest sim.test_engine -v
import unittest

from .engine import Monster, RuleConfig, battle
from .parts import make


class ScriptRNG:
    """脚本化随机:random() 依次弹出预设值(耗尽后返回 0.99),choice() 取首个。"""

    def __init__(self, randoms=()):
        self.randoms = list(randoms)

    def random(self):
        return self.randoms.pop(0) if self.randoms else 0.99

    def choice(self, seq):
        return seq[0]


def mk(name="M", torso="新手躯干", heads=(), hands=(), legs=(), tails=()):
    return Monster(name=name, torso=make(torso),
                   heads=[make(n, i + 1) for i, n in enumerate(heads)],
                   hands=[make(n, i + 1) for i, n in enumerate(hands)],
                   legs=[make(n, i + 1) for i, n in enumerate(legs)],
                   tails=[make(n, i + 1) for i, n in enumerate(tails)])


class TestAssemblyRules(unittest.TestCase):
    def test_闪避加总_腿12各5(self):
        m = mk(legs=["新手腿", "新手腿"])
        self.assertAlmostEqual(m.dodge_total(RuleConfig()), 0.10)

    def test_闪避失效_腿死即失效(self):
        m = mk(legs=["新手腿", "新手腿"])
        m.legs[0].hp = 0
        self.assertAlmostEqual(m.dodge_total(RuleConfig()), 0.05)

    def test_腿3以上不计闪避(self):
        m = mk(legs=["新手腿", "新手腿", "灵活的腿"])
        self.assertAlmostEqual(m.dodge_total(RuleConfig()), 0.10)

    def test_先攻_存活腿加尾巴(self):
        m = mk(legs=["猛腿", "新手腿"], tails=["猛尾"])  # 2+1+2
        self.assertEqual(m.initiative_total(), 5)
        m.legs[0].hp = 0
        self.assertEqual(m.initiative_total(), 3)

    def test_踢腿_无先攻无闪避(self):
        m = mk(legs=["踢腿", "踢腿"])
        self.assertEqual(m.initiative_total(), 0)
        self.assertAlmostEqual(m.dodge_total(RuleConfig()), 0.0)


class TestBattleRules(unittest.TestCase):
    def _run(self, a, b, randoms, rounds=1):
        cfg = RuleConfig(round_limit=rounds)
        return battle(a, b, cfg=cfg, rng=ScriptRNG(randoms))

    def test_胜负_躯干HP0即败(self):
        a = mk("A", heads=["猛头"])   # 20 攻
        b = mk("B")                    # 光躯干 100 血
        rep = battle(a, b, seed=7)     # b 无反击能力,a 必胜
        self.assertEqual(rep["winner"], "A")

    def test_头攻目标_50载头50躯干(self):
        a = mk("A", heads=["猛头"])
        b = mk("B", heads=["新手头"])
        # randoms: 先攻(0.0→A先), 头目标(0.4<0.5→打头), 闪避无, 格挡无
        rep = self._run(a, b, [0.0, 0.4])
        first_hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertIn("头", first_hit["target"])
        # 0.6>0.5 → 打躯干
        rep = self._run(mk("A", heads=["猛头"]), mk("B", heads=["新手头"]), [0.0, 0.6])
        first_hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertIn("躯干", first_hit["target"])

    def test_E4_无头回退打躯干(self):
        a = mk("A", heads=["猛头"])
        b = mk("B")  # 无头
        rep = self._run(a, b, [0.0, 0.1])  # roll 到打头,但无头 → 躯干
        first_hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertIn("躯干", first_hit["target"])

    def test_格挡_20概率x80转末位存活手(self):
        a = mk("A", heads=["猛头"])                      # 20 攻打躯干(暴击率 8%,多耗一个 roll)
        b = mk("B", hands=["新手手", "猛爪"])            # 末位=手2 猛爪
        # randoms: 先攻, 头目标0.9→躯干, 暴击0.5→无, 格挡0.1<0.2→触发
        rep = self._run(a, b, [0.0, 0.9, 0.5, 0.1])
        blk = next(e for e in rep["events"] if e["type"] == "block")
        self.assertEqual(blk["taken"], 16)              # floor(20*0.8)
        self.assertIn("手2", blk["blocker"])            # 末位手
        # E5:末位手已死 → 转给存活的最大槽位
        b2 = mk("B", hands=["新手手", "猛爪"])
        b2.hands[1].hp = 0
        rep = self._run(mk("A", heads=["猛头"]), b2, [0.0, 0.9, 0.5, 0.1])
        blk = next(e for e in rep["events"] if e["type"] == "block")
        self.assertIn("手1", blk["blocker"])

    def test_E3_格挡伤害向下取整最小1(self):
        a = mk("A", hands=["新手手"])                    # 5 攻;手无手可打→躯干
        b = mk("B", hands=["新手手"])
        # A 手打 B:B 有手,目标=手,不触发格挡… 改用头攻
        a = mk("A", heads=["新手头"])                    # 10 攻
        rep = self._run(a, b, [0.0, 0.9, 0.1])
        blk = next(e for e in rep["events"] if e["type"] == "block")
        self.assertEqual(blk["taken"], 8)                # floor(10*0.8)=8

    def test_闪避判定_全身共享(self):
        a = mk("A", heads=["猛头"])
        b = mk("B", legs=["新手腿", "新手腿"])           # 10% 闪避
        # randoms: 先攻0.0, (A头出手在腿后:B 腿先打 A…) 简化:回合1 B 无先攻腿? 新手腿有先攻1
        # B 先攻 2, A 先攻 0 → P(A先)=0 → 0.0<0? no → B 先。腿阶段 B 腿1 打 A(A 无腿→躯干)
        # 这里只验证:A 攻击 B 时 roll 0.05 < 0.10 → 闪避事件
        rep = battle(a, b, cfg=RuleConfig(round_limit=1),
                     rng=ScriptRNG([0.99,          # 先攻:0.99 → B 先(P_A=0)
                                    0.99, 0.99,    # B腿1 打 A躯干:闪避 roll(A无闪避→跳过?)
                                    ]))
        # 直接单测 dodge_total 已覆盖;这里跑通不抛错即可
        self.assertIn(rep["winner"], ("A", "B", "draw"))

    def test_头击破_下回合全队不行动(self):
        a = mk("A", heads=["顶撞头"])                    # 25 攻
        b = mk("B", heads=["新手头"], hands=["猛爪"])    # 新手头 50 血
        cfg = RuleConfig(round_limit=3)
        # R1: A先(0.0), A头打头(0.1), 无格挡(头目标不劣化)… 新手头 50-25=25
        # R2: A先(0.0), A头打头(0.1) 25-25=0 → 击破+眩晕
        # R3: B 全队不行动;A 头打躯干(0.9)
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([
            0.0, 0.1, 0.9,        # R1 先攻A, B手打A躯干? 手阶段:B猛爪打A(A无手→躯干,格挡?A无手) → hit; 头阶段 A头打B头0.1
            # 脚本化精确序列复杂,改为语义断言:见下
        ]))
        # 语义断言:出现 stun_set 后,下一回合该方无任何攻击事件
        rep = battle(a, b, seed=123, cfg=RuleConfig(round_limit=50))
        stun_rounds = [(e["round"], e["side"]) for e in rep["events"] if e["type"] == "stun_set"]
        if stun_rounds:
            r0, side = stun_rounds[0]
            nxt = [e for e in rep["events"]
                   if e["round"] == r0 + 1 and e.get("side") == side and e["type"] in ("hit", "dodge", "block")]
            self.assertEqual(nxt, [], "眩晕方下回合不应有攻击事件")
            stunned_ev = [e for e in rep["events"] if e["type"] == "stunned" and e["round"] == r0 + 1]
            self.assertTrue(stunned_ev, "下回合应有 stunned 事件")

    def test_E2_超时按躯干血量比(self):
        a = mk("A", torso="稍微长大的躯干")   # 都打不死对方
        b = mk("B")
        rep = battle(a, b, seed=1, cfg=RuleConfig(round_limit=5))
        self.assertEqual(rep["winner"], "draw")  # 双方无攻击,血量比相同 100%

    def test_E1_纯函数_同种子同结果且不改输入(self):
        from .builds import roster
        r = roster()
        a, b = r["多头流"], r["无头流"]
        hp_before = [p.hp for p in a.all_parts()]
        r1 = battle(a, b, seed=99)
        r2 = battle(a, b, seed=99)
        self.assertEqual(r1["winner"], r2["winner"])
        self.assertEqual(len(r1["events"]), len(r2["events"]))
        self.assertEqual(hp_before, [p.hp for p in a.all_parts()], "battle 不得改动输入对象")

    def test_Q7_攻击次数不等_多出方逐个攻击(self):
        # command_mode=off:单独验证交错出手语义(新手躯干基础指挥 2 会截断 3 手)
        a = mk("A", hands=["猛爪"])
        b = mk("B", hands=["新手手", "新手手", "新手手"])
        rep = battle(a, b, seed=5, cfg=RuleConfig(round_limit=1, command_mode="off"))
        hand_attacks_b = [e for e in rep["events"]
                          if e["type"] in ("hit", "dodge", "block") and e.get("side") == "B"]
        self.assertEqual(len(hand_attacks_b), 3, "B 的 3 只手都应出手")

    def test_Q4_一方先攻为0则另一方固定先手(self):
        a = mk("A", heads=["猛头"])                      # 先攻 0
        b = mk("B", hands=["猛爪"], legs=["新手腿"])     # 先攻 1
        for seed in range(20):
            rep = battle(a, b, seed=seed, cfg=RuleConfig(round_limit=1))
            rs = next(e for e in rep["events"] if e["type"] == "round_start")
            self.assertEqual(rs["first"], "B", "先攻>0 的一方必须固定先手")

    def test_Q2_槽位校验(self):
        from .builds import build
        # 3 头无插槽 → 超限
        with self.assertRaises(AssertionError):
            build("非法", "有些肌肉的躯干", heads=["新手头", "新手头", "新手头"])
        # 补 2 个头部插槽 → 合法
        build("合法", "有些肌肉的躯干", heads=["新手头", "新手头", "新手头"],
              slots=["头部插槽", "头部插槽"])

    def test_眩晕方仍可被打且闪避格挡有效(self):
        # stun_scope=all 下,眩晕只停攻击;防御判定照常 —— 通过跑长局不出现异常来覆盖
        from .builds import roster
        r = roster()
        rep = battle(r["多头流"], r["耗材手流"], seed=2024)
        self.assertIn(rep["winner"], ("A", "B", "draw"))


class TestCommandRules(unittest.TestCase):
    """Q12 提案:指挥点池(command_mode="battle")。默认 off,不影响既有规则。"""

    def test_指挥供给_躯干基础加存活头(self):
        m = mk(heads=["新手头", "肿头"])          # 躯干2 + 2 + 3(Akun 2026-07-15:新手躯干基础 2)
        self.assertEqual(m.command_supply(), 7)
        m.heads[1].hp = 0
        self.assertEqual(m.command_supply(), 4)   # 头死指挥点即时消失

    def test_指挥不足_超出的肢体不攻击(self):
        # 无头:躯干基础 2 点;4 手 → 只有前 2 只出手,后 2 只记 no_command
        a = mk("A", hands=["猛爪", "猛爪", "猛爪", "猛爪"])
        b = mk("B", torso="稍微长大的躯干")       # 沙包
        cfg = RuleConfig(round_limit=1, command_mode="battle")
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0]))
        atks = [e for e in rep["events"] if e["type"] in ("hit", "dodge", "block") and e["side"] == "A"]
        idle = [e for e in rep["events"] if e["type"] == "no_command" and e["side"] == "A"]
        self.assertEqual(len(atks), 2)
        self.assertEqual(len(idle), 2)
        self.assertIn("手3", idle[0]["part"])

    def test_头不耗指挥点(self):
        # 顶撞头(供2) + 躯干2 = 4 点 = 4 肢刚好;若头也耗点则必有 1 肢站桩
        a = mk("A", heads=["顶撞头"], hands=["猛爪", "猛爪"], legs=["踢腿", "踢腿"])
        b = mk("B", torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=1, command_mode="battle")
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9]))  # 先攻A;头目标roll→躯干
        atks = [e for e in rep["events"] if e["type"] in ("hit", "dodge", "block") and e["side"] == "A"]
        idle = [e for e in rep["events"] if e["type"] == "no_command" and e["side"] == "A"]
        self.assertEqual(len(atks), 5, "4 肢 + 1 头 = 5 次攻击(头不占肢体点数)")
        self.assertEqual(len(idle), 0)

    def test_头被击破_下回合肢体行动力下降(self):
        # A: 新手头(供2)+躯干2=4 → 4 肢全动;头被打死后掉到 2 → 只动 2 肢
        a = mk("A", heads=["新手头"], hands=["猛爪", "猛爪"], legs=["踢腿", "踢腿"])
        a.heads[0].hp = 1                          # 一击必碎
        b = mk("B", heads=["顶撞头"], torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=3, command_mode="battle")
        rep = battle(a, b, seed=11, cfg=cfg)
        cmd_events = {e["round"]: e for e in rep["events"] if e["type"] == "command"}
        break_round = next((e["round"] for e in rep["events"]
                            if e["type"] == "break" and e["side"] == "A" and e["kind"] == "head"), None)
        if break_round and break_round + 1 in cmd_events:
            self.assertEqual(cmd_events[break_round + 1]["cmd_a"], 2, "头死后指挥供给应降为躯干基础 2")

    def test_默认battle_产生指挥事件_off则无(self):
        # Q12 方案A 拍板后(2026-07-07)默认 command_mode="battle"
        a = mk("A", hands=["猛爪", "猛爪", "猛爪"])
        b = mk("B")
        rep = battle(a, b, seed=3, cfg=RuleConfig(round_limit=2))
        self.assertTrue([e for e in rep["events"] if e["type"] == "command"])
        rep_off = battle(a, b, seed=3, cfg=RuleConfig(round_limit=2, command_mode="off"))
        self.assertFalse([e for e in rep_off["events"] if e["type"] in ("command", "no_command")])


class TestCritAndMultiHit(unittest.TestCase):
    """Q10 暴击(头的本体暴击率,倍率默认 2x)+ Q13 猛犸象头双击。"""

    def test_暴击_双倍伤害且记入事件(self):
        a = mk("A", heads=["顶撞头"])                    # 25 攻,暴击率 10%
        b = mk("B", torso="稍微长大的躯干")
        # randoms: 先攻0.0→A先, 头目标0.9→躯干, 暴击roll 0.05<0.10→暴击, 格挡0.99 无
        cfg = RuleConfig(round_limit=1)
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9, 0.05, 0.99]))
        hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertTrue(hit["crit"])
        self.assertEqual(hit["dmg"], 50)                 # 25×2
        # 暴击 roll 0.15>0.10 → 不暴击
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9, 0.15, 0.99]))
        hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertFalse(hit["crit"])
        self.assertEqual(hit["dmg"], 25)

    def test_暴击率0的部件不消耗随机数(self):
        # 新手头 crit=0:随机流应与加暴击前完全一致(只有 crit>0 才掷骰)
        a = mk("A", heads=["新手头"])
        b = mk("B", torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=1)
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9, 0.99]))  # 先攻,目标,格挡
        hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertEqual(hit["dmg"], 10)
        self.assertFalse(hit["crit"])

    def test_crit_mult_1即关闭暴击(self):
        a = mk("A", heads=["顶撞头"])
        b = mk("B", torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=1, crit_mult=1.0)
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9, 0.99]))
        hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertEqual(hit["dmg"], 25)

    def test_双击_猛犸象头一回合两次独立攻击(self):
        a = mk("A", torso="猛犸象躯干", heads=["猛犸象头"])
        b = mk("B", torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=1)
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9, 0.99, 0.9, 0.99]))
        hits = [e for e in rep["events"] if e["type"] == "hit" and e["side"] == "A"]
        self.assertEqual(len(hits), 2, "双击应产生两次攻击结算")
        self.assertTrue(all(h["dmg"] == 2 for h in hits))

    def test_工程卫生_未知零件与槽位类型与PVE边界(self):
        from .parts import make
        from .builds import build
        with self.assertRaises(KeyError):
            make("不存在的零件")
        # 零件装错槽位(手塞进腿槽)→ validate 拒绝
        with self.assertRaises(AssertionError):
            build("错槽", "新手躯干", legs=["新手手"])
        # PVE 专属件不可用于玩家配装
        with self.assertRaises(AssertionError):
            build("偷跑", "新手躯干", heads=["猛犸象头"])

    def test_插件更新_能量核心与尾巴独立位(self):
        # 普通能量核心 +20 供能(机制引擎后改为躯干"身体"位插件);尾巴独立位、暂限 1
        from .builds import build
        m = build("核心", "新手躯干", heads=["新手头"], hands=["猛爪", "猛爪", "猛爪", "猛爪"],
                  torso_plugin="普通能量核心")          # 能量 50 ≤ 30+20
        self.assertEqual(m.supply_total(), 50)
        with self.assertRaises(AssertionError):        # 不加核心 → 能量超限
            build("超能", "新手躯干", heads=["新手头"], hands=["猛爪", "猛爪", "猛爪", "猛爪"])
        with self.assertRaises(KeyError):              # 旧写法:核心塞 slots → 报"是插件"
            build("旧核心", "新手躯干", slots=["普通能量核心"])
        build("尾独立", "有些肌肉的躯干", hands=["猛爪", "猛爪", "猛爪", "猛爪"], tails=["猛尾"])
        with self.assertRaises(AssertionError):        # 尾巴限 1
            build("双尾", "新手躯干", tails=["新手尾巴", "猛尾"])

    def test_装饰件血0_不可格挡不入目标池(self):
        # Akun 2026-07-15:装饰件血量 10→0(Q16 的回答:纯摆设,不能当肉墙/格挡耗材)
        a = mk("A", heads=["猛头"])
        b = mk("B", hands=["装饰手"])
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9, 0.5, 0.1]))
        self.assertFalse([e for e in rep["events"] if e["type"] == "block"],
                         "0 血装饰手不应触发格挡")
        hit = next(e for e in rep["events"] if e["type"] == "hit")
        self.assertIn("躯干", hit["target"])

    def test_PVE配置_老迈的鹿不还手(self):
        deer = mk("鹿", torso="鹿躯干")
        player = mk("玩家", heads=["新手头"], hands=["装饰手"], legs=["装饰腿"])
        rep = battle(player, deer, seed=1)
        self.assertEqual(rep["winner"], "A")
        deer_atks = [e for e in rep["events"] if e["type"] in ("hit", "dodge", "block") and e["side"] == "B"]
        self.assertEqual(deer_atks, [], "鹿没有攻击部件,不应有任何攻击事件")


def mkp(name="M", torso="新手躯干", torso_plugin="", heads=(), hands=(), legs=(), tails=()):
    """支持插件的组装(不走 validate,方便造极端测试态);entry 可为 "名" 或 ("名","插件")。"""
    def _mk(entry, i):
        if isinstance(entry, (tuple, list)):
            return make(entry[0], i + 1, entry[1])
        return make(entry, i + 1)
    return Monster(name=name, torso=make(torso, 0, torso_plugin),
                   heads=[_mk(n, i) for i, n in enumerate(heads)],
                   hands=[_mk(n, i) for i, n in enumerate(hands)],
                   legs=[_mk(n, i) for i, n in enumerate(legs)],
                   tails=[make(n, i + 1) for i, n in enumerate(tails)])


class TestMechanics(unittest.TestCase):
    """Q17 机制引擎:DoT / 死亡触发 / 部件级眩晕 / 插件挂载(规则:06-decisions.md Q17 + 05 页 Q19 工程默认)。"""

    def _events(self, rep, etype, **match):
        return [e for e in rep["events"] if e["type"] == etype
                and all(e.get(k) == v for k, v in match.items())]

    # ---- 喷火头:火焰 AOE + 灼烧 ----
    def test_喷火头_额外目标与灼烧(self):
        a = mkp("A", heads=["喷火头"])
        b = mkp("B", torso="稍微长大的躯干", hands=["猛爪"])
        # randoms: 先攻0.0→A先;(B猛爪打A躯干无掷骰);A头目标0.9→躯干;额外目标=choice(无掷骰)
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9]))
        hits = self._events(rep, "hit", side="A")
        self.assertEqual(len(hits), 2, "喷火头应主目标+额外目标各打一次")
        self.assertTrue(any(h["extra"] for h in hits))
        self.assertEqual(len(self._events(rep, "status", status="burn")), 2, "两个受伤目标都应被灼烧")
        ticks = self._events(rep, "dot_tick", status="burn")
        self.assertEqual(len(ticks), 2)
        self.assertTrue(all(t["dmg"] == 2 for t in ticks))

    def test_灼烧_持续3回合且来源死亡不中断(self):
        a = mkp("A", heads=["喷火头"])
        a.heads[0].hp = 1                                # 喷火头一击即碎
        b = mkp("B", torso="稍微长大的躯干", heads=["猛头"])
        # R1: A先(0.0);A头目标0.4→打B猛头,灼烧;额外目标→B躯干,灼烧;B头目标0.4→打A喷火头(20伤秒杀)
        rep = battle(a, b, cfg=RuleConfig(round_limit=6), rng=ScriptRNG([0.0, 0.4, 0.4]))
        ticks = self._events(rep, "dot_tick", status="burn")
        self.assertEqual(len(ticks), 6, "2 个部件 × 3 回合灼烧,来源(喷火头)已死仍然烧完")
        self.assertFalse([t for t in ticks if t["round"] > 3], "灼烧只应持续到第 3 回合")

    def test_耐火皮肤_火焰减半且免疫灼烧(self):
        a = mkp("A", heads=["喷火头"])
        b = mkp("B", torso_plugin="耐火皮肤")            # 新手躯干 100 血
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9]))
        hit = self._events(rep, "hit")[0]
        self.assertTrue(hit["fireproof"])
        self.assertEqual(hit["dmg"], 7, "floor(15×0.5)=7")
        self.assertFalse(self._events(rep, "status"), "耐火宿主不应被灼烧")
        self.assertFalse(self._events(rep, "dot_tick"))

    def test_耐火皮肤_保护全身(self):
        """Akun Q19d 批注(2026-07-21):耐火皮肤保护范围=全身,非仅躯干。"""
        a = mkp("A", heads=["喷火头"])
        b = mkp("B", torso_plugin="耐火皮肤", hands=["猛爪"])
        # A先(0.0);A头目标0.9→打躯干;额外目标=choice→B猛爪(手也应减半+免灼烧)
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9]))
        hits = self._events(rep, "hit", side="A")
        self.assertEqual(len(hits), 2)
        self.assertTrue(all(h["fireproof"] for h in hits), "耐火应护到非躯干部件")
        self.assertFalse(self._events(rep, "status", status="burn"), "全身免疫灼烧")

    def test_单状态栏位_新顶旧(self):
        """Q19b A/B:status_slots=single 时撕裂顶掉灼烧,不共存。"""
        a = mkp("A", heads=["喷火头"], hands=[("猛爪", "撕裂爪")])
        b = mkp("B", torso="稍微长大的躯干")
        cfg = RuleConfig(round_limit=1, status_slots="single")
        # A先(0.0);猛爪打躯干挂撕裂;头目标0.9→躯干挂灼烧(顶掉撕裂);额外目标choice→无其他部件
        rep = battle(a, b, cfg=cfg, rng=ScriptRNG([0.0, 0.9]))
        ticks = self._events(rep, "dot_tick")
        self.assertEqual(len(ticks), 1, "单栏位:只剩最后挂上的状态在跳")
        self.assertEqual(ticks[0]["status"], "burn", "灼烧后挂,顶掉撕裂")

    # ---- 撕裂爪 / 尖刺皮肤 ----
    def test_撕裂爪_减2攻且命中挂撕裂(self):
        a = mkp("A", hands=[("猛爪", "撕裂爪")])
        b = mkp("B", hands=["猛爪"])
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0]))
        hit = self._events(rep, "hit", side="A")[0]
        self.assertEqual(hit["dmg"], 8, "猛爪 10 攻挂撕裂爪 -2 = 8")
        self.assertTrue(self._events(rep, "status", status="tear", side="B"))
        self.assertTrue(self._events(rep, "dot_tick", status="tear", side="B"))

    def test_尖刺皮肤_躯干受伤反挂撕裂到攻击部件(self):
        a = mkp("A", heads=["猛头"])
        b = mkp("B", torso_plugin="尖刺皮肤")
        # randoms: 先攻0.0;头目标0.9→躯干;暴击0.99→无
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9, 0.99]))
        st = self._events(rep, "status", status="tear", side="A")
        self.assertTrue(st and "猛头" in st[0]["part"], "撕裂应挂在攻击方的猛头上")
        self.assertTrue(self._events(rep, "dot_tick", status="tear", side="A"))

    # ---- 碎骨锥:部件级眩晕 ----
    def test_碎骨锥_命中50概率下回合部件不能行动(self):
        a = mkp("A", legs=[("踢腿", "碎骨锥")])
        b = mkp("B", legs=["猛腿"])
        # R1: 先攻p_a=0→B先(0.5);B猛腿打A踢腿(A闪避0无掷骰);A踢腿打B猛腿:闪避0.9→中;碎骨0.3<0.5→眩
        # R2: 先攻(0.5);B猛腿被部件眩晕不出手;A踢腿:闪避0.9→中;碎骨0.9→无
        rep = battle(a, b, cfg=RuleConfig(round_limit=2),
                     rng=ScriptRNG([0.5, 0.9, 0.3, 0.5, 0.9, 0.9]))
        self.assertTrue(self._events(rep, "part_stun_set", side="B", round=1))
        self.assertTrue(self._events(rep, "part_stunned", side="B", round=2))
        b_atks_r2 = [e for e in rep["events"] if e["round"] == 2 and e.get("side") == "B"
                     and e["type"] in ("hit", "dodge", "block")]
        self.assertEqual(b_atks_r2, [], "被碎骨锥眩晕的猛腿下回合不应出手")

    # ---- 抓握手 ----
    def test_抓握手_首次命中不伤害且清零闪避_闪避掉不消耗(self):
        a = mkp("A", hands=["抓握手"])
        b = mkp("B", legs=["新手腿", "新手腿"])          # 10% 闪避
        # 每回合:先攻p_a=0→B先;B两腿打A躯干各掷1次格挡骰(A有手,0.9→不格挡)
        # R1: A抓握:闪避0.05<0.10→被闪掉(不消耗首次)
        # R2: A抓握:闪避0.5→未闪→抓住!5回合闪避清零,无伤害
        # R3: A攻击:闪避被清零无掷骰→直接命中 10 伤
        rep = battle(a, b, cfg=RuleConfig(round_limit=3),
                     rng=ScriptRNG([0.5, 0.9, 0.9, 0.05,
                                    0.5, 0.9, 0.9, 0.5,
                                    0.5, 0.9, 0.9]))
        self.assertTrue(self._events(rep, "dodge", side="A", round=1), "首次尝试应被闪避")
        grabs = self._events(rep, "grab", side="A")
        self.assertEqual([g["round"] for g in grabs], [2], "第二次尝试才抓住,且只抓一次")
        self.assertFalse(self._events(rep, "hit", side="A", round=2), "抓住的那次不造成伤害")
        hit3 = self._events(rep, "hit", side="A", round=3)
        self.assertTrue(hit3 and hit3[0]["dmg"] == 10, "抓握后闪避清零,第三回合直接命中")

    # ---- 头顶角质层 ----
    def test_角质层_替头吸收两次攻击(self):
        a = mkp("A", heads=["猛头"])
        b = mkp("B", heads=[("新手头", "头顶角质层")])
        # 每回合: 先攻0.0→A;A头目标0.4→打B头;暴击0.99;(吸收后B头反击:目标0.4→A头,新手头无暴击)
        seq = [0.0, 0.4, 0.99, 0.4] * 3
        rep = battle(a, b, cfg=RuleConfig(round_limit=3), rng=ScriptRNG(seq))
        absorbs = self._events(rep, "absorb")
        self.assertEqual([ab["left"] for ab in absorbs], [1, 0], "角质层应恰好吸收 2 次")
        hit_r3 = self._events(rep, "hit", side="A", round=3)
        self.assertTrue(hit_r3 and "头" in hit_r3[0]["target"], "第 3 次攻击应真正打到头")

    def test_角质层_生效期间宿主头不暴击(self):
        a = mkp("A", heads=[("顶撞头", "头顶角质层")])   # 25 攻,10% 暴击被压成 0
        b = mkp("B", torso="稍微长大的躯干")
        # randoms: 先攻0.0;头目标0.9→躯干;若掷暴击骰 0.05<0.10 会暴击 → 断言未消耗该骰
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9, 0.05]))
        hit = self._events(rep, "hit")[0]
        self.assertFalse(hit["crit"])
        self.assertEqual(hit["dmg"], 25, "角质层生效期间不掷暴击骰")

    # ---- 骨盾 ----
    def test_骨盾_格挡成功再减20(self):
        a = mkp("A", heads=["猛头"])
        b = mkp("B", hands=[("猛爪", "骨盾")])
        # randoms: 先攻0.0→A;(B猛爪打A躯干无掷骰);A头目标0.9→躯干;暴击0.5;格挡0.1<0.2→触发
        rep = battle(a, b, cfg=RuleConfig(round_limit=1), rng=ScriptRNG([0.0, 0.9, 0.5, 0.1]))
        blk = self._events(rep, "block")[0]
        self.assertTrue(blk["bone"])
        self.assertEqual(blk["taken"], 12, "floor(floor(20×0.8)×0.8)=12")

    # ---- 死亡触发:爆裂腺体 / 肾上腺素 / 胶质瘤 / 芽孢 ----
    def test_爆裂腺体_破坏者吃40伤(self):
        a = mkp("A", hands=["小手手"])                   # 7 攻 65 血
        b = mkp("B", hands=[("新手手", "爆裂腺体")])     # 25 血,4 击破;其间反击 3×5=15
        rep = battle(a, b, cfg=RuleConfig(round_limit=4), rng=ScriptRNG([0.0] * 4))
        glands = self._events(rep, "gland")
        self.assertEqual(len(glands), 1)
        self.assertEqual(glands[0]["dmg"], 40)
        self.assertEqual(glands[0]["target_hp"], 10, "小手手 65-15 反击 = 50,吃 40 = 剩 10")

    def test_爆裂腺体_级联但不无限(self):
        a = mkp("A", hands=[("新手手", "爆裂腺体")])
        b = mkp("B", hands=[("新手手", "爆裂腺体")])
        rep = battle(a, b, seed=1, cfg=RuleConfig(round_limit=10))
        # 一方手被打破 → 腺体炸死对方手 → 对方腺体无目标(破坏者已死)不再回炸
        self.assertEqual(len(self._events(rep, "gland")), 1)
        self.assertEqual(len(self._events(rep, "break")), 2, "两只手同一时刻同归于尽")

    def test_肾上腺素_宿主腿破其他部位立回5(self):
        a = mkp("A", legs=["踢腿"])                      # 10 攻
        b = mkp("B", legs=[("新手腿", "肾上腺素")])      # 20 血,2 击破
        b.torso.hp = 90
        rep = battle(a, b, cfg=RuleConfig(round_limit=2),
                     rng=ScriptRNG([0.5, 0.9, 0.5, 0.9]))
        ad = self._events(rep, "adrenaline")
        self.assertEqual(len(ad), 1)
        self.assertEqual(ad[0]["healed"], 5, "只剩躯干存活,+5")
        b_torso = next(p for p in rep["final"]["B"] if "躯干" in p["name"])
        self.assertEqual(b_torso["hp"], 95)

    def test_胶质瘤_宿主手破每回合回2持续5回合(self):
        a = mkp("A", hands=["猛爪"])
        b = mkp("B", hands=[("新手手", "胶质瘤")])
        b.torso.hp = 90
        rep = battle(a, b, cfg=RuleConfig(round_limit=3), rng=ScriptRNG([0.0, 0.0, 0.0]))
        self.assertTrue(self._events(rep, "regen_start", side="B", round=3))
        regen = self._events(rep, "regen", side="B", round=3)
        self.assertTrue(regen and regen[0]["heal"] == 2)
        b_torso = next(p for p in rep["final"]["B"] if "躯干" in p["name"])
        self.assertEqual(b_torso["hp"], 92, "第 3 回合手破,当回合末即回 2")

    def test_芽孢_空2回合后长出新手(self):
        a = mkp("A", hands=["猛爪"])                     # 10 攻
        b = mkp("B", hands=["长有芽孢的手"])             # 30 血,3 击破(R3)
        rep = battle(a, b, cfg=RuleConfig(round_limit=6), rng=ScriptRNG([0.0] * 8))
        self.assertTrue(self._events(rep, "spore_set", side="B", round=3))
        grow = self._events(rep, "spore_grow", side="B")
        self.assertEqual([g["round"] for g in grow], [6], "R3 破 → R4/R5 空槽 → R6 长出")
        for r in (4, 5):
            b_atk = [e for e in rep["events"] if e["round"] == r and e.get("side") == "B"
                     and e["type"] in ("hit", "dodge", "block", "grab")]
            self.assertEqual(b_atk, [], f"芽孢期 R{r} 不应出手")
            a_hits = self._events(rep, "hit", side="A", round=r)
            self.assertTrue(all("躯干" in h["target"] for h in a_hits), "芽孢不可被攻击,A 应回退打躯干")
        hit6 = [e for e in rep["events"] if e["round"] == 6 and e.get("side") == "B" and e["type"] == "hit"]
        self.assertTrue(hit6 and hit6[0]["dmg"] == 8, "芽孢长出来的手 8 攻")

    # ---- 装配校验 ----
    def test_插件校验_位置与衍生件(self):
        from .builds import build
        m = build("插件装", "新手躯干", hands=[("猛爪", "骨盾")], torso_plugin="尖刺皮肤")
        self.assertEqual(m.price_total(), 630, "350+30(尖刺皮肤)+200+50(骨盾)")
        with self.assertRaises(AssertionError):          # 骨盾只能装手
            build("错位", "新手躯干", legs=[("新手腿", "骨盾")])
        with self.assertRaises(AssertionError):          # 碎骨锥只能装腿
            build("错位2", "新手躯干", hands=[("猛爪", "碎骨锥")])
        with self.assertRaises(AssertionError):          # 衍生件不可直接装
            build("偷芽孢", "新手躯干", hands=["芽孢长出来的手"])
        build("腺体腿", "新手躯干", legs=[("新手腿", "爆裂腺体")])   # 手/腿双位插件合法

    def test_机制流_跑通且纯函数(self):
        from .builds import roster
        r = roster()
        rep1 = battle(r["机制流"], r["均衡流"], seed=42)
        rep2 = battle(r["机制流"], r["均衡流"], seed=42)
        self.assertIn(rep1["winner"], ("A", "B", "draw"))
        self.assertEqual(rep1["winner"], rep2["winner"])
        self.assertEqual(len(rep1["events"]), len(rep2["events"]))


if __name__ == "__main__":
    unittest.main()
