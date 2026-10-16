---
language:
  - kk

license: cc-by-4.0

pretty_name: KazakhLawCorpus-clean

size_categories:
  - 100K<n<1M

multilinguality:
  - monolingual

language_creators:
  - expert-generated

annotations_creators:
  - no-annotation

source_datasets:
  - extended

task_categories:
  - text-retrieval
  - text-classification
  - text-generation

task_ids:
  - document-retrieval
  - language-modeling

tags:
  - kazakh
  - legal
  - legislation
  - law
  - legal-nlp
  - corpus
  - low-resource-language
  - information-retrieval
  - semantic-search
  - retrieval
  - document-retrieval
  - retrieval-augmented-generation
  - rag
  - legal-search
  - legal-question-answering
  - legal-document-classification
  - metadata

configs:
  - config_name: default
    data_files:
      - split: train
        path: data/kazakhlawcorpus_kk_only.csv
---

# KazakhLawCorpus-clean

## Dataset Summary

**KazakhLawCorpus-clean** is a cleaned, Kazakh-only corpus of legislative documents from the Republic of Kazakhstan. It is a processed derivative of the original [Arailym-tleubayeva/KazakhLawCorpus](https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus) dataset.

The original dataset repository was downloaded from Hugging Face and used as the source for this release. Its `laws_metadata.csv` file contained **223,245 legislative records** with multilingual fields and source-oriented metadata.

The cleaned release contains **215,889 unique Kazakh-language legislative records**, with one row representing one legal act. Each record includes the available legal, temporal, institutional, regional, publication, and source metadata extracted from the official Adilet legal information system.

The dataset contains **25 metadata fields** and covers legal acts adopted between **1947-10-30** and **2026-07-20**.

The corpus is intended for research and development in:

- Legal information retrieval
- Retrieval-augmented generation
- Legal question answering
- Legal document classification
- Semantic search
- Legal natural language processing
- Language model adaptation
- Corpus linguistics
- Low-resource Kazakh-language NLP

## Dataset Origin and Derivation

**KazakhLawCorpus-clean** was produced from the original **KazakhLawCorpus** dataset through a reproducible cleaning and validation pipeline.

The processing procedure included:

1. Selecting the Kazakh-language fields with the `_kk` suffix.
2. Removing the corresponding Russian-language fields with the `_ru` suffix.
3. Removing mixed-language base fields where Kazakh-specific versions were available.
4. Renaming the retained Kazakh-language fields to their base field names.
5. Converting source-system placeholders to null values.
6. Detecting and removing CAPTCHA, bot-verification, and scraping artefacts.
7. Removing records without usable Kazakh-language content.
8. Removing records missing the essential `title` or `description` fields.
9. Validating the dataset schema and identifiers.
10. Confirming the one-row-per-law structure.
11. Preserving the available source, temporal, legal-status, institutional, publication, and regional metadata.

The original dataset contained **223,245 records**. During preprocessing, **7,356 records** were removed, resulting in a final corpus of **215,889 unique Kazakh-language legislative records**.

The original source dataset remains available separately and has not been replaced or modified by this cleaned release.

## Relationship Between the Repositories

