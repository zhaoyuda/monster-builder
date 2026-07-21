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
    // 喷火头(Q17a):无法暴击,火焰伤害,额外随机攻击 1 个目标,伤害目标挂"灼烧"(2/回合×3,刷新)
    "喷火头":   { kind: "head", atk: 15, hp: 100, energy: 30, command: 2, crit: 0, fire: true, price: 550 },
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
    // 腿
    "新手腿":   { kind: "leg", atk: 3,  hp: 20, energy: 5,  initiative: 1, dodge: 0.05, price: 100 },
    "猛腿":     { kind: "leg", atk: 6,  hp: 50, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "鞭腿":     { kind: "leg", atk: 8,  hp: 40, energy: 10, initiative: 2, dodge: 0.05, price: 200 },
    "灵活的腿": { kind: "leg", atk: 4,  hp: 60, energy: 10, initiative: 2, dodge: 0.07, price: 200 },
    "踢腿":     { kind: "leg", atk: 10, hp: 50, energy: 10, initiative: 0, dodge: 0.0,  price: 200 },
    // 躯干:command=基础指挥点(Akun 2026-07-15 拍板 2/3/3;价格按新公式 1供能=5价)
    "新手躯干":       { kind: "torso", atk: 0, hp: 100, supply: 30, command: 2, price: 350 },
    "稍微长大的躯干": { kind: "torso", atk: 0, hp: 200, supply: 60, command: 3, price: 700 },
    "有些肌肉的躯干": { kind: "torso", atk: 0, hp: 150, supply: 80, command: 3, price: 700 },
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
  };
  const KIND_CN = { head: "头", hand: "手", leg: "腿", torso: "躯干", tail: "尾" };
  // 机制常量(与 sim/engine.py 同步)
  const BURN_DMG = 2, TEAR_DMG = 2, BURN_ROUNDS = 3, GRAB_ROUNDS = 5, SPORE_ROUNDS = 2;

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
      plugin: "", pve: !!s.pve, price: s.price || 0,
      // 运行时状态
      burn: null, tear: null, stunPartNext: false, stunnedPart: false,
      grabUsed: false, keratin: 0, sporeWait: -1,
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
    m.tails.reduce((s, t) => s + t.initiative, 0);
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
    if (m.heads.length > headSlots) errs.push(`头槽超限:${m.heads.length} > ${headSlots}`);
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
      victim.burn = victim.tear = null;
      victim.stunnedPart = victim.stunPartNext = false;
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

    // 耐火皮肤护全身(Akun 2026-07-21 批注 Q19d):躯干挂耐火 → 全队火伤减半+免疫灼烧
    function fireproofSide(key) {
      const t = sides[key].torso;
      return t.plugin === "耐火皮肤" && alive(t);
    }

    function afterDamage(round, attacker, atkKey, victim, defKey, dmg) {
      if (dmg <= 0) return;
      if (attacker.fire && alive(victim) && !fireproofSide(defKey)) {
        victim.burn = { left: BURN_ROUNDS, src: attacker, srcKey: atkKey };
        log(round, "status", { side: defKey, part: label(victim), status: "burn",
          rounds: BURN_ROUNDS, by: label(attacker) });
      }
      if (attacker.plugin === "撕裂爪" && alive(victim)) {
        victim.tear = { left: PLUGINS["撕裂爪"].tearRounds, src: attacker, srcKey: atkKey };
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
        log(round, "status", { side: atkKey, part: label(attacker), status: "tear",
          rounds: PLUGINS["尖刺皮肤"].tearRounds, by: label(victim) });
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

    function strike(round, atkKey, attacker, target, extra) {
      const defKey = enemyKey(atkKey), defender = sides[defKey];
      // 1) 闪避(全身共享;被抓握则清零)
      const dv = round <= zeroUntil[defKey] ? 0 : dodgeTotal(defender, cfg);
      if (dv > 0 && rand() < dv) {
        log(round, "dodge", { side: atkKey, attacker: label(attacker),
          target: label(target), dodge: dv, extra: !!extra });
        return;
      }
      // 1.2) 抓握手:第一次命中不造成伤害,敌方 5 回合闪避清零(被闪掉不消耗)
      if (attacker.grab && !attacker.grabUsed) {
        attacker.grabUsed = true;
        zeroUntil[defKey] = round + GRAB_ROUNDS;
        log(round, "grab", { side: atkKey, attacker: label(attacker),
          target: label(target), rounds: GRAB_ROUNDS });
        return;
      }
      let dmg = attacker.atk;
      // 1.5) 暴击(仅 crit>0 掷骰;角质层生效期间宿主头不暴击)
      const effCrit = attacker.keratin > 0 ? 0 : attacker.crit;
      let crit = false;
      if (effCrit > 0 && cfg.critMult > 1 && rand() < effCrit) {
        crit = true;
        dmg = Math.floor(dmg * cfg.critMult);
      }
      // 1.8) 头顶角质层:替宿主头整次吸收,2 次后失效
      if (target.kind === "head" && target.keratin > 0) {
        target.keratin -= 1;
        log(round, "absorb", { side: atkKey, attacker: label(attacker),
          target: label(target), left: target.keratin });
        return;
      }
      // 2) 格挡(E5 末位存活手;骨盾再×80%)
      const blockers = defender.hands.filter(alive);
      if ((target.kind === "head" || target.kind === "torso") && blockers.length && rand() < cfg.blockProb) {
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
        return;
      }
      // 3) 正常结算(E6;耐火皮肤护全身:火焰伤害减半,Akun Q19d 批注)
      const fireproof = attacker.fire && fireproofSide(defKey) && dmg > 0;
      if (fireproof) dmg = Math.max(1, Math.floor(dmg * 0.5));
      target.hp -= dmg;
      log(round, "hit", { side: atkKey, attacker: label(attacker), target: label(target),
        dmg, targetHp: Math.max(target.hp, 0), crit, extra: !!extra, fireproof });
      afterDamage(round, attacker, atkKey, target, defKey, dmg);
      if (!alive(target)) handleBreak(round, target, defKey, attacker, atkKey);
    }

    function resolve(round, atkKey, attacker) {
      const defender = sides[enemyKey(atkKey)];
      const target = chooseTarget(attacker.kind, defender);
      strike(round, atkKey, attacker, target, false);
      // 喷火头(Q17a):额外随机攻击 1 个目标(尽量避开主目标),独立结算
      if (attacker.fire && !winner && alive(attacker)) {
        const pool = [defender.torso, ...defender.heads, ...defender.hands, ...defender.legs]
          .filter((p) => alive(p) && p !== target);
        if (pool.length) strike(round, atkKey, attacker, choice(pool), true);
      }
    }

    function tickDots(round) {
      for (const k of ["A", "B"]) {
        for (const p of allParts(sides[k])) {
          for (const [statusName, dmgVal] of [["burn", BURN_DMG], ["tear", TEAR_DMG]]) {
            const st = p[statusName];
            if (!st || !alive(p)) continue;
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

    function tickRegen(round) {
      for (const k of ["A", "B"]) {
        if (!regen[k].length) continue;
        const amount = PLUGINS["胶质瘤"].heal * regen[k].length;
        const [healed, hparts] = healSide(k, amount, null);
        if (healed > 0) log(round, "regen", { side: k, heal: amount, healed, parts: hparts });
        regen[k] = regen[k].map((r) => r - 1).filter((r) => r > 0);
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
        const seq = [];
        for (let i = 0; i < Math.max(fp.length, sp.length); i++) {
          if (i < fp.length) seq.push([firstKey, fp[i]]);
          if (i < sp.length) seq.push([secondKey, sp[i]]);
        }
        for (const [atkKey, part] of seq) {
          if (winner || skip[atkKey] || !alive(part) || part.stunnedPart
              || (part.atk <= 0 && !part.grab)) continue;
          if (cfg.commandMode === "battle" && (kind === "leg" || kind === "hand")) {
            if (cmdPool[atkKey] <= 0) {
              log(roundNo, "no_command", { side: atkKey, part: label(part) });
              continue;
            }
            cmdPool[atkKey] -= 1;
          }
          // 多段攻击(猛犸象头"双击"):每段独立结算,整体只耗 1 指挥点
          for (let h = 0; h < part.hits; h++) {
            if (winner || !alive(part)) break;
            resolve(roundNo, atkKey, part);
          }
        }
        if (winner) break;
      }
      // 回合末:DoT 结算 → 胶质瘤回复
      if (!winner) tickDots(roundNo);
      if (!winner) tickRegen(roundNo);
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
    { lv: 3, title: "先攻与闪避", name: "剑齿虎", reward: 1000,
      unlocks: ["头部插槽", "四肢插槽", "普通能量核心", "头顶尖刺", "胶质瘤"],   // 机制引擎上线,Akun 拍板的插件解锁生效
      enemy: { torso: "剑齿虎躯干", heads: ["剑齿虎头"], hands: ["剑齿虎爪", "剑齿虎爪"] },
      story: "你慢慢厌倦了打不还手的对手,难道没有更有挑战性的敌人吗?\n这时一只剑齿虎出现在你面前。\n它甚至不知道你为什么要攻击它……" },
  ];

  return { CATALOG, PLUGINS, KIND_CN, makeMonster, makePart, allParts, validate, battle,
           dodgeTotal, initiativeTotal, commandSupply, energyUsed, supplyTotal, priceTotal,
           ARCHETYPES, DEFAULT_CFG, label, alive,
           CAMPAIGN, STARTER_BUILD, STARTER_UNLOCKED, STARTER_BUDGET };
});
