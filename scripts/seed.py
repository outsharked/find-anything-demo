#!/usr/bin/env python3
"""
Seed script for find-anything-demo.

Downloads:
  1. Wikipedia articles — Nicolas Cage, his filmography, co-stars, directors
  2. Wikimedia Commons media — freely licensed images, GIFs, PDFs from the
     Nicolas Cage Commons category
  3. Internet Archive texts — PDFs related to Nicolas Cage
  4. GitHub repos — MIT-licensed repos mentioning Nicolas Cage (cloned shallow)
"""

import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

CONTENT_DIR   = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/data/content")

WIKI_DIR      = CONTENT_DIR / "wikipedia"
GITHUB_DIR    = CONTENT_DIR / "github"
GUTENBERG_DIR = CONTENT_DIR / "gutenberg"
IA_DIR        = CONTENT_DIR / "archive"

WIKI_DIR.mkdir(parents=True, exist_ok=True)
GITHUB_DIR.mkdir(parents=True, exist_ok=True)
GUTENBERG_DIR.mkdir(parents=True, exist_ok=True)
IA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "find-anything-demo/1.0 (https://github.com/jamietre/find-anything)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == retries - 1:
                print(f"  WARN: failed to fetch {url}: {e}")
                return {}
            time.sleep(2 ** attempt)
    return {}


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
            return True
        except Exception as e:
            if attempt == retries - 1:
                print(f"  WARN: failed to download {url}: {e}")
                return False
            time.sleep(2 ** attempt)
    return False


def safe_filename(title: str) -> str:
    return title.replace("/", "_").replace("\\", "_").replace(":", "_")[:200]


# ── 1. Wikipedia articles ─────────────────────────────────────────────────────

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def fetch_article_text(title: str) -> str | None:
    params = urllib.parse.urlencode({
        "action": "query",
        "prop": "extracts",
        "titles": title,
        "explaintext": "1",
        "exsectionformat": "plain",
        "format": "json",
        "redirects": "1",
    })
    data = get_json(f"{WIKIPEDIA_API}?{params}")
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if "missing" not in page:
            return page.get("extract", "")
    return None


def save_article(title: str, subdir: str = "") -> bool:
    dest_dir = WIKI_DIR / subdir if subdir else WIKI_DIR
    dest = dest_dir / f"{safe_filename(title)}.txt"
    if dest.exists():
        return True
    text = fetch_article_text(title)
    if not text:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"# {title}\n\n{text}", encoding="utf-8")
    print(f"  Wikipedia: {title}")
    return True


