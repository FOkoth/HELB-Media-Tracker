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

# ---------- CSS: keep header dark gold, sidebar dark gold, nav items green (hover white/black) ----------
st.markdown(
    """
    <style>
    /* Ensure header (top navigation bar) is dark gold */
    header, header > div, header[data-testid="stHeader"] {
        background-color: #B8860B !important;
    }

    /* Make the entire sidebar / navigation pane dark gold */
    section[data-testid="stSidebar"] {
        background-color: #B8860B !important;
    }

    /* Navigation items (links for pages) — green background + white text */
    div[data-testid="stSidebarNav"] ul li a {
        background-color: #228B22 !important; /* green */
        color: white !important;
        border-radius: 6px;
        display: inline-block;
        padding: 6px 10px;
        margin: 6px 2px;
        text-decoration: none;
    }

    /* Hover / focus: white background and black text */
    div[data-testid="stSidebarNav"] ul li a:hover,
    div[data-testid="stSidebarNav"] ul li a:focus {
        background-color: white !important;
        color: black !important;
    }

    /* Sidebar labels/inputs should appear readable on dark gold */
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] .stTextInput, 
    section[data-testid="stSidebar"] .stSelectbox, 
    section[data-testid="stSidebar"] .stButton {
        color: white !important;
    }

    /* Mention card minor styling */
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
    # Load data from persistent local CSV (if present) else from the published Google Sheet CSV URL
    if os.path.exists(LOCAL_CSV):
        df = pd.read_csv(LOCAL_CSV)
    else:
        df = pd.read_csv(CSV_URL)

    # normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # ensure expected columns exist
    for col in ["title", "summary", "source", "tonality", "link", "published"]:
        if col not in df.columns:
            df[col] = ""

    # normalize tonality text
    df["tonality"] = df["tonality"].astype(str).str.strip().replace({"nan": ""})
    df.loc[df["tonality"] == "", "tonality"] = "Unknown"
    df["tonality"] = df["tonality"].str.capitalize()

    # parse published safely
    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    # try convert timezone to Nairobi if timezone-aware
    try:
        df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
    except Exception:
        # if naive or conversion fails, leave as-is (we'll format safely)
        pass

    # human-friendly date/time
    df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y").fillna("")
    df["TIME"] = df["published_parsed"].dt.strftime("%H:%M").fillna("")

    # YEAR as nullable integer then clean to string (no decimals)
    df["YEAR"] = df["published_parsed"].dt.year
    try:
        df["YEAR"] = df["YEAR"].astype("Int64")
        df["YEAR"] = df["YEAR"].astype(str).replace("<NA>", "")
    except Exception:
        # fallback: coerce to int when possible, else string
        df["YEAR"] = df["published_parsed"].dt.year.fillna("").apply(lambda x: str(int(x)) if pd.notna(x) else "")

    # MONTH (categorical ordered Jan->Dec)
    month_order = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    months = df["published_parsed"].dt.strftime("%B").fillna("")
    df["MONTH"] = pd.Categorical(months, categories=month_order, ordered=True)

    # QUARTER as Q1..Q4 (no year)
    quarter_series = df["published_parsed"].dt.quarter
    df["QUARTER"] = quarter_series.fillna("").apply(lambda x: f"Q{int(x)}" if pd.notna(x) else "")

    # Financial year (Jul-Jun)
    def compute_fin_year(dt):
        if pd.isna(dt):
            return ""
        y = dt.year
        m = dt.month
        return f"{y}/{y+1}" if m >= 7 else f"{y-1}/{y}"
    df["FIN_YEAR"] = df["published_parsed"].apply(lambda x: compute_fin_year(x) if not pd.isna(x) else "")

    # ensure text columns are strings
    for col in ["title", "summary", "source", "link"]:
        df[col] = df[col].fillna("").astype(str)

    # rename for UI
    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)

    # ensure additional columns exist post-rename
    for col in ["DATE", "TIME", "YEAR", "MONTH", "QUARTER", "FIN_YEAR", "published_parsed"]:
        if col not in df.columns:
            df[col] = ""

    return df

# ---------- HELPERS ----------
def safe_sort_key(val):
    # sort numeric strings as numbers, "2024/2025" by first year else lexicographic
    try:
        if isinstance(val, str) and val.isdigit():
            return (0, int(val))
        if isinstance(val, str) and "/" in val and val.split("/")[0].isdigit():
            return (0, int(val.split("/")[0]))
    except Exception:
        pass
    return (1, str(val).lower())

def make_options_from_series(series):
    # create unique non-empty string options sorted sensibly
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

# ensure predictable 0..n-1 index for session mapping
df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

# tonality map persistence
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# color codes (neutral text will be white)
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f",
    "Unknown": "#808080"
}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")

# Tonality options
tonality_opts = make_options_from_series(df["TONALITY"])
tonality_filter = st.sidebar.selectbox("Filter by Tonality", tonality_opts)

# Financial year options
fin_year_opts = make_options_from_series(df["FIN_YEAR"])
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", fin_year_opts)

# Quarter options (Q1..Q4)
quarter_opts = make_options_from_series(df["QUARTER"])
quarter_filter = st.sidebar.selectbox("Filter by Quarter", quarter_opts)

# Year options (clean ints as strings)
year_opts = make_options_from_series(df["YEAR"])
year_filter = st.sidebar.selectbox("Filter by Year", year_opts)

# Months: ensure Jan->Dec order; show only months present
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
            # refresh session copy
            st.session_state["mentions_df"] = load_data()
            df = st.session_state["mentions_df"]
            df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)
            df_filtered = df[mask]
        except Exception as e:
            st.sidebar.error(f"Failed to save CSV: {e}")

# ---------- TITLE BAR with count ----------
st.markdown(
    f"""
    <div style="background-color:#B8860B; color:white; padding:12px; border-radius:6px; margin-bottom:16px;">
        <strong>📰 Mentions — Media Coverage</strong> &nbsp;&nbsp; <span style="opacity:0.95">({len(df_filtered)} results)</span>
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
        # neutral text should be white as requested
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
