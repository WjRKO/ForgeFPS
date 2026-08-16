# tests_unit — suite veloce, senza dipendenze esterne

Diversa da `backend/tests/`, che sono test di **integrazione** contro un backend
vivo + MongoDB (vanno lanciati in seriale, vedi `pytest.ini`).

Qui dentro solo logica pura o con i collaboratori sostituiti da fake: nessuna
rete, nessun database, nessun processo uvicorn. Obiettivo: girare su ogni commit
in pochi secondi.

```
cd backend
./.venv/Scripts/python.exe -m pytest tests_unit -q -p no:cacheprovider -c /dev/null
```

(`-c /dev/null` evita di ereditare gli `addopts` di `pytest.ini`, che imporrebbero xdist.)
