"""
Backtest — قياس جدوى الأنماط تاريخياً
=====================================
يكتشف كل الأنماط المكتملة تاريخياً في كل سهم، يحاكي صفقة لكل نمط، ويحسب
نسبة النجاح والعائد المتوقع لكل نوع نمط.

منطق الصفقة (مبني على ص67 — التداول بعد التصحيح ومع الاتجاه):
  • الأنماط التصحيحية (Zigzag/Flat/Triangle): بعد اكتمال التصحيح ندخل في
    اتجاه استئناف الترند الرئيسي. وقف الخسارة عند طرف التصحيح، الهدف = R×المخاطرة.
  • الأنماط الحافزة (Impulse/Diagonal): بعد اكتمال 5 موجات نتوقع تصحيحاً،
    فندخل عكسياً. وقف الخسارة خلف نهاية W5.

الاستخدام:
    python backtest.py ./data
    python backtest.py ./data --rr 2 --max-hold 40 --min-struct 60
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

from elliott_waves import scan_dataframe, load_csv


def simulate_trade(df, m, rr=2.0, max_hold=40):
    """يحاكي صفقة من نمط مكتمل ويعيد (النتيجة، عائد R، أيام الحمل)."""
    last_idx = max(m.points_idx)
    entry_idx = last_idx + 1
    if entry_idx >= len(df) - 1:
        return None

    entry = float(df["Close"].iloc[entry_idx])
    stop = float(m.points_price[-1])  # طرف النمط = نقطة الإبطال

    if m.category == "Motive":
        trade_dir = -1 if m.direction == "bullish" else 1   # تصحيح متوقع بعد الدافعة
    else:
        d = 1 if m.direction == "bullish" else -1
        trade_dir = -d                                       # استئناف الاتجاه الرئيسي

    risk = abs(entry - stop)
    if risk <= 0 or risk / entry > 0.40:   # تجاهل مخاطرة غير منطقية
        return None
    target = entry + trade_dir * rr * risk

    end = min(len(df), entry_idx + 1 + max_hold)
    for j in range(entry_idx + 1, end):
        hi, lo = float(df["High"].iloc[j]), float(df["Low"].iloc[j])
        if trade_dir == 1:
            if lo <= stop:
                return ("loss", -1.0, j - entry_idx)
            if hi >= target:
                return ("win", rr, j - entry_idx)
        else:
            if hi >= stop:
                return ("loss", -1.0, j - entry_idx)
            if lo <= target:
                return ("win", rr, j - entry_idx)
    # انتهاء المدة — نحسب العائد عند الإغلاق الأخير
    final = float(df["Close"].iloc[end - 1])
    r = (final - entry) / risk * trade_dir
    return ("timeout", round(r, 2), end - 1 - entry_idx)


def main():
    ap = argparse.ArgumentParser(description="Backtest لأنماط إليوت")
    ap.add_argument("folder")
    ap.add_argument("--rr", type=float, default=2.0, help="نسبة الهدف للمخاطرة (افتراضي 2)")
    ap.add_argument("--max-hold", type=int, default=40, help="أقصى أيام للصفقة")
    ap.add_argument("--min-struct", type=float, default=55, help="أدنى درجة بنية للنمط")
    ap.add_argument("--min-confirm", type=float, default=0.0, help="أدنى نسبة تأكيدات 0..1")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, "*.csv")))
    trades = []

    for path in files:
        ticker = os.path.splitext(os.path.basename(path))[0]
        try:
            df = load_csv(path)
        except Exception:
            continue
        # كل التاريخ، الأنماط المكتملة فقط
        matches = scan_dataframe(df, recent_windows=None, only_valid=True,
                                 min_score=args.min_struct, confirm=True)
        for m in matches:
            if m.forming or m.confirm_ratio < args.min_confirm:
                continue
            res = simulate_trade(df, m, rr=args.rr, max_hold=args.max_hold)
            if res is None:
                continue
            outcome, r, held = res
            trades.append({"Ticker": ticker, "Pattern": m.pattern, "Dir": m.direction,
                           "Struct": m.score, "Confirm": round(m.confirm_ratio, 2),
                           "Outcome": outcome, "R": r, "Held": held})

    if not trades:
        print("لا توجد صفقات كافية. خفّض --min-struct أو نزّل بيانات أكثر/أطول.")
        return

    t = pd.DataFrame(trades)
    print(f"\n🧪 Backtest: {len(t)} صفقة من {len(files)} سهم | RR={args.rr} | "
          f"max_hold={args.max_hold}\n")

    # ملخص حسب النمط
    def agg(g):
        wins = (g["Outcome"] == "win").sum()
        losses = (g["Outcome"] == "loss").sum()
        decided = wins + losses
        return pd.Series({
            "صفقات": len(g),
            "فوز": wins, "خسارة": losses,
            "نسبة الفوز%": round(100 * wins / decided, 1) if decided else 0,
            "متوسط R": round(g["R"].mean(), 2),
            "إجمالي R": round(g["R"].sum(), 1),
        })

    by_pat = t.groupby("Pattern").apply(agg, include_groups=False).sort_values("إجمالي R", ascending=False)
    print("— حسب النمط —")
    print(by_pat.to_string())

    overall_dec = (t["Outcome"].isin(["win", "loss"])).sum()
    overall_win = (t["Outcome"] == "win").sum()
    print(f"\n— الإجمالي —")
    print(f"نسبة الفوز: {round(100*overall_win/overall_dec,1) if overall_dec else 0}% | "
          f"متوسط R: {round(t['R'].mean(),2)} | إجمالي R: {round(t['R'].sum(),1)}")
    print("\nملاحظة: العائد بوحدة R (مضاعف المخاطرة). إجمالي R موجب = استراتيجية رابحة.")


if __name__ == "__main__":
    main()
