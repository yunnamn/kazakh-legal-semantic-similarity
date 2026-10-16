# Connectivity restored; manual official-text intake needed

**No authentic legislation has yet been processed.** This continuation recovered
metadata discovery and investigated official download methods. It did not produce
a validated legal corpus or an authentic-data end-to-end build.

## Measured progress

| Check | Current result |
|---|---|
| Adilet robots policy | HTTP 200, 6,568 bytes |
| Hub-resolved catalog CDN | HTTP 200 |
| Pinned catalog CSV | Downloaded, 336,764,115 bytes; SHA-256 verified |
| Metadata rows inspected | 215,889 |
| Eligible distinct act IDs | 215,888 |
| Rejected catalog rows | 1: `V97L000010_ ` has trailing whitespace |
| Planned pilot / first manual batch | 75 / 10 distinct catalog IDs |
| Authentic legal documents acquired / processed / retained | **0 / 0 / 0** |
| Actual corpus language, deduplication and leakage statistics | Unmeasured |
| Authentic train/validation/MLM-test/annotation-pool files | Not produced |
| Current automated tests | 122 passed, 1 training test deselected |

The completed catalog acquisition is pinned to
`Arailym-tleubayeva/KazakhLawCorpus-clean` revision
`588f13ed7af351c485955698de72de18fe9acce8`. Its CSV hash is
`1099c257c6f9d82b56318b1f887b6d6051fd8518816bac458ed48f068a8d0d1b`.
Both raw receipts were verified with the existing `RawStore.load` checks.
The prior metadata-only CC BY 4.0 review applies; statutory bodies were not inferred
from catalog titles or descriptions. See `catalog.upstream.lock.json`.

The existing hash-ranked sampler used the previously planned seed
`adilet-pilot-2026-10-16-v1`, limit 75 and status `all`. No model results or observed
split sizes influenced selection. `planned-75.jsonl` retains compact discovery
metadata and explicitly marks official text as unverified. The first ten, in ID
order, are listed in [`docs/MANUAL_FIRST_10.md`](../../docs/MANUAL_FIRST_10.md).
They are an intake subset, not a representative-law or currently-effective-law claim.

## Why HTTP 200 did not deliver legislation

The normal client retrieved `/eng`, the copyright-law URL
`/eng/docs/Z960000006_`, and the first sampled act
`/kaz/docs/G20E0000668`. These returned the same JavaScript application shell
(1,573 bytes), with an empty `#root` and a notice that document text requires
JavaScript. None contained statutory body text. The existing parser rejected the
first sampled response:

> Expected one verified legal-text container, found 0; inspect the saved HTML and supply selector

This is a correctly refused input, not a successful extraction or an application
bug requiring a rewrite. No empty shell was imported as legislation, no synthetic
text was substituted, and no corpus statistics or zero-leakage result was invented.

## Access and redistribution conditions actually inspected

The current robots file was retrieved and retained as `robots.txt`. It permits
ordinary document pages for general clients, disallows `/api/` and internal exports,
and separately blocks named AI-training crawlers. The explanatory comments make a
purpose distinction between model-training collection and user-requested access.
This does not establish that all research use is prohibited, nor does a custom
crawler name constitute permission for training-corpus extraction.

The public frontend links to the official user agreement at
`https://adilet.zan.kz/legal/polzovatelskoe-soglashenie.docx`. That exact file was
retrieved over verified HTTPS and read using standard ZIP/XML tools:

- §1.7 states that official normative legal-act texts are outside copyright under
  Article 8, while software, database structure and interface rights are retained.
- §4.3.2 permits personal, informational, scientific-research and professional use,
  requiring Adilet attribution when quoting or disseminating materials.
- §4.4.4 prohibits destabilizing actions, excessive-load automated collection and
  unauthorized copying/use of protected software, interface and specialized databases.
- §4.2.3 supplies the official support contact `support@zqai.kz`.

