# find-anything demo

Live demo of [find-anything](https://github.com/outsharked/find-anything), pre-seeded with:

- **Wikipedia articles** — Nicolas Cage, his full filmography, co-stars, and directors
- **Wikimedia Commons media** — freely licensed images, GIFs, and PDFs
- **Internet Archive PDFs** — texts related to his films and era
- **GitHub repos** — MIT-licensed repositories about Nicolas Cage (source code, fan projects)

No login required — the server runs without authentication.

## Deploy (Railway)

1. Create a Railway service pointing at this repo
2. Add a volume mounted at `/data`
3. Deploy — no environment variables required

## Local test

```bash
docker build -t find-anything-demo .
docker run -p 8765:8765 -v $(pwd)/data:/data find-anything-demo
```
