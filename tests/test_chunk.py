from ingest.reader import Block, Chapter, read_library
from rag.chunk import chunk_chapter, tokens
from tests.conftest import SAMPLES


def synthetic_chapter(paragraphs: int = 60, heading_every: int = 7) -> Chapter:
    """Generated filler text: no real book content."""
    blocks, i = [], 0
    for p in range(paragraphs):
        if p % heading_every == 0:
            blocks.append(Block("h2", f"Section {p // heading_every}", i, page=p // 4 + 1))
            i += 1
        words = " ".join(f"word{(p * 31 + w) % 97}" for w in range(60 + (p * 13) % 90))
        blocks.append(Block("p", f"Paragraph {p}. {words}.", i, page=p // 4 + 1))
        i += 1
    return Chapter("synth-book", "Synthetic Book", "Test Author", "001-synth", "Synthetic", blocks)


def test_book_chunks_are_400_to_800_tokens_except_last():
    chunks = chunk_chapter(synthetic_chapter())
    assert len(chunks) > 3
    for c in chunks[:-1]:
        assert 400 <= c.n_tokens <= 800, (c.id, c.n_tokens)
    assert chunks[-1].n_tokens <= 800


def test_heading_never_ends_a_chunk():
    for c in chunk_chapter(synthetic_chapter()):
        assert not c.text.splitlines()[-1].startswith("## "), c.id


def test_heading_starts_a_new_chunk_once_the_chunk_has_400_tokens():
    for c in chunk_chapter(synthetic_chapter(paragraphs=80, heading_every=6)):
        text = c.text
        pos = text.find("\n\n## ")
        while pos != -1:
            assert tokens(text[:pos]) < 400, c.id      # a heading only joins a chunk that is still small
            pos = text.find("\n\n## ", pos + 1)


def test_ids_are_unique_and_stable():
    a = [c.id for c in chunk_chapter(synthetic_chapter())]
    b = [c.id for c in chunk_chapter(synthetic_chapter())]
    assert a == b
    assert len(set(a)) == len(a)
    assert a[0].startswith("synth-book:001-synth:0-")


def test_metadata_fields():
    c = chunk_chapter(synthetic_chapter())[0]
    m = c.metadata()
    for key in ("book_id", "book_title", "author", "chapter_id", "chapter_title",
                "page_start", "page_end", "block_start", "block_end", "kind"):
        assert key in m
    assert m["author"] == "Test Author" and m["page_start"] == 1
    assert all(v is not None for v in m.values())          # Chroma rejects None


def test_oversized_block_is_split_and_ids_stay_unique():
    huge = " ".join(f"Sentence number {i} is filler text for the test." for i in range(400))
    ch = Chapter("b", "B", "", "c", "C", [Block("p", huge, 0, page=1)])
    chunks = chunk_chapter(ch)
    assert len(chunks) > 1
    assert all(c.n_tokens <= 800 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_sample_library_reads_and_cleans_markup():
    chapters = list(read_library(SAMPLES))
    assert {c.chapter_id for c in chapters} == {"001-patience", "002-gratitude"}
    assert all("*" not in b.text for c in chapters for b in c.blocks)
    assert chapters[0].author == "Noor sample text"


def test_tokens_estimate():
    assert tokens("abcd" * 100) == 100
