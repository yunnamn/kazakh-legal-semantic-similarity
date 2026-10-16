from __future__ import annotations
from pathlib import Path
from .errors import CorpusError
from .io import digest, file_sha, read_json, safe_relative


def verify_artifacts(root: Path) -> dict:
    manifest = read_json(root / "manifest.json")
    if digest({k: v for k, v in manifest.items() if k != "build_id"}) != manifest.get("build_id"):
        raise CorpusError("Build manifest was modified")
    for relative, expected in manifest["files"].items():
        path = safe_relative(root, relative)
        if not path.is_file() or file_sha(path) != expected:
            raise CorpusError(f"Artifact missing or modified: {relative}")
    return manifest
