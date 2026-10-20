from ingest.sources import HADITH, citation, hadith_chapters, quran_chapters
from rag.chunk import chunk_chapter
from tests.conftest import fixture


def test_quran_converts_to_surah_chapters_with_ayah_refs():
    chapters = list(quran_chapters(fixture("quran-info.json"), fixture("quran-edition.json")))
    assert [c.chapter_id for c in chapters] == ["001", "002"]
    assert chapters[0].chapter_title.startswith("Surah 1 The Sample")
    assert [b.ref for b in chapters[0].blocks] == ["1:1", "1:2", "1:3"]
    chunks = chunk_chapter(chapters[0])
    assert [c.id for c in chunks] == ["quran:1:1-3"]
    assert "(1:2)" in chunks[0].text
    assert citation(chunks[0].metadata()) == "Quran 1:1-3"
    assert chunk_chapter(chapters[1])[0].id == "quran:2:1"


def test_hadith_one_chunk_per_hadith_with_grades():
    HADITH.setdefault("sample", ("eng-sample", "Sample Collection", "Test Compiler"))
    chapters = list(hadith_chapters("sample", fixture("hadith-sample.json")))
    assert [c.chapter_title for c in chapters] == ["Book of Testing", "Book of Samples"]  # empty section 0 skipped
    chunks = [c for ch in chapters for c in chunk_chapter(ch)]
    assert [c.id for c in chunks] == ["sample:1", "sample:2", "sample:3"]
    assert chunks[0].grades == "Test Grader: Sahih"
    assert chunks[1].grades == ""
    cite = citation(chunks[2].metadata())
    assert cite.startswith("Sample Collection 3 (Book of Samples)") and "Daif" in cite
