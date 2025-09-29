# pages/Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
CSV_URL = "https://docs.google.com/spreadsheets/d/10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ/export?format=csv"
LOCAL_CSV = "persistent_mentions.csv"  # File to save updates
EDITOR_PASSWORD = "MyHardSecret123"

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title="HELB Mentions",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- CSS ----------
st.markdown(
    """
    <style>
    /* Header (dark gold) */
    header, header > div, header[data-testid="stHeader"] {
        background-color: #B8860B !important;
    }

    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #B8860B !important;
    }

    /* Sidebar nav items: green */
    div[data-testid="stSidebarNav"] ul li a {
        background-color: #228B22 !important; /* green */
        color: white !important;
        border-radius: 6px;
        display: inline-block;
        padding: 6px 10px;
        margin: 6px 2px;
        text-decoration: none;
    }

    /* Hover effect: white background + black text */
    div[data-testid="stSidebarNav"] ul li a:hover,
    div[data-testid="stSidebarNav"] ul li a:focus {
        background-color: white !important;
        color: black !important;
    }

    /* Sidebar labels */
    section[data-testid="stSidebar"] label {
        color: white !important;
    }

    /* Mention cards */
    .mention-card { padding: 14px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- AUTH ----------
password = st.sidebar.text_input("Enter edit password", type="password")
is_editor = password == EDITOR_PASSWORD
if is_editor:
    st.sidebar.success("Editor mode ✅")
else:
    st.sidebar.info("Read-only mode 🔒")

# ---------- DATA LOADING ----------
@st.cache_data
def load_data():
    if os.path.exists(LOCAL_CSV):
        df = pd.read_csv(LOCAL_CSV)
    else:
        df = pd.read_csv(CSV_URL)

    df.columns = [c.strip().lower() for c in df.columns]

    for col in ["title", "summary", "source", "tonality", "link", "published"]:
        if col not in df.columns:
            df[col] = ""

    df["tonality"] = df["tonality"].astype(str).str.strip().replace({"nan": ""})
    df.loc[df["tonality"] == "", "tonality"] = "Unknown"
    df["tonality"] = df["tonality"].str.capitalize()

    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    try:
        df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
    except Exception:
        pass

    df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y").fillna("")
    df["TIME"] = df["published_parsed"].dt.strftime("%H:%M").fillna("")

    df["YEAR"] = df["published_parsed"].dt.year
    try:
        df["YEAR"] = df["YEAR"].astype("Int64").astype(str).replace("<NA>", "")
    except Exception:
        df["YEAR"] = df["published_parsed"].dt.year.fillna("").apply(lambda x: str(int(x)) if pd.notna(x) else "")

    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    months = df["published_parsed"].dt.strftime("%B").fillna("")
    df["MONTH"] = pd.Categorical(months, categories=month_order, ordered=True)

    df["QUARTER"] = df["published_parsed"].dt.quarter.fillna("").apply(
        lambda x: f"Q{int(x)}" if pd.notna(x) and x != "" else ""
    )

    def compute_fin_year(dt):
        if pd.isna(dt): return ""
        y, m = dt.year, dt.month
        return f"{y}/{y+1}" if m >= 7 else f"{y-1}/{y}"
    df["FIN_YEAR"] = df["published_parsed"].apply(lambda x: compute_fin_year(x) if not pd.isna(x) else "")

    for col in ["title", "summary", "source", "link"]:
        df[col] = df[col].fillna("").astype(str)

    rename_map = {"title": "TITLE","summary": "SUMMARY","source": "SOURCE","tonality": "TONALITY","link": "LINK"}
    df = df.rename(columns=rename_map)

    for col in ["DATE","TIME","YEAR","MONTH","QUARTER","FIN_YEAR","published_parsed"]:
        if col not in df.columns:
            df[col] = ""

    return df

# ---------- HELPERS ----------
def safe_sort_key(val):
    try:
        if isinstance(val, str) and val.isdigit():
            return (0, int(val))
        if isinstance(val, str) and "/" in val and val.split("/")[0].isdigit():
            return (0, int(val.split("/")[0]))
    except Exception: pass
    return (1, str(val).lower())

def make_options_from_series(series):
    vals = []
    for v in pd.Series(series).dropna().unique():
        s = str(v).strip()
        if s == "" or s.lower() == "nan": continue
        vals.append(s)
    unique = sorted(set(vals), key=safe_sort_key)
    return ["All"] + unique

# ---------- LOAD INTO SESSION ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()
df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available."); st.stop()
df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i,"TONALITY"] for i in df.index}

COLORS = {"Positive":"#3b8132","Neutral":"#6E6F71","Negative":"#d1001f","Unknown":"#808080"}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")

tonality_filter = st.sidebar.selectbox("Filter by Tonality", make_options_from_series(df["TONALITY"]))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", make_options_from_series(df["FIN_YEAR"]))
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All","Q1","Q2","Q3","Q4"])
year_filter = st.sidebar.selectbox("Filter by Year", make_options_from_series(df["YEAR"]))

month_order = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]
present_months = [m for m in month_order if m in list(df["MONTH"].astype(str).unique())]
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + present_months)

mask = pd.Series([True]*len(df))
if tonality_filter!="All": mask &= df["TONALITY"]==tonality_filter
if fin_year_filter!="All": mask &= df["FIN_YEAR"]==fin_year_filter
if quarter_filter!="All": mask &= df["QUARTER"]==quarter_filter
if year_filter!="All": mask &= df["YEAR"]==year_filter
if month_filter!="All": mask &= df["MONTH"].astype(str)==month_filter

df_filtered = df[mask]

# ---------- DISPLAY ----------
st.markdown(
    f"""
    <div style="background-color:#B8860B; color:white; padding:12px; border-radius:6px; margin-bottom:16px;">
        <strong>📰 Mentions — Media Coverage</strong> &nbsp;&nbsp;
        <span style="opacity:0.95">({len(df_filtered)} results)</span>
    </div>
    """, unsafe_allow_html=True
)

if df_filtered.empty:
    st.info("No mentions for the selected filters.")
else:
    for display_pos, idx in enumerate(df_filtered.index, start=1):
        row = df_filtered.loc[idx]
        tonality = st.session_state["tonality_map"].get(idx, row["TONALITY"])
        bg_color = COLORS.get(tonality, "#ffffff")
        text_color = "#ffffff"  # neutral + all text white

        st.markdown(
            f"""
            <div class="mention-card" style="background-color:{bg_color}; color:{text_color};">
                <div style="font-size:13px; opacity:0.95;"><b>{display_pos}. {row['DATE']} {row['TIME']}</b> — <i>{row['SOURCE']}</i></div>
                <div style="font-weight:700; margin-top:6px;">{row['TITLE']}</div>
                <div style="margin-top:6px;">{row['SUMMARY']}</div>
                <div style="margin-top:8px;"><b>Tonality:</b> {tonality}</div>
            </div>
            """, unsafe_allow_html=True
        )
        if row["LINK"].startswith("http"):
            st.markdown(f"[🔗 Read Full Story]({row['LINK']})")
        st.markdown("---")

# ---------- EXPORT ----------
st.subheader("Export Updated Mentions")
export_df = df_filtered.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, export_df.at[i,"TONALITY"]) for i in export_df.index]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Download Mentions CSV", data=csv_bytes, file_name="updated_mentions.csv", mime="text/csv")
