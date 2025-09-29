import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="HELB Media Mentions", layout="wide")

# Custom CSS
st.markdown(
    """
    <style>
        /* Sidebar background */
        section[data-testid="stSidebar"] {
            background-color: #b8860b !important; /* Dark gold */
        }

        /* Navigation items (buttons/links) */
        .stSidebar button, .stSidebar a {
            background-color: green !important;
            color: white !important;
            border-radius: 5px;
        }
        .stSidebar button:hover, .stSidebar a:hover {
            background-color: white !important;
            color: black !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Load Data ----------
@st.cache_data
def load_data():
    df = pd.read_csv("https://docs.google.com/spreadsheets/d/e/2PACX-1vQmqNnR4KiN1sCufN6UatXqu9T8VXLFe0Xt7KgxE4j0h9n07Gm1i6qM6FC9tPYO0M/pub?output=csv")

    # Parse published date
    df["published_parsed"] = pd.to_datetime(df["published_parsed"], errors="coerce")

    # Clean YEAR
    df["YEAR"] = df["published_parsed"].dt.year

    # Clean MONTH (full names, Jan–Dec order)
    month_map = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    df["MONTH"] = df["published_parsed"].dt.month.map(month_map)

    # Clean QUARTER
    df["QUARTER"] = df["published_parsed"].dt.quarter.map(lambda q: f"Q{q}")

    # Financial Year (manual academic year July–June)
    def get_fin_year(date):
        if pd.isna(date):
            return None
        if date.month >= 7:
            return f"{date.year}/{date.year+1}"
        else:
            return f"{date.year-1}/{date.year}"

    df["FIN_YEAR"] = df["published_parsed"].apply(get_fin_year)

    # Drop rows with no date (avoids NaT in filters)
    df = df.dropna(subset=["published_parsed", "YEAR", "MONTH", "QUARTER", "FIN_YEAR"])

    # Ensure TONALITY exists
    if "TONALITY" not in df.columns:
        df["TONALITY"] = "Neutral"

    return df


df = load_data()

# ---------- Sidebar Filters ----------
st.sidebar.header("Filters")

year_filter = st.sidebar.selectbox(
    "Filter by Year",
    ["All"] + sorted(df["YEAR"].dropna().unique().astype(int).astype(str).tolist())
)

# Financial Year filter
fin_year_filter = st.sidebar.selectbox(
    "Filter by Financial Year",
    ["All"] + sorted(df["FIN_YEAR"].dropna().unique().tolist())
)

# Months filter (always Jan–Dec order)
all_months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
available_months = df["MONTH"].dropna().unique().tolist()
month_filter = st.sidebar.selectbox(
    "Filter by Month",
    ["All"] + [m for m in all_months if m in available_months]
)

# Quarters filter (always Q1–Q4 order)
all_quarters = ["Q1", "Q2", "Q3", "Q4"]
available_quarters = df["QUARTER"].dropna().unique().tolist()
quarter_filter = st.sidebar.selectbox(
    "Filter by Quarter",
    ["All"] + [q for q in all_quarters if q in available_quarters]
)

tonality_filter = st.sidebar.selectbox(
    "Filter by Tonality",
    ["All"] + sorted(df["TONALITY"].dropna().unique().tolist())
)

# ---------- Apply Filters ----------
filtered_df = df.copy()

if year_filter != "All":
    filtered_df = filtered_df[filtered_df["YEAR"].astype(str) == year_filter]

if fin_year_filter != "All":
    filtered_df = filtered_df[filtered_df["FIN_YEAR"] == fin_year_filter]

if month_filter != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == month_filter]

if quarter_filter != "All":
    filtered_df = filtered_df[filtered_df["QUARTER"] == quarter_filter]

if tonality_filter != "All":
    filtered_df = filtered_df[filtered_df["TONALITY"] == tonality_filter]

# ---------- Dashboard Content ----------
st.title("📊 HELB Media Mentions")

st.metric("Total Mentions", len(filtered_df))

if not filtered_df.empty:
    fig = px.histogram(
        filtered_df,
        x="MONTH",
        color="TONALITY",
        category_orders={"MONTH": all_months},
        title="Mentions by Month & Tonality"
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(filtered_df[["title", "link", "published_parsed", "TONALITY"]])
else:
    st.warning("No mentions found for selected filters.")
