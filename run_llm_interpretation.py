#!/usr/bin/env python3
"""
Prepare LLM interpretation prompts for free/manual web-interface use.

This script does not call any paid APIs. It reads the PM4Py result files,
builds a structured interpretation prompt, and writes copy-paste prompt files
for ChatGPT and Claude.

Run:
  python3 run_llm_interpretation.py

Then copy the generated prompt into the free ChatGPT and Claude web interfaces.
"""

import argparse
import csv
import json
from pathlib import Path


RESULT_FILES = [
    "metrics_summary.csv",
    "cross_model_metrics_summary.csv",
    "preprocessing_summary.json",
    "emsc/emsc_results.json",
    "conformance/cross_model_age_gt_55_on_age_le_55_token_replay_summary.json",
    "conformance/cross_model_age_le_55_on_age_gt_55_token_replay_summary.json",
    "conformance/cross_model_age_gt_55_on_age_le_55_alignment_summary.json",
    "conformance/cross_model_age_le_55_on_age_gt_55_alignment_summary.json",
    "variants/top_variants.csv",
]


INSTRUCTIONS = """You are an expert in process mining, conformance checking, and subpopulation process comparison.

I am writing a thesis titled:
"Using Large Language Models to Support the Evaluation of Subpopulation Process Comparison Techniques in Process Mining".

The process-mining analysis compares two M16 diagnosis-code subpopulations from the BPI Challenge 2011 hospital log:
1. patients aged <=55
2. patients aged >55

Please interpret the provided outputs as an expert process-mining analyst.

Return the answer in this structure:
1. Dataset and preprocessing interpretation
2. Token-based replay interpretation
3. Alignment-based conformance interpretation
4. Process variant comparison interpretation
5. EMSC / stochastic comparison interpretation
6. Overall comparison between the two subpopulations
7. Limitations and cautions

Important constraints:
- Interpret only the provided process-mining outputs.
- Do not claim that older patients received better or worse care.
- Do not infer clinical causality.
- Clearly distinguish between conformance results, variant results, and stochastic comparison results.
- Explain why high conformance fitness can coexist with low stochastic similarity.
- Mention that representative alignments are sample-based, not full-log alignments.
- Mention data-quality limitations where relevant.
- Treat cross-model conformance as the main SPC conformance comparison, because it replays one subpopulation log on the other subpopulation's model.
"""


README = """# Manual LLM interpretation workflow

This folder contains prompt files for free/manual use with ChatGPT and Claude.

1. Open `chatgpt_5_5_prompt.txt`.
2. Copy all text and paste it into ChatGPT 5.5.
3. Save the answer in `chatgpt_5_5_response.md`.
4. Open `claude_sonnet_4_6_prompt.txt`.
5. Copy all text and paste it into Claude Sonnet 4.6.
6. Save the answer in `claude_sonnet_4_6_response.md`.

Use the response files later for evaluation against your expert/reference
interpretation.

Methodology note for thesis:
The LLMs were accessed through their user-facing web interfaces. The same
structured prompt, generated from the PM4Py output files, was manually provided
to both models. Exact backend model settings such as temperature could not be
controlled, which is treated as a limitation.
"""


def compact_csv(path, max_rows):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    limited = rows[:max_rows]
    return {
        "columns": list(rows[0].keys()) if rows else [],
        "row_count": len(rows),
        "included_rows": len(limited),
        "rows": limited,
    }


def load_result_payload(results_dir, max_variant_rows):
    payload = {}
    for rel_path in RESULT_FILES:
        path = results_dir / rel_path
        if not path.exists():
            payload[rel_path] = {"missing": True}
            continue

        if path.suffix == ".csv":
            max_rows = max_variant_rows if rel_path == "variants/top_variants.csv" else 100
            payload[rel_path] = compact_csv(path, max_rows)
        else:
            payload[rel_path] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def build_prompt(payload, model_label):
    return (
        f"Target LLM: {model_label}\n\n"
        + INSTRUCTIONS
        + "\n\nPROCESS MINING OUTPUTS:\n"
        + json.dumps(payload, indent=2, ensure_ascii=False)
    )


def write_if_missing(path, text):
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results_m16_spc_pm4py")
    parser.add_argument("--out-dir", default="llm_interpretation_outputs")
    parser.add_argument("--max-variant-rows", type=int, default=20)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = load_result_payload(results_dir, args.max_variant_rows)

    shared_prompt = build_prompt(payload, "same prompt for all models")
    chatgpt_prompt = build_prompt(payload, "ChatGPT 5.5")
    claude_prompt = build_prompt(payload, "Claude Sonnet 4.6")

    (out_dir / "README_manual_workflow.md").write_text(README, encoding="utf-8")
    (out_dir / "latest_prompt.txt").write_text(shared_prompt, encoding="utf-8")
    (out_dir / "chatgpt_5_5_prompt.txt").write_text(chatgpt_prompt, encoding="utf-8")
    (out_dir / "claude_sonnet_4_6_prompt.txt").write_text(claude_prompt, encoding="utf-8")

    write_if_missing(
        out_dir / "chatgpt_5_5_response.md",
        "# ChatGPT 5.5 response\n\nPaste the ChatGPT response here.\n",
    )
    write_if_missing(
        out_dir / "claude_sonnet_4_6_response.md",
        "# Claude Sonnet 4.6 response\n\nPaste the Claude response here.\n",
    )

    print(f"Manual LLM prompt files written to {out_dir.resolve()}")
    print("Next: copy chatgpt_5_5_prompt.txt into ChatGPT and claude_sonnet_4_6_prompt.txt into Claude.")


if __name__ == "__main__":
    main()
