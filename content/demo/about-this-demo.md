# About This Demo

This is a live demo of [Find Anything](https://github.com/jamietre/find-anything), a fast full-text search engine for local files and documents.

## What's Indexed

This demo is populated with a bunch of uncopyrighted and/or MIT-licensed content:

- **Wikinews** — Recent news articles fetched from [Wikinews](https://en.wikinews.org/), refreshed hourly. Articles include images and are stored as HTML.
- **arXiv** — Recent research papers from arXiv in categories cs.AI, cs.CL, cs.LG, and cs.CV, fetched as PDFs and archived weekly.
- **Wikipedia** — A selection of Wikipedia articles covering a broad range of topics.
- **Project Gutenberg** — Public domain books and texts from [Project Gutenberg](https://www.gutenberg.org/).
- **GitHub** — README files and documentation from popular open source repositories.
- **Internet Archive** — Selected texts from the [Internet Archive](https://archive.org/).

If you believe any of the content here is not freely distributable, please [let me know](mailto:alien@outsharked.com)

## How It Works

The demo runs inside a Docker container on [Railway](https://railway.app/). On startup it indexes some pre-seeded content, then fetches and indexes fresh Wikinews articles and arXiv papers. An hourly background job keeps the live sources up to date.

Search is powered by the `find-server` and `find-scan` binaries from the Find Anything project. Results are ranked by relevance and can be filtered by source or date.

## Source Code

The demo configuration and fetch scripts are available at:
https://github.com/outsharked/find-anything-demo
