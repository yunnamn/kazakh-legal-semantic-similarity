# First ten manual Adilet acquisitions

Place files in **`/workspace/kazakh-legal-semantic-similarity/data/legal_corpus/manual-inbox/`**.
This directory exists and is ignored by Git. If downloading on your own computer,
create a `manual-inbox/` folder, then upload a ZIP of it here; it will be placed at
that location. Do not put private account/session data in the ZIP.

These are the first ten IDs, in ID order, of the existing deterministic 75-act
sample, not invented URLs or a new semantic benchmark. Titles and dates below come
from the pinned metadata catalog, not verified current official body text. Confirm
the ID, Kazakh language and title in your browser before saving; record any mismatch
or unavailable document rather than substituting another act. `status=all` was
retained, so historical/repealed acts are possible. This is an intake pilot, not a
representative sample or assurance of current legal validity.

**Required format for each row:** `.html` containing the **fully rendered Kazakh
legal text**, saved through your normal browser after the whole act loads. In
Chrome/Firefox use Save Page As → Webpage, Complete and keep the related asset
folder if created. Check the saved file offline: the actual provisions must still
appear, not only the application logo, menus, a spinner or sign-in page. Keep the
single Kazakh text view, not a Russian/Kazakh comparison. Do not edit or regenerate
the legal wording. An actual publisher-provided UTF-8 `.txt` export with intact
paragraphs is also supported, if available; no TXT export was observed in the
current Download interface.

