"""
Elliott Wave Scanner — محرك اكتشاف أنماط إليوت الموجية
=======================================================
يطبّق قوانين دورة "التحليل الموجي واستراتيجية التداول" على بيانات الأسهم.

الأنماط الخمسة:
  Motive (حافزة - 5 موجات):   1) Impulse دافعة   2) Diagonal قطرية/وتدية
  Corrective (تصحيحية):        3) Zigzag زجزاج   4) Flat فلات   5) Triangle مثلث

المكونات:
  - compute_atr / zigzag_pivots : كشف النقاط المحورية (القمم والقيعان)
  - check_*                     : فاحص قوانين كل نمط + درجة ثقة فيبوناتشي
  - scan_dataframe              : يفحص سهم واحد ويرجع كل الأنماط المكتشفة
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# نسب فيبوناتشي المستخدمة في الملف
FIB = {
    "0.382": 0.382, "0.50": 0.5, "0.618": 0.618, "0.786": 0.786,
    "1.0": 1.0, "1.272": 1.272, "1.618": 1.618, "2.618": 2.618, "4.236": 4.236,
}


# ───────────────────────────── كشف النقاط المحورية ─────────────────────────────

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """متوسط المدى الحقيقي — لضبط حساسية الـ ZigZag حسب تذبذب السهم."""
    high, low, close = df["High"], df["Low"], df["Close"]
    prev = close.shift(1)
    tr = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def zigzag_pivots(high: np.ndarray, low: np.ndarray, pct: float):
    """
    خوارزمية ZigZag: ترجع قائمة نقاط محورية [(index, price, 'H'|'L'), ...].
    النقطة تتأكد فقط عند انعكاس السعر بنسبة pct من القمة/القاع الأخير.
    آخر نقطة تكون "تكوينية" (الموجة الجارية الآن).
    """
    n = len(high)
    pivots: list[tuple[int, float, str]] = []
    if n < 2:
        return pivots

    direction = 0  # 1 صاعد، -1 هابط، 0 غير محدد
    max_price, max_idx = high[0], 0
    min_price, min_idx = low[0], 0

    for i in range(1, n):
        if direction == 1:
            if high[i] >= max_price:
                max_price, max_idx = high[i], i
            elif low[i] <= max_price * (1 - pct):
                pivots.append((max_idx, float(max_price), "H"))
                direction = -1
                min_price, min_idx = low[i], i
        elif direction == -1:
            if low[i] <= min_price:
                min_price, min_idx = low[i], i
            elif high[i] >= min_price * (1 + pct):
                pivots.append((min_idx, float(min_price), "L"))
                direction = 1
                max_price, max_idx = high[i], i
        else:  # غير محدد — ننتظر أول حركة معتبرة
            if high[i] >= max_price:
                max_price, max_idx = high[i], i
            if low[i] <= min_price:
                min_price, min_idx = low[i], i
            if low[i] <= max_price * (1 - pct):
                pivots.append((max_idx, float(max_price), "H"))
                direction = -1
                min_price, min_idx = low[i], i
            elif high[i] >= min_price * (1 + pct):
                pivots.append((min_idx, float(min_price), "L"))
                direction = 1
                max_price, max_idx = high[i], i

    # النقطة الأخيرة (الموجة الجارية) — مفيدة لاكتشاف النماذج قيد التكوّن
    if direction == 1:
        pivots.append((max_idx, float(max_price), "H"))
    elif direction == -1:
        pivots.append((min_idx, float(min_price), "L"))
    return pivots


# ───────────────────────────── أدوات مساعدة ─────────────────────────────

def _closeness(ratio: float, target: float, tol: float = 0.25) -> float:
    """قرب نسبة من هدف فيبو: 1.0 = مطابق تماماً، 0 = خارج النطاق المسموح."""
    if target == 0:
        return 0.0
    diff = abs(ratio - target) / target
    return max(0.0, 1.0 - diff / tol)


def _best_fib(ratio: float, targets: list[float], tol: float = 0.25):
    """أفضل نسبة فيبو مطابقة + درجة القرب."""
    best_t, best_s = None, 0.0
    for t in targets:
        s = _closeness(ratio, t, tol)
        if s > best_s:
            best_t, best_s = t, s
    return best_t, best_s


@dataclass
class WaveMatch:
    """نتيجة اكتشاف نمط واحد."""
    pattern: str                 # نوع النمط بالإنجليزي
    pattern_ar: str              # نوع النمط بالعربي
    category: str                # Motive / Corrective
    direction: str               # bullish / bearish
    points_idx: list             # مؤشرات النقاط في الـ DataFrame
    points_price: list           # أسعار النقاط
    rules_ok: bool               # هل تحققت كل القوانين الإلزامية
    rules: dict                  # تفاصيل كل قانون
    score: float                 # درجة البنية 0..100 (قوانين + فيبو)
    fib: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)
    targets: dict = field(default_factory=dict)
    forming: bool = False        # هل النمط لا يزال قيد التكوّن
    confirmations: dict = field(default_factory=dict)  # تأكيدات الدقة (MTF/حجم/ماكد/قناة)
    confirm_ratio: float = 0.0   # نسبة التأكيدات المحققة 0..1
    final_score: float = 0.0     # الدرجة النهائية = البنية × التأكيدات

    def __post_init__(self):
        if not self.final_score:
            self.final_score = self.score

    def summary(self) -> str:
        tag = "⏳ قيد التكوّن" if self.forming else ("✅" if self.rules_ok else "❌")
        return (f"{tag} {self.pattern} ({self.pattern_ar}) | {self.direction} | "
                f"بنية={self.score:.0f} | نهائي={self.final_score:.0f} | "
                f"تأكيدات={sum(self.confirmations.values())}/{len(self.confirmations)}")


# ───────────────────────────── فاحصات الأنماط ─────────────────────────────

def check_impulse(pts) -> Optional[WaveMatch]:
    """نمط الدافعة Impulse — قوانين ص15 + إرشادات فيبو ص25/26."""
    kinds = [k for _, _, k in pts]
    if kinds == ["L", "H", "L", "H", "L", "H"]:
        d = 1
    elif kinds == ["H", "L", "H", "L", "H", "L"]:
        d = -1
    else:
        return None

    p = [pr for _, pr, _ in pts]
    idx = [i for i, _, _ in pts]
    w1, w2, w3, w4, w5 = (abs(p[1]-p[0]), abs(p[2]-p[1]), abs(p[3]-p[2]),
                          abs(p[4]-p[3]), abs(p[5]-p[4]))

    rules = {}
    if d == 1:
        rules["W2 لا تكسر بداية W1"] = p[2] > p[0]
        rules["W3 تتجاوز نهاية W1"] = p[3] > p[1]
        rules["W4 لا تتداخل مع W1"] = p[4] > p[1]
    else:
        rules["W2 لا تكسر بداية W1"] = p[2] < p[0]
        rules["W3 تتجاوز نهاية W1"] = p[3] < p[1]
        rules["W4 لا تتداخل مع W1"] = p[4] < p[1]
    rules["W3 ليست الأقصر"] = not (w3 < w1 and w3 < w5)
    rules_ok = all(rules.values())

    # درجة فيبو
    fib, notes, fscore, fmax = {}, [], 0.0, 0.0
    if w1 > 0:
        t, s = _best_fib(w3 / w1, [1.618, 2.618, 4.236]); fmax += 1; fscore += s
        fib["W3/W1"] = (round(w3/w1, 3), t);
        if s > 0.5: notes.append(f"W3 ≈ {t}×W1 (هدف الموجة الثالثة)")
        t, s = _best_fib(w5 / w1, [0.618, 1.0, 1.618]); fmax += 1; fscore += s
        fib["W5/W1"] = (round(w5/w1, 3), t)
    if w1 > 0:
        t, s = _best_fib(w2 / w1, [0.382, 0.5, 0.618, 0.786]); fmax += 1; fscore += s
        fib["W2 retr"] = (round(w2/w1, 3), t)
    if w3 > 0:
        t, s = _best_fib(w4 / w3, [0.236, 0.382, 0.5]); fmax += 1; fscore += s
        fib["W4 retr"] = (round(w4/w3, 3), t)

    # الموجة الثالثة هي الأطول غالباً (مكافأة)
    if w3 >= max(w1, w5):
        notes.append("W3 هي الأطول (مثالي)")
        fscore += 0.5;
    fmax += 0.5

    score = _final_score(rules, fscore, fmax)

    # الأهداف: امتداد W5 = نهاية W4 ± طول W1
    targets = {}
    if rules_ok:
        end4 = p[4]
        targets["W5 = W1"] = round(end4 + d * w1, 4)
        targets["W5 = 1.618×W1"] = round(end4 + d * 1.618 * w1, 4)

    return WaveMatch("Impulse", "دافعة", "Motive",
                     "bullish" if d == 1 else "bearish",
                     idx, [round(x, 4) for x in p], rules_ok, rules,
                     score, fib, notes, targets)


def check_diagonal(pts) -> Optional[WaveMatch]:
    """النمط القطري/الوتدي Diagonal — قوانين ص28 (يسمح بتداخل W4 مع W1)."""
    kinds = [k for _, _, k in pts]
    if kinds == ["L", "H", "L", "H", "L", "H"]:
        d = 1
    elif kinds == ["H", "L", "H", "L", "H", "L"]:
        d = -1
    else:
        return None

    p = [pr for _, pr, _ in pts]
    idx = [i for i, _, _ in pts]
    w1, w3, w5 = abs(p[1]-p[0]), abs(p[3]-p[2]), abs(p[5]-p[4])
    w2, w4 = abs(p[2]-p[1]), abs(p[4]-p[3])

    rules = {}
    if d == 1:
        rules["W2 لا تكسر بداية W1"] = p[2] > p[0]
        rules["W3 تتجاوز نهاية W1"] = p[3] > p[1]
        rules["W4 تتداخل مع W1 (شرط الوتد)"] = p[4] < p[1]
        rules["W4 لا تكسر بداية W3"] = p[4] > p[2]
    else:
        rules["W2 لا تكسر بداية W1"] = p[2] < p[0]
        rules["W3 تتجاوز نهاية W1"] = p[3] < p[1]
        rules["W4 تتداخل مع W1 (شرط الوتد)"] = p[4] > p[1]
        rules["W4 لا تكسر بداية W3"] = p[4] < p[2]
    rules["W3 ليست الأقصر"] = not (w3 < w1 and w3 < w5)
    # متقارب: W3<W1 و W5<W3 (الشكل الأشيع)
    contracting = (w3 < w1) and (w5 < w3) and (w4 < w2)
    rules["متقارب (3<1, 5<3, 4<2)"] = contracting
    rules_ok = all(rules.values())

    notes = ["وتد متقارب — غالباً ينعكس الاتجاه بقوة بعده"] if contracting else []
    score = _final_score(rules, 0.0, 0.0)
    return WaveMatch("Diagonal", "قطرية/وتدية", "Motive",
                     "bullish" if d == 1 else "bearish",
                     idx, [round(x, 4) for x in p], rules_ok, rules, score,
                     {}, notes)


def check_zigzag(pts) -> Optional[WaveMatch]:
    """عائلة الزجزاج Zigzag (A-B-C) — قوانين ص38 + إرشادات ص39."""
    kinds = [k for _, _, k in pts]
    if kinds == ["H", "L", "H", "L"]:
        d = -1   # تصحيح هابط (يصحح اتجاه صاعد)
    elif kinds == ["L", "H", "L", "H"]:
        d = 1    # تصحيح صاعد
    else:
        return None

    p = [pr for _, pr, _ in pts]
    idx = [i for i, _, _ in pts]
    a, b, c = abs(p[1]-p[0]), abs(p[2]-p[1]), abs(p[3]-p[2])

    rules = {}
    if d == -1:
        rules["B لا تتجاوز بداية A"] = p[2] < p[0]
        rules["C تتجاوز نهاية A"] = p[3] < p[1]
    else:
        rules["B لا تتجاوز بداية A"] = p[2] > p[0]
        rules["C تتجاوز نهاية A"] = p[3] > p[1]
    # B يصحح 38.2%–79% من A (إرشاد ص39)
    b_retr = b / a if a else 0
    rules["تصحيح B بين 38%–79% (إرشادي)"] = 0.30 <= b_retr <= 0.85
    rules_ok = rules["B لا تتجاوز بداية A"] and rules["C تتجاوز نهاية A"]

    fib, notes, fscore, fmax = {}, [], 0.0, 0.0
    if a > 0:
        t, s = _best_fib(c / a, [0.618, 1.0, 1.618]); fmax += 1; fscore += s
        fib["C/A"] = (round(c/a, 3), t)
        if s > 0.6: notes.append(f"C ≈ {t}×A")
        t, s = _best_fib(b_retr, [0.382, 0.5, 0.618, 0.786]); fmax += 1; fscore += s
        fib["B retr"] = (round(b_retr, 3), t)

    score = _final_score(rules, fscore, fmax)
    targets = {}
    if rules_ok:
        targets["C = A (تساوي)"] = round(p[2] + d * a, 4)
        targets["C = 1.618×A"] = round(p[2] + d * 1.618 * a, 4)
    return WaveMatch("Zigzag", "زجزاج", "Corrective",
                     "bullish" if d == 1 else "bearish",
                     idx, [round(x, 4) for x in p], rules_ok, rules, score,
                     fib, notes, targets)


def check_flat(pts) -> Optional[WaveMatch]:
    """عائلة الفلات Flat (A-B-C) — قوانين ص48 (B يصحح ≥90% من A)."""
    kinds = [k for _, _, k in pts]
    if kinds == ["H", "L", "H", "L"]:
        d = -1
    elif kinds == ["L", "H", "L", "H"]:
        d = 1
    else:
        return None

    p = [pr for _, pr, _ in pts]
    idx = [i for i, _, _ in pts]
    a, b, c = abs(p[1]-p[0]), abs(p[2]-p[1]), abs(p[3]-p[2])
    b_retr = b / a if a else 0

    rules = {}
    rules["B يصحح ≥ 90% من A"] = b_retr >= 0.90
    if d == -1:
        rules["B لا تتجاوز بداية A"] = p[2] <= p[0] * 1.05
    else:
        rules["B لا تتجاوز بداية A بكثير"] = p[2] >= p[0] * 0.95
    rules_ok = rules["B يصحح ≥ 90% من A"]

    # تصنيف نوع الفلات
    subtype = "Regular منتظم"
    if b_retr > 1.05:
        # ممتد إذا C تجاوزت نهاية A، متسلق إذا لم تتجاوز
        if (d == -1 and p[3] < p[1]) or (d == 1 and p[3] > p[1]):
            subtype = "Expanded ممتد"
        else:
            subtype = "Running متسلق (قوة الاتجاه القادم)"
    notes = [f"النوع: {subtype}"]

    fib, fscore, fmax = {}, 0.0, 0.0
    if a > 0:
        t, s = _best_fib(c / a, [1.0, 1.272, 1.618]); fmax += 1; fscore += s
        fib["C/A"] = (round(c/a, 3), t)
        fib["B/A"] = (round(b_retr, 3), None)
    score = _final_score(rules, fscore, fmax)
    return WaveMatch("Flat", "فلات", "Corrective",
                     "bullish" if d == 1 else "bearish",
                     idx, [round(x, 4) for x in p], rules_ok, rules, score,
                     fib, notes)


def check_triangle(pts) -> Optional[WaveMatch]:
    """نمط المثلث Triangle (A-B-C-D-E) — قوانين ص61 (متقارب/متوسع)."""
    if len(pts) < 6:
        return None
    pts = pts[:6]
    p = [pr for _, pr, _ in pts]
    idx = [i for i, _, _ in pts]
    a, b, c, dd, e = (abs(p[1]-p[0]), abs(p[2]-p[1]), abs(p[3]-p[2]),
                      abs(p[4]-p[3]), abs(p[5]-p[4]))

    contracting = (c < a) and (e < c) and (dd < b)
    expanding = (c > a) and (e > c) and (dd > b)
    rules = {
        "متقارب أو متوسع": contracting or expanding,
        "5 موجات متناقصة/متزايدة بانتظام": contracting or expanding,
    }
    rules_ok = contracting or expanding
    notes = []
    if contracting:
        notes.append("مثلث متقارب — يتبعه اختراق في اتجاه الترند")
    elif expanding:
        notes.append("مثلث متوسع (نادر)")

    fib, fscore, fmax = {}, 0.0, 0.0
    if a > 0:
        t, s = _best_fib(c / a, [0.618]); fmax += 1; fscore += s; fib["C/A"] = (round(c/a, 3), t)
    if b > 0:
        t, s = _best_fib(dd / b, [0.618]); fmax += 1; fscore += s; fib["D/B"] = (round(dd/b, 3), t)
    if c > 0:
        t, s = _best_fib(e / c, [0.618]); fmax += 1; fscore += s; fib["E/C"] = (round(e/c, 3), t)
    score = _final_score(rules, fscore, fmax)
    return WaveMatch("Triangle", "مثلث", "Corrective", "neutral",
                     idx, [round(x, 4) for x in p], rules_ok, rules, score,
                     fib, notes)


def _final_score(rules: dict, fscore: float, fmax: float) -> float:
    """درجة البنية: 60% للقوانين الإلزامية + 40% لإرشادات فيبوناتشي."""
    rule_part = (sum(1 for v in rules.values() if v) / len(rules)) if rules else 0
    fib_part = (fscore / fmax) if fmax > 0 else 0
    return round(100 * (0.60 * rule_part + 0.40 * fib_part), 1)


# ─────────────────────── محرك تأكيدات الدقة (تطويرات الدقة) ───────────────────────

def compute_indicators(df: pd.DataFrame) -> dict:
    """يحسب المؤشرات اللازمة للتأكيدات: MACD، المتوسطات، الاتجاه الأكبر، الحجم."""
    close = df["Close"].astype(float)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = (ema12 - ema26)
    hist = (macd - macd.ewm(span=9, adjust=False).mean())
    sma50 = close.rolling(50, min_periods=10).mean()
    sma100 = close.rolling(100, min_periods=20).mean()
    sma200 = close.rolling(200, min_periods=40).mean()

    # الاتجاه الأكبر (بديل عن الفريم الأسبوعي): قريب من اتجاه 100 يوم ≈ 20 أسبوع
    larger = np.zeros(len(df))
    c, s100, s50 = close.values, sma100.values, sma50.values
    for i in range(len(df)):
        if np.isnan(s100[i]):
            larger[i] = 0
        elif c[i] > s100[i] and s50[i] >= s100[i]:
            larger[i] = 1
        elif c[i] < s100[i] and s50[i] <= s100[i]:
            larger[i] = -1
        else:
            larger[i] = 0

    vol = df["Volume"].astype(float).values if "Volume" in df.columns else np.zeros(len(df))
    return {"macd": macd.values, "hist": hist.values, "larger_trend": larger,
            "sma50": s50, "sma100": s100, "sma200": sma200.values, "vol": vol}


def _mean_slice(arr, a, b):
    a, b = sorted((a, b))
    seg = arr[a:b + 1]
    return float(np.nanmean(seg)) if len(seg) else 0.0


def _max_slice(arr, a, b):
    a, b = sorted((a, b))
    seg = arr[a:b + 1]
    return float(np.nanmax(seg)) if len(seg) else 0.0


def _channel_break(idx, price, d) -> bool:
    """هل كسرت W3 القناة الموجية للموجة 1؟ (ص20)
    الخط الأساسي يمر ببداية W1 ونهاية W2، والقناة موازية تمر بقمة W1."""
    x0, x1, x2, x3 = idx[0], idx[1], idx[2], idx[3]
    y0, y1, y2, y3 = price[0], price[1], price[2], price[3]
    if x2 == x0:
        return False
    slope = (y2 - y0) / (x2 - x0)
    proj = y1 + slope * (x3 - x1)   # خط القناة الموازي عند زمن نهاية W3
    return (y3 > proj) if d == 1 else (y3 < proj)


def apply_confirmations(m: WaveMatch, df: pd.DataFrame, ind: dict) -> WaveMatch:
    """يضيف تأكيدات الدقة الخمسة ويعيد حساب الدرجة النهائية."""
    idx, price = m.points_idx, m.points_price
    macd, vol, larger = ind["macd"], ind["vol"], ind["larger_trend"]
    d = 1 if m.direction == "bullish" else -1
    last_i = max(idx)
    conf = {}

    if m.category == "Motive" and len(idx) >= 6:
        # 1) الحجم: حجم W3 أعلى من W1 (ص21)
        if vol.any():
            conf["حجم W3 > W1"] = _mean_slice(vol, idx[2], idx[3]) > _mean_slice(vol, idx[0], idx[1])
        # 2) قوة الماكد في W3 أعلى من W1 (ص18)
        conf["ماكد W3 الأقوى"] = (_max_slice(macd, idx[2], idx[3]) >= _max_slice(macd, idx[0], idx[1])) if d == 1 \
            else (-_max_slice(-macd, idx[2], idx[3]) <= -_max_slice(-macd, idx[0], idx[1]))
        # 3) دايفرجنس الماكد بين W3 و W5 لإنهاء الموجة (ص19)
        m3 = _max_slice(macd, idx[2], idx[3]); m5 = _max_slice(macd, idx[4], idx[5])
        conf["دايفرجنس W5 (نهاية)"] = (m5 < m3) if d == 1 else (
            _max_slice(-macd, idx[4], idx[5]) < _max_slice(-macd, idx[2], idx[3]))
        # 4) كسر W3 للقناة (ص20)
        conf["W3 تكسر القناة"] = _channel_break(idx, price, d)
        # 5) توافق الاتجاه الأكبر (MTF) (ص66)
        conf["توافق الفريم الأكبر"] = (larger[last_i] == d)

    else:  # تصحيحية: التصحيح فرصة للانضمام للاتجاه الأكبر (ص67)
        # MTF: التصحيح يجب أن يكون عكس الاتجاه الأكبر (تصحيح صحي)
        if m.direction != "neutral":
            conf["تصحيح مع الاتجاه الأكبر"] = (larger[last_i] == -d)
        # الحجم: في الزجزاج حجم A أعلى من C (ص39)
        if m.pattern == "Zigzag" and vol.any() and len(idx) >= 4:
            conf["حجم A > C"] = _mean_slice(vol, idx[0], idx[1]) > _mean_slice(vol, idx[2], idx[3])
        # قرب السعر من متوسط 200 (ارتداد منطقي)
        s200 = ind["sma200"][last_i]
        if not np.isnan(s200) and s200 > 0:
            conf["قرب متوسط 200"] = abs(price[-1] - s200) / s200 < 0.10

    m.confirmations = conf
    m.confirm_ratio = (sum(conf.values()) / len(conf)) if conf else 0.0
    # الدرجة النهائية: البنية مع مكافأة/خصم حسب التأكيدات (±30%)
    m.final_score = round(m.score * (0.70 + 0.30 * m.confirm_ratio), 1)
    return m


# ───────────────────────────── الماسح الرئيسي ─────────────────────────────

# (دالة الفحص، عدد النقاط المطلوبة)
_DETECTORS = [
    (check_impulse, 6),
    (check_diagonal, 6),
    (check_triangle, 6),
    (check_zigzag, 4),
    (check_flat, 4),
]


def scan_dataframe(df: pd.DataFrame, pct: Optional[float] = None,
                   atr_mult: float = 1.5, min_score: float = 0.0,
                   only_valid: bool = True, recent_windows: Optional[int] = 4,
                   confirm: bool = True) -> list[WaveMatch]:
    """
    يفحص سهماً واحداً ويرجع كل الأنماط المكتشفة (مرتبة حسب الدرجة النهائية).

    pct          : عتبة الـ ZigZag. لو None تُحسب تلقائياً من ATR.
    atr_mult     : مضاعف ATR لاشتقاق العتبة (افتراضي 1.5).
    min_score    : أدنى درجة نهائية للقبول.
    only_valid   : إن True يرجع فقط الأنماط المحققة لكل القوانين.
    recent_windows: كم نافذة أخيرة نفحص. None = كل التاريخ (للـ backtest).
    confirm      : تطبيق تأكيدات الدقة (MTF/حجم/ماكد/قناة).
    """
    df = df.dropna(subset=["High", "Low", "Close"]).reset_index(drop=True)
    if len(df) < 20:
        return []

    if pct is None:
        atr = compute_atr(df).iloc[-1]
        last = df["Close"].iloc[-1]
        pct = max(0.02, min(0.15, float(atr_mult * atr / last))) if last else 0.05

    pivots = zigzag_pivots(df["High"].values, df["Low"].values, pct)
    if len(pivots) < 4:
        return []

    ind = compute_indicators(df) if confirm else None
    matches: list[WaveMatch] = []
    n = len(pivots)
    for detector, size in _DETECTORS:
        start_from = 0 if recent_windows is None else max(0, n - size - recent_windows + 1)
        for s in range(start_from, n - size + 1):
            window = pivots[s:s + size]
            m = detector(window)
            if m is None:
                continue
            m.forming = (window[-1][0] == pivots[-1][0]) and (pivots[-1][0] >= len(df) - 5)
            if only_valid and not m.rules_ok:
                continue
            if confirm:
                apply_confirmations(m, df, ind)
            if m.final_score < min_score:
                continue
            matches.append(m)

    matches.sort(key=lambda x: x.final_score, reverse=True)
    return matches


def load_csv(path: str) -> pd.DataFrame:
    """يقرأ CSV بأعمدة Date,Open,High,Low,Close,Volume (غير حساس لحالة الأحرف)."""
    df = pd.read_csv(path)
    df.columns = [c.strip().capitalize() for c in df.columns]
    rename = {"Adj close": "Close", "Adj_close": "Close", "Vol": "Volume",
              "Timestamp": "Date", "Datetime": "Date"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    required = {"High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"الأعمدة الناقصة في {path}: {missing}")
    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
