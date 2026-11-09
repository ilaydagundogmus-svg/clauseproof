from clauseproof.segmenter import format_clauses, segment


def test_segments_by_numbering(sample_dpa):
    clauses = segment(sample_dpa)
    refs = [c.ref for c in clauses]
    assert refs[0] == "preamble"
    assert {"1", "1.1", "1.2", "2", "2.1", "4.1"} <= set(refs)


def test_spans_point_into_original_text(sample_dpa):
    for c in segment(sample_dpa):
        assert c.text in sample_dpa[c.start : c.end]


def test_article_headings():
    text = "Article 3 Security\nThe processor secures data.\nArticle 4 Audit\nAudits allowed."
    assert [c.ref for c in segment(text)] == ["Article 3", "Article 4"]


def test_no_numbering_falls_back_to_paragraphs():
    clauses = segment("First paragraph here.\n\nSecond paragraph here.")
    assert len(clauses) == 2
    assert clauses[0].ref == "para 1"


def test_covers_all_content(sample_dpa):
    joined = " ".join(c.text for c in segment(sample_dpa))
    for fragment in ("hosting Services", "delete or return"):
        assert fragment in joined


def test_format_tags_refs():
    out = format_clauses(segment("1. One\nText.\n2. Two\nMore."))
    assert "[1]" in out and "[2]" in out
