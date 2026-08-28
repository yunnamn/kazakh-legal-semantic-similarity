from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import run_sts_evaluation
from src.utils import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate lexical and embedding similarities against human annotations.")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration.")
    args = parser.parse_args()
    metrics, _ = run_sts_evaluation(load_config(args.config))
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
