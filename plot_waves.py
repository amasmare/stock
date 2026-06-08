"""
رسم الموجات — Wave Chart
========================
يرسم شارت السهم مع تأشير موجات أعلى نمط مكتشف + الأهداف.

الاستخدام:
    python plot_waves.py ./data --ticker AAPL
    python plot_waves.py ./data --ticker LRCX --pattern Impulse --out lrcx.png
"""
import argparse
import os

import matplotlib
matplotlib.use("Agg")  # حفظ كملف بدون واجهة
import matplotlib.pyplot as plt

from elliott_waves import scan_dataframe, load_csv, compute_atr, zigzag_pivots

MOTIVE_LABELS = ["0", "1", "2", "3", "4", "5"]
CORR4_LABELS = ["0", "A", "B", "C"]
CORR5_LABELS = ["0", "A", "B", "C", "D", "E"]


def labels_for(m):
    if m.category == "Motive":
        return MOTIVE_LABELS
    return CORR5_LABELS if len(m.points_idx) == 6 else CORR4_LABELS


def main():
    ap = argparse.ArgumentParser(description="رسم موجات إليوت")
    ap.add_argument("folder")
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--pattern", help="نوع محدد (Impulse/Zigzag/...)")
    ap.add_argument("--out", help="اسم ملف الصورة (افتراضي <ticker>_wave.png)")
    args = ap.parse_args()

    path = os.path.join(args.folder, f"{args.ticker}.csv")
    if not os.path.exists(path):
        print(f"⚠️ غير موجود: {path}")
        return
    df = load_csv(path)
    matches = scan_dataframe(df, min_score=0)
    if args.pattern:
        matches = [m for m in matches if m.pattern.lower() == args.pattern.lower()]
    if not matches:
        print("لا توجد أنماط لرسمها.")
        return
    m = matches[0]

    # السعر + كل النقاط المحورية بخط رمادي خفيف
    atr = compute_atr(df).iloc[-1]
    last = df["Close"].iloc[-1]
    pct = max(0.02, min(0.15, float(1.5 * atr / last))) if last else 0.05
    piv = zigzag_pivots(df["High"].values, df["Low"].values, pct)

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df.index, df["Close"], color="#888", lw=0.8, alpha=0.6, label="Close")
    if piv:
        ax.plot([p[0] for p in piv], [p[1] for p in piv],
                color="#bbb", lw=0.8, alpha=0.5, zorder=1)

    # موجات النمط المختار
    xs, ys = m.points_idx, m.points_price
    color = "#1a9641" if m.direction == "bullish" else ("#d7191c" if m.direction == "bearish" else "#2b83ba")
    ax.plot(xs, ys, color=color, lw=2.4, marker="o", ms=7, zorder=3)
    for x, y, lab in zip(xs, ys, labels_for(m)):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=13, fontweight="bold", color=color)

    # خطوط الأهداف
    for name, tgt in (m.targets or {}).items():
        ax.axhline(tgt, ls="--", lw=1, color=color, alpha=0.6)
        ax.text(df.index[-1], tgt, f" {name}={tgt}", va="center", fontsize=8, color=color)

    title = (f"{args.ticker} — {m.pattern} ({m.direction}) | "
             f"struct={m.score:.0f} final={m.final_score:.0f} "
             f"confirm={sum(m.confirmations.values())}/{len(m.confirmations)}")
    ax.set_title(title, fontsize=12)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()

    out = args.out or f"{args.ticker}_wave.png"
    fig.savefig(out, dpi=120)
    print(f"🖼️  حُفظت الصورة: {out}")
    print(f"    النمط: {m.summary()}")
    if m.targets:
        print("    الأهداف: " + ", ".join(f"{k}={v}" for k, v in m.targets.items()))


if __name__ == "__main__":
    main()
