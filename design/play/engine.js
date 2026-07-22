// monster-builder 战斗引擎 —— sim/engine.py + sim/parts.py 的忠实 JS 移植
// 规则版本:02-combat.md + Q1-Q17 拍板(06-decisions.md)+ 机制工程默认(05 页 Q19)
// 浏览器 <script> 与 node require 双用;统计口径与 Python 模拟器对齐(见 parity 脚本)
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MonsterEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ===== 零件目录(与 sim/parts.py CATALOG 同步;数值:Akun 2026-07-15 零件表)=====
  const CATALOG = {
    // 头:command=指挥点供给(Q12 方案A);crit=暴击率(本体)
    "新手头":   { kind: "head", atk: 10, hp: 50,  energy: 10, command: 2, crit: 0,    price: 200 },
    "猛头":     { kind: "head", atk: 20, hp: 100, energy: 20, command: 2, crit: 0.08, price: 400 },
    "顶撞头":   { kind: "head", atk: 25, hp: 75,  energy: 20, command: 2, crit: 0.10, price: 400 },
    "肿头":     { kind: "head", atk: 15, hp: 125, energy: 20, command: 3, crit: 0.06, price: 400 },
    // 喷火头(Q17a + 2026-07-22 补:先攻-1、不可被格挡):火焰伤害,额外目标,挂"灼烧"(2/回合×3,刷新)
    "喷火头":   { kind: "head", atk: 15, hp: 100, energy: 30, command: 2, crit: 0, price: 550,
                  fire: true, dtype: "fire", extraTarget: true, noblock: true, initiative: -1 },
    // ---- 第二批头(Akun 2026-07-22,细则 Q22)----
    "喷毒头":   { kind: "head", atk: 14, hp: 100, energy: 30, command: 2, crit: 0, price: 550,
                  dtype: "poison", aoePos: true, noblock: true, initiative: -1 },
    "喷冰头":   { kind: "head", atk: 15, hp: 100, energy: 30, command: 2, crit: 0, price: 550,
                  dtype: "ice", extraTarget: true, noblock: true, freezeProb: 0.25, initiative: -1 },
    "伸缩头":   { kind: "head", atk: 20, hp: 100, energy: 20, command: 2, crit: 0.08, price: 400, stretch: true },
    "蓄力头":   { kind: "head", atk: 20, hp: 100, energy: 20, command: 2, crit: 0, price: 400, charge: true },
    "尾巴上的头": { kind: "head", atk: 19, hp: 100, energy: 20, command: 1, crit: 0.10, price: 400,
                    tailHead: true, noblock: true },
    // 手
    "新手手":   { kind: "hand", atk: 5,  hp: 25,  energy: 5,  price: 100 },
    "猛爪":     { kind: "hand", atk: 10, hp: 50,  energy: 10, price: 200 },
    "强力爪":   { kind: "hand", atk: 13, hp: 35,  energy: 10, price: 200 },
    "小手手":   { kind: "hand", atk: 7,  hp: 65,  energy: 10, price: 200 },
    // 抓握手:第一次攻击命中时不造成伤害,敌方 5 回合闪避清零(被闪掉不消耗"第一次")
    "抓握手":   { kind: "hand", atk: 10, hp: 50,  energy: 10, grab: true, price: 200 },
    // 长有芽孢的手(Q17b):被击破后原槽留"芽孢"标记(无血/不可被攻击/不可格挡),空 2 回合后长出新手
    "长有芽孢的手":   { kind: "hand", atk: 7, hp: 30, energy: 10, spore: true, price: 250 },
    "芽孢长出来的手": { kind: "hand", atk: 8, hp: 30, energy: 10, derived: true, price: 0 },
    // ---- 第二批手(Akun 2026-07-22,细则 Q22)----
    "刺拳手":   { kind: "hand", atk: 5,  hp: 50, energy: 10, hits: 2, price: 200 },
    "触手":     { kind: "hand", atk: 5,  hp: 65, energy: 10, tentacle: true, price: 210 },
    "蓄力拳":   { kind: "hand", atk: 10, hp: 55, energy: 10, charge: true, price: 200 },
    "残像拳":   { kind: "hand", atk: 8,  hp: 45, energy: 10, afterimage: true, price: 210 },
    // 腿
    "新手腿":   { kind: "leg", atk: 3,  hp: 20, energy: 5,  initiative: 1, dodge: 0.05, price: 100 },
    "猛腿":     { kind: "leg", atk: 6,  hp: 50, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "鞭腿":     { kind: "leg", atk: 8,  hp: 40, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "灵活的腿": { kind: "leg", atk: 4,  hp: 60, energy: 10, initiative: 2, dodge: 0.07, price: 200 },
    "踢腿":     { kind: "leg", atk: 10, hp: 50, energy: 10, initiative: 0, dodge: 0.0,  price: 200 },
    // ---- 第二批腿(Akun 2026-07-22,细则 Q22)----
    "闪避腿":   { kind: "leg", atk: 8,  hp: 45, energy: 10, initiative: 2, dodge: 0.12, price: 200 },
    "高鞭腿":   { kind: "leg", atk: 10, hp: 40, energy: 10, initiative: 2, dodge: 0.05, price: 200, revengeHead: true },
    "连环腿":   { kind: "leg", atk: 3,  hp: 45, energy: 10, initiative: 2, dodge: 0.05, price: 200, combo3: true },
    "黏腿":     { kind: "leg", atk: 8,  hp: 50, energy: 10, initiative: 2, dodge: 0.05, price: 200, sticky: true },
    "震撼腿":   { kind: "leg", atk: 7,  hp: 50, energy: 10, initiative: 2, dodge: 0.05, price: 200, shock: true },
    // 躯干:command=基础指挥点(Akun 2026-07-15 拍板 2/3/3;价格按新公式 1供能=5价)
    "新手躯干":       { kind: "torso", atk: 0, hp: 100, supply: 30, command: 2, price: 350 },
    "稍微长大的躯干": { kind: "torso", atk: 0, hp: 200, supply: 60, command: 3, price: 700 },
    "有些肌肉的躯干": { kind: "torso", atk: 0, hp: 150, supply: 80, command: 3, price: 700 },
    // 第二批躯干(Akun 2026-07-22)。⚠️ 臃肿指挥 4 已探针报警(无头流回 T0),等 Akun 拍改法
    "强能躯干":       { kind: "torso", atk: 0, hp: 145, supply: 90, command: 3, price: 750 },
    "臃肿的躯干":     { kind: "torso", atk: 0, hp: 300, supply: 60, command: 4, price: 850 },
    // 尾巴(独立位不占四肢槽,Q9 限 1;E8:不可被攻击)
    "新手尾巴": { kind: "tail", atk: 0, hp: 0, initiative: 1, price: 20 },
    "猛尾":     { kind: "tail", atk: 0, hp: 0, initiative: 2, price: 40 },
    // 扩槽件
    "四肢插槽": { kind: "slot", atk: 0, hp: 0, price: 30 },
    "头部插槽": { kind: "slot", atk: 0, hp: 0, price: 50 },
    // 装饰件(PVE 起始装;Akun 2026-07-15 血量 0:纯摆设不可当肉墙)
    "装饰手":   { kind: "hand", atk: 0, hp: 0, energy: 0, price: 0 },
    "装饰腿":   { kind: "leg",  atk: 0, hp: 0, energy: 0, price: 0 },
    // PVE 专属敌方部件(不入玩家目录)
    "鹿躯干":     { kind: "torso", atk: 0, hp: 50,  supply: 99, command: 99, price: 0, pve: true },
    "猛犸象头":   { kind: "head",  atk: 2, hp: 75,  hits: 2, price: 0, pve: true },
    "猛犸象躯干": { kind: "torso", atk: 0, hp: 200, supply: 99, command: 99, price: 0, pve: true },
    "剑齿虎头":   { kind: "head",  atk: 5, hp: 100, price: 0, pve: true },
    "剑齿虎躯干": { kind: "torso", atk: 0, hp: 100, supply: 99, command: 99, price: 0, pve: true },
    "剑齿虎爪":   { kind: "hand",  atk: 2, hp: 50,  price: 0, pve: true },
  };

  // ===== 插件目录(Q17e:无血量、随宿主、每部件限 1;躯干"身体"位也限 1)=====
  //   ⚠️ 普通能量核心与耐火皮肤/尖刺皮肤竞争躯干唯一插件位
  const PLUGINS = {
    "头顶角质层": { pos: ["head"], price: 60, absorbs: 2 },
    "头顶尖刺":   { pos: ["head"], price: 20, critBonus: 0.05 },
    "骨盾":       { pos: ["hand"], price: 50, blockMult: 0.80 },
    "胶质瘤":     { pos: ["hand"], price: 40, heal: 2, rounds: 5 },
    "肾上腺素":   { pos: ["leg"],  price: 40, heal: 5 },
    "爆裂腺体":   { pos: ["hand", "leg"], price: 60, dmg: 40 },
    "耐火皮肤":   { pos: ["torso"], price: 50 },
    "撕裂爪":     { pos: ["hand"], price: 50, atkDelta: -2, tearRounds: 5 },
    "碎骨锥":     { pos: ["leg"],  price: 40, stunProb: 0.5 },
    "尖刺皮肤":   { pos: ["torso"], price: 30, tearRounds: 2 },
    "普通能量核心": { pos: ["torso"], price: 100, supply: 20 },
    // ---- 第二批插件(Akun 2026-07-22,细则 Q22)----
    "耐毒皮肤":   { pos: ["torso"], price: 50 },
    "耐冰皮肤":   { pos: ["torso"], price: 50 },
    "火蜥蜴尾巴": { pos: ["tail"], price: 40, burnBonus: 2 },
    "毒蛇尾巴":   { pos: ["tail"], price: 40, poisonBonus: 1 },
    "冰虫尾巴":   { pos: ["tail"], price: 40, freezeBonus: 0.15, initiative: 1 },
    "先守后攻":   { pos: ["leg"],  price: 25 },
    "头槌":       { pos: ["head"], price: 50, atkDelta: 4 },
    "认真一拳":   { pos: ["hand"], price: 30, critMultBonus: 0.5 },
  };
  const KIND_CN = { head: "头", hand: "手", leg: "腿", torso: "躯干", tail: "尾" };
  // 机制常量(与 sim/engine.py 同步)
  const BURN_DMG = 2, TEAR_DMG = 2, BURN_ROUNDS = 3, GRAB_ROUNDS = 5, SPORE_ROUNDS = 2;
  const POISON_DMG = 3, POISON_ROUNDS = 2, POISON_ATKDOWN = 1;
  const ENTANGLE_ROUNDS = 5, ENTANGLE_DMG = 5;
  const SHOCK_DODGE = 0.05, SHOCK_ROUNDS = 2;
  const RESIST_SKIN = { fire: "耐火皮肤", poison: "耐毒皮肤", ice: "耐冰皮肤" };
  const RESIST_TAIL = { fire: "火蜥蜴尾巴", poison: "毒蛇尾巴", ice: "冰虫尾巴" };

  function makePart(name, slot, plugin) {
    const s = CATALOG[name];
    if (!s) {
      if (PLUGINS[name]) throw new Error(`「${name}」是插件,不能当独立零件——挂到宿主部件上`);
      throw new Error(`未知零件「${name}」——检查拼写或 CATALOG 是否与零件表同步`);
    }
    const p = {
      name, slot: slot || 0, kind: s.kind, atk: s.atk || 0,
      hp: s.hp, maxHp: s.hp, energy: s.energy || 0, supply: s.supply || 0,
      initiative: s.initiative || 0, dodge: s.dodge || 0,
      command: s.command || 0, crit: s.crit || 0, hits: s.hits || 1,
      fire: !!s.fire, grab: !!s.grab, spore: !!s.spore, derived: !!s.derived,
      dtype: s.dtype || "phys", extraTarget: !!s.extraTarget, aoePos: !!s.aoePos,
      noblock: !!s.noblock, freezeProb: s.freezeProb || 0, stretch: !!s.stretch,
      charge: !!s.charge, afterimage: !!s.afterimage, tentacle: !!s.tentacle,
      tailHead: !!s.tailHead, revengeHead: !!s.revengeHead, combo3: !!s.combo3,
      sticky: !!s.sticky, shock: !!s.shock,
      plugin: "", pve: !!s.pve, price: s.price || 0,
      // 运行时状态
      burn: null, tear: null, poison: null, stunPartNext: false, stunnedPart: false,
      grabUsed: false, keratin: 0, sporeWait: -1,
      lastTarget: null, revengePending: false, lockTarget: null,
      entangledLeft: 0, entanglePartner: null,
    };
    if (plugin) {
      const ps = PLUGINS[plugin];
      if (!ps) throw new Error(`未知插件「${plugin}」——检查拼写或 PLUGINS 是否与零件表同步`);
      p.plugin = plugin;
      p.atk = Math.max(0, p.atk + (ps.atkDelta || 0));   // 撕裂爪 -2 攻
      p.crit = p.crit + (ps.critBonus || 0);             // 头顶尖刺 +5%
    }
    return p;
  }
  const alive = (p) => p.hp > 0;
  const label = (p) => p.kind === "torso" ? p.name : `${p.name}(${KIND_CN[p.kind]}${p.slot})`;

  // ===== 怪兽 =====
  // spec: {torso, torsoPlugin?, heads: [...], hands: [...], legs: [...], tails: [...], slots: [...]}
  //   部件项可为 "猛爪" 或 {name:"猛爪", plugin:"骨盾"}
  function makeMonster(name, spec) {
    const mk = (names) => (names || []).map((n, i) =>
      typeof n === "string" ? makePart(n, i + 1) : makePart(n.name, i + 1, n.plugin || ""));
    return {
      name, torso: makePart(spec.torso, 0, spec.torsoPlugin || ""),
      heads: mk(spec.heads), hands: mk(spec.hands), legs: mk(spec.legs),
      tails: mk(spec.tails), slots: mk(spec.slots),
    };
  }
  const allParts = (m) => [m.torso, ...m.heads, ...m.hands, ...m.legs];
  const dodgeTotal = (m, cfg) =>
    m.legs.slice(0, cfg.dodgeLegSlots).filter(alive).reduce((s, l) => s + l.dodge, 0);
  const initiativeTotal = (m) =>
    m.legs.filter(alive).reduce((s, l) => s + l.initiative, 0) +
    m.tails.reduce((s, t) => s + t.initiative, 0) +
    m.heads.filter(alive).reduce((s, h) => s + h.initiative, 0) +   // 喷头 -1(Q22b)
    m.tails.reduce((s, t) => s + (t.plugin ? (PLUGINS[t.plugin].initiative || 0) : 0), 0);
  const commandSupply = (m) =>
    m.torso.command + m.heads.filter(alive).reduce((s, h) => s + h.command, 0);
  const energyUsed = (m) =>
    [...m.heads, ...m.hands, ...m.legs, ...m.tails].reduce((s, p) => s + p.energy, 0);
  const supplyTotal = (m) =>
    m.torso.supply + m.slots.reduce((s, p) => s + (p.supply || 0), 0) +
    allParts(m).reduce((s, p) => s + (p.plugin ? (PLUGINS[p.plugin].supply || 0) : 0), 0);
  const priceTotal = (m) =>
    [...allParts(m), ...m.tails, ...m.slots].reduce((s, p) => s + p.price, 0) +
    allParts(m).reduce((s, p) => s + (p.plugin ? PLUGINS[p.plugin].price : 0), 0);

  // 装配校验(Q1 能量 / Q2 槽位 / 槽位类型 / PVE 边界 / Q17e 插件位置)—— 返回违规信息数组,空即合法
  function validate(m) {
    const errs = [];
    const groups = [[[m.torso], "torso"], [m.heads, "head"], [m.hands, "hand"],
                    [m.legs, "leg"], [m.tails, "tail"], [m.slots, "slot"]];
    for (const [list, want] of groups)
      for (const p of list) {
        if (p.kind !== want) errs.push(`「${p.name}」(${KIND_CN[p.kind] || p.kind})装错槽位`);
        if (p.pve) errs.push(`「${p.name}」是 PVE 专属敌方部件,玩家不可用`);
        if (p.derived) errs.push(`「${p.name}」是战斗中长出的衍生部件,不可直接装配`);
        if (p.plugin) {
          const pos = PLUGINS[p.plugin].pos;
          if (!pos.includes(p.kind))
            errs.push(`插件「${p.plugin}」只能装在${pos.map(k => KIND_CN[k]).join("/")},不能装在「${p.name}」`);
        }
      }
    const used = energyUsed(m), sup = supplyTotal(m);
    if (used > sup) errs.push(`能量超限:需求 ${used} > 供能 ${sup}`);
    const headSlots = 1 + m.slots.filter((s) => s.name === "头部插槽").length;
    const limbSlots = 4 + m.slots.filter((s) => s.name === "四肢插槽").length;
    const normalHeads = m.heads.filter((h) => !h.tailHead).length;
    if (normalHeads > headSlots) errs.push(`头槽超限:${normalHeads} > ${headSlots}`);
    // 尾巴上的头(Q22i):骑在尾巴上,不占头槽;需已装尾巴,与属性尾巴插件互斥,限 1
    const tailHeads = m.heads.filter((h) => h.tailHead);
    if (tailHeads.length > 1) errs.push(`「尾巴上的头」限 1 个`);
    if (tailHeads.length) {
      if (!m.tails.length) errs.push(`「尾巴上的头」需要先装备一条尾巴`);
      else if (m.tails.some((t) => ["火蜥蜴尾巴", "毒蛇尾巴", "冰虫尾巴"].includes(t.plugin)))
        errs.push(`装了属性尾巴插件的尾巴不能再装「尾巴上的头」`);
    }
    const nLimbs = m.hands.length + m.legs.length;   // 尾巴独立位(Akun 2026-07-15)
    if (nLimbs > limbSlots) errs.push(`四肢槽超限(手+腿):${nLimbs} > ${limbSlots}`);
    if (m.tails.length > 1) errs.push(`尾巴独立位暂限 1 条(上限待定)`);
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
    commandMode: "battle",   // Q12 方案A 已拍板(2026-07-07)
    critMult: 2.0,           // 暴击倍率(待 Akun 确认,暂 2 倍;1.0=关闭)
    blockOverflow: false,
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
    const zeroUntil = { A: 0, B: 0 };    // 抓握手:该方闪避清零至此回合(含)
    const regen = { A: [], B: [] };      // 胶质瘤:激活中的回复计数器
    const shockLeft = { A: 0, B: 0 };    // 震撼腿:该方全队闪避 -5% 剩余回合(Q22n)
    let winner = null, firstKeyLocked = null;

    for (const m of [a, b])
      for (const p of allParts(m))
        if (p.plugin === "头顶角质层") p.keratin = PLUGINS["头顶角质层"].absorbs;

    const log = (round, type, kw) => events.push(Object.assign({ round, type }, kw));
    const enemyKey = (k) => (k === "A" ? "B" : "A");

    function updateWinner() {
      const aDead = !alive(a.torso), bDead = !alive(b.torso);
      if (aDead && bDead) winner = "draw";           // E7
      else if (aDead) winner = "B";
      else if (bDead) winner = "A";
    }

    function healSide(key, amount, exclude) {
      let healed = 0;
      const parts = [];
      for (const p of allParts(sides[key])) {
        if (p === exclude || !alive(p)) continue;
        const gain = Math.min(amount, p.maxHp - p.hp);
        p.hp += gain; healed += gain;
        if (gain > 0) parts.push({ part: label(p), hp: p.hp });
      }
      return [healed, parts];
    }

    function handleBreak(round, victim, vicKey, killer, killerKey) {
      log(round, "break", { side: vicKey, part: label(victim), kind: victim.kind });
      victim.burn = victim.tear = victim.poison = null;
      victim.stunnedPart = victim.stunPartNext = false;
      if (victim.entangledLeft > 0) {   // 被缠部件死亡 → 另一方立即解脱(Q22j)
        const partner = victim.entanglePartner;
        victim.entangledLeft = 0; victim.entanglePartner = null;
        if (partner != null && alive(partner)) {
          partner.entangledLeft = 0; partner.entanglePartner = null;
          log(round, "entangle_end", { side: enemyKey(vicKey), part: label(partner), freed: true });
        }
      }
      if (victim.kind === "head") { stunNext[vicKey] = true; log(round, "stun_set", { side: vicKey }); }
      if (victim.kind === "torso") updateWinner();
      if (victim.spore) {   // Q17b
        victim.sporeWait = SPORE_ROUNDS;
        log(round, "spore_set", { side: vicKey, part: label(victim) });
      }
      const plug = victim.plugin;
      if (plug === "胶质瘤") {
        regen[vicKey].push(PLUGINS["胶质瘤"].rounds);
        log(round, "regen_start", { side: vicKey, part: label(victim),
          heal: PLUGINS["胶质瘤"].heal, rounds: PLUGINS["胶质瘤"].rounds });
      } else if (plug === "肾上腺素") {
        const [healed, hparts] = healSide(vicKey, PLUGINS["肾上腺素"].heal, victim);
        log(round, "adrenaline", { side: vicKey, part: label(victim), healed, parts: hparts });
      } else if (plug === "爆裂腺体" && killer != null && alive(killer)) {
        const gdmg = PLUGINS["爆裂腺体"].dmg;
        killer.hp -= gdmg;
        log(round, "gland", { side: vicKey, part: label(victim),
          target: label(killer), dmg: gdmg, targetHp: Math.max(killer.hp, 0) });
        if (!alive(killer)) handleBreak(round, killer, killerKey, null, vicKey);
      }
    }

    // 耐×皮肤护全身(Q19d/Q22q):躯干挂对应皮肤 → 全队该类伤害减半+免疫对应状态
    function resistSkin(key, dtype) {
      const t = sides[key].torso;
      return alive(t) && t.plugin === RESIST_SKIN[dtype];
    }
    function resistMult(key, dtype) {   // 皮肤 ×0.5 与属性尾巴 ×0.8 叠乘
      if (dtype === "phys") return 1;
      let m = resistSkin(key, dtype) ? 0.5 : 1;
      if (sides[key].tails.some((t) => t.plugin === RESIST_TAIL[dtype])) m *= 0.8;
      return m;
    }
    function tailBonus(key, field) {
      return sides[key].tails.reduce((s, t) => s + (t.plugin ? (PLUGINS[t.plugin][field] || 0) : 0), 0);
    }
    function singleSlotClear(part, keep) {
      if (cfg.statusSlots === "single")
        for (const s of ["burn", "tear", "poison"]) if (s !== keep) part[s] = null;
    }
    const effAtk = (p) => Math.max(0, p.atk - (p.poison ? p.poison.atkdown : 0));

    function afterDamage(round, attacker, atkKey, victim, defKey, dmg) {
      if (dmg <= 0) return;
      if (attacker.dtype === "fire" && alive(victim) && !resistSkin(defKey, "fire")) {
        victim.burn = { left: BURN_ROUNDS, dmg: BURN_DMG + tailBonus(atkKey, "burnBonus"),
          src: attacker, srcKey: atkKey };
        singleSlotClear(victim, "burn");
        log(round, "status", { side: defKey, part: label(victim), status: "burn",
          rounds: BURN_ROUNDS, by: label(attacker) });
      }
      if (attacker.dtype === "poison" && alive(victim) && !resistSkin(defKey, "poison")) {
        const pb = tailBonus(atkKey, "poisonBonus");
        victim.poison = { left: POISON_ROUNDS, dmg: POISON_DMG + pb,
          atkdown: POISON_ATKDOWN + pb, src: attacker, srcKey: atkKey };
        singleSlotClear(victim, "poison");
        log(round, "status", { side: defKey, part: label(victim), status: "poison",
          rounds: POISON_ROUNDS, by: label(attacker) });
      }
      if (attacker.freezeProb > 0 && alive(victim) && victim.kind !== "torso"
          && !resistSkin(defKey, "ice")) {
        if (rand() < attacker.freezeProb + tailBonus(atkKey, "freezeBonus")) {
          victim.stunPartNext = true;   // 冻结=部件级 1 回合不行动(同碎骨锥,Q22e)
          log(round, "status", { side: defKey, part: label(victim), status: "freeze",
            rounds: 1, by: label(attacker) });
        }
      }
      if (attacker.plugin === "撕裂爪" && alive(victim)) {
        victim.tear = { left: PLUGINS["撕裂爪"].tearRounds, src: attacker, srcKey: atkKey };
        singleSlotClear(victim, "tear");
        log(round, "status", { side: defKey, part: label(victim), status: "tear",
          rounds: PLUGINS["撕裂爪"].tearRounds, by: label(attacker) });
      }
      if (attacker.plugin === "碎骨锥" && alive(victim) && victim.kind !== "torso") {
        if (rand() < PLUGINS["碎骨锥"].stunProb) {
          victim.stunPartNext = true;
          log(round, "part_stun_set", { side: defKey, part: label(victim), by: label(attacker) });
        }
      }
      if (victim.kind === "torso" && victim.plugin === "尖刺皮肤" && alive(attacker)) {
        attacker.tear = { left: PLUGINS["尖刺皮肤"].tearRounds, src: victim, srcKey: defKey };
        singleSlotClear(attacker, "tear");
        log(round, "status", { side: atkKey, part: label(attacker), status: "tear",
          rounds: PLUGINS["尖刺皮肤"].tearRounds, by: label(victim) });
      }
      if (victim.revengeHead && alive(victim)) victim.revengePending = true;   // 高鞭腿(Q22k)
      if (attacker.shock) {   // 震撼腿(Q22n)
        shockLeft[defKey] = SHOCK_ROUNDS;
        log(round, "status", { side: defKey, part: label(victim), status: "shock",
          rounds: SHOCK_ROUNDS, by: label(attacker) });
      }
    }

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

    function strike(round, atkKey, attacker, target, extra, counter) {
      const defKey = enemyKey(atkKey), defender = sides[defKey];
      // 1) 闪避(全身共享;被抓握则清零;震撼腿 debuff -5%)
      let dv = round <= zeroUntil[defKey] ? 0 : dodgeTotal(defender, cfg);
      if (shockLeft[defKey] > 0) dv = Math.max(0, dv - SHOCK_DODGE);
      if (dv > 0 && rand() < dv) {
        log(round, "dodge", { side: atkKey, attacker: label(attacker),
          target: label(target), dodge: dv, extra: !!extra });
        // 先守后攻(Q22o):指向该腿的攻击被闪掉 → 该腿反击攻击者(反击不再触发反击)
        if (!counter && target.kind === "leg" && target.plugin === "先守后攻"
            && alive(target) && alive(attacker) && !winner)
          strike(round, defKey, target, attacker, false, true);
        return "dodge";
      }
      // 1.2) 抓握手:第一次命中不造成伤害,敌方 5 回合闪避清零(被闪掉不消耗)
      if (attacker.grab && !attacker.grabUsed) {
        attacker.grabUsed = true;
        zeroUntil[defKey] = round + GRAB_ROUNDS;
        log(round, "grab", { side: atkKey, attacker: label(attacker),
          target: label(target), rounds: GRAB_ROUNDS });
        return "grab";
      }
      let dmg = effAtk(attacker);   // 中毒降攻实时生效(Q22d)
      // 1.5) 暴击(角质层压制;蓄力偶数回合必暴/残像拳同目标必暴无视压制,Q22g/h)
      const effCrit = attacker.keratin > 0 ? 0 : attacker.crit;
      let crit = false;
      if (cfg.critMult > 1) {
        if ((attacker.charge && round % 2 === 0)
            || (attacker.afterimage && attacker.lastTarget === target)) crit = true;
        else if (effCrit > 0 && rand() < effCrit) crit = true;
      }
      if (crit) {
        let mult = cfg.critMult;
        if (attacker.plugin === "认真一拳") mult += PLUGINS["认真一拳"].critMultBonus;
        dmg = Math.floor(dmg * mult);
      }
      // 1.6) 伸缩头(Q22f):奇数回合造成 ×1.25,偶数 ×0.75
      if (attacker.stretch && dmg > 0)
        dmg = Math.max(1, Math.floor(dmg * (round % 2 === 1 ? 1.25 : 0.75)));
      // 1.8) 头顶角质层:替宿主头整次吸收,2 次后失效
      if (target.kind === "head" && target.keratin > 0) {
        target.keratin -= 1;
        log(round, "absorb", { side: atkKey, attacker: label(attacker),
          target: label(target), left: target.keratin });
        return "absorb";
      }
      // 2) 格挡(E5 末位存活手;骨盾再×80%;喷头/尾巴头不可被格挡;被缠的手不能格挡)
      const blockers = defender.hands.filter((h) => alive(h) && h.entangledLeft <= 0);
      if (!attacker.noblock && (target.kind === "head" || target.kind === "torso")
          && blockers.length && rand() < cfg.blockProb) {
        const blocker = blockers.reduce((m, h) => (h.slot > m.slot ? h : m));
        let bdmg = dmg > 0 ? Math.max(1, Math.floor(dmg * cfg.blockMult)) : 0;
        const bone = blocker.plugin === "骨盾";
        if (bone && bdmg > 0) bdmg = Math.max(1, Math.floor(bdmg * PLUGINS["骨盾"].blockMult));
        let overflow = 0;
        if (cfg.blockOverflow && bdmg > blocker.hp) { overflow = bdmg - blocker.hp; bdmg = blocker.hp; }
        blocker.hp -= bdmg;
        log(round, "block", { side: atkKey, attacker: label(attacker), target: label(target),
          blocker: label(blocker), dmg, taken: bdmg, blockerHp: Math.max(blocker.hp, 0),
          crit, overflow, bone });
        afterDamage(round, attacker, atkKey, blocker, defKey, bdmg);
        if (!alive(blocker)) handleBreak(round, blocker, defKey, attacker, atkKey);
        if (overflow > 0) {
          target.hp -= overflow;
          log(round, "hit", { side: atkKey, attacker: label(attacker), target: label(target),
            dmg: overflow, targetHp: Math.max(target.hp, 0), crit: false, overflow: true });
          afterDamage(round, attacker, atkKey, target, defKey, overflow);
          if (!alive(target)) handleBreak(round, target, defKey, attacker, atkKey);
        }
        return "block";
      }
      // 3) 正常结算(E6;属性伤害全身减免:耐×皮肤 ×0.5、属性尾巴 ×0.8 叠乘)
      const rm = resistMult(defKey, attacker.dtype);
      const resisted = rm < 1 && dmg > 0;
      if (resisted) dmg = Math.max(1, Math.floor(dmg * rm));
      // 伸缩头挨打(Q22f)
      if (target.stretch && dmg > 0)
        dmg = Math.max(1, Math.floor(dmg * (round % 2 === 1 ? 1.25 : 0.75)));
      target.hp -= dmg;
      log(round, "hit", { side: atkKey, attacker: label(attacker), target: label(target),
        dmg, targetHp: Math.max(target.hp, 0), crit, extra: !!extra,
        fireproof: resisted && attacker.dtype === "fire",
        resist: resisted ? attacker.dtype : "" });
      afterDamage(round, attacker, atkKey, target, defKey, dmg);
      if (!alive(target)) handleBreak(round, target, defKey, attacker, atkKey);
      return "hit";
    }

    function resolve(round, atkKey, attacker) {
      const defender = sides[enemyKey(atkKey)];
      // 喷毒头(Q22c):攻击除躯干外随机 1 个部位的所有部件;都没有 → 打躯干
      if (attacker.aoePos) {
        const kinds = ["head", "hand", "leg"].filter((k) =>
          ({ head: defender.heads, hand: defender.hands, leg: defender.legs }[k]).some(alive));
        if (kinds.length) {
          const kind = choice(kinds);
          const targets = ({ head: defender.heads, hand: defender.hands, leg: defender.legs }[kind]).filter(alive);
          for (const t of targets) {
            if (winner || !alive(attacker)) break;
            strike(round, atkKey, attacker, t, false);
          }
        } else strike(round, atkKey, attacker, defender.torso, false);
        return;
      }
      let target;
      if (attacker.revengePending) {   // 高鞭腿(Q22k):被打后改打头,打完清标记
        attacker.revengePending = false;
        const heads = defender.heads.filter(alive);
        target = heads.length ? choice(heads) : chooseTarget(attacker.kind, defender);
      } else if (attacker.sticky && attacker.lockTarget != null && alive(attacker.lockTarget)) {
        target = attacker.lockTarget;   // 黏腿(Q22m)
      } else {
        target = chooseTarget(attacker.kind, defender);
      }
      const outcome = strike(round, atkKey, attacker, target, false);
      if (attacker.sticky) attacker.lockTarget = outcome === "dodge" ? null : target;
      if (attacker.afterimage) attacker.lastTarget = target;   // 残像拳(Q22h)
      // 喷火头/喷冰头:额外随机攻击 1 个目标(尽量避开主目标),独立结算
      if (attacker.extraTarget && !winner && alive(attacker)) {
        const pool = [defender.torso, ...defender.heads, ...defender.hands, ...defender.legs]
          .filter((p) => alive(p) && p !== target);
        if (pool.length) strike(round, atkKey, attacker, choice(pool), true);
      }
    }

    function comboResolve(round, atkKey, part) {
      // 连环腿(Q22l):同目标 3 段(各判闪避/格挡),全未被闪且目标存活 → 补第 4 段
      const defender = sides[enemyKey(atkKey)];
      const target = chooseTarget(part.kind, defender);
      let dodged = false, landed = 0;
      for (let i = 0; i < 3; i++) {
        if (winner || !alive(part) || !alive(target)) break;
        if (strike(round, atkKey, part, target, false) === "dodge") dodged = true;
        landed += 1;
      }
      if (landed === 3 && !dodged && !winner && alive(part) && alive(target))
        strike(round, atkKey, part, target, false);
    }

    function tickDots(round) {
      for (const k of ["A", "B"]) {
        for (const p of allParts(sides[k])) {
          for (const [statusName, baseDmg] of [["burn", BURN_DMG], ["tear", TEAR_DMG],
                                               ["poison", POISON_DMG]]) {
            const st = p[statusName];
            if (!st || !alive(p)) continue;
            const dmgVal = st.dmg != null ? st.dmg : baseDmg;
            p.hp -= dmgVal;
            log(round, "dot_tick", { side: k, part: label(p), status: statusName,
              dmg: dmgVal, partHp: Math.max(p.hp, 0) });
            st.left -= 1;
            if (st.left <= 0) p[statusName] = null;
            if (!alive(p)) {
              const src = st.src, srcKey = st.srcKey;
              handleBreak(round, p, k, src != null && alive(src) ? src : null, srcKey);
            }
          }
        }
      }
      updateWinner();
    }

    function tickEntangle(round) {
      // 缠绕结算(Q22j):双方被缠部件各扣 5(不可闪避/格挡,可致死),一方死另一方解脱
      for (const k of ["A", "B"]) {
        for (const p of [...sides[k].heads, ...sides[k].hands, ...sides[k].legs]) {
          if (p.entangledLeft <= 0 || !alive(p)) continue;
          p.hp -= ENTANGLE_DMG;
          p.entangledLeft -= 1;
          log(round, "entangle_tick", { side: k, part: label(p),
            dmg: ENTANGLE_DMG, partHp: Math.max(p.hp, 0), left: p.entangledLeft });
          const partner = p.entanglePartner;
          if (!alive(p)) {
            p.entangledLeft = 1;   // 让 handleBreak 走"死亡解缠"分支
            handleBreak(round, p, k, partner != null && alive(partner) ? partner : null, enemyKey(k));
          } else if (p.entangledLeft <= 0) {
            log(round, "entangle_end", { side: k, part: label(p), freed: false });
            p.entanglePartner = null;
          }
        }
      }
      updateWinner();
    }

    function tickRegen(round) {
      for (const k of ["A", "B"]) {
        if (!regen[k].length) continue;
        const amount = PLUGINS["胶质瘤"].heal * regen[k].length;
        const [healed, hparts] = healSide(k, amount, null);
        if (healed > 0) log(round, "regen", { side: k, heal: amount, healed, parts: hparts });
        regen[k] = regen[k].map((r) => r - 1).filter((r) => r > 0);
      }
    }

    // 触手战吼(Q22j):开战时(回合 0)每只触手随机缠绕一个敌方非躯干存活部件,不可闪避
    for (const key of ["A", "B"]) {
      for (const tent of sides[key].hands) {
        if (!tent.tentacle || !alive(tent)) continue;
        const ek = enemyKey(key);
        const em = sides[ek];
        let pool = [...em.heads, ...em.hands, ...em.legs].filter((p) => alive(p) && p.entangledLeft <= 0);
        if (!pool.length) pool = [...em.heads, ...em.hands, ...em.legs].filter(alive);
        if (!pool.length) continue;
        const victim = choice(pool);
        tent.entangledLeft = victim.entangledLeft = ENTANGLE_ROUNDS;
        tent.entanglePartner = victim; victim.entanglePartner = tent;
        log(0, "entangle", { side: key, part: label(tent), target: label(victim), rounds: ENTANGLE_ROUNDS });
      }
    }

    let roundNo = 0;
    for (roundNo = 1; roundNo <= cfg.roundLimit; roundNo++) {
      const ia = Math.max(0, initiativeTotal(a)), ib = Math.max(0, initiativeTotal(b));
      let firstKey;
      if (cfg.initiativeMode === "once" && firstKeyLocked) firstKey = firstKeyLocked;
      else {
        const pA = ia + ib > 0 ? ia / (ia + ib) : 0.5;
        firstKey = rand() < pA ? "A" : "B";
        if (cfg.initiativeMode === "once") firstKeyLocked = firstKey;
      }
      const secondKey = enemyKey(firstKey);
      log(roundNo, "round_start", { first: firstKey, initA: ia, initB: ib });

      // 芽孢重生(Q17b):R 破 → R+1/R+2 空槽 → R+3 长出满血登场
      for (const k of ["A", "B"]) {
        for (const p of sides[k].hands) {
          if (p.sporeWait < 0) continue;
          if (p.sporeWait === 0) {
            const spec = CATALOG["芽孢长出来的手"];
            p.name = "芽孢长出来的手";
            p.atk = spec.atk; p.hp = p.maxHp = spec.hp; p.energy = spec.energy || 0;
            p.spore = false; p.derived = true; p.plugin = "";   // 插件随原宿主消失(Q17e)
            p.crit = 0; p.grab = false; p.fire = false; p.grabUsed = false;
            p.dtype = "phys"; p.extraTarget = p.aoePos = p.noblock = false;
            p.freezeProb = 0; p.stretch = p.charge = p.afterimage = p.tentacle = false;
            p.hits = 1;
            p.sporeWait = -1;
            log(roundNo, "spore_grow", { side: k, part: label(p), hp: p.hp });
          } else p.sporeWait -= 1;
        }
      }

      const skip = { A: stunNext.A, B: stunNext.B };
      for (const k of ["A", "B"]) {
        if (skip[k]) log(roundNo, "stunned", { side: k });
        stunNext[k] = false;
      }

      // 部件级眩晕消费(碎骨锥,Q17d):与整队眩晕叠加只算眩晕
      for (const k of ["A", "B"]) {
        for (const p of [...sides[k].heads, ...sides[k].hands, ...sides[k].legs]) {
          p.stunnedPart = p.stunPartNext;
          p.stunPartNext = false;
          if (p.stunnedPart && alive(p) && !skip[k])
            log(roundNo, "part_stunned", { side: k, part: label(p) });
        }
      }

      const cmdPool = { A: commandSupply(a), B: commandSupply(b) };
      if (cfg.commandMode === "battle")
        log(roundNo, "command", { cmdA: cmdPool.A, cmdB: cmdPool.B });

      const phases = cfg.legsAttack ? ["leg", "hand", "head"] : ["hand", "head"];
      for (const kind of phases) {
        const listOf = (m) => ({ head: m.heads, hand: m.hands, leg: m.legs }[kind]);
        const fp = listOf(sides[firstKey]).filter(alive);
        const sp = listOf(sides[secondKey]).filter(alive);
        const weave = (f, s) => {
          const out = [];
          for (let i = 0; i < Math.max(f.length, s.length); i++) {
            if (i < f.length) out.push([firstKey, f[i]]);
            if (i < s.length) out.push([secondKey, s[i]]);
          }
          return out;
        };
        // 尾巴上的头(Q22i):头阶段最后行动——双方普通头打完再轮双方尾巴头
        const seq = kind === "head"
          ? [...weave(fp.filter((p) => !p.tailHead), sp.filter((p) => !p.tailHead)),
             ...weave(fp.filter((p) => p.tailHead), sp.filter((p) => p.tailHead))]
          : weave(fp, sp);
        for (const [atkKey, part] of seq) {
          if (winner || skip[atkKey] || !alive(part) || part.stunnedPart
              || part.entangledLeft > 0 || (part.atk <= 0 && !part.grab)) continue;
          if (part.charge && roundNo % 2 === 1) {   // 蓄力件:奇数回合蓄力,不耗指挥(Q22g)
            log(roundNo, "charging", { side: atkKey, part: label(part) });
            continue;
          }
          if (cfg.commandMode === "battle" && (kind === "leg" || kind === "hand")) {
            if (cmdPool[atkKey] <= 0) {
              log(roundNo, "no_command", { side: atkKey, part: label(part) });
              continue;
            }
            cmdPool[atkKey] -= 1;
          }
          if (part.combo3) { comboResolve(roundNo, atkKey, part); continue; }   // 连环腿(Q22l)
          // 多段攻击(猛犸象头"双击"/刺拳手):每段独立结算,整体只耗 1 指挥点
          for (let h = 0; h < part.hits; h++) {
            if (winner || !alive(part)) break;
            resolve(roundNo, atkKey, part);
          }
        }
        if (winner) break;
      }
      // 回合末:缠绕 → DoT 结算 → 胶质瘤回复;震撼腿 debuff 递减
      if (!winner) tickEntangle(roundNo);
      if (!winner) tickDots(roundNo);
      if (!winner) tickRegen(roundNo);
      for (const k of ["A", "B"]) if (shockLeft[k] > 0) shockLeft[k] -= 1;
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
  const snapshot = (m) => allParts(m).map((p) =>
    ({ name: label(p), hp: Math.max(p.hp, 0), maxHp: p.maxHp, plugin: p.plugin }));

  // ===== 预设流派(与 sim/builds.py 同步)=====
  const ARCHETYPES = {
    "均衡流": { torso: "有些肌肉的躯干", heads: ["新手头"], hands: ["猛爪", "强力爪"],
               legs: ["猛腿", "新手腿"], tails: ["猛尾"] },
    "多头流": { torso: "有些肌肉的躯干", heads: ["猛头", "顶撞头", "新手头"], slots: ["头部插槽", "头部插槽"] },
    "无头流": { torso: "有些肌肉的躯干", hands: ["猛爪", "强力爪", "小手手"], legs: ["猛腿", "灵活的腿"], slots: ["四肢插槽"] },
    "踢腿流": { torso: "有些肌肉的躯干", legs: ["踢腿", "踢腿", "踢腿", "踢腿", "踢腿"], slots: ["四肢插槽"] },
    "耗材手流": { torso: "有些肌肉的躯干", heads: ["猛头"], hands: ["强力爪", "强力爪", "新手手"], legs: ["新手腿"] },
    "肉盾流": { torso: "稍微长大的躯干", heads: ["肿头"], hands: ["小手手"], legs: ["灵活的腿"] },
    "带头踢腿流": { torso: "有些肌肉的躯干", heads: ["新手头"], legs: ["踢腿", "踢腿", "踢腿", "踢腿"] },
    "机制流": { torso: "有些肌肉的躯干", torsoPlugin: "尖刺皮肤", heads: ["喷火头"],
               hands: [{ name: "抓握手", plugin: "爆裂腺体" }, { name: "长有芽孢的手", plugin: "胶质瘤" }],
               legs: [{ name: "新手腿", plugin: "碎骨锥" }] },
    // 第二批试验流:Akun 2026-07-22 新零件橱窗(喷毒部位AOE+触手战吼+蓄力+机制腿+属性尾巴)
    "第二批试验流": { torso: "强能躯干", heads: ["喷毒头"],
                     hands: ["触手", { name: "蓄力拳", plugin: "认真一拳" }],
                     legs: ["连环腿", "震撼腿"],
                     tails: [{ name: "猛尾", plugin: "冰虫尾巴" }] },
  };

  // ===== PVE 战役(Akun 2026-07-15 正式版:关卡名/剧情/奖励/解锁树均为他拍板)=====
  const STARTER_BUILD = { torso: "新手躯干", heads: ["新手头"], hands: ["装饰手"], legs: ["装饰腿"] };
  const STARTER_UNLOCKED = ["新手躯干", "新手头", "装饰手", "装饰腿"];
  const STARTER_BUDGET = 550;   // = 起始装价值(新手躯干350 + 新手头200)
  const CAMPAIGN = [
    { lv: 1, title: "生物质", name: "老迈的鹿", reward: 200, unlocks: ["新手手"],
      enemy: { torso: "鹿躯干" },
      story: "你从朦胧中醒来,漫步在一片荒凉的土地上,只感到一阵饥饿袭来……\n那是什么?一个四足行走的动物?\n不,你只觉得那是一团生物质……" },
    { lv: 2, title: "上手", name: "猛犸象", reward: 250, unlocks: ["新手腿", "新手尾巴"],
      enemy: { torso: "猛犸象躯干", heads: ["猛犸象头"] },
      story: "不错的一餐,你感到自己强壮了一些,是时候巡视一下这片地方了……\n远处有一个什么动物?他正恶狠狠地盯着你,他似乎对你的捕猎行为不太满意。\n一个猛犸象!" },
    { lv: 3, title: "先攻与闪避", name: "剑齿虎", reward: 650,   // 2026-07-22 Akun:1000→650(新增 L4 后重排曲线)
      unlocks: ["头部插槽", "四肢插槽", "普通能量核心", "头顶尖刺", "胶质瘤"],   // 机制引擎上线,Akun 拍板的插件解锁生效
      enemy: { torso: "剑齿虎躯干", heads: ["剑齿虎头"], hands: ["剑齿虎爪", "剑齿虎爪"] },
      story: "你慢慢厌倦了打不还手的对手,难道没有更有挑战性的敌人吗?\n这时一只剑齿虎出现在你面前。\n它甚至不知道你为什么要攻击它……" },
    { lv: 4, title: "毕竟,是一只怪兽", name: "肮脏的小怪兽", reward: 1200,   // Akun 2026-07-22 新增(d9cdfd2)
      // "解锁猛系部件" 按 猛头/猛爪/猛腿/猛尾 落地(工程理解,待 Akun 复核)
      unlocks: ["猛头", "猛爪", "猛腿", "猛尾", "稍微长大的躯干", "骨盾", "尖刺皮肤"],
      enemy: { torso: "新手躯干", slots: ["头部插槽"], heads: ["新手头", "新手头"],
               hands: ["新手手", { name: "新手手", plugin: "胶质瘤" }],
               legs: ["新手腿", "新手腿"], tails: ["新手尾巴"] },
      story: "远处有一个脏兮兮的家伙,它竟然有2个头!\n不过这没什么好惊讶\n毕竟,你是一只怪兽,你不仅可以有2个头,还可以有3只手!",
      winStory: "太好了!你战胜了第1个怪兽,只有怪兽才配做你的对手!\n接下来,去征服无尽的旷野,成为最厉害的大怪兽吧!" },
  ];

  return { CATALOG, PLUGINS, KIND_CN, makeMonster, makePart, allParts, validate, battle,
           dodgeTotal, initiativeTotal, commandSupply, energyUsed, supplyTotal, priceTotal,
           ARCHETYPES, DEFAULT_CFG, label, alive,
           CAMPAIGN, STARTER_BUILD, STARTER_UNLOCKED, STARTER_BUDGET };
});
