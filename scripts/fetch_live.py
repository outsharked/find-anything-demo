#!/usr/bin/env python3
"""
Fetch live content from Wikinews and arXiv and write it to the live content
directory. Designed to be run periodically (e.g. hourly) inside the container;
find-scan is run afterward to pick up the changes.

Usage:
  fetch_live.py [--backfill] [live-dir]

  --backfill   Also fetch articles from the last 30 days (run once on first start)

Outputs:
  <live-dir>/wikinews/<date> - <title>/index.html   — article with images
  <live-dir>/wikinews/<date> - <title>/media/       — downloaded images
  <live-dir>/arxiv/<arxiv-id>.txt                   — one file per arXiv abstract
"""

import html as html_mod
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

MAX_IMAGES_PER_ARTICLE = 6


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
    return re.sub(r'[\\/:*?"<>|]', '_', title)[:180]


# ── Wikinews ──────────────────────────────────────────────────────────────────

WIKINEWS_API  = "https://en.wikinews.org/w/api.php"
WIKINEWS_REST = "https://en.wikinews.org/api/rest_v1/page"

HTML_WRAPPER = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  body       {{ font-family: Georgia, serif; max-width: 820px; margin: 2rem auto;
                padding: 0 1.5rem; line-height: 1.75; color: #1a1a1a; }}
  h1         {{ font-family: sans-serif; font-size: 1.8rem; margin-bottom: .2rem; }}
  .meta      {{ font-size: .85rem; color: #666; margin-bottom: 1.8rem; }}
  img        {{ max-width: 100%; height: auto; display: block; }}
  figure     {{ margin: 1.5rem 0; }}
  figcaption {{ font-size: .8rem; color: #555; margin-top: .3rem; }}
  table      {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9rem; }}
  td, th     {{ border: 1px solid #ccc; padding: .4rem .6rem; }}
  a          {{ color: #0645ad; }}
  .thumb     {{ float: right; clear: right; margin: 0 0 1rem 1.5rem; max-width: 280px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Published {date} &middot;
  <a href="https://en.wikinews.org/wiki/{url_title}" target="_blank">View on Wikinews</a></p>
{body}
</body>
</html>
"""


def wikinews_titles_by_date(start: str, end: str, limit: int = 500) -> list[tuple[str, str]]:
    """Return (title, date) pairs for the date range (MediaWiki timestamp format)."""
    params = urllib.parse.urlencode({
        "action":      "query",
        "list":        "recentchanges",
        "rcnamespace": "0",
        "rclimit":     limit,
        "rctype":      "new",
        "rcprop":      "title|timestamp",
        "rcstart":     end,
        "rcend":       start,
        "format":      "json",
    })
    data = get_json(f"{WIKINEWS_API}?{params}")
    return [
        (rc["title"], rc.get("timestamp", "")[:10])
        for rc in data.get("query", {}).get("recentchanges", [])
    ]


def wikinews_recent_titles(limit: int = 60) -> list[tuple[str, str]]:
    """Return recently changed/created (title, date) pairs."""
    params = urllib.parse.urlencode({
        "action":      "query",
        "list":        "recentchanges",
        "rcnamespace": "0",
        "rclimit":     limit,
        "rctype":      "new|edit",
        "rcprop":      "title|timestamp",
        "format":      "json",
    })
    data = get_json(f"{WIKINEWS_API}?{params}")
    return [
        (rc["title"], rc.get("timestamp", "")[:10])
        for rc in data.get("query", {}).get("recentchanges", [])
    ]


def wikinews_fetch_html(title: str) -> str | None:
    """Fetch rendered HTML body for the article from the REST API."""
    encoded = urllib.parse.quote(title.replace(' ', '_'), safe='')
    raw = fetch(f"{WIKINEWS_REST}/html/{encoded}")
    if not raw:
        return None
    html = raw.decode('utf-8', errors='replace')
    # Extract just the body content from the full document
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else html


def _download_images(html_body: str, media_dir: Path) -> str:
    """Download Wikimedia images into media/ and rewrite src attributes."""
    img_re = re.compile(r'src="((?:https?:)?//upload\.wikimedia\.org/[^"]+)"')
    downloaded = 0

    def replace(m: re.Match) -> str:
        nonlocal downloaded
        if downloaded >= MAX_IMAGES_PER_ARTICLE:
            return m.group(0)
        url = html_mod.unescape(m.group(1))  # decode &amp; → &
        if url.startswith('//'):
            url = 'https:' + url
        # Skip thumbnails narrower than 150px
        px = re.search(r'/(\d+)px-', url)
        if px and int(px.group(1)) < 150:
            return m.group(0)
        clean_url = url.split('?')[0]  # strip query string for fetching
        raw_name = urllib.parse.unquote(clean_url.rsplit('/', 1)[-1])
        filename = re.sub(r'[\\/:*?"<>|]', '_', raw_name)[:120]
        if not filename:
            return m.group(0)
        media_dir.mkdir(exist_ok=True)
        dest = media_dir / filename
        if not dest.exists():
            data = fetch(clean_url) or fetch(url)
            if not data:
                return m.group(0)
            dest.write_bytes(data)
        downloaded += 1
        return f'src="media/{filename}"'

    return img_re.sub(replace, html_body)


def save_wikinews_article(title: str, date: str, news_dir: Path) -> bool:
    """
    Fetch and save one Wikinews article as:
      <news_dir>/<date> - <title>/index.html
      <news_dir>/<date> - <title>/media/<images>
    Returns True if newly saved, False if already exists or skipped.
    """
    article_dir = news_dir / f"{date} - {safe_filename(title)}"
    if (article_dir / "index.html").exists():
        return False

    html_body = wikinews_fetch_html(title)
    if not html_body or len(html_body) < 200:
        return False

    article_dir.mkdir(parents=True, exist_ok=True)
    media_dir = article_dir / "media"

    html_body = _download_images(html_body, media_dir)

    # Remove media dir if nothing was downloaded
    if media_dir.exists() and not any(media_dir.iterdir()):
        media_dir.rmdir()

    url_title = urllib.parse.quote(title.replace(' ', '_'), safe='')
    page = HTML_WRAPPER.format(
        title=title,
        date=date or "unknown",
        url_title=url_title,
        body=html_body,
    )
    (article_dir / "index.html").write_text(page, encoding='utf-8')
    return True


def save_wikinews_batch(entries: list[tuple[str, str]], max_articles: int, news_dir: Path) -> int:
    seen: set[str] = set()
    saved = 0
    for title, date in entries:
        if title in seen or title.startswith("Wikinews:"):
            continue
        seen.add(title)
        article_dir = news_dir / f"{date} - {safe_filename(title)}"
        if (article_dir / "index.html").exists():
            saved += 1
            continue
        if save_wikinews_article(title, date, news_dir):
            print(f"  news  {title[:70]}")
            saved += 1
        if saved >= max_articles:
            break
        time.sleep(0.4)
    return saved


def fetch_wikinews() -> None:
    print("\n=== Wikinews ===")

    # Migrate any old plain-text files to the new format
    old_txt = list(NEWS_DIR.glob("*.txt"))
    if old_txt:
        print(f"  Removing {len(old_txt)} old .txt files")
        for f in old_txt:
            f.unlink(missing_ok=True)

    if BACKFILL:
        now   = datetime.now(timezone.utc)
        chunk = timedelta(days=7)
        total = 0
        for week in range(4):
            end_dt    = now - chunk * week
            start_dt  = end_dt - chunk
            end_str   = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            entries   = wikinews_titles_by_date(start_str, end_str, limit=200)
            n = save_wikinews_batch(entries, max_articles=50, news_dir=NEWS_DIR)
            total += n
            print(f"  week -{week+1}: {n} articles ({start_str[:10]} → {end_str[:10]})")
        print(f"  backfill total: {total} Wikinews articles")
    else:
        entries = wikinews_recent_titles(80)
        saved   = save_wikinews_batch(entries, max_articles=40, news_dir=NEWS_DIR)

        # Remove article directories no longer in the recent window
        current_dirs = {
            f"{date} - {safe_filename(title)}"
            for title, date in entries
            if not title.startswith("Wikinews:")
        }
        for d in NEWS_DIR.iterdir():
            if d.is_dir() and d.name not in current_dirs:
                import shutil
                shutil.rmtree(d, ignore_errors=True)

    article_count = sum(1 for d in NEWS_DIR.iterdir() if d.is_dir())
    print(f"  {NEWS_DIR} now has {article_count} articles")


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
        pages_per_cat = 5
        for cat in ARXIV_CATS:
            cat_total = 0
            for page in range(pages_per_cat):
                papers = fetch_arxiv_category(cat, max_results=25, start=page * 25)
                for p in papers:
                    write_arxiv_paper(p)
                    cat_total += 1
                time.sleep(3)
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
