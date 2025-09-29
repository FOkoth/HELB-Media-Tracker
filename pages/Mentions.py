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
    header, header > div, header[data-testid="stHeader"] {
        background-color: #B8860B !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #B8860B !important;
    }
    div[data-testid="stSidebarNav"] ul li a {
        background-color: #228B22 !important;
        color: white !important;
        border-radius: 6px;
        display: inline-block;
        padding: 6px 10px;
        margin: 6px 2px;
        text-decoration: none;
    }
    div[data-testid="stSidebarNav"] ul li a:hover,
    div[data-testid="stSidebarNav"] ul li a:focus {
        background-color: white !important;
        color: black !important;
    }
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] .stTextInput, 
    section[data-testid="stSidebar"] .stSelectbox, 
    section[data-testid="stSidebar"] .stButton {
        color: white !important;
    }
    .mention-card { padding: 14px; border-radius: 8px; margin-bottom: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- AUTH / EDIT MODE ----------
password = st.sidebar.text_input("Enter edit password", type="password")
is_editor = password == EDITOR_PASSWORD
if is_editor:
    st.sidebar.success("Editor mode ✅")
else:
    st.sidebar.info("Read-only mode 🔒")

# ---------- DATA LOADING ----------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_URL)
    try:
        df.to_csv(LOCAL_CSV, index=False)
    except Exception:
        pass

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
        df["YEAR"] = df["YEAR"].astype("Int64")
        df["YEAR"] = df["YEAR"].astype(str).replace("<NA>", "")
    except Exception:
        df["YEAR"] = df["published_parsed"].dt.year.fillna("").apply(lambda x: str(int(x)) if pd.notna(x) else "")

    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    months = df["published_parsed"].dt.strftime("%B").fillna("")
    df["MONTH"] = pd.Categorical(months, categories=month_order, ordered=True)

    # ---------- FIXED QUARTER (FY Jul–Jun) ----------
    def get_fy_quarter(dt):
        if pd.isna(dt):
            return ""
        m = dt.month
        if m in [7, 8, 9]:
            return "Q1"
        elif m in [10, 11, 12]:
            return "Q2"
        elif m in [1, 2, 3]:
            return "Q3"
        elif m in [4, 5, 6]:
            return "Q4"
        return ""

    df["QUARTER"] = df["published_parsed"].apply(get_fy_quarter)

    # Financial year (Jul–Jun)
    def compute_fin_year(dt):
        if pd.isna(dt):
            return ""
        y = dt.year
        m = dt.month
        return f"{y}/{y+1}" if m >= 7 else f"{y-1}/{y}"
    df["FIN_YEAR"] = df["published_parsed"].apply(lambda x: compute_fin_year(x) if not pd.isna(x) else "")

    for col in ["title", "summary", "source", "link"]:
        df[col] = df[col].fillna("").astype(str)

    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)

    for col in ["DATE", "TIME", "YEAR", "MONTH", "QUARTER", "FIN_YEAR", "published_parsed"]:
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
    except Exception:
        pass
    return (1, str(val).lower())

def make_options_from_series(series):
    vals = []
    for v in pd.Series(series).dropna().unique():
        s = str(v).strip()
        if s == "" or s.lower() == "nan":
            continue
        vals.append(s)
    unique = sorted(set(vals), key=safe_sort_key)
    return ["All"] + unique

# ---------- LOAD INTO SESSION ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()

df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available.")
    st.stop()

df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f",
    "Unknown": "#808080"
}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")
tonality_opts = make_options_from_series(df["TONALITY"])
tonality_filter = st.sidebar.selectbox("Filter by Tonality", tonality_opts)

fin_year_opts = make_options_from_series(df["FIN_YEAR"])
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", fin_year_opts)

quarter_opts = make_options_from_series(df["QUARTER"])
quarter_filter = st.sidebar.selectbox("Filter by Quarter", quarter_opts)

