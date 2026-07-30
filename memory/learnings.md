
## 2026-07-30 — Validazione PS agent: falso positivo
- /api/agent/script SENZA ?t=<token> ritorna una riga di errore (o vuoto): il parse pwsh su quel file da' sempre "OK" -> FALSO POSITIVO.
- Procedura corretta: login -> GET /api/agent/token -> GET /api/agent/script?t=$TK -> verificare wc -l > 5000 -> pwsh ParseFile.
- Bug reale trovato dall'utente: un search_replace aveva rimosso un newline in Invoke-LabRun unendo due statement ('$arr = ...ToArray()  $sorted = ...') -> ParserError su Windows PS 5.1. Mai fare edit "no-op" che toccano solo il trailing newline.