| # | Catalog title / identifier | Official Kazakh page | Save as |
|---|---|---|---|
| 1 | Қазақстан Республикасы Қаржы министрлігінің кейбір бұйрықтарының күші жойылды деп тану туралы — `G20E0000668` | [Open official page](https://adilet.zan.kz/kaz/docs/G20E0000668) | `G20E0000668.html` |
| 2 | Сунақата ауылдық округінің 2022-2024 жылдарға арналған бюджеті туралы — `G21LG00182M` | [Open official page](https://adilet.zan.kz/kaz/docs/G21LG00182M) | `G21LG00182M.html` |
| 3 | Біржан сал ауданы мәслихатының 2021 жылғы 24 желтоқсандағы № С-11/2 "2022 – 2024 жылдарға арналған аудандық бюджет туралы" шешіміне өзгерістер мен толықтыру енгізу туралы — `G22BJ00172M` | [Open official page](https://adilet.zan.kz/kaz/docs/G22BJ00172M) | `G22BJ00172M.html` |
| 4 | Сандықтау аудандық мәслихатының 2021 жылғы 27 желтоқсандағы № 13/2/11 "Сандықтау ауданының Максимов ауылдық округінің 2022-2024 жылдарға арналған бюджетін бекіту туралы" шешіміне өзгерістер енгізу туралы — `G22BP19311M` | [Open official page](https://adilet.zan.kz/kaz/docs/G22BP19311M) | `G22BP19311M.html` |
| 5 | "Мақат аудандық экономика және қаржы бөлімі" мемлекеттік мекемесі туралы Ережені бекіту туралы — `G22TG00079A` | [Open official page](https://adilet.zan.kz/kaz/docs/G22TG00079A) | `G22TG00079A.html` |
| 6 | Кентау қалалық мәслихатының 2021 жылғы 22 желтоқсандағы № 99 "2022-2024 жылдарға арналған қалалық бюджет туралы" шешіміне өзгерістер енгізу туралы — `G22UC00168M` | [Open official page](https://adilet.zan.kz/kaz/docs/G22UC00168M) | `G22UC00168M.html` |
| 7 | Еңбекшіқазақ ауданының 2024-2026 жылдарға арналған бюджеті туралы — `G23DH01358M` | [Open official page](https://adilet.zan.kz/kaz/docs/G23DH01358M) | `G23DH01358M.html` |
| 8 | Жер учаскесіне қауымдық сервитутты белгілеу туралы — `G23KMH1224B` | [Open official page](https://adilet.zan.kz/kaz/docs/G23KMH1224B) | `G23KMH1224B.html` |
| 9 | Қызылорда облысы Арал аудандық мәслихатының 2022 жылғы 26 желтоқсандағы № 342 "2023-2025 жылдарға арналған Беларан ауылдық округінің бюджеті туралы" шешіміне өзгерістер енгізу туралы — `G23LC00117M` | [Open official page](https://adilet.zan.kz/kaz/docs/G23LC00117M) | `G23LC00117M.html` |
| 10 | Кейбір коммуналдық мемлекеттік мекемелерді қайта атау туралы — `G23TF00144A` | [Open official page](https://adilet.zan.kz/kaz/docs/G23TF00144A) | `G23TF00144A.html` |

For every file, keep a matching `<ID>.acquisition.json`. Start from
[`manual-sidecar.uncompleted.json`](../reports/adilet-pilot-recheck-2026-10-16/manual-sidecar.uncompleted.json)
or the existing `corpus_pipeline/configs/manual-adilet.example.json` and record:

- `source_document_id` and `canonical_url`: the exact ID and Kazakh page in the table;
- `source_url`: the actual official page/download URL used, without inventing a
  `.pdf`, `.txt` or export endpoint;
- `retrieved_at`: the actual download date/time including timezone;
- `title` and `source_version`: what you actually observed; leave unknowns null;
- `acquisition_method`: `manual`; `acquisition_note`: the browser/export method,
  whether the saved copy includes rendered HTML, and any conversion performed;
- `encoding`: `utf-8` when verified. Keep the downloaded bytes unchanged.

For HTML use `adapter=adilet_html`, `format=html`. The current frontend identifies
its text container as `[data-tour="doc-body-content"]`; that candidate selector
is supplied in the template and will be checked against the actual saved files.
The pipeline requires exactly one nonempty legal-text container. Do not substitute
`body`, `html` or `*` to force acceptance. For a genuine official text export use
`adapter=adilet_text`, `format=text`, and `selector=null`. Acquisition timestamps and
review fields in the template are deliberately incomplete, not ready-made approvals.
You can supply the acquisition facts and leave the source/content review for intake.

**If the browser save is still an empty app shell:** the verified official alternative
is the site's normal Download / Жүктеу → PDF interface. Sign in only through your
own normal account, and obey displayed limits. Preserve the original `<ID>.pdf`
and its acquisition facts, then upload it for inspection. PDF/DOCX are **not direct
inputs to this pipeline**; a separately documented, source-checked conversion
would be necessary before processing. Do not rename a PDF to `.txt`, copy text from
search results, translate Russian text, or turn on OCR without retaining and reviewing
the original. No authentic PDF was downloaded or converted during this task.

Another legitimate route is to ask the official support channel, `support@zqai.kz`
(listed in the current user agreement §4.2.3), for a permitted Kazakh HTML/TXT research
export of these ten IDs or the full 75-act manifest. Describe the intended corpus/
MLM research and ask for any collection/redistribution conditions. No message has
been sent on your behalf. Account access or manual saving must not be used to bypass
source restrictions on the intended use.

## Intake with the existing pipeline

Once genuine files and their source review are checked, existing commands suffice:

```bash
source .venv/bin/activate
python -m kazlegal_corpus import-raw \
  --raw-dir data/legal_corpus/manual-raw \
  --file data/legal_corpus/manual-inbox/G20E0000668.html \
  --sidecar data/legal_corpus/manual-inbox/G20E0000668.acquisition.json \
  --review /path/to/completed-actual-source-review.json
python -m kazlegal_corpus freeze-raw \
  --raw-dir data/legal_corpus/manual-raw \
  --output data/legal_corpus/manual.raw.lock.json
python -m kazlegal_corpus process \
  --raw-dir data/legal_corpus/manual-raw \
  --raw-lock data/legal_corpus/manual.raw.lock.json \
  --config corpus_pipeline/configs/pipeline.toml \
  --output data/legal_corpus/manual-processed-001
```

Repeat `import-raw` for the other verified files before freezing. The review path is
an unmet input, not a file created or approved by this handoff. Diagnostics can then
use the existing `split` and `validate` commands. With only ten law families, some
folds may be empty; do not move documents or relax leakage rules to force a pass.
A research training view still requires the actual frozen semantic-evaluation
artifacts and completed human source/boundary QA. No such export is claimed here.

Metadata attribution: Arailym Tleubayeva, *KazakhLawCorpus-clean*, CC BY 4.0,
revision `588f13ed7af351c485955698de72de18fe9acce8`. Official text source: Adilet legal
information system. The source metadata and measured discovery results are in
[`reports/adilet-pilot-recheck-2026-10-16/`](../reports/adilet-pilot-recheck-2026-10-16/).