def get_category_members(category: str, ns: int = 0, limit: int = 500) -> list[str]:
    members = []
    cmcontinue = None
    while True:
        params: dict = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmnamespace": ns,
            "cmlimit": min(limit - len(members), 500),
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        data = get_json(f"{WIKIPEDIA_API}?{urllib.parse.urlencode(params)}")
        batch = [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        members.extend(batch)
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue or len(members) >= limit:
            break
    return members[:limit]


def get_links(title: str, limit: int = 50) -> list[str]:
    params = urllib.parse.urlencode({
        "action": "query",
        "prop": "links",
        "titles": title,
        "pllimit": limit,
        "format": "json",
    })
    data = get_json(f"{WIKIPEDIA_API}?{params}")
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        return [l["title"] for l in page.get("links", [])]
    return []


def seed_wikipedia():
    print("\n=== Wikipedia articles ===")

    # Core Nicolas Cage articles
    core = [
        "Nicolas Cage",
        "Nicolas Cage filmography",
        "Nicolas Cage discography",
        "Coppola family",
        "Francis Ford Coppola",
        "Peggy Sue Got Married",
        "Raising Arizona",
        "Moonstruck",
        "Vampire's Kiss",
        "Wild at Heart (film)",
        "Honeymoon in Vegas",
        "Red Rock West",
        "Guarding Tess",
        "It Could Happen to You (film)",
        "Leaving Las Vegas",
        "The Rock (film)",
        "Con Air",
        "Face/Off",
        "City of Angels (film)",
        "Snake Eyes (1998 film)",
        "8MM (film)",
        "Bringing Out the Dead",
        "Gone in 60 Seconds (2000 film)",
        "The Family Man",
        "Captain Corelli's Mandolin (film)",
        "Windtalkers",
        "Adaptation (film)",
        "Matchstick Men",
        "National Treasure (film)",
        "National Treasure: Book of Secrets",
        "Lord of War",
        "The Weather Man",
        "World Trade Center (film)",
        "Ghost Rider (film)",
        "Next (2007 film)",
        "Grindhouse (film)",
        "Knowing (film)",
        "Bad Lieutenant: Port of Call New Orleans",
        "Kick-Ass (film)",
        "The Sorcerer's Apprentice (2010 film)",
        "Season of the Witch (film)",
        "Drive Angry",
        "Ghost Rider: Spirit of Vengeance",
        "Stolen (2012 film)",
        "The Croods",
        "Joe (2013 film)",
        "Left Behind (2014 film)",
        "Outcast (2014 film)",
        "The Trust (film)",
        "Mom and Dad (film)",
        "Mandy (film)",
        "Spider-Man: Into the Spider-Verse",
        "Colour Out of Space (film)",
        "Prisoners of the Ghostland",
        "The Unbearable Weight of Massive Talent",
        "Renfield (film)",
        "Dream Scenario",
        "Longlegs (film)",
        "Academy Award for Best Actor",
        "Golden Globe Award for Best Actor – Motion Picture Drama",
        "Method acting",
        "Gonzo filmmaking",
        "New Hollywood",
        "Action film",
        "Nicolas Cage (band)",
    ]
    for title in core:
        save_article(title, "core")
        time.sleep(0.3)

    # All films from the Nicolas Cage films category
    print("  Fetching Nicolas Cage films category...")
    film_titles = get_category_members("Nicolas Cage films")
    print(f"  Found {len(film_titles)} films in category")
    for title in film_titles:
        save_article(title, "films")
        time.sleep(0.2)

    # Co-stars and directors from his Wikipedia page links
    print("  Fetching linked articles from main Nicolas Cage page...")
    links = get_links("Nicolas Cage", limit=100)
    for title in links:
        if not (WIKI_DIR / "core" / f"{safe_filename(title)}.txt").exists():
            save_article(title, "related")
            time.sleep(0.2)

    # Nicolas Cage meme / internet culture articles
    meme_articles = [
        "Internet meme",
        "Nicolas Cage as Everyone",
        "Pillowcase",
        "Wicker Man (2006 film)",
        "Bees (Nicolas Cage scene)",
        "Sailor Ripley",
        "H.I. McDunnough",
        "Ghost Rider",
        "Ghostbusters",
        "Comic book collecting",
        "Action Comics #1",
        "Superman",
    ]
    for title in meme_articles:
        save_article(title, "culture")
        time.sleep(0.2)


# ── 2. Wikimedia Commons media ────────────────────────────────────────────────

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".webp", ".tiff", ".ogg", ".ogv"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def get_commons_files(category: str, limit: int = 100) -> list[dict]:
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": limit,
        "format": "json",
    })
    data = get_json(f"{COMMONS_API}?{params}")
    return data.get("query", {}).get("categorymembers", [])


def get_file_info(titles: list[str]) -> list[dict]:
    if not titles:
        return []
    params = urllib.parse.urlencode({
        "action": "query",
        "prop": "imageinfo",
        "titles": "|".join(titles[:50]),
        "iiprop": "url|size|mediatype",
        "format": "json",
    })
    data = get_json(f"{COMMONS_API}?{params}")
    results = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        if info.get("url") and info.get("size", 0) <= MAX_FILE_SIZE:
            results.append({
                "title": page["title"],
                "url": info["url"],
                "size": info.get("size", 0),
            })
    return results


