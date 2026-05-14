"""
Unit tests for RAG helpers in utils.rag.

Covers text extraction and file-type detection; ingest/retrieve are integration-heavy
and can be covered later with mocked embeddings.
"""

import pytest

from utils.rag import (
    _detect_file_type,
    _extract_text_from_txt,
    _extract_text,
    _chunk_text,
)


class TestDetectFileType:
    """_detect_file_type returns lowercased extension without leading dot."""

    def test_txt(self):
        assert _detect_file_type("doc.txt") == "txt"
        assert _detect_file_type("DOC.TXT") == "txt"

    def test_pdf(self):
        assert _detect_file_type("file.pdf") == "pdf"

    def test_docx(self):
        assert _detect_file_type("report.docx") == "docx"

    def test_md(self):
        assert _detect_file_type("readme.md") == "md"


class TestExtractTextFromTxt:
    """_extract_text_from_txt decodes bytes to str."""

    def test_utf8(self):
        assert _extract_text_from_txt(b"Hello world") == "Hello world"

    def test_fallback_encoding(self):
        # latin-1 fallback for non-utf8
        result = _extract_text_from_txt(b"\x80\x81")
        assert isinstance(result, str)
        assert len(result) == 2


class TestExtractText:
    """_extract_text dispatches by file type and returns raw_text + file_type."""

    def test_txt_extraction(self):
        out = _extract_text(b"Some content here.", "doc.txt")
        assert out["raw_text"] == "Some content here."
        assert out["file_type"] == "txt"

    def test_md_extraction(self):
        out = _extract_text(b"# Title\n\nBody.", "readme.md")
        assert out["raw_text"] == "# Title\n\nBody."
        assert out["file_type"] == "md"

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="no extractable text"):
            _extract_text(b"   \n\n  ", "empty.txt")

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            _extract_text(b"content", "file.xyz")


class TestChunkText:
    """_chunk_text returns list of dicts with text, char_start, char_end."""

    def test_chunk_splits_long_text(self):
        text = "a" * 2000
        chunks = _chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) >= 2
        for c in chunks:
            assert "text" in c and "char_start" in c and "char_end" in c
            assert c["char_end"] - c["char_start"] == len(c["text"])

    def test_short_text_single_chunk(self):
        chunks = _chunk_text("Short.", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Short."
