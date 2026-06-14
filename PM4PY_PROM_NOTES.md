# M16 SPC / conformance pipeline notes

This folder contains a PM4Py pipeline for reproducing the process-mining part of
the thesis setup:

> Using Large Language Models to Support the Evaluation of Subpopulation Process
> Comparison Techniques in Process Mining

Run:

```bash
python3 run_m16_spc_pm4py.py
```

The script writes results to `results_m16_spc_pm4py/`.

The default mode is now the recommended thesis mode: full preprocessing, model
discovery, token replay, variants, EMSC, and a bounded representative alignment
sample.

For a fast run that skips alignments entirely:

```bash
python3 run_m16_spc_pm4py.py --skip-alignments
```

For exact alignments on one cohort at a time:

```bash
python3 run_m16_spc_pm4py.py --alignment-mode full --align-group age_le
python3 run_m16_spc_pm4py.py --alignment-mode full --align-group age_gt
```

For a smaller representative alignment sample:

```bash
python3 run_m16_spc_pm4py.py --alignment-mode representative --alignment-sample-size 5 --alignment-max-events 30
```

## Attribute choices found in the local XES log

- Diagnosis code keys: `Diagnosis code`, `Diagnosis code:1`, `Diagnosis code:2`, ...
- Patient age keys: `Age`, `Age:1`, `Age:2`, ...
- M16 inclusion rule: a trace is included when any diagnosis-code key equals `M16`.
- Age rule: the first numeric `Age*` attribute in sorted key order is used.
- Subpopulations:
  - `age_le_55`
  - `age_gt_55`

The script also exports `trace_attribute_inventory.csv` and
`preprocessing_summary.json`, so these choices can be reported transparently.

## PM4Py techniques used

- Process discovery: Inductive Miner via `pm4py.discover_petri_net_inductive`.
- Alignment-based conformance: `pm4py.algo.conformance.alignments.petri_net`.
- Enhanced token-based replay proxy: PM4Py token replay with place/trace fitness
  enabled via `pm4py.algo.conformance.tokenreplay`.
- Process variant comparison: frequency-ranked stochastic trace variants.
- EMSC: PM4Py Earth Mover's Distance over the two stochastic languages via
  `pm4py.algo.evaluation.earth_mover_distance`; the script reports both distance
  and `1 - distance` as a stochastic similarity.

The script now exports both:

- own-model conformance: each subgroup log replayed on its own model. This is
  useful for checking within-group model fit.
- cross-model conformance: each subgroup log replayed on the other subgroup's
  model. This is the main Alecu-style SPC conformance comparison.

## Output structure

- `filtered_logs/`: filtered XES logs for each age group.
- `models/`: Inductive Miner Petri nets as PNML, plus PNG visualizations when
  Graphviz rendering is available. If PNG export fails with a missing `dot`
  executable, install the Graphviz system package and rerun.
- `conformance/`: alignment and token replay trace-level tables plus deviation
  summaries.
- `variants/top_variants.csv`: top process variants per group.
- `emsc/emsc_results.json`: stochastic distance/similarity.
- `metrics_summary.csv`: compact table for thesis tables and LLM prompts.
- `cross_model_metrics_summary.csv`: main cross-subpopulation conformance table.
- `own_model_metrics_summary.csv`: supporting within-group model-fit table.

## ProM equivalents

- Import the XES log with **Import Event Log**.
- Filter M16 and age groups with **Filter Log using Simple Heuristics** or the
  event/trace attribute filters.
- Discover models with **Mine Petri net with Inductive Miner**.
- Run alignments with **Replay a Log on Petri Net for Conformance Analysis**.
- Run token replay with **Replay a Log on Petri Net for Performance/Conformance**
  or the token-based replay plugins available in your ProM package set.
- Export tables/visuals from each result view where available. For EMSC, PM4Py is
  usually simpler and more reproducible unless your ProM installation already has
  a stochastic conformance package installed.

## LLM interpretation runner

After generating `results_m16_spc_pm4py/`, prepare prompts for manual use with
the free ChatGPT and Claude web interfaces:

```bash
python3 run_llm_interpretation.py
```

The script does not call any APIs and does not require credits. It writes:

- `llm_interpretation_outputs/chatgpt_5_5_prompt.txt`
- `llm_interpretation_outputs/claude_sonnet_4_6_prompt.txt`
- placeholder response files for saving copied LLM outputs

Copy each prompt into the corresponding web interface and paste the model's
answer into the matching response `.md` file.
