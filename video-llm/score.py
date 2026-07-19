#!/usr/bin/env python3
"""
Scoring / judge harness CLI (thin wrapper around scoring.py).

    python score.py score [--llm-match]   # accuracy report (fuzzy or LLM judge)
    python score.py spotcheck             # human review of the LLM judge's decisions
    python score.py calibrate             # re-cut confidence calibration under the judge

(Equivalent to `python extract.py <same subcommand>` — same code, either entry point.)
"""

import argparse
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

ROOT = Path(__file__).parent
DEFAULT_MODEL = "claude-sonnet-4-6"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("score", help="accuracy report")
    sc.add_argument("--threshold", type=int, default=85)
    sc.add_argument("--llm-match", action="store_true")
    sc.add_argument("--labels-dir", default=str(ROOT / "labels"))
    sc.add_argument("--out", default=str(ROOT / "output"))
    sc.add_argument("--report", default=str(ROOT / "report.md"))
    sc.add_argument("--model", default=DEFAULT_MODEL)

    sp = sub.add_parser("spotcheck", help="human review of LLM-judge decisions")
    sp.add_argument("--labels-dir", default=str(ROOT / "labels"))
    sp.add_argument("--out", default=str(ROOT / "output"))
    sp.add_argument("--model", default=DEFAULT_MODEL)

    cal = sub.add_parser("calibrate", help="re-cut calibration table under the judge")
    cal.add_argument("--threshold", type=int, default=85)
    cal.add_argument("--labels-dir", default=str(ROOT / "labels"))
    cal.add_argument("--out", default=str(ROOT / "output"))
    cal.add_argument("--model", default=DEFAULT_MODEL)
    cal.add_argument("--report", default=str(ROOT / "calibration.md"))

    args = ap.parse_args()
    import scoring
    if args.cmd == "score":
        scoring.run_scoring(Path(args.labels_dir), Path(args.out), args.threshold,
                            Path(args.report), use_llm=args.llm_match, model=args.model)
    elif args.cmd == "spotcheck":
        scoring.run_spotcheck(Path(args.labels_dir), Path(args.out), model=args.model)
    elif args.cmd == "calibrate":
        scoring.run_calibrate(Path(args.labels_dir), Path(args.out), args.threshold,
                              model=args.model, report_path=Path(args.report))


if __name__ == "__main__":
    sys.exit(main())
