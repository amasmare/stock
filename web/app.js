/* واجهة المستخدم — يربط محرك Elliott بالصفحة */
(function () {
  "use strict";
  const E = window.Elliott;
  const data = {};            // {ticker: df}
  let lastScanRows = [];

  const $ = id => document.getElementById(id);
  const COLORS = { bullish: "#1a9641", bearish: "#d7191c", neutral: "#2b83ba" };

  // ───── التبويبات ─────
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
    document.querySelectorAll(".tabpane").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    $(t.dataset.tab).classList.add("active");
  });

  // ───── المتزلقات ─────
  const sync = (id, valId) => { const e = $(id); $(valId).textContent = e.value; e.oninput = () => { $(valId).textContent = e.value; if (id === "minScore" || id === "atrMult") runScanner(); refreshDetail(); }; };
  sync("minScore", "minScoreVal"); sync("atrMult", "atrVal");
  sync("rr", "rrVal"); sync("hold", "holdVal"); sync("minStruct", "structVal");
  $("patFilter").onchange = () => { runScanner(); refreshDetail(); };
  $("onlyValid").onchange = runScanner;

  // ───── رفع الملفات ─────
  $("files").onchange = async (ev) => {
    const files = [...ev.target.files];
    let ok = 0;
    for (const f of files) {
      try {
        const txt = await f.text();
        const df = E.parseCSV(txt);
        if (df.close.length >= 20) { data[f.name.replace(/\.csv$/i, "")] = df; ok++; }
      } catch (e) { console.warn(f.name, e.message); }
    }
    $("loaded").textContent = `✅ حُمّل ${Object.keys(data).length} سهم`;
    fillTickerSelect();
    runScanner();
  };

  function opts() {
    return {
      minScore: +$("minScore").value, atrMult: +$("atrMult").value,
      onlyValid: $("onlyValid").checked,
    };
  }
  function patOK(p) { const f = $("patFilter").value; return f === "الكل" || p === f; }

  // ───── الماسح ─────
  function runScanner() {
    const o = opts(), rows = [];
    for (const [tk, df] of Object.entries(data)) {
      for (const m of E.scan(df, o)) {
        if (!patOK(m.pattern)) continue;
        rows.push({ tk, m });
      }
    }
    rows.sort((a, b) => b.m.final_score - a.m.final_score);
    lastScanRows = rows;
    const wrap = $("scanTable");
    if (!rows.length) { wrap.innerHTML = '<p class="muted">لا توجد أنماط مطابقة. خفّض الدرجة أو ألغِ "القوانين المكتملة فقط".</p>'; return; }
    let html = `<table><thead><tr><th>السهم</th><th>النمط</th><th>الاتجاه</th><th>النهائي</th><th>البنية</th><th>التأكيدات</th><th>تكوّن</th><th>ملاحظة</th></tr></thead><tbody>`;
    for (const { tk, m } of rows) {
      const c = Object.values(m.confirmations).filter(Boolean).length, ct = Object.keys(m.confirmations).length;
      html += `<tr><td><b>${tk}</b></td><td>${m.pattern} <span class="muted">${m.patternAr}</span></td>`
        + `<td><span class="pill ${dirCls(m.direction)}">${dirAr(m.direction)}</span></td>`
        + `<td><b>${m.final_score}</b></td><td>${m.score}</td><td>${ct ? c + "/" + ct : "-"}</td>`
        + `<td>${m.forming ? "⏳" : ""}</td><td class="muted">${(m.notes[0] || "").slice(0, 40)}</td></tr>`;
    }
    wrap.innerHTML = html + "</tbody></table>";
  }

  $("dlCsv").onclick = () => {
    if (!lastScanRows.length) return;
    let csv = "Ticker,Pattern,NameAr,Direction,Final,Struct,Confirm,Forming,Note\n";
    for (const { tk, m } of lastScanRows) {
      const c = Object.values(m.confirmations).filter(Boolean).length, ct = Object.keys(m.confirmations).length;
      csv += `${tk},${m.pattern},${m.patternAr},${m.direction},${m.final_score},${m.score},${c}/${ct},${m.forming},"${(m.notes[0] || "")}"\n`;
    }
    const blob = new Blob(["﻿" + csv], { type: "text/csv" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "results.csv"; a.click();
  };

  // ───── التفاصيل ─────
  function fillTickerSelect() {
    const sel = $("detTicker"); sel.innerHTML = "";
    Object.keys(data).forEach(tk => { const o = document.createElement("option"); o.value = o.textContent = tk; sel.appendChild(o); });
    sel.onchange = refreshDetail;
    refreshDetail();
  }
  function refreshDetail() {
    const tk = $("detTicker").value; if (!tk || !data[tk]) return;
    const ms = E.scan(data[tk], { minScore: 0, onlyValid: false, atrMult: +$("atrMult").value }).filter(m => patOK(m.pattern));
    const sel = $("detMatch"); sel.innerHTML = "";
    ms.slice(0, 15).forEach((m, i) => { const o = document.createElement("option"); o.value = i; o.textContent = `${i + 1}. ${m.pattern} (${dirAr(m.direction)}) — نهائي ${m.final_score}`; sel.appendChild(o); });
    sel._matches = ms;
    sel.onchange = () => drawDetail(data[tk], ms[+sel.value]);
    if (ms.length) drawDetail(data[tk], ms[0]); else { $("detInfo").innerHTML = '<p class="muted">لا أنماط.</p>'; clearCanvas(); }
  }

  function drawDetail(df, m) {
    drawChart(df, m);
    const c = Object.values(m.confirmations).filter(Boolean).length, ct = Object.keys(m.confirmations).length;
    let h = `<div class="bigscore" style="color:${COLORS[m.direction]}">${m.final_score}</div>`
      + `<div class="muted">بنية ${m.score} · تأكيدات ${ct ? c + "/" + ct : "-"} · ${m.pattern} (${m.patternAr})</div>`;
    h += `<h3>القوانين</h3>`;
    for (const [k, v] of Object.entries(m.rules)) h += `<div class="line"><span class="${v ? 'ok' : 'no'}">${v ? '✅' : '❌'}</span>${k}</div>`;
    if (ct) { h += `<h3>تأكيدات الدقة</h3>`; for (const [k, v] of Object.entries(m.confirmations)) h += `<div class="line"><span class="${v ? 'ok' : 'no'}">${v ? '✅' : '❌'}</span>${k}</div>`; }
    if (Object.keys(m.targets).length) { h += `<h3>الأهداف 🎯</h3>`; for (const [k, v] of Object.entries(m.targets)) h += `<div class="line target">${k} = ${v}</div>`; }
    if (Object.keys(m.fib).length) { h += `<h3>فيبوناتشي</h3>`; for (const [k, v] of Object.entries(m.fib)) h += `<div class="line muted">${k}: ${v[0]}${v[1] != null ? " → " + v[1] : ""}</div>`; }
    $("detInfo").innerHTML = h;
  }

  // ───── رسم الشارت (canvas) ─────
  function clearCanvas() { const cv = $("chart"), x = cv.getContext("2d"); x.clearRect(0, 0, cv.width, cv.height); }
  function drawChart(df, m) {
    const cv = $("chart"), ctx = cv.getContext("2d");
    const W = cv.width, H = cv.height, padL = 8, padR = 70, padT = 16, padB = 24;
    ctx.clearRect(0, 0, W, H);
    const n = df.close.length;
    const allTargets = Object.values(m.targets);
    let lo = Math.min(...df.low), hi = Math.max(...df.high);
    for (const t of allTargets) { lo = Math.min(lo, t); hi = Math.max(hi, t); }
    const pad = (hi - lo) * 0.05 || 1; lo -= pad; hi += pad;
    const X = i => padL + (i / (n - 1)) * (W - padL - padR);
    const Y = p => padT + (1 - (p - lo) / (hi - lo)) * (H - padT - padB);

    // شبكة أفقية
    ctx.strokeStyle = "#1b2735"; ctx.fillStyle = "#7d93a6"; ctx.font = "10px sans-serif"; ctx.textAlign = "left";
    for (let g = 0; g <= 4; g++) { const p = lo + (hi - lo) * g / 4, y = Y(p); ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke(); ctx.fillText(p.toFixed(2), W - padR + 4, y + 3); }

    // خط الإغلاق
    ctx.strokeStyle = "#5a6b7d"; ctx.lineWidth = 1; ctx.beginPath();
    for (let i = 0; i < n; i++) { const x = X(i), y = Y(df.close[i]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); } ctx.stroke();

    // النقاط المحورية الخفيفة
    const atr = E.computeATRlast(df), last = df.close[n - 1];
    const pct = last ? Math.max(0.02, Math.min(0.15, (+$("atrMult").value) * atr / last)) : 0.05;
    const piv = E.zigzagPivots(df.high, df.low, pct);
    ctx.strokeStyle = "#3a4a5a"; ctx.lineWidth = 1; ctx.beginPath();
    piv.forEach((p, i) => { const x = X(p.idx), y = Y(p.price); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();

    // خطوط الأهداف
    const col = COLORS[m.direction];
    ctx.setLineDash([5, 4]); ctx.strokeStyle = col; ctx.fillStyle = col; ctx.globalAlpha = 0.8;
    for (const [name, t] of Object.entries(m.targets)) { const y = Y(t); ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke(); ctx.fillText(name + "=" + t, padL + 4, y - 3); }
    ctx.setLineDash([]); ctx.globalAlpha = 1;

    // موجات النمط
    ctx.strokeStyle = col; ctx.lineWidth = 2.6; ctx.beginPath();
    m.points_idx.forEach((ix, i) => { const x = X(ix), y = Y(m.points_price[i]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
    const labels = labelsFor(m);
    ctx.fillStyle = col; ctx.font = "bold 14px sans-serif"; ctx.textAlign = "center";
    m.points_idx.forEach((ix, i) => {
      const x = X(ix), y = Y(m.points_price[i]);
      ctx.beginPath(); ctx.arc(x, y, 4.5, 0, 7); ctx.fill();
      ctx.fillText(labels[i] || "", x, y - 10);
    });
  }
  function labelsFor(m) {
    if (m.category === "Motive") return ["0", "1", "2", "3", "4", "5"];
    return m.points_idx.length === 6 ? ["0", "A", "B", "C", "D", "E"] : ["0", "A", "B", "C"];
  }

  // ───── Backtest ─────
  $("runBt").onclick = () => {
    const rr = +$("rr").value, hold = +$("hold").value, ms = +$("minStruct").value;
    const trades = [];
    for (const [tk, df] of Object.entries(data)) {
      for (const m of E.scan(df, { recentWindows: null, onlyValid: true, minScore: ms, confirm: true })) {
        if (m.forming) continue;
        const r = E.simulateTrade(df, m, rr, hold);
        if (r) trades.push({ tk, pattern: m.pattern, outcome: r[0], R: r[1] });
      }
    }
    const wrap = $("btResult");
    if (!trades.length) { wrap.innerHTML = '<p class="muted">لا توجد صفقات كافية. خفّض "أدنى بنية".</p>'; return; }
    const byPat = {};
    for (const t of trades) { (byPat[t.pattern] ||= []).push(t); }
    let html = `<p>إجمالي ${trades.length} صفقة · RR=${rr} · أقصى ${hold} يوم</p><table><thead><tr><th>النمط</th><th>صفقات</th><th>فوز%</th><th>متوسط R</th><th>إجمالي R</th></tr></thead><tbody>`;
    const order = Object.entries(byPat).map(([p, g]) => {
      const w = g.filter(x => x.outcome === "win").length, l = g.filter(x => x.outcome === "loss").length, dec = w + l;
      const totR = g.reduce((a, x) => a + x.R, 0), avg = totR / g.length;
      return { p, n: g.length, win: dec ? 100 * w / dec : 0, avg, totR };
    }).sort((a, b) => b.totR - a.totR);
    for (const r of order) html += `<tr><td>${r.p}</td><td>${r.n}</td><td>${r.win.toFixed(1)}</td><td>${r.avg.toFixed(2)}</td><td><b>${r.totR.toFixed(1)}</b></td></tr>`;
    const W = trades.filter(x => x.outcome === "win").length, L = trades.filter(x => x.outcome === "loss").length, dec = W + L;
    const totR = trades.reduce((a, x) => a + x.R, 0);
    html += `</tbody></table><p class="${totR > 0 ? 'ok' : 'no'}" style="margin-top:10px">الإجمالي — فوز ${dec ? (100 * W / dec).toFixed(1) : 0}% · إجمالي R = ${totR.toFixed(1)}</p>`;
    wrap.innerHTML = html;
  };

  function dirAr(d) { return d === "bullish" ? "صاعد" : d === "bearish" ? "هابط" : "محايد"; }
  function dirCls(d) { return d === "bullish" ? "bull" : d === "bearish" ? "bear" : "neut"; }
})();
