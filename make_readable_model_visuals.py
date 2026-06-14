#!/usr/bin/env python3
"""
Create thesis-friendly visualizations from the filtered M16 age-group logs.

The full Inductive Miner Petri nets are useful as artifacts, but they are often
too dense for a thesis page. By default this script exports smaller
directly-follows graphs (DFGs) with only the most frequent edges. Use the
top-15 graph in the thesis body and keep larger graphs as appendix material.
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import pm4py
from graphviz import Digraph
from pm4py.objects.log.importer.xes import importer as xes_importer


GROUPS = ["age_le_55", "age_gt_55"]


def export_petri(log, group, out_dir):
    net, im, fm = pm4py.discover_petri_net_inductive(log)
    gviz = pm4py.visualization.petri_net.visualizer.apply(net, im, fm)
    pm4py.visualization.petri_net.visualizer.save(gviz, str(out_dir / f"{group}_inductive_miner_zoomable.svg"))
    pm4py.visualization.petri_net.visualizer.save(gviz, str(out_dir / f"{group}_inductive_miner_printable.pdf"))


def readable_activity_label(label, max_words=4, max_chars=32):
    text = str(label).replace("\n", " ").strip()
    words = text.split()
    if len(words) > max_words:
        text = " ".join(words[:max_words]) + "..."
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text


def export_dfg(log, group, out_dir, max_edges, min_edge_freq):
    dfg, start_activities, end_activities = pm4py.discover_dfg(log)
    frequent_edges = [(edge, count) for edge, count in dfg.items() if count >= min_edge_freq]
    top_edges = sorted(frequent_edges, key=lambda item: item[1], reverse=True)[:max_edges]

    graph = Digraph(name=f"{group}_dfg", format="svg")
    graph.attr(
        rankdir="LR",
        label=f"{group}: core directly-follows graph, top {len(top_edges)} edges",
        labelloc="t",
        fontsize="18",
        concentrate="true",
        splines="polyline",
        ranksep="0.75",
        nodesep="0.35",
        margin="0.05",
    )
    graph.attr("node", shape="box", fontsize="13", margin="0.08,0.04", height="0.28")
    graph.attr("edge", fontsize="11", arrowsize="0.7")

    activities = set()
    for (source, target), _count in top_edges:
        activities.add(source)
        activities.add(target)

    for activity in sorted(activities):
        graph.node(activity, readable_activity_label(activity))
    for (source, target), count in top_edges:
        graph.edge(source, target, label=str(count), penwidth=str(1 + min(count, 20) / 8))

    svg_base = str(out_dir / f"{group}_dfg_top_{max_edges}_edges")
    graph.render(svg_base, cleanup=True)
    graph.format = "pdf"
    graph.render(svg_base, cleanup=True)
    graph.format = "png"
    graph.render(svg_base, cleanup=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results_m16_spc_pm4py")
    parser.add_argument(
        "--max-dfg-edges",
        type=int,
        default=None,
        help="Deprecated single-size option. Prefer --dfg-edge-counts.",
    )
    parser.add_argument(
        "--dfg-edge-counts",
        default="15,25",
        help="Comma-separated DFG sizes to export. Default creates clear thesis-body and appendix versions.",
    )
    parser.add_argument("--min-edge-freq", type=int, default=2, help="Hide edges that occur fewer than this many times.")
    parser.add_argument("--include-full-petri", action="store_true", help="Also export huge full Petri net SVG/PDF files.")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    logs_dir = results_dir / "filtered_logs"
    out_dir = results_dir / "readable_visuals"
    out_dir.mkdir(parents=True, exist_ok=True)

    for group in GROUPS:
        log_path = logs_dir / f"{group}.xes"
        log = xes_importer.apply(str(log_path))
        if args.include_full_petri:
            export_petri(log, group, out_dir)
        if args.max_dfg_edges is not None:
            edge_counts = [args.max_dfg_edges]
        else:
            edge_counts = [int(value.strip()) for value in args.dfg_edge_counts.split(",") if value.strip()]
        for edge_count in edge_counts:
            export_dfg(log, group, out_dir, edge_count, args.min_edge_freq)

    print(f"Readable visuals written to {out_dir.resolve()}")


if __name__ == "__main__":
    main()
