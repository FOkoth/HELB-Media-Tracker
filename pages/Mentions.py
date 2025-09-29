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

        /* Sidebar styling - navigation area is dark gold, select inputs shown on green */
        section[data-testid="stSidebar"] {
            background-color: #b8860b; /* dark gold */
        }
        section[data-testid="stSidebar"] .css-1d391kg, 
        section[data-testid="stSidebar"] label, 
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] .stSelectbox.__webio__ {
            color: white !important;
        }

        /* Make underlying select control area green to mimic "navigation items" */
        section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
            background-color: #006400 !important; /* green */
            color: white !important;
            border-radius: 6px;
            padding-left: 6px;
        }

        /* Card style for mention items */
        .mention-card {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
        }

        .mention-meta {
            font-size: 13px;
            color: rgba(255,255,255,0.95);
            margin-bottom: 6px;
        }
        .mention-title {
            font-weight: 700;
            margin-bottom: 6px;
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
    # Load persistent CSV if it exists locally, otherwise load from public CSV link
    if os.path.exists(LOCAL_CSV):
        df = pd.read_csv(LOCAL_CSV)
    else:
        df = pd.read_csv(CSV_URL)

    # normalize column names to lowercase for easier handling
    df.columns = [c.strip().lower() for c in df.columns]

    # Ensure essential columns exist
    for col in ["title", "summary", "source", "tonality", "link", "published"]:
        if col not in df.columns:
            df[col] = ""

    # Normalize tonality text
    df["tonality"] = df["tonality"].astype(str).str.strip().replace({"nan": ""})
    df.loc[df["tonality"] == "", "tonality"] = "Unknown"
    df["tonality"] = df["tonality"].str.capitalize()

    # Parse published date safely
    df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
    try:
        # If it is timezone-aware, convert to Nairobi; if not, this will throw and be ignored
        df["published_parsed"] = df["published_parsed"].dt.tz_convert("Africa/Nairobi")
    except Exception:
        # attempt to localize naive datetimes (best-effort)
        try:
            df["published_parsed"] = pd.to_datetime(df["published"], errors="coerce")
        except Exception:
            df["published_parsed"] = df["published_parsed"]

    # Human-friendly date/time strings (empty when missing)
    df["DATE"] = df["published_parsed"].dt.strftime("%d-%b-%Y").fillna("")
    df["TIME"] = df["published_parsed"].dt.strftime("%H:%M").fillna("")

    # YEAR as string (so selectbox options are strings)
    def safe_year(x):
        if pd.isna(x):
            return ""
        try:
            return str(int(x.year))
        except Exception:
            return ""

    df["YEAR"] = df["published_parsed"].apply(lambda x: safe_year(x))

    # MONTH full name
    df["MONTH"] = df["published_parsed"].dt.strftime("%B").fillna("")

    # QUARTER as readable label (e.g., '2025Q3')
    df["QUARTER"] = df["published_parsed"].dt.to_period("Q").astype(str).fillna("")

    # Financial year starting in July (e.g., '2024/2025'), empty if no date
    def get_fin_year(x):
        if pd.isna(x):
            return ""
        y = x.year
        m = x.month
        if m >= 7:
            return f"{y}/{y+1}"
        return f"{y-1}/{y}"

    df["FIN_YEAR"] = df["published_parsed"].apply(lambda x: get_fin_year(x) if not pd.isna(x) else "")

    # Ensure string types and uppercase for UI column names
    df["title"] = df["title"].fillna("").astype(str)
    df["summary"] = df["summary"].fillna("").astype(str)
    df["source"] = df["source"].fillna("").astype(str)
    df["link"] = df["link"].fillna("").astype(str)

    rename_map = {
        "title": "TITLE",
        "summary": "SUMMARY",
        "source": "SOURCE",
        "tonality": "TONALITY",
        "link": "LINK",
    }
    df = df.rename(columns=rename_map)

    # Ensure the new columns exist after rename (so code later can reference uppercase names)
    for col in ["DATE", "TIME", "YEAR", "MONTH", "QUARTER", "FIN_YEAR"]:
        if col not in df.columns:
            df[col] = ""

    return df

# ---------- UTILS ----------
def safe_sort_key(val: str):
    """Sort numbers numerically where possible, otherwise lexicographically (case-insensitive)."""
    try:
        if str(val).isdigit():
            return (0, int(val))
        # handle common year-like '2024/2025' by parsing first 4-digit prefix
        if "/" in str(val) and str(val).split("/")[0].isdigit():
            return (0, int(str(val).split("/")[0]))
    except Exception:
        pass
    return (1, str(val).lower())

def make_options(series):
    """Return ['All', ...sorted unique non-empty strings...] from a pandas Series"""
    vals = []
    for v in pd.Series(series).dropna().unique():
        s = str(v).strip()
        if s == "" or s.lower() == "nan":
            continue
        vals.append(s)
    unique = sorted(set(vals), key=safe_sort_key)
    return ["All"] + unique

# ---------- SESSION STATE & DATA ----------
if "mentions_df" not in st.session_state:
    st.session_state["mentions_df"] = load_data()

df = st.session_state["mentions_df"]

if df.empty:
    st.info("No data available.")
    st.stop()

# Keep df indexed 0..n-1 for consistent session_state mapping
df = df.sort_values(by="published_parsed", ascending=False).reset_index(drop=True)

# Tonality mapping persistence (one entry per row index)
if "tonality_map" not in st.session_state:
    st.session_state["tonality_map"] = {i: df.at[i, "TONALITY"] for i in df.index}

# ---------- COLOR CODES ----------
COLORS = {
    "Positive": "#3b8132",
    "Neutral": "#6E6F71",
    "Negative": "#d1001f",
    "Unknown": "#808080"
}

# ---------- FILTERS (safe option generation) ----------
st.sidebar.subheader("Filters")

tonality_options = make_options(df["TONALITY"])
fin_year_options = make_options(df["FIN_YEAR"])
quarter_options = make_options(df["QUARTER"])
year_options = make_options(df["YEAR"])
month_options = make_options(df["MONTH"])

tonality_filter = st.sidebar.selectbox("Filter by Tonality", tonality_options)
fin_year_filter = st.sidebar.selectbox("Filter by Financial Year", fin_year_options)
quarter_filter = st.sidebar.selectbox("Filter by Quarter", quarter_options)
year_filter = st.sidebar.selectbox("Filter by Year", year_options)
month_filter = st.sidebar.selectbox("Filter by Month", month_options)

# ---------- EDITOR PANEL (optional, scrollable) ----------
if is_editor:
    st.sidebar.subheader("✏️ Edit Tonality for Visible Mentions")
    edited_values = {}
    st.sidebar.markdown('<div style="max-height:500px; overflow-y:auto; padding-right:5px;">', unsafe_allow_html=True)
    # show editors for every visible row (we'll compute visible mask later, but pre-define)
    # Note: We'll populate editors after we calculate mask, so skip here

# ---------- APPLY FILTERS ----------
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

# ---------- EDITOR UI FOR FILTERED ROWS ----------
if is_editor:
    # Build editable widgets for only the filtered rows (so editor adjusts what's visible)
    edited_values = {}
    for i in df_filtered.index:
        current = st.session_state["tonality_map"].get(i, df.at[i, "TONALITY"])
        # create a selectbox per row, unique key uses index
        new_val = st.sidebar.selectbox(
            f"{i+1}. {df.at[i, 'TITLE'][:60]}...",
            options=["Positive", "Neutral", "Negative", "Unknown"],
            index=["Positive", "Neutral", "Negative", "Unknown"].index(current) if current in ["Positive","Neutral","Negative","Unknown"] else 3,
            key=f"tonality_editor_{i}"
        )
        edited_values[i] = new_val

    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    if st.sidebar.button("💾 Save Tonality Updates"):
        # apply changes into session_state map and write out CSV
        for idx, val in edited_values.items():
            st.session_state["tonality_map"][idx] = val
        updated_df = df.copy()
        updated_df["TONALITY"] = [st.session_state["tonality_map"].get(i, updated_df.at[i, "TONALITY"]) for i in updated_df.index]
        try:
            updated_df.to_csv(LOCAL_CSV, index=False)
            st.sidebar.success("Tonality changes applied and saved!")
            # update session data
            st.session_state["mentions_df"] = updated_df
            df = updated_df
            df_filtered = df[mask]
        except Exception as e:
            st.sidebar.error(f"Failed to save CSV: {e}")

# ---------- DISPLAY MENTIONS ----------
if df_filtered.empty:
    st.info("No mentions for the selected filters.")
else:
    for display_pos, idx in enumerate(df_filtered.index, start=1):
        row = df_filtered.loc[idx]
        tonality = st.session_state["tonality_map"].get(idx, row["TONALITY"])
        bg_color = COLORS.get(tonality, "#ffffff")
        text_color = "#ffffff" if tonality in ["Positive", "Negative"] else "#000000"

        st.markdown(
            f"""
            <div class="mention-card" style="background-color:{bg_color}; color:{text_color};">
                <div class="mention-meta"><b>{display_pos}. {row['DATE']} {row['TIME']}</b> — <i>{row['SOURCE']}</i></div>
                <div class="mention-title">{row['TITLE']}</div>
                <div class="mention-summary">{row['SUMMARY']}</div>
                <div style="margin-top:8px;"><b>Tonality:</b> {tonality}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if row["LINK"].startswith("http"):
            st.markdown(f"[🔗 Read Full Story]({row['LINK']})")
        st.markdown("---")

# ---------- DOWNLOAD UPDATED CSV ----------
st.subheader("📥 Export Updated Mentions")
export_df = df_filtered.copy()
export_df["TONALITY"] = [st.session_state["tonality_map"].get(i, export_df.at[i, "TONALITY"]) for i in export_df.index]
csv_bytes = export_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Download Mentions CSV",
    data=csv_bytes,
    file_name="updated_mentions.csv",
    mime="text/csv"
)
