# pages/Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
LOCAL_CSV = "persistent_mentions.csv"
EDITOR_PASSWORD = "MyHardSecret123"

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
    # Load persistent CSV if it exists, else Google Sheet
    if os.path.exists(LOCAL_CSV):
        df = pd.read_csv(LOCAL_CSV)
    else:
        sheet_url = st.secrets["gcp"]["sheet_url"]
        df = pd.read_csv(sheet_url)

    df.columns = [c.strip().lower() for c in df.columns]

    # Parse published datetime
    if "published" in df.columns:
        df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        try:
            df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
        except Exception:
            pass
        df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y")
        df["TIME"] = df["published_parsed"].dt.strftime("%H:%M")
        df["YEAR"] = df["published_parsed"].dt.year.dropna().astype(int).astype(str)

        # Financial year: July–June
        df["FIN_YEAR"] = df["published_parsed"].apply(
            lambda x: f"{x.year}/{x.year+1}" if x.month >= 7 else f"{x.year-1}/{x.year}"
            if pd.notnull(x) else None
        )

        # Quarters: Q1–Q4
        df["QUARTER"] = df["published_parsed"].dt.quarter.apply(
            lambda q: f"Q{q}" if pd.notnull(q) else None
        )

        # Month name
        df["MONTH"] = df["published_parsed"].dt.month_name().where(df["published_parsed"].notna())
    else:
        df["published_parsed"] = pd.NaT
        df["DATE"], df["TIME"], df["YEAR"], df["FIN_YEAR"], df["QUARTER"], df["MONTH"] = "", "", "", "", "", ""

    # Ensure required cols exist
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

# Tonality state
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLOR CODES ----------
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f"
}

# ---------- STYLING ----------
st.markdown("""
    <style>
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #B8860B; /* dark gold */
    }
    /* Sidebar nav items */
    section[data-testid="stSidebar"] .stMarkdown a {
        background-color: #228B22; /* green */
        color: white !important;
        padding: 6px 12px;
        border-radius: 4px;
        display: block;
        margin-bottom: 5px;
        text-decoration: none;
    }
    section[data-testid="stSidebar"] .stMarkdown a:hover {
        background-color: white !important;
        color: black !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- FILTERS ----------
filters = {}

tonality_filter = st.sidebar.selectbox(
    "Filter by Tonality", ["All"] + sorted([t for t in df["TONALITY"].dropna().unique()])
)
filters["TONALITY"] = tonality_filter

fin_years = sorted([fy for fy in df["FIN_YEAR"].dropna().unique()])
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", ["All"] + fin_years)
filters["FIN_YEAR"] = fin_year_filter

quarters = ["Q1", "Q2", "Q3", "Q4"]
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All"] + quarters)
filters["QUARTER"] = quarter_filter

years = sorted([str(int(y)) for y in df["YEAR"].dropna().unique()])
year_filter = st.sidebar.selectbox("Filter by Year", ["All"] + years)
filters["YEAR"] = year_filter

months = ["January","February","March","April","May","June",
          "July","August","September","October","November","December"]
month_filter = st.sidebar.selectbox("Filter by Month", ["All"] + months)
filters["MONTH"] = month_filter

# Apply filters
filtered_df = df.copy()
for col, val in filters.items():
    if val != "All" and col in filtered_df.columns:
        filtered_df = filtered_df[filtered_df[col] == val]

# ---------- HEADER ----------
st.markdown(
    f"""
    <div style="background-color:#B8860B; padding:12px; border-radius:6px; text-align:center;">
        <h2 style="color:white; margin:0;">📰 Mentions — Media Coverage ({len(filtered_df)})</h2>
    </div>
    """,
    unsafe_allow_html=True
)

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
                index=["Positive","Neutral","Negative"].index(current) if current in ["Positive","Neutral","Negative"] else 1,
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
        st.sidebar.success("Tonality changes applied and saved!")

# ---------- DISPLAY MENTIONS ----------
for i in filtered_df.index:
    row = filtered_df.loc[i]
    tonality = st.session_state["tonality_map"].get(i, row["TONALITY"])
    bg_color = COLORS.get(tonality, "#ffffff")
    text_color = "#ffffff" if tonality in ["Positive", "Negative", "Neutral"] else "#000000"

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
    if str(row["LINK"]).startswith("http"):
        st.markdown(f"[🔗 Read Full Story]({row['LINK']})")
    st.markdown("---")

# ---------- DOWNLOAD ----------
st.subheader("Export Updated Mentions")
export_df = filtered_df.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, row["TONALITY"]) for i, row in filtered_df.iterrows()]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Updated Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