These are observed publisher terms, not an independent legal determination about
every intended use or redistribution of full saved pages. Full-page/corpus
redistribution remains unapproved pending actual content and source review.
No raw legal text or full terms/frontend source was committed.

Only publicly referenced JavaScript assets were inspected to identify normal
download options. The frontend uses an API with `/api` as its base. Those
robots-disallowed endpoints were **not requested**, and no authenticated session,
crawler impersonation or access-limit workaround was used.

The visible Download/Жүктеу implementation offers **PDF export**, requires sign-in,
and accounts for export limits. No native TXT, HTML or DOCX export was observed in
that component. UI-code inspection does not establish that a particular account
can export every act; no actual official PDF was downloaded.

The catalog also supplies EKB links for 64 of the 75 selected records, pointing to
`law.gov.kz`; the first ten links are Russian client routes. They are retained as
catalog metadata, not verified Kazakh text sources. No Russian text was translated
or mislabeled Kazakh. That site's content/terms were not independently retrieved,
and its bodies cannot be passed through the Adilet adapter as if downloaded there.

## Manual route and remaining validation

The existing pipeline accepts `adilet_html` or `adilet_text` manual imports with
real acquisition sidecars and a completed source review. Its HTML parser accepts
an explicit selector, so no new ingestion pipeline is needed for a saved rendered
Adilet page. The current frontend's candidate text selector is
`[data-tour="doc-body-content"]`; it must be checked against each real saved file,
not assumed correct from the frontend bundle alone.

[`docs/MANUAL_FIRST_10.md`](../../docs/MANUAL_FIRST_10.md) gives ten exact URLs,
filenames, required formats, acquisition facts and existing import commands.
The directory `data/legal_corpus/manual-inbox/` was created locally and remains
ignored by Git. A saved HTML file must contain the full rendered Kazakh provisions;
an empty Save Page shell is insufficient. A genuine official UTF-8 TXT export is
supported if available, but one was not found in the current Download component.

An official browser-generated PDF is a legitimate alternative download, subject
to the user's ordinary sign-in and source limits. **PDF and DOCX are not directly
supported inputs.** If HTML cannot preserve the rendered text, retain the original
PDF and acquisition metadata for a separately documented, source-checked extraction;
do not rename it or pretend conversion was already validated. Official support can
also be asked for a permitted HTML/TXT research export. No message was sent.

Source-byte authenticity, Kazakh language quality, boundaries, normalization,
deduplication, law-family splits and overlap checks still require actual legal
text. No source/content QA approval was manufactured. The existing research-export
requirements for protected semantic-evaluation artifacts and real human QA remain
unmet and unchanged. A small ten-document intake may also produce empty folds;
the 80/10/5/5 policy and leakage edges must not be adjusted merely to force a pass.

## Reproduction and outputs

From the repository root, activate `.venv`. The successful catalog download repeats
the exact pinned `acquire-hub` command in the previous pilot report. The completed
raw store and upstream lock are under `data/legal_corpus/pilot-2026-10-16/`.
Then run:

```bash
python -m kazlegal_corpus discover-catalog \
  --raw-dir data/legal_corpus/pilot-2026-10-16/discovery-raw \
  --receipt c4690bf95858442187331638e02661f2f014add34a1a979ab622ce1d203383a5 \
  --limit 75 --seed adilet-pilot-2026-10-16-v1 --status all \
  --output data/legal_corpus/pilot-2026-10-16/adilet-manifest-075.jsonl
python -m pytest -q -k 'not test_project_dapt_trains_saves_and_evaluates_local_checkpoint'
```

The manifest already exists locally; choose a new output name when repeating its
immutable write. Tests used software fixtures and do not validate this unacquired
corpus. No training was run. C4, source code, model configurations and methodology
were preserved.

`results.json`, policy/route checks and their hashes, the measured discovery report,
compact 75-ID manifest, first-ten list and test log are committed alongside this
report. Raw catalog bytes and frontend/terms inspection files remain outside Git.
**The remaining blocker is obtaining permitted, complete official legal text in an
ingestible form—not the previous network 403.**
