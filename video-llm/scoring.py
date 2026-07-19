"""
Accuracy harness: match extracted products against hand-labeled ground truth
and report precision / recall / F1 plus a confidence-calibration table.

Ground truth: ./labels/{video_id}.csv with columns
    product_name, brand, variant_or_shade
Predictions:  ./output/{video_id}.json (written by `run`).
"""

import csv
import json
import random
import re
from pathlib import Path

from rapidfuzz import fuzz

JUDGE_CACHE_PATH = Path(__file__).parent / "judge_cache.json"
DEFAULT_JUDGE_MODEL = "claude-sonnet-4-6"
CAND_K = 4        # judge each prediction against up to this many fuzzy-nearest labels
CAND_MIN = 30     # ...that score at least this fuzzy ratio (else fall back to top 1)
SPOTCHECK_SEED = 42
SPOTCHECK_PER_STRATUM = 10


# --------------------------------------------------------------------------
# normalization + matching
# --------------------------------------------------------------------------
# Corporate filler words stripped from brands so "NYX" == "NYX Professional
# Makeup", "Charlotte Tilbury" == "Charlotte Tilbury Beauty", etc.
_BRAND_FILLER = ("professional makeup", "cosmetics", "beauty", "professional",
                 "makeup", "paris", "official")


def norm(s) -> str:
    s = (s or "").lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_brand(b) -> str:
    b = norm(b)
    for w in _BRAND_FILLER:
        b = re.sub(rf"\b{w}\b", "", b)
    return re.sub(r"\s+", " ", b).strip()


def _ratio(a, b) -> float:
    # max of token_sort (order-insensitive) and token_set (subset-tolerant, so
    # extra descriptive words / brand suffixes don't wrongly fail a real match).
    return max(fuzz.token_sort_ratio(a, b), fuzz.token_set_ratio(a, b))


def prod_key(brand, name) -> str:
    return norm(f"{_norm_brand(brand)} {name or ''}")


def _greedy_match(preds, gts, threshold, key_fn):
    """One-to-one greedy match by descending fuzzy score. Returns matched pairs."""
    pairs = []
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            sc = _ratio(key_fn(p), key_fn(g))
            if sc >= threshold:
                pairs.append((sc, i, j))
    pairs.sort(reverse=True)
    used_p, used_g, matched = set(), set(), []
    for sc, i, j in pairs:
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        matched.append((i, j, sc))
    return matched, used_p, used_g


