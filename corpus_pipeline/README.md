# Authentic Kazakh legal corpus pipeline

**Delivery status: standalone, tested implementation; original-repository integration is blocked.**

Target repository: https://github.com/yunnamn/kazakh-legal-semantic-similarity

The repository could not be retrieved in the delivery environment. Its files, commit,
models, notebooks, labels and evaluation protocol have **not** been inspected. This is
an additive toolkit, not a purported patch against unseen files. No upstream file was
modified. The original research design must be reconstructed and approved before this
toolkit exports research inputs. See [the audit status](docs/REPOSITORY_AUDIT.md).

No authentic corpus was downloaded in this delivery, no human annotation was performed,
and no model was trained. All automated test content is explicitly `TEST_ONLY`, is not
legal corpus evidence, and cannot be exported as research data.

## What is implemented

The package acquires immutable public-source snapshots, retains per-document and
per-sentence provenance, extracts structured legal text conservatively, produces
leakage-aware deterministic splits, validates them independently, and exports explicit
training views only after source review, original-experiment review and human QA.

The default core is **Kazakh-language Adilet legislation**, not C4 keyword matches,
translations, generated legal prose, generated QA answers, or model paraphrases.
Reusable legal metadata is used for discovery before scraping. Two published text
corpora have opt-in adapters; neither is silently treated as an original official
snapshot. [Source assessment and citations](docs/SOURCE_REVIEW.md).

```
reviewed source + pinned dataset/catalog or explicit official URLs
  -> raw blobs + acquisition receipts + frozen raw lock
  -> processed documents / blocks / sentence occurrences / rejection ledger
  -> law-family + overlap components + protected original evaluation
  -> train / validation / mlm_test / annotation_pool + excluded occurrences
  -> independent validation + actual human QA
  -> read-only research input view + line-aligned provenance
```

The four weights in `configs/pipeline.toml` are a **proposed** 80/10/5/5 policy,
not reconstructed project settings. The experiment gate requires explicit acceptance
of the exact configuration. Hash assignment targets proportions over independent
components, not exact sentence counts. Empty folds or oversized components block release.

## Install and test

Python 3.11 or later is required. The delivered offline tests ran on Python 3.13;
that does not constitute a completed multi-platform CI run. On a connected machine:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m kazlegal_corpus --help
python -m pytest -q
```

For optional Hub acquisition, install `python -m pip install '.[hub]'` and freeze
that environment too. Parquet support is optional and was not exercised in this
delivery; prefer the tested CSV/JSONL paths where the publisher provides them.
See [testing and dependency scope](docs/TESTING.md). No GPU or model dependency is
required for corpus construction. Use a separate virtual environment from the
existing project's training environment.

## Step 1: inspect and freeze the original experiment

Use a complete local checkout with actual Git LFS objects and external evaluation
data. Keep an immutable **reference checkout** separate from any integration branch.
Do not run unknown repository code merely to inspect it.

```bash
export ORIGINAL=/absolute/path/to/original-reference-checkout
mkdir -p work/reviews
kazlegal-corpus audit-repo --repo-root "$ORIGINAL" --output work/original-audit
kazlegal-corpus experiment-review-template \
  --inventory work/original-audit/repository_inventory.json \
  --config configs/pipeline.toml --output work/reviews/experiment.json
```

Read the complete files, notebooks and data/model dependencies, resolve the review
candidates, and fill the generated review form with the actual design and evidence.
It starts with **no approvals**. Declare both text endpoints of all original held-out
similarity pair files, without changing pair IDs, labels, splits or scores.

```bash
kazlegal-corpus config-hash --config configs/pipeline.toml
# Complete the real review before running the following command.
kazlegal-corpus freeze-experiment --repo-root "$ORIGINAL" \
  --inventory work/original-audit/repository_inventory.json \
  --review work/reviews/experiment.json --config configs/pipeline.toml \
  --output work/experiment.lock.json
```

The review format and an explicit methodology checklist are in
[EXPERIMENT_INTEGRATION.md](docs/EXPERIMENT_INTEGRATION.md). Automatic keyword flags
are review leads, not findings that the original repository has a bug.

## Step 2: acquire authentic inputs

Follow [ACQUISITION.md](docs/ACQUISITION.md) for pinned reusable metadata, legal text
reuse, robots-aware Adilet downloads and lawful offline/manual import. Example review
files are deliberately unapproved and cannot be used unchanged.

Minimal official-source route after a real source review:

```bash
# Copy the example, then actually review its license/access/authenticity fields.
cp configs/source-review.example.json work/reviews/adilet.json
# Complete work/reviews/adilet.json before making requests.
kazlegal-corpus acquire-adilet --raw-dir data/raw \
  --manifest configs/adilet-seeds.jsonl --review work/reviews/adilet.json \
  --contact 'YOUR_REAL_RESEARCH_CONTACT' --report work/adilet-acquisition.json
