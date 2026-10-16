# Adilet pilot attempt: blocked before legislation acquisition

**Result: zero authentic legal documents acquired or processed. No corpus release
or real-data end-to-end validation was produced.** This report records a failed
acquisition attempt, not the first validated corpus. No synthetic text, generated
annotations, model training or replacement research claims were introduced.

## Repository and execution evidence

Checked on 2026-10-16, using integration commit
`eb8995f394b6606009ef11cfdc6ed3148d2e1391` on the new feature branch
`codex/authentic-corpus-pilot`. The remote `codex/integrate-legal-corpus` branch
still identified that same commit. Remote `main` was
`5e84833d520eb5fed9fbc63e322a3fe0373a73d5`; it did not yet contain the integration.
There were no open pull requests when checked. This branch retains the integration
and adds evidence only; C4, model configurations, split policy and implementation
are unchanged.

The existing acquisition, source-review, corpus-design and experiment-integration
documents were read. A read-only inventory covered 101 tracked files at the base
commit. It is an inventory, not a completed scientific audit or human approval.
There were no `data/annotations/annotations_*.csv` files in this checkout.

| Actual outcome | Count or status |
|---|---|
| Intended pilot | Approximately 75 distinct official Kazakh acts |
| Executed official robots/access-policy probes | 2 |
| Official legal-document body requests | 0: stopped at policy preflight |
| Real legal documents acquired / processed / retained | 0 / 0 / 0 |
| Documents rejected after content/quality inspection | 0: no content inspected |
| Language/normalization/deduplication findings | Not measured on authentic data |
| Train / validation / MLM-test / annotation-pool | Not generated |
| Family isolation and cross-split leakage on authentic data | Not evaluated |
| Training-view export and real-data loader validation | Not completed |
| Authentic text examples with source references | 0 available; five cannot be supplied |

`results.json` keeps unavailable split/quality measurements null rather than
reporting invented zero-leakage or perfect-quality results.

## Access and redistribution review

At 09:23:38 UTC (14:23:38 Asia/Tashkent), the existing `PoliteAdiletClient` attempted
`https://adilet.zan.kz/robots.txt` with an identified project URL in its User-Agent
and normal TLS verification. The environment proxy refused the CONNECT tunnel:
`Tunnel connection failed: 403 Forbidden`. A permitted outside-sandbox retry at
09:25:12 UTC (14:25:12 Asia/Tashkent) returned the same error. Both executed results
are in `access-attempts.jsonl`.

This establishes an **environment/proxy access failure**, not an Adilet HTTP response,
robots prohibition or disconnection diagnosis. No challenge was solved, proxy
rotated, alternate source impersonated or access control bypassed. It was not
possible to inspect the current official access policy, live copyright-law text
or site-specific conditions, so no source approval was issued.
`adilet-source-review.unapproved.json` explicitly retains that status.

The repository cites Article 8 of Kazakhstan's copyright law as an exclusion for
specified official documents. That is an inherited claim, not newly verified legal
evidence, and is insufficient to approve every site component or automated access.
Redistribution of official raw/derived legislation remains **pending review**.
No raw legal texts were committed.

The environment draft now includes the required `adilet.zan.kz` destination. A saved
draft does not apply runtime networking or prove the source is reachable. The user
must review/save the network configuration in environment settings and publish the
environment when required by the UI; access must then be retested.

## Metadata discovery: useful evidence, not corpus content

The documented catalog's API and README were reachable:
`Arailym-tleubayeva/KazakhLawCorpus-clean`, pinned at
`588f13ed7af351c485955698de72de18fe9acce8`.
The pinned README declares CC BY 4.0 and permits sharing/adaptation with attribution.
It is preserved as `catalog-card.md`; the automated metadata-only review and
attribution are in `catalog-source-review.json`. This is not human legal-text QA
or approval for Adilet acquisition. The publisher-supplied bibliographic citation
has not been independently verified.

The file listing contained `README.md` and
`data/kazakhlawcorpus_kk_only.csv`. Server metadata advertised 336,764,115 CSV bytes.
The card claims 215,889 records; **we did not measure that count**.
The existing pinned `acquire-hub` command retained one license-evidence receipt,
but the CSV acquisition exited 2: Xet reconstruction could not reach
`us.aws.cdn.hf.co`. A HEAD request to the Hub-resolved HTTP download destination
also received proxy CONNECT 403 (`catalog-download-checks.jsonl`). The requested
outside-sandbox CDN retry was cancelled by the user and did not execute.
`catalog-acquisition.redacted.log` removes the temporary signed query string.

Consequently no 75-act sampling manifest was produced. Titles, descriptions and
publisher counts were not substituted for authentic legislative bodies or the
five requested examples. Were discovery available, the existing deterministic
document-ID hash sampler would select 75 acts from the catalog with seed
`adilet-pilot-2026-10-16-v1`, status `all`. This is a reproducible convenience pilot,
not a representative sample or certification of current legal validity. No seed
was tuned against downstream results.

## Actual pipeline execution and validation limits

The production `freeze-raw` command was run against the official raw-store location.
It exited **2**, with `ERROR: No content acquisitions to freeze`, and created no
raw lock. Parsing and later stages cannot truthfully run without source documents;
they were not run on synthetic substitutes, a metadata catalog or an empty fake
corpus. There are no authentic corpus statistics, duplicate rates, split files or
leakage measurements to defend from this attempt.

