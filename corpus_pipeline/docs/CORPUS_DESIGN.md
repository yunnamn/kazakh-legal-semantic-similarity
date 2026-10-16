# Corpus design and invariants

## Scope and data layers

This is a legal-text corpus intervention, not a new semantic-similarity benchmark.
The proposed core covers public statutory Kazakh prose. It is not a general legal
advice dataset, court-judgment collection, complete regulatory database or statement
of currently effective law. No text generation, translation, paraphrase, synthetic
positive/negative pair generation, model-based text repair or automatic gold labels
are part of the pipeline.

`raw/` contains immutable source bytes addressed by SHA-256 and immutable acquisition
receipts. A receipt identifies the exact act or pinned curator file, real acquisition
URL/time, content hash, adapter, acquisition method, source review and supporting
evidence. Retaining both original time and import time avoids equating a local copy
with a source crawl. Licenses, robots and discovery metadata have non-content roles.

`processed/` contains deterministic document units, structural blocks and sentence
**occurrences**, a malformed-source ledger, normalization/extraction metadata,
language reviews, identity links, config/raw locks and measured statistics. This
layer retains excluded text; it is not an invitation to train on all its sentences.

`derived/` contains fold memberships, overlap edges, split locks, four role-specific
files and an excluded-occurrence file. A training view is a further immutable export,
not a new copy of the gold similarity benchmark. Existing evaluation files are read
for protection only, never overwritten.

## Identity and provenance

The law family is `adilet:<act ID>` or `zan:<registry ID>`, not a title hash. All known
versions and chunks of the same act share a family. A reviewed identity-link JSONL
can map cross-registry IDs using `source_family_id`, `canonical_family_id`, actual
`reviewer`, `reviewed_at` and `evidence`; matching titles alone are insufficient.
Cycles/conflicts fail. The original source IDs remain in provenance.

Document IDs hash family, language, upstream unit identity, source version when known
and normalized structural layout. Duplicate **harvests** of that same unit merge
with all acquisition receipts, source descriptions and block locators retained.
The same wording in two provisions or two acts remains separate occurrence records.
A changed number, negation, date, punctuation or structural position is not rewritten
into a canonical legal meaning. Document identity includes unit kind so a publisher
chunk is not misrepresented as an official full act.

Each sentence retains its source document ID and URL where known, title, language,
retrieval date, version when observed, article/section path, block and sentence IDs,
normalized-character offsets, raw hash and complete acquisition provenance. Unknown
fields stay null. Missing per-document URLs in a reused source are a measurable
limitation, not an excuse to fabricate a link. Upstream row/chunk locators locate
published text; normalized offsets are explicitly **not** raw HTML byte offsets.

A compact field map:

| Record | Important fields |
|---|---|
| Receipt | `receipt_id`, `sha256`, `source_url`, `retrieved_at`, `imported_at`, `source_revision`, `upstream_path`, `source_review` |
| Document | `document_id`, `family_id`, `source_family_ids`, `unit_kind`, `upstream_unit_id`, `text`, `text_sha256`, `source_fidelity`, `provenance` |
| Block | `block_id`, `document_id`, `kind`, `article`, `article_occurrence`, `section_path`, `document_start/end`, `source_locators`, normalization changes |
| Sentence | `sentence_id`, `text`, block/document offsets, language evidence, inherited source fields, eligibility and quarantine reasons |
| Membership | sentence/document/family/component IDs, explicit role and disposition reasons |
| Experiment lock | original commit and file hashes, reviewed reconstruction, protected pair specifications, accepted config hash |

## Unicode, whitespace and boilerplate

Normalization is NFC, not compatibility folding. Within each structural block it
collapses Unicode whitespace and removes BOM/zero-width-space layout characters,
recording changes. It preserves case, Kazakh letters, digits, punctuation and the
actual wording. It never strips stopwords or legal-keyword-filters this corpus.
Zero-width removal and whitespace changes are inspectable against immutable raw
bytes; they need QA in any publisher with unusual typography.

HTML extraction requires a unique legal-text container. It removes only scripts,
styles, noscript and navigation elements **inside that root**. It does not globally
strip every header/footer, anchor, reference or repeated phrase. Legal signatures,
amendment notes, footnotes and repeal notices can carry meaning and remain. Inline
link text survives. A multilingual compare view is not an accepted act endpoint.
An inaccessible/unknown DOM is rejected instead of ingesting a login/challenge page.

Tables and structural headings remain in processed data with structural labels but
are excluded from the default sentence-prose MLM view. Table cells are not silently
flattened into sentences claimed to be faithful legal prose. This is a substantive
scope limitation to report, especially for numeric/regulatory schedules. Amendment
notes are included by default; a reviewed explicit policy can exclude them from
training while retaining them in processed provenance.

## Segmentation and language

The deterministic rule segmenter preserves dates, decimals, list numbering, common
Kazakh abbreviations and initials. It returns exact spans into normalized blocks.
Article labels, section hierarchy and occurrence counters help distinguish repeated
article numbering, including annex resets. It is not asserted to parse every legal
document layout or recover a complete legal hierarchy. Unknown structure stays
unknown rather than being invented.