```

The two seeds are only acquisition/structure smoke checks, not a representative
corpus or a claim that either snapshot is currently operative law. Prefer the
metadata-driven manifest for a research acquisition frame. Acquisition stops on
robots restrictions, HTTP failures, challenge pages or unexpected redirects; it
does not rotate proxies, solve CAPTCHAs, impersonate browsers or bypass controls.

When automated access is unavailable, obtain a **permitted official HTML or text
export** and register the unchanged file, actual URL, retrieval time and acquisition
method. This is an explicit human acquisition step, not a secretly automated fallback.

```bash
kazlegal-corpus import-raw --raw-dir data/raw --file /path/to/saved-act.html \
  --sidecar /path/to/completed-actual-acquisition.json \
  --review work/reviews/adilet.json
```

Never paste generated text into an acquisition file. Raw registration plus a source
review records the chain of custody; it cannot cryptographically prove that a human
supplied authentic bytes. Source verification and recorded QA remain essential.

## Step 3: process, protect the evaluation, and split

```bash
kazlegal-corpus freeze-raw --raw-dir data/raw --output work/raw.lock.json
kazlegal-corpus process --raw-dir data/raw --raw-lock work/raw.lock.json \
  --config configs/pipeline.toml --output data/processed/release-001
kazlegal-corpus split --processed data/processed/release-001 \
  --experiment-lock work/experiment.lock.json --repo-root "$ORIGINAL" \
  --output data/derived/release-001
kazlegal-corpus validate --raw-dir data/raw \
  --processed data/processed/release-001 --derived data/derived/release-001 \
  --repo-root "$ORIGINAL" --report work/validation-001.json
kazlegal-corpus statistics --directory data/processed/release-001
kazlegal-corpus statistics --directory data/derived/release-001
```

A diagnostic split without `--experiment-lock` is supported for inspection but is
**not research-exportable**. Never point a training script directly at a diagnostic
processed/split file to bypass the release gate. A successful ordinary `validate`
checks invariants; it is not an approval to train or publish. `--require-ready`
and `export` also enforce experiment, source and human-QA gates.

For corpus updates, pass the previous `split.lock.json` using `split --prior-lock`.
Old families keep their folds; newly discovered edges between incompatible old
folds quarantine the merged component rather than move held-out text into training.
Without that prior lock, reproducibility is guaranteed only within a frozen release,
not across changing input corpora.

## Step 4: human QA and export

```bash
kazlegal-corpus qa-template --processed data/processed/release-001 \
  --derived data/derived/release-001 --output work/qa-001.blank.jsonl
# A real Kazakh-capable reviewer compares full source documents, structure and
# sentence boundaries. Fill a separate work/qa-001.reviewed.jsonl; do not auto-accept.
kazlegal-corpus show-document --processed data/processed/release-001 \
  --document-id ACTUAL_DOCUMENT_SHA256
kazlegal-corpus validate --raw-dir data/raw \
  --processed data/processed/release-001 --derived data/derived/release-001 \
  --repo-root "$ORIGINAL" --qa-review work/qa-001.reviewed.jsonl \
  --require-ready --report work/release-validation-001.json
kazlegal-corpus export --raw-dir data/raw \
  --processed data/processed/release-001 --derived data/derived/release-001 \
  --repo-root "$ORIGINAL" --qa-review work/qa-001.reviewed.jsonl \
  --format text --output data/derived/training-view-001
```

Each `.txt` line has a matching `.provenance.jsonl` line. JSONL export keeps the full
record. Never combine the four roles with a glob. `annotation_pool` is an input to
the **existing** annotation protocol, not a newly generated gold dataset. No labels
or pair scores are generated. `mlm_test` is not a checkpoint-selection set.

Source review distinguishes local research use from redistribution. A successful
local export is **not** a blanket publication license. Preserve attribution and
review each source before publishing raw or derived text.

## Files and documentation

| Location | Purpose |
|---|---|
| `src/kazlegal_corpus/` | Acquisition, parsing, provenance, deduplication, split, audit, validation and export implementation |
| `configs/` | Strict corpus configuration, unapproved review examples and official URL smoke seeds |
| `tests/` | Offline regression tests with nonlegal `TEST_ONLY` fixtures |
| `scripts/validate_corpus.py` | Command-line validation entry script |
| `docs/REPOSITORY_AUDIT.md` | Actual access limitation; no fabricated reconstruction or findings |
| `docs/SOURCE_REVIEW.md` | Reuse decisions, published licenses, primary-source references |
| `docs/CORPUS_DESIGN.md` | Identity, normalization, boundaries, deduplication and leakage semantics |
| `docs/EXPERIMENT_INTEGRATION.md` | Preserve the original scientific question and evaluation |
| `docs/DATA_CARD.md` | Unbuilt-corpus status and fields to fill with measured results |
| `docs/README_APPENDIX.md` | Additive original-README section, to append only after repository inspection |
| `reports/` | Actual delivery and test status, not invented corpus metrics |

See [limitations](docs/LIMITATIONS.md) before interpreting coverage or claiming a
paper-ready release. The software license covers this new toolkit only, not the
uninspected repository or third-party legal data.