Independently, the current research export gate requires frozen, nonempty original
semantic-evaluation artifacts and real human source/boundary QA. Neither exists
in this checkout. Even after network access is repaired, diagnostic processing
must not be described as a reviewed, benchmark-protected training export until
these requirements are met. No gate or methodology was weakened to manufacture
a deliverable.

Regression checks: **122 passed, 1 deselected, 0 failed**. The tiny DAPT-training
test was deliberately excluded because training is a separate requested milestone.
The existing synthetic smoke check and `pip check` passed. These results establish
software/fixture behavior, not correctness of extraction from live Adilet HTML.
The recorded warnings concern bootstrap resamples with constant input, not corpus
language measurements. See `pytest.txt` and `environment.json`.

## Exact commands and output locations

Commands below run from the repository root with the existing `.venv` activated.
No dependency, application or lockfile changes were needed. Retained local artifacts
are under the ignored `data/legal_corpus/pilot-2026-10-16/`; committed evidence is
in this report directory.

Executed repository checks:

```bash
git ls-remote --heads origin
git fetch origin main codex/integrate-legal-corpus
git switch -c codex/authentic-corpus-pilot
git rev-parse HEAD origin/main
gh api repos/yunnamn/kazakh-legal-semantic-similarity/pulls
python -m pip check
python -m pytest -q -k 'not test_project_dapt_trains_saves_and_evaluates_local_checkpoint' \
  --junitxml=/workspace/pilot-acquisition/test-results/pytest.xml
python scripts/run_smoke_tests.py
```

Equivalent reproduction of each executed official-access probe (run the second
only after authorized sandbox/network troubleshooting; retain timestamps/results):

```bash
python - <<'PY'
from kazlegal_corpus.acquire import PoliteAdiletClient
client = PoliteAdiletClient(
    'https://github.com/yunnamn/kazakh-legal-semantic-similarity', timeout=20)
body, headers = client.fetch('https://adilet.zan.kz/robots.txt', maximum_bytes=1000000)
print(headers)
print(body.decode('utf-8'))
PY
```

Executed pinned catalog acquisition (failed; repeat only after access is repaired):

```bash
export HF_HOME=/workspace/.cache/huggingface
python -m kazlegal_corpus inspect-hub --repo Arailym-tleubayeva/KazakhLawCorpus-clean
python -m kazlegal_corpus acquire-hub \
  --raw-dir data/legal_corpus/pilot-2026-10-16/discovery-raw \
  --repo Arailym-tleubayeva/KazakhLawCorpus-clean \
  --revision 588f13ed7af351c485955698de72de18fe9acce8 \
  --file data/kazakhlawcorpus_kk_only.csv --format csv \
  --review reports/adilet-pilot-2026-10-16/catalog-source-review.json \
  --output data/legal_corpus/pilot-2026-10-16/catalog.upstream.lock.json
```

The pinned README was separately inspected with
`hf_hub_download(repo_id='Arailym-tleubayeva/KazakhLawCorpus-clean',
repo_type='dataset', revision='588f13ed7af351c485955698de72de18fe9acce8',
filename='README.md')`. The CSV size/ETag and resolved CDN hostname came from
`get_hf_file_metadata(hf_hub_url(...))`, not a completed CSV download.
Only the license-evidence receipt exists in `discovery-raw/`; no completed
`catalog.upstream.lock.json` exists. No official content receipt exists.

Executed inventory/template and official-freeze commands:

```bash
python -m kazlegal_corpus audit-repo --repo-root . \
  --output data/legal_corpus/pilot-2026-10-16/experiment-audit
python -m kazlegal_corpus experiment-review-template \
  --inventory data/legal_corpus/pilot-2026-10-16/experiment-audit/repository_inventory.json \
  --config corpus_pipeline/configs/pipeline.toml \
  --output data/legal_corpus/pilot-2026-10-16/experiment-review.unapproved.json
python -m kazlegal_corpus freeze-raw \
  --raw-dir data/legal_corpus/pilot-2026-10-16/official-raw \
  --output data/legal_corpus/pilot-2026-10-16/official.raw.lock.json
```

Use new output names for future immutable audit/build attempts. The base inventory
is bound to `eb8995f` and must not be presented as an audit of later commits.

## What must happen next

1. Apply permitted network access for `adilet.zan.kz` and, for catalog discovery,
   `us.aws.cdn.hf.co`. Retest; an allowlist is not source permission.
2. Inspect actual robots/access terms and official rights evidence. Complete the
   source review with defensible evidence before downloading legal bodies.
3. Acquire the official pilot using the existing polite client and a metadata-based
   manifest. Keep immutable source bytes and receipts locally while redistribution
   remains unresolved. Record all unavailable/rejected acts.
4. Run the existing process/split/validate workflow, review actual Kazakh source
   extraction, and quantify exclusions. Retain the 80/10/5/5 roles and law-family/
   overlap components: related provisions must stay together so evaluation cannot
   be inflated by near copies across folds. Do not force exact sentence ratios or
   discard leakage edges to make a small pilot pass.
5. Supply the real protected evaluation artifacts and complete genuine human QA
   before research export. Then check all four roles with the existing project
   loader and supply five source-linked excerpts from the acquired bytes.

This task has **not fulfilled the authentic-corpus objective**. The evidence makes
the blockers independently inspectable without claiming an unbuilt research result.
