# pages/Mentions.py

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Mentions", layout="wide")

# ===============================
# Load data (always live from sheet)
# ===============================
@st.cache_data(ttl=60)
def load_data():
    url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQmqNnR4KiN1sCufN6UatXqu9T8VXLFe0Xt7KgxE4j0h9n07Gm1i6qM6FC9tPYO0M/pub?output=csv"
    df = pd.read_csv(url)

    # Ensure DATE column is datetime
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")

        # Extract Year, Month name
        df["YEAR"] = df["DATE"].dt.year
        df["MONTH"] = df["DATE"].dt.strftime("%b")

        # Apply FY logic (July–June)
        df["FY"] = df["DATE"].apply(
            lambda x: f"{x.year}/{x.year+1}" if x.month >= 7 else f"{x.year-1}/{x.year}"
        )

        # Apply FY Quarter mapping
        def get_fy_quarter(date):
            if pd.isna(date):
                return None
            m = date.month
            if m in [7, 8, 9]:
                return "Q1"
            elif m in [10, 11, 12]:
                return "Q2"
            elif m in [1, 2, 3]:
                return "Q3"
            elif m in [4, 5, 6]:
                return "Q4"
            return None

        df["QUARTER"] = df["DATE"].apply(get_fy_quarter)

    return df


# Store live dataframe
df = load_data()
st.session_state["mentions_df"] = df

# ===============================
# Sidebar filters
# ===============================
st.sidebar.header("Filters")

# Tonality filter
tonality_filter = st.sidebar.selectbox("Filter by Tonality", ["All"] + sorted(df["TONALITY"].dropna().unique()))

# FY filter (sorted, no NaT)
fy_options = ["All"] + sorted(df["FY"].dropna().unique())
fy_filter = st.sidebar.selectbox("Filter by Financial Year", fy_options)

# Quarter filter (Q1-Q4)
quarter_options = ["All", "Q1", "Q2", "Q3", "Q4"]
quarter_filter = st.sidebar.selectbox("Filter by Quarter", quarter_options)

# Month filter (Jan–Dec in correct order)
month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
month_options = ["All"] + month_order
month_filter = st.sidebar.selectbox("Filter by Month", month_options)

# Year filter (no decimals)
year_options = ["All"] + sorted(df["YEAR"].dropna().unique().astype(int).tolist())
year_filter = st.sidebar.selectbox("Filter by Year", year_options)

# ===============================
# Apply filters
# ===============================
filtered_df = df.copy()

if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]

if fy_filter != "All":
    filtered_df = filtered_df[filtered_df["FY"] == fy_filter]

if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]

if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == month_filter]

if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"] == year_filter]

# ===============================
# Display results
# ===============================
st.subheader("Media Mentions")

for _, row in filtered_df.iterrows():
    tonality = row.get("TONALITY", "").lower()
    bg_color = "white"
    text_color = "black"

    if tonality == "positive":
        bg_color = "#d4edda"  # light green
        text_color = "black"
    elif tonality == "negative":
        bg_color = "#f8d7da"  # light red
        text_color = "black"
    elif tonality == "neutral":
        bg_color = "grey"
        text_color = "white"

    st.markdown(
        f"""
        <div style="background-color:{bg_color}; color:{text_color}; padding:10px; 
        border-radius:10px; margin-bottom:10px;">
            <b>{row.get("TITLE", "No Title")}</b><br>
            <i>{row.get("SOURCE", "Unknown Source")}</i> | {row.get("DATE", "")}<br>
            {row.get("SUMMARY", "")}
        </div>
        """,
        unsafe_allow_html=True,
    )
