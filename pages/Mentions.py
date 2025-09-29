# pages/1_Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
CSV_URL = "https://docs.google.com/spreadsheets/d/10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ/export?format=csv"
LOCAL_CSV = "persistent_mentions.csv"  # File to save updates
EDITOR_PASSWORD = "MyHardSecret123"

# ---------- STYLING ----------
st.markdown(
    """
    <style>
    /* Top navigation bar */
    .stAppHeader {
        background-color: #b8860b !important; /* Dark gold */
    }
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #006400; /* Dark green */
    }
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    /* Title bar */
    .mentions-title {
        background-color: #b8860b;
        color: white;
        padding: 12px;
        border-radius: 6px;
        text-align: center;
        font-size: 22px;
        font-weight: bold;
        margin-bottom: 15px;
    }
    </style>
    """,
    unsafe_allow_html=True
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
    # Load persistent CSV if it exists
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
        df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y")
        df["TIME"] = df["published_parsed"].dt.strftime("%H:%M")
        df["YEAR"] = df["published_parsed"].dt.year
        df["MONTH"] = df["published_parsed"].dt.strftime("%B")
        df["QUARTER"] = df["published_parsed"].dt.to_period("Q").astype(str)
        # Financial Year: starts in July
        df["FIN_YEAR"] = df["published_parsed"].apply(
            lambda x: f"{x.year}/{x.year+1}" if x.month >= 7 else f"{x.year-1}/{x.year}"
        )
    else:
        df["published_parsed"] = pd.NaT
        df["DATE"] = ""
        df["TIME"] = ""
        df["YEAR"] = ""
        df["MONTH"] = ""
        df["QUARTER"] = ""
        df["FIN_YEAR"] = ""

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
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f"
}

# ---------- FILTERS ----------
st.sidebar.subheader("🔍 Filters")

tonality_filter = st.sidebar.selectbox("Filter by Tonality", ["All"] + sorted(df["TONALITY"].unique()))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", ["All"] + sorted(df["FIN_YEAR"].unique()))
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All"] + sorted(df["QUARTER"].unique()))
year_filter = st.sidebar.selectbox("Filter by Year", ["All"] + sorted(df["YEAR"].unique().astype(str)))
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + sorted(df["MONTH"].unique()))

filtered_df = df.copy()

if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]
if fin_year_filter != "All":
    filtered_df = filtered_df[filtered_df["FIN_YEAR"] == fin_year_filter]
if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]
if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"].astype(str) == year_filter]
if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == month_filter]

# ---------- TITLE BAR ----------
st.markdown(
    f"<div class='mentions-title'>📰 Mentions — Media Coverage ({len(filtered_df)} results)</div>",
    unsafe_allow_html=True
)

# ---------- EDITOR PANEL (SCROLLABLE) ----------
if is_editor:
    st.sidebar.subheader("✏️ Edit Tonality")
    edited_values = {}

    with st.sidebar.container():
        st.markdown(
            '<div style="max-height:600px; overflow-y:auto; padding-right:5px;">', 
            unsafe_allow_html=True
        )
        for i in filtered_df.index:
            current = st.session_state["tonality_map"].get(i, "Neutral")
            new_val = st.selectbox(
                f"{i+1}. {filtered_df.at[i, 'TITLE'][:50]}...",
                options=["Positive", "Neutral", "Negative"],
                index=["Positive","Neutral","Negative"].index(current) if current in ["Positive","Neutral","Negative"] else 1,
                key=f"tonality_{i}"
            )
            edited_values[i] = new_val
        st.markdown('</div>', unsafe_allow_html=True)

    if st.sidebar.button("💾 Save Tonality Updates"):
        for idx, val in edited_values.items():
            st.session_state["tonality_map"][idx] = val
        updated_df = df.copy()
        updated_df["TONALITY"] = [st.session_state["tonality_map"][i] for i in df.index]
        updated_df.to_csv(LOCAL_CSV, index=False)
        st.sidebar.success("Tonality changes applied and saved!")

# ---------- DISPLAY MENTIONS ----------
for i in filtered_df.index:
    row = filtered_df.loc[i]
    tonality = st.session_state["tonality_map"].get(i, "Neutral")
    bg_color = COLORS.get(tonality, "#ffffff")
    text_color = "#ffffff"

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
st.subheader("📥 Export Updated Mentions")
export_df = filtered_df.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, "Neutral") for i in filtered_df.index]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