def seed_commons():
    print("\n=== Wikimedia Commons media ===")
    media_dir = WIKI_DIR / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    categories = [
        "Nicolas Cage",
        "Nicolas Cage films",
        "Face/Off (film)",
        "Con Air (film)",
        "The Rock (film)",
        "Raising Arizona",
        "Moonstruck (film)",
        "Leaving Las Vegas (film)",
        "Adaptation (film)",
        "National Treasure (film)",
        "Ghost Rider (film)",
        "Films directed by Joel Schumacher",
        "Films directed by John Woo",
        "Films directed by Brian De Palma",
        "Films directed by David Lynch",
        "Films directed by the Coen Brothers",
        "New Orleans in film",
    ]

    all_files: list[dict] = []
    seen_urls: set[str] = set()
    for cat in categories:
        members = get_commons_files(cat, limit=50)
        titles = [m["title"] for m in members]
        file_infos = get_file_info(titles)
        for fi in file_infos:
            if fi["url"] not in seen_urls:
                seen_urls.add(fi["url"])
                all_files.append(fi)
        time.sleep(0.5)

    print(f"  Found {len(all_files)} Commons files")
    for info in all_files:
        ext = Path(urllib.parse.urlparse(info["url"]).path).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        fname = safe_filename(Path(info["title"].replace("File:", "")).stem) + ext
        dest = media_dir / fname
        if download_file(info["url"], dest):
            print(f"  Commons: {info['title']} ({info['size'] // 1024} KB)")
        time.sleep(0.3)


# ── 3. Internet Archive PDFs ──────────────────────────────────────────────────

IA_SEARCH = "https://archive.org/advancedsearch.php"
IA_DOWNLOAD = "https://archive.org/download"


def search_ia(query: str, limit: int = 20) -> list[dict]:
    # Build query string manually — urlencode encodes brackets and colons which
    # breaks the IA API (fl%5B%5D not accepted; subject%3Aastronomy not parsed).
    qs = (
        f"q={urllib.parse.quote(query, safe=':+')}"
        f"&fl[]=identifier&fl[]=title"
        f"&rows={limit}&output=json"
    )
    data = get_json(f"{IA_SEARCH}?{qs}")
    return data.get("response", {}).get("docs", [])


def get_ia_pdf_url(identifier: str) -> str | None:
    data = get_json(f"https://archive.org/metadata/{identifier}/files")
    for f in data.get("result", []):
        if f.get("format") in ("Text PDF", "Additional Text PDF", "PDF") and \
                f.get("name", "").endswith(".pdf"):
            return f"{IA_DOWNLOAD}/{identifier}/{f['name']}"
    return None


IA_PDF_MAX_BYTES = 20 * 1024 * 1024  # 20 MB per PDF


def get_ia_pdf_url(identifier: str) -> str | None:
    """Return URL for the best non-private PDF in an IA item, up to IA_PDF_MAX_BYTES."""
    data = get_json(f"https://archive.org/metadata/{identifier}/files")
    best = None
    for f in data.get("result", []):
        if f.get("private"):
            continue
        if f.get("format") in ("Text PDF", "Additional Text PDF", "PDF") and \
                f.get("name", "").endswith(".pdf"):
            size = int(f.get("size") or 0)
            if 0 < size <= IA_PDF_MAX_BYTES:
                if best is None or size < int(best.get("size") or 0):
                    best = f
    if best:
        encoded_name = urllib.parse.quote(best["name"])
        return f"{IA_DOWNLOAD}/{identifier}/{encoded_name}"
    return None


# Curated NASA items: Spinoff magazines, mission press kits — all freely downloadable.
# These are image-rich public-domain documents that make the demo visually interesting.
IA_NASA_SEEDS = [
    ("nasa_techdoc_20030011275",        "NASA Spinoff 2002"),
    ("nasa_techdoc_20030099639",        "NASA Spinoff 2003 - 100 Years of Powered Flight"),
    ("NASA_NTRS_Archive_20060022016",   "NASA Spinoff 2005"),
    ("ERIC_ED310944",                   "NASA Spinoff 1985"),
    ("NASA_NTRS_Archive_19710029176",   "NASA Mariner 9 Press Kit"),
    ("NASA_NTRS_Archive_19700024873",   "NASA Orbiting Frog Otolith Press Kit"),
    ("gemini-titan-9-a-press-kit-addenda", "NASA Gemini-Titan 9A Press Kit"),
    ("nasa_techdoc_20040200959",        "NASA Lunar Receiving Laboratory History"),
]


