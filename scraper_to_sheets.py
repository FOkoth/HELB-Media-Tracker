"""
scraper_to_sheets.py
Scraper for HELB mentions in Kenyan news (from Jan 1, 2025).

Sources:
1. Google News (via gnews)
2. Kenyan Media RSS feeds
3. Direct HTML scrapers (Nation, Standard, Citizen Digital, Capital FM, KBC, K24, Star, People Daily, Tuko)

Appends only NEW mentions to Google Sheet (deduplicated by link/title+date).
"""

import os, sys, time
import pandas as pd
import feedparser
import requests
from bs4 import BeautifulSoup
from gnews import GNews
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urljoin

# ---------------- CONFIG ----------------
SHEET_NAME = "HELB_Mentions"
SPREADSHEET_ID = None
HEADERS = ["title", "published", "source", "summary", "link", "tonality"]

QUERY = "HELB Kenya"
START_DATE = (2025, 1, 1)

KEYWORDS = [
    "helb",
    "higher education loans board",
    "loan board",
    "tvet funding",
    "Geoffrey Monari",
    "student-centred funding model",
    "student centred funding model",
    "new funding model",
    "higher education financier",
    "student loans kenya",
]

RSS_FEEDS = {
    "Nation": "https://nation.africa/kenya/rss",
    "Capital FM": "https://www.capitalfm.co.ke/news/rss",
    "KBC": "https://www.kbc.co.ke/feed/",
    "Citizen Digital": "https://citizen.digital/rss",
    "Standard Media": "https://www.standardmedia.co.ke/rss/headlines.php",
}

HTML_SOURCES = {
    "Nation (General)": "https://nation.africa/kenya/news",
    "Nation (Education)": "https://nation.africa/kenya/news/education",
    "Standard Media": "https://www.standardmedia.co.ke/kenya",
    "Citizen Digital": "https://citizen.digital/news",
    "Capital FM": "https://www.capitalfm.co.ke/news",
    "KBC": "https://www.kbc.co.ke/category/news/",
    "K24": "https://www.k24tv.co.ke/news/",
    "The Star": "https://www.the-star.co.ke/news/",
    "People Daily": "https://www.pd.co.ke/news/",
    "Tuko (General)": "https://www.tuko.co.ke/",
    "Tuko (Money)": "https://www.tuko.co.ke/business-economy/money/",
}

# ---------------- AUTH ----------------
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

if not os.path.exists("service_account.json"):
    print("❌ service_account.json missing.")
    sys.exit(1)

creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPES)
gc = gspread.authorize(creds)

try:
    if SPREADSHEET_ID:
        sh = gc.open_by_key(SPREADSHEET_ID)
    else:
        sh = gc.open(SHEET_NAME)
    worksheet = sh.get_worksheet(0)
except Exception as e:
    print(f"❌ Failed to open sheet: {e}")
    sys.exit(1)

# ---------------- Existing Records ----------------
existing_records = worksheet.get_all_records()
existing_links = {str(r.get("link", "")).strip() for r in existing_records if r.get("link")}
existing_sigs = {(str(r.get("title", "")).strip(), str(r.get("published", "")).strip()) for r in existing_records}
print(f"✅ Existing rows: {len(existing_records)}")

# ---------------- Sentiment Analyzer ----------------
nltk.download("vader_lexicon", quiet=True)
sia = SentimentIntensityAnalyzer()

def classify_sentiment(text):
    score = sia.polarity_scores(text)["compound"]
    return "Positive" if score >= 0.05 else "Negative" if score <= -0.05 else "Neutral"

def contains_keywords(text):
    text_low = text.lower()
    return any(k in text_low for k in KEYWORDS)

# ---------------- GNews Fetch ----------------
g = GNews(language="en", country="KE", start_date=START_DATE)
articles = g.get_news(QUERY) or []
print(f"📰 GNews articles fetched: {len(articles)}")

