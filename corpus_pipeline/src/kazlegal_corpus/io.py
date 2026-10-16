"""Canonical serialization, bounded readers, and atomic immutable artifacts."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

from .errors import CorpusError


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise CorpusError("Expected an ISO-8601 timestamp with a timezone") from exc
    if parsed.tzinfo is None:
        raise CorpusError("A retrieval/review timestamp must include its timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_relative(root: Path, relative: str) -> Path:
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        raise CorpusError(f"Unsafe relative path: {relative!r}")
    result = (root / p).resolve()
    if not result.is_relative_to(root.resolve()):
        raise CorpusError(f"Path escapes root: {relative!r}")
    return result


def write_bytes(path: Path, data: bytes, *, immutable: bool = True) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if immutable and path.read_bytes() != data:
            raise CorpusError(f"Refusing to overwrite immutable artifact: {path}")
        if immutable:
            return
    fd, name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path: Path, value: Any, *, immutable: bool = True) -> None:
    write_bytes(path, canonical(value) + b"\n", immutable=immutable)


def read_json(path: Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    """Stream into a new path. Publication directories are atomically renamed later."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        for row in rows:
            handle.write(canonical(row) + b"\n")


def iter_jsonl(path: Path) -> Iterator[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError) as exc:
                raise CorpusError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
            if not isinstance(value, dict):
                raise CorpusError(f"Expected an object at {path}:{line_no}")
            yield value


def _json_array(handle, max_record_chars: int) -> Iterator[tuple[dict, dict]]:
    """Incremental JSON-array reader; malformed arrays fail, never auto-repair."""
    decoder = json.JSONDecoder()
    buffer = ""
    eof = False
    offset = 0
    index = 0

    def refill() -> None:
        nonlocal buffer, eof
        part = handle.read(65536)
        if not part:
            eof = True
        buffer += part

    def whitespace() -> None:
        nonlocal buffer, offset
        while True:
            trimmed = len(buffer) - len(buffer.lstrip())
            buffer = buffer[trimmed:]
            offset += trimmed
            if buffer or eof:
                return
            refill()

    refill()
    whitespace()
    if not buffer.startswith("["):
        raise CorpusError("JSON array input must begin with '['; use jsonl for JSON Lines")
    buffer = buffer[1:]
    offset += 1
    expect_value = True
    after_comma = False
    while True:
        whitespace()
        if buffer.startswith("]"):
            if after_comma:
                raise CorpusError("Trailing comma in JSON array")
            buffer = buffer[1:]
            offset += 1
            whitespace()
            if buffer:
                raise CorpusError("Trailing data after JSON array")
            return
        if not buffer and eof:
            raise CorpusError("Truncated JSON array")
        if not expect_value:
            if not buffer.startswith(","):
                raise CorpusError(f"Expected comma in JSON array near character {offset}")
            buffer = buffer[1:]
            offset += 1
            expect_value = True
            after_comma = True
            continue
        start = offset
        while True:
            try:
                value, end = decoder.raw_decode(buffer)
                break
            except json.JSONDecodeError as exc:
                if eof or len(buffer) > max_record_chars:
                    raise CorpusError(f"Invalid/oversize JSON record near character {start}: {exc}") from exc
                refill()
        if end > max_record_chars or not isinstance(value, dict):
            raise CorpusError("JSON input must contain bounded object records")
        yield value, {"record_index": index, "decoded_character_offset": start}
        index += 1
        buffer = buffer[end:]
        offset += end
        expect_value = False
        after_comma = False


def source_rows(path: Path, format_name: str, *, max_record_chars: int = 50_000_000,
                quarantine: list[dict] | None = None) -> Iterator[tuple[dict, dict]]:
    """Keep original archive bytes; locators refer to decoded records, not fake raw offsets."""
    compressed = format_name.endswith(".gz")
    base_format = format_name.removesuffix(".gz")
    if base_format == "parquet":
        if compressed:
            raise CorpusError("External gzip of Parquet is not supported")
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise CorpusError("Install the optional parquet dependency or obtain the publisher's JSON/CSV") from exc
        record_index = 0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=1024):
            for row in batch.to_pylist():
                yield row, {"record_index": record_index}
                record_index += 1
        return
    opener = gzip.open if compressed else open
    with opener(path, "rt", encoding="utf-8-sig", errors="strict", newline="") as handle:
        if base_format == "jsonl":
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    if len(line) > max_record_chars:
                        raise ValueError("Record exceeds maximum size")
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("Expected a JSON object")
                    yield row, {"line": line_no}
                except (ValueError, UnicodeError) as exc:
                    if quarantine is None:
                        raise CorpusError(f"Malformed input record at line {line_no}: {exc}") from exc
                    quarantine.append({"line": line_no, "decoded_line_sha256": text_sha(line),
                                       "reason": "malformed_jsonl", "detail": str(exc)[:500]})
        elif base_format == "csv":
            csv.field_size_limit(max_record_chars)
            reader = csv.DictReader(handle)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise CorpusError("Missing or duplicate CSV header fields")
            for record_index, row in enumerate(reader):
                if None in row or any(v is None for v in row.values()):
                    raise CorpusError(f"Malformed CSV record ending at line {reader.line_num}")
                yield row, {"record_index": record_index, "csv_end_line": reader.line_num}
        elif base_format == "json":
            yield from _json_array(handle, max_record_chars)
        else:
            raise CorpusError(f"Unsupported tabular format: {format_name}")
