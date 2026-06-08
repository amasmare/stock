"""
مُنزّل الأسعار التاريخية — Price Fetcher
========================================
يقرأ قائمة الرموز (Symbol,Name,Sector,Market_Cap) وينزّل تاريخ OHLC لكل سهم
عبر yfinance ويحفظه في مجلد ./data كملف CSV لكل سهم — جاهز لـ scan.py

الاستخدام:
    python fetch.py "tickers 2604.csv" --limit 100 --period 2y
    python fetch.py "tickers 2604.csv" --sector Technology --min-cap 10 --limit 50
    python fetch.py "tickers 2604.csv" --symbols AAPL,MSFT,NVDA

ثم:
    python scan.py ./data --min-score 65
"""
import argparse
import os
import re
import time

import pandas as pd
import yfinance as yf


def parse_cap(s):
    """يحوّل '$38.3B' / '$910M' / '$1.2T' إلى رقم بالمليار."""
    if not isinstance(s, str):
        return 0.0
    m = re.search(r"([\d.]+)\s*([TBM]?)", s.replace(",", "").upper())
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2)
    return val * {"T": 1000, "B": 1, "M": 0.001, "": 0.001}.get(unit, 1)


def main():
    ap = argparse.ArgumentParser(description="تنزيل أسعار الأسهم التاريخية")
    ap.add_argument("tickers_file", help="ملف الرموز (Symbol,Name,Sector,Market_Cap)")
    ap.add_argument("--out", default="data", help="مجلد الحفظ (افتراضي data)")
    ap.add_argument("--period", default="2y", help="المدة: 1y/2y/5y/max")
    ap.add_argument("--interval", default="1d", help="الفريم: 1d/1wk")
    ap.add_argument("--limit", type=int, default=100, help="أقصى عدد أسهم (افتراضي 100)")
    ap.add_argument("--sector", help="فلترة بقطاع معيّن (مثل Technology)")
    ap.add_argument("--min-cap", type=float, default=0, help="أدنى قيمة سوقية بالمليار $")
    ap.add_argument("--symbols", help="رموز محددة مفصولة بفاصلة (تتجاهل الفلاتر)")
    ap.add_argument("--chunk", type=int, default=80, help="حجم الدفعة في كل تنزيل")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # تحديد قائمة الرموز
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        meta = pd.read_csv(args.tickers_file)
        meta.columns = [c.strip() for c in meta.columns]
        if "Market_Cap" in meta.columns:
            meta["_cap"] = meta["Market_Cap"].apply(parse_cap)
        else:
            meta["_cap"] = 0
        if args.sector and "Sector" in meta.columns:
            meta = meta[meta["Sector"].str.contains(args.sector, case=False, na=False)]
        if args.min_cap:
            meta = meta[meta["_cap"] >= args.min_cap]
        meta = meta.sort_values("_cap", ascending=False)
        symbols = meta["Symbol"].astype(str).str.strip().head(args.limit).tolist()

    print(f"📥 سيتم تنزيل {len(symbols)} سهم | period={args.period} interval={args.interval}")
    saved, failed = 0, []

    for i in range(0, len(symbols), args.chunk):
        batch = symbols[i:i + args.chunk]
        print(f"   دفعة {i//args.chunk + 1}: {len(batch)} سهم ...", flush=True)
        try:
            data = yf.download(batch, period=args.period, interval=args.interval,
                               group_by="ticker", auto_adjust=True, progress=False,
                               threads=True)
        except Exception as e:
            print(f"   ⚠️ فشلت الدفعة: {e}")
            failed += batch
            continue

        for sym in batch:
            try:
                df = data[sym] if len(batch) > 1 else data
                df = df.dropna(how="all")
                if df is None or len(df) < 30:
                    failed.append(sym)
                    continue
                out = df.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
                safe = sym.replace("/", "-").replace(".", "-")
                out.to_csv(os.path.join(args.out, f"{safe}.csv"), index=False)
                saved += 1
            except Exception:
                failed.append(sym)
        time.sleep(0.5)  # تهدئة بسيطة لتجنّب الحظر

    print(f"\n✅ حُفظ {saved} سهم في ./{args.out}")
    if failed:
        print(f"⚠️ فشل {len(failed)} رمز (قد يكون غير متاح): {', '.join(failed[:15])}"
              + (" ..." if len(failed) > 15 else ""))
    print(f"\nالخطوة التالية:\n    python scan.py ./{args.out} --min-score 65")


if __name__ == "__main__":
    main()
