# Source review and reuse decisions

Assessment date: 2026-09-07. This review used public official pages, dataset cards and
visible schemas. **Publisher counts are not corpus measurements from this toolkit.**
Full dataset bytes were not downloaded/validated in the delivery environment.
No publisher's marketing claims of novelty, completeness or quality are adopted.
Dataset revisions must be resolved and frozen at actual acquisition, not invented here.

## Decisions

| Source | Evidence and reuse assessment | Implemented decision |
|---|---|---|
| Official Adilet Kazakh documents [1,2] | Primary legal publisher; text, legal structure and amendment notes available. Automated access and current DOM could not be verified here. Copyright exclusion and access rules are separate questions. | Default core. Explicit URL manifest, immutable HTML/TXT, careful structure extraction, manual permitted acquisition fallback. |
| `Arailym-tleubayeva/KazakhLawCorpus-clean` [3] | Card declares CC BY 4.0 and 215,889 Kazakh-language act metadata rows with 25 fields. Includes IDs, titles, dates, status and official links, **not statutory bodies**. | Reuse for discovery/sampling/provenance, never treat descriptions as legal corpus text. Pinned `data/kazakhlawcorpus_kk_only.csv` adapter. |
| `Arailym-tleubayeva/KazakhLawCorpus` [4] | Card declares Apache 2.0 and 223,245 metadata records, plus history/reference exports. Body/version/article/chunk releases are described as future work. | Alternate catalog adapter for `data/laws_metadata.csv`; retain history metadata as evidence, not body text. Do not join the entire citation network into one leakage family. |
| `Arailym-tleubayeva/LegalRAG` [5] | Card declares CC BY 4.0; processed Adilet chunks with `source`, `doc_id`, `chunk_id`, `text`. `doc_id` is often a title, not a legal act identifier. Visible examples suggest some lost inline references/glued text; quality cannot be inferred for all rows. | Conditional text reuse. Derive law ID from the official Kazakh URL, preserve original row/chunk locator, never stitch chunks into an invented full document, quarantine uncertain boundary sentences. Not enabled by default. |
| `kurumikz/kazakhstan_legal_corpus` [6] | Card declares ODC-BY 1.0; aligned `kk`/`ru` text from Zan.gov.kz documents. Fields include `id`, `src`, `kk`, `ru`, quality/hash fields, but no validated per-document URL/title or original retrieval date in the inspected schema. Card describes removal of headers, footnotes and other material. Viewer displayed an ArrowInvalid parsing error. | Conditional reuse of `kk` only, streaming validation and explicit malformed-row quarantine. Preserve unknown fields as null. No invented URL template or claim to restore removed notes. Not the core authenticity reference. |
| `olzhasAl/adilet-legal-qa-kz` [7] | Card identifies generated questions/answers built from legal contexts and declares Apache 2.0. A license does not make generated answers authentic legislation. | No corpus adapter. Exclude generated prompts, answers and rationales. Any future context reuse needs independent source verification, not automatic trust in a context field. |
| `Arailym-tleubayeva/KazakhTextDuplicates` and v2 [8,9] | Cards mix source texts with transformations/generated paraphrases; v2 includes preset transformation-based similarity values. These are not original legal text plus human legal-similarity judgments. | Do not use as an authentic-legal replacement or silently substitute for the existing semantic gold protocol. |
| KazParC / SynC [10] | KazParC covers multiple domains including regulatory/government text; the repository separately describes a machine-translated synthetic corpus (SynC). Sentence alignment is not complete legal-document provenance. | Useful background resource, not the default source for this corpus. A verified original Kazakh legal subset could be assessed separately; exclude SynC. No adapter that merges the two. |

## Why metadata-first, official-body second

The largest clearly documented reusable legislation collections above are valuable
**catalogs**, not ready-made statutory training corpora. Their IDs and source links
avoid needless rediscovery of the legal inventory, provide a reproducible acquisition
frame and allow year/status/act-form/region coverage reporting. For the clean catalog,
Kazakh titles may coexist with `/rus/docs/` links. The adapter validates the act ID,
records the original link and requests `/kaz/docs/<ID>`; it does not translate Russian.

