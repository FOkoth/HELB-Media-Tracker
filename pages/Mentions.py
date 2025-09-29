import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="HELB Mentions", layout="wide")

# ----------------------------
# Load Data
# ----------------------------
@st.cache_data
def load_data():
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQmqNnR4KiN1sCufN6UatXqu9T8VXLFe0Xt7KgxE4j0h9n07Gm1i6qM6FC9tPYO0M/pub?output=csv"
    df = pd.read_csv(sheet_url)

    # Ensure DATE column exists and is datetime
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    else:
        df["DATE"] = pd.NaT

    # Extract Year, Month, Quarter
    df["YEAR"] = df["DATE"].dt.year
    df["MONTH"] = df["DATE"].dt.month_name().str[:3]  # Jan, Feb, ...
    df["QUARTER"] = df["DATE"].dt.quarter.apply(lambda x: f"Q{x}" if pd.notna(x) else np.nan)

    # Financial Year (Kenyan: runs July–June)
    def get_financial_year(date):
        if pd.isna(date):
            return np.nan
        year = date.year
        if date.month >= 7:
            return f"{year}/{year+1}"
        else:
            return f"{year-1}/{year}"
    df["FIN_YEAR"] = df["DATE"].apply(get_financial_year)

    # Clean TONALITY if missing
    if "TONALITY" not in df.columns:
        df["TONALITY"] = "Neutral"

    return df

df = load_data()

# ----------------------------
# Sidebar Navigation
# ----------------------------
st.markdown(
    """
    <style>
    /* Sidebar background */
    section[data-testid="stSidebar"] {
        background-color: #B8860B; /* dark gold */
    }
    /* Nav items */
    .css-1d391kg, .css-1v3fvcr, .css-16idsys {
        background-color: green !important;
        color: white !important;
        border-radius: 8px;
        padding: 6px 12px;
        margin: 4px 0;
    }
    .css-1d391kg:hover, .css-1v3fvcr:hover, .css-16idsys:hover {
        background-color: white !important;
        color: black !important;
    }
    /* Neutral tonality card */
    .neutral-card {
        background-color: grey !important;
        color: white !important;
        padding: 8px;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# Filters
# ----------------------------
st.sidebar.header("Filters")

tonality_filter = st.sidebar.selectbox(
    "Filter by Tonality",
    ["All"] + sorted(df["TONALITY"].dropna().unique())
)

# Ordered months
month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

month_filter = st.sidebar.selectbox(
    "Filter by Month",
    ["All"] + month_order
)

quarter_filter = st.sidebar.selectbox(
    "Filter by Quarter",
    ["All"] + [f"Q{i}" for i in range(1, 5)]
)

year_filter = st.sidebar.selectbox(
    "Filter by Year",
    ["All"] + sorted(df["YEAR"].dropna().astype(int).unique().tolist())
)

fin_year_filter = st.sidebar.selectbox(
    "Filter by Financial Year",
    ["All"] + sorted(df["FIN_YEAR"].dropna().unique())
)

# ----------------------------
# Apply Filters
# ----------------------------
filtered_df = df.copy()
if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]
if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == month_filter]
if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]
if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"] == year_filter]
if fin_year_filter != "All":
    filtered_df = filtered_df[filtered_df["FIN_YEAR"] == fin_year_filter]

# ----------------------------
# Display Mentions
# ----------------------------
st.title("HELB Media Mentions")

if filtered_df.empty:
    st.warning("No mentions found for the selected filters.")
else:
    for _, row in filtered_df.iterrows():
        tonality = row.get("TONALITY", "Neutral")
        date = row.get("DATE", "")
        source = row.get("SOURCE", "Unknown Source")
        title = row.get("TITLE", "No Title")

        # Background color based on tonality
        if tonality == "Positive":
            bg_color = "#4CAF50"  # Green
            text_color = "white"
        elif tonality == "Negative":
            bg_color = "#F44336"  # Red
            text_color = "white"
        elif tonality == "Neutral":
            bg_color = "grey"
            text_color = "white"
        else:
            bg_color = "#2196F3"  # Blue default
            text_color = "white"

        st.markdown(
            f"""
            <div style="background-color:{bg_color}; color:{text_color}; padding:10px;
                        border-radius:8px; margin-bottom:8px;">
                <b>{title}</b><br>
                <small>{date} | {source} | Tonality: {tonality}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
