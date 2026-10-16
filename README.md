# Domain Adaptation for Kazakh Legal Semantic Similarity

## Overview

This repository implements a reproducible AI/NLP project on domain adaptation for Kazakh legal semantic similarity.

The project studies whether masked-language-model domain-adaptive pretraining (DAPT) on weakly filtered Kazakh legal-domain text improves held-out MLM performance, and whether resulting sentence embeddings align with independent human semantic-similarity judgments.

No large model is trained automatically by this repository. No semantic-similarity labels are generated from model outputs.

## Research Questions

1. Does DAPT on weakly filtered Kazakh legal-domain text improve held-out MLM loss within each model family?
2. Do base or DAPT transformer embeddings correlate with human 0-5 similarity judgments for Kazakh legal sentence pairs?
3. How do multilingual encoders, a Kazakh-oriented encoder, frozen LaBSE, and lexical baselines compare on the manually annotated benchmark?

## Why Kazakh?

Kazakh is lower-resourced than English and many other high-resource languages in NLP. Legal-domain Kazakh text adds another layer of difficulty because the language can be morphologically rich, domain vocabulary is specialized, and pretrained multilingual models may not allocate much capacity to Kazakh legal usage.

## Dataset Construction

The corpus is a weakly filtered Kazakh legal-domain candidate corpus built from Kazakh C4 using legal-language heuristics. The pipeline performs Unicode normalization, sentence splitting, length filtering, legal keyword/root filtering, conservative near-exact deduplication, metadata preservation, deterministic split assignment, and split leakage checks.

The four mutually exclusive partitions are:

- `train`
- `validation`
- `mlm_test`
- `annotation_pool`

The annotation pool is excluded from DAPT so human semantic-similarity examples are not used during adaptation.

## Models

- mBERT: `bert-base-multilingual-cased`
- XLM-R: `xlm-roberta-base`
- Kaz-RoBERTa: `kz-transformers/kaz-roberta-conversational`
- LaBSE: `sentence-transformers/LaBSE`

The code distinguishes explicit `base` and `dapt` checkpoint variants. If a DAPT checkpoint is requested and does not exist, the loader raises an error instead of silently falling back to the base checkpoint.

## Domain-Adaptive Pretraining

DAPT uses MLM training on the `train` split only. Checkpoint selection uses the `validation` split only. Final MLM evaluation uses `mlm_test` only. Training uses dynamic masking; held-out evaluation uses deterministic fixed masks.

## Held-Out MLM Evaluation

Base and DAPT variants from the same model family are evaluated with identical deterministic masks. This makes within-family base-vs-DAPT MLM loss comparisons meaningful. MLM loss should not be overinterpreted across different tokenizer/model families.

## Semantic Similarity Benchmark

Candidate sentence pairs are sampled only from `annotation_pool`. Lexical heuristics may select pairs with high overlap, moderate overlap, shared legal keywords, or random pairing, but these are sampling strategies only.

The generated `annotation_candidates.csv` keeps `similarity_score` blank. Human annotators score each pair on a 0-5 semantic-similarity scale.

Semantic-similarity evaluation is pending manual annotation.

## Lexical Baselines

The repository includes:

- TF-IDF cosine similarity
- token Jaccard similarity

These baselines help test whether transformer embeddings add value beyond surface lexical overlap.

## Evaluation Metrics

Semantic similarity is evaluated with:

- Spearman correlation
- Pearson correlation
- bootstrap confidence intervals

The repository intentionally excludes pseudo-label classification and sentence-level NGD evaluation.

## Repository Structure

```text
config/default.yaml
data/
models/
notebooks/analysis.ipynb
results/
scripts/
src/
tests/
README.md
PROJECT_EXPLANATION.md
requirements.txt
```

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On Linux/macOS, activate with `source .venv/bin/activate`.

## Reproduction

Build the corpus and deterministic splits:

```bash
python scripts/build_corpus.py
```

Evaluate a base MLM checkpoint:

```bash
python scripts/evaluate_mlm.py --model mbert --variant base
```

Run DAPT for one model:

```bash
python scripts/train_dapt.py --model mbert
```

Generate blank annotation candidates:

```bash
python scripts/generate_annotation_pairs.py
```

Annotate manually:

```bash
python scripts/annotate_pairs.py --annotator annotator1
```

Evaluate semantic similarity after annotation:

```bash
python scripts/evaluate_similarity.py
```

## Official-source corpus alternative

The additive [`corpus_pipeline/`](corpus_pipeline/README.md) toolkit from the supplied
archive acquires and validates authentic-source Kazakh legal text, preserves provenance,
and protects law-family and text-overlap boundaries. It contains code and test fixtures,
not a downloaded legal corpus or completed source reviews.

Install the integration with `python -m pip install -r requirements-dev.txt`. After
building a reviewed JSONL research export, use `--config config/adilet.yaml` with
the existing training, MLM evaluation, and annotation scripts. The C4 default remains
available. The new loader verifies the export and consumes its existing four roles
without applying the C4 keyword filter or resplitting sentences.

See [integration and reproducible commands](docs/LEGAL_CORPUS.md) for acquisition,
review requirements, separate outputs, and tests. No real corpus release, human review,
large-model training or semantic benchmark result is claimed by this integration.

## Results

Results are reported only for completed experiments. Semantic-similarity evaluation remains pending manual annotation unless completed human annotation files are present.

## Limitations

The legal-domain corpus is heuristic and noisy, not professionally annotated legal data. Kazakh NLP resources are comparatively limited. The human benchmark may be small, and a single annotator should be described as a pilot benchmark rather than a gold-standard dataset. Compute constraints limit DAPT scale. Generic MLM encoders are not purpose-trained sentence encoders, so mean-pooled sentence embeddings have known limitations. Cross-family MLM loss should not be overinterpreted because tokenizers and pretraining histories differ.

## Future Work

Future extensions could add multi-annotator agreement analysis, larger manually annotated STS data, stronger sentence-embedding fine-tuning after human labels exist, more legal-domain diagnostics, and compute-scaled DAPT runs.
