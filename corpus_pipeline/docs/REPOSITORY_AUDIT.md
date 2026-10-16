# Repository audit status and methodological review boundary

## What was and was not inspected

Target: https://github.com/yunnamn/kazakh-legal-semantic-similarity
Assessment date: 2026-09-07.

The GitHub repository page and raw README could not be fetched (cache-miss/access
errors); the GitHub API route was not usable. A container clone/download route also
failed, and no authenticated GitHub connection became available. These failures do
**not** establish that the repository is private, deleted or malformed. No source
archive, tree or commit was obtained. Repository-specific audit completion is **false**.

The only repository design information available is the user's description:
Kazakh C4 filtered with legal keywords, a semantic-similarity evaluation that must
be preserved, and four required corpus roles. These are user-reported facts, not
independently verified code findings.

| Experimental element | Reconstructed status |
|---|---|
| Research question, hypotheses and intended estimand | Unknown; must be read from repository/paper |
| Models, checkpoints, tokenizer revisions, pooling | Unknown |
| C4 version, keyword inventory, sampling seed, corpus sizes | Unknown |
| MLM sequence packing, mask policy, token budget, early stopping | Unknown |
| Similarity pair source, pair IDs, labels, annotators and agreement | Unknown |
| Similarity metrics, baselines, confidence intervals, repeated seeds | Unknown |
| Original train/validation/test/annotation roles and split ratios | Unknown |
| Existing implementations, result files and notebook execution order | Unknown |

No original code bug is claimed confirmed, and no original result is claimed fixed.
The delivered toolkit was implemented separately rather than changing unseen files.
A new original-README replacement would erase unknown content, so the delivery
contains its own README and a separate append-only integration section.

## Required sequence once the complete repository is accessible

Create a fixed reference checkout, retrieve all LFS/external data needed to interpret
the experiment, then run `audit-repo`. It reads every tracked working-tree file,
hashes binaries, extracts notebook code without executing it, records Git status,
and flags review candidates. Review notebooks including outputs and execution order,
all configuration, data preparation and evaluation scripts, reported tables, licenses
and relevant external artifacts. An automatic file scan is not a scientific audit.

Generate `experiment-review-template`, complete the reconstruction and per-file
reviews with evidence, document every confirmed issue, and only then freeze the
experiment. Each relevant file needs `reviewed`, or a specific `out_of_scope_with_reason`
justification; missing/LFS-pointer/submodule/symlink files must first be resolved.
External datasets and model revisions need a separate evidence record; hashing the
local working tree does not inspect dependencies or Git history.

## Risks that require verification, not assertions about unseen code

| Risk | Why it matters | Implemented protection or required audit action |
|---|---|---|
| Keyword-selected C4 is called authentic legislation | Domain keywords do not establish official source identity | Core adapters accept official snapshots only; preserve the old C4 condition as a historical baseline |
| Sentence-random splits | Versions or adjacent provisions can leak across folds | Group source law families and verified overlap components before assigning folds |
| Gold pair endpoints enter MLM training | Labels are not needed for training contamination | Freeze original pairs and guard both endpoints and known source law IDs |
| Annotation pool is used as unlabeled MLM data | Later similarity evaluation is no longer independent | Separate annotation pool, prohibit it as adaptation input, retain the original annotation protocol |
| Near deduplication erases legally important differences | Negation, numerals or dates can change legal meaning | Near matches are grouped, not substituted/deleted or labeled equivalent |
| Checkpoint choice uses MLM test or semantic test results | Selection bias and optimistic final scores | Preserve/audit selection logic; separate validation from final diagnostic roles |
| Dynamic MLM evaluation masks vary by model/run | Scores can reflect different masked positions | Optional deterministic mask helper; integrate only after reviewing original implementation |
| Batch means are averaged instead of masked-token losses | Unequal mask counts distort the diagnostic | Optional summed-NLL/token-count aggregator; not automatically wired into original training |
| Pooling includes padding or truncation differs by condition | Apparent corpus benefit may be an embedding artifact | Audit attention masks, pooling, sequence limits and tokenizer versions; no speculative patch |
| Unequal adaptation token budgets or additional tuning | Confounds authentic-source quality with compute/selection | Pre-register matched-token/compute comparison while retaining original reported condition |
| Pair endpoints/documents recur across semantic train/test | Pair-row independence is misleading | Audit pair/source graph; report original protocol and any separately named corrected sensitivity analysis |
| Synthetic labels/text are mistaken for human gold/source law | Invalid provenance and evaluation claims | No generated-text adapter; do not replace the original gold set with generated QA/duplicate benchmarks |
| Unpinned datasets, models, code or random seeds | Experiment cannot be reproduced | Pin source commits/bytes, corpus policy, code, original artifacts, and model/training environment |
| Single seed or inappropriate uncertainty estimates | Reported improvements may be unstable | Retain original metric; add predeclared repeated runs and source-aware uncertainty only as documented analyses |

A confirmed methodological defect can warrant a correction, but its effect on the
research question, evaluation population and comparability must be stated explicitly.
Do not silently overwrite an old result table or present a redesigned experiment as
a reproduction of the original one.

## Delivery boundary

Implemented protections were tested on marked fixtures. The gate prevents research
export until the real reconstruction is supplied. There is no invented inventory,
commit SHA, model list, annotation score, citation to nonexistent repository lines,
training result or assertion that the original evaluation was successfully preserved
through a completed end-to-end rerun.
