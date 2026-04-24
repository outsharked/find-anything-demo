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
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from lxml import html as lxml_html
from datetime import datetime, timezone, timedelta
from pathlib import Path

BACKFILL  = "--backfill" in sys.argv
args      = [a for a in sys.argv[1:] if not a.startswith("--")]
LIVE_DIR  = Path(args[0]) if args else Path("/content/live")
NEWS_DIR  = LIVE_DIR / "wikinews"
ARXIV_DIR      = LIVE_DIR / "arxiv"
ARXIV_WEEK_DIR = ARXIV_DIR / "this-week"
NEWS_DIR.mkdir(parents=True, exist_ok=True)
ARXIV_DIR.mkdir(parents=True, exist_ok=True)
ARXIV_WEEK_DIR.mkdir(parents=True, exist_ok=True)

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


def wikinews_published_titles(target: int = 100) -> list[tuple[str, str]]:
    """Return (title, date) pairs from the Published category, newest first."""
    results: list[tuple[str, str]] = []
    cmcontinue: str | None = None
    while len(results) < target:
        params: dict = {
            "action":  "query",
            "list":    "categorymembers",
            "cmtitle": "Category:Published",
            "cmlimit": min(500, target - len(results)),
            "cmprop":  "title|timestamp",
            "cmtype":  "page",
            "cmsort":  "timestamp",
            "cmdir":   "desc",
            "format":  "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = get_json(f"{WIKINEWS_API}?{urllib.parse.urlencode(params)}")
        for m in data.get("query", {}).get("categorymembers", []):
            results.append((m["title"], m.get("timestamp", "")[:10]))
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            break
    return results


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
    doc = lxml_html.fromstring(raw.decode('utf-8', errors='replace'))
    body = doc.find('.//body')
    el = body if body is not None else doc
    # Wikimedia includes desktop-only and mobile-only duplicates of some elements;
    # strip the mobile copies so they don't appear twice in our static HTML.
    for node in el.xpath('.//*[contains(@class,"mobile-only")]'):
        node.drop_tree()
    # Rewrite ./File:... links to Wikimedia Commons so image enlargement works.
    for a in el.xpath('.//a[starts-with(@href,"./File:")]'):
        file_name = a.get('href')[2:]  # strip leading ./
        a.set('href', f'https://commons.wikimedia.org/wiki/{file_name}')
        a.set('target', '_blank')
    return (el.text or '') + ''.join(
        lxml_html.tostring(child, encoding='unicode') for child in el
    )


def _download_images(html_body: str, media_dir: Path) -> str:
    """Download Wikimedia images into media/ and rewrite src attributes."""
    root = lxml_html.fragment_fromstring(html_body, create_parent='div')
    downloaded = 0

    for img in list(root.iter('img')):
        img.attrib.pop('srcset', None)

        src = img.get('src', '')
        if 'upload.wikimedia.org' not in src:
            continue

        if downloaded >= MAX_IMAGES_PER_ARTICLE:
            img.drop_tree()
            continue

        url = html_mod.unescape(src)
        if url.startswith('//'):
            url = 'https:' + url
        clean_url = url.split('?')[0]
        raw_name = urllib.parse.unquote(clean_url.rsplit('/', 1)[-1])
        filename = re.sub(r'[\\/:*?"<>|]', '_', raw_name)[:120]
        if not filename:
            img.drop_tree()
            continue

        try:
            media_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            img.drop_tree()
            continue

        dest = media_dir / filename
        if not dest.exists():
            data = fetch(clean_url) or fetch(url)
            if not data:
                img.drop_tree()
                continue
            dest.write_bytes(data)

        downloaded += 1
        img.set('src', f'media/{filename}')

    return (root.text or '') + ''.join(
        lxml_html.tostring(child, encoding='unicode') for child in root
    )


def _month_dir(date: str, news_dir: Path) -> Path:
    try:
        return news_dir / datetime.strptime(date, "%Y-%m-%d").strftime("%B %Y")
    except ValueError:
        return news_dir / "Unknown"


def save_wikinews_article(title: str, date: str, news_dir: Path) -> bool:
    """
    Fetch and save one Wikinews article as:
      <news_dir>/<Month YYYY>/<date> - <title>/index.html
      <news_dir>/<Month YYYY>/<date> - <title>/media/<images>
    Returns True if newly saved, False if already exists or skipped.
    """
    article_dir = _month_dir(date, news_dir) / f"{date} - {safe_filename(title)}"
    if (article_dir / "index.html").exists():
        return False

    html_body = wikinews_fetch_html(title)
    if not html_body or len(html_body) < 200:
        return False

    # Remove any incomplete directory left by a previous failed run
    if article_dir.exists():
        shutil.rmtree(article_dir, ignore_errors=True)
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
    html_path = article_dir / "index.html"
    html_path.write_text(page, encoding='utf-8')
    if date:
        try:
            ts = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
            os.utime(html_path, (ts, ts))
        except ValueError:
            pass
    return True


def save_wikinews_batch(entries: list[tuple[str, str]], max_articles: int, news_dir: Path) -> int:
    seen: set[str] = set()
    saved = 0
    for title, date in entries:
        if title in seen or title.startswith("Wikinews:"):
            continue
        seen.add(title)
        article_dir = _month_dir(date, news_dir) / f"{date} - {safe_filename(title)}"
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

    # Migrate any old plain-text files
    for f in NEWS_DIR.glob("*.txt"):
        f.unlink(missing_ok=True)

    # Migrate flat <date> - <title>/ dirs into month subdirs
    for d in list(NEWS_DIR.iterdir()):
        if d.is_dir() and re.match(r'^\d{4}-\d{2}-\d{2} - ', d.name):
            try:
                dest_dir = _month_dir(d.name[:10], NEWS_DIR)
                dest_dir.mkdir(exist_ok=True)
                d.rename(dest_dir / d.name)
            except (ValueError, OSError):
                pass

    if BACKFILL:
        entries = wikinews_published_titles(target=150)
        total   = save_wikinews_batch(entries, max_articles=100, news_dir=NEWS_DIR)
        print(f"  backfill total: {total} Wikinews articles")
    else:
        entries = wikinews_recent_titles(300)
        save_wikinews_batch(entries, max_articles=100, news_dir=NEWS_DIR)

        # Keep only the 100 most recent articles across all month dirs
        all_article_dirs = sorted(
            (article_dir
             for month_dir in NEWS_DIR.iterdir() if month_dir.is_dir()
             for article_dir in month_dir.iterdir() if article_dir.is_dir()),
            key=lambda d: d.name, reverse=True
        )
        for old in all_article_dirs[100:]:
            shutil.rmtree(old, ignore_errors=True)
        # Remove empty month dirs
        for month_dir in list(NEWS_DIR.iterdir()):
            if month_dir.is_dir() and not any(month_dir.iterdir()):
                month_dir.rmdir()

    article_count = sum(
        1 for month_dir in NEWS_DIR.iterdir() if month_dir.is_dir()
        for article_dir in month_dir.iterdir() if article_dir.is_dir()
    )
    print(f"  {NEWS_DIR} now has {article_count} articles")


# ── arXiv ─────────────────────────────────────────────────────────────────────

ARXIV_API  = "https://export.arxiv.org/api/query"
ARXIV_NS   = {
    "atom":   "http://www.w3.org/2005/Atom",
    "arxiv":  "http://arxiv.org/schemas/atom",
}
ARXIV_CATS = ["cs.AI", "cs.CL", "cs.LG", "cs.CV"]


def fetch_arxiv_category(cat: str, max_results: int = 25, start: int = 0,
                         date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    query = f"cat:{cat}"
    if date_from and date_to:
        query += f" AND submittedDate:[{date_from} TO {date_to}]"
    params = urllib.parse.urlencode({
        "search_query": query,
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
        raw_id    = id_url.rsplit("/", 1)[-1]
        arxiv_id  = raw_id.replace(".", "_")
        papers.append({
            "id":        arxiv_id,
            "raw_id":    raw_id,
            "title":     title.strip().replace("\n", " "),
            "summary":   summary.strip(),
            "authors":   authors,
            "published": published[:10],
            "category":  cat,
            "url":       id_url.strip(),
        })
    return papers


def write_arxiv_paper(p: dict) -> bool:
    """Download the PDF for a paper. Returns True if newly saved."""
    dest = ARXIV_WEEK_DIR / f"{p['published']}_{p['id']}.pdf"
    if dest.exists():
        return False
    pdf_url = f"https://arxiv.org/pdf/{p['raw_id']}"
    data = fetch(pdf_url)
    if not data or not data.startswith(b"%PDF"):
        return False
    dest.write_bytes(data)
    try:
        ts = datetime.strptime(p['published'], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
        os.utime(dest, (ts, ts))
    except ValueError:
        pass
    return True


def _week_zip_name(pub_date: str) -> str:
    """Return archive name for the ISO week containing pub_date (YYYY-MM-DD)."""
    d = datetime.strptime(pub_date, "%Y-%m-%d").date()
    iso = d.isocalendar()          # (year, week, weekday)
    week_start = d - timedelta(days=d.weekday())   # Monday
    mon_abbr = week_start.strftime("%b").lower()
    return f"{iso[0]}_week-{iso[1]}_{mon_abbr}-{week_start.day}"


def archive_old_arxiv_pdfs() -> None:
    """Zip PDFs from past ISO weeks into weekly archives, remove originals."""
    today = datetime.now(timezone.utc).date()
    current_week = today.isocalendar()[:2]  # (year, week)

    by_week: dict[str, list[Path]] = {}
    for pdf in ARXIV_WEEK_DIR.glob("*.pdf"):
        m = re.match(r'^(\d{4}-\d{2}-\d{2})_', pdf.name)
        if not m:
            continue
        pub_date = m.group(1)
        d = datetime.strptime(pub_date, "%Y-%m-%d").date()
        if d.isocalendar()[:2] == current_week:
            continue
        week_key = _week_zip_name(pub_date)
        by_week.setdefault(week_key, []).append(pdf)

    for week_key, pdfs in sorted(by_week.items()):
        zip_path = ARXIV_DIR / f"{week_key}.zip"
        with zipfile.ZipFile(zip_path, 'a', compression=zipfile.ZIP_DEFLATED) as zf:
            existing = set(zf.namelist())
            added = 0
            for pdf in pdfs:
                if pdf.name not in existing:
                    zf.write(pdf, pdf.name)
                    added += 1
                pdf.unlink(missing_ok=True)
        print(f"  archived {week_key}: {len(pdfs)} PDFs → {zip_path.name} ({added} new)")

    # Drop oldest archives if total zip storage exceeds 100 MB
    MAX_ZIP_BYTES = 100 * 1024 * 1024
    zips = sorted(ARXIV_DIR.glob("*.zip"), key=lambda f: f.name, reverse=True)
    total = sum(z.stat().st_size for z in zips)
    while total > MAX_ZIP_BYTES and zips:
        oldest = zips.pop()
        total -= oldest.stat().st_size
        oldest.unlink()
        print(f"  pruned {oldest.name} (storage cap)")


def fetch_arxiv() -> None:
    print("\n=== arXiv ===")

    if BACKFILL:
        # Fetch 12 papers per category from each of the past 6 weeks
        now = datetime.now(timezone.utc)
        weeks = [
            (now - timedelta(weeks=w+1), now - timedelta(weeks=w))
            for w in range(6)
        ]
        for cat in ARXIV_CATS:
            cat_total = 0
            for week_start, week_end in weeks:
                d_from = week_start.strftime("%Y%m%d%H%M%S")
                d_to   = week_end.strftime("%Y%m%d%H%M%S")
                papers = fetch_arxiv_category(cat, max_results=5,
                                              date_from=d_from, date_to=d_to)
                for p in papers:
                    if write_arxiv_paper(p):
                        cat_total += 1
                        time.sleep(1)
                time.sleep(3)
            print(f"  {cat}: {cat_total} new PDFs (backfill)")
    else:
        for cat in ARXIV_CATS:
            papers = fetch_arxiv_category(cat, max_results=5)
            saved = 0
            for p in papers:
                if write_arxiv_paper(p):
                    saved += 1
                    time.sleep(1)
            print(f"  {cat}: {saved} new PDFs")
            time.sleep(3)

    archive_old_arxiv_pdfs()

    pdf_count  = len(list(ARXIV_WEEK_DIR.glob("*.pdf")))
    zip_count  = len(list(ARXIV_DIR.glob("*.zip")))
    print(f"  {ARXIV_DIR}: {pdf_count} current PDFs, {zip_count} monthly archives")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mode = "backfill" if BACKFILL else "update"
    print(f"Fetching live content ({mode}) into {LIVE_DIR}")
    fetch_wikinews()
    fetch_arxiv()
    print("\nDone.")
