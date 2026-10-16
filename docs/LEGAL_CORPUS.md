# Official-source corpus integration

The supplied `kazakh_legal_corpus_upgrade(2).zip` was imported as `corpus_pipeline/`.
All entries listed in its `FILE_SHA256SUMS.txt` were checked before import. The
imported toolkit, license, checksum list, documentation and historical delivery
reports are retained unchanged. Those reports and the toolkit README describe the
standalone archive's earlier delivery, not the current integration status. This
document describes the connection to the inspected repository.

## What changes and what stays comparable

`config/default.yaml` retains the original keyword-filtered C4 workflow.
`config/adilet.yaml` selects an alternative authentic-source corpus condition.
Model/tokenizer identities, training budget, pooling, masking algorithm, primary
metrics and human similarity scale are retained. The corpus population changes;
results from the two conditions must be reported separately.

`src.corpus.load_split` accepts either the original C4 JSONL paths or a **JSONL
training view** produced by `kazlegal-corpus export`. The alternative loader:

- verifies the manifest and all referenced files, reviewed-export stage, experiment
  and human-QA status, line-aligned provenance and all four role files;
- rejects test fixtures, quarantine records, duplicate IDs and cross-role family,
  component or normalized exact-text overlap;
- preserves original sentence IDs, source metadata, text and split assignments;
- derives legal keywords only for existing annotation sampling, without filtering
  out official-source sentences or creating similarity scores.

This loader checks an export contract. Hashes detect edits, but do not authenticate
source websites, attest to a human review, or replace the upstream validation of
near-text overlap and protected evaluation artifacts. Use only exports from the
reviewed acquisition/build/QA workflow, never manually fabricated manifests.
All four files are checked on each split load; there is no mutable validation cache.

## Installation and tests

From the repository root, using Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
# Appropriate for CPU development; choose a supported CUDA wheel for GPU training.
python -m pip install 'torch>=2.3' --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-dev.txt
python -m pip check
python -m pytest -q tests
python scripts/run_smoke_tests.py
cd corpus_pipeline
python -m pytest -q
python -m kazlegal_corpus --help
```

The integration environment uses the project's pinned Transformers 5.16.0 and
sentence-transformers 6.0.0. The toolkit's standalone `requirements-dev.lock` is
available for a separate corpus-only environment; do not apply its older test/Hub
pins over the model environment. Optional Hub/Parquet extras are not needed by the
offline tests or the JSONL training loader. The repository-level GitHub workflow
runs toolkit and integration checks separately; its hosted execution is not implied
by a local passing run.

## Produce the research input

Follow [`corpus_pipeline/README.md`](../corpus_pipeline/README.md) and its
[acquisition guide](../corpus_pipeline/docs/ACQUISITION.md) for source-specific
commands. Run toolkit commands from `corpus_pipeline/` after activating the venv.
Use the existing isolated checkout; no additional Git worktree is needed for
development. The experiment lock must refer to a complete, stable reference version
with its actual held-out pair files. Do not point an old lock at changing files.

The release sequence is:

1. Audit the actual reference experiment and complete its review with the existing
   semantic evaluation endpoints. Freeze its exact corpus configuration and files.
2. Review the real source/access conditions and acquire or import permitted source
   snapshots with actual retrieval metadata. Freeze the raw store.
3. Process documents and build family/overlap-aware splits protected against the
   frozen semantic evaluation. Validate the resulting artifacts.
4. Complete the required human source/language/boundary QA, then export JSONL to
   `data/legal_corpus/training-view-001` **relative to the repository root**.
   When running from `corpus_pipeline/`, that output is
   `../data/legal_corpus/training-view-001`.

Examples in the archive start unapproved. No approvals or human judgments are
filled automatically by this integration. At inspection, this repository had no
completed human annotation files or generated C4 corpus. The current toolkit
requires a nonempty held-out semantic artifact to freeze a research experiment;
this prerequisite remains unmet until the actual benchmark is available. Diagnostic
builds can be inspected, but cannot be passed off as reviewed research exports.

No source acquisition or official-site request is necessary to run the tests.
Live access to Adilet/Hugging Face and full-corpus scaling remain unverified.

## Use the reviewed export

From the repository root:

```bash
python scripts/evaluate_mlm.py --config config/adilet.yaml --model mbert --variant base
python scripts/train_dapt.py --config config/adilet.yaml --model mbert
python scripts/evaluate_mlm.py --config config/adilet.yaml --model mbert --variant dapt
python scripts/evaluate_similarity.py --config config/adilet.yaml
```

The export path is set in `corpus_input.directory`. It resolves relative to the
repository root, as do existing project paths; an absolute export path also works.
Do not run `build_corpus.py --config config/adilet.yaml`: the script explicitly
rejects the alternative input instead of starting another C4 download.

Alternative checkpoints live in `models/adilet/`, and metrics/figures live under
`results/metrics/adilet/` and `results/figures/adilet/`. Existing C4 checkpoints and
results remain available. Training and MLM evaluation metadata record the imported
corpus build and experiment IDs. Evaluation passes the selected configuration to
the encoders, so it loads the alternative adapted checkpoint rather than silently
using the original checkpoint directory.

`evaluate_similarity.py` still reads the original human benchmark from
`data/annotations/`. To propose **additional**, unscored pairs:

```bash
python scripts/generate_annotation_pairs.py --config config/adilet.yaml
python scripts/annotate_pairs.py --config config/adilet.yaml --annotator reviewer
```

Candidates and new manual annotations go to `data/legal_corpus/`; the optional
`annotation_output_dir` keeps them separate from the original benchmark. These new
annotations are not automatically substituted into semantic evaluation. A separately
named benchmark/configuration is needed to evaluate them. Real evaluation requires
human scores; blank candidates are not a benchmark.

## Compatibility corrections

The pinned Transformers 5.16.0 no longer accepts `overwrite_output_dir` or
`warmup_ratio` in `TrainingArguments`. DAPT now omits the removed overwrite flag
and uses `ceil(max_steps * warmup_ratio)` warmup steps, preserving the prior
ratio-to-step rule. A local tiny-model regression exercises the actual project
training, checkpoint selection/save/reload and held-out MLM evaluation without
external downloads. Output directories are created for the separate corpus
condition. These corrections do not change the masking, metric or human-label
protocol, and do not establish large-model research results.
