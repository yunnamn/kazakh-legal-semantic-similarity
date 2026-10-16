# Reproducible acquisition, including restricted-access fallback

No command below manufactures legal content. Examples contain paths/configuration,
not substitute statutory text. Complete source reviews with real evidence first.
Use an acquisition workstation with permitted network access, then move the whole
raw store and frozen locks to the offline processing machine.

## A. Reuse a pinned catalog for discovery

Install the optional Hub client in a separate acquisition environment. Inspect the
actual revision and files rather than assuming a current branch or guessed filename:

```bash
python -m pip install '.[hub]'
kazlegal-corpus inspect-hub \
  --repo Arailym-tleubayeva/KazakhLawCorpus-clean > work/catalog-inspection.json
```

Read the pinned card and license. Create `work/reviews/catalog.json` from the review
schema; change `source` to the exact dataset ID, use its actual attribution/license
and document the access and authenticity assessment. Do not copy an Adilet approval
onto a curator's dataset. The source registry is a research assessment, not an approval.

```bash
export REVISION=$(python -c 'import json; print(json.load(open("work/catalog-inspection.json"))["revision"])')
kazlegal-corpus acquire-hub --raw-dir data/raw \
  --repo Arailym-tleubayeva/KazakhLawCorpus-clean --revision "$REVISION" \
  --file data/kazakhlawcorpus_kk_only.csv --format csv \
  --review work/reviews/catalog.json --output work/catalog.upstream.lock.json
```

Include `--file LICENSE` or `--file NOTICE` when present in the inspected source.
`README.md` is always acquired as license/source evidence, never as body text. The
full forty-character commit is mandatory. `--expected-hashes` can supply a previously
published filename-to-SHA256 mapping for a re-download. Retain the acquisition lock
and raw receipts, not merely a mutable Hub cache entry.

Find the content receipt ID in `work/catalog.upstream.lock.json` and use it below:

```bash
export CATALOG_RECEIPT=ACTUAL_CONTENT_RECEIPT_SHA256
kazlegal-corpus discover-catalog --raw-dir data/raw --receipt "$CATALOG_RECEIPT" \
  --limit 10000 --seed YOUR_PREREGISTERED_DISCOVERY_SEED --status all \
  --output work/adilet-manifest.jsonl
```

`10000` is an example operational cap, **not** a recommended research sample size.
The companion report records the input count, eligible unique IDs, selected count,
act forms and rejected metadata. Choose a sampling policy appropriate to the actual
research question, freeze the manifest, and report coverage. `not_marked_repealed`
uses the publisher's status field; it does not certify present legal validity.
The original metadata catalog can be used analogously with its exact dataset ID and
`data/laws_metadata.csv`. Neither catalog adapter emits legislation body text.

## B. Retrieve reviewed official Kazakh documents

```bash
kazlegal-corpus acquire-adilet --raw-dir data/raw \
  --manifest work/adilet-manifest.jsonl --review work/reviews/adilet.json \
  --contact 'ACTUAL_RESEARCH_CONTACT_EMAIL_OR_PROJECT_URL' \
  --report work/acquisition-pass-001.json
```

The client retrieves and archives robots rules, honors their path decisions/crawl
delay, sends an identified research User-Agent, spaces requests by at least two
seconds (three by default), and stops on failures. It allows only same-host HTTPS
redirects and verifies that a redirect has not switched the act/language. It does
not recursively crawl search results or enumerate guessed IDs. No proxy rotation,
credential use, CAPTCHA solving or browser fingerprint evasion is implemented.

The failure report retains completed receipt IDs. Already acquired bytes remain in
the raw store. For an authorized later retry, derive a new manifest by removing
successfully acquired document IDs, preserve both manifests and reports, and honor
any Retry-After/access restrictions. The client intentionally does not hammer an
unavailable source with automatic retries. Failure reasons are not corpus text.

The current Adilet DOM was not accessible for verification during delivery. Known
candidate legal-root selectors are tried conservatively; an unknown or ambiguous
root stops processing. Inspect the actual saved HTML and supply a verified unique
`--selector` during acquisition, or a selector in the manual sidecar. Do not select
`body`, `html` or `*`. A passing selector is not a substitute for human source QA.

