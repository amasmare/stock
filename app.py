"""
Elliott Wave Scanner — موقع الويب (Streamlit)
=============================================
موقع تفاعلي لمسح أنماط إليوت الموجية على الأسهم.
التشغيل محلياً:   streamlit run app.py
النشر:            ارفع المجلد على GitHub ثم انشره على share.streamlit.io
"""
import glob
import os

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from elliott_waves import scan_dataframe, load_csv, compute_atr, zigzag_pivots
from backtest import simulate_trade

st.set_page_config(page_title="ماسح إليوت الموجي", page_icon="🌊", layout="wide")

# دعم عرض عربي بسيط (محاذاة لليمين)
st.markdown("""<style>
.main, .stMarkdown, .stDataFrame { direction: rtl; }
h1,h2,h3 { text-align: right; }
</style>""", unsafe_allow_html=True)

st.title("🌊 ماسح أنماط إليوت الموجية")
st.caption("الأنماط الخمسة: Impulse دافعة · Diagonal قطرية · Zigzag زجزاج · Flat فلات · Triangle مثلث")

MOTIVE_LABELS = ["0", "1", "2", "3", "4", "5"]
CORR4 = ["0", "A", "B", "C"]
CORR5 = ["0", "A", "B", "C", "D", "E"]


def labels_for(m):
    if m.category == "Motive":
        return MOTIVE_LABELS
    return CORR5 if len(m.points_idx) == 6 else CORR4


def make_chart(df, m):
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df.index, df["Close"], color="#999", lw=0.8, alpha=0.6, label="Close")
    atr = compute_atr(df).iloc[-1]
    last = df["Close"].iloc[-1]
    pct = max(0.02, min(0.15, float(1.5 * atr / last))) if last else 0.05
    piv = zigzag_pivots(df["High"].values, df["Low"].values, pct)
    if piv:
        ax.plot([p[0] for p in piv], [p[1] for p in piv], color="#ccc", lw=0.8, alpha=0.5)
    color = "#1a9641" if m.direction == "bullish" else ("#d7191c" if m.direction == "bearish" else "#2b83ba")
    ax.plot(m.points_idx, m.points_price, color=color, lw=2.4, marker="o", ms=7)
    for x, y, lab in zip(m.points_idx, m.points_price, labels_for(m)):
        ax.annotate(lab, (x, y), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=12, fontweight="bold", color=color)
    for name, tgt in (m.targets or {}).items():
        ax.axhline(tgt, ls="--", lw=1, color=color, alpha=0.6)
        ax.text(df.index[-1], tgt, f" {name}={tgt}", va="center", fontsize=7, color=color)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


# ───────────────────────── مصدر البيانات (الشريط الجانبي) ─────────────────────────
st.sidebar.header("📂 مصدر البيانات")
source = st.sidebar.radio("اختر", ["رفع ملفات أسعار CSV", "مجلد data المحلي", "تنزيل من قائمة رموز"])

if "data" not in st.session_state:
    st.session_state.data = {}

if source == "رفع ملفات أسعار CSV":
    ups = st.sidebar.file_uploader("ملفات OHLC (Date,Open,High,Low,Close,Volume)",
                                   type="csv", accept_multiple_files=True)
    if ups:
        d = {}
        for f in ups:
            name = os.path.splitext(f.name)[0]
            try:
                d[name] = load_csv(f)
            except Exception as e:
                st.sidebar.error(f"{name}: {e}")
        st.session_state.data = d
        st.sidebar.success(f"حُمّل {len(d)} سهم")

elif source == "مجلد data المحلي":
    folder = st.sidebar.text_input("مسار المجلد", "data")
    if st.sidebar.button("تحميل المجلد"):
        d = {}
        for p in sorted(glob.glob(os.path.join(folder, "*.csv"))):
            name = os.path.splitext(os.path.basename(p))[0]
            try:
                d[name] = load_csv(p)
            except Exception:
                pass
        st.session_state.data = d
        st.sidebar.success(f"حُمّل {len(d)} سهم")

else:  # تنزيل
    tick_file = st.sidebar.file_uploader("قائمة الرموز (Symbol,...)", type="csv")
    limit = st.sidebar.number_input("عدد الأسهم", 1, 500, 30)
    period = st.sidebar.selectbox("المدة", ["1y", "2y", "5y", "max"], index=1)
    if tick_file and st.sidebar.button("تنزيل الأسعار"):
        try:
            import yfinance as yf
            meta = pd.read_csv(tick_file)
            meta.columns = [c.strip() for c in meta.columns]
            syms = meta["Symbol"].astype(str).str.strip().head(int(limit)).tolist()
            with st.spinner(f"تنزيل {len(syms)} سهم..."):
                raw = yf.download(syms, period=period, group_by="ticker",
                                  auto_adjust=True, progress=False)
            d = {}
            for s in syms:
                try:
                    sub = raw[s] if len(syms) > 1 else raw
                    sub = sub.dropna(how="all").reset_index()
                    if len(sub) >= 30:
                        d[s] = sub
                except Exception:
                    pass
            st.session_state.data = d
            st.sidebar.success(f"نُزّل {len(d)} سهم")
        except Exception as e:
            st.sidebar.error(f"خطأ: {e}")

data = st.session_state.data

# ───────────────────────── إعدادات المسح ─────────────────────────
st.sidebar.header("⚙️ الإعدادات")
min_score = st.sidebar.slider("أدنى درجة نهائية", 0, 100, 60)
pat_filter = st.sidebar.selectbox("النمط", ["الكل", "Impulse", "Diagonal", "Zigzag", "Flat", "Triangle"])
atr_mult = st.sidebar.slider("حساسية ZigZag (ATR×)", 0.5, 3.0, 1.5, 0.1)
only_valid = st.sidebar.checkbox("القوانين المكتملة فقط", True)

