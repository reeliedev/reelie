# Reelie — Automatic Page Generation

Turns a creator's video into one **shoppable routine page**, then emits it two ways:

1. **In-app** — an app-facing JSON the Reelie iOS app loads and previews (creator
   can name their own link before publishing).
2. **On the web** — a public page at `reelie.shop/<handle>/<slug>` that is built to
   be **maximally AI-discoverable**: embedded Schema.org, plus site-wide
   `robots.txt` / `llms.txt` / `sitemap.xml`, and **prices on every product** so AI
   assistants read a complete offer.

A single **canonical Page** (`out/pages/*.json`) is the source of truth; every
output is rendered from it.

```
video ──▶ extract (video-llm) ──▶ enrich price/retailer/link ──▶ assemble page ──┐
                                                                                 ▼
      out/app/<slug>.json   out/public/<handle>/<slug>/index.html   out/site/{robots,llms,sitemap,schema}
                                                                    + main-site Schema.org (in sync)
```

## Quick start

```bash
# Offline smoke test — no API key, deterministic stub prices:
python3 generate.py --from-output YmA9l0eHFrk --handle glowbyjess --name "Jess Tan" --mock

# Live — real title + LLM price estimates (needs ANTHROPIC_API_KEY):
python3 generate.py --from-output YmA9l0eHFrk --handle glowbyjess --name "Jess Tan"

# Full pipeline from a raw video (needs ffmpeg + key; runs video-llm end-to-end):
python3 generate.py --video ./clip.mp4 --handle glowbyjess

# Also refresh the iOS app's bundled sample page:
python3 generate.py --from-output YmA9l0eHFrk --handle glowbyjess --mock --bundle-sample
```

Uses the same interpreter as `video-llm` — either `pip install -r requirements.txt`
or run with `../../video-llm/.venv/bin/python3`. `--mock` needs no dependencies.

## Layout

| file | purpose |
|---|---|
| `config.py` | brand (`Reelie`), domain (`reelie.shop`), AI-crawler allow-list, paths — **the one place to change branding** |
| `models.py` | canonical `Page` / `ProductItem` / `Price` / `Link` dataclasses + JSON (de)serialization |
| `extractor.py` | load an existing `video-llm/output/{id}.json`, or run full extraction via `video-llm/pipeline.py` |
| `price.py` | `PriceResolver` interface + `LLMPriceResolver` (default) + `StubPriceResolver` (`--mock`) — **swap point for a real commerce feed** |
| `page_builder.py` | products (+ transcript) → title, emoji, slug, routine order, per-product notes/emoji |
| `prompts.py` | page-assembly + price-estimate prompts & JSON schemas (structured outputs) |
| `render/app_json.py` | app-facing JSON (decodes 1:1 into the app's `GeneratedPageDTO`) |
| `render/web.py` + `templates/public_page.html` | public web page + embedded JSON-LD |
| `render/schema.py` | Schema.org graphs: page-level (`ProfilePage`+`ItemList`+`Product`/`Offer`+`Person`+`BreadcrumbList`) and site-level (`Organization`+`WebSite`+`CollectionPage`) |
| `render/site_files.py` | registry + `robots.txt` / `llms.txt` / `sitemap.xml` + idempotent main-site Schema.org injection |
| `generate.py` | CLI entrypoint |

## AI discoverability

- **Every product carries a real `Offer`** (price, currency, availability, seller,
  `priceValidUntil`) so a chatbot reading the page has a complete answer.
- **`robots.txt`** explicitly allows GPTBot, ClaudeBot, PerplexityBot,
  Google-Extended, Applebot-Extended, CCBot, etc.
- **`llms.txt`** ([llmstxt.org](https://llmstxt.org)) maps every creator page for LLMs.
- **Main-site sync:** the main webpage's Schema.org is regenerated from the full
  page catalogue on each run and injected between
  `<!-- reelie:schema:start/end -->` markers (target: `Landing Page/index.html`,
  set in `config.py`). Idempotent — it never duplicates or clobbers other markup.

## Pricing note

`LLMPriceResolver` estimates *typical* retail prices from product knowledge; they
are marked **approximate** (`estimated: true`, `priceValidUntil` set) in the page,
the app, and the schema. Replace with a live retailer/affiliate feed by
implementing `PriceResolver.resolve()` in `price.py` — nothing else changes.

## App integration

`render/app_json.py` output decodes into `GeneratedPageDTO`
(`ReelieApp/ReelieApp/Models/GeneratedPage.swift`). The app bundles
`Resources/sample-generated-page.json` so it demos standalone, and also loads any
JSON dropped in `<Documents>/generated-pages/`. In-app, generated pages appear
under **"JUST GENERATED"** on the Pages tab → tap **Preview** to see the routine,
prices, and the **"name your link"** editor before publishing.
