"""Fake minimale di una collezione motor: quel tanto che serve ai test unit.

Supporta i soli operatori usati dal codice sotto test: uguaglianza, `$ne`, `$in`
e i confronti d'ordine (`$gte`, `$gt`, `$lte`, `$lt`), che servono alle finestre
temporali - per esempio il freno sugli invii di reset password.
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
            for op, ok in (("$gte", lambda a, b: a >= b), ("$gt", lambda a, b: a > b),
                           ("$lte", lambda a, b: a <= b), ("$lt", lambda a, b: a < b)):
                if op in cond:
                    if value is None:
                        return False
                    try:
                        if not ok(value, cond[op]):
                            return False
                    except TypeError:
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

    async def count_documents(self, query: dict | None = None) -> int:
        return sum(1 for d in self.docs if _matches(d, query or {}))

    async def insert_one(self, doc: dict):
        # Il documento viene tenuto per riferimento: i test che modificano un
        # campo dopo l'inserimento (per esempio invecchiare un `created_at`)
        # devono vedere l'effetto senza dover riscrivere la collezione.
        self.docs.append(doc)
        return type("Esito", (), {"inserted_id": doc.get("_id")})()


class FakeDb:
    """`db.qualsiasi_nome` restituisce una collezione vuota se non pre-popolata."""

    def __init__(self, **collections: list[dict]):
        self._cols = {name: FakeCollection(docs) for name, docs in collections.items()}

    def __getattr__(self, name: str) -> FakeCollection:
        return self._cols.setdefault(name, FakeCollection())
