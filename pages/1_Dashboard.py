# pages/1_Dashboard.py
import streamlit as st 
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud, STOPWORDS
import nltk
import gspread
from google.oauth2.service_account import Credentials
import calendar
import io
from datetime import datetime

# Ensure nltk stopwords are available
nltk.download("stopwords", quiet=True)
from nltk.corpus import stopwords as nltk_stopwords

# ---------------- CONFIG ----------------
HELB_GREEN = "#008000"
HELB_GREEN_LIGHT = "#00A000"
HELB_GOLD = "#FFD700"
HELB_BLUE = "#1E90FF"
HELB_RED = "#B22222"
HELB_GREY = "#808080"
HELB_COLORS = [HELB_GREEN, HELB_GOLD, HELB_BLUE, HELB_RED]
LOGO_URL = "https://www.helb.co.ke/wp-content/uploads/2022/05/helb-logo.png"

# ---------------- PAGE CONFIG ----------------
st.set_page_config(layout="wide", page_title="HELB INTELLIGENT MEDIA MONITORING SYSTEM")

# ---------------- STYLES: Header, Hero, Sidebar, Tiles ----------------
st.markdown(
    f"""
    <style>
        /* Pinned header with logo */
        .helb-header {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            z-index: 9999;
            background: linear-gradient(135deg, {HELB_GREEN}, {HELB_GREEN_LIGHT});
            color: white;
            display:flex;
            align-items:center;
            gap:16px;
            padding: 10px 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.12);
        }}
        .helb-header img {{
            height:50px;
            width:auto;
            display:block;
        }}
        .helb-header .subtitle {{
            font-size:12px;
            opacity:0.95;
            margin-top:2px;
        }}

        /* Accent under header */
        .helb-accent {{
            height: 4px;
            width: 100%;
            background: linear-gradient(90deg, {HELB_GOLD}, rgba(255,215,0,0.4));
        }}

        /* Hero banner (the big title users see first) */
        .hero-banner {{
            margin-top: 86px; /* space for pinned header */
            background: linear-gradient(90deg, {HELB_GREEN}, {HELB_GREEN_LIGHT});
            color: white;
            padding: 36px 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .hero-banner h1 {{
            margin: 0;
            font-size: 32px;
            font-weight: 900;
            letter-spacing: 1px;
        }}
        .hero-banner p {{
            margin: 6px 0 0;
            opacity: 0.95;
        }}

        /* Body spacing to ensure footer doesn't overlap */
        .app-body {{
            padding-top: 20px;
            padding-bottom: 90px; /* leave room for footer */
        }}

        /* Sidebar styling */
        section[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {HELB_GREEN}, {HELB_GREEN_LIGHT});
        }}
        section[data-testid="stSidebar"] .css-1d391kg, 
        section[data-testid="stSidebar"] label, 
        section[data-testid="stSidebar"] span {{
            color: white !important;
        }}

        /* Tiles and chart containers */
        .tile {{
            background-color: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            text-align: center;
            margin-bottom: 10px;
        }}
        .tile h3 {{
            margin: 0;
            font-size: 14px;
            color: {HELB_GREEN};
        }}
        .tile p {{
            font-size: 26px;
            font-weight: 600;
            margin: 6px 0 0;
        }}
        .chart-tile {{
            background-color: white;
            padding: 12px;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.04);
            margin-bottom: 18px;
        }}

        /* Footer */
        .footer {{
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background: linear-gradient(90deg, {HELB_GREEN_LIGHT}, {HELB_GREEN});
            color: white;
            text-align: center;
            padding: 8px 12px;
            font-size: 0.95rem;
            box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------- HEADER + HERO ----------------

st.markdown(
    f"""
    <div class="helb-header">
        <img src="{LOGO_URL}" alt="HELB Logo">
        <div>
            <div style="font-weight:800;">HELB</div>
            <div class="subtitle">Media Monitoring & Insights</div>
        </div>
    </div>
    <div class="helb-accent"></div>

    <div class="hero-banner">
        <h1>HELB INTELLIGENT MEDIA MONITORING SYSTEM</h1>
        <p>Automated Live Media Mentions, Sentiment Analysis and Trends </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# wrapper to provide spacing below hero
st.markdown('<div class="app-body">', unsafe_allow_html=True)

# ---------------- DATA LOADER ----------------
@st.cache_data(ttl=600)
def load_data_from_sheet(sheet_id: str):
    # Attempt to authenticate via st.secrets first, otherwise fall back to local file
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = None
    try:
        if "gcp_service_account" in st.secrets:
            # st.secrets["gcp_service_account"] should be the parsed JSON (dict)
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        else:
            # fallback to local file 'service_account.json' if exists
            import os
            if os.path.exists("service_account.json"):
                creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
            else:
                raise FileNotFoundError("No GCP service account available. Add st.secrets['gcp_service_account'] or service_account.json in app root.")
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        worksheet = sh.sheet1
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error loading Google Sheet: {e}")
        return pd.DataFrame()
    return df

# Replace with your sheet ID (the long ID from the sheet URL)
SHEET_ID = "10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ"

df_raw = load_data_from_sheet(SHEET_ID)

# ---------------- Data sanity / normalization ----------------
if df_raw.empty:
    st.error("No data loaded from the Google Sheet. Please check credentials and Sheet ID.")
    st.stop()

# normalize column names to lowercase
df_raw.columns = [c.strip().lower() for c in df_raw.columns]

# ensure expected columns exist (create if missing)
for col in ["title", "summary", "source", "tonality", "link", "published"]:
    if col not in df_raw.columns:
        df_raw[col] = ""

# parse published into datetime (robust)
df = df_raw.copy()
df["published"] = df["published"].astype(str).str.strip()
# try parse as utc then convert to Nairobi
try:
    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True).dt.tz_convert("Africa/Nairobi")
