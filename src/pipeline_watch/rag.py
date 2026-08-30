"""Runbook RAG — chunked semantic search over docs/runbook/*.md.

Chunking
--------

Each markdown file is split at every `## ` heading. The chunk body is the
heading text plus everything up to (but not including) the next `## ` or
end-of-file. `# ` (H1) is treated as the file title and prepended to every
chunk from that file so short chunks retain topical context in embeddings.

Retrieval
---------

- Embeddings: `fastembed` default model (BAAI/bge-small-en-v1.5, 384 dims).
- Index: FAISS `IndexFlatIP` (cosine similarity via L2-normalized vectors).
- Persistence: `<index>.faiss` + a sidecar `<index>.chunks.json` keeping the
  chunk metadata in the exact order of the FAISS vectors.

Rebuild
-------

The first `RunbookIndex.load_or_build()` call scans `runbook_dir`; if any
file's mtime is newer than the index file, the index is rebuilt. This
matches the CI dogfood workflow where the runbook can evolve without a
manual reindex step.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

_DEFAULT_RUNBOOK_DIR = Path(__file__).resolve().parents[2] / "docs" / "runbook"
_DEFAULT_INDEX_PATH = Path(__file__).resolve().parents[2] / ".cache" / "runbook.faiss"
_DEFAULT_EMBED_MODEL = "BAAI/bge-small-en-v1.5"

_HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass
class Chunk:
    source: str  # file name, e.g. "lint.md"
    title: str  # H1 of the source file
    heading: str  # H2 that introduces this chunk
    body: str  # full text of the chunk (heading + content)


def _split_file(md_path: Path) -> list[Chunk]:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = lines[0].lstrip("#").strip() if lines and lines[0].startswith("# ") else md_path.stem

    chunks: list[Chunk] = []
    matches = list(_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        chunks.append(
            Chunk(source=md_path.name, title=title, heading=m.group(1).strip(), body=body)
        )
    return chunks


class RunbookIndex:
    """Persisted FAISS index over runbook chunks."""

    def __init__(
        self,
        runbook_dir: Path = _DEFAULT_RUNBOOK_DIR,
        index_path: Path = _DEFAULT_INDEX_PATH,
        embed_model: str = _DEFAULT_EMBED_MODEL,
    ) -> None:
        self.runbook_dir = runbook_dir
        self.index_path = index_path
        self.chunks_path = index_path.with_suffix(".chunks.json")
        self.embed_model = embed_model
        self._index: faiss.IndexFlatIP | None = None
        self._chunks: list[Chunk] = []
        self._embedder: TextEmbedding | None = None

    # -------------------------------------------------------- lifecycle --

    def load_or_build(self) -> RunbookIndex:
        if self._is_index_stale():
            self._build()
        else:
            self._load()
        return self

    def _is_index_stale(self) -> bool:
        if not self.index_path.exists() or not self.chunks_path.exists():
            return True
        index_mtime = self.index_path.stat().st_mtime
        return any(
            md.stat().st_mtime > index_mtime for md in self.runbook_dir.glob("*.md")
        )

    def _load(self) -> None:
        self._index = faiss.read_index(str(self.index_path))
        raw = json.loads(self.chunks_path.read_text(encoding="utf-8"))
        self._chunks = [Chunk(**c) for c in raw]

    def _build(self) -> None:
        chunks: list[Chunk] = []
        for md in sorted(self.runbook_dir.glob("*.md")):
            chunks.extend(_split_file(md))
        if not chunks:
            raise RuntimeError(f"no runbook chunks found in {self.runbook_dir}")

        vectors = self._embed([f"{c.title} :: {c.body}" for c in chunks])
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(self.index_path))
        self.chunks_path.write_text(
            json.dumps([asdict(c) for c in chunks], indent=2), encoding="utf-8"
        )
        self._index = index
        self._chunks = chunks

    # ----------------------------------------------------------- query --

    def query(self, text: str, k: int = 3) -> list[Chunk]:
        if self._index is None or not self._chunks:
            self.load_or_build()
        assert self._index is not None
        vector = self._embed([text])
        scores, ids = self._index.search(vector, min(k, len(self._chunks)))
        return [self._chunks[i] for i in ids[0] if i != -1]

    # -------------------------------------------------------- internal --

    def _embed(self, texts: list[str]) -> np.ndarray:
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=self.embed_model)
        vectors = np.array(list(self._embedder.embed(texts)), dtype=np.float32)
        # L2-normalize so IndexFlatIP == cosine similarity.
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


_singleton: RunbookIndex | None = None


def get_index() -> RunbookIndex:
    """Process-wide cached index. First call takes ~10s (model download + build)."""

    global _singleton
    if _singleton is None:
        _singleton = RunbookIndex().load_or_build()
    return _singleton


def reset_singleton() -> None:
    """Used by tests to force a fresh index build."""

    global _singleton
    _singleton = None
