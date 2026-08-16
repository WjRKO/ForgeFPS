"""Fake minimale di una collezione motor: quel tanto che serve ai test unit.

Supporta i soli operatori usati dal codice sotto test: uguaglianza, `$ne`, `$in`.
La proiezione viene ignorata (i test guardano il risultato, non i campi trasferiti).
"""
from __future__ import annotations


def _matches(doc: dict, query: dict) -> bool:
    for key, cond in (query or {}).items():
        value = doc.get(key)
        if isinstance(cond, dict):
            if "$ne" in cond and value == cond["$ne"]:
                return False
            if "$in" in cond and value not in cond["$in"]:
                return False
        elif value != cond:
            return False
    return True


class FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = docs

    def limit(self, n: int) -> "FakeCursor":
        return FakeCursor(self._docs[:n])

    def sort(self, *_args, **_kwargs) -> "FakeCursor":
        return self

    async def to_list(self, n: int | None = None) -> list[dict]:
        return self._docs if n is None else self._docs[:n]

    def __aiter__(self):
        return self._agen()

    async def _agen(self):
        for d in self._docs:
            yield d


class FakeCollection:
    def __init__(self, docs: list[dict] | None = None):
        self.docs = list(docs or [])

    def find(self, query: dict | None = None, projection: dict | None = None) -> FakeCursor:
        return FakeCursor([d for d in self.docs if _matches(d, query or {})])

    async def find_one(self, query: dict | None = None, projection: dict | None = None, **_kw):
        for d in self.docs:
            if _matches(d, query or {}):
                return d
        return None


class FakeDb:
    """`db.qualsiasi_nome` restituisce una collezione vuota se non pre-popolata."""

    def __init__(self, **collections: list[dict]):
        self._cols = {name: FakeCollection(docs) for name, docs in collections.items()}

    def __getattr__(self, name: str) -> FakeCollection:
        return self._cols.setdefault(name, FakeCollection())