if not data:
    st.info("👉 اختر مصدر بيانات من الشريط الجانبي للبدء. "
            "صيغة ملف الأسعار: أعمدة Date,Open,High,Low,Close,Volume (كل ملف = سهم).")
    st.stop()


def run_scan(df):
    ms = scan_dataframe(df, atr_mult=atr_mult, min_score=min_score, only_valid=only_valid)
    if pat_filter != "الكل":
        ms = [m for m in ms if m.pattern == pat_filter]
    return ms


tab1, tab2, tab3 = st.tabs(["🔎 الماسح", "📈 التفاصيل والرسم", "🧪 Backtest"])

# ── تبويب الماسح ──
with tab1:
    rows = []
    for tk, df in data.items():
        for m in run_scan(df):
            rows.append({
                "السهم": tk, "Pattern": m.pattern, "النمط": m.pattern_ar,
                "الاتجاه": m.direction, "النهائي": m.final_score, "البنية": m.score,
                "التأكيدات": f"{sum(m.confirmations.values())}/{len(m.confirmations)}" if m.confirmations else "-",
                "تكوّن": "نعم" if m.forming else "",
            })
    if rows:
        res = pd.DataFrame(rows).sort_values("النهائي", ascending=False).reset_index(drop=True)
        st.subheader(f"النتائج: {len(res)} نمط في {len(data)} سهم")
        st.dataframe(res, use_container_width=True, height=500)
        st.download_button("⬇️ تحميل النتائج CSV",
                           res.to_csv(index=False).encode("utf-8-sig"),
                           "results.csv", "text/csv")
    else:
        st.warning("لا توجد أنماط مطابقة. خفّض الدرجة أو ألغِ 'القوانين المكتملة فقط'.")

# ── تبويب التفاصيل ──
with tab2:
    tk = st.selectbox("اختر السهم", list(data.keys()))
    df = data[tk]
    ms = scan_dataframe(df, atr_mult=atr_mult, min_score=0, only_valid=False)
    if pat_filter != "الكل":
        ms = [m for m in ms if m.pattern == pat_filter]
    if not ms:
        st.warning("لا توجد أنماط.")
    else:
        opts = [f"{i+1}. {m.pattern} ({m.direction}) — نهائي {m.final_score}" for i, m in enumerate(ms[:15])]
        choice = st.selectbox("النمط المكتشف", range(len(opts)), format_func=lambda i: opts[i])
        m = ms[choice]
        c1, c2 = st.columns([3, 2])
        with c1:
            st.pyplot(make_chart(df, m))
        with c2:
            st.metric("الدرجة النهائية", m.final_score, f"بنية {m.score}")
            st.write("**القوانين:**")
            for k, v in m.rules.items():
                st.write(f"{'✅' if v else '❌'} {k}")
            if m.confirmations:
                st.write(f"**تأكيدات الدقة ({sum(m.confirmations.values())}/{len(m.confirmations)}):**")
                for k, v in m.confirmations.items():
                    st.write(f"{'✅' if v else '❌'} {k}")
            if m.targets:
                st.write("**الأهداف 🎯:**")
                for k, v in m.targets.items():
                    st.write(f"{k} = **{v}**")
            if m.fib:
                with st.expander("نسب فيبوناتشي"):
                    st.json({k: str(v) for k, v in m.fib.items()})

# ── تبويب Backtest ──
with tab3:
    st.write("قياس جدوى الأنماط تاريخياً على الأسهم المحمّلة.")
    cc1, cc2, cc3 = st.columns(3)
    rr = cc1.slider("نسبة الهدف/المخاطرة (R)", 1.0, 4.0, 2.0, 0.5)
    max_hold = cc2.slider("أقصى أيام للصفقة", 10, 80, 40, 5)
    min_struct = cc3.slider("أدنى درجة بنية", 0, 100, 55)
    if st.button("▶️ تشغيل Backtest"):
        trades = []
        prog = st.progress(0.0)
        items = list(data.items())
        for i, (tk, df) in enumerate(items):
            for m in scan_dataframe(df, recent_windows=None, only_valid=True,
                                    min_score=min_struct, confirm=True):
                if m.forming:
                    continue
                r = simulate_trade(df, m, rr=rr, max_hold=max_hold)
                if r:
                    trades.append({"السهم": tk, "Pattern": m.pattern,
                                   "النتيجة": r[0], "R": r[1]})
            prog.progress((i + 1) / len(items))
        if trades:
            t = pd.DataFrame(trades)
            def agg(g):
                w = (g["النتيجة"] == "win").sum(); l = (g["النتيجة"] == "loss").sum()
                dec = w + l
                return pd.Series({"صفقات": len(g), "فوز%": round(100*w/dec, 1) if dec else 0,
                                  "متوسط R": round(g["R"].mean(), 2), "إجمالي R": round(g["R"].sum(), 1)})
            summary = t.groupby("Pattern").apply(agg, include_groups=False).sort_values("إجمالي R", ascending=False)
            st.subheader(f"النتيجة: {len(t)} صفقة")
            st.dataframe(summary, use_container_width=True)
            tot_dec = (t["النتيجة"].isin(["win", "loss"])).sum()
            tot_w = (t["النتيجة"] == "win").sum()
            st.success(f"الإجمالي — فوز {round(100*tot_w/tot_dec,1) if tot_dec else 0}% | "
                       f"إجمالي R = {round(t['R'].sum(),1)}")
        else:
            st.warning("لا توجد صفقات كافية.")
