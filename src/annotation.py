from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .corpus import load_split, word_tokens
from .utils import get_path, load_config


FORBIDDEN_PSEUDO_LABEL_COLUMNS = {
    "auto_label",
    "pseudo_label",
    "mbert_label",
    "labse_label",
    "model_label",
    "predicted_label",
}


def token_set(text: str) -> set[str]:
    return set(word_tokens(text))


def jaccard_similarity(a: str, b: str) -> float:
    left = token_set(a)
    right = token_set(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def validate_score(score: float | int | str) -> float:
    value = float(score)
    if not 0 <= value <= 5:
        raise ValueError("Similarity score must be between 0 and 5.")
    return value


def reject_pseudo_label_columns(df: pd.DataFrame) -> None:
    found = FORBIDDEN_PSEUDO_LABEL_COLUMNS & set(df.columns)
    if found:
        raise ValueError(f"Pseudo-label columns are not allowed: {sorted(found)}")


def generate_annotation_candidates(config: dict | None = None) -> pd.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.neighbors import NearestNeighbors

    config = config or load_config()
    pool = load_split("annotation_pool", config).copy()
    n_pairs = int(config["annotation"]["candidate_count"])
    if len(pool) < 20:
        raise ValueError("Annotation pool is too small. Rebuild from a larger corpus.")

    texts = pool["text"].tolist()
    ids = pool["sentence_id"].tolist()
    tfidf = TfidfVectorizer(
        lowercase=True,
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        max_features=50_000,
    )
    x_matrix = tfidf.fit_transform(texts)
    k = min(8, len(pool))
    nn = NearestNeighbors(n_neighbors=k, metric="cosine")
    nn.fit(x_matrix)
    distances, indices = nn.kneighbors(x_matrix)
    pair_records: dict[tuple[int, int], dict] = {}
    rng = np.random.default_rng(int(config["seed"]))

    def add_pair(i: int, j: int, strategy: str) -> None:
        if i == j:
            return
        a, b = sorted((i, j))
        key = (a, b)
        if key in pair_records:
            return
        pair_records[key] = {
            "pair_id": f"pair-{len(pair_records) + 1:04d}",
            "sentence_1_id": ids[a],
            "sentence_2_id": ids[b],
            "sentence_1": texts[a],
            "sentence_2": texts[b],
            "sampling_strategy": strategy,
            "similarity_score": np.nan,
        }

    target_each = max(1, n_pairs // 4)
    neighbors = []
    for i in range(len(pool)):
        for rank in range(1, k):
            j = int(indices[i, rank])
            sim = 1.0 - float(distances[i, rank])
            neighbors.append((sim, i, j))

    for _, i, j in sorted(neighbors, reverse=True):
        if sum(r["sampling_strategy"] == "high_lexical_overlap" for r in pair_records.values()) >= target_each:
            break
        add_pair(i, j, "high_lexical_overlap")

    moderate = [(sim, i, j) for sim, i, j in neighbors if 0.15 <= sim <= 0.55]
    rng.shuffle(moderate)
    for _, i, j in moderate:
        if sum(r["sampling_strategy"] == "moderate_lexical_overlap" for r in pair_records.values()) >= target_each:
            break
        add_pair(i, j, "moderate_lexical_overlap")

    keyword_to_indices = defaultdict(list)
    for idx, keywords in enumerate(pool["matched_keywords"]):
        if isinstance(keywords, str):
            keywords = [kw.strip() for kw in keywords.strip("[]").replace("'", "").split(",") if kw.strip()]
        for keyword in keywords:
            keyword_to_indices[keyword].append(idx)

    hard = []
    for _, idxs in keyword_to_indices.items():
        if len(idxs) < 2:
            continue
        for _ in range(min(30, len(idxs) * 2)):
            i, j = rng.choice(idxs, size=2, replace=False)
            lexical = float(cosine_similarity(x_matrix[i], x_matrix[j])[0, 0])
            if lexical < 0.35:
                hard.append((lexical, int(i), int(j)))
    rng.shuffle(hard)
    for _, i, j in hard:
        if sum(r["sampling_strategy"] == "shared_keyword_hard_candidate" for r in pair_records.values()) >= target_each:
            break
        add_pair(i, j, "shared_keyword_hard_candidate")

    attempts = 0
    while (
        sum(r["sampling_strategy"] == "random_pair" for r in pair_records.values()) < target_each
        and attempts < n_pairs * 50
    ):
        i, j = rng.choice(len(pool), size=2, replace=False)
        add_pair(int(i), int(j), "random_pair")
        attempts += 1

    attempts = 0
    while len(pair_records) < n_pairs and attempts < n_pairs * 100:
        i, j = rng.choice(len(pool), size=2, replace=False)
        add_pair(int(i), int(j), "random_fill")
        attempts += 1

    out = pd.DataFrame(list(pair_records.values())).head(n_pairs)
    reject_pseudo_label_columns(out)
    if not out["similarity_score"].isna().all():
        raise AssertionError("Generated annotation candidates must keep similarity_score blank.")
    out_path = get_path(config, "annotation_candidates")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    return out


def annotate_pairs_cli(annotator_id: str, config: dict | None = None, resume: bool = True) -> pd.DataFrame:
    config = config or load_config()
    if not annotator_id.strip():
        raise ValueError("annotator_id cannot be blank")
    candidates_path = get_path(config, "annotation_candidates")
    candidates = pd.read_csv(candidates_path)
    reject_pseudo_label_columns(candidates)
    out_path = get_path(config, "annotations_dir") / f"annotations_{annotator_id}.csv"
    if resume and out_path.exists():
        annotations = pd.read_csv(out_path)
    else:
        annotations = candidates.copy()
        annotations["annotator_id"] = annotator_id
        annotations["similarity_score"] = np.nan

    for idx, row in annotations.iterrows():
        if pd.notna(row["similarity_score"]):
            continue
        print("\n" + "=" * 90)
        print(f"{row['pair_id']} | sampling={row['sampling_strategy']}")
        print("\nSentence 1:")
        print(row["sentence_1"])
        print("\nSentence 2:")
        print(row["sentence_2"])
        print("\n0=unrelated, 1=weak, 2=somewhat, 3=strong, 4=nearly equivalent, 5=equivalent")
        while True:
            value = input("Similarity [0-5], s=skip, q=quit: ").strip().lower()
            if value == "q":
                annotations.to_csv(out_path, index=False)
                return annotations
            if value == "s":
                break
            try:
                annotations.at[idx, "similarity_score"] = validate_score(value)
                annotations.at[idx, "annotator_id"] = annotator_id
                break
            except ValueError:
                print("Enter 0-5, 's', or 'q'.")
        annotations.to_csv(out_path, index=False)
    return annotations


def load_human_annotations(config: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    from scipy.stats import spearmanr

    config = config or load_config()
    files = sorted(Path(get_path(config, "annotations_dir")).glob("annotations_*.csv"))
    if not files:
        raise FileNotFoundError("No manual annotation files found.")
    frames = []
    for path in files:
        df = pd.read_csv(path)
        reject_pseudo_label_columns(df)
        if "annotator_id" not in df.columns:
            df["annotator_id"] = path.stem.replace("annotations_", "")
        frames.append(df)
    all_ann = pd.concat(frames, ignore_index=True)
    all_ann = all_ann[pd.notna(all_ann["similarity_score"])].copy()
    if all_ann.empty:
        raise ValueError("Annotation files exist but contain no scores.")
    all_ann["similarity_score"] = all_ann["similarity_score"].map(validate_score)
    meta_cols = ["pair_id", "sentence_1_id", "sentence_2_id", "sentence_1", "sentence_2", "sampling_strategy"]
    meta = all_ann[meta_cols].drop_duplicates("pair_id")
    scores = all_ann.groupby("pair_id", as_index=False).agg(
        human_score=("similarity_score", "mean"),
        n_annotators=("annotator_id", "nunique"),
    )
    aggregated = meta.merge(scores, on="pair_id", how="inner")
    agreement_rows = []
    annotators = sorted(all_ann["annotator_id"].unique())
    for i, a in enumerate(annotators):
        for b in annotators[i + 1 :]:
            left = all_ann[all_ann["annotator_id"] == a][["pair_id", "similarity_score"]]
            right = all_ann[all_ann["annotator_id"] == b][["pair_id", "similarity_score"]]
            merged = left.merge(right, on="pair_id", suffixes=("_a", "_b"))
            if len(merged) >= 3:
                rho = spearmanr(merged["similarity_score_a"], merged["similarity_score_b"]).statistic
                agreement_rows.append(
                    {"annotator_a": a, "annotator_b": b, "n_common_pairs": len(merged), "spearman": rho}
                )
    return aggregated, pd.DataFrame(agreement_rows)

