# Dataset card: unbuilt release template

## Current status

This delivery contains software, tests, configuration and source assessments, not a
released Kazakh legal corpus. Authentic acquired documents: **0**. Research corpus
sentences: **0**. Actual human source reviews/annotations completed here: **0**.
Original experimental design reconstructed: **no; repository access blocked**.
MLM or semantic-similarity performance measured: **none**.

The upstream publisher counts in SOURCE_REVIEW.md are not this corpus's size. Test
fixture counts are not data collection results. Do not cite either as measurements
of an authentic corpus built by this toolkit.

## Intended release description

Name and immutable release ID: pending a real acquisition/build.
Language: authentic Kazakh from verified sources, with per-unit language evidence.
Domain: public statutory/legal prose; not necessarily currently effective law.
Primary source: permitted official Adilet Kazakh snapshots.
Optional additional sources: explicitly approved pinned reusable corpora, with
publisher-processed fidelity disclosed and evaluated separately where appropriate.
Purpose: improve the corpus component of the existing legal semantic-similarity
experiment without replacing its research question or gold evaluation.

## Fields to fill from real artifacts

Record raw acquisition frame/date range, official acts and versions, registry IDs,
source revisions and SHA-256 locks, metadata coverage, unique law families, document
units, sentence occurrences, actual tokenizer tokens, missing-provenance percentages,
source/language/structure exclusions, duplicate harvest counts, overlap relation
counts, component-size distribution and the four actual split sizes. Copy measured
values from the immutable processed/derived statistics, then add training-token and
human-QA measurements from the reviewed original training/annotation workflow.

Record source permissions, redistribution status, actual reviewer identity/date,
quality sample design, error/disagreement rates, unresolved extraction issues and
all interventions. Include the experiment lock, code/environment manifest, original
evaluation artifact hashes and prior split-lock history. A source URL alone is not
a recoverable snapshot if a mutable portal changes later.

## Limitations and responsible use

No representation of all Kazakhstan law or all legal registers is guaranteed. Metadata
sampling, source availability, language heuristics, tables excluded from the prose view,
chunk-boundary quarantine and repeated-formula exclusions can bias coverage. Repealed
or amended texts can be linguistically useful but are not current legal advice.
Article structure and sentence boundaries are rule-based and require native review.

Official public text can still contain names and other personal information. This
pipeline does not claim complete PII detection or anonymization and does not expand
into personal court/case records. Review privacy and redistribution scope before any
publication. Do not use the corpus to assert legal obligations without checking the
current authoritative act and relevant effective dates.

## Licensing

The new toolkit's software license is separate from official-document treatment,
curator licenses and source access rules. Retain source-specific attribution and
rights metadata. Local research-export validation is not public-release authorization.
Do not publish test fixtures as authentic law or generated labels as human gold.
