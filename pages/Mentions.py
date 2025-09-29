# Mentions.py
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

# ---------- NAVIGATION + GLOBAL STYLES ----------
st.markdown(
    """
    <style>
    /* Navigation bar styling */
    .stApp header {background-color: #B8860B;} /* dark gold */
    section[data-testid="stSidebar"] {
        background-color: #228B22; /* green */
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stButton button {
        color: white !important;
    }
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
        background-color: white !important;
        color: black !important;
    }
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"]:hover {
        background-color: #f5f5f5 !important;
        color: black !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

    if "published" in df.columns:
        df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        try:
            df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
        except Exception:
            pass

        df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y").fillna("")
        df["TIME"] = df["published_parsed"].dt.strftime("%H:%M").fillna("")

        # Year (no decimals, no <NA>)
        df["YEAR"] = df["published_parsed"].dt.year
        df["YEAR"] = df["YEAR"].astype("Int64")
        df["YEAR"] = df["YEAR"].astype(str).replace("<NA>", "")

        # Month
        df["MONTH"] = df["published_parsed"].dt.strftime("%B").fillna("")

        # Quarter (Q1, Q2 etc.)
        df["QUARTER"] = df["published_parsed"].dt.quarter.fillna("").apply(
            lambda x: f"Q{int(x)}" if str(x).isdigit() else ""
        )

        # Financial Year (simple July–June assumption)
        fy = []
        for dt in df["published_parsed"]:
            if pd.isna(dt):
                fy.append("")
            else:
                year = dt.year
                if dt.month >= 7:
                    fy.append(f"{year}/{year+1}")
                else:
                    fy.append(f"{year-1}/{year}")
        df["FIN_YEAR"] = fy
    else:
        df["published_parsed"] = pd.NaT
        df["DATE"] = df["TIME"] = df["YEAR"] = df["MONTH"] = df["QUARTER"] = df["FIN_YEAR"] = ""

    for col in ["title", "summary", "source", "tonality", "link"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

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

# Tonality mapping
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLOR CODES ----------
COLORS = {
    "Positive": "#3b8132",   # green
    "Neutral": "#6E6F71",    # grey
    "Negative": "#d1001f"    # red
}

# ---------- FILTERS ----------
st.sidebar.subheader("Filters")

tonality_filter = st.sidebar.selectbox("Filter by Tonality", ["All"] + sorted(df["TONALITY"].unique()))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", ["All"] + sorted(df["FIN_YEAR"].unique()))
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All"] + sorted([q for q in df["QUARTER"].unique() if q]))
year_filter = st.sidebar.selectbox("Filter by Year", ["All"] + sorted([y for y in df["YEAR"].unique() if y]))
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + sorted([m for m in df["MONTH"].unique() if m]))

filtered_df = df.copy()
if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]
if fin_year_filter != "All":
    filtered_df = filtered_df[filtered_df["FIN_YEAR"] == fin_year_filter]
if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]
if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"] == year_filter]
if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == month_filter]

# ---------- EDITOR PANEL ----------
if is_editor:
    st.sidebar.subheader("Edit Tonality")
    edited_values = {}
    with st.sidebar.container():
        st.markdown('<div style="max-height:600px; overflow-y:auto; padding-right:5px;">', unsafe_allow_html=True)
        for i in df.index:
            current = st.session_state["tonality_map"][i]
            new_val = st.selectbox(
                f"{i+1}. {df.at[i, 'TITLE'][:50]}...",
                options=["Positive", "Neutral", "Negative"],
                index=["Positive", "Neutral", "Negative"].index(current)
                if current in ["Positive", "Neutral", "Negative"] else 1,
                key=f"tonality_{i}"
            )
            edited_values[i] = new_val
        st.markdown('</div>', unsafe_allow_html=True)

    if st.sidebar.button("Execute Update"):
        for idx, val in edited_values.items():
            st.session_state["tonality_map"][idx] = val
        updated_df = df.copy()
        updated_df["TONALITY"] = [st.session_state["tonality_map"][i] for i in df.index]
        updated_df.to_csv(LOCAL_CSV, index=False)
        st.sidebar.success("Tonality changes applied and saved! Colours updated below.")

# ---------- DISPLAY MENTIONS ----------
st.markdown(
    f"""
    <div style="background-color:#B8860B; color:white; padding:10px; border-radius:5px; margin-bottom:20px;">
        <h2>📰 Mentions — Media Coverage ({len(filtered_df)})</h2>
    </div>
    """,
    unsafe_allow_html=True
)

for i in filtered_df.index:
    row = filtered_df.loc[i]
    tonality = st.session_state["tonality_map"].get(i, row["TONALITY"])
    bg_color = COLORS.get(tonality, "#ffffff")
    text_color = "#ffffff"  # ensure white text for all, including Neutral

    st.markdown(
        f"""
        <div style="
            background-color:{bg_color};
            color:{text_color};
            padding:15px;
            border-radius:8px;
            margin-bottom:10px;
        ">
            <b>{i+1}. {row['DATE']} {row['TIME']}</b><br>
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
export_df = df.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"][i] for i in df.index]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Updated Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