def seed_internet_archive():
    print("\n=== Internet Archive PDFs ===")
    pdf_dir = IA_DIR / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    seen: set[str] = set()
    downloaded = 0

    # 1. Curated NASA seeds (image-rich, publicly downloadable)
    for identifier, label in IA_NASA_SEEDS:
        seen.add(identifier)
        dest = pdf_dir / f"{safe_filename(label)}.pdf"
        if dest.exists():
            print(f"  skip  {label}")
            downloaded += 1
            continue
        pdf_url = get_ia_pdf_url(identifier)
        if pdf_url and download_file(pdf_url, dest):
            size_kb = dest.stat().st_size // 1024
            print(f"  PDF   {label} ({size_kb} KB)")
            downloaded += 1
        else:
            print(f"  WARN  {label} — no downloadable PDF found")
        time.sleep(0.5)

    # 2. Dynamic search for additional NASA tech reports
    if downloaded < 15:
        extra_queries = [
            "subject:\"space exploration\" NASA mediatype:texts",
            "NASA press kit mediatype:texts",
        ]
        for query in extra_queries:
            docs = search_ia(query, limit=8)
            for doc in docs:
                identifier = doc.get("identifier", "")
                if identifier in seen:
                    continue
                seen.add(identifier)
                title = doc.get("title", identifier)
                dest = pdf_dir / f"{safe_filename(title)}.pdf"
                if dest.exists():
                    print(f"  skip  {title}")
                    downloaded += 1
                    continue
                pdf_url = get_ia_pdf_url(identifier)
                if pdf_url and download_file(pdf_url, dest):
                    size_kb = dest.stat().st_size // 1024
                    print(f"  PDF   {title} ({size_kb} KB)")
                    downloaded += 1
                time.sleep(0.5)
            if downloaded >= 15:
                break


# ── 4. GitHub repos ───────────────────────────────────────────────────────────

GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def github_headers() -> dict:
    h = {**HEADERS, "Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        h["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return h


def search_github_repos(query: str, limit: int = 30) -> list[dict]:
    params = urllib.parse.urlencode({
        "q": f"{query} license:mit",
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30),
    })
    url = f"{GITHUB_API}/search/repositories?{params}"
    req = urllib.request.Request(url, headers=github_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data.get("items", [])
    except Exception as e:
        print(f"  WARN: GitHub search failed: {e}")
        return []


def clone_repo(clone_url: str, dest: Path, as_zip: bool = False) -> bool:
    """Clone a repo to dest (directory) or dest.zip (if as_zip=True).

    as_zip=True: clone to a temp dir, zip it up, delete the dir.
    This saves significant space for large repos while still making the
    contents fully searchable (find-anything traverses zip archives).
    """
    zip_dest = dest.with_suffix(".zip")
    if dest.exists() or zip_dest.exists():
        return True
    tmp = dest.with_suffix(".tmp")
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", "--quiet", clone_url, str(tmp)],
            check=True, capture_output=True, timeout=300,
        )
        # Remove .git so nested repos don't confuse our parent repo
        subprocess.run(["rm", "-rf", str(tmp / ".git")], check=True)
        # Remove Git LFS pointer stubs
        for lfs_stub in tmp.rglob("*"):
            if lfs_stub.is_file() and lfs_stub.stat().st_size < 512:
                try:
                    if lfs_stub.read_bytes().startswith(b"version https://git-lfs.github.com"):
                        lfs_stub.unlink()
                except OSError:
                    pass
        # Trim large ML training image datasets
        for img_dir in tmp.rglob("*"):
            if not img_dir.is_dir():
                continue
            images = sorted(f for f in img_dir.iterdir()
                            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"})
            for excess in images[20:]:
                excess.unlink()

        if as_zip:
            # Zip the whole repo — code compresses 60-80%, saves Docker image space
            # and demonstrates find-anything's zip traversal.
            with zipfile.ZipFile(zip_dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for f in tmp.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(tmp))
            subprocess.run(["rm", "-rf", str(tmp)], capture_output=True)
            return True
        else:
            tmp.rename(dest)
            return True
    except Exception as e:
        subprocess.run(["rm", "-rf", str(tmp)], capture_output=True)
        print(f"  WARN: clone failed for {clone_url}: {e}")
        return False


def has_inline_images(repo: dict) -> bool:
    """Return True if the repo is likely to have images committed directly (not via LFS).
    Heuristic: repos with a 'has_wiki' or non-trivial size and HTML/CSS topics
    often have screenshots; we also check language and size."""
    lang = (repo.get("language") or "").lower()
    size_kb = repo.get("size", 0)
    # Very small repos are usually just code stubs with no assets.
    if size_kb < 50:
        return False
    # Pure backend languages rarely have committed images.
    if lang in ("python", "go", "rust", "java", "c", "c++", "ruby", "shell"):
        return False
    return True


def seed_github():
    print("\n=== GitHub repos ===")

    # Curated list of diverse, well-known open-source repos.
    # (clone_url, full_name, as_zip)
    # as_zip=True: zip the repo after cloning — saves Docker image space while
    # still making content fully searchable (find-anything traverses zips).
    FEATURED_REPOS = [
        # Algorithms — thousands of small files
        ("https://github.com/TheAlgorithms/Python.git",
         "TheAlgorithms/Python",           False),
        ("https://github.com/trekhleb/javascript-algorithms.git",
         "trekhleb/javascript-algorithms", False),

        # Shell / CLI
        ("https://github.com/ohmyzsh/ohmyzsh.git",
         "ohmyzsh/ohmyzsh",                False),

        # Data Science notebooks with images
        ("https://github.com/jakevdp/PythonDataScienceHandbook.git",
         "jakevdp/PythonDataScienceHandbook", False),

        # AI / ML — large repos stored as zips
        # ("https://github.com/norvig/pytudes.git",
        #  "norvig/pytudes",                 True),   # 69 MB — omitted to keep image lean
        # ("https://github.com/microsoft/promptflow.git",
        #  "microsoft/promptflow",           True),   # 97 MB — omitted to keep image lean
        ("https://github.com/huggingface/diffusers.git",
         "huggingface/diffusers",          True),

        # Scientific Python — large, stored as zip
        ("https://github.com/scipy/scipy.git",
         "scipy/scipy",                    True),

        # Systems / Infrastructure — large, stored as zip
        ("https://github.com/grafana/grafana.git",
         "grafana/grafana",                True),

        # Web / Visualization
        ("https://github.com/d3/d3.git",
         "d3/d3",                          False),
        ("https://github.com/mermaid-js/mermaid.git",
         "mermaid-js/mermaid",             False),

        # Games / Fun
        ("https://github.com/nicehash/NiceHashQuickMiner.git",
         "nicehash/NiceHashQuickMiner",    False),

        # Omitted — restore by uncommenting if extra content is desired:
        # ("https://github.com/norvig/pytudes.git",
        #  "norvig/pytudes",                 True),                         # 69 MB
        # ("https://github.com/microsoft/promptflow.git",
        #  "microsoft/promptflow",           True),                         # 97 MB
        ("https://github.com/mans-andersson/AutoEncoderFaceSwap.git",
         "mans-andersson/AutoEncoderFaceSwap", True),                     # Nicolas Cage face dataset (images)
    ]

    seen: set[str] = set()
    cloned = 0

    for clone_url, full_name, as_zip in FEATURED_REPOS:
        if full_name in seen:
            continue
        seen.add(full_name)
        name = full_name.replace("/", "__")
        dest = GITHUB_DIR / name
        suffix = " (→ zip)" if as_zip else ""
        print(f"  Cloning {full_name}{suffix}...")
        if clone_repo(clone_url, dest, as_zip=as_zip):
            cloned += 1
        time.sleep(1)

    # Also keep a small selection of Nicolas Cage fun repos
    cage_queries = [
        "nicolas cage face",
        "nicolas cage website",
        "nic cage game",
    ]
    for query in cage_queries:
        repos = search_github_repos(query, limit=10)
        for repo in repos:
            if repo["id"] in {r for r in seen}:
                continue
            full_name = repo["full_name"]
            if full_name in seen:
                continue
            seen.add(full_name)
            name = full_name.replace("/", "__")
            dest = GITHUB_DIR / name
            stars = repo.get("stargazers_count", 0)
            print(f"  Cloning {full_name} ({stars}★)")
            if clone_repo(repo["clone_url"], dest):
                cloned += 1
            time.sleep(1)

    print(f"  Cloned {cloned} repos total")


# ── 5. Project Gutenberg texts ────────────────────────────────────────────────

# (gutenberg_id, title) — plain text via gutendex API
GUTENBERG_BOOKS = [
    (84,   "Frankenstein"),
    (345,  "Dracula"),
    (174,  "The Picture of Dorian Gray"),
    (11,   "Alice's Adventures in Wonderland"),
    (1661, "The Adventures of Sherlock Holmes"),
    (36,   "The War of the Worlds"),
    (2701, "Moby Dick"),
    (1342, "Pride and Prejudice"),
    (98,   "A Tale of Two Cities"),
    (1260, "Jane Eyre"),
]


def get_gutenberg_epub_url(book_id: int) -> str | None:
    data = get_json(f"https://gutendex.com/books/{book_id}/")
    formats = data.get("formats", {})
    return formats.get("application/epub+zip")


def seed_gutenberg():
    print("\n=== Project Gutenberg EPUBs ===")
    for book_id, title in GUTENBERG_BOOKS:
        dest = GUTENBERG_DIR / f"{safe_filename(title)}.epub"
        # Remove old .txt version if present
        old = GUTENBERG_DIR / f"{safe_filename(title)}.txt"
        if old.exists():
            old.unlink()
        if dest.exists():
            print(f"  skip  {title}")
            continue
        url = get_gutenberg_epub_url(book_id)
        if not url:
            print(f"  WARN  {title} — no EPUB URL found")
            continue
        if download_file(url, dest):
            size_kb = dest.stat().st_size // 1024
            print(f"  epub  {title} ({size_kb} KB)")
        else:
            print(f"  WARN  {title} — download failed")
        time.sleep(0.5)


# ── 6. Internet Archive audio & video ─────────────────────────────────────────

def get_ia_file_url(identifier: str, formats: list[str], max_mb: int = 50) -> tuple[str, str] | None:
    """Return (url, filename) for the first matching format under max_mb."""
    data = get_json(f"https://archive.org/metadata/{identifier}/files")
    max_bytes = max_mb * 1024 * 1024
    for f in data.get("result", []):
        if f.get("format") in formats:
            name = f.get("name", "")
            size = int(f.get("size", 0) or 0)
            if name and (size == 0 or size <= max_bytes):
                return f"https://archive.org/download/{identifier}/{urllib.parse.quote(name)}", name
    return None


IA_AUDIO_ITEMS = [
    # Old Time Radio (verified identifiers)
    ("OTRR_Jack_Benny_Singles",            "Jack Benny Program"),
    ("OTRR_Gunsmoke_Singles",              "Gunsmoke Radio Show"),
    ("OTRR_YoursTrulyJohnnyDollar_Singles","Yours Truly Johnny Dollar"),
    # Speeches & spoken word
    ("MLKDream",                           "Martin Luther King - I Have a Dream"),
    # Music (public domain 78rpm recordings)
    ("MapleLeafRag",                       "Scott Joplin - Maple Leaf Rag"),
]

IA_VIDEO_ITEMS = [
    # Early cinema (small enough to fit under size limit)
    ("TripToTheMoon",                                "A Trip to the Moon - Méliès (1902)"),
    ("DasKabinettdesDoktorCaligariTheCabinetofDrCaligari", "The Cabinet of Dr. Caligari (1920)"),
]

AUDIO_FORMATS = ["VBR MP3", "MP3", "128Kbps MP3", "64Kbps MP3", "Ogg Vorbis"]
VIDEO_FORMATS = ["512Kb MPEG4", "MPEG4", "h.264 MPEG4", "Ogg Video"]


def seed_ia_audio():
    print("\n=== Internet Archive — Audio ===")
    audio_dir = IA_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    for identifier, label in IA_AUDIO_ITEMS:
        result = get_ia_file_url(identifier, AUDIO_FORMATS, max_mb=30)
        if not result:
            print(f"  WARN  {label} — no audio file found")
            continue
        url, fname = result
        ext = Path(fname).suffix.lower()
        dest = audio_dir / f"{safe_filename(label)}{ext}"
        if dest.exists():
            print(f"  skip  {label}")
            continue
        if download_file(url, dest):
            print(f"  audio {label} ({dest.stat().st_size // 1024} KB)")
        time.sleep(1)


def seed_ia_video():
    print("\n=== Internet Archive — Video ===")
    video_dir = IA_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    for identifier, label in IA_VIDEO_ITEMS:
        result = get_ia_file_url(identifier, VIDEO_FORMATS, max_mb=40)
        if not result:
            print(f"  WARN  {label} — no video file found")
            continue
        url, fname = result
        ext = Path(fname).suffix.lower()
        dest = video_dir / f"{safe_filename(label)}{ext}"
        if dest.exists():
            print(f"  skip  {label}")
            continue
        if download_file(url, dest):
            print(f"  video {label} ({dest.stat().st_size // 1024} KB)")
        else:
            dest.unlink(missing_ok=True)
        time.sleep(1)


# ── 7. Nested zip files ───────────────────────────────────────────────────────

import zipfile


def seed_zips():
    """Create nested zip files from existing content — demonstrating archive traversal."""
    print("\n=== Nested zip archives ===")
    zip_dir = CONTENT_DIR / "zips"
    zip_dir.mkdir(parents=True, exist_ok=True)

    # 1. Zip of NASA PDFs (images inside a zip)
    nasa_zip = zip_dir / "NASA_publications.zip"
    if not nasa_zip.exists():
        pdf_dir = IA_DIR / "pdfs"
        pdfs = list(pdf_dir.glob("NASA*.pdf"))
        if pdfs:
            with zipfile.ZipFile(nasa_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for p in pdfs:
                    zf.write(p, p.name)
            print(f"  zip   NASA_publications.zip ({nasa_zip.stat().st_size // 1024} KB, {len(pdfs)} PDFs)")

    # 2. Zip of Gutenberg EPUBs
    books_zip = zip_dir / "Gutenberg_classics.zip"
    if not books_zip.exists():
        epubs = list(GUTENBERG_DIR.glob("*.epub"))
        if epubs:
            with zipfile.ZipFile(books_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for e in epubs:
                    zf.write(e, e.name)
            print(f"  zip   Gutenberg_classics.zip ({books_zip.stat().st_size // 1024} KB, {len(epubs)} EPUBs)")

    # 3. Nested zip: wikipedia images inside a zip, that zip inside another zip
    outer_zip = zip_dir / "wikipedia_media_archive.zip"
    if not outer_zip.exists():
        media_dir = WIKI_DIR / "media"
        images = [f for f in media_dir.glob("*") if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".svg"}] if media_dir.exists() else []
        if images:
            # Inner zip
            inner_bytes = __import__("io").BytesIO()
            with zipfile.ZipFile(inner_bytes, "w", zipfile.ZIP_DEFLATED) as inner:
                for img in images[:20]:
                    inner.write(img, img.name)
            inner_bytes.seek(0)
            # Outer zip containing the inner zip + a README
            with zipfile.ZipFile(outer_zip, "w", zipfile.ZIP_DEFLATED) as outer:
                outer.writestr("README.txt",
                    "Wikipedia media archive\n\nContains: images.zip (Wikipedia Commons images)\n")
                outer.writestr("images.zip", inner_bytes.read())
            print(f"  zip   wikipedia_media_archive.zip (nested, {outer_zip.stat().st_size // 1024} KB)")

    # 4. Zip of Commons images directly (flat, for easy preview demo)
    commons_zip = zip_dir / "wikipedia_commons_images.zip"
    if not commons_zip.exists():
        media_dir = WIKI_DIR / "media"
        images = [f for f in media_dir.glob("*") if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}] if media_dir.exists() else []
        if images:
            with zipfile.ZipFile(commons_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for img in images:
                    zf.write(img, img.name)
            print(f"  zip   wikipedia_commons_images.zip ({commons_zip.stat().st_size // 1024} KB, {len(images)} images)")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Seeding content into {CONTENT_DIR}")
    seed_wikipedia()
    seed_commons()
    seed_internet_archive()
    seed_gutenberg()
    seed_ia_audio()
    seed_ia_video()
    seed_github()
    seed_zips()
    print("\nDone.")
