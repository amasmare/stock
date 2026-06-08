/* ============================================================
   Elliott Wave Engine — JavaScript (منقول من elliott_waves.py)
   يعمل بالكامل في المتصفح — لا يحتاج سيرفر ولا بايثون.
   ============================================================ */
(function (root) {
  "use strict";

  // ───────────── أدوات مساعدة ─────────────
  function closeness(ratio, target, tol = 0.25) {
    if (target === 0) return 0;
    const diff = Math.abs(ratio - target) / target;
    return Math.max(0, 1 - diff / tol);
  }
  function bestFib(ratio, targets, tol = 0.25) {
    let bt = null, bs = 0;
    for (const t of targets) { const s = closeness(ratio, t, tol); if (s > bs) { bt = t; bs = s; } }
    return [bt, bs];
  }
  function meanSlice(arr, a, b) {
    if (a > b) [a, b] = [b, a];
    let sum = 0, n = 0;
    for (let i = a; i <= b && i < arr.length; i++) { if (!isNaN(arr[i])) { sum += arr[i]; n++; } }
    return n ? sum / n : 0;
  }
  function maxSlice(arr, a, b) {
    if (a > b) [a, b] = [b, a];
    let m = -Infinity;
    for (let i = a; i <= b && i < arr.length; i++) { if (!isNaN(arr[i]) && arr[i] > m) m = arr[i]; }
    return m === -Infinity ? 0 : m;
  }
  function minSlice(arr, a, b) {
    if (a > b) [a, b] = [b, a];
    let m = Infinity;
    for (let i = a; i <= b && i < arr.length; i++) { if (!isNaN(arr[i]) && arr[i] < m) m = arr[i]; }
    return m === Infinity ? 0 : m;
  }

  // ───────────── كشف النقاط المحورية (ZigZag) ─────────────
  function zigzagPivots(high, low, pct) {
    const n = high.length, pivots = [];
    if (n < 2) return pivots;
    let direction = 0;
    let maxP = high[0], maxI = 0, minP = low[0], minI = 0;
    for (let i = 1; i < n; i++) {
      if (direction === 1) {
        if (high[i] >= maxP) { maxP = high[i]; maxI = i; }
        else if (low[i] <= maxP * (1 - pct)) { pivots.push({ idx: maxI, price: maxP, kind: "H" }); direction = -1; minP = low[i]; minI = i; }
      } else if (direction === -1) {
        if (low[i] <= minP) { minP = low[i]; minI = i; }
        else if (high[i] >= minP * (1 + pct)) { pivots.push({ idx: minI, price: minP, kind: "L" }); direction = 1; maxP = high[i]; maxI = i; }
      } else {
        if (high[i] >= maxP) { maxP = high[i]; maxI = i; }
        if (low[i] <= minP) { minP = low[i]; minI = i; }
        if (low[i] <= maxP * (1 - pct)) { pivots.push({ idx: maxI, price: maxP, kind: "H" }); direction = -1; minP = low[i]; minI = i; }
        else if (high[i] >= minP * (1 + pct)) { pivots.push({ idx: minI, price: minP, kind: "L" }); direction = 1; maxP = high[i]; maxI = i; }
      }
    }
    if (direction === 1) pivots.push({ idx: maxI, price: maxP, kind: "H" });
    else if (direction === -1) pivots.push({ idx: minI, price: minP, kind: "L" });
    return pivots;
  }

  function computeATRlast(df, period = 14) {
    const { high, low, close } = df, n = high.length;
    if (n < 2) return 0;
    const tr = [];
    for (let i = 0; i < n; i++) {
      if (i === 0) tr.push(high[i] - low[i]);
      else tr.push(Math.max(high[i] - low[i], Math.abs(high[i] - close[i - 1]), Math.abs(low[i] - close[i - 1])));
    }
    const start = Math.max(0, n - period);
    let s = 0, c = 0;
    for (let i = start; i < n; i++) { s += tr[i]; c++; }
    return c ? s / c : 0;
  }

  function finalScore(rules, fscore, fmax) {
    const vals = Object.values(rules);
    const rulePart = vals.length ? vals.filter(Boolean).length / vals.length : 0;
    const fibPart = fmax > 0 ? fscore / fmax : 0;
    return Math.round((100 * (0.60 * rulePart + 0.40 * fibPart)) * 10) / 10;
  }

  // ───────────── فاحصات الأنماط ─────────────
  function kindsStr(pts) { return pts.map(p => p.kind).join(""); }

  function checkImpulse(pts) {
    const ks = kindsStr(pts);
    let d;
    if (ks === "LHLHLH") d = 1; else if (ks === "HLHLHL") d = -1; else return null;
    const p = pts.map(x => x.price), idx = pts.map(x => x.idx);
    const w1 = Math.abs(p[1]-p[0]), w2 = Math.abs(p[2]-p[1]), w3 = Math.abs(p[3]-p[2]),
          w4 = Math.abs(p[4]-p[3]), w5 = Math.abs(p[5]-p[4]);
    const rules = {};
    if (d === 1) {
      rules["W2 لا تكسر بداية W1"] = p[2] > p[0];
      rules["W3 تتجاوز نهاية W1"] = p[3] > p[1];
      rules["W4 لا تتداخل مع W1"] = p[4] > p[1];
    } else {
      rules["W2 لا تكسر بداية W1"] = p[2] < p[0];
      rules["W3 تتجاوز نهاية W1"] = p[3] < p[1];
      rules["W4 لا تتداخل مع W1"] = p[4] < p[1];
    }
    rules["W3 ليست الأقصر"] = !(w3 < w1 && w3 < w5);
    const rulesOk = Object.values(rules).every(Boolean);

    const fib = {}, notes = []; let fscore = 0, fmax = 0, t, s;
    if (w1 > 0) {
      [t, s] = bestFib(w3 / w1, [1.618, 2.618, 4.236]); fmax++; fscore += s;
      fib["W3/W1"] = [Math.round(w3/w1*1000)/1000, t]; if (s > 0.5) notes.push("W3 ≈ "+t+"×W1 (هدف الموجة الثالثة)");
      [t, s] = bestFib(w5 / w1, [0.618, 1.0, 1.618]); fmax++; fscore += s; fib["W5/W1"] = [Math.round(w5/w1*1000)/1000, t];
      [t, s] = bestFib(w2 / w1, [0.382, 0.5, 0.618, 0.786]); fmax++; fscore += s; fib["W2 retr"] = [Math.round(w2/w1*1000)/1000, t];
    }
    if (w3 > 0) { [t, s] = bestFib(w4 / w3, [0.236, 0.382, 0.5]); fmax++; fscore += s; fib["W4 retr"] = [Math.round(w4/w3*1000)/1000, t]; }
    if (w3 >= Math.max(w1, w5)) { notes.push("W3 هي الأطول (مثالي)"); fscore += 0.5; }
    fmax += 0.5;

    const score = finalScore(rules, fscore, fmax);
    const targets = {};
    if (rulesOk) { const e4 = p[4]; targets["W5 = W1"] = round4(e4 + d*w1); targets["W5 = 1.618×W1"] = round4(e4 + d*1.618*w1); }
    return mk("Impulse", "دافعة", "Motive", d === 1 ? "bullish" : "bearish", idx, p.map(round4), rulesOk, rules, score, fib, notes, targets);
  }

  function checkDiagonal(pts) {
    const ks = kindsStr(pts); let d;
    if (ks === "LHLHLH") d = 1; else if (ks === "HLHLHL") d = -1; else return null;
    const p = pts.map(x => x.price), idx = pts.map(x => x.idx);
    const w1 = Math.abs(p[1]-p[0]), w2 = Math.abs(p[2]-p[1]), w3 = Math.abs(p[3]-p[2]),
          w4 = Math.abs(p[4]-p[3]), w5 = Math.abs(p[5]-p[4]);
    const rules = {};
    if (d === 1) {
      rules["W2 لا تكسر بداية W1"] = p[2] > p[0];
      rules["W3 تتجاوز نهاية W1"] = p[3] > p[1];
      rules["W4 تتداخل مع W1 (شرط الوتد)"] = p[4] < p[1];
      rules["W4 لا تكسر بداية W3"] = p[4] > p[2];
    } else {
      rules["W2 لا تكسر بداية W1"] = p[2] < p[0];
      rules["W3 تتجاوز نهاية W1"] = p[3] < p[1];
      rules["W4 تتداخل مع W1 (شرط الوتد)"] = p[4] > p[1];
      rules["W4 لا تكسر بداية W3"] = p[4] < p[2];
    }
    rules["W3 ليست الأقصر"] = !(w3 < w1 && w3 < w5);
    const contracting = (w3 < w1) && (w5 < w3) && (w4 < w2);
    rules["متقارب (3<1, 5<3, 4<2)"] = contracting;
    const rulesOk = Object.values(rules).every(Boolean);
    const notes = contracting ? ["وتد متقارب — غالباً ينعكس الاتجاه بقوة بعده"] : [];
    return mk("Diagonal", "قطرية/وتدية", "Motive", d === 1 ? "bullish" : "bearish", idx, p.map(round4), rulesOk, rules, finalScore(rules, 0, 0), {}, notes, {});
  }

  function checkZigzag(pts) {
    const ks = kindsStr(pts); let d;
    if (ks === "HLHL") d = -1; else if (ks === "LHLH") d = 1; else return null;
    const p = pts.map(x => x.price), idx = pts.map(x => x.idx);
    const a = Math.abs(p[1]-p[0]), b = Math.abs(p[2]-p[1]), c = Math.abs(p[3]-p[2]);
    const rules = {};
    if (d === -1) { rules["B لا تتجاوز بداية A"] = p[2] < p[0]; rules["C تتجاوز نهاية A"] = p[3] < p[1]; }
    else { rules["B لا تتجاوز بداية A"] = p[2] > p[0]; rules["C تتجاوز نهاية A"] = p[3] > p[1]; }
    const bRetr = a ? b / a : 0;
    rules["تصحيح B بين 38%–79% (إرشادي)"] = bRetr >= 0.30 && bRetr <= 0.85;
    const rulesOk = rules["B لا تتجاوز بداية A"] && rules["C تتجاوز نهاية A"];
    const fib = {}, notes = []; let fscore = 0, fmax = 0, t, s;
    if (a > 0) {
      [t, s] = bestFib(c / a, [0.618, 1.0, 1.618]); fmax++; fscore += s; fib["C/A"] = [Math.round(c/a*1000)/1000, t]; if (s > 0.6) notes.push("C ≈ "+t+"×A");
      [t, s] = bestFib(bRetr, [0.382, 0.5, 0.618, 0.786]); fmax++; fscore += s; fib["B retr"] = [Math.round(bRetr*1000)/1000, t];
    }
    const score = finalScore(rules, fscore, fmax);
    const targets = {};
    if (rulesOk) { targets["C = A (تساوي)"] = round4(p[2] + d*a); targets["C = 1.618×A"] = round4(p[2] + d*1.618*a); }
    return mk("Zigzag", "زجزاج", "Corrective", d === 1 ? "bullish" : "bearish", idx, p.map(round4), rulesOk, rules, score, fib, notes, targets);
  }

  function checkFlat(pts) {
    const ks = kindsStr(pts); let d;
    if (ks === "HLHL") d = -1; else if (ks === "LHLH") d = 1; else return null;
    const p = pts.map(x => x.price), idx = pts.map(x => x.idx);
    const a = Math.abs(p[1]-p[0]), b = Math.abs(p[2]-p[1]), c = Math.abs(p[3]-p[2]);
    const bRetr = a ? b / a : 0;
    const rules = {};
    rules["B يصحح ≥ 90% من A"] = bRetr >= 0.90;
    if (d === -1) rules["B لا تتجاوز بداية A"] = p[2] <= p[0] * 1.05;
    else rules["B لا تتجاوز بداية A بكثير"] = p[2] >= p[0] * 0.95;
    const rulesOk = bRetr >= 0.90;
    let subtype = "Regular منتظم";
    if (bRetr > 1.05) {
      if ((d === -1 && p[3] < p[1]) || (d === 1 && p[3] > p[1])) subtype = "Expanded ممتد";
      else subtype = "Running متسلق (قوة الاتجاه القادم)";
    }
    const notes = ["النوع: " + subtype];
    const fib = {}; let fscore = 0, fmax = 0, t, s;
    if (a > 0) { [t, s] = bestFib(c / a, [1.0, 1.272, 1.618]); fmax++; fscore += s; fib["C/A"] = [Math.round(c/a*1000)/1000, t]; fib["B/A"] = [Math.round(bRetr*1000)/1000, null]; }
    return mk("Flat", "فلات", "Corrective", d === 1 ? "bullish" : "bearish", idx, p.map(round4), rulesOk, rules, finalScore(rules, fscore, fmax), fib, notes, {});
  }

  function checkTriangle(pts) {
    if (pts.length < 6) return null;
    pts = pts.slice(0, 6);
    const p = pts.map(x => x.price), idx = pts.map(x => x.idx);
    const a = Math.abs(p[1]-p[0]), b = Math.abs(p[2]-p[1]), c = Math.abs(p[3]-p[2]), dd = Math.abs(p[4]-p[3]), e = Math.abs(p[5]-p[4]);
    const contracting = (c < a) && (e < c) && (dd < b);
    const expanding = (c > a) && (e > c) && (dd > b);
    const rules = { "متقارب أو متوسع": contracting || expanding, "5 موجات منتظمة": contracting || expanding };
    const rulesOk = contracting || expanding;
    const notes = [];
    if (contracting) notes.push("مثلث متقارب — يتبعه اختراق في اتجاه الترند"); else if (expanding) notes.push("مثلث متوسع (نادر)");
    const fib = {}; let fscore = 0, fmax = 0, t, s;
    if (a > 0) { [t, s] = bestFib(c / a, [0.618]); fmax++; fscore += s; fib["C/A"] = [Math.round(c/a*1000)/1000, t]; }
    if (b > 0) { [t, s] = bestFib(dd / b, [0.618]); fmax++; fscore += s; fib["D/B"] = [Math.round(dd/b*1000)/1000, t]; }
    if (c > 0) { [t, s] = bestFib(e / c, [0.618]); fmax++; fscore += s; fib["E/C"] = [Math.round(e/c*1000)/1000, t]; }
    return mk("Triangle", "مثلث", "Corrective", "neutral", idx, p.map(round4), rulesOk, rules, finalScore(rules, fscore, fmax), fib, notes, {});
  }

  function mk(pattern, patternAr, category, direction, idx, price, rulesOk, rules, score, fib, notes, targets) {
    return { pattern, patternAr, category, direction, points_idx: idx, points_price: price,
             rules_ok: rulesOk, rules, score, fib: fib || {}, notes: notes || [], targets: targets || {},
             forming: false, confirmations: {}, confirm_ratio: 0, final_score: score };
  }
  function round4(x) { return Math.round(x * 10000) / 10000; }

  // ───────────── المؤشرات والتأكيدات ─────────────
  function ema(arr, span) {
    const k = 2 / (span + 1), out = new Array(arr.length);
    out[0] = arr[0];
    for (let i = 1; i < arr.length; i++) out[i] = arr[i] * k + out[i - 1] * (1 - k);
    return out;
  }
  function sma(arr, win, minP) {
    const out = new Array(arr.length).fill(NaN);
    let sum = 0;
    for (let i = 0; i < arr.length; i++) {
      sum += arr[i];
      if (i >= win) sum -= arr[i - win];
      const cnt = Math.min(i + 1, win);
      if (cnt >= (minP || win)) out[i] = sum / cnt;
    }
    return out;
  }
  function computeIndicators(df) {
    const close = df.close;
    const e12 = ema(close, 12), e26 = ema(close, 26);
    const macd = close.map((_, i) => e12[i] - e26[i]);
    const sma50 = sma(close, 50, 10), sma100 = sma(close, 100, 20), sma200 = sma(close, 200, 40);
    const larger = close.map((c, i) => {
      const s100 = sma100[i], s50 = sma50[i];
      if (isNaN(s100)) return 0;
      if (c > s100 && s50 >= s100) return 1;
      if (c < s100 && s50 <= s100) return -1;
      return 0;
    });
    const vol = df.volume && df.volume.length ? df.volume : close.map(() => 0);
    return { macd, larger_trend: larger, sma200, vol };
  }
  function channelBreak(idx, price, d) {
    const x0 = idx[0], x1 = idx[1], x2 = idx[2], x3 = idx[3];
    const y0 = price[0], y1 = price[1], y2 = price[2], y3 = price[3];
    if (x2 === x0) return false;
    const slope = (y2 - y0) / (x2 - x0);
    const proj = y1 + slope * (x3 - x1);
    return d === 1 ? (y3 > proj) : (y3 < proj);
  }
  function applyConfirmations(m, df, ind) {
    const idx = m.points_idx, price = m.points_price;
    const macd = ind.macd, vol = ind.vol, larger = ind.larger_trend;
    const d = m.direction === "bullish" ? 1 : -1;
    const lastI = Math.max(...idx);
    const conf = {};
    const hasVol = vol.some(v => v > 0);
    if (m.category === "Motive" && idx.length >= 6) {
      if (hasVol) conf["حجم W3 > W1"] = meanSlice(vol, idx[2], idx[3]) > meanSlice(vol, idx[0], idx[1]);
      conf["ماكد W3 الأقوى"] = d === 1 ? (maxSlice(macd, idx[2], idx[3]) >= maxSlice(macd, idx[0], idx[1]))
                                       : (minSlice(macd, idx[2], idx[3]) <= minSlice(macd, idx[0], idx[1]));
      conf["دايفرجنس W5 (نهاية)"] = d === 1 ? (maxSlice(macd, idx[4], idx[5]) < maxSlice(macd, idx[2], idx[3]))
                                            : (minSlice(macd, idx[4], idx[5]) > minSlice(macd, idx[2], idx[3]));
      conf["W3 تكسر القناة"] = channelBreak(idx, price, d);
      conf["توافق الفريم الأكبر"] = larger[lastI] === d;
    } else {
      if (m.direction !== "neutral") conf["تصحيح مع الاتجاه الأكبر"] = larger[lastI] === -d;
      if (m.pattern === "Zigzag" && hasVol && idx.length >= 4) conf["حجم A > C"] = meanSlice(vol, idx[0], idx[1]) > meanSlice(vol, idx[2], idx[3]);
      const s200 = ind.sma200[lastI];
      if (!isNaN(s200) && s200 > 0) conf["قرب متوسط 200"] = Math.abs(price[price.length - 1] - s200) / s200 < 0.10;
    }
    m.confirmations = conf;
    const vals = Object.values(conf);
    m.confirm_ratio = vals.length ? vals.filter(Boolean).length / vals.length : 0;
    m.final_score = Math.round(m.score * (0.70 + 0.30 * m.confirm_ratio) * 10) / 10;
    return m;
  }

  // ───────────── الماسح ─────────────
  const DETECTORS = [[checkImpulse, 6], [checkDiagonal, 6], [checkTriangle, 6], [checkZigzag, 4], [checkFlat, 4]];

  function scan(df, opts) {
    opts = opts || {};
    const atrMult = opts.atrMult != null ? opts.atrMult : 1.5;
    const minScore = opts.minScore != null ? opts.minScore : 0;
    const onlyValid = opts.onlyValid != null ? opts.onlyValid : true;
    const recentWindows = opts.recentWindows === undefined ? 4 : opts.recentWindows; // null = الكل
    const confirm = opts.confirm != null ? opts.confirm : true;
    const n = df.close.length;
    if (n < 20) return [];
    let pct = opts.pct;
    if (pct == null) {
      const atr = computeATRlast(df), last = df.close[n - 1];
      pct = last ? Math.max(0.02, Math.min(0.15, atrMult * atr / last)) : 0.05;
    }
    const pivots = zigzagPivots(df.high, df.low, pct);
    if (pivots.length < 4) return [];
    const ind = confirm ? computeIndicators(df) : null;
    const matches = [];
    const np = pivots.length;
    for (const [detector, size] of DETECTORS) {
      const startFrom = recentWindows == null ? 0 : Math.max(0, np - size - recentWindows + 1);
      for (let sIdx = startFrom; sIdx <= np - size; sIdx++) {
        const win = pivots.slice(sIdx, sIdx + size);
        const m = detector(win);
        if (!m) continue;
        m.forming = (win[win.length - 1].idx === pivots[np - 1].idx) && (pivots[np - 1].idx >= n - 5);
        if (onlyValid && !m.rules_ok) continue;
        if (confirm) applyConfirmations(m, df, ind);
        if (m.final_score < minScore) continue;
        matches.push(m);
      }
    }
    matches.sort((a, b) => b.final_score - a.final_score);
    return matches;
  }

  // ───────────── Backtest ─────────────
  function simulateTrade(df, m, rr = 2.0, maxHold = 40) {
    const lastIdx = Math.max(...m.points_idx), entryIdx = lastIdx + 1;
    if (entryIdx >= df.close.length - 1) return null;
    const entry = df.close[entryIdx], stop = m.points_price[m.points_price.length - 1];
    let tradeDir;
    if (m.category === "Motive") tradeDir = m.direction === "bullish" ? -1 : 1;
    else tradeDir = m.direction === "bullish" ? -1 : 1; // resume = -d ; d=bull->1 => -1
    const risk = Math.abs(entry - stop);
    if (risk <= 0 || risk / entry > 0.40) return null;
    const target = entry + tradeDir * rr * risk;
    const end = Math.min(df.close.length, entryIdx + 1 + maxHold);
    for (let j = entryIdx + 1; j < end; j++) {
      const hi = df.high[j], lo = df.low[j];
      if (tradeDir === 1) {
        if (lo <= stop) return ["loss", -1.0];
        if (hi >= target) return ["win", rr];
      } else {
        if (hi >= stop) return ["loss", -1.0];
        if (lo <= target) return ["win", rr];
      }
    }
    const fin = df.close[end - 1];
    return ["timeout", Math.round((fin - entry) / risk * tradeDir * 100) / 100];
  }

  // ───────────── قارئ CSV ─────────────
  function parseCSV(text) {
    const lines = text.replace(/\r/g, "").split("\n").filter(l => l.trim());
    if (!lines.length) throw new Error("ملف فارغ");
    const header = lines[0].split(",").map(h => h.trim().toLowerCase());
    const col = name => header.findIndex(h => h === name || h === name + "_" || h.startsWith(name));
    const ci = {
      date: header.findIndex(h => /date|time/.test(h)),
      open: col("open"), high: col("high"), low: col("low"),
      close: header.findIndex(h => h === "close" || h === "adj close" || h === "adj_close"),
      volume: col("volume"),
    };
    if (ci.high < 0 || ci.low < 0 || ci.close < 0) throw new Error("أعمدة ناقصة (يلزم High,Low,Close)");
    const df = { date: [], open: [], high: [], low: [], close: [], volume: [] };
    for (let i = 1; i < lines.length; i++) {
      const c = lines[i].split(",");
      const close = parseFloat(c[ci.close]); if (isNaN(close)) continue;
      df.date.push(ci.date >= 0 ? c[ci.date] : i);
      df.open.push(ci.open >= 0 ? parseFloat(c[ci.open]) : close);
      df.high.push(parseFloat(c[ci.high]));
      df.low.push(parseFloat(c[ci.low]));
      df.close.push(close);
      df.volume.push(ci.volume >= 0 ? parseFloat(c[ci.volume]) || 0 : 0);
    }
    return df;
  }

  root.Elliott = { zigzagPivots, scan, simulateTrade, parseCSV, computeIndicators, computeATRlast };
})(typeof window !== "undefined" ? window : global);

if (typeof module !== "undefined" && module.exports) module.exports = (typeof global !== "undefined" ? global.Elliott : null);
