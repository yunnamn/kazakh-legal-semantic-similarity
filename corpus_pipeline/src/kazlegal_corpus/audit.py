"""Read-only local repository inventory and review candidates, never a fake scientific audit."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

from .errors import CorpusError
from .io import digest, file_sha, write_json

TEXT_EXTENSIONS = {".py", ".md", ".txt", ".toml", ".yml", ".yaml", ".json", ".jsonl", ".csv", ".tsv", ".sh", ".ini", ".cfg", ".ipynb"}
RULES = {
    "keyword_filtering": r"legal_keywords|keywords|\bmc4\b|\bc4\b",
    "row_random_split_review_grouping": r"train_test_split|random_split|\.shuffle\(",
    "potential_unseeded_randomness": r"random\.|np\.random|numpy\.random|torch\.rand",
    "checkpoint_selection": r"load_best_model_at_end|metric_for_best_model|early.stop|best.*checkpoint",
    "mlm_masking_and_loss": r"DataCollatorForLanguageModeling|mlm_probability|labels|perplexity",
    "evaluation_protocol": r"spearman|pearson|cosine|similarity|evaluate\(|compute_metrics",
    "padding_pooling_truncation": r"mean\(.*dim|pooling|attention_mask|truncation|max_length",
    "annotation_or_sampling": r"annotat|negative|positive|pair|sample\(",
    "external_or_generated_data": r"openai|gpt-|generate\(|synthetic|paraphras|load_dataset",
    "possible_direct_train_eval_alias": r"eval_dataset\s*=\s*train_dataset|test_dataset\s*=\s*train_dataset",
}


def git(root: Path, *arguments: str) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(root), *arguments], text=True, stderr=subprocess.PIPE).rstrip("\r\n")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise CorpusError("A local Git checkout is required for a commit-bound repository audit") from exc


def audit_repository(root: Path, output: Path) -> dict:
    root = root.resolve()
    if output.exists():
        raise CorpusError("Audit output already exists; retain prior audits and choose a new directory")
    commit = git(root, "rev-parse", "HEAD")
    # NUL-delimited tracked paths cover every tracked file, including notebook artifacts.
    tracked = git(root, "ls-files", "-z").split("\0")
    tracked = sorted(p for p in tracked if p)
    inventory = []
    findings = []
    notebook_exports = {}
    for relative in tracked:
        path = root / relative
        entry = {"path": relative, "review_status": "not_human_reviewed"}
        if path.is_symlink():
            entry.update({"kind": "symlink", "target": str(path.readlink()), "read_status": "not_followed"})
            inventory.append(entry)
            continue
        if not path.is_file():
            entry.update({"kind": "missing_or_submodule", "read_status": "requires_separate_inspection"})
            inventory.append(entry)
            continue
        entry.update({"sha256": file_sha(path), "bytes": path.stat().st_size})
        data = path.read_bytes()
        if data.startswith(b"version https://git-lfs.github.com/spec/"):
            entry.update({"kind": "git_lfs_pointer", "read_status": "actual_object_not_inspected"})
            inventory.append(entry)
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeError:
            entry.update({"kind": "binary", "read_status": "hashed_binary_requires_format_review"})
            inventory.append(entry)
            continue
        entry.update({"kind": "text", "read_status": "entire_file_read_not_methodologically_reviewed"})
        if path.suffix == ".ipynb":
            try:
                notebook = json.loads(text)
            except ValueError as exc:
                raise CorpusError(f"Invalid notebook {relative}: {exc}") from exc
            pieces = []
            cells = []
            for i, cell in enumerate(notebook.get("cells", [])):
                source = cell.get("source", "")
                source = "".join(source) if isinstance(source, list) else source
                cells.append({"index": i, "type": cell.get("cell_type"), "source_sha256": digest(source),
                              "execution_count": cell.get("execution_count"), "outputs_count": len(cell.get("outputs", []))})
                if cell.get("cell_type") == "code":
                    pieces.append(f"# original notebook cell {i}\n{source}\n")
            entry["notebook_cells"] = cells
            text = "\n".join(pieces)
            notebook_exports[relative] = text
        if path.suffix in {".py", ".ipynb", ".sh", ".toml", ".yaml", ".yml", ".json", ".md"}:
            for line_no, line in enumerate(text.splitlines(), 1):
                for rule, pattern in RULES.items():
                    if re.search(pattern, line, re.I):
                        findings.append({"path": relative, "line": line_no, "rule": rule,
                                         "evidence": line[:1500], "status": "review_candidate_not_confirmed_bug",
                                         "line_basis": "exported_notebook_code" if path.suffix == ".ipynb" else "original_file"})
        if path.suffix == ".py":
            try:
                tree = ast.parse(text)
                entry["imports"] = sorted({n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                                          {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names})
                entry["functions"] = sorted({n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))})
            except SyntaxError:
                entry["python_parse_status"] = "syntax_error_or_different_python_version"
        inventory.append(entry)
    output.mkdir(parents=True)
    report = {"schema_version": 1, "repository_commit": commit, "git_status": git(root, "status", "--porcelain"),
              "files": inventory, "tracked_files": len(inventory),
              "scope": "all tracked working-tree files; history/dependencies/external data not audited",
              "scientific_audit_complete": False}
    write_json(output / "repository_inventory.json", report)
    write_json(output / "methodology_review_candidates.json", findings)
    for relative, text in notebook_exports.items():
        name = digest(relative)[:16] + ".py"
        path = output / "notebook_code" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return report