year_opts = make_options_from_series(df["YEAR"])
year_filter = st.sidebar.selectbox("Filter by Year", year_opts)

month_order = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
present_months = [m for m in month_order if m in list(df["MONTH"].astype(str).unique())]
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + present_months)

# ---------- APPLY FILTERS ----------
mask = pd.Series([True] * len(df))
if tonality_filter != "All":
    mask &= df["TONALITY"] == tonality_filter
if fin_year_filter != "All":
    mask &= df["FIN_YEAR"] == fin_year_filter
if quarter_filter != "All":
    mask &= df["QUARTER"] == quarter_filter
if year_filter != "All":
    mask &= df["YEAR"] == year_filter
if month_filter != "All":
    mask &= df["MONTH"].astype(str) == month_filter

df_filtered = df[mask]

# ---------- EDITOR PANEL ----------
if is_editor:
    st.sidebar.subheader("Edit Tonality")
    edited_values = {}
    st.sidebar.markdown('<div style="max-height:600px; overflow-y:auto; padding-right:5px;">', unsafe_allow_html=True)
    for i in df.index:
        current = st.session_state["tonality_map"].get(i, df.at[i, "TONALITY"])
        new_val = st.selectbox(
            f"{i+1}. {df.at[i, 'TITLE'][:60]}...",
            options=["Positive", "Neutral", "Negative", "Unknown"],
            index=["Positive", "Neutral", "Negative", "Unknown"].index(current) if current in ["Positive","Neutral","Negative","Unknown"] else 3,
            key=f"tonality_{i}"
        )
        edited_values[i] = new_val
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    if st.sidebar.button("💾 Save Tonality Updates"):
        for idx, val in edited_values.items():
            st.session_state["tonality_map"][idx] = val
        updated_df = df.copy()
        updated_df["TONALITY"] = [st.session_state["tonality_map"].get(i, updated_df.at[i, "TONALITY"]) for i in updated_df.index]
        try:
            updated_df.to_csv(LOCAL_CSV, index=False)
            st.sidebar.success("Tonality changes applied and saved!")
            st.session_state["mentions_df"] = load_data()
            df = st.session_state["mentions_df"]
            df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)
            df_filtered = df[mask]
        except Exception as e:
            st.sidebar.error(f"Failed to save CSV: {e}")

# ---------- TITLE BAR ----------
st.markdown(
    f"""
    <div style="background-color:#B8860B; color:white; padding:12px; border-radius:6px; margin-bottom:16px;">
        <strong>📰 MENTIONS — MEDIA COVERAGE</strong> &nbsp;&nbsp; <span style="opacity:0.95">({len(df_filtered)} results)</span>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------- DISPLAY MENTIONS ----------
if df_filtered.empty:
    st.info("No mentions for the selected filters.")
else:
    for display_pos, idx in enumerate(df_filtered.index, start=1):
        row = df_filtered.loc[idx]
        tonality = st.session_state["tonality_map"].get(idx, row["TONALITY"])
        bg_color = COLORS.get(tonality, "#ffffff")
        text_color = "#ffffff"

        st.markdown(
            f"""
            <div class="mention-card" style="background-color:{bg_color}; color:{text_color};">
                <div style="font-size:13px; opacity:0.95;"><b>{display_pos}. {row['DATE']} {row['TIME']}</b> — <i>{row['SOURCE']}</i></div>
                <div style="font-weight:700; margin-top:6px;">{row['TITLE']}</div>
                <div style="margin-top:6px;">{row['SUMMARY']}</div>
                <div style="margin-top:8px;"><b>Tonality:</b> {tonality}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if row["LINK"].startswith("http"):
            st.markdown(f"[🔗 Read Full Story]({row['LINK']})")
        st.markdown("---")

# ---------- DOWNLOAD UPDATED CSV ----------
st.subheader("Export Updated Mentions")
export_df = df_filtered.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, export_df.at[i, "TONALITY"]) for i in export_df.index]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
