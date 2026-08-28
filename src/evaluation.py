from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .annotation import jaccard_similarity, load_human_annotations, reject_pseudo_label_columns
from .embeddings import LaBSEEncoder, TransformerSentenceEncoder, cosine_for_paired_embeddings
from .models import model_specs
from .utils import get_path, load_config


def lexical_baseline_scores(pairs_df: pd.DataFrame) -> pd.DataFrame:
    from sklearn.feature_extraction.text import TfidfVectorizer

    all_texts = pd.concat([pairs_df["sentence_1"], pairs_df["sentence_2"]], ignore_index=True)
    vectorizer = TfidfVectorizer(lowercase=True, analyzer="word", ngram_range=(1, 2), min_df=1)
    vectorizer.fit(all_texts)
    left = vectorizer.transform(pairs_df["sentence_1"])
    right = vectorizer.transform(pairs_df["sentence_2"])
    tfidf_cosine = np.asarray(left.multiply(right).sum(axis=1)).ravel()
    jaccard = np.array(
        [jaccard_similarity(a, b) for a, b in zip(pairs_df["sentence_1"], pairs_df["sentence_2"])]
    )
    return pd.DataFrame(
        {"pair_id": pairs_df["pair_id"].values, "tfidf_cosine": tfidf_cosine, "token_jaccard": jaccard}
    )


def score_pairs_with_encoder(pairs_df: pd.DataFrame, model_key: str, variant: str = "base") -> pd.DataFrame:
    if model_key == "labse":
        if variant != "base":
            raise ValueError("Adapted LaBSE is not part of the core experiment.")
        encoder = LaBSEEncoder()
        label = "labse_base"
    else:
        encoder = TransformerSentenceEncoder(model_key, variant)
        label = f"{model_key}_{variant}"
    left = encoder.encode(pairs_df["sentence_1"].tolist())
    right = encoder.encode(pairs_df["sentence_2"].tolist())
    return pd.DataFrame({"pair_id": pairs_df["pair_id"].values, label: cosine_for_paired_embeddings(left, right)})


def safe_spearman(x, y) -> float:
    from scipy.stats import spearmanr

    value = spearmanr(x, y).statistic
    return float(value) if np.isfinite(value) else np.nan


def safe_pearson(x, y) -> float:
    from scipy.stats import pearsonr

    value = pearsonr(x, y).statistic
    return float(value) if np.isfinite(value) else np.nan


def bootstrap_ci(y_true, y_pred, metric_fn, n_boot: int = 2000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y_true), size=len(y_true))
        value = metric_fn(y_true[idx], y_pred[idx])
        if np.isfinite(value):
            values.append(value)
    if len(values) < max(10, n_boot // 10):
        return np.nan, np.nan
    return float(np.quantile(values, alpha / 2)), float(np.quantile(values, 1 - alpha / 2))


def evaluate_score_column(df: pd.DataFrame, score_col: str, config: dict | None = None) -> dict:
    config = config or load_config()
    reject_pseudo_label_columns(df)
    clean = df[["human_score", score_col]].dropna()
    if len(clean) < 3:
        raise ValueError(f"Need at least 3 labeled pairs for {score_col}.")
    y = clean["human_score"].to_numpy(dtype=float)
    pred = clean[score_col].to_numpy(dtype=float)
    rho = safe_spearman(y, pred)
    pearson = safe_pearson(y, pred)
    n_boot = int(config["evaluation"]["bootstrap_samples"])
    seed = int(config["seed"])
    rho_lo, rho_hi = bootstrap_ci(y, pred, safe_spearman, n_boot=n_boot, seed=seed)
    p_lo, p_hi = bootstrap_ci(y, pred, safe_pearson, n_boot=n_boot, seed=seed)
    return {
        "system": score_col,
        "n_pairs": len(clean),
        "spearman": rho,
        "spearman_ci_low": rho_lo,
        "spearman_ci_high": rho_hi,
        "pearson": pearson,
        "pearson_ci_low": p_lo,
        "pearson_ci_high": p_hi,
    }


def run_sts_evaluation(config: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or load_config()
    pairs, agreement = load_human_annotations(config)
    scores = pairs[["pair_id", "human_score"]].copy()
    scores = scores.merge(lexical_baseline_scores(pairs), on="pair_id", how="left")
    scores = scores.merge(score_pairs_with_encoder(pairs, "labse", "base"), on="pair_id", how="left")
    specs = model_specs(config)
    for key in ["mbert", "xlmr", "kazroberta"]:
        for variant in ["base", "dapt"]:
            if variant == "dapt" and not (specs[key]["adapted_dir"] / "config.json").exists():
                continue
            scored = score_pairs_with_encoder(pairs, key, variant)
            scores = scores.merge(scored, on="pair_id", how="left")
    metrics = pd.DataFrame(
        [evaluate_score_column(scores, col, config) for col in scores.columns if col not in {"pair_id", "human_score"}]
    ).sort_values("spearman", ascending=False)
    metrics_dir = get_path(config, "metrics_dir")
    metrics.to_csv(metrics_dir / "sts_metrics.csv", index=False)
    scores.to_csv(metrics_dir / "sts_pair_scores.csv", index=False)
    if not agreement.empty:
        agreement.to_csv(metrics_dir / "annotator_agreement.csv", index=False)
    return metrics, scores


def plot_sts_metrics(metrics: pd.DataFrame, config: dict | None = None) -> None:
    import matplotlib.pyplot as plt

    config = config or load_config()
    if metrics.empty:
        return
    x_values = np.arange(len(metrics))
    width = 0.36
    plt.figure(figsize=(max(9, len(metrics) * 0.8), 5))
    plt.bar(x_values - width / 2, metrics["spearman"], width, label="Spearman")
    plt.bar(x_values + width / 2, metrics["pearson"], width, label="Pearson")
    plt.xticks(x_values, metrics["system"], rotation=45, ha="right")
    plt.ylim(-1, 1)
    plt.ylabel("Correlation with human similarity score")
    plt.title("Kazakh legal semantic similarity: system comparison")
    plt.legend()
    plt.tight_layout()
    plt.savefig(get_path(config, "figures_dir") / "sts_correlation_comparison.png", dpi=160)


def plot_score_scatter(scores: pd.DataFrame, score_col: str, config: dict | None = None) -> None:
    import matplotlib.pyplot as plt

    config = config or load_config()
    clean = scores[["human_score", score_col]].dropna()
    plt.figure(figsize=(5, 4))
    plt.scatter(clean["human_score"], clean[score_col], alpha=0.7)
    plt.xlabel("Human similarity score (0-5)")
    plt.ylabel(score_col)
    plt.title(f"{score_col}: score vs human judgment")
    plt.tight_layout()
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", score_col)
    plt.savefig(get_path(config, "figures_dir") / f"scatter_{safe}.png", dpi=160)

