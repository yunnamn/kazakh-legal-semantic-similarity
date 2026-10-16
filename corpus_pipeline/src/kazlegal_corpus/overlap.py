"""Deterministic disk-backed overlap joins, not semantic equivalence judgements.

Prefix filtering is an exact candidate filter for the configured Jaccard relation:
if J(A,B) >= t, their intersection contains >= t*max(|A|,|B|) elements, so their
prefixes of length |A|-ceil(t*|A|)+1 share an element in a common global order.
Candidates are verified with the complete sets. There is no LSH recall lottery.
"""
from __future__ import annotations

import json
import sqlite3
from fractions import Fraction
from typing import Iterable

from .errors import CorpusError
from .io import text_sha
from .normalize import guard_text


class UnionFind:
    def __init__(self, nodes: Iterable[str] = ()):
        self.parent = {n: n for n in nodes}

    def find(self, node: str) -> str:
        if node not in self.parent:
            self.parent[node] = node
        root = node
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[node] != node:
            following = self.parent[node]
            self.parent[node] = root
            node = following
        return root

    def union(self, a: str, b: str) -> None:
        a, b = self.find(a), self.find(b)
        if a != b:
            self.parent[max(a, b)] = min(a, b)

    def components(self) -> list[list[str]]:
        groups: dict[str, list[str]] = {}
        for node in sorted(self.parent):
            groups.setdefault(self.find(node), []).append(node)
        return sorted(groups.values(), key=lambda group: group[0])


def shingles(text: str, width: int) -> set[str]:
    tokens = guard_text(text).split()
    return {text_sha("\x00".join(tokens[i:i + width])) for i in range(max(0, len(tokens) - width + 1))}


def _chunks(values: list, n: int = 400):
    for i in range(0, len(values), n):
        yield values[i:i + n]


class SimilarityIndex:
    def __init__(self, db: sqlite3.Connection, *, threshold: float, width: int,
                 min_words: int, max_candidates: int):
        self.db = db
        self.t = Fraction(str(threshold))
        self.width = width
        self.min_words = min_words
        self.max_candidates = max_candidates
        self.comparisons = 0
        self.db.executescript("""
            CREATE TABLE fp (uid TEXT PRIMARY KEY, node TEXT, kind TEXT, guard TEXT,
                             n INTEGER, grams TEXT, UNIQUE(node, guard));
            CREATE INDEX fp_guard ON fp(guard);
            CREATE TABLE prefix (key TEXT, uid TEXT, PRIMARY KEY(key, uid)) WITHOUT ROWID;
        """)

    def exact(self, text: str, *, node: str, evaluation_only: bool = False) -> list[dict]:
        key = text_sha(guard_text(text))
        sql = "SELECT uid,node,kind FROM fp WHERE guard=? AND node<>?"
        params = [key, node]
        if evaluation_only:
            sql += " AND kind LIKE 'evaluation_%'"
        return [{"other_unit": uid, "other_node": n, "reason": "exact_guard_text", "guard_sha256": key}
                for uid, n, _ in self.db.execute(sql, params)]

    def add(self, uid: str, node: str, text: str, *, kind: str = "corpus_sentence") -> list[dict]:
        guard = guard_text(text)
        key = text_sha(guard)
        matches = self.exact(text, node=node)
        if self.db.execute("SELECT 1 FROM fp WHERE node=? AND guard=?", (node, key)).fetchone():
            return matches
        grams = shingles(text, self.width) if len(guard.split()) >= self.min_words else set()
        n = len(grams)
        ordered = sorted(grams)
        prefix_len = n - ((n * self.t.numerator + self.t.denominator - 1) // self.t.denominator) + 1 if n else 0
        prefix = ordered[:prefix_len]
        candidates: set[str] = set()
        for chunk in _chunks(prefix):
            marks = ",".join("?" for _ in chunk)
            sql = f"SELECT DISTINCT p.uid FROM prefix p JOIN fp f ON p.uid=f.uid WHERE p.key IN ({marks}) AND f.node<>? AND f.guard<>?"
            for (candidate,) in self.db.execute(sql, [*chunk, node, key]):
                candidates.add(candidate)
                if len(candidates) > self.max_candidates:
                    raise CorpusError(f"Near-duplicate candidate budget exceeded for {uid}; increase resources or review common text, never silently skip candidates")
        for candidate in sorted(candidates):
            other_node, m, encoded = self.db.execute("SELECT node,n,grams FROM fp WHERE uid=?", (candidate,)).fetchone()
            if min(n, m) * self.t.denominator < max(n, m) * self.t.numerator:
                continue
            self.comparisons += 1
            other = set(json.loads(encoded))
            intersection = len(grams & other)
            union = n + m - intersection
            if union and intersection * self.t.denominator >= union * self.t.numerator:
                matches.append({"other_unit": candidate, "other_node": other_node,
                                "reason": "near_word_shingle_jaccard", "intersection": intersection,
                                "union": union, "jaccard": round(intersection / union, 8)})
        self.db.execute("INSERT INTO fp VALUES (?,?,?,?,?,?)", (uid, node, kind, key, n, json.dumps(ordered)))
        self.db.executemany("INSERT INTO prefix VALUES (?,?)", ((g, uid) for g in prefix))
        return matches


class SpanIndex:
    """Every contiguous window, stride one; catches substring contamination/chunk boundaries."""
    def __init__(self, db: sqlite3.Connection, *, width: int, max_candidates: int):
        self.db = db
        self.width = width
        self.max_candidates = max_candidates
        self.db.execute("CREATE TABLE span (key TEXT, node TEXT, uid TEXT, PRIMARY KEY(key,node)) WITHOUT ROWID")

    def add(self, uid: str, node: str, text: str) -> list[dict]:
        keys = sorted(shingles(text, self.width))
        found: dict[str, dict] = {}
        for chunk in _chunks(keys):
            marks = ",".join("?" for _ in chunk)
            for key, other_node, other_uid in self.db.execute(
                    f"SELECT key,node,uid FROM span WHERE key IN ({marks}) AND node<>? ORDER BY key,node", [*chunk, node]):
                found.setdefault(other_node, {"other_node": other_node, "other_unit": other_uid,
                                              "reason": "contiguous_word_overlap", "window_words": self.width,
                                              "window_sha256": key})
                if len(found) > self.max_candidates:
                    raise CorpusError("Overlap candidate budget exceeded; refusing an incomplete leakage scan")
        self.db.executemany("INSERT OR IGNORE INTO span VALUES (?,?,?)", ((key, node, uid) for key in keys))
        return [found[n] for n in sorted(found)]
