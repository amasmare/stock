"""
مولّد بيانات تجريبية — ينشئ ملفات CSV فيها أنماط إليوت معروفة لاختبار الماسح.
ينشئ مجلد ./data فيه:
  IMPULSE.csv  — دافعة صاعدة كاملة 1-2-3-4-5
  ZIGZAG.csv   — تصحيح زجزاج A-B-C
  NOISE.csv    — حركة عشوائية (يجب ألا يلتقط نمطاً قوياً)
"""
import os
import numpy as np
import pandas as pd

os.makedirs("data", exist_ok=True)
rng = np.random.default_rng(42)


def to_ohlc(closes, name):
    """يحوّل سلسلة إغلاقات إلى OHLC مع شمعات واقعية ويحفظها."""
    closes = np.asarray(closes, dtype=float)
    dates = pd.bdate_range("2022-01-03", periods=len(closes))
    opens = np.r_[closes[0], closes[:-1]]
    noise = np.abs(rng.normal(0, np.maximum(closes * 0.004, 0.01)))
    highs = np.maximum(opens, closes) + noise
    lows = np.minimum(opens, closes) - noise
    vol = rng.integers(1_000_000, 5_000_000, len(closes))
    df = pd.DataFrame({"Date": dates, "Open": opens.round(2), "High": highs.round(2),
                       "Low": lows.round(2), "Close": closes.round(2), "Volume": vol})
    path = os.path.join("data", f"{name}.csv")
    df.to_csv(path, index=False)
    print(f"✅ {path}  ({len(df)} شمعة)")


def leg(start, end, steps, wobble=0.15):
    """ساق سعرية من start إلى end مع تذبذب صغير داخلها."""
    base = np.linspace(start, end, steps)
    amp = abs(end - start) * wobble
    jitter = rng.normal(0, amp / 3, steps)
    jitter[0] = jitter[-1] = 0
    return base + jitter


# نمط دافعة صاعدة مثالي: W3 الأطول، W2/W4 تصحيحات، W4 لا يتداخل مع W1
imp = np.concatenate([
    leg(100, 100, 15),          # تمهيد
    leg(100, 120, 20),          # W1  +20
    leg(120, 110, 12),          # W2  retr ~50%
    leg(110, 150, 30),          # W3  +40 (الأطول، ≈2×W1)
    leg(150, 138, 12),          # W4  retr ~30% (لا يتداخل مع قمة W1=120)
    leg(138, 162, 20),          # W5  ≈W1
    leg(162, 150, 15),          # بداية تصحيح
])
to_ohlc(imp, "IMPULSE")

# نمط زجزاج هابط A-B-C مع A=C
zz = np.concatenate([
    leg(80, 80, 15),
    leg(80, 100, 18),           # صعود سابق
    leg(100, 78, 22),           # A  -22
    leg(78, 90, 12),            # B  retr ~55%
    leg(90, 68, 22),            # C  ≈A
    leg(68, 75, 12),
])
to_ohlc(zz, "ZIGZAG")

# ضوضاء عشوائية
noise = 50 + np.cumsum(rng.normal(0, 1.0, 160))
to_ohlc(noise, "NOISE")

print("\nجاهز. شغّل:  python scan.py ./data --all --min-score 0")
