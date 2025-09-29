# Mentions.py
import streamlit as st
import pandas as pd
import os

# ---------- CONFIG ----------
CSV_URL = "https://docs.google.com/spreadsheets/d/10LcDId4y2vz5mk7BReXL303-OBa2QxsN3drUcefpdSQ/export?format=csv"
LOCAL_CSV = "persistent_mentions.csv"  # File to save updates
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
    else:
        df["published_parsed"] = pd.NaT
        df["DATE"] = ""
        df["TIME"] = ""
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

# ---------- EDITOR PANEL (SCROLLABLE) ----------
if is_editor:
    st.sidebar.subheader("Edit Tonality")
    edited_values = {}

    with st.sidebar.container():
        st.markdown(
            '<div style="max-height:600px; overflow-y:auto; padding-right:5px;">', 
            unsafe_allow_html=True
        )
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

    # Execute update button
    if st.sidebar.button("Execute Update"):
        for idx, val in edited_values.items():
            st.session_state["tonality_map"][idx] = val
        # Save updated CSV for persistence
        updated_df = df.copy()
        updated_df["TONALITY"] = [st.session_state["tonality_map"][i] for i in df.index]
        updated_df.to_csv(LOCAL_CSV, index=False)
        st.sidebar.success("Tonality changes applied and saved! Colours updated below.")

# ---------- DISPLAY MENTIONS ----------
st.title("📰 Mentions — Media Coverage")
st.subheader("Mentions List")

for i in df.index:
    row = df.loc[i]
    tonality = st.session_state["tonality_map"][i]
    bg_color = COLORS.get(tonality, "#ffffff")
    text_color = "#ffffff" if tonality in ["Positive", "Negative"] else "#ffffff"

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
