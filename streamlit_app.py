import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="HELB Intelligent Media Monitoring System",
    page_icon="📊",
    layout="wide"
)

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def connect_to_gsheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=600)  # refresh every 10 mins
def load_data(sheet_name="HELB_Mentions"):
    client = connect_to_gsheet()
    spreadsheet = client.open("Your-Google-Sheet-Name")  # 👈 replace with actual sheet
    worksheet = spreadsheet.worksheet(sheet_name)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

# --- MAIN DASHBOARD ---
st.title("📊 HELB Media Monitoring Dashboard")
st.markdown("Tracking media mentions, keywords, and sentiment around HELB in Kenya.")

try:
    df = load_data()
    st.success(f"Loaded {len(df)} rows from Google Sheets ✅")

    # --- Quick KPIs ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Mentions", len(df))
    with col2:
        st.metric("Unique Sources", df["Source"].nunique() if "Source" in df else 0)
    with col3:
        st.metric("Latest Date", df["Date"].max() if "Date" in df else "N/A")

    # --- Recent Mentions Table ---
    st.subheader("📰 Latest Mentions")
    st.dataframe(df.sort_values("Date", ascending=False).head(10))

except Exception as e:
    st.error("⚠️ Could not load data from Google Sheets.")
    st.exception(e)

st.markdown("---")
st.info("Use the sidebar to explore detailed pages: Mentions and Keyword Trends.")