Language checks combine declared official locale, Cyrillic proportion and
Kazakh-specific letters. This is a transparent heuristic, not a trained language-ID
model or proof of Kazakh authenticity. Uncertain full documents and mixed/unsupported
sentences are quarantined pending explicit review. Short sentences inherit acceptance
only from accepted documents. Reviewer overrides identify exact document/sentence
IDs, carry decisions/evidence/time and reject stale IDs. A human-rejected document
cannot be silently rehabilitated by an unrelated automatic signal.

Upstream chunk boundaries may truncate sentences. LegalRAG fragments are never
concatenated into an imagined whole act; their first/last prose sentences are
quarantined by default. Clean source re-acquisition is preferable to text completion.

## Deduplication versus leakage grouping

These are intentionally different operations. Exact duplicate harvests can be merged
with provenance. Near-matching **legal provisions are not deleted or labeled
semantically equivalent**. They are linked for split protection only.

The overlap-only fingerprint applies NFC/whitespace normalization, casefolding and
word extraction. This conservative guard may group text differing in punctuation;
the training text itself is unchanged. Numerals and negation words remain tokens.

For retained occurrences, exact shared text links law families. Very short shared
text (fewer than eight regex words) and ubiquitous exact text (more than 100 families)
are excluded from all derived roles instead of turning the corpus into one boilerplate
component. They remain in processed data and the exclusion ledger. This can remove
substantive recurrent formulas from the core view and must be quantified.

Near overlap uses exact set Jaccard on word five-grams with threshold 0.90 for
sentences of at least 12 regex words. A disk-backed prefix-filter join generates
candidates; each candidate is verified with the full set. It is not a probabilistic
MinHash claim. Thresholds are proposed engineering defaults, not Kazakh-law-calibrated
optima. Candidate limits cause an explicit failure rather than silently skip checks.

Every contiguous 32-word window at stride one is also checked across consecutive
eligible sentences, including adjacent paragraphs. Runs break at document boundaries
or excluded structure/sentences. This catches long substrings missed by whole-sentence
Jaccard and protects against chunk-size differences. It does not catch all shorter
containments, paraphrases, translations or semantically equivalent provisions.

An undirected union-find groups source families, explicit identity links, exact/near
matches and contiguous overlaps. Transitive components can grow; the release gate
blocks a component larger than the configured fraction of retained families. It never
breaks leakage edges just to obtain attractive split sizes. Inspect the edge ledger
and sampling policy rather than weakening safeguards after seeing evaluation scores.

## Deterministic split semantics

A SHA-256-based integer bucket maps each component to ordered named roles using an
explicit seed and integer weights summing to 10,000. No process-randomized `hash()` or
implicit global RNG affects assignment. All versions of one law are colocated.
The proposed weights are 8,000/1,000/500/500 for train/validation/mlm_test/annotation_pool.
They require review against the real original design. Small corpora can have empty
folds; this correctly blocks release rather than manufacturing data.

Both original semantic pair endpoints, their sentence spans and declared source-law
IDs are indexed as protected external evaluation units. A matching component is
quarantined from **all four** corpus roles, not assigned to MLM test and claimed
uncontaminated. Original labels are not read for matching and pair artifacts are
checksummed in full. Even excluded common text may reveal an evaluation law identity.

For later releases, a prior split lock preserves old family assignments. A newly
connected train/test conflict quarantines the entire component. There is no promise
of split stability after arbitrary source updates without the prior lock. Immutable
snapshots, pinned runtime/Unicode/parser versions and unchanged pipeline code give
byte-identical builds in the tested fixed environment. A fresh live crawl changes
retrieval metadata/content and is a different release.

## Independent validation and quality review

Validation verifies raw checksums and receipt chains, build manifests, source reviews,
identities, document/block/sentence reconstruction, offsets, exact occurrence
accounting, component/family roles and reported counts/blockers. It independently
rebuilds overlap indexes across the emitted splits and original evaluation guard.
Hashes detect modification, not truth: a manually supplied authenticity claim still
needs review against the source.

A deterministic sample per source is selected with blank human decisions. The
reviewer examines full source and processed documents, sentence boundaries, language,
notes, links and omissions. The minimum ten-document default is a smoke-quality
gate, **not** a statistically justified estimate of error rate. A paper should
predeclare a larger, stratified source/year/act-type review as appropriate and report
sample size, disagreement and error categories. Rejections require source/policy
correction and a new build, not selectively dropping inconvenient QA examples.

Statistics count raw receipts, harvested/unique units, merged harvests, source and
fidelity coverage, missing fields, language decisions, structure kinds, rejected
records, sentence lengths, word counts, exclusion reasons, split sizes and component
sizes. Metadata coverage is publisher-supplied and counts units (including chunks),
not necessarily unique acts. Regex word counts are **not** tokenizer token budgets.
Training-token counts and actual model/training results require the original pipeline.
