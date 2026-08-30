"""Unit tests for rag.py using a deterministic fake embedder.

The real embedder (fastembed) downloads a 90 MB model on first use — we don't
want that in unit tests. `_FakeEmbedder` gives every distinct token bucket a
distinct 4-D basis vector, so semantic search behaves predictably.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from pipeline_watch.rag import Chunk, RunbookIndex, _split_file

# ------------------------------------------------------------- chunking --


def test_split_file_produces_one_chunk_per_h2(tmp_path: Path):
    md = tmp_path / "sample.md"
    md.write_text(
        "# Sample\n\nintro\n\n## Alpha\n\nalpha body\n\n## Beta\n\nbeta body\n",
        encoding="utf-8",
    )
    chunks = _split_file(md)
    assert len(chunks) == 2
    assert chunks[0].heading == "Alpha"
    assert chunks[0].title == "Sample"
    assert "alpha body" in chunks[0].body
    assert chunks[1].heading == "Beta"


def test_split_file_no_h2_produces_no_chunks(tmp_path: Path):
    md = tmp_path / "x.md"
    md.write_text("# Only H1\n\nsome text\n", encoding="utf-8")
    assert _split_file(md) == []


# ---------------------------------------------------------- fake index --


class _FakeEmbedder:
    """Deterministic 8-D embedder: hash → index → one-hot-ish vector."""

    def embed(self, texts: list[str]):
        for t in texts:
            h = int(hashlib.md5(t.encode()).hexdigest(), 16)
            vec = np.zeros(8, dtype=np.float32)
            vec[h % 8] = 1.0
            # Add a tiny nudge from another dim so identical hashes still differ
            vec[(h >> 8) % 8] += 0.5
            yield vec


@pytest.fixture
def fake_runbook_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runbook"
    d.mkdir()
    (d / "a.md").write_text(
        "# A\n## Alpha rule\n\nprefer ruff format for lint.\n",
        encoding="utf-8",
    )
    (d / "b.md").write_text(
        "# B\n## Beta rule\n\nnever autofix test failures.\n",
        encoding="utf-8",
    )
    return d


def _make_index(runbook_dir: Path, tmp_path: Path) -> RunbookIndex:
    index_path = tmp_path / ".cache" / "runbook.faiss"
    ix = RunbookIndex(runbook_dir=runbook_dir, index_path=index_path)
    # Inject fake embedder before build.
    ix._embedder = _FakeEmbedder()  # type: ignore[assignment]
    return ix


def test_build_and_persist_index(fake_runbook_dir: Path, tmp_path: Path):
    ix = _make_index(fake_runbook_dir, tmp_path).load_or_build()
    assert ix.index_path.exists(), "index file not written"
    assert ix.chunks_path.exists(), "chunks sidecar not written"
    assert len(ix._chunks) == 2


def test_load_uses_cached_index(fake_runbook_dir: Path, tmp_path: Path):
    ix1 = _make_index(fake_runbook_dir, tmp_path).load_or_build()
    mtime_after_build = ix1.index_path.stat().st_mtime

    # New index instance points at the same paths.
    ix2 = RunbookIndex(
        runbook_dir=fake_runbook_dir, index_path=ix1.index_path
    )
    ix2._embedder = _FakeEmbedder()  # type: ignore[assignment]
    ix2.load_or_build()

    assert ix2.index_path.stat().st_mtime == mtime_after_build, "index was rebuilt"
    assert [c.heading for c in ix2._chunks] == ["Alpha rule", "Beta rule"]


def test_rebuild_when_runbook_changes(fake_runbook_dir: Path, tmp_path: Path):
    ix = _make_index(fake_runbook_dir, tmp_path).load_or_build()
    original_mtime = ix.index_path.stat().st_mtime

    # Touch a runbook file to make it newer.
    import os
    import time
    time.sleep(0.05)
    new_time = time.time()
    os.utime(fake_runbook_dir / "a.md", (new_time, new_time))

    ix2 = RunbookIndex(runbook_dir=fake_runbook_dir, index_path=ix.index_path)
    ix2._embedder = _FakeEmbedder()  # type: ignore[assignment]
    ix2.load_or_build()

    assert ix2.index_path.stat().st_mtime > original_mtime, "index should rebuild"


def test_query_returns_chunks(fake_runbook_dir: Path, tmp_path: Path):
    ix = _make_index(fake_runbook_dir, tmp_path).load_or_build()
    results: list[Chunk] = ix.query("prefer ruff format for lint.", k=2)
    assert results, "query returned nothing"
    assert all(isinstance(c, Chunk) for c in results)