except Exception:
    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce")
    try:
        # attempt localization if naive
        df["published_parsed"] = df["published_parsed"].dt.tz_localize("Africa/Nairobi", ambiguous="NaT", nonexistent="NaT")
    except Exception:
        pass

# tonality normalization
df["tonality_norm"] = df["tonality"].astype(str).str.strip().str.capitalize()

# derived fields
df["YEAR"] = df["published_parsed"].dt.year
df["MONTH_NUM"] = df["published_parsed"].dt.month
df["MONTH"] = df["published_parsed"].dt.strftime("%b")
# financial year
fy_list = []
for d in df["published_parsed"]:
    if pd.isnull(d):
        fy_list.append(None)
    else:
        if d.month >= 7:
            fy_list.append(f"{d.year}/{d.year+1}")
        else:
            fy_list.append(f"{d.year-1}/{d.year}")
df["FINANCIAL_YEAR"] = fy_list

def fy_quarter(date):
    if pd.isnull(date):
        return None
    m = date.month
    if m in (7, 8, 9):
        return "Q1 (Jul–Sep)"
    if m in (10, 11, 12):
        return "Q2 (Oct–Dec)"
    if m in (1, 2, 3):
        return "Q3 (Jan–Mar)"
    return "Q4 (Apr–Jun)"

df["QUARTER"] = df["published_parsed"].apply(fy_quarter)
#-----------------HEADER FORM----------------------


# ---------------- SIDEBAR SLICERS ----------------
st.sidebar.header("🔎 Filters (Slicers)")

years_all = sorted([int(y) for y in df["YEAR"].dropna().unique()]) if not df["YEAR"].dropna().empty else []
fys_all = sorted([fy for fy in df["FINANCIAL_YEAR"].dropna().unique()]) if not df["FINANCIAL_YEAR"].dropna().empty else []
quarters_all = ["Q1 (Jul–Sep)", "Q2 (Oct–Dec)", "Q3 (Jan–Mar)", "Q4 (Apr–Jun)"]
months_all = list(calendar.month_abbr)[1:]

selected_years = st.sidebar.multiselect("Select Year(s)", years_all, default=[])
selected_fys = st.sidebar.multiselect("Select Financial Year(s)", fys_all, default=[])
selected_quarters = st.sidebar.multiselect("Select Quarter(s)", quarters_all, default=[])
selected_months = st.sidebar.multiselect("Select Month(s)", months_all, default=[])

keyword = st.sidebar.text_input("Keyword search (title + summary)")
show_debug = st.sidebar.checkbox("🛠 Show Debug Table")

if st.sidebar.button("Clear All Filters"):
    # reset local variables (widgets will keep state until page reload)
    selected_years = []
    selected_fys = []
    selected_quarters = []
    selected_months = []
    keyword = ""

