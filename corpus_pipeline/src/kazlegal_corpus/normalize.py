"""Conservative normalization and legal sentence spans. Text is never paraphrased."""
from __future__ import annotations

import re
import unicodedata

# U+FEFF and U+200B are layout artifacts; all other punctuation/letters survive.
_LAYOUT = {"\ufeff": "", "\u200b": ""}
WORDS = re.compile(r"\w+", flags=re.UNICODE)
KAZAKH_LETTERS = set("\u04d9\u0493\u049b\u04a3\u04e9\u04b1\u04af\u04bb\u0456")
ABBREVIATIONS = {"\u0436", "\u0431", "\u049b", "\u0442.\u0431", "\u0442.\u0441.\u0441", "\u0442.\u0442", "\u043c\u043b\u043d", "\u043c\u043b\u0440\u0434"}
ARTICLE = re.compile(r"^(\d+(?:-\d+)?)\s*[-\u2010\u2011\u2013]\s*\u0431\u0430\u043f\b", re.I)
SECTION = re.compile(r"^(?:[IVXLCDM]+|\d+(?:-\d+)?)\s*[-. ]*\s*(\u0431\u04e9\u043b\u0456\u043c|\u0442\u0430\u0440\u0430\u0443|\u043f\u0430\u0440\u0430\u0433\u0440\u0430\u0444)\b", re.I)
NOTE = re.compile(r"^(?:\u0415\u0441\u043a\u0435\u0440\u0442\u0443|\u0415\u0441\u043a\u0435\u0440\u0442\u043f\u0435|\u0421\u043d\u043e\u0441\u043a\u0430)\s*[.:]", re.I)


def normalize(text: str) -> tuple[str, dict]:
    if not isinstance(text, str):
        raise TypeError("Corpus text must be a string")
    nfc = unicodedata.normalize("NFC", text)
    counts = {"nfc_changed": int(nfc != text), "removed_bom": nfc.count("\ufeff"),
              "removed_zero_width_space": nfc.count("\u200b")}
    value = "".join(_LAYOUT.get(c, c) for c in nfc)
    value = re.sub(r"\s+", " ", value, flags=re.UNICODE).strip()
    counts["whitespace_changed"] = int(value != nfc)
    return value, counts


def guard_text(text: str) -> str:
    """ONLY for conservative overlap detection; never emitted as training text."""
    normalized, _ = normalize(text)
    return " ".join(WORDS.findall(normalized.casefold()))


def words(text: str) -> list[str]:
    return WORDS.findall(text)


def language_signals(text: str, *, declared: str) -> dict:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return {"decision": "reject_no_letters", "alphabetic": 0, "kk_specific": 0,
                "cyrillic_ratio": 0.0, "kk_specific_ratio": 0.0}
    cyrillic = sum("CYRILLIC" in unicodedata.name(c, "") for c in letters)
    kk = sum(c.casefold() in KAZAKH_LETTERS for c in letters)
    ratio = cyrillic / len(letters)
    kr = kk / len(letters)
    if declared not in {"kk", "kaz"}:
        decision = "reject_declared_non_kazakh"
    elif len(letters) < 40:
        decision = "uncertain_short"
    elif ratio < 0.70:
        decision = "review_non_cyrillic_or_mixed"
    elif kk < 2 or kr < 0.005:
        decision = "review_unconfirmed_kazakh"
    else:
        decision = "supported_by_locale_and_script"
    return {"decision": decision, "alphabetic": len(letters), "kk_specific": kk,
            "cyrillic_ratio": round(ratio, 6), "kk_specific_ratio": round(kr, 6)}


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Offsets into normalized block text. Protect decimals, dates, list numbers, initials.

    This deterministic rule-based segmenter is intentionally conservative and needs
    native-speaker boundary QA. It does not claim universal Kazakh accuracy.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c not in ".!?\u2026":
            i += 1
            continue
        end = i + 1
        while end < len(text) and text[end] in ".!?\u2026\"\u00bb')\u201d":
            end += 1
        if end < len(text) and not text[end].isspace():
            i += 1
            continue
        if c == ".":
            prefix = text[start:i].strip()
            token_match = re.search(r"([\w.]+)$", text[:i], re.UNICODE)
            token = token_match.group(1) if token_match else ""
            if (re.fullmatch(r"\d+(?:-\d+)?", prefix) or token.casefold() in ABBREVIATIONS
                    or (len(token) == 1 and token.isupper())):
                i += 1
                continue
        left = start
        while left < end and text[left].isspace():
            left += 1
        right = end
        while right > left and text[right - 1].isspace():
            right -= 1
        if right > left:
            spans.append((left, right))
        start = end
        i = end
    left = start
    while left < len(text) and text[left].isspace():
        left += 1
    if left < len(text):
        spans.append((left, len(text)))
    return spans
