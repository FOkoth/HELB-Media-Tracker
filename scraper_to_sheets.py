#!/usr/bin/env python3
"""
scraper_to_sheets.py - Improved HELB mentions scraper

Key improvements:
- primary deduplication by article link
- added more RSS/category feeds for Nation & others
- smarter HTML scraping (article blocks / site-specific fallbacks)
- attempt to extract published date via <time> or meta tags
- safe batch append with fallback, verbose logging
- optional --backfill to ignore dedupe for a single run
"""

import os
import sys
import time
import argparse
import re
from urllib.parse import urljoin, urlparse
import pandas as pd
import feedparser
import requests
from bs4 import BeautifulSoup
from gnews import GNews
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- CONFIG ----------------
SHEET_NAME = "HELB_Mentions"
SPREADSHEET_ID = None  # If you prefer open by key, set here
HEADERS = ["title", "published", "source", "summary", "link", "tonality"]
QUERY = "HELB Kenya"
START_DATE = (2025, 1, 1)

# Keywords - keep as lowercase for matching
KEYWORDS = [
    "helb",
    "higher education loans board",
    "loan board",
    "student loans kenya",
]

# RSS feeds - expanded to include some category feeds where possible
RSS_FEEDS = {
    "Nation (general)": "https://nation.africa/kenya/rss",
    "Nation (business)": "https://nation.africa/business/rss",            # try business
    "Nation (education)": "https://nation.africa/education/rss",        # try education (if available)
    "Capital FM": "https://www.capitalfm.co.ke/news/rss",
    "KBC": "https://www.kbc.co.ke/feed/",
    "Citizen Digital": "https://citizen.digital/rss",
    "Standard Media": "https://www.standardmedia.co.ke/rss/headlines.php",
    # Add more category feeds here if you find them
}

# HTML sources - home / section pages (we will attempt to parse article blocks)
HTML_SOURCES = {
    "Nation": "https://nation.africa/kenya",
    "Standard Media": "https://www.standardmedia.co.ke/kenya",
    "Citizen Digital": "https://citizen.digital/news",
    "Capital FM": "https://www.capitalfm.co.ke/news",
    "KBC": "https://www.kbc.co.ke/category/news/",
    "K24": "https://www.k24tv.co.ke/news/",
    "The Star": "https://www.the-star.co.ke/news/",
    "People Daily": "https://www.pd.co.ke/news/",
    "Tuko": "https://www.tuko.co.ke/",
}

# HTTP request defaults
REQUEST_TIMEOUT = 12
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; HELB-Scraper/1.0; +https://example.org)"}
PAUSE_BETWEEN_REQUESTS = 1.0  # seconds

# Google Sheets scopes
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# ---------------- ARGPARSE ----------------
parser = argparse.ArgumentParser(description="HELB mentions scraper -> Google Sheets")
parser.add_argument("--backfill", action="store_true", help="Ignore dedupe and attempt to fetch all mentions (use once)")
args = parser.parse_args()

# ---------------- AUTH (Service Account JSON required) ----------------
if "ST_SECRETS" in os.environ:
    # (Optional) path for environment-driven deployments - not implemented here
    pass

if not os.path.exists("service_account.json"):
    print("❌ service_account.json missing. Place service_account.json in this folder or adapt authentication.")
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

# ---------------- Read existing records and create dedupe sets ----------------
existing_records = worksheet.get_all_records()
existing_links = {str(r.get("link", "")).strip() for r in existing_records if r.get("link")}
existing_sigs = {
    (str(r.get("title", "")).strip(), str(r.get("published", "")).strip()) for r in existing_records
}
print(f"✅ Existing rows: {len(existing_records)}")
print(f"✅ Existing links: {len(existing_links)}")

# ---------------- Sentiment Analyzer ----------------
nltk.download("vader_lexicon", quiet=True)
sia = SentimentIntensityAnalyzer()


def classify_sentiment(text: str) -> str:
    text = str(text or "")
    score = sia.polarity_scores(text)["compound"]
    return "Positive" if score >= 0.05 else "Negative" if score <= -0.05 else "Neutral"


# keyword contains: use word-boundary-aware matching to reduce false positives
_keyword_patterns = [re.compile(r"\b" + re.escape(k) + r"\b", flags=re.IGNORECASE) for k in KEYWORDS]


def contains_keywords(text: str) -> bool:
    text = str(text or "")
    return any(p.search(text) for p in _keyword_patterns)


# ---------------- Utility functions ----------------
def make_absolute(base_url: str, link: str) -> str:
    if not link:
        return ""
    link = link.strip()
    if link.startswith("//"):
        scheme = urlparse(base_url).scheme or "https"
        return f"{scheme}:{link}"
    if bool(urlparse(link).netloc):
        return link
    return urljoin(base_url, link)