# ---------------- APPLY FILTERS ----------------
filtered = df.copy()

if selected_years:
    filtered = filtered[filtered["YEAR"].isin(selected_years)]
if selected_fys:
    filtered = filtered[filtered["FINANCIAL_YEAR"].isin(selected_fys)]
if selected_quarters:
    filtered = filtered[filtered["QUARTER"].isin(selected_quarters)]
if selected_months:
    filtered = filtered[filtered["MONTH"].isin(selected_months)]

if keyword:
    kw = keyword.strip().lower()
    mask = (
        filtered["title"].fillna("").str.lower().str.contains(kw)
        | filtered["summary"].fillna("").str.lower().str.contains(kw)
    )
    filtered = filtered[mask]

# ---------------- KPI TILES ----------------
col1, col2, col3, col4 = st.columns(4)

total_mentions = len(filtered)
pos_count = int(filtered["tonality_norm"].str.lower().eq("positive").sum())
neg_count = int(filtered["tonality_norm"].str.lower().eq("negative").sum())
neu_count = int(filtered["tonality_norm"].str.lower().eq("neutral").sum())

with col1:
    st.markdown(f"<div class='tile'><h3>Total Mentions</h3><p style='color:{HELB_BLUE};'>{total_mentions}</p></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='tile'><h3>Positive</h3><p style='color:{HELB_GREEN};'>{pos_count}</p></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='tile'><h3>Negative</h3><p style='color:{HELB_RED};'>{neg_count}</p></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='tile'><h3>Neutral</h3><p style='color:{HELB_GREY};'>{neu_count}</p></div>", unsafe_allow_html=True)

st.markdown("---")

# ---------------- CHARTS (2x2 grid) ----------------
colA, colB = st.columns(2)

# --- Chart A: Tonality Doughnut
with colA:
    st.markdown("<div class='chart-tile'>", unsafe_allow_html=True)
    st.subheader("Tonality Distribution")
    ton_order = ["Positive", "Negative", "Neutral"]
    counts = filtered["tonality_norm"].value_counts().reindex(ton_order).fillna(0).astype(int)
    donut_df = pd.DataFrame({"Tonality": counts.index, "Count": counts.values})
    if donut_df["Count"].sum() > 0:
        fig_donut = px.pie(
            donut_df,
            names="Tonality",
            values="Count",
            hole=0.54,
            color="Tonality",
            color_discrete_map={"Positive": HELB_GREEN, "Negative": HELB_RED, "Neutral": HELB_GREY},
        )
        fig_donut.update_traces(textposition="inside", textinfo="percent+label", insidetextfont=dict(color="white"))
        fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No tonality data for selected filters.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- Chart B: Mentions Over Time
with colB:
    st.markdown("<div class='chart-tile'>", unsafe_allow_html=True)
    st.subheader("Mentions Over Time")
    if filtered["published_parsed"].notna().any():
        times = filtered.copy()
        times["date_only"] = times["published_parsed"].dt.date
        timeline = times.groupby("date_only").size().reset_index(name="count")
        timeline["date"] = pd.to_datetime(timeline["date_only"])
        fig_line = px.line(timeline.sort_values("date"), x="date", y="count", markers=True)
        fig_line.update_traces(line_color=HELB_BLUE)
        fig_line.update_layout(margin=dict(t=10, b=20, l=20, r=10), height=320)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No date information available for selected filters.")
    st.markdown("</div>", unsafe_allow_html=True)

colC, colD = st.columns(2)

