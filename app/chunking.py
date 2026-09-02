from pathlib import Path

from pydantic import BaseModel


class Chunk(BaseModel):
    id: str
    source: str
    text: str


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIRECTORY = PROJECT_ROOT / "data"


def split_text(text: str, chunk_size: int = 220, overlap: int = 40) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()
    chunks = []
    current_words = []
    current_length = 0

    for word in words:
        separator_length = 1 if current_words else 0
        next_length = current_length + separator_length + len(word)

        if current_words and next_length > chunk_size:
            chunks.append(" ".join(current_words))

            overlap_words = []
            overlap_length = 0

            for previous_word in reversed(current_words):
                word_length = len(previous_word) + (1 if overlap_words else 0)

                if overlap_length + word_length > overlap:
                    break

                overlap_words.insert(0, previous_word)
                overlap_length += word_length

            current_words = overlap_words
            current_length = len(" ".join(current_words))

        if current_words:
            current_length += 1

        current_words.append(word)
        current_length += len(word)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def load_chunks() -> list[Chunk]:
    result = []

    for file_path in DATA_DIRECTORY.glob("*.md"):
        text = file_path.read_text(encoding="utf-8")

        for index, chunk_text in enumerate(split_text(text)):
            result.append(
                Chunk(
                    id=f"{file_path.stem}-{index}",
                    source=file_path.name,
                    text=chunk_text,
                )
            )

    return result