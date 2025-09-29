# pages/Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
CSV_URL = "https://docs.google.com/spreadsheets/d/10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ/export?format=csv"
LOCAL_CSV = "persistent_mentions.csv"  # File to save updates
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

        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background-color: #b8860b; /* dark gold */
        }
        section[data-testid="stSidebar"] .stSelectbox label {
            color: white !important;
            font-weight: bold;
        }
        section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
            background-color: #006400 !important; /* green */
            color: white !important;
            border-radius: 5px;
        }
        section[data-testid="stSidebar"] .stTextInput label {
            color: white !important;
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

    # Ensure all expected cols exist
    for col in ["title", "summary", "source", "tonality", "link", "published"]:
        if col not in df.columns:
            df[col] = ""

    # Parse published date
    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    try:
        df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
    except Exception:
        pass

    df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y").fillna("")
    df["TIME"] = df["published_parsed"].dt.strftime("%H:%M").fillna("")
    df["YEAR"] = df["published_parsed"].dt.year.fillna("").astype(str)
    df["MONTH"] = df["published_parsed"].dt.strftime("%B").fillna("")
    df["QUARTER"] = df["published_parsed"].dt.to_period("Q").astype(str).fillna("")

    def get_fin_year(x):
        if pd.isna(x):
            return ""
        return f"{x.year}/{x.year+1}" if x.month >= 7 else f"{x.year-1}/{x.year}"
    df["FIN_YEAR"] = df["published_parsed"].apply(get_fin_year)

    # Rename cols for UI
    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)
    return df

# ---------- SESSION STATE ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()
df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available.")
    st.stop()

df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

# Tonality mapping persistence
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLOR CODES ----------
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f"
}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")
tonality_filter = st.sidebar.selectbox("Filter by Tonality", ["All"] + sorted(df["TONALITY"].unique()))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", ["All"] + sorted(df["FIN_YEAR"].unique()))
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All"] + sorted(df["QUARTER"].unique()))
year_filter = st.sidebar.selectbox("Filter by Year", ["All"] + sorted(df["YEAR"].unique()))
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + sorted(df["MONTH"].unique()))

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

# ---------- DISPLAY MENTIONS ----------
for i in df_filtered.index:
    row = df_filtered.loc[i]
    tonality = st.session_state["tonality_map"].get(i, row["TONALITY"])
    bg_color = COLORS.get(tonality, "#ffffff")
    text_color = "#ffffff" if tonality in ["Positive", "Negative"] else "#ffffff"

    st.markdown(
        f"""
        <div style="
            background-color:{bg_color};
            color:{text_color};
            padding:15px;
            border-radius:8px;
            margin-bottom:10px;
        ">
            <b>{row['DATE']} {row['TIME']}</b><br>
            <b>Source:</b> {row['SOURCE']}<br>
            <b>Title:</b> {row['TITLE']}<br>
            <b>Summary:</b> {row['SUMMARY']}<br>
            <b>Tonality:</b> {tonality}
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
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, row["TONALITY"]) for i, row in df_filtered.iterrows()]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Updated Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