def process_gnews(a):
    title = str(a.get("title", "")).strip()
    summary = str(a.get("description") or a.get("summary") or "").strip()
    link = str(a.get("url") or a.get("link") or "").strip()
    published_raw = str(a.get("published date") or a.get("published") or "").strip()
    pub = a.get("publisher")
    source = pub.get("title", "") if isinstance(pub, dict) else str(a.get("source") or "").strip()

    published_parsed = pd.to_datetime(published_raw, errors="coerce")
    published = published_parsed.strftime("%Y-%m-%d") if not pd.isna(published_parsed) else published_raw
    tonality = classify_sentiment(summary if summary else title)

    return [title, published, source, summary, link, tonality]

# ---------------- RSS Fetch ----------------
def process_rss(feed_name, url):
    rows = []
    feed = feedparser.parse(url)
    for entry in feed.entries:
        title = str(entry.get("title", "")).strip()
        summary = str(entry.get("summary", "")).strip()
        link = str(entry.get("link", "")).strip()
        published_raw = str(entry.get("published", "")).strip()
        published_parsed = pd.to_datetime(published_raw, errors="coerce")
        published = published_parsed.strftime("%Y-%m-%d") if not pd.isna(published_parsed) else published_raw

        if not contains_keywords(title + " " + summary):
            continue

        tonality = classify_sentiment(summary if summary else title)
        rows.append([title, published, feed_name, summary, link, tonality])
    print(f"✅ {feed_name} RSS yielded {len(rows)} mentions")
    return rows

# ---------------- HTML Scraping ----------------
def process_html(source_name, url):
    rows = []
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            print(f"⚠️ {source_name} returned {resp.status_code}")
            return rows

        soup = BeautifulSoup(resp.text, "html.parser")
        candidates = soup.find_all(["a", "h2", "h3", "article", "div"], limit=500)

        for c in candidates:
            title = c.get_text(strip=True)
            link = c.get("href")

            if not title or not link:
                continue

            link = urljoin(url, link)

            if not contains_keywords(title):
                continue

            published = ""  # most sites don’t expose date easily
            tonality = classify_sentiment(title)
            rows.append([title, published, source_name, "", link, tonality])

        print(f"✅ {source_name} scraped {len(rows)} mentions (pre-dedup).")

    except Exception as e:
        print(f"⚠️ Failed to scrape {source_name}: {e}")
    return rows

# ---------------- Collect All Articles ----------------
new_rows = []

# GNews
for a in articles:
    row = process_gnews(a)
    sig = (row[0], row[1])
    if (row[4] and row[4] in existing_links) or (sig in existing_sigs):
        continue
    if contains_keywords(row[0] + " " + row[3]):
        new_rows.append(row)

# RSS
for source, url in RSS_FEEDS.items():
    rss_rows = process_rss(source, url)
    for row in rss_rows:
        sig = (row[0], row[1])
        if (row[4] and row[4] in existing_links) or (sig in existing_sigs):
            continue
        new_rows.append(row)

# HTML
for source, url in HTML_SOURCES.items():
    html_rows = process_html(source, url)
    for row in html_rows:
        sig = (row[0], row[1])
        if (row[4] and row[4] in existing_links) or (sig in existing_sigs):
            continue
        new_rows.append(row)

# ---------------- Append to Sheet ----------------
if not new_rows:
    print("ℹ️ No new mentions to append.")
else:
    if len(worksheet.get_all_values()) == 0:
        worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")
        time.sleep(1)

    try:
        worksheet.append_rows(new_rows, value_input_option="USER_ENTERED")
        print(f"✅ Appended {len(new_rows)} new mentions.")
    except Exception as e:
        print(f"⚠️ Batch append failed: {e}. Trying row-by-row...")
        for r in new_rows:
            worksheet.append_row(r, value_input_option="USER_ENTERED")
        print(f"✅ Appended {len(new_rows)} mentions (row-by-row).")

print("🎉 Done.")
