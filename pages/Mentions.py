# pages/Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
CSV_URL = "https://docs.google.com/spreadsheets/d/10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ/export?format=csv"
LOCAL_CSV = "persistent_mentions.csv"
EDITOR_PASSWORD = "MyHardSecret123"

# ---------- PAGE STYLE ----------
st.markdown("""
    <style>
        /* Top title bar */
        .title-bar {
            background-color: #b8860b; /* dark gold */
            padding: 15px;
            border-radius: 8px;
            color: white;
            font-size: 22px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20px;
        }

        /* Sidebar styling - dark gold background */
        section[data-testid="stSidebar"] {
            background-color: #b8860b;
        }

        /* Selectbox wrapper */
        section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
            background-color: #006400 !important; /* green */
            color: white !important;
            border-radius: 6px;
            padding-left: 6px;
        }

        /* Dropdown text */
        section[data-testid="stSidebar"] .stSelectbox span {
            color: white !important;
        }

        /* Hover effect */
        section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"]:hover {
            background-color: white !important;
            color: black !important;
        }
        section[data-testid="stSidebar"] .stSelectbox span:hover {
            color: black !important;
        }

        /* Card style for mentions */
        .mention-card {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

# ---------- PASSWORD ----------
password = st.sidebar.text_input("Enter edit password", type="password")
is_editor = password == EDITOR_PASSWORD
if is_editor:
    st.sidebar.success("Editor mode ✅")
else:
    st.sidebar.info("Read-only mode 🔒")

# ---------- LOAD DATA ----------
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

    # Year as int
    df["YEAR"] = df["published_parsed"].dt.year.fillna("").astype("Int64").astype(str)

    # Month
    df["MONTH"] = df["published_parsed"].dt.strftime("%B").fillna("")

    # Quarter (Q1, Q2, etc.)
    df["QUARTER"] = df["published_parsed"].dt.quarter.fillna("").apply(
        lambda x: f"Q{int(x)}" if str(x).isdigit() else ""
    )

    # Financial year
    def get_fin_year(x):
        if pd.isna(x):
            return ""
        y = x.year
        m = x.month
        return f"{y}/{y+1}" if m >= 7 else f"{y-1}/{y}"
    df["FIN_YEAR"] = df["published_parsed"].apply(lambda x: get_fin_year(x) if not pd.isna(x) else "")

    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)

    return df

# ---------- UTILS ----------
def safe_sort_key(val: str):
    try:
        if str(val).isdigit():
            return (0, int(val))
        if "/" in str(val) and str(val).split("/")[0].isdigit():
            return (0, int(str(val).split("/")[0]))
    except Exception:
        pass
    return (1, str(val).lower())

def make_options(series):
    vals = [str(v).strip() for v in pd.Series(series).dropna().unique()]
    vals = [v for v in vals if v and v.lower() != "nan"]
    unique = sorted(set(vals), key=safe_sort_key)
    return ["All"] + unique

# ---------- SESSION STATE ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()
df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available.")
    st.stop()

df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLORS ----------
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f",
    "Unknown": "#808080"
}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")
tonality_filter = st.sidebar.selectbox("Filter by Tonality", make_options(df["TONALITY"]))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", make_options(df["FIN_YEAR"]))
quarter_filter = st.sidebar.selectbox("Filter by Quarter", make_options(df["QUARTER"]))
year_filter = st.sidebar.selectbox("Filter by Year", make_options(df["YEAR"]))
month_filter = st.sidebar.selectbox("Filter by Month", make_options(df["MONTH"]))

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
    mask &= df["MONTH"] == month_filter

df_filtered = df[mask]

# ---------- TITLE BAR ----------
st.markdown(f"""
<div class="title-bar">
    📰 Mentions — Media Coverage (Total: {len(df_filtered)})
</div>
""", unsafe_allow_html=True)

# ---------- DISPLAY ----------
if df_filtered.empty:
    st.info("No mentions for the selected filters.")
else:
    for display_pos, idx in enumerate(df_filtered.index, start=1):
        row = df_filtered.loc[idx]
        tonality = st.session_state["tonality_map"].get(idx, row["TONALITY"])
        bg_color = COLORS.get(tonality, "#ffffff")
        # Make neutral text white instead of black
        text_color = "#ffffff" if tonality in ["Positive", "Negative", "Neutral"] else "#000000"

        st.markdown(
            f"""
            <div class="mention-card" style="background-color:{bg_color}; color:{text_color};">
                <div><b>{display_pos}. {row['DATE']} {row['TIME']}</b> — <i>{row['SOURCE']}</i></div>
                <div style="font-weight:700;">{row['TITLE']}</div>
                <div>{row['SUMMARY']}</div>
                <div style="margin-top:8px;"><b>Tonality:</b> {tonality}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if row["LINK"].startswith("http"):
            st.markdown(f"[🔗 Read Full Story]({row['LINK']})")
        st.markdown("---")

# ---------- DOWNLOAD ----------
st.subheader("📥 Export Updated Mentions")
csv_bytes = df_filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
