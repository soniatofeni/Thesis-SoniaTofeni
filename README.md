# LLM-Supported Interpretation of SPC Outputs

This repository contains the reproducible process-mining and LLM-prompting
pipeline for the thesis:

**Using Large Language Models to Support the Interpretation of Subpopulation
Process Comparison Techniques in Process Mining**

The case study compares two subpopulations from diagnosis group `M16` in the
BPI Challenge 2011 hospital event log:

- `age_le_55`: patients aged 55 or younger
- `age_gt_55`: patients older than 55

## Scope

The repository does not propose a new SPC technique. It generates structured
outputs from existing process-mining approaches and prepares identical prompts
for evaluating LLM-based interpretation.

The implemented analysis includes:

1. Cross-model alignment-based conformance checking
2. Cross-model token-based replay
3. Process variant comparison
4. EMSC-style stochastic language comparison using Earth Mover's Distance

Cross-model conformance is used because each subpopulation log is replayed on
the model discovered from the other subpopulation, directly testing behavioral
compatibility.

## Repository Structure

```text
.
├── run_m16_spc_pm4py.py          # Main process-mining pipeline
├── make_readable_model_visuals.py # Thesis-readable DFG generation
├── run_llm_interpretation.py      # Manual ChatGPT/Claude prompt generation
├── requirements.txt
├── PM4PY_PROM_NOTES.md
├── results_m16_spc_pm4py/
│   ├── conformance/               # Aggregate cross-model summaries
│   ├── emsc/                      # EMD and stochastic similarity
│   ├── models/                    # Reproducible PNML models
│   ├── readable_visuals/          # Top-15 DFG figures
│   ├── variants/                  # Top process variants
│   └── preprocessing_summary.json
└── llm_interpretation_outputs/
    ├── chatgpt_5_5_prompt.txt
    ├── claude_sonnet_4_6_prompt.txt
    ├── chatgpt_5_5_response.md
    └── claude_sonnet_4_6_response.md
```

## Data

The BPI Challenge 2011 event log is not redistributed in this repository.
Place `Hospital_log.xes` in the repository root before running the pipeline.
The source log can be obtained from the official BPI Challenge data provider,
subject to its access and usage conditions.

## Installation

Python 3.11-3.13 may be used. Create an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Graphviz must also be installed as a system dependency. On macOS:

```bash
brew install graphviz
```

## Run the Process-Mining Analysis

```bash
source .venv/bin/activate
python run_m16_spc_pm4py.py \
  --alignment-mode representative \
  --alignment-sample-size 5 \
  --alignment-max-events 30 \
  --alignment-max-time-trace 5 \
  --alignment-max-time-total 60
```

The pipeline:

- filters traces containing diagnosis code `M16`;
- assigns age using the first numeric `Age*` trace attribute in sorted order;
- splits cases at age 55;
- retains traces containing 6-100 events;
- discovers one Inductive Miner model per subpopulation;
- performs cross-model token replay on the full filtered logs;
- performs bounded, variant-informed alignments on five traces per direction;
- exports variants and EMSC-style stochastic comparison results.

## Generate Readable Figures

```bash
python make_readable_model_visuals.py
```

The top-15 directly-follows graphs are intended as readable thesis figures.
They are descriptive summaries, not conformance-checking results. Full PNML
models are retained for reproducibility.

## Generate LLM Prompts

```bash
python run_llm_interpretation.py
```

This creates equivalent prompt files for ChatGPT and Claude. The script does
not call paid APIs. Responses are manually saved in the corresponding Markdown
files for evaluation against an expert interpretation.

## Main Results

- Final filtered logs: 48 traces (`age_le_55`) and 54 traces (`age_gt_55`)
- Cross-model token fitness:
  - `age_gt_55` log on `age_le_55` model: `0.964900`
  - `age_le_55` log on `age_gt_55` model: `0.984344`
- Representative alignment fitness: `1.0` in both directions, based on five
  bounded sample traces per direction
- Unique variants: 48 and 53
- Earth Mover's Distance: `0.565815`
- Reported stochastic similarity (`1 - EMD`): `0.434185`

In this PM4Py implementation, the stochastic languages are probability
distributions and normalized Levenshtein distance is used as the ground
distance. The resulting EMD is therefore bounded between 0 and 1.

## Reproducibility Notes

- The 6-100 event-length filter means conclusions apply only to the filtered
  M16 subset.
- Ninety-eight M16 traces contained inconsistent repeated age attributes.
- Alignment results are sample-based and must not be interpreted as full-log
  alignment results.
- The EMSC-style calculation is a PM4Py EMD comparison over stochastic
  languages, not an execution of the official ProM EMSC plugin.
- LLM web-interface settings such as temperature and hidden system prompts
  could not be controlled.

