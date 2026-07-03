# CLI:单场战报 / 流派锦标赛
#   python3 -m sim.cli duel 多头流 无头流 --seed 42 -v
#   python3 -m sim.cli tournament --games 500 --seed 1
import argparse
import statistics
from collections import Counter

from .builds import roster, ARCHETYPES
from .engine import battle, RuleConfig


def render(report, verbose=False):
    lines = []
    for ev in report["events"]:
        r, t = ev["round"], ev["type"]
        if t == "round_start":
            if verbose:
                lines.append(f"—— 回合 {r}(先攻 {ev['first']} | A:{ev['init_a']} vs B:{ev['init_b']})——")
        elif t == "stunned":
            lines.append(f"R{r} 💫 {ev['side']} 方眩晕,本回合全队不攻击")
        elif t == "dodge":
            lines.append(f"R{r} [{ev['side']}] {ev['attacker']} → {ev['target']}:被闪避(闪避 {ev['dodge']:.0%})")
        elif t == "block":
            lines.append(f"R{r} [{ev['side']}] {ev['attacker']} → {ev['target']}:被格挡!伤害 {ev['dmg']}→{ev['taken']} 转 {ev['blocker']}(余 {ev['blocker_hp']})")
        elif t == "hit":
            lines.append(f"R{r} [{ev['side']}] {ev['attacker']} → {ev['target']}:伤害 {ev['dmg']}(余 {ev['target_hp']})")
        elif t == "break":
            lines.append(f"R{r} 💥 {ev['side']} 方 {ev['part']} 被击破!")
        elif t == "stun_set":
            lines.append(f"R{r} ⚡ {ev['side']} 方头部被击破 → 下回合不行动")
        elif t == "timeout":
            lines.append(f"R{r} ⏱ 达到回合上限,按躯干血量比判定(A {ev['torso_pct_a']:.0%} vs B {ev['torso_pct_b']:.0%})")
    lines.append(f"\n结果:{report['winner_name']} 胜(共 {report['rounds']} 回合,winner={report['winner']})")
    return "\n".join(lines)


def cmd_duel(args):
    r = roster()
    a, b = r[args.a], r[args.b]
    rep = battle(a, b, seed=args.seed, cfg=RuleConfig(initiative_mode=args.initiative))
    if not args.verbose:
        rep_events = [e for e in rep["events"] if e["type"] in ("break", "stun_set", "stunned", "timeout")]
        rep = {**rep, "events": rep_events}
    print(f"⚔️  A={a.name}(能量 {a.energy_used()}/{a.torso.supply},价 {a.price_total()})"
          f" vs B={b.name}(能量 {b.energy_used()}/{b.torso.supply},价 {b.price_total()})\n")
    print(render(rep, verbose=args.verbose))


def cmd_tournament(args):
    r = roster()
    names = list(ARCHETYPES)
    cfg = RuleConfig(initiative_mode=args.initiative)
    print(f"锦标赛:{len(names)} 流派 round-robin(含镜像),每对 {args.games} 局,"
          f"先攻模式={args.initiative}\n")
    # 胜率矩阵
    header = "| vs → | " + " | ".join(names) + " |"
    sep = "|---" * (len(names) + 1) + "|"
    rows, mirror_stats, round_lens = [header, sep], {}, []
    for ia, na in enumerate(names):
        cells = []
        for ib, nb in enumerate(names):
            pair_id = ia * len(names) + ib  # 确定性配对编号(str hash 每进程随机,不可用作种子)
            c = Counter()
            for g in range(args.games):
                rep = battle(r[na], r[nb], seed=args.seed * 1_000_003 + pair_id * 100_000 + g, cfg=cfg)
                c[rep["winner"]] += 1
                round_lens.append(rep["rounds"])
            wr = c["A"] / args.games
            if na == nb:
                mirror_stats[na] = wr
            cells.append(f"{wr:.0%}" + (f"(平{c['draw']})" if c["draw"] else ""))
        rows.append(f"| **{na}** | " + " | ".join(cells) + " |")
    print("\n".join(rows))
    print(f"\n镜像对战 A 侧胜率(理想 50%±5%):")
    for n, wr in mirror_stats.items():
        flag = "✅" if abs(wr - 0.5) <= 0.05 else "⚠️"
        print(f"  {flag} {n}: {wr:.1%}")
    print(f"\n回合数:平均 {statistics.mean(round_lens):.1f},中位 {statistics.median(round_lens)},"
          f"最长 {max(round_lens)}(上限 {cfg.round_limit})")


def main():
    p = argparse.ArgumentParser(description="monster-builder 战斗模拟器")
    sub = p.add_subparsers(required=True)
    d = sub.add_parser("duel", help="单场对决,输出战报")
    d.add_argument("a", choices=ARCHETYPES)
    d.add_argument("b", choices=ARCHETYPES)
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("-v", "--verbose", action="store_true", help="逐次攻击的完整战报")
    d.add_argument("--initiative", choices=["per_round", "once"], default="per_round")
    d.set_defaults(fn=cmd_duel)
    t = sub.add_parser("tournament", help="流派 round-robin 胜率矩阵")
    t.add_argument("--games", type=int, default=500)
    t.add_argument("--seed", type=int, default=1)
    t.add_argument("--initiative", choices=["per_round", "once"], default="per_round")
    t.set_defaults(fn=cmd_tournament)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
