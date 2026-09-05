import pytest
from app.chunking import load_chunks, split_text

def test_short_text_stays_in_one_chunk() -> None:
    assert split_text("One short document.") == ["One short document."]

def test_chunks_keep_whole_words_and_overlap() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"

    chunks = split_text(text, chunk_size=30, overlap=12)

    assert len(chunks) > 1

    original_words = set(text.split())
    chunk_words = {
        word
        for chunk in chunks
        for word in chunk.split()
    }

    assert chunk_words <= original_words
    assert set(chunks[0].split()) & set(chunks[1].split())

def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        split_text("text", chunk_size=10, overlap=10)

def test_loaded_chunks_keep_source_metadata() -> None:
    chunks = load_chunks()

    assert chunks
    assert {
        "remote_work.md",
        "incident_response.md",
        "support_escalation.md",
    } <= {
        chunk.source for chunk in chunks
    }
