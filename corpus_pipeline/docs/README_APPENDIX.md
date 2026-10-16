<!-- Append this section to the ORIGINAL README only after inspecting that repository.
Do not replace the original README or imply that integration is already complete. -->

## Authentic-source legal corpus (corpus intervention)

The additive `corpus_pipeline/` package provides an authentic-source alternative to
keyword-filtered web text. Its primary inputs are permitted official Adilet Kazakh
snapshots, with pinned reusable metadata for discovery and opt-in, separately reviewed
published legal-text adapters. It does not generate legal prose or similarity labels.

Raw bytes/receipts, normalized documents/sentences, and derived experimental inputs
are separate. Every occurrence retains available source URL/ID/title/article/section,
language, actual retrieval date, raw checksum and acquisition provenance. Duplicate
harvests retain all source evidence; different provisions remain distinct records.

Law-family/version and text-overlap components are split deterministically into
`train`, `validation`, `mlm_test` and `annotation_pool`. Existing held-out semantic
pair endpoints and known source laws are protected from all corpus roles. This does
not replace the original similarity protocol, gold labels or reported baseline.

Before adapting the original loader, follow `corpus_pipeline/README.md`: audit the
complete reference experiment, approve the exact corpus policy, acquire permitted
source bytes, freeze provenance, build/validate splits, complete actual human QA and
export a role-specific training view. Never train directly on diagnostic intermediate
files or concatenate annotation/test files into MLM training.

Acquisition restrictions, manual import, dataset reuse assessment, proposed-vs-original
settings and all remaining limitations are documented under `corpus_pipeline/docs/`.
The software delivery alone is not a measured corpus release or a completed rerun.
