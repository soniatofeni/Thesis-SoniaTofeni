#!/usr/bin/env python3
"""
Reproduce the process-mining/SPC export pipeline for BPI Challenge 2011 M16.

Outputs are written to results_m16_spc_pm4py/ and are intended to be clean
inputs for later LLM prompting/evaluation.

Main SPC conformance results use cross-model replay:
  age_gt_55 log -> age_le_55 model
  age_le_55 log -> age_gt_55 model
"""

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from statistics import mean, median

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import pm4py
from pm4py.algo.conformance.alignments.petri_net import algorithm as alignments
from pm4py.algo.conformance.tokenreplay import algorithm as token_replay
from pm4py.algo.evaluation.earth_mover_distance import algorithm as emd
from pm4py.objects.log.importer.xes import importer as xes_importer
from pm4py.objects.log.obj import EventLog


DEFAULT_LOG = "Hospital_log.xes"
OUT_DIR = Path("results_m16_spc_pm4py")


def trace_keys(log):
    keys = Counter()
    values = defaultdict(Counter)
    for trace in log:
        for key, value in trace.attributes.items():
            keys[key] += 1
            if len(values[key]) < 25:
                values[key][str(value)] += 1
    return keys, values


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)


def remove_obsolete_own_model_outputs(out_dir):
    """Remove old non-cross-model conformance files from earlier pipeline versions."""
    obsolete_patterns = [
        "conformance/own_model_*",
        "conformance/age_le_*",
        "conformance/age_gt_*",
        "filtered_logs/own_model_*",
        "filtered_logs/age_le_*_alignment_sample.xes",
        "filtered_logs/age_gt_*_alignment_sample.xes",
    ]
    for pattern in obsolete_patterns:
        for path in out_dir.glob(pattern):
            if path.is_file():
                path.unlink()
    obsolete_summary = out_dir / "own_model_metrics_summary.csv"
    if obsolete_summary.exists():
        obsolete_summary.unlink()


def diagnosis_keys(attrs):
    return sorted([k for k in attrs if k == "Diagnosis code" or k.startswith("Diagnosis code:")])


def age_keys(attrs):
    return sorted([k for k in attrs if k == "Age" or k.startswith("Age:")])


def trace_has_diagnosis(trace, diagnosis_code):
    return any(str(trace.attributes.get(k, "")).strip() == diagnosis_code for k in diagnosis_keys(trace.attributes))


def first_numeric_age(trace):
    ages = []
    for key in age_keys(trace.attributes):
        raw = trace.attributes.get(key)
        try:
            ages.append(int(float(str(raw).strip())))
        except (TypeError, ValueError):
            pass
    return ages[0] if ages else None, ages


def clone_log(traces, source_log):
    new_log = EventLog(
        attributes=deepcopy(getattr(source_log, "attributes", {})),
        extensions=deepcopy(getattr(source_log, "extensions", {})),
        classifiers=deepcopy(getattr(source_log, "classifiers", {})),
        omni_present=deepcopy(getattr(source_log, "omni_present", {})),
    )
    for trace in traces:
        new_log.append(deepcopy(trace))
    return new_log


def length_stats(log):
    lengths = [len(t) for t in log]
    if not lengths:
        return {"traces": 0, "events": 0}
    return {
        "traces": len(log),
        "events": sum(lengths),
        "min_events": min(lengths),
        "median_events": median(lengths),
        "mean_events": round(mean(lengths), 2),
        "max_events": max(lengths),
    }


def get_variants(log):
    variants = Counter()
    for trace in log:
        variant = tuple(str(ev.get("concept:name", "")) for ev in trace)
        variants[variant] += 1
    return variants


def variant_rows(log, group, top_n=25):
    total = len(log) or 1
    rows = []
    for rank, (variant, count) in enumerate(get_variants(log).most_common(top_n), 1):
        rows.append({
            "group": group,
            "rank": rank,
            "trace_count": count,
            "percentage": round(100 * count / total, 2),
            "variant_length": len(variant),
            "variant": " > ".join(variant),
        })
    return rows


def stochastic_language(log):
    variants = get_variants(log)
    total = sum(variants.values()) or 1
    return {variant: count / total for variant, count in variants.items()}


def representative_alignment_log(log, source_log, sample_size=10, max_events=40):
    """Pick one trace per frequent variant, bounded by trace length and count."""
    variant_counts = get_variants(log)
    candidates = []
    seen = set()
    for trace in sorted(log, key=lambda t: (-variant_counts[tuple(str(ev.get("concept:name", "")) for ev in t)], len(t))):
        variant = tuple(str(ev.get("concept:name", "")) for ev in trace)
        if variant in seen or len(trace) > max_events:
            continue
        seen.add(variant)
        candidates.append(trace)
        if len(candidates) >= sample_size:
            break
    if len(candidates) < sample_size:
        for trace in sorted(log, key=len):
            if trace in candidates or len(trace) > max_events:
                continue
            candidates.append(trace)
            if len(candidates) >= sample_size:
                break
    return clone_log(candidates, source_log)