The current discovery sampler uses deterministic document-ID hash ranking. It is not
a domain-stratified or nationally representative sample. A full catalog census can
be requested with a sufficiently large limit; any constrained research sample needs
an explicitly recorded sampling frame and coverage analysis. The included two-act
seed manifest is an acquisition smoke check only.

Text reuse remains technically worthwhile when official bulk access is unavailable,
but its quality ceiling is the publisher's extraction. The LegalRAG and kurumikz
adapters retain this distinction in `source_fidelity`. A second, explicitly named
reuse profile can set `allow_reused_text=true` after source-level permissions and
source-comparison QA. Compare it with, rather than silently merge it into, the
high-fidelity official-snapshot core. Preserve attribution and the pinned upstream
card/license evidence in either case.

## Rights and access

Article 8 of Kazakhstan's Law on Copyright and Related Rights excludes specified
official documents and official translations from copyright protection [2]. This is
relevant to authentic statutory text; it is **not** a blanket license for every site
component, third-party annotation, database arrangement or access method. This toolkit
does not decide jurisdiction-specific database rights or supply a legal opinion.

CC BY, Apache and ODC-BY entries above describe the publishers' declarations. They do
not automatically clear all upstream rights. A completed `source_review` must record
the actual reviewer, time, access basis, authenticity assessment, attribution, claimed
license and separate redistribution status. A source can be approved for local
research while public redistribution remains pending or disallowed. Export never
silently relicenses source text as the toolkit's MIT license.

Respect robots rules and applicable access conditions. A missing/unusable robots file
or challenge page makes the automatic client stop. Where a browser export or supplied
bulk file is permitted, retain that unmodified file and describe the acquisition.
Where neither access route is permitted, omit the source and record the coverage loss.
Do not infer permission from technical reachability.

## Technical verification to repeat at acquisition

Resolve a full Hub commit and list its actual filenames with `inspect-hub`. Review
that pinned README and any LICENSE/NOTICE files. Acquire only exact files at that
revision; record SHA-256, upstream path, repository and actual local retrieval time.
Hub download time is not the publisher's original crawl time. Both are represented,
with the latter null when unknown. Hugging Face documents revision-pinned downloads
and its content-addressed cache [11].

Do not rely on a dataset viewer's successful preview as validation, and do not infer
that a viewer error proves an entire source file unusable. Parse the actual stream,
record failures and compare a deterministic sample to source documents. The pipeline
rejects malformed JSONL by default; explicit quarantine records rejected row locators
and checksums rather than fabricating repaired legal text.

## Primary references

[1] Adilet legal information system: https://adilet.zan.kz/eng

[2] Kazakhstan Law on Copyright and Related Rights, Article 8:
https://adilet.zan.kz/eng/docs/Z960000006_
and https://adilet.zan.kz/rus/docs/Z960000006_

[3] Clean legislation metadata card:
https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus-clean

[4] Original metadata/history/reference release:
https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus

[5] LegalRAG card and schema:
https://huggingface.co/datasets/Arailym-tleubayeva/LegalRAG

[6] Registry-aligned legal text card and viewer:
https://huggingface.co/datasets/kurumikz/kazakhstan_legal_corpus

[7] Generated legal QA card:
https://huggingface.co/datasets/olzhasAl/adilet-legal-qa-kz

[8] KazakhTextDuplicates:
https://huggingface.co/datasets/Arailym-tleubayeva/KazakhTextDuplicates

[9] KazakhTextDuplicates v2:
https://huggingface.co/datasets/Arailym-tleubayeva/KazakhTextDuplicatesv2.0/blob/main/README.md

[10] KazParC authors' repository and paper:
https://github.com/IS2AI/KazParC and https://arxiv.org/abs/2403.19399

[11] Hugging Face Hub download documentation:
https://huggingface.co/docs/huggingface_hub/guides/download

[12] Lee et al. (2022), *Deduplicating Training Data Makes Language Models Better*:
https://aclanthology.org/2022.acl-long.577/
This supports checking repeated/overlapping training and evaluation text; it does
not establish that this toolkit's unmeasured thresholds are optimal for Kazakh law.
