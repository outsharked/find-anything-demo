#!/usr/bin/env python3
"""
Fetch live content from Wikinews and arXiv and write it to the live content
directory. Designed to be run periodically (e.g. hourly) inside the container;
find-scan is run afterward to pick up the changes.

Usage:
  fetch_live.py [--backfill] [live-dir]

  --backfill   Also fetch articles from the last 30 days (run once on first start)

Outputs:
  <live-dir>/wikinews/<safe-title>.txt  — one file per Wikinews article
  <live-dir>/arxiv/<arxiv-id>.txt       — one file per arXiv abstract
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKFILL  = "--backfill" in sys.argv
args      = [a for a in sys.argv[1:] if not a.startswith("--")]
LIVE_DIR  = Path(args[0]) if args else Path("/content/live")
NEWS_DIR  = LIVE_DIR / "wikinews"
ARXIV_DIR = LIVE_DIR / "arxiv"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
ARXIV_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "find-anything-demo/1.0 (https://github.com/outsharked/find-anything)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read()
        except Exception as e:
            if attempt == retries - 1:
                print(f"  WARN: {url}: {e}")
                return b""
            time.sleep(2 ** attempt)
    return b""


def get_json(url: str) -> dict:
    data = fetch(url)
    try:
        return json.loads(data) if data else {}
    except Exception:
        return {}


def safe_filename(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', title)[:200]


def strip_wikitext(text: str) -> str:
    """Remove common wiki markup to leave readable plain text."""
    while "{{" in text:
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', text)
    text = re.sub(r"'{2,}", '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Wikinews ──────────────────────────────────────────────────────────────────

WIKINEWS_API = "https://en.wikinews.org/w/api.php"


def wikinews_titles_by_date(start: str, end: str, limit: int = 500) -> list[str]:
    """Return article titles for the date range (MediaWiki timestamp format)."""
    params = urllib.parse.urlencode({
        "action":      "query",
        "list":        "recentchanges",
        "rcnamespace": "0",
        "rclimit":     limit,
        "rctype":      "new",
        "rcprop":      "title|timestamp",
        "rcstart":     end,    # MediaWiki: rcstart > rcend (newest first)
        "rcend":       start,
        "format":      "json",
    })
    data = get_json(f"{WIKINEWS_API}?{params}")
    return [rc["title"] for rc in data.get("query", {}).get("recentchanges", [])]


def wikinews_recent_titles(limit: int = 60) -> list[str]:
    """Return recently changed/created article titles."""
    params = urllib.parse.urlencode({
        "action":      "query",
        "list":        "recentchanges",
        "rcnamespace": "0",
        "rclimit":     limit,
        "rctype":      "new|edit",
        "rcprop":      "title",
        "format":      "json",
    })
    data = get_json(f"{WIKINEWS_API}?{params}")
    return [rc["title"] for rc in data.get("query", {}).get("recentchanges", [])]


def wikinews_article_text(title: str, _depth: int = 0) -> str | None:
    """Return plain-text article body, following one redirect."""
    if _depth > 1:
        return None
    params = urllib.parse.urlencode({
        "action": "parse",
        "page":   title,
        "prop":   "wikitext",
        "format": "json",
    })
    data = get_json(f"{WIKINEWS_API}?{params}")
    wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
    if not wikitext:
        return None
    redirect = re.match(r"#REDIRECT\s*\[\[(.+?)\]\]", wikitext, re.IGNORECASE)
    if redirect:
        return wikinews_article_text(redirect.group(1), _depth + 1)
    return strip_wikitext(wikitext) or None


def save_wikinews_titles(titles: list[str], max_articles: int) -> int:
    seen: set[str] = set()
    saved = 0
    for title in titles:
        if title in seen or title.startswith("Wikinews:"):
            continue
        seen.add(title)
        dest = NEWS_DIR / f"{safe_filename(title)}.txt"
        if dest.exists():
            saved += 1
            continue
        text = wikinews_article_text(title)
        if not text or len(text) < 100:
            continue
        dest.write_text(f"{title}\n\n{text}\n", encoding="utf-8")
        print(f"  news  {title[:70]}")
        saved += 1
        if saved >= max_articles:
            break
        time.sleep(0.3)
    return saved


def fetch_wikinews() -> None:
    print("\n=== Wikinews ===")

    if BACKFILL:
        # Fetch articles from the last 30 days in weekly chunks
        now   = datetime.now(timezone.utc)
        chunk = timedelta(days=7)
        total = 0
        for week in range(4):
            end_dt   = now - chunk * week
            start_dt = end_dt - chunk
            end_str   = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            titles = wikinews_titles_by_date(start_str, end_str, limit=200)
            n = save_wikinews_titles(titles, max_articles=50)
            total += n
            print(f"  week -{week+1}: {n} articles from {start_str[:10]} to {end_str[:10]}")
        print(f"  backfill total: {total} Wikinews articles")
    else:
        titles = wikinews_recent_titles(80)
        saved  = save_wikinews_titles(titles, max_articles=40)

        # Remove files that are no longer in the recent window
        current_names = {safe_filename(t) + ".txt" for t in titles}
        for f in NEWS_DIR.glob("*.txt"):
            if f.name not in current_names:
                f.unlink(missing_ok=True)

    print(f"  {NEWS_DIR} now has {len(list(NEWS_DIR.glob('*.txt')))} files")


# ── arXiv ─────────────────────────────────────────────────────────────────────

ARXIV_API  = "https://export.arxiv.org/api/query"
ARXIV_NS   = {
    "atom":   "http://www.w3.org/2005/Atom",
    "arxiv":  "http://arxiv.org/schemas/atom",
}
ARXIV_CATS = ["cs.AI", "cs.CL", "cs.LG", "cs.CV"]


def fetch_arxiv_category(cat: str, max_results: int = 25, start: int = 0) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": f"cat:{cat}",
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
        "max_results":  max_results,
        "start":        start,
    })
    raw = fetch(f"{ARXIV_API}?{params}")
    if not raw:
        return []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    def elem_text(parent: ET.Element, tag: str) -> str:
        el = parent.find(tag, ARXIV_NS)
        return (el.text or "") if el is not None else ""

    papers = []
    for entry in root.findall("atom:entry", ARXIV_NS):
        id_url    = elem_text(entry, "atom:id")
        title     = elem_text(entry, "atom:title")
        summary   = elem_text(entry, "atom:summary")
        published = elem_text(entry, "atom:published")
        authors   = [
            elem_text(a, "atom:name")
            for a in entry.findall("atom:author", ARXIV_NS)
        ]
        arxiv_id  = id_url.rsplit("/", 1)[-1].replace(".", "_")
        papers.append({
            "id":        arxiv_id,
            "title":     title.strip().replace("\n", " "),
            "summary":   summary.strip(),
            "authors":   authors,
            "published": published[:10],
            "category":  cat,
            "url":       id_url.strip(),
        })
    return papers


def write_arxiv_paper(p: dict) -> None:
    dest = ARXIV_DIR / f"{p['id']}.txt"
    if dest.exists():
        return
    author_str = ", ".join(p["authors"][:5])
    if len(p["authors"]) > 5:
        author_str += f" and {len(p['authors']) - 5} others"
    content = (
        f"{p['title']}\n\n"
        f"Authors: {author_str}\n"
        f"Category: {p['category']}\n"
        f"Published: {p['published']}\n"
        f"URL: {p['url']}\n\n"
        f"{p['summary']}\n"
    )
    dest.write_text(content, encoding="utf-8")


def fetch_arxiv() -> None:
    print("\n=== arXiv ===")

    if BACKFILL:
        # Fetch ~30 days back: 5 pages × 25 results × 4 categories ≈ 500 papers
        pages_per_cat = 5
        for cat in ARXIV_CATS:
            cat_total = 0
            for page in range(pages_per_cat):
                papers = fetch_arxiv_category(cat, max_results=25, start=page * 25)
                for p in papers:
                    write_arxiv_paper(p)
                    cat_total += 1
                time.sleep(3)  # arXiv rate limit: 3 seconds between requests
            print(f"  {cat}: {cat_total} papers (backfill)")
    else:
        for cat in ARXIV_CATS:
            papers = fetch_arxiv_category(cat, max_results=25)
            for p in papers:
                write_arxiv_paper(p)
            print(f"  {cat}: {len(papers)} papers")
            time.sleep(3)

    # Cap total files at 600 (keep most recent by mtime)
    all_files = sorted(ARXIV_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True)
    for old in all_files[600:]:
        old.unlink(missing_ok=True)

    print(f"  {ARXIV_DIR} now has {len(list(ARXIV_DIR.glob('*.txt')))} files")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = "backfill" if BACKFILL else "update"
    print(f"Fetching live content ({mode}) into {LIVE_DIR}")
    fetch_wikinews()
    fetch_arxiv()
    print("\nDone.")
