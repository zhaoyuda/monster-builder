// monster-builder 战斗引擎 —— sim/engine.py + sim/parts.py 的忠实 JS 移植
// 规则版本:02-combat.md + Q1-Q8 拍板 + Q12 方案A(指挥点,默认开启)
// 浏览器 <script> 与 node require 双用;统计口径与 Python 模拟器对齐(见 parity_test.js)
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MonsterEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ===== 零件目录(与 sim/parts.py CATALOG 同步)=====
  const CATALOG = {
    // 头:command=指挥点供给(Q12 方案A)
    "新手头":   { kind: "head", atk: 10, hp: 50,  energy: 10, command: 2, price: 200 },
    "猛头":     { kind: "head", atk: 20, hp: 100, energy: 20, command: 2, price: 400 },
    "顶撞头":   { kind: "head", atk: 25, hp: 75,  energy: 20, command: 1, price: 400 },
    "肿头":     { kind: "head", atk: 15, hp: 125, energy: 20, command: 3, price: 400 },
    // 手
    "新手手":   { kind: "hand", atk: 5,  hp: 25,  energy: 5,  price: 100 },
    "猛爪":     { kind: "hand", atk: 10, hp: 50,  energy: 10, price: 200 },
    "强力爪":   { kind: "hand", atk: 13, hp: 35,  energy: 10, price: 200 },
    "小手手":   { kind: "hand", atk: 7,  hp: 65,  energy: 10, price: 200 },
    // 腿
    "新手腿":   { kind: "leg", atk: 3,  hp: 20, energy: 5,  initiative: 1, dodge: 0.05, price: 100 },
    "猛腿":     { kind: "leg", atk: 6,  hp: 50, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "鞭腿":     { kind: "leg", atk: 8,  hp: 40, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "粗腿":     { kind: "leg", atk: 4,  hp: 60, energy: 10, initiative: 2, dodge: 0.07, price: 200 },
    "踢腿":     { kind: "leg", atk: 10, hp: 50, energy: 10, initiative: 0, dodge: 0.0,  price: 200 },
    // 躯干:command=基础指挥点
    "新手躯干":       { kind: "torso", atk: 0, hp: 100, supply: 30, command: 3, price: 500 },
    "稍微长大的躯干": { kind: "torso", atk: 0, hp: 200, supply: 40, command: 4, price: 800 },
    "有些肌肉的躯干": { kind: "torso", atk: 0, hp: 150, supply: 50, command: 3, price: 800 },
    // 插件(E8:不可被攻击)
    "新手尾巴": { kind: "tail", atk: 0, hp: 0, initiative: 1, price: 20 },
    "猛尾":     { kind: "tail", atk: 0, hp: 0, initiative: 2, price: 40 },
    "四肢插槽": { kind: "slot", atk: 0, hp: 0, price: 30 },
    "头部插槽": { kind: "slot", atk: 0, hp: 0, price: 50 },
  };
  const KIND_CN = { head: "头", hand: "手", leg: "腿", torso: "躯干", tail: "尾" };

  function makePart(name, slot) {
    const s = CATALOG[name];
    return {
      name, slot: slot || 0, kind: s.kind, atk: s.atk || 0,
      hp: s.hp, maxHp: s.hp, energy: s.energy || 0, supply: s.supply || 0,
      initiative: s.initiative || 0, dodge: s.dodge || 0,
      command: s.command || 0, price: s.price || 0,
    };
  }
  const alive = (p) => p.hp > 0;
  const label = (p) => p.kind === "torso" ? p.name : `${p.name}(${KIND_CN[p.kind]}${p.slot})`;

  // ===== 怪兽 =====
  function makeMonster(name, spec) {
    // spec: {torso: "新手躯干", heads: [...], hands: [...], legs: [...], tails: [...], slots: [...]}
    const mk = (names) => (names || []).map((n, i) => makePart(n, i + 1));
    return {
      name, torso: makePart(spec.torso),
      heads: mk(spec.heads), hands: mk(spec.hands), legs: mk(spec.legs),
      tails: mk(spec.tails), slots: mk(spec.slots),
    };
  }
  const allParts = (m) => [m.torso, ...m.heads, ...m.hands, ...m.legs];
  const dodgeTotal = (m, cfg) =>
    m.legs.slice(0, cfg.dodgeLegSlots).filter(alive).reduce((s, l) => s + l.dodge, 0);
  const initiativeTotal = (m) =>
    m.legs.filter(alive).reduce((s, l) => s + l.initiative, 0) +
    m.tails.reduce((s, t) => s + t.initiative, 0);
  const commandSupply = (m) =>
    m.torso.command + m.heads.filter(alive).reduce((s, h) => s + h.command, 0);
  const energyUsed = (m) =>
    [...m.heads, ...m.hands, ...m.legs, ...m.tails].reduce((s, p) => s + p.energy, 0);
  const priceTotal = (m) =>
    [...allParts(m), ...m.tails, ...m.slots].reduce((s, p) => s + p.price, 0);

  // 装配校验(Q1 能量 / Q2 槽位)—— 返回违规信息数组,空即合法
  function validate(m) {
    const errs = [];
    const used = energyUsed(m), sup = m.torso.supply;
    if (used > sup) errs.push(`能量超限:需求 ${used} > 供能 ${sup}`);
    const headSlots = 1 + m.slots.filter((s) => s.name === "头部插槽").length;
    const limbSlots = 4 + m.slots.filter((s) => s.name === "四肢插槽").length;
    if (m.heads.length > headSlots) errs.push(`头槽超限:${m.heads.length} > ${headSlots}`);
    const nLimbs = m.hands.length + m.legs.length + m.tails.length;
    if (nLimbs > limbSlots) errs.push(`四肢槽超限(手+腿+尾):${nLimbs} > ${limbSlots}`);
    return errs;
  }

  // ===== RNG(mulberry32,可复现;与 Python 侧只做统计口径对齐)=====
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const DEFAULT_CFG = {
    initiativeMode: "per_round", headVsHeadProb: 0.5,
    blockProb: 0.2, blockMult: 0.8, dodgeLegSlots: 2,
    roundLimit: 100, stunScope: "all", legsAttack: true,
    commandMode: "battle",   // demo 按 Q12 方案A 默认开启
  };

  // ===== battle:纯函数,同 (a, b, seed, cfg) 必得同一战报 =====
  function battle(specA, specB, seed, cfg) {
    cfg = Object.assign({}, DEFAULT_CFG, cfg || {});
    const rand = mulberry32(seed == null ? 0 : seed);
    const choice = (arr) => arr[Math.floor(rand() * arr.length)];
    const a = makeMonster(specA.name, specA), b = makeMonster(specB.name, specB);
    const sides = { A: a, B: b };
    const events = [];
    const stunNext = { A: false, B: false };
    let winner = null, firstKeyLocked = null;

    const log = (round, type, kw) => events.push(Object.assign({ round, type }, kw));
    const enemyKey = (k) => (k === "A" ? "B" : "A");
    const checkEnd = (atkKey) => { if (!alive(sides[enemyKey(atkKey)].torso)) winner = atkKey; };

    function chooseTarget(kind, defender) {
      if (kind === "leg") {
        const pool = defender.legs.filter(alive);
        return pool.length ? choice(pool) : defender.torso;
      }
      if (kind === "hand") {
        const pool = defender.hands.filter(alive);
        return pool.length ? choice(pool) : defender.torso;
      }
      const pool = defender.heads.filter(alive);   // head:50% 打头,无头回退躯干(E4)
      if (rand() < cfg.headVsHeadProb && pool.length) return choice(pool);
      return defender.torso;
    }

    function resolve(round, atkKey, attacker) {
      const defKey = enemyKey(atkKey), defender = sides[defKey];
      const target = chooseTarget(attacker.kind, defender);
      const dv = dodgeTotal(defender, cfg);
      if (dv > 0 && rand() < dv) {
        log(round, "dodge", { side: atkKey, attacker: label(attacker), target: label(target), dodge: dv });
        return;
      }
      const dmg = attacker.atk;
      const blockers = defender.hands.filter(alive);
      if ((target.kind === "head" || target.kind === "torso") && blockers.length && rand() < cfg.blockProb) {
        const blocker = blockers.reduce((m, h) => (h.slot > m.slot ? h : m));
        const bdmg = dmg > 0 ? Math.max(1, Math.floor(dmg * cfg.blockMult)) : 0;
        blocker.hp -= bdmg;
        log(round, "block", { side: atkKey, attacker: label(attacker), target: label(target),
          blocker: label(blocker), dmg, taken: bdmg, blockerHp: Math.max(blocker.hp, 0) });
        if (!alive(blocker)) log(round, "break", { side: defKey, part: label(blocker), kind: "hand" });
        return;
      }
      target.hp -= dmg;
      log(round, "hit", { side: atkKey, attacker: label(attacker), target: label(target),
        dmg, targetHp: Math.max(target.hp, 0) });
      if (!alive(target)) {
        log(round, "break", { side: defKey, part: label(target), kind: target.kind });
        if (target.kind === "head") { stunNext[defKey] = true; log(round, "stun_set", { side: defKey }); }
        if (target.kind === "torso") checkEnd(atkKey);
      }
    }

    let roundNo = 0;
    for (roundNo = 1; roundNo <= cfg.roundLimit; roundNo++) {
      const ia = initiativeTotal(a), ib = initiativeTotal(b);
      let firstKey;
      if (cfg.initiativeMode === "once" && firstKeyLocked) firstKey = firstKeyLocked;
      else {
        const pA = ia + ib > 0 ? ia / (ia + ib) : 0.5;
        firstKey = rand() < pA ? "A" : "B";
        if (cfg.initiativeMode === "once") firstKeyLocked = firstKey;
      }
      const secondKey = enemyKey(firstKey);
      log(roundNo, "round_start", { first: firstKey, initA: ia, initB: ib });

      const skip = { A: stunNext.A, B: stunNext.B };
      for (const k of ["A", "B"]) {
        if (skip[k]) log(roundNo, "stunned", { side: k });
        stunNext[k] = false;
      }

      const cmdPool = { A: commandSupply(a), B: commandSupply(b) };
      if (cfg.commandMode === "battle")
        log(roundNo, "command", { cmdA: cmdPool.A, cmdB: cmdPool.B });

      const phases = cfg.legsAttack ? ["leg", "hand", "head"] : ["hand", "head"];
      for (const kind of phases) {
        const listOf = (m) => ({ head: m.heads, hand: m.hands, leg: m.legs }[kind]);
        const fp = listOf(sides[firstKey]).filter(alive);
        const sp = listOf(sides[secondKey]).filter(alive);
        const seq = [];
        for (let i = 0; i < Math.max(fp.length, sp.length); i++) {
          if (i < fp.length) seq.push([firstKey, fp[i]]);
          if (i < sp.length) seq.push([secondKey, sp[i]]);
        }
        for (const [atkKey, part] of seq) {
          if (winner || skip[atkKey] || !alive(part) || part.atk <= 0) continue;
          if (cfg.commandMode === "battle" && (kind === "leg" || kind === "hand")) {
            if (cmdPool[atkKey] <= 0) {
              log(roundNo, "no_command", { side: atkKey, part: label(part) });
              continue;
            }
            cmdPool[atkKey] -= 1;
          }
          resolve(roundNo, atkKey, part);
        }
        if (winner) break;
      }
      if (winner) break;
    }

    let result = winner;
    if (result === null) {
      const pa = a.torso.hp / a.torso.maxHp, pb = b.torso.hp / b.torso.maxHp;
      result = pa > pb ? "A" : pb > pa ? "B" : "draw";
      log(roundNo, "timeout", { torsoPctA: pa, torsoPctB: pb });
    }
    return {
      winner: result,
      winnerName: result === "A" ? a.name : result === "B" ? b.name : "平局",
      rounds: Math.min(roundNo, cfg.roundLimit), events,
      final: { A: snapshot(a), B: snapshot(b) }, seed, config: cfg,
    };
  }
  const snapshot = (m) => allParts(m).map((p) => ({ name: label(p), hp: Math.max(p.hp, 0), maxHp: p.maxHp }));

  // ===== 预设流派(与 sim/builds.py 同步)=====
  const ARCHETYPES = {
    "均衡流": { torso: "有些肌肉的躯干", heads: ["新手头"], hands: ["猛爪", "强力爪"],
               legs: ["猛腿", "新手腿"], tails: ["猛尾"], slots: ["四肢插槽"] },
    "多头流": { torso: "有些肌肉的躯干", heads: ["猛头", "顶撞头", "新手头"], slots: ["头部插槽", "头部插槽"] },
    "无头流": { torso: "有些肌肉的躯干", hands: ["猛爪", "强力爪", "小手手"], legs: ["猛腿", "粗腿"], slots: ["四肢插槽"] },
    "踢腿流": { torso: "有些肌肉的躯干", legs: ["踢腿", "踢腿", "踢腿", "踢腿", "踢腿"], slots: ["四肢插槽"] },
    "耗材手流": { torso: "有些肌肉的躯干", heads: ["猛头"], hands: ["强力爪", "强力爪", "新手手"], legs: ["新手腿"] },
    "肉盾流": { torso: "稍微长大的躯干", heads: ["肿头"], hands: ["小手手"], legs: ["粗腿"] },
    "带头踢腿流": { torso: "有些肌肉的躯干", heads: ["新手头"], legs: ["踢腿", "踢腿", "踢腿", "踢腿"] },
  };

  return { CATALOG, KIND_CN, makeMonster, makePart, allParts, validate, battle,
           dodgeTotal, initiativeTotal, commandSupply, energyUsed, priceTotal,
           ARCHETYPES, DEFAULT_CFG, label, alive };
});
