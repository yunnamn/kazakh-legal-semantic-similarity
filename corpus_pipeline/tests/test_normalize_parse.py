import pytest
from kazlegal_corpus.errors import CorpusError
from kazlegal_corpus.normalize import guard_text, language_signals, normalize, sentence_spans
from kazlegal_corpus.parse import parse_html, structure_blocks


def test_nfc_whitespace_and_numeric_meaning():
    text, changes = normalize("\ufeffA\u0301\u00a0  12.5\tNOT\u200b 13\u00b2")
    assert text == "\u00c1 12.5 NOT 13\u00b2"
    assert changes["nfc_changed"] == 1
    assert changes["removed_bom"] == 1
    assert "13\u00b2" in text  # NFC, not compatibility normalization


def test_guard_is_not_training_normalization():
    assert guard_text("Not 12!") == "not 12"
    assert normalize("Not 12!")[0] == "Not 12!"
    assert guard_text("12") != guard_text("13")


def test_sentence_offsets_dates_enumeration_and_abbreviation():
    text = "1. TEST_ONLY 01.01.2024 \u0436. value 3.14 remains. TEST_ONLY next sentence!"
    spans = sentence_spans(text)
    assert [text[a:b] for a, b in spans] == ["1. TEST_ONLY 01.01.2024 \u0436. value 3.14 remains.", "TEST_ONLY next sentence!"]


def test_initials_are_not_broken():
    text = "TEST_ONLY A. B. Example appears. TEST_ONLY another clause."
    assert len(sentence_spans(text)) == 2


def test_empty_segmenter():
    assert sentence_spans("") == []


def test_language_heuristic_is_not_keyword_filter():
    text = ("\u04d8\u043b\u0435\u043c \u049b\u0430\u0437\u0430\u049b \u0442\u0456\u043b\u0456 " * 10)
    assert language_signals(text, declared="kk")["decision"] == "supported_by_locale_and_script"
    assert language_signals(text, declared="ru")["decision"] == "reject_declared_non_kazakh"
    assert language_signals("TEST_ONLY", declared="kk")["decision"] == "uncertain_short"


def test_html_structure_inline_reference_notes_and_tables():
    html = ('<html><h1>TEST_ONLY title</h1><nav>outside navigation</nav><div id="text">'
            '<h2>1-\u0431\u0430\u043f</h2><p>TEST_ONLY See <a href="#ref">12</a> and not 13.</p>'
            '<p>\u0415\u0441\u043a\u0435\u0440\u0442\u0443. TEST_ONLY amendment note.</p>'
            '<table><tr><td>TEST_ONLY cell one</td><td>TEST_ONLY cell two</td></tr></table>'
            '<script>BAD_SCRIPT</script></div></html>').encode()
    blocks, metadata = parse_html(html)
    result = structure_blocks(blocks)
    assert result[1]["text"] == "TEST_ONLY See 12 and not 13."
    assert result[2]["kind"] == "editorial_note"
    assert result[2]["article"] == "1"
    assert result[3]["table_cells"] == ["TEST_ONLY cell one", "TEST_ONLY cell two"]
    assert not any("BAD_SCRIPT" in x["text"] or "outside navigation" in x["text"] for x in result)
    assert metadata["removed_elements"][0]["tag"] == "script"


@pytest.mark.parametrize("html,selector", [
    (b"<html><body>TEST_ONLY</body></html>", None),
    (b'<div id="text">TEST_ONLY</div><div class="doc-text">TEST_ONLY two</div>', None),
    (b"<body>TEST_ONLY</body>", "body"),
    (b'<div id="text">Checking your browser...</div>', None),
])
def test_fail_closed_html(html, selector):
    with pytest.raises(CorpusError):
        parse_html(html, selector=selector)


def test_article_occurrences_not_unique_numbers():
    blocks = structure_blocks([{"text": "1-\u0431\u0430\u043f", "kind": "heading"},
                               {"text": "TEST_ONLY text", "kind": "paragraph"},
                               {"text": "1-\u0431\u0430\u043f", "kind": "heading"},
                               {"text": "TEST_ONLY text", "kind": "paragraph"}])
    assert blocks[1]["article"] == blocks[3]["article"] == "1"
    assert blocks[1]["article_occurrence"] != blocks[3]["article_occurrence"]
