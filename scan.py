"""
الماسح — Elliott Wave Scanner CLI
=================================
يمر على مجلد فيه ملفات CSV (كل ملف = سهم) ويطبع الأسهم المكوّنة لأنماط إليوت
مرتبة حسب درجة الثقة.

الاستخدام:
    python scan.py <مجلد_البيانات> [خيارات]

أمثلة:
    python scan.py ./data
    python scan.py ./data --pattern Impulse --min-score 70
    python scan.py ./data --all --csv-out results.csv
    python scan.py ./data --ticker AAPL          # تفاصيل سهم واحد

صيغة ملف CSV المتوقعة (أعمدة):
    Date,Open,High,Low,Close,Volume
"""

import argparse
import glob
import os
import sys

import pandas as pd

from elliott_waves import scan_dataframe, load_csv


def main():
    ap = argparse.ArgumentParser(description="ماسح أنماط إليوت الموجية للأسهم")
    ap.add_argument("folder", help="مجلد ملفات CSV (كل ملف = سهم)")
    ap.add_argument("--pattern", help="فلترة نوع واحد: Impulse/Diagonal/Zigzag/Flat/Triangle")
    ap.add_argument("--min-score", type=float, default=55, help="أدنى درجة ثقة (افتراضي 55)")
    ap.add_argument("--pct", type=float, default=None, help="عتبة ZigZag يدوية (مثل 0.05)")
    ap.add_argument("--atr-mult", type=float, default=1.5, help="مضاعف ATR للعتبة التلقائية")
    ap.add_argument("--all", action="store_true", help="إظهار حتى الأنماط غير المكتملة القوانين")
    ap.add_argument("--ticker", help="فحص سهم واحد بالتفصيل (اسم الملف بدون .csv)")
    ap.add_argument("--csv-out", help="حفظ النتائج في ملف CSV")
    ap.add_argument("--top", type=int, default=40, help="عدد الصفوف المعروضة")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.folder, "*.csv")))
    if args.ticker:
        files = [f for f in files if os.path.splitext(os.path.basename(f))[0].upper() == args.ticker.upper()]
    if not files:
        print(f"⚠️  لا توجد ملفات CSV في: {args.folder}")
        sys.exit(1)

    rows = []
    detail_mode = bool(args.ticker)

    for path in files:
        ticker = os.path.splitext(os.path.basename(path))[0]
        try:
            df = load_csv(path)
        except Exception as e:
            print(f"❌ {ticker}: {e}")
            continue

        matches = scan_dataframe(
            df, pct=args.pct, atr_mult=args.atr_mult,
            min_score=(0 if detail_mode else args.min_score),
            only_valid=not args.all,
        )
        if args.pattern:
            matches = [m for m in matches if m.pattern.lower() == args.pattern.lower()]

        if detail_mode:
            _print_detail(ticker, df, matches)
            return

        for m in matches:
            last_date = df["Date"].iloc[-1] if "Date" in df.columns else len(df)
            rows.append({
                "Ticker": ticker, "Pattern": m.pattern, "النمط": m.pattern_ar,
                "Dir": m.direction, "Final": m.final_score, "Struct": m.score,
                "Confirm": f"{sum(m.confirmations.values())}/{len(m.confirmations)}"
                           if m.confirmations else "-",
                "Forming": "نعم" if m.forming else "",
                "Note": "؛ ".join(m.notes)[:45],
                "LastDate": last_date,
            })

    if not rows:
        print("لا توجد أنماط مطابقة. جرّب --all أو خفّض --min-score.")
        return

    res = pd.DataFrame(rows).sort_values(["Final"], ascending=False).reset_index(drop=True)
    pd.set_option("display.unicode.east_asian_width", True)
    pd.set_option("display.max_colwidth", 40)
    print(f"\n📊 نتائج المسح — {len(files)} سهم، {len(res)} نمط مكتشف:\n")
    print(res.head(args.top).to_string(index=False))

    if args.csv_out:
        res.to_csv(args.csv_out, index=False, encoding="utf-8-sig")
        print(f"\n💾 حُفظت النتائج في: {args.csv_out}")


def _print_detail(ticker: str, df: pd.DataFrame, matches):
    print(f"\n{'='*60}\n🔎 تفاصيل: {ticker}  ({len(df)} شمعة)\n{'='*60}")
    if not matches:
        print("لا توجد أنماط مكتشفة بالعتبة الحالية.")
        return
    for m in matches[:8]:
        print(f"\n{m.summary()}")
        print(f"   النقاط (index): {m.points_idx}")
        print(f"   الأسعار:        {m.points_price}")
        print("   القوانين:")
        for k, v in m.rules.items():
            print(f"      {'✅' if v else '❌'} {k}")
        if m.fib:
            print("   فيبوناتشي:")
            for k, v in m.fib.items():
                print(f"      {k}: {v}")
        if m.confirmations:
            print(f"   تأكيدات الدقة ({sum(m.confirmations.values())}/{len(m.confirmations)}):")
            for k, v in m.confirmations.items():
                print(f"      {'✅' if v else '❌'} {k}")
        if m.targets:
            print("   الأهداف:")
            for k, v in m.targets.items():
                print(f"      🎯 {k} = {v}")
        if m.notes:
            print("   ملاحظات: " + " | ".join(m.notes))


if __name__ == "__main__":
    main()
