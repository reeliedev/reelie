#!/usr/bin/env python3
"""
Reelie automatic page generation — CLI.

From a video (or an existing extraction), produce ONE canonical page and emit:
  - out/app/<slug>.json          app-facing JSON (decodes into the iOS app)
  - out/public/<handle>/<slug>/  public web page + embedded Schema.org JSON-LD
  - out/site/                    robots.txt, llms.txt, sitemap.xml, schema-graph.json
  - Landing Page/index.html      managed Schema.org block, updated in sync
  - out/pages/<...>.json         the canonical page (source of truth)

Examples
--------
  # Offline smoke test — no API key, deterministic prices:
  python generate.py --from-output YmA9l0eHFrk --handle glowbyjess --name "Jess Tan" --mock

  # Live — real title + LLM price estimates (needs ANTHROPIC_API_KEY):
  python generate.py --from-output YmA9l0eHFrk --handle glowbyjess

  # Full pipeline from a raw video (needs ffmpeg + key):
  python generate.py --video ./clip.mp4 --handle glowbyjess
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# make sibling modules importable when run from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure clip-cutting has ffmpeg/ffprobe on PATH (pip-bundled; no Homebrew needed).
try:
    import os as _os
    from static_ffmpeg import run as _sf
    _os.environ["PATH"] = (_os.path.dirname(_sf.get_or_fetch_platform_executables_else_raise()[0])
                           + _os.pathsep + _os.environ.get("PATH", ""))
except Exception:
    pass

import config
import clips
import extractor
import page_builder
from models import Page
from price import LLMPriceResolver, StubPriceResolver
from render import app_json, web, site_files, creator_page, directory, recommend, api_sync


def _client():
    import anthropic
    key = config.anthropic_key()
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. Use --mock for an offline run, or export "
            "the key for live title/price generation."
        )
    return anthropic.Anthropic(api_key=key)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate a Reelie page from a video.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-output", metavar="ID_OR_PATH",
                     help="video id (in video-llm/output) or path to an output JSON")
    src.add_argument("--video", metavar="PATH", help="raw video file (full extraction)")
    ap.add_argument("--handle", required=True, help="creator handle, e.g. glowbyjess")
    ap.add_argument("--name", help="creator display name (default: derived from handle)")
    ap.add_argument("--platforms", nargs="*", default=["YouTube", "Instagram"])
    ap.add_argument("--video-url", default="", help="public URL of the source video")
    ap.add_argument("--custom-slug", default=None,
                    help="creator's custom link (overrides the generated slug)")
    ap.add_argument("--title", default=None,
                    help="page title (overrides the auto/video title)")
    ap.add_argument("--mock", action="store_true",
                    help="offline: heuristic title + stub prices, no API calls")
    ap.add_argument("--no-clips", action="store_true",
                    help="skip per-step video clips (they need the source video)")
    ap.add_argument("--bundle-sample", action="store_true",
                    help="also copy the app JSON to the iOS app bundle sample path")
    args = ap.parse_args(argv)

    client = None if args.mock else _client()

    # 1. extract (or load) ------------------------------------------------
    if args.video:
        if args.mock:
            raise SystemExit("--video needs live extraction; drop --mock.")
        ext = extractor.run_extraction(args.video, client)
    else:
        ext = extractor.load_extraction(args.from_output)
    print(f"· {len(ext.products)} products from {ext.video_id}")

    # 2. prices -----------------------------------------------------------
    resolver = StubPriceResolver() if args.mock else LLMPriceResolver(client)
    prices = resolver.resolve(ext.products)
    retailers = [
        resolver.retailer_for(p) if isinstance(resolver, StubPriceResolver)
        else resolver.retailer_for_index(i, p)
        for i, p in enumerate(ext.products)
    ]
    print(f"· priced {sum(1 for p in prices if p)} products "
          f"({'stub' if args.mock else 'LLM estimate'})")

    # 3. assemble canonical page -----------------------------------------
    page = page_builder.build_page(
        ext, handle=args.handle, prices=prices, retailers=retailers,
        client=client, mock=args.mock,
        display_name=args.name, platforms=args.platforms, video_url=args.video_url,
    )
    if args.title:
        page.title = args.title.strip()[:80]
    if args.custom_slug:
        page.custom_slug = page_builder.slugify(args.custom_slug)
    elif args.title:
        # keep the URL in sync with the creator's chosen name
        page.custom_slug = page_builder.slugify(args.title)
    print(f"· page: “{page.title}”  →  {page.url}")

    # 4. per-step video clips (before render, so the page can embed them) -----
    clip_count = 0
    if not args.no_clips:
        page_dir = config.OUT_PUBLIC / page.handle / page.path_slug
        clip_count = clips.make_step_clips(page.video_id, page.products,
                                           ext.duration_s, page_dir)
        if clip_count:
            print(f"· clipped {clip_count} step video{'s' if clip_count != 1 else ''}"
                  f"{' (un-mirrored)' if clips.is_mirrored(page.video_id) else ''}")
        else:
            print("· no source video found — skipping clips (emoji tiles instead)")

    # 5. emit -------------------------------------------------------------
    canonical = config.OUT_DIR / "pages" / f"{page.handle}-{page.path_slug}.json"
    page.save(canonical)

    app_path = app_json.write_app_json(page, config.OUT_APP / f"{page.path_slug}.json")

    # Register FIRST so recommendations (this page included) are complete, then
    # render everything from the full catalogue.
    pages = site_files.register_page(page)
    html_path = web.write_public_page(page, config.OUT_PUBLIC, pages)
    site = site_files.write_all(pages)

    # Consumer surfaces: per-creator index (fills the dead <handle> route),
    # the browsable directory, and a debug reco dump.
    creator_paths = creator_page.write_creator_pages(pages, config.OUT_PUBLIC)
    directory_path = directory.write_directory(pages, config.OUT_PUBLIC)
    recommend.write_reco_json(pages)

    # Optional: push to the backend API (source of truth) if REELIE_API_URL is set.
    api_status = api_sync.sync_page(page)

    # Recommendations reference the WHOLE catalogue, so adding this page can change
    # earlier pages' "also used by" / "similar creators" modules. Re-render every
    # public page from the final registry to keep them in sync (HTML only — clips
    # and canonical data are untouched).
    for entry in pages:
        cp = config.OUT_DIR / "pages" / f"{entry['handle']}-{entry['slug']}.json"
        if cp.exists() and entry["url"] != page.url:
            web.write_public_page(Page.load(cp), config.OUT_PUBLIC, pages)

    if args.bundle_sample:
        config.APP_BUNDLE_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
        config.APP_BUNDLE_SAMPLE.write_text(app_path.read_text())

    # 6. report -----------------------------------------------------------
    print("\n✓ generated")
    print(f"  canonical : {canonical}")
    print(f"  app json  : {app_path}")
    print(f"  web page  : {html_path}")
    if clip_count:
        print(f"  clips     : {clip_count} → {html_path.parent / 'clips'}")
    print(f"  robots    : {site['robots']}")
    print(f"  llms.txt  : {site['llms']}")
    print(f"  sitemap   : {site['sitemap']}")
    print(f"  schema    : {site['schema']}")
    print(f"  main site : {'updated' if site['main_site_injected'] else 'skipped (no target)'}")
    print(f"  directory : {directory_path}")
    print(f"  creators  : {len(creator_paths)} index page(s) → {config.OUT_PUBLIC}/<handle>/")
    if api_status:
        print(f"  api sync  : {api_status}")
    if args.bundle_sample:
        print(f"  app bundle: {config.APP_BUNDLE_SAMPLE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