def extract_date_from_soup(soup: BeautifulSoup, base_url: str) -> str:
    # Try <time datetime=...>, meta property og:article:published_time, meta name=date, etc.
    dt = None
    time_tag = soup.find("time")
    if time_tag:
        dt = time_tag.get("datetime") or time_tag.get_text(strip=True)
        if dt:
            try:
                parsed = pd.to_datetime(dt, errors="coerce")
                if not pd.isna(parsed):
                    return parsed.strftime("%Y-%m-%d")
            except Exception:
                pass

    meta_candidates = [
        ('meta', {'property': 'article:published_time'}),
        ('meta', {'property': 'og:published_time'}),
        ('meta', {'name': 'pubdate'}),
        ('meta', {'name': 'publish-date'}),
        ('meta', {'name': 'publication_date'}),
        ('meta', {'name': 'date'}),
        ('meta', {'itemprop': 'datePublished'}),
    ]
    for tag_name, attrs in meta_candidates:
        tag = soup.find(tag_name, attrs=attrs)
        if tag:
            dt = tag.get("content") or tag.get("value") or tag.get_text()
            if dt:
                try:
                    parsed = pd.to_datetime(dt, errors="coerce")
                    if not pd.isna(parsed):
                        return parsed.strftime("%Y-%m-%d")
                except Exception:
                    pass
    # fallback: return empty
    return ""


# ---------------- GNews Fetch (keep but treat as best-effort) ----------------
print("🔎 Fetching GNews (best-effort)...")
g = GNews(language="en", country="KE", start_date=START_DATE)
try:
    articles = g.get_news(QUERY) or []
except Exception as e:
    print(f"⚠️ GNews fetch failed: {e}")
    articles = []
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
def process_rss(feed_name: str, url: str):
    rows = []
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"⚠️ Failed to parse RSS {url}: {e}")
        return rows

    for entry in feed.entries:
        title = str(entry.get("title", "")).strip()
        summary = str(entry.get("summary", "") or entry.get("description") or "").strip()
        link = str(entry.get("link", "")).strip()
        published_raw = str(entry.get("published", "") or entry.get("updated") or "").strip()

        published_parsed = pd.to_datetime(published_raw, errors="coerce")
        published = (
            published_parsed.strftime("%Y-%m-%d")
            if not pd.isna(published_parsed)
            else published_raw
        )

        if not contains_keywords(title + " " + summary):
            continue

        tonality = classify_sentiment(summary if summary else title)
        rows.append([title, published, feed_name, summary, link, tonality])
    return rows