# --- Chart C: Top Sources
with colC:
    st.markdown("<div class='chart-tile'>", unsafe_allow_html=True)
    st.subheader("Top News Sources")
    src_counts = filtered["source"].fillna("Unknown").value_counts().head(8).reset_index()
    if not src_counts.empty:
        src_counts.columns = ["Source", "Count"]
        fig_bar = px.bar(
            src_counts.sort_values("Count"),
            x="Count",
            y="Source",
            orientation="h",
            text="Count",
        )
        fig_bar.update_traces(marker_color=HELB_GREEN)
        fig_bar.update_layout(margin=dict(t=6, b=6, l=6, r=6), yaxis=dict(dtick=1), height=320)
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No source data for selected filters.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- Chart D: Tonality Trend (Monthly area)
with colD:
    st.markdown("<div class='chart-tile'>", unsafe_allow_html=True)
    st.subheader("Tonality Trend Over Time (Monthly)")
    if filtered["published_parsed"].notna().any():
        trend = (
            filtered.assign(month=filtered["published_parsed"].dt.to_period("M").astype(str))
            .groupby(["month", "tonality_norm"])
            .size()
            .reset_index(name="count")
        )
        if not trend.empty:
            trend["month_dt"] = pd.to_datetime(trend["month"].astype(str) + "-01", errors="coerce")
            trend = trend.sort_values("month_dt")
            fig_area = px.area(
                trend,
                x="month",
                y="count",
                color="tonality_norm",
                color_discrete_map={"Positive": HELB_GREEN, "Negative": HELB_RED, "Neutral": HELB_GREY},
            )
            fig_area.update_layout(margin=dict(t=6, b=6, l=6, r=6), legend_title_text="Tonality", height=320)
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("No tonality trend data for selected filters.")
    else:
        st.info("No date information for trend chart.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# ---------------- WORD CLOUD ----------------
st.markdown("<div class='chart-tile'>", unsafe_allow_html=True)
if st.button("☁️ Generate Word Cloud"):
    st.subheader("Keyword Word Cloud")
    title_col = "title" if "title" in filtered.columns else "TITLE"
    summary_col = "summary" if "summary" in filtered.columns else "SUMMARY"
    texts = (filtered[title_col].astype(str) + " " + filtered[summary_col].astype(str)).tolist()
    big_text = " ".join(texts).strip()
    if big_text:
        stop_words = set(nltk_stopwords.words("english")) | set(STOPWORDS)

        def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
            idx = abs(hash(word)) % len(HELB_COLORS)
            return HELB_COLORS[idx]

        wc = WordCloud(
            width=900,
            height=400,
            background_color="white",
            stopwords=stop_words,
            color_func=color_func,
        ).generate(big_text)

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig)
    else:
        st.info("No text available to generate word cloud.")
st.markdown("</div>", unsafe_allow_html=True)

# ---------------- DOWNLOAD BUTTON ----------------
st.markdown("---")
st.subheader("Export / Download")
if not filtered.empty:
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download filtered data (CSV)", data=csv_bytes, file_name="helb_mentions_filtered.csv", mime="text/csv")
else:
    st.info("No data to download for the current filters.")

# ---------------- DEBUG / RAW TABLE ----------------
if show_debug:
    st.markdown(
        "<h4 style='text-align: left; color: white;'>TOP 10 LATEST MENTIONS</h4>",
        unsafe_allow_html=True
    )

    debug_df = filtered.sort_values("published_parsed", ascending=False).copy()
    debug_df = debug_df.head(10).reset_index(drop=True)
    debug_df.index = debug_df.index + 1  # start numbering at 1

    # Format date column to dd-mmm-yyyy
    debug_df["published"] = pd.to_datetime(debug_df["published"], errors="coerce").dt.strftime("%d-%b-%Y")

    # Add Open Link button
    debug_df["Link"] = debug_df["link"].apply(
        lambda x: f'<a href="{x}" target="_blank" class="open-link-btn"><button>Open Link</button></a>' if x else ""
    )

    # Select & rename columns
    disp_cols = ["title", "published", "source", "tonality_norm", "Link"]
    debug_df = debug_df[disp_cols]
    debug_df.columns = [c.upper() for c in debug_df.columns]  # UPPERCASE HEADERS

    # Render table with faint grey borders
    st.write(debug_df.to_html(escape=False, index=True), unsafe_allow_html=True)

    # Apply CSS styles
    st.markdown("""
        <style>
        table, th, td {
            border: 1px solid #d9d9d9 !important;
            border-collapse: collapse;
        }
        th {
            color: gold !important;
            text-transform: uppercase;
        }
        .open-link-btn button {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 4px 10px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 12px;
            border-radius: 4px;
            cursor: pointer;
        }
        .open-link-btn button:hover {
            background-color: #45a049;
        }
        </style>
    """, unsafe_allow_html=True)


# ---------------- FOOTER ----------------
st.markdown(
    f"""
    <div class="footer">
        Developed by Fred Okoth
    </div>
    """,
    unsafe_allow_html=True,
)

# close wrapper
st.markdown("</div>", unsafe_allow_html=True)
