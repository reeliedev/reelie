#!/usr/bin/env python3
"""
Beauty/skincare product extractor — validation prototype.

    python extract.py run                 # process ./videos/*  -> ./output/
    python extract.py run --urls URL ...  # also download+process YouTube URLs
    python extract.py run --api           # use OpenAI Whisper API instead of local
    python extract.py score               # score ./output vs ./labels -> report.md
"""

import argparse
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass  # only needed for `run`; `score` has no heavy deps

ROOT = Path(__file__).parent
DEFAULT_MODEL = "claude-sonnet-4-6"


def cmd_run(args):
    import anthropic
    from pipeline import (discover_local_videos, download_youtube,
                          process_video, write_video_csv)

    videos_dir = Path(args.videos_dir)
    out_dir = Path(args.out)
    cache_dir = Path(args.cache)
    videos_dir.mkdir(parents=True, exist_ok=True)

    paths = list(discover_local_videos(videos_dir))
    for url in args.urls or []:
        print(f"downloading {url} ...")
        try:
            paths.append(download_youtube(url, videos_dir))
        except Exception as e:
            print(f"  ! failed to download {url}: {e}")

    # Dedupe: a downloaded URL that lands in videos/ is also found by the local
    # scan — keep each file once (by resolved path), preserving order.
    seen, unique = set(), []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    paths = unique

    if not paths:
        print(f"No videos found in {videos_dir}/ and no --urls given.")
        print("Drop local files (mp4/mov/…) into ./videos/ or pass --urls.")
        return

    client = anthropic.Anthropic()
    results, grand_total = [], 0.0
    for p in paths:
        try:
            r = process_video(p, client, args.model, cache_dir, out_dir,
                              args.api, args.whisper_model,
                              reconcile=not args.no_reconcile,
                              scene_threshold=args.scene_threshold,
                              floor_interval=args.floor_interval,
                              hold=not args.no_hold,
                              use_description=not args.no_description,
                              auto_mirror=not args.no_mirror,
                              recover_brands_flag=args.recover)
            # Each video gets its own standalone CSV: output/{video_id}.csv
            n = write_video_csv(r, out_dir)
            print(f"  wrote {r['video_id']}.json + {r['video_id']}.csv ({n} rows)")
            results.append(r)
            grand_total += r["cost_usd"]["total"]
        except Exception as e:
            print(f"  ! error processing {p.name}: {e}")

    if results:
        print(f"\nProcessed {len(results)} video(s). Each has its own "
              f"output/{{video_id}}.json + output/{{video_id}}.csv.")
        print(f"Running cost this run: ${grand_total:.4f}")


def cmd_score(args):
    from scoring import run_scoring
    run_scoring(Path(args.labels_dir), Path(args.out),
                args.threshold, Path(args.report),
                use_llm=args.llm_match, model=args.model)


def cmd_spotcheck(args):
    from scoring import run_spotcheck
    run_spotcheck(Path(args.labels_dir), Path(args.out), model=args.model)


def cmd_calibrate(args):
    from scoring import run_calibrate
    run_calibrate(Path(args.labels_dir), Path(args.out),
                  args.threshold, model=args.model, report_path=Path(args.report))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="process videos -> ./output/")
    r.add_argument("--videos-dir", default=str(ROOT / "videos"))
    r.add_argument("--urls", nargs="*", help="YouTube URLs to download via yt-dlp")
    r.add_argument("--api", action="store_true",
                   help="use OpenAI Whisper API instead of local faster-whisper")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--whisper-model", default="base",
                   help="faster-whisper size: tiny|base|small|medium|large-v3")
    r.add_argument("--no-reconcile", action="store_true",
                   help="skip the final LLM dedupe/reconciliation pass")
    r.add_argument("--scene-threshold", type=float, default=0.3,
                   help="ffmpeg scene-change sensitivity 0-1 (lower = more frames)")
    r.add_argument("--floor-interval", type=int, default=30,
                   help="guarantee one frame every N seconds (lower = more frames)")
    r.add_argument("--no-hold", action="store_true",
                   help="disable stillness-based 'held product' keyframes "
                        "(freezedetect + sharpest-frame pick)")
    r.add_argument("--no-description", action="store_true",
                   help="skip merging the creator's description list into the result")
    r.add_argument("--no-mirror", action="store_true",
                   help="skip auto-detecting/un-mirroring selfie-camera videos")
    r.add_argument("--recover", action="store_true",
                   help="EXPERIMENTAL opt-in: brand-recovery of brand-null shown "
                        "products via Claude's knowledge. OFF by default — it "
                        "hallucinates brands (measured F1 0.40 -> 0.29). Needs "
                        "external grounding (catalogue / Google Vision) to be safe.")
    r.add_argument("--out", default=str(ROOT / "output"))
    r.add_argument("--cache", default=str(ROOT / "cache"))
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("score", help="score ./output vs ./labels -> report.md")
    s.add_argument("--threshold", type=int, default=85,
                   help="fuzzy match threshold 0-100 (default 85)")
    s.add_argument("--llm-match", action="store_true",
                   help="grade with an LLM judge instead of fuzzy string matching "
                        "(tolerant of spelling/ASR variants, strict on real diffs)")
    s.add_argument("--model", default=DEFAULT_MODEL,
                   help="model for --llm-match")
    s.add_argument("--labels-dir", default=str(ROOT / "labels"))
    s.add_argument("--out", default=str(ROOT / "output"))
    s.add_argument("--report", default=str(ROOT / "report.md"))
    s.set_defaults(func=cmd_score)

    # spotcheck — interactive human review of the LLM judge's decisions
    sc = sub.add_parser("spotcheck", help="human review of LLM-judge decisions")
    sc.add_argument("--labels-dir", default=str(ROOT / "labels"))
    sc.add_argument("--out", default=str(ROOT / "output"))
    sc.add_argument("--model", default=DEFAULT_MODEL)
    sc.set_defaults(func=cmd_spotcheck)

    # calibrate — re-cut the confidence calibration table under the judge
    cal = sub.add_parser("calibrate", help="re-cut calibration table under the judge")
    cal.add_argument("--threshold", type=int, default=85,
                     help="fuzzy threshold for the side-by-side comparison column")
    cal.add_argument("--labels-dir", default=str(ROOT / "labels"))
    cal.add_argument("--out", default=str(ROOT / "output"))
    cal.add_argument("--model", default=DEFAULT_MODEL)
    cal.add_argument("--report", default=str(ROOT / "calibration.md"))
    cal.set_defaults(func=cmd_calibrate)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
