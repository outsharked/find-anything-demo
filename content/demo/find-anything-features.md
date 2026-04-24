# Find Anything — Features

Find Anything is a self-hosted full-text search engine. It's designed for distributed full-content file indexing — index one or more machines into a central server, then query everything from a single CLI or web UI.

## Main Features

- *Almost no security!* Expose it to the internet at your own risk!
- Client/server architecture — aggregate indexes from across your network into one place
- Fuzzy, exact, and regex search modes
- Displays search results in context (surrounding lines of content where the match was found)
- Find files in tree view by path/name using CTRL+P (command palette)
- Changes are monitored incrementally via `find-watch`; after initial indexing, resource use is very minimal
- Content deduplication — identical files stored once; search results surface all duplicate paths
- Indexes the inner contents of archive types (ZIP, TAR, 7Z, GZ) as individual searchable files, recursively
- Can extract indexable content from a wide range of file types (see below)
- Can display most common file types (images, PDF, video, Markdown, code) inline and formatted
- Highly configurable with inclusion/exclusion patterns, per-source settings, `.index` and `.noindex` files to alter configuration for inner directories
- Indexing error tracking — extraction failures surfaced per source in the UI and CLI
- Client has low resource requirements and is cross-platform (Linux, macOS, Windows) with builds for many architectures. For example, this will runs on a Synology DS216j — armv7 CPU, 512 MB RAM — and can index several terabytes from scratch in a few hours
- Custom content extractors and post-processing formatters can be added via configuration
- Complete CLI for querying the index

## Supported File Types

| Type | What's extracted |
|------|-----------------|
| Text, source code, Markdown | Full content; Markdown YAML frontmatter as structured fields |
| PDF | Full text content |
| HTML (.html, .htm, .xhtml) | Visible text from headings/paragraphs; title and description as metadata |
| Office (DOCX, XLSX, XLS, XLSM, PPTX) | Paragraphs, rows, slide text; document title/author as metadata |
| EPUB | Full chapter text; title, creator, publisher, language as metadata |
| Images (JPEG, PNG, TIFF, HEIC, RAW) | EXIF metadata (camera, GPS, dates) |
| Audio (MP3, FLAC, M4A, OGG) | ID3/Vorbis/MP4 tags (title, artist, album) |
| Video (MP4, MKV, WebM, AVI, MOV) | Format, resolution, duration |
| Archives (ZIP, TAR, 7Z, GZ) | Members extracted recursively and indexed as individual searchable files |
| Windows PE/DLL | File version, description, company, original filename from version info |

## Search Filters

Results can be filtered by:

- **Source** — limit to a named source (e.g. only news articles, only research papers)
- **Date** — filter by file modification time; setting accurate mtimes (e.g. to publication date) makes this meaningful
- **File type / path pattern** — target specific extensions or directory structures
- **Search mode** — fuzzy (default), exact, or regex

## Binaries

| Binary | Role |
|--------|------|
| `find-server` | Central index server |
| `find-scan` | Initial filesystem indexer |
| `find-watch` | Real-time file watcher (incremental updates) |
| `find-anything` | CLI search client |
| `find-admin` | Admin utilities: config, status, inbox management |

## Source Code

https://github.com/jamietre/find-anything