## C. Required human step when automatic access is unavailable

Obtain a publisher-provided bulk export or save a legally permitted official **Kazakh
HTML or text export** in an ordinary browser. Respect restrictions; browser access
is not permission to circumvent them. Save original bytes, not a generated summary,
a pasted model answer, a Russian page translated by a model, a search snippet or a
multilingual compare page. Prefer full official HTML over plain text because links,
paragraphs and legal structure are easier to verify.

Copy `configs/manual-adilet.example.json` and fill:

| Field | Required meaning |
|---|---|
| `source_url` | Actual official acquisition URL, not a guessed source attribution |
| `canonical_url`, `source_document_id` | Verified `/kaz/docs/<ID>` identity for the same act |
| `retrieved_at` | Actual browser/export retrieval timestamp including timezone |
| `source_retrieved_at` | Publisher's own retrieval timestamp only when known; otherwise null |
| `title`, `source_version` | Observed title/version, otherwise null; do not infer effective status |
| `acquisition_method` | `manual` |
| `acquisition_note` | Actual method and permission/access basis, including any publisher export conversion |
| `selector`, `encoding` | Verified unique HTML root and actual encoding when nondefault |
| `expected_sha256` | Optional trusted checksum for transferred bytes |

For an official plain-text export, set `adapter` to `adilet_text` and `format` to
`text`. Paragraph reconstruction from hard line wraps is intentionally not guessed;
this representation requires boundary review. PDF parsing/OCR is **not** included:
obtain HTML/text or perform a separately documented, source-verified extraction with
its own retained PDF and conversion evidence before extending an adapter. Do not
rename a PDF to `.txt` or claim OCR output is untouched publisher text.

```bash
kazlegal-corpus import-raw --raw-dir data/raw --file /actual/path/act.html \
  --sidecar /actual/path/act.acquisition.json --review work/reviews/adilet.json
```

Missing source approval, invented placeholder dates, mismatched IDs, non-Kazakh
canonical URLs and arbitrary corpus adapters fail. Store transferred files with
checksums and transport notes. If acquisition is not permitted, record the omission
and use another reviewed source rather than bypass access controls.

## D. Reuse published text only after inspecting its pinned release

`inspect-hub` and `acquire-hub` also support `Arailym-tleubayeva/LegalRAG` and
`kurumikz/kazakhstan_legal_corpus`. Use the actual content filename returned by
inspection, the actual format (`jsonl`, `jsonl.gz`, `json`, `csv` or optional `parquet`),
and a separate completed source review. No content filename or revision is fabricated
for these sources in the toolkit. Request exact files, not all repository artifacts.

For offline/cache acquisition use `--local-files-only`; otherwise download permitted
files through the publisher and use `import-raw` with the matching adapter,
`source_revision` (full commit), `upstream_path`, actual acquisition URL/timestamp
and review. The operator must also retain the pinned README/license as raw evidence;
record their receipt IDs in `license_evidence_receipt_ids` on the content sidecar.

Copy `pipeline.toml` into a separately named reuse profile and explicitly enable
`allow_reused_text`. That changes the configuration hash and requires renewed
experiment approval. Source text remains marked publisher-processed rather than an
official HTML snapshot. `kk` is the only kurumikz language field read as corpus text.
LegalRAG's title-like `doc_id` is never used to identify the act.

Malformed JSONL normally aborts. `process --quarantine-malformed` is an explicit,
recorded alternative: rejected rows/receipts go to `quarantine.jsonl`, never into an
LLM repair prompt. Structural truncation, transport corruption or an invalid format
can still require a corrected publisher download; quarantine is not a repair tool.

## E. Freeze once, rebuild offline

```bash
kazlegal-corpus freeze-raw --raw-dir data/raw --output work/raw.lock.json
```

Without `--receipt`, this includes all current receipts. For a release with only a
selected set of content, repeat `--receipt ACTUAL_ID`. Transitive license, access and
discovery evidence referenced by those receipts is automatically included and checked.
Preserve the entire referenced raw store, lock, profile, manual reviews, identity
links, pipeline version and environment. Re-downloading a mutable official endpoint
later is a **new acquisition**, not reproduction of the same source bytes.