# --------------------------------------------------------------------------
# LLM-judge matcher (tolerant of spelling/ASR variants, strict on real diffs)
# --------------------------------------------------------------------------
def llm_match_video(client, model, preds, gts):
    """Returns matched pairs [(pred_i, gt_j, variant_match)] via one LLM call."""
    import json as _json
    from prompts import MATCH_SCHEMA, MATCH_SYSTEM_PROMPT, build_match_messages
    if not preds or not gts:
        return []
    resp = client.messages.create(
        model=model, max_tokens=2000,
        system=MATCH_SYSTEM_PROMPT,
        messages=build_match_messages(preds, gts),
        output_config={"format": {"type": "json_schema", "schema": MATCH_SCHEMA}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    raw = _json.loads(text).get("matches", [])
    # enforce one-to-one, validate indices
    used_p, used_g, matched = set(), set(), []
    for m in raw:
        i, j = m.get("pred_index"), m.get("gt_index")
        if not (isinstance(i, int) and isinstance(j, int)):
            continue
        if not (0 <= i < len(preds) and 0 <= j < len(gts)):
            continue
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        matched.append((i, j, bool(m.get("variant_match"))))
    return matched


def score_from_matched(preds, gts, matched):
    """Compute product + product-variant metrics from a matched-pair list."""
    prod = _prf(len(matched), len(preds) - len(matched), len(gts) - len(matched))
    tp_pv = sum(1 for _, _, vm in matched if vm)
    pv = _prf(tp_pv, len(preds) - tp_pv, len(gts) - tp_pv)
    used_p = {i for i, _, _ in matched}
    return prod, pv, used_p


# --------------------------------------------------------------------------
# Per-pair cached judge (the canonical LLM matcher; used by score/spotcheck/calibrate)
# --------------------------------------------------------------------------
def load_judge_cache():
    return json.loads(JUDGE_CACHE_PATH.read_text()) if JUDGE_CACHE_PATH.exists() else {}


def save_judge_cache(cache):
    JUDGE_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _pkey(p):
    return (f"{_norm_brand(p.get('brand'))}|{norm(p.get('product_name'))}"
            f"|{norm(p.get('variant_or_shade'))}")


def cache_key(pred, gt):
    """Normalized (prediction, ground_truth) pair key — deterministic, order-fixed."""
    return _pkey(pred) + " <=> " + _pkey(gt)


def _parse_json_obj(text):
    """Robustly pull the first JSON object out of a model reply."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).rstrip("`").strip()
    a, b = text.find("{"), text.rfind("}")
    if a != -1 and b > a:
        text = text[a:b + 1]
    try:
        return json.loads(text)
    except Exception:
        return {}


def judge_pair(client, model, pred, gt, cache):
    """Judge one (prediction, ground-truth) pair. Cached on disk; temperature 0.
    Uses plain-JSON output (not structured) to avoid grammar-compilation timeouts."""
    key = cache_key(pred, gt)
    if key in cache:
        return cache[key]
    from prompts import JUDGE_PAIR_SYSTEM_PROMPT, build_judge_pair_messages
    resp = client.messages.create(
        model=model, max_tokens=300, temperature=0,
        system=JUDGE_PAIR_SYSTEM_PROMPT,
        messages=build_judge_pair_messages(pred, gt),
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = _parse_json_obj(text)
    v = {"match": bool(data.get("match")),
         "variant_match": bool(data.get("variant_match")),
         "reasoning": data.get("reasoning", "")}
    cache[key] = v
    return v


def judge_match_video(client, model, preds, gts, cache):
    """Per-pair judge matching for one video. Returns (matched, decisions).
    matched = [(pred_i, gt_j, variant_match)] (one-to-one);
    decisions = every pair judged, each a dict with the verdict + reasoning + fuzzy."""
    decisions, accepted = [], []
    for i, p in enumerate(preds):
        pk = prod_key(p.get("brand"), p.get("product_name"))
        ranked = sorted(
            range(len(gts)),
            key=lambda j: -_ratio(pk, prod_key(gts[j].get("brand"), gts[j].get("product_name"))),
        )
        cands = [j for j in ranked
                 if _ratio(pk, prod_key(gts[j].get("brand"), gts[j].get("product_name"))) >= CAND_MIN][:CAND_K]
        if not cands and ranked:
            cands = ranked[:1]
        for j in cands:
            v = judge_pair(client, model, p, gts[j], cache)
            fr = _ratio(pk, prod_key(gts[j].get("brand"), gts[j].get("product_name")))
            decisions.append({"pred_i": i, "gt_j": j, "match": v["match"],
                              "variant_match": v["variant_match"],
                              "reasoning": v["reasoning"], "fuzzy_ratio": fr})
            if v["match"]:
                accepted.append((i, j, v["variant_match"], fr))
    # one-to-one, fuzzy ratio as tiebreak among accepted pairs
    accepted.sort(key=lambda x: -x[3])
    used_p, used_g, matched = set(), set(), []
    for i, j, vm, _fr in accepted:
        if i in used_p or j in used_g:
            continue
        used_p.add(i)
        used_g.add(j)
        matched.append((i, j, vm))
    return matched, decisions


def _prf(tp, fp, fn) -> dict:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": p, "recall": r, "f1": f}


def score_video(preds, gts, threshold):
    """Returns product-level metrics, product+variant metrics, and the set of
    prediction indices that matched at product level (for calibration)."""
    matched, used_p, _ = _greedy_match(
        preds, gts, threshold, lambda x: prod_key(x.get("brand"), x.get("product_name"))
    )
    prod = _prf(len(matched), len(preds) - len(matched), len(gts) - len(matched))

    # product+variant: among product-matched pairs, also require variant match
    tp_pv = 0
    for i, j, _sc in matched:
        pv, gv = norm(preds[i].get("variant_or_shade")), norm(gts[j].get("variant_or_shade"))
        if (not pv and not gv) or _ratio(pv, gv) >= threshold:
            tp_pv += 1
    pv_metrics = _prf(tp_pv, len(preds) - tp_pv, len(gts) - tp_pv)

    return prod, pv_metrics, used_p


# --------------------------------------------------------------------------
# confidence calibration
# --------------------------------------------------------------------------
BUCKETS = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)]


def bucket_label(lo, hi):
    hi = min(hi, 1.0)
    return f"{lo:.2f}-{hi:.2f}"


def calibrate(preds, matched_idx, acc):
    """Accumulate per-bucket (count, num correct) into `acc`."""
    for i, p in enumerate(preds):
        c = p.get("confidence", 0.0)
        for lo, hi in BUCKETS:
            if lo <= c < hi:
                key = bucket_label(lo, hi)
                acc.setdefault(key, [0, 0])
                acc[key][0] += 1
                if i in matched_idx:
                    acc[key][1] += 1
                break


# --------------------------------------------------------------------------
# IO
# --------------------------------------------------------------------------
def load_labels(fp: Path) -> list:
    with open(fp, newline="") as f:
        return [
            {"product_name": row.get("product_name", ""),
             "brand": row.get("brand", ""),
             "variant_or_shade": row.get("variant_or_shade", "")}
            for row in csv.DictReader(f)
        ]


def load_predictions(fp: Path) -> list:
    if not fp.exists():
        return []
    return json.loads(fp.read_text()).get("products", [])


# --------------------------------------------------------------------------
# PART 1: judge spot-check
# --------------------------------------------------------------------------
def collect_decisions(labels_dir: Path, out_dir: Path, client, model, cache):
    """Every per-pair judge decision across all videos (uses cache; free re-runs)."""
    recs = []
    for lf in sorted(labels_dir.glob("*.csv")):
        vid = lf.stem
        gts = load_labels(lf)
        preds = load_predictions(out_dir / f"{vid}.json")
        _matched, decisions = judge_match_video(client, model, preds, gts, cache)
        for d in decisions:
            recs.append({
                "video_id": vid,
                "pred": preds[d["pred_i"]],
                "gt": gts[d["gt_j"]],
                "judge_match": d["match"],
                "reasoning": d["reasoning"],
                "fuzzy_match": d["fuzzy_ratio"] >= 85,
            })
    for k, r in enumerate(recs):
        r["idx"] = k
    return recs


def run_spotcheck(labels_dir: Path, out_dir: Path, model=DEFAULT_JUDGE_MODEL,
                  results_path: Path = None, input_fn=input):
    import anthropic
    results_path = results_path or (Path(__file__).parent / "spotcheck_results.csv")
    client = anthropic.Anthropic()
    cache = load_judge_cache()
    print("Collecting judge decisions (cached where available)...")
    recs = collect_decisions(labels_dir, out_dir, client, model, cache)
    save_judge_cache(cache)
    if not recs:
        print("No judge decisions found. Run scoring/calibrate first.")
        return

    accepts = [r for r in recs if r["judge_match"]]
    rejects = [r for r in recs if not r["judge_match"]]
    disagree = [r for r in recs if r["judge_match"] != r["fuzzy_match"]]

    rng = random.Random(SPOTCHECK_SEED)
    picked, seen = [], set()
    for pool in (accepts, rejects, disagree):
        shuffled = list(pool)
        rng.shuffle(shuffled)
        for r in shuffled[:SPOTCHECK_PER_STRATUM]:
            if r["idx"] not in seen:
                seen.add(r["idx"])
                picked.append(r)

    print(f"\nSpot-checking {len(picked)} judge decisions "
          f"(~10 accepts / ~10 rejects / ~10 judge-vs-fuzzy disagreements).")
    print("For each: y = judge was right,  n = judge was wrong,  s = skip/unsure.\n")

    def line(p):
        b = p.get("brand") or "—"
        v = p.get("variant_or_shade") or ""
        return f"{b} — {p.get('product_name','')}" + (f"  ({v})" if v else "")

    for k, r in enumerate(picked, 1):
        verdict = "MATCH" if r["judge_match"] else "NO MATCH"
        flag = "  [judge≠fuzzy]" if r["judge_match"] != r["fuzzy_match"] else ""
        print(f"[{k}/{len(picked)}]  video {r['video_id']}{flag}")
        print(f"   predicted : {line(r['pred'])}")
        print(f"   candidate : {line(r['gt'])}")
        print(f"   JUDGE     : {verdict}  —  {r['reasoning']}")
        ans = ""
        while ans not in ("y", "n", "s"):
            ans = input_fn("   judge correct? [y/n/s]: ").strip().lower()
        r["human"] = ans
        print()

    # write results
    with open(results_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "pred_brand", "pred_name", "pred_variant",
                    "gt_brand", "gt_name", "gt_variant",
                    "judge_verdict", "reasoning", "judge_vs_fuzzy", "human"])
        for r in picked:
            p, g = r["pred"], r["gt"]
            w.writerow([r["video_id"], p.get("brand", ""), p.get("product_name", ""),
                        p.get("variant_or_shade", ""), g.get("brand", ""),
                        g.get("product_name", ""), g.get("variant_or_shade", ""),
                        "match" if r["judge_match"] else "no_match", r["reasoning"],
                        "disagree" if r["judge_match"] != r["fuzzy_match"] else "agree",
                        r.get("human", "")])

    reviewed = [r for r in picked if r.get("human") in ("y", "n")]
    def rate(pool):
        rv = [r for r in pool if r.get("human") in ("y", "n")]
        return (sum(1 for r in rv if r["human"] == "y") / len(rv)) if rv else None, len(rv)
    overall, n_over = rate(picked)
    acc_rate, n_acc = rate([r for r in picked if r["judge_match"]])
    rej_rate, n_rej = rate([r for r in picked if not r["judge_match"]])
    disagreements = [r for r in reviewed if r["human"] == "n"]

    print("=" * 60)
    print(f"Reviewed {n_over} decisions ({len(picked)-n_over} skipped).")
    if overall is not None:
        print(f"  Overall human–judge agreement : {overall:.0%}  ({n_over} reviewed)")
    if acc_rate is not None:
        print(f"  Agreement on ACCEPTS (judge=match)   : {acc_rate:.0%}  ({n_acc})")
    if rej_rate is not None:
        print(f"  Agreement on REJECTS (judge=no-match): {rej_rate:.0%}  ({n_rej})")
    if disagreements:
        print(f"\n  {len(disagreements)} case(s) where YOU disagreed with the judge "
              f"(judge bugs to fix):")
        for r in disagreements:
            v = "MATCH" if r["judge_match"] else "NO MATCH"
            print(f"    [{r['video_id']}] {line(r['pred'])}  ~vs~  {line(r['gt'])}")
            print(f"        judge said {v}: {r['reasoning']}")
    print()
    if overall is not None:
        verdict = "PASS" if overall >= 0.90 else "FAIL"
        print(f"  PASS bar = 90% agreement  ->  {verdict}  ({overall:.0%})")
    print(f"\nWrote {results_path}")


# --------------------------------------------------------------------------
# PART 2: re-cut calibration table under the judge matcher
# --------------------------------------------------------------------------
def _collect_confidence_correct(labels_dir, out_dir, client, model, cache, threshold):
    """Per-prediction (confidence, judge_correct, fuzzy_correct) across all videos."""
    judge_rows, fuzzy_rows = [], []
    for lf in sorted(labels_dir.glob("*.csv")):
        vid = lf.stem
        gts = load_labels(lf)
        preds = load_predictions(out_dir / f"{vid}.json")
        jmatched, _ = judge_match_video(client, model, preds, gts, cache)
        j_idx = {i for i, _, _ in jmatched}
        _p, _pv, f_idx = score_video(preds, gts, threshold)
        for i, p in enumerate(preds):
            c = float(p.get("confidence", 0))
            judge_rows.append((c, i in j_idx))
            fuzzy_rows.append((c, i in f_idx))
    return judge_rows, fuzzy_rows


_CALIB_BUCKETS = [(">= 0.85", 0.85, 1.01), ("0.70 - 0.85", 0.70, 0.85),
                  ("< 0.70", 0.0, 0.70)]


def _bucket_rows(data):
    out = []
    for name, lo, hi in _CALIB_BUCKETS:
        items = [ok for c, ok in data if lo <= c < hi]
        n, k = len(items), sum(items)
        out.append([name, n, k, f"{k / n:.2f}" if n else "-"])
    return out


def run_calibrate(labels_dir: Path, out_dir: Path, threshold: int,
                  model=DEFAULT_JUDGE_MODEL, report_path: Path = None):
    import anthropic
    from tabulate import tabulate
    report_path = report_path or (Path(__file__).parent / "calibration.md")
    client = anthropic.Anthropic()
    cache = load_judge_cache()
    print(f"Re-scoring all videos with the judge ({model}); reusing cached pairs...")
    judge_rows, fuzzy_rows = _collect_confidence_correct(
        labels_dir, out_dir, client, model, cache, threshold)
    save_judge_cache(cache)
    total = len(judge_rows)

    # --- bucket tables, side by side ---
    jb, fb = _bucket_rows(judge_rows), _bucket_rows(fuzzy_rows)
    side = [[jb[i][0], fb[i][1], fb[i][2], fb[i][3], jb[i][2], jb[i][3]]
            for i in range(len(jb))]
    bucket_tbl = tabulate(
        side, headers=["confidence", "#preds", "fuzzy #correct", "fuzzy prec",
                       "judge #correct", "judge prec"], tablefmt="github")

    # --- fine sweep on judge correctness ---
    sweep, cross = [], None
    t = 0.70
    while t <= 0.9501:
        appr = [ok for c, ok in judge_rows if c >= t - 1e-9]
        cov = len(appr) / total if total else 0
        prec = (sum(appr) / len(appr)) if appr else 0.0
        sweep.append([f"{t:.3f}", len(appr), f"{cov:.0%}", f"{prec:.3f}"])
        if cross is None and appr and prec >= 0.90:
            cross = (t, cov, prec)
        t += 0.025
    sweep_tbl = tabulate(sweep, headers=["threshold", "#approved",
                         "coverage", "precision"], tablefmt="github")

    out = ["# Confidence calibration — judge matcher\n",
           f"Matcher: **LLM judge ({model})**  |  {total} predictions across "
           f"{len(list(labels_dir.glob('*.csv')))} videos\n",
           "## Buckets — fuzzy vs judge (side by side)\n", bucket_tbl + "\n",
           "## Threshold sweep (auto-approve at confidence >= T; judge-verified)\n",
           sweep_tbl + "\n"]
    if cross:
        t, cov, prec = cross
        rec = (f"**Recommended auto-approve threshold: confidence >= {t:.3f}** "
               f"— lowest threshold with judge precision >= 0.90 "
               f"(precision {prec:.3f}, coverage {cov:.0%}).")
    else:
        rec = ("**No threshold in 0.70–0.95 reaches 0.90 precision under the judge.** "
               "Raise extraction quality or accept lower precision.")
    out.append("## Recommendation\n")
    out.append(rec + "\n")
    old_rule = ("\n> The old >= 0.85 rule was derived under the fuzzy matcher. "
                "Under the judge, use the recommendation above.")
    out.append(old_rule)
    report = "\n".join(out)

    print("\n" + report)
    report_path.write_text(report)
    print(f"\nWrote {report_path}")


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def _fmt(m):
    return (f"P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} "
            f"(tp={m['tp']} fp={m['fp']} fn={m['fn']})")


def run_scoring(labels_dir: Path, out_dir: Path, threshold: int,
                report_path: Path, use_llm: bool = False,
                model: str = "claude-sonnet-4-6"):
    from tabulate import tabulate

    label_files = sorted(labels_dir.glob("*.csv"))
    if not label_files:
        print(f"No label files found in {labels_dir}/. Add {{video_id}}.csv files first.")
        return

    client, cache = None, {}
    if use_llm:
        import anthropic
        client = anthropic.Anthropic()
        cache = load_judge_cache()
        print(f"Matching with LLM judge ({model})... (cached pairs reused)")

    rows = []
    agg = {k: {"tp": 0, "fp": 0, "fn": 0} for k in ("prod", "pv")}
    calib = {}

    for lf in label_files:
        video_id = lf.stem
        gts = load_labels(lf)
        preds = load_predictions(out_dir / f"{video_id}.json")

        if use_llm:
            matched, _dec = judge_match_video(client, model, preds, gts, cache)
            prod, pv, matched_idx = score_from_matched(preds, gts, matched)
        else:
            prod, pv, matched_idx = score_video(preds, gts, threshold)
        calibrate(preds, matched_idx, calib)

        for m, key in ((prod, "prod"), (pv, "pv")):
            for k in ("tp", "fp", "fn"):
                agg[key][k] += m[k]

        rows.append([
            video_id, len(gts), len(preds),
            f"{prod['precision']:.2f}", f"{prod['recall']:.2f}", f"{prod['f1']:.2f}",
            f"{pv['precision']:.2f}", f"{pv['recall']:.2f}", f"{pv['f1']:.2f}",
        ])

    if use_llm:
        save_judge_cache(cache)

    prod_agg = _prf(**agg["prod"])
    pv_agg = _prf(**agg["pv"])

    headers = ["video", "#gt", "#pred",
               "prod_P", "prod_R", "prod_F1",
               "pv_P", "pv_R", "pv_F1"]
    per_video = tabulate(rows, headers=headers, tablefmt="github")

    agg_tbl = tabulate(
        [["Product-level", f"{prod_agg['precision']:.3f}", f"{prod_agg['recall']:.3f}",
          f"{prod_agg['f1']:.3f}", prod_agg["tp"], prod_agg["fp"], prod_agg["fn"]],
         ["Product+Variant", f"{pv_agg['precision']:.3f}", f"{pv_agg['recall']:.3f}",
          f"{pv_agg['f1']:.3f}", pv_agg["tp"], pv_agg["fp"], pv_agg["fn"]]],
        headers=["level", "precision", "recall", "F1", "TP", "FP", "FN"],
        tablefmt="github",
    )

    calib_rows = []
    for lo, hi in BUCKETS:
        key = bucket_label(lo, hi)
        n, correct = calib.get(key, [0, 0])
        acc = (correct / n) if n else 0.0
        calib_rows.append([key, n, correct, f"{acc:.2f}" if n else "-"])
    calib_tbl = tabulate(
        calib_rows,
        headers=["confidence", "#preds", "#correct", "precision"],
        tablefmt="github",
    )

    out = []
    out.append(f"# Extraction accuracy report\n")
    matcher = f"LLM judge ({model})" if use_llm else f"fuzzy (threshold {threshold})"
    out.append(f"Matcher: **{matcher}**  |  videos scored: **{len(label_files)}**\n")
    out.append("## Per-video\n")
    out.append(per_video + "\n")
    out.append("## Aggregate\n")
    out.append(agg_tbl + "\n")
    out.append("## Confidence calibration (product-level)\n")
    out.append("Precision within each confidence bucket — use it to pick an "
               "auto-approve threshold.\n")
    out.append(calib_tbl + "\n")
    report = "\n".join(out)

    print("\n" + report)
    report_path.write_text(report)
    print(f"\nWrote {report_path}")
