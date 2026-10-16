"""Structure-aware extraction. No fallback to an entire webpage body."""
from __future__ import annotations

import re
from typing import Iterator

from bs4 import BeautifulSoup, NavigableString, Tag

from .acquire import CHALLENGE
from .errors import CorpusError
from .normalize import ARTICLE, NOTE, SECTION, normalize

ROOT_SELECTORS = ("#text", "#div_text", ".doc-text", ".document-text", "#adilet-document-text")
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "pre", "blockquote"}
CONTAINERS = {"div", "section", "article", "main", "header", "footer", "aside", "ul", "ol", "dl", "dd", "dt"}


def _rendered_text(node: Tag) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name == "br":
                parts.append("\n")
            else:
                boundary = child.name in BLOCK_TAGS | CONTAINERS
                if boundary:
                    parts.append("\n")
                parts.append(_rendered_text(child))
                if boundary:
                    parts.append("\n")
    return "".join(parts)


def _walk_blocks(root: Tag) -> Iterator[dict]:
    if root.name == "table":
        caption = root.find("caption", recursive=False)
        if caption:
            yield {"text": _rendered_text(caption), "kind": "table_caption", "anchor": caption.get("id")}
        for row in root.find_all("tr"):
            # Do not accidentally duplicate rows inside a nested table.
            if row.find_parent("table") is not root:
                continue
            cells = row.find_all(["td", "th"], recursive=False)
            values = [_rendered_text(cell) for cell in cells]
            if values:
                yield {"text": "\t".join(values), "kind": "table_row", "table_cells": values,
                       "anchor": row.get("id")}
        return
    if root.name in BLOCK_TAGS:
        yield {"text": _rendered_text(root), "kind": "heading" if root.name.startswith("h") else "paragraph",
               "heading_level": int(root.name[1]) if re.fullmatch(r"h[1-6]", root.name) else None,
               "anchor": root.get("id"), "element": root.name}
        return
    inline: list[str] = []

    def flush() -> dict | None:
        text = "".join(inline)
        inline.clear()
        if text.strip():
            return {"text": text, "kind": "paragraph", "anchor": root.get("id"), "element": root.name}
        return None

    for child in root.children:
        if isinstance(child, NavigableString):
            inline.append(str(child))
        elif isinstance(child, Tag):
            if child.name in BLOCK_TAGS | CONTAINERS | {"table"}:
                if item := flush():
                    yield item
                yield from _walk_blocks(child)
            elif child.name == "br":
                inline.append("\n")
            else:
                inline.append(_rendered_text(child))
    if item := flush():
        yield item


def parse_html(data: bytes, *, selector: str | None = None, encoding: str = "utf-8") -> tuple[list[dict], dict]:
    try:
        html = data.decode(encoding, errors="strict")
    except (LookupError, UnicodeError) as exc:
        raise CorpusError("HTML encoding is unknown/invalid; specify the real source encoding, never replace errors") from exc
    if CHALLENGE.search(html[:1_000_000]):
        raise CorpusError("Bot challenge detected, not a legal document")
    soup = BeautifulSoup(html, "html.parser")
    selectors = (selector,) if selector else ROOT_SELECTORS
    found: dict[int, tuple[Tag, str]] = {}
    for candidate_selector in selectors:
        if candidate_selector.strip().lower() in {"html", "body", "*"}:
            raise CorpusError("Whole-page selectors are forbidden")
        try:
            matches = soup.select(candidate_selector)
        except Exception as exc:
            raise CorpusError(f"Invalid content selector: {candidate_selector!r}") from exc
        for match in matches:
            found[id(match)] = (match, candidate_selector)
    if len(found) != 1:
        raise CorpusError(f"Expected one verified legal-text container, found {len(found)}; inspect the saved HTML and supply selector")
    root, chosen = next(iter(found.values()))
    removed = []
    # Notes, footnotes, legal headers, signatures and repeal notices are NOT boilerplate.
    for tag in list(root.find_all(["script", "style", "noscript", "nav"])):
        removed.append({"tag": tag.name, "id": tag.get("id"), "reason": "nontext_or_navigation_element"})
        tag.decompose()
    for br in list(root.find_all("br")):
        br.replace_with("\n")
    blocks = list(_walk_blocks(root))
    if not any(normalize(b["text"])[0] for b in blocks):
        raise CorpusError("Selected document container is empty")
    h1 = soup.find("h1")
    title = normalize(_rendered_text(h1))[0] if h1 else None
    return blocks, {"selector": chosen, "removed_elements": removed, "extracted_title": title,
                    "parser": "beautifulsoup4/html.parser", "encoding": encoding}


def parse_text(data: bytes, *, encoding: str = "utf-8") -> tuple[list[dict], dict]:
    try:
        text = data.decode(encoding, errors="strict").replace("\r\n", "\n").replace("\r", "\n")
    except (LookupError, UnicodeError) as exc:
        raise CorpusError("Invalid text-export encoding") from exc
    if CHALLENGE.search(text[:1_000_000]):
        raise CorpusError("Challenge text is not corpus text")
    if re.search(r"<\s*(html|!doctype|body)\b", text, re.I):
        raise CorpusError("HTML supplied to the plain-text adapter; use the HTML adapter")
    # Do not pretend browser line wraps are recoverable paragraph boundaries.
    blocks = [{"text": line, "kind": "paragraph", "line": i, "anchor": None}
              for i, line in enumerate(text.split("\n"), 1) if line.strip()]
    return blocks, {"parser": "explicit_plain_text_lines", "encoding": encoding,
                    "warning": "Line wrapping cannot be distinguished from paragraph boundaries without publisher structure"}


def structure_blocks(raw_blocks: list[dict]) -> list[dict]:
    result = []
    section_path: dict[int, str] = {}
    article = None
    article_occurrence = -1
    article_heading = None
    for source_ordinal, raw in enumerate(raw_blocks):
        text, changes = normalize(raw["text"])
        if not text:
            continue
        kind = raw.get("kind", "paragraph")
        am = ARTICLE.match(text)
        sm = SECTION.match(text)
        if sm:
            label = sm.group(1).casefold()
            level = {"\u0431\u04e9\u043b\u0456\u043c": 1, "\u0442\u0430\u0440\u0430\u0443": 2}.get(label, 3)
            section_path = {k: v for k, v in section_path.items() if k < level}
            section_path[level] = text
            article = None
            article_heading = None
            kind = "section_heading"
        if am:
            article = am.group(1)
            article_heading = text
            article_occurrence += 1
            if kind == "heading" or re.fullmatch(r"\d+(?:-\d+)?\s*[-\u2010\u2011\u2013]\s*\u0431\u0430\u043f\s*\.?", text, re.I):
                kind = "article_heading"
        if NOTE.match(text):
            kind = "editorial_note"
        if kind == "heading" and "\u049b\u043e\u0441\u044b\u043c\u0448\u0430" in text.casefold():
            # An explicit annex heading resets article scope, not the document identity.
            section_path = {0: text}
            article = None
            article_heading = None
        locator = {"block_ordinal": source_ordinal, "anchor": raw.get("anchor")}
        if "line" in raw:
            locator["line"] = raw["line"]
        item = {
            "text": text, "kind": kind, "source_ordinal": source_ordinal,
            "article": article, "article_heading": article_heading,
            "article_occurrence": article_occurrence if article is not None else None,
            "section_path": [section_path[k] for k in sorted(section_path)],
            "normalization": changes, "source_locator": locator,
        }
        if "table_cells" in raw:
            item["table_cells"] = [normalize(v)[0] for v in raw["table_cells"]]
        result.append(item)
    return result
