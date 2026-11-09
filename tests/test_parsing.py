import pytest
from pypdf import PdfWriter

from clauseproof.parsing import ParsingError, normalize_text, read_document, validate_text


def test_reads_txt(tmp_path, sample_dpa):
    f = tmp_path / "dpa.txt"
    f.write_text(sample_dpa, encoding="utf-8")
    assert "DATA PROCESSING AGREEMENT" in read_document(f)


@pytest.mark.parametrize("content", ["", "   \n\t  "])
def test_empty_rejected(tmp_path, content):
    f = tmp_path / "e.txt"
    f.write_text(content)
    with pytest.raises(ParsingError, match="empty"):
        read_document(f)


def test_short_text_rejected(tmp_path):
    f = tmp_path / "s.txt"
    f.write_text("x" * 199)
    with pytest.raises(ParsingError, match="Text too short for DPA analysis"):
        read_document(f)


def test_exactly_min_length_accepted():
    assert validate_text("x" * 200)


def test_missing_file():
    with pytest.raises(ParsingError, match="not found"):
        read_document("/nonexistent/file.txt")


def test_unsupported_extension(tmp_path):
    f = tmp_path / "a.docx"
    f.write_text("x")
    with pytest.raises(ParsingError, match="Unsupported"):
        read_document(f)


def test_non_utf8_txt(tmp_path):
    f = tmp_path / "b.txt"
    f.write_bytes(b"\xff\xfe\x00bad" * 100)
    with pytest.raises(ParsingError, match="UTF-8"):
        read_document(f)


def test_corrupted_pdf(tmp_path):
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"not a pdf at all")
    with pytest.raises(ParsingError, match="corrupted|unreadable"):
        read_document(f)


def test_scanned_style_pdf_without_text(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    f = tmp_path / "blank.pdf"
    with f.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ParsingError, match="OCR is not supported"):
        read_document(f)


def test_encrypted_pdf(tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("secret")
    f = tmp_path / "enc.pdf"
    with f.open("wb") as fh:
        writer.write(fh)
    with pytest.raises(ParsingError, match="encrypted"):
        read_document(f)


def test_normalize_text_whitespace():
    assert normalize_text("a \t b\r\n\r\n\r\n\r\nc") == "a b\n\nc"