def alignment_summary(log, net, im, fm, max_time_trace=10, max_time_total=120):
    variant = alignments.Variants.VERSION_STATE_EQUATION_A_STAR
    params = {
        variant.value.Parameters.PARAM_MAX_ALIGN_TIME_TRACE: max_time_trace,
        variant.value.Parameters.PARAM_MAX_ALIGN_TIME: max_time_total,
    }
    results = alignments.apply_log(log, net, im, fm, parameters=params, variant=variant)
    rows = []
    totals = Counter()
    fitnesses = []
    for idx, res in enumerate(results):
        if res is None:
            rows.append({
                "trace_index": idx,
                "fitness": None,
                "cost": None,
                "queued_states": None,
                "visited_states": None,
                "traversed_arcs": None,
                "status": "timeout_or_no_alignment",
            })
            continue
        fitnesses.append(res.get("fitness"))
        for move in res.get("alignment", []):
            if len(move) >= 2 and isinstance(move[0], str):
                log_move, model_move = move[0], move[1]
            else:
                log_move, model_move = move[0]
            if log_move == ">>" and model_move != ">>":
                totals[f"model_move::{model_move}"] += 1
            elif model_move == ">>" and log_move != ">>":
                totals[f"log_move::{log_move}"] += 1
        rows.append({
            "trace_index": idx,
            "fitness": res.get("fitness"),
            "cost": res.get("cost"),
            "queued_states": res.get("queued_states"),
            "visited_states": res.get("visited_states"),
            "traversed_arcs": res.get("traversed_arcs"),
            "status": "ok",
        })
    summary = {
        "trace_count": len(results),
        "mean_trace_fitness": round(mean([x for x in fitnesses if x is not None]), 6) if fitnesses else None,
        "deviations": [{"deviation": k, "count": v} for k, v in totals.most_common()],
        "max_time_per_trace_seconds": max_time_trace,
        "max_time_total_seconds": max_time_total,
    }
    return summary, rows


def token_summary(log, net, im, fm):
    results = token_replay.apply(log, net, im, fm, parameters={
        token_replay.Variants.TOKEN_REPLAY.value.Parameters.ENABLE_PLTR_FITNESS: True
    })
    if isinstance(results, tuple):
        results = results[0]
    rows = []
    place_missing = Counter()
    place_remaining = Counter()
    def token_total(value):
        if isinstance(value, dict):
            return sum(value.values())
        if isinstance(value, list):
            return len(value)
        return value

    def count_places(value):
        if isinstance(value, dict):
            for place, count in value.items():
                yield str(place), count
        elif isinstance(value, list):
            for place in value:
                yield str(place), 1

    for idx, res in enumerate(results):
        for place, count in count_places(res.get("missing_tokens", {})):
            place_missing[str(place)] += count
        for place, count in count_places(res.get("remaining_tokens", {})):
            place_remaining[str(place)] += count
        rows.append({
            "trace_index": idx,
            "trace_is_fit": res.get("trace_is_fit"),
            "trace_fitness": res.get("trace_fitness"),
            "missing_tokens": token_total(res.get("missing_tokens")),
            "remaining_tokens": token_total(res.get("remaining_tokens")),
            "consumed_tokens": res.get("consumed_tokens"),
            "produced_tokens": res.get("produced_tokens"),
        })
    fitnesses = [r["trace_fitness"] for r in rows if r["trace_fitness"] is not None]
    summary = {
        "trace_count": len(results),
        "fit_trace_count": sum(1 for r in rows if r["trace_is_fit"]),
        "mean_trace_fitness": round(mean(fitnesses), 6) if fitnesses else None,
        "missing_tokens_by_place": [{"place": k, "count": v} for k, v in place_missing.most_common()],
        "remaining_tokens_by_place": [{"place": k, "count": v} for k, v in place_remaining.most_common()],
    }
    return summary, rows


def discover_and_export(log, group, out_dir):
    net, im, fm = pm4py.discover_petri_net_inductive(log)
    (out_dir / "models").mkdir(parents=True, exist_ok=True)
    pm4py.write_pnml(net, im, fm, out_dir / "models" / f"{group}_inductive_miner.pnml")
    try:
        gviz = pm4py.visualization.petri_net.visualizer.apply(net, im, fm)
        pm4py.visualization.petri_net.visualizer.save(gviz, str(out_dir / "models" / f"{group}_inductive_miner.png"))
    except Exception as exc:
        save_json(out_dir / "models" / f"{group}_visualization_error.json", {"error": repr(exc)})
    return net, im, fm


