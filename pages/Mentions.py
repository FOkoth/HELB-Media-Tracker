# pages/Mentions.py
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
    /* Sidebar background (dark gold) */
    section[data-testid="stSidebar"] {
        background-color: #b8860b !important;
    }
    /* Sidebar navigation items */
    section[data-testid="stSidebar"] .st-emotion-cache-1v0mbdj a {
        background-color: #006400 !important; /* dark green */
        color: white !important;
        border-radius: 5px;
        padding: 6px 10px;
        margin-bottom: 4px;
        display: block;
        text-decoration: none;
    }
    /* Hover effect */
    section[data-testid="stSidebar"] .st-emotion-cache-1v0mbdj a:hover {
        background-color: white !important;
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
    # Load CSV (local persistence first, fallback to Google Sheet)
    if os.path.exists(LOCAL_CSV):
        df = pd.read_csv(LOCAL_CSV)
    else:
        df = pd.read_csv(CSV_URL)

    df.columns = [c.strip().lower() for c in df.columns]

    # Detect possible date column
    date_col = None
    for candidate in ["published", "date", "pub_date"]:
        if candidate in df.columns:
            date_col = candidate
            break

    if date_col:
        df["published_parsed"] = pd.to_datetime(
            df[date_col], errors="coerce", utc=True, dayfirst=True
        )
        try:
            df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
        except Exception:
            pass
        df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y")
        df["TIME"] = df["published_parsed"].dt.strftime("%H:%M")
        df["YEAR"] = df["published_parsed"].dt.year.fillna(0).astype(int).astype(str)
        df["MONTH"] = df["published_parsed"].dt.month.fillna(0).astype(int)
        df["QUARTER"] = df["published_parsed"].dt.quarter.fillna(0).astype(int)
        df["FIN_YEAR"] = df["published_parsed"].dt.to_period("A-JUN").astype(str)
    else:
        # fallback if no valid date column
        df["published_parsed"] = pd.NaT
        df["DATE"], df["TIME"], df["YEAR"], df["MONTH"], df["QUARTER"], df["FIN_YEAR"] = "", "", "", "", "", ""

    # Fill missing essential cols
    for col in ["title", "summary", "source", "tonality", "link"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("")

    # Rename for display
    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)

    # Map months to names
    month_map = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    if "MONTH" in df.columns:
        df["MONTH_NAME"] = df["MONTH"].map(month_map).fillna("")

    # Format quarter (Q1–Q4 only, no year prefix)
    if "QUARTER" in df.columns:
        df["QUARTER"] = df["QUARTER"].apply(lambda x: f"Q{x}" if x in [1, 2, 3, 4] else "")

    return df

# ---------- SESSION STATE ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()
df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available.")
    st.stop()

df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

# Tonality map (for editing)
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLOR CODES ----------
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f"
}

# ---------- FILTERING ----------
st.sidebar.header("🔎 Filters")

tonality_filter = st.sidebar.selectbox("Filter by Tonality", ["All"] + sorted(df["TONALITY"].unique()))
year_filter = st.sidebar.selectbox("Filter by Year", ["All"] + sorted(df["YEAR"].unique()))
month_filter = st.sidebar.selectbox(
    "Filter by Month",
    ["All"] + [m for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"] if m in df.get("MONTH_NAME", [])]
)
quarter_filter = st.sidebar.selectbox("Filter by Quarter", ["All"] + sorted([q for q in df["QUARTER"].unique() if q]))
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", ["All"] + sorted([fy for fy in df["FIN_YEAR"].unique() if fy]))

filtered_df = df.copy()
if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]
if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"] == year_filter]
if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH_NAME"] == month_filter]
if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]
if fin_year_filter != "All":
    filtered_df = filtered_df[filtered_df["FIN_YEAR"] == fin_year_filter]

# ---------- TITLE ----------
st.markdown(
    f"""
    <div style="background-color:#b8860b; padding:10px; border-radius:5px; text-align:center;">
        <h2 style="color:white;">📰 Mentions — Media Coverage ({len(filtered_df)} total)</h2>
    </div>
    """,
    unsafe_allow_html=True,
)

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
    if row["LINK"].startswith("http"):
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