# ---------------- HTML Scraping (smarter) ----------------
def extract_headlines_from_page(source_name: str, base_url: str):
    """
    Returns rows: [title, published, source_name, summary, absolute_link, tonality]
    Uses several heuristics:
      - parse <article> tags and inside look for <a> with headline text
      - fallback: find common headline selectors (h2 a, h3 a, .story-title, .headline, .card__title)
    """
    rows = []
    try:
        resp = requests.get(base_url, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
        if resp.status_code != 200:
            print(f"⚠️ {source_name} returned HTTP {resp.status_code} for {base_url}")
            return rows
        soup = BeautifulSoup(resp.text, "html.parser")

        # Candidate article blocks
        articles = soup.find_all("article")
        seen = set()

        def process_candidate(a_tag, candidate_link):
            if not a_tag:
                return
            title = a_tag.get_text(strip=True)
            if not title or not contains_keywords(title):
                return
            link = make_absolute(base_url, candidate_link)
            if not link:
                return
            # avoid duplicates on the same page
            if link in seen:
                return
            seen.add(link)

            # try to get article page to extract published date and summary (light - optional)
            published = ""
            summary = ""
            try:
                time.sleep(0.25)  # very short polite pause
                art_resp = requests.get(link, timeout=REQUEST_TIMEOUT, headers=REQUEST_HEADERS)
                if art_resp.status_code == 200:
                    art_soup = BeautifulSoup(art_resp.text, "html.parser")
                    published = extract_date_from_soup(art_soup, link)
                    # summary fallback: meta description or first paragraph inside article
                    meta_desc = art_soup.find("meta", attrs={"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        summary = meta_desc.get("content").strip()
                    else:
                        p = art_soup.find("p")
                        if p:
                            summary = p.get_text(strip=True)
            except Exception:
                # If retrieving article fails, we still keep title + link
                pass

            tonality = classify_sentiment(summary if summary else title)
            rows.append([title, published, source_name, summary, link, tonality])

        # 1) Use <article> blocks
        for art in articles:
            # find headline anchor inside article
            a_tag = art.find(["a"], href=True)
            if a_tag:
                process_candidate(a_tag, a_tag.get("href"))

        # 2) Common headline selectors (fallback)
        selectors = [
            ("h1 a",), ("h2 a",), ("h3 a",), (".story-title a",), (".headline a",), (".card__title a",), (".teaser__title a",)
        ]
        for sel_tuple in selectors:
            sel = sel_tuple[0]
            for a in soup.select(sel):
                process_candidate(a, a.get("href"))

        # 3) As last resort: any <a> that looks like an article (href contains '/news' or '/article' or '/stories')
        if not rows:
            for a in soup.find_all("a", href=True):
                href = a.get("href")
                if not href:
                    continue
                if any(p in href.lower() for p in ["/news", "/article", "/stories", "/story", "/business", "/education"]):
                    if a.get_text(strip=True) and contains_keywords(a.get_text(strip=True)):
                        process_candidate(a, href)

    except Exception as e:
        print(f"⚠️ Failed to scrape {source_name} ({base_url}): {e}")
    return rows


# ---------------- Collect All Articles ----------------
new_rows = []

# GNews: prefer link dedupe
for a in articles:
    row = process_gnews(a)
    title, published, source, summary, link, tonality = row
    link = link.strip()
    if not args.backfill:
        if link and link in existing_links:
            continue
        # fallback signature dedupe if link missing
        if (not link) and ((title.strip(), published.strip()) in existing_sigs):
            continue
    if contains_keywords(title + " " + summary):
        new_rows.append([title, published, source, summary, link, tonality])

print(f"🆕 Candidate new rows from GNews: {len(new_rows)}")

# RSS feeds
for source, url in RSS_FEEDS.items():
    try:
        rss_rows = process_rss(source, url)
    except Exception as e:
        print(f"⚠️ RSS processing error for {source}: {e}")
        rss_rows = []
    for row in rss_rows:
        title, published, src, summary, link, tonality = row
        link = link.strip()
        if not args.backfill:
            if link and link in existing_links:
                continue
            if (not link) and ((title.strip(), published.strip()) in existing_sigs):
                continue
        new_rows.append([title, published, src, summary, link, tonality])
    time.sleep(PAUSE_BETWEEN_REQUESTS)

print("🆕 After RSS fetch, candidate rows:", len(new_rows))

# HTML scrapers (site-specific)
for source, base_url in HTML_SOURCES.items():
    try:
        html_rows = extract_headlines_from_page(source, base_url)
    except Exception as e:
        print(f"⚠️ HTML fetch failed for {source}: {e}")
        html_rows = []
    for row in html_rows:
        title, published, src, summary, link, tonality = row
        link = link.strip()
        if not args.backfill:
            if link and link in existing_links:
                continue
            if (not link) and ((title.strip(), published.strip()) in existing_sigs):
                continue
        new_rows.append([title, published, src, summary, link, tonality])
    time.sleep(PAUSE_BETWEEN_REQUESTS)

# Deduplicate within new_rows by link or signature
final_rows = []
seen_links_local = set()
seen_sigs_local = set()
for r in new_rows:
    title, published, src, summary, link, tonality = r
    link_norm = link.strip()
    sig = (title.strip(), str(published).strip())
    if link_norm:
        if link_norm in seen_links_local:
            continue
        seen_links_local.add(link_norm)
    else:
        if sig in seen_sigs_local:
            continue
        seen_sigs_local.add(sig)
    final_rows.append([title, published, src, summary, link_norm, tonality])

print(f"🔎 Final deduped new rows to append: {len(final_rows)}")

# ---------------- Append to Sheet ----------------
if not final_rows:
    print("ℹ️ No new mentions to append.")
else:
    # If sheet empty, add headers
    try:
        if len(worksheet.get_all_values()) == 0:
            worksheet.append_row(HEADERS, value_input_option="USER_ENTERED")
            time.sleep(1)
    except Exception:
        # ignore

    try:
        # Append in batches of 50 to avoid huge single calls
        BATCH = 50
        for i in range(0, len(final_rows), BATCH):
            batch = final_rows[i : i + BATCH]
            try:
                worksheet.append_rows(batch, value_input_option="USER_ENTERED")
                print(f"✅ Appended batch size {len(batch)}")
            except Exception as e:
                print(f"⚠️ Batch append failed ({e}) - falling back to row-by-row for this batch")
                for r in batch:
                    try:
                        worksheet.append_row(r, value_input_option="USER_ENTERED")
                        time.sleep(0.2)
                    except Exception as e_row:
                        print(f"⚠️ Row append failed for {r}: {e_row}")
    except Exception as e:
        print(f"⚠️ Unexpected append error: {e}")

print("🎉 Done.")