def should_run_alignment_for_group(args, observed_group):
    if args.alignment_mode == "none":
        return False
    if args.align_group == "age_le":
        return observed_group.startswith("age_le_")
    if args.align_group == "age_gt":
        return observed_group.startswith("age_gt_")
    return True


def conformance_comparison(
    observed_group,
    model_group,
    observed_log,
    model_tuple,
    source_log,
    out_dir,
    args,
    prefix,
):
    net, im, fm = model_tuple
    should_align = should_run_alignment_for_group(args, observed_group)

    if should_align:
        align_log = observed_log
        if args.alignment_mode == "representative":
            align_log = representative_alignment_log(
                observed_log,
                source_log,
                sample_size=args.alignment_sample_size,
                max_events=args.alignment_max_events,
            )
            pm4py.write_xes(
                align_log,
                out_dir / "filtered_logs" / f"{prefix}_{observed_group}_on_{model_group}_alignment_sample.xes",
            )
        align_summary, align_rows = alignment_summary(
            align_log,
            net,
            im,
            fm,
            max_time_trace=args.alignment_max_time_trace,
            max_time_total=args.alignment_max_time_total,
        )
        align_summary["comparison_type"] = prefix
        align_summary["observed_log"] = observed_group
        align_summary["model"] = model_group
        align_summary["alignment_mode"] = args.alignment_mode
        align_summary["source_trace_count"] = len(observed_log)
        if args.alignment_mode == "representative":
            align_summary["sample_size_requested"] = args.alignment_sample_size
            align_summary["sample_max_events"] = args.alignment_max_events
        save_json(out_dir / "conformance" / f"{prefix}_{observed_group}_on_{model_group}_alignment_summary.json", align_summary)
        write_csv(
            out_dir / "conformance" / f"{prefix}_{observed_group}_on_{model_group}_alignment_traces.csv",
            align_rows,
            list(align_rows[0].keys()) if align_rows else ["trace_index"],
        )
    else:
        align_summary = {
            "comparison_type": prefix,
            "observed_log": observed_group,
            "model": model_group,
            "trace_count": len(observed_log),
            "mean_trace_fitness": None,
            "deviations": [],
            "skipped": True,
            "alignment_mode": "none",
            "reason": "Exact alignments skipped by command-line option.",
        }
        save_json(out_dir / "conformance" / f"{prefix}_{observed_group}_on_{model_group}_alignment_summary.json", align_summary)

    tok_summary, tok_rows = token_summary(observed_log, net, im, fm)
    tok_summary["comparison_type"] = prefix
    tok_summary["observed_log"] = observed_group
    tok_summary["model"] = model_group
    save_json(out_dir / "conformance" / f"{prefix}_{observed_group}_on_{model_group}_token_replay_summary.json", tok_summary)
    write_csv(
        out_dir / "conformance" / f"{prefix}_{observed_group}_on_{model_group}_token_replay_traces.csv",
        tok_rows,
        list(tok_rows[0].keys()) if tok_rows else ["trace_index"],
    )

    return {
        "comparison_type": prefix,
        "observed_log": observed_group,
        "model": model_group,
        **length_stats(observed_log),
        "alignment_mean_trace_fitness": align_summary["mean_trace_fitness"],
        "token_replay_mean_trace_fitness": tok_summary["mean_trace_fitness"],
        "token_replay_fit_trace_count": tok_summary["fit_trace_count"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=DEFAULT_LOG)
    parser.add_argument("--diagnosis", default="M16")
    parser.add_argument("--age-cutoff", type=int, default=55)
    parser.add_argument("--min-events", type=int, default=6)
    parser.add_argument("--max-events", type=int, default=100)
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--alignment-mode", choices=["representative", "none", "full"], default="representative", help="Representative is recommended for this thesis pipeline.")
    parser.add_argument("--skip-alignments", action="store_true", help="Alias for --alignment-mode none.")
    parser.add_argument("--align-group", choices=["all", "age_le", "age_gt"], default="all", help="Limit exact alignments to one subgroup.")
    parser.add_argument("--alignment-sample-size", type=int, default=10, help="Representative alignment traces per subgroup.")
    parser.add_argument("--alignment-max-events", type=int, default=40, help="Maximum events per trace in representative alignment sample.")
    parser.add_argument("--alignment-max-time-trace", type=int, default=10, help="Maximum alignment seconds per trace.")
    parser.add_argument("--alignment-max-time-total", type=int, default=120, help="Maximum alignment seconds per subgroup.")
    args = parser.parse_args()
    if args.skip_alignments:
        args.alignment_mode = "none"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    remove_obsolete_own_model_outputs(out_dir)

    log = xes_importer.apply(args.log)
    keys, samples = trace_keys(log)
    trace_attr_rows = [{
        "attribute": key,
        "trace_count": count,
        "sample_values": "; ".join([f"{v} ({c})" for v, c in samples[key].most_common(10)]),
    } for key, count in keys.most_common()]
    write_csv(out_dir / "trace_attribute_inventory.csv", trace_attr_rows, ["attribute", "trace_count", "sample_values"])

    m16 = []
    excluded_missing_age = []
    inconsistent_age = []
    for trace in log:
        if not trace_has_diagnosis(trace, args.diagnosis):
            continue
        age, ages = first_numeric_age(trace)
        if age is None:
            excluded_missing_age.append(trace.attributes.get("concept:name"))
            continue
        if len(set(ages)) > 1:
            inconsistent_age.append({"case": trace.attributes.get("concept:name"), "ages": ages})
        trace.attributes["spc:selected_age"] = age
        m16.append(trace)

    young_raw = [t for t in m16 if t.attributes["spc:selected_age"] <= args.age_cutoff]
    old_raw = [t for t in m16 if t.attributes["spc:selected_age"] > args.age_cutoff]
    young = [t for t in young_raw if args.min_events <= len(t) <= args.max_events]
    old = [t for t in old_raw if args.min_events <= len(t) <= args.max_events]

    logs = {
        f"age_le_{args.age_cutoff}": clone_log(young, log),
        f"age_gt_{args.age_cutoff}": clone_log(old, log),
    }

    preprocessing = {
        "input_log": args.log,
        "diagnosis_filter": args.diagnosis,
        "diagnosis_keys": sorted({k for t in log for k in diagnosis_keys(t.attributes)}),
        "age_keys": sorted({k for t in log for k in age_keys(t.attributes)}),
        "age_assignment": "first numeric Age* attribute in sorted key order",
        "age_cutoff": args.age_cutoff,
        "length_filter": [args.min_events, args.max_events],
        "all_log": length_stats(log),
        "m16_before_age_filter": len(m16) + len(excluded_missing_age),
        "m16_excluded_missing_age": len(excluded_missing_age),
        "m16_inconsistent_age_trace_count": len(inconsistent_age),
        "age_le_raw": length_stats(clone_log(young_raw, log)),
        "age_gt_raw": length_stats(clone_log(old_raw, log)),
        "age_le_after_length_filter": length_stats(logs[f"age_le_{args.age_cutoff}"]),
        "age_gt_after_length_filter": length_stats(logs[f"age_gt_{args.age_cutoff}"]),
    }
    save_json(out_dir / "preprocessing_summary.json", preprocessing)
    save_json(out_dir / "inconsistent_age_traces.json", inconsistent_age)

    (out_dir / "filtered_logs").mkdir(parents=True, exist_ok=True)
    for group, group_log in logs.items():
        pm4py.write_xes(group_log, out_dir / "filtered_logs" / f"{group}.xes")

    models = {group: discover_and_export(group_log, group, out_dir) for group, group_log in logs.items()}

    young_group = f"age_le_{args.age_cutoff}"
    old_group = f"age_gt_{args.age_cutoff}"
    cross_metrics_rows = [
        conformance_comparison(
            old_group,
            young_group,
            logs[old_group],
            models[young_group],
            log,
            out_dir,
            args,
            prefix="cross_model",
        ),
        conformance_comparison(
            young_group,
            old_group,
            logs[young_group],
            models[old_group],
            log,
            out_dir,
            args,
            prefix="cross_model",
        ),
    ]

    variant_all_rows = []
    for group, group_log in logs.items():
        variant_all_rows.extend(variant_rows(group_log, group, top_n=50))
    write_csv(out_dir / "variants" / "top_variants.csv", variant_all_rows, ["group", "rank", "trace_count", "percentage", "variant_length", "variant"])

    lang_young = stochastic_language(logs[f"age_le_{args.age_cutoff}"])
    lang_old = stochastic_language(logs[f"age_gt_{args.age_cutoff}"])
    emd_value = emd.apply(lang_young, lang_old)
    emsc_similarity = 1 - emd_value
    save_json(out_dir / "emsc" / "emsc_results.json", {
        "comparison": f"age_le_{args.age_cutoff} vs age_gt_{args.age_cutoff}",
        "earth_movers_distance": emd_value,
        "emsc_similarity": emsc_similarity,
        "note": "PM4Py returns Earth Mover's Distance over stochastic languages; similarity is reported as 1 - distance.",
        "language_sizes": {
            f"age_le_{args.age_cutoff}": len(lang_young),
            f"age_gt_{args.age_cutoff}": len(lang_old),
        }
    })

    write_csv(out_dir / "metrics_summary.csv", cross_metrics_rows, list(cross_metrics_rows[0].keys()) if cross_metrics_rows else ["group"])
    write_csv(out_dir / "cross_model_metrics_summary.csv", cross_metrics_rows, list(cross_metrics_rows[0].keys()) if cross_metrics_rows else ["group"])
    print(f"Done. Results written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
