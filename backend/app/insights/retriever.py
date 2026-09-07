"""Tiny BM25-backed retriever over the markdown knowledge base.

Chunks are paragraphs with their enclosing headings; retrieval is fully local
(no embeddings, no API cost). Swap for an embedding retriever later behind the
same interface if needed.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge_base"

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


@dataclass
class Chunk:
    doc: str
    heading: str
    text: str


def load_chunks() -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(KB_DIR.glob("*.md")):
        heading = path.stem
        para: list[str] = []

        def flush():
            text = " ".join(para).strip()
            if len(text) >= 60:
                chunks.append(Chunk(doc=path.stem, heading=heading, text=text))
            para.clear()

        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                flush()
                heading = stripped.lstrip("#").strip()
            elif not stripped:
                flush()
            else:
                para.append(stripped)
        flush()
    return chunks


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.n = len(docs)
        self.avgdl = (sum(len(d) for d in docs) / self.n) if self.n else 1.0
        self.df: Counter[str] = Counter()
        for doc in docs:
            self.df.update(set(doc))

    def scores(self, query: list[str]) -> list[float]:
        out = []
        for doc in self.docs:
            tf = Counter(doc)
            dl = len(doc)
            score = 0.0
            for term in query:
                if term not in tf:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                score += idf * (tf[term] * (self.k1 + 1)) / (
                    tf[term] + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                )
            out.append(score)
        return out


class Retriever:
    def __init__(self) -> None:
        self.chunks = load_chunks()
        self.bm25 = BM25([tokenize(c.text) for c in self.chunks])

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        scores = self.bm25.scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                continue
            chunk = self.chunks[i]
            results.append(
                {
                    "doc": chunk.doc,
                    "heading": chunk.heading,
                    "snippet": chunk.text[:400],
                    "score": round(scores[i], 3),
                }
            )
        return results


@lru_cache
def get_retriever() -> Retriever:
    return Retriever()