| Repository | Purpose |
|---|---|
| [KazakhLawCorpus](https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus) | Original multilingual dataset containing source-oriented and unprocessed metadata |
| [KazakhLawCorpus-clean](https://huggingface.co/datasets/Arailym-tleubayeva/KazakhLawCorpus-clean) | Cleaned, Kazakh-only, one-row-per-law research release |

Users who require the original multilingual fields, historical versions, reference links, or unprocessed source metadata should use **KazakhLawCorpus**.

Users who require a cleaned Kazakh-language table for NLP, information retrieval, semantic search, legal document classification, corpus analysis, or retrieval-augmented generation should use **KazakhLawCorpus-clean**.

## Dataset Statistics

| Property | Value |
|---|---:|
| Final documents | 215,889 |
| Original documents | 223,245 |
| Records removed during cleaning | 7,356 |
| Metadata fields | 25 |
| Unique `law_id` values | 215,889 |
| Duplicate `law_id` values | 0 |
| Missing `title` values | 0 |
| Missing `description` values | 0 |
| Date coverage | 1947-10-30 to 2026-07-20 |
| Language | Kazakh |
| License | CC BY 4.0 |

## Data File

The dataset is distributed as:

```text
data/kazakhlawcorpus_kk_only.csv
```

Each row corresponds to one legal act.

## Dataset Structure

### Dataset Schema

The dataset contains the following 25 fields:

| Field | Description |
|---|---|
| `source_id` | Identifier inherited from the source system |
| `law_id` | Unique identifier of the legal act |
| `date_adopted` | Date on which the legal act was adopted |
| `date_modified` | Most recent available modification date |
| `date_published` | Publication date |
| `state_registry_number` | State registry number |
| `law_registry_number` | Legal act registry number |
| `gov_registration_number` | Government registration number |
| `ministry_registration_date` | Ministry registration date |
| `is_archive` | Indicator showing whether the record is archived |
| `is_repealed` | Indicator showing whether the legal act has been repealed |
| `adilet_url` | URL of the document in the Adilet legal information system |
| `ekb_url` | URL associated with the EKB source system |
| `title` | Kazakh-language title of the legal act |
| `description` | Kazakh-language description or text content |
| `official_publication_info` | Information about official publication |
| `act_form` | Form or type of the legal act |
| `legal_relation_area` | Area of legal regulation |
| `legal_force` | Legal force or hierarchical status |
| `adopting_body` | Institution that adopted the legal act |
| `regulatory_body` | Responsible regulatory institution |
| `developer_body` | Institution that developed the legal act |
| `region` | Region associated with the legal act |
| `place_of_adoption` | Place where the legal act was adopted |
| `database_section` | Section of the source legal database |

## Cleaning Pipeline

The corpus was produced using a reproducible, multi-stage cleaning pipeline.

1. Kazakh-language fields ending in `_kk` were selected.
2. Russian-language fields ending in `_ru` were removed.
3. Mixed-language base fields were removed where language-specific fields were available.
4. Retained `_kk` columns were renamed to their corresponding base names.
5. Source placeholders such as `"ЖОҚ"`, `"НЕТ"`, `"N/A"`, `"-"`, and `"---"` were converted to null values.
6. CAPTCHA, bot-verification, and scraping artefacts were identified and removed.
7. Records without usable Kazakh-language content were removed.
8. Records missing the required `title` or `description` fields were removed.
9. Identifier uniqueness was validated.
10. Date fields were validated.
11. URL fields were checked.
12. Duplicate titles and descriptions were analysed.
13. Metadata consistency checks were performed.
14. The final one-row-per-law structure was confirmed.

## Quality Validation

The dataset underwent the following validation procedures:

- [x] Schema validation
- [x] Identifier validation
- [x] Duplicate identifier detection
- [x] Missing-value analysis
- [x] Metadata completeness analysis
- [x] URL validation
- [x] Date validation
- [x] Unicode validation
- [x] Encoding validation
- [x] CAPTCHA and bot-verification detection
- [x] Statistical quality assessment
- [x] One-row-per-law structure validation

## Known Limitations

Some metadata fields are sparse because the corresponding information is absent from the original source database.

Fields with relatively high levels of missing data may include:

- `developer_body`
- `regulatory_body`
- `ministry_registration_date`
- `date_modified`
- `date_published`

These missing values reflect the completeness of the original source rather than errors introduced during preprocessing.

The `is_archive` field is constant in the current release and should therefore not be treated as an informative feature for statistical modelling.

Duplicate titles may occur legitimately because many legal acts follow standardised naming conventions or share similar titles across regions, institutions, and adoption dates.

The dataset represents the source records available at the time of collection and may not reflect subsequent amendments, repeals, or corrections made in the official legal information system.

## Intended Uses

The dataset may be used for research and development in:

- Sparse legal document retrieval
- Dense retrieval
- BM25 evaluation
- Hybrid retrieval
- Retrieval-augmented generation
- Legal question answering
- Legal document classification
- Legal search systems
- Text similarity detection
- Metadata prediction
- Corpus analysis
- Language model fine-tuning
- Domain adaptation for Kazakh-language models

## Out-of-Scope Uses

This dataset must not be treated as a source of legal advice.

Users should verify legal provisions, document status, amendments, and current applicability against official legal information sources before making legal, administrative, financial, or policy decisions.

The dataset should not be used as the sole basis for automated decisions that may affect individuals, organisations, or legal rights.

## Loading the Dataset

The dataset can be loaded using the Hugging Face `datasets` library:

```python
from datasets import load_dataset

dataset = load_dataset(
    "Arailym-tleubayeva/KazakhLawCorpus-clean"
)

df = dataset["train"].to_pandas()
```

To inspect the dataset structure:

```python
print(dataset)
print(dataset["train"].column_names)
print(dataset["train"][0])
```

## Reproducibility

The accompanying analysis and preprocessing pipeline supports reproducible:

- Data cleaning
- Schema validation
- Identifier validation
- Duplicate analysis
- Missing-value analysis
- Metadata completeness assessment
- Statistical summaries
- Publication-quality figure generation
- `quality_report.json` generation

The original dataset remains available in a separate repository, allowing users to compare the cleaned release with its source data.

## License

This dataset is released under the **Creative Commons Attribution 4.0 International — CC BY 4.0** license.

Users may share and adapt the dataset for any purpose, provided that appropriate attribution is given.

## Citation

When using this dataset, please cite it as follows:

Tleubayeva, A., Mansurova, A., Shomanov, A., Makhambetova, Z., & Boluk, P. S. (2026). KazakhLawCorpus: A Large-Scale Metadata Corpus for Kazakh Legislation. Data, 11(9), 217. https://doi.org/10.3390/data11090217
## Author

- **Arailym Tleubayeva**

## Contact

For questions, suggestions, error reports, or contributions, please use the issue tracker in the Hugging Face dataset repository.
