"""I due motori si passano lo stesso backup e lo stesso journal.

Non e' un test di pytest e non gira in CI: importa forgefps_agent, che parla col
registro di Windows e vuole un token. Si lancia a mano su Windows:

    python backend/tests/prova_storage_condiviso.py

Usa un %APPDATA% finto in una cartella temporanea: non tocca i dati veri.
Le proprieta' che verifica sono le stesse pinnate da
tests_unit/test_agent_storage_condiviso.py, ma qui vengono eseguite davvero.
"""
import io, json, os, sys, tempfile, shutil

AB = r"C:\Users\tocci\OneDrive\Desktop\Claude\ForgeFPS\agent-build"
sys.path.insert(0, AB)

# APPDATA finto: non tocco quello vero dell'utente
finto = tempfile.mkdtemp(prefix="ff_prova_")
os.environ["APPDATA"] = finto
sys.argv = ["forgefps_agent.py"]
os.environ["FORGEFPS_TOKEN"] = "token-di-prova"   # altrimenti l'import chiede il token a mano
import forgefps_agent as A

print("FF_HOME       :", A._FF_HOME.replace(finto, "<APPDATA>"))
print("BACKUP_FILE   :", A.BACKUP_FILE.replace(finto, "<APPDATA>"))
print("JOURNAL_FILE  :", A.JOURNAL_FILE.replace(finto, "<APPDATA>"))
assert A.BACKUP_FILE.endswith(os.path.join("FrameForge", "backup.json"))
assert A.JOURNAL_FILE.endswith(os.path.join("FrameForge", "journal.jsonl"))

# 1. un backup scritto dall'agent PowerShell, con i suoi metadati
psbk = {
    "HKCU:\Control Panel\Mouse::MouseSpeed": "String|1",
    "svc::SysMain": "Automatic",
    "__tweak_keys__": {"mouse": ["HKCU:\Control Panel\Mouse::MouseSpeed"]},
    "__applied_at__": {"mouse": "2026-08-22T14:32:00+02:00"},
}
io.open(A.BACKUP_FILE, "w", encoding="utf-8").write(json.dumps(psbk))

# 2. un backup vecchio accanto all'exe, di quando l'exe scriveva li'
vecchio = A._OLD_BACKUPS[0]
io.open(vecchio, "w", encoding="utf-8").write(json.dumps({
    "HKLM:\SOFTWARE\X::Vecchia": "DWord|7"}))

bk = A._load_backup()
print("\nletto dal motore Python:", sorted(k for k in bk))
assert "__tweak_keys__" in bk, "metadati dell'altro motore persi in lettura"
assert "HKLM:\SOFTWARE\X::Vecchia" in bk, "backup vecchio abbandonato"

# 3. il Python aggiunge una sua chiave e salva
bk["HKCU:\Software\Y::Nuova"] = "DWord|1"
A._save_backup(bk)
riletto = json.load(io.open(A.BACKUP_FILE, encoding="utf-8"))
print("dopo il salvataggio :", sorted(riletto))
assert riletto.get("__tweak_keys__") == psbk["__tweak_keys__"], "metadati persi in scrittura"
assert riletto.get("__applied_at__") == psbk["__applied_at__"]
assert not os.path.exists(vecchio), "il file vecchio doveva sparire dopo il salvataggio"

# 4. il journal condiviso
A._journal("apply", "tcp-nagle-off", "Nagle OFF", "latency", True)
A._journal("apply", "dns-cloudflare", "DNS Cloudflare", "network", False, "accesso negato")
righe = [json.loads(r) for r in io.open(A.JOURNAL_FILE, encoding="utf-8") if r.strip()]
print("\njournal condiviso:")
for r in righe:
    print("  ", json.dumps(r, ensure_ascii=False))
assert all(r["via"] == "cli" for r in righe)
assert righe[0]["ok"] is True and righe[1]["ok"] is False
assert righe[0]["session"] == righe[1]["session"]

# 5. il ripristino salta i metadati invece di trattarli come chiavi
comandi = []
A.run = lambda c: comandi.append(c)
A.ps = lambda c: comandi.append("ps: " + c)
A.restore_tweaks()
junk = [c for c in comandi if "__tweak_keys__" in c or "__applied_at__" in c or '"tweaks"' in c]
print("\ncomandi di ripristino:", len(comandi), "| su metadati:", len(junk))
for c in comandi:
    print("   ", c[:96])
assert not junk, "il ripristino ha trattato i metadati come chiavi di registro"
assert not os.path.exists(A.BACKUP_FILE)
rev = [json.loads(r) for r in io.open(A.JOURNAL_FILE, encoding="utf-8") if r.strip()][2:]
print("\nannullamenti registrati:", [r["tweak"] for r in rev])
assert any(r["event"] == "revert" and r["tweak"] == "mouse" for r in rev), \
    "il ripristino non ha registrato il tweak dell'altro motore"

shutil.rmtree(finto, ignore_errors=True)
print("\nTUTTO OK")
