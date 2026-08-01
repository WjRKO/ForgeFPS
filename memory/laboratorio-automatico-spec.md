# Laboratorio Automatico delle Prestazioni — Spec di implementazione

## 1. Data model

### 1.1 Sessione di laboratorio

```json
{
  "lab_session_id": "uuid",
  "user_id": "uuid",
  "hardware_profile_id": "uuid",
  "game_id": "warzone",
  "risk_level": "safe | medium | expert | hardware",
  "status": "snapshot | baseline | testing | validating | completed | aborted",
  "current_step": 3,
  "total_candidate_tweaks": 12,
  "created_at": "...",
  "requires_reboot_resume": false,
  "pending_reboot_test_id": null
}
```

Lo stato deve essere persistito lato backend (non solo in memoria locale), perché la sessione può attraversare più riavvii del PC. L'agent locale, all'avvio, controlla se esiste una `lab_session_id` con `requires_reboot_resume = true` e riprende automaticamente il test in corso.

### 1.2 Registro tweak (tabella statica, versionata)

```json
{
  "tweak_id": "xmp_enable",
  "category": "hardware",
  "risk_level": "hardware",
  "requires_reboot": true,
  "reversible": "auto | manual | partial",
  "applicability_rules": {
    "requires": ["ram.xmp_capable == true", "ram.xmp_enabled == false"]
  },
  "base_priors": {
    "cpu_bound_games": 0.35,
    "gpu_bound_games": 0.10
  },
  "conflicts_with": [],
  "synergy_candidates": ["pbo_enable", "memory_context_restore"]
}
```

Ogni tweak ha regole di applicabilità (per non proporre XMP se la RAM non lo supporta) e prior di probabilità di miglioramento per categoria di gioco/hardware — questi prior alimentano il motore di selezione (punto 3).

### 1.3 Risultato singolo test

```json
{
  "test_id": "uuid",
  "lab_session_id": "uuid",
  "tweak_id": "xmp_enable",
  "runs": [
    {"fps_avg": 212, "fps_p1": 178, "fps_p01": 145, "frametime_var": 1.8, "cpu_pct": 62, "gpu_pct": 97, "vram_mb": 8100, "temp_gpu": 71, "power_w": 285},
    { "...run2..." },
    { "...run3..." }
  ],
  "baseline_ref_test_id": "uuid",
  "delta": {"fps_avg_pct": 8.1, "fps_p1_pct": 6.4, "frametime_var_pct": -12.0},
  "significance": {"method": "welch_t_test", "p_value": 0.02, "significant": true},
  "stability_check_passed": true,
  "decision": "kept | rolled_back | pending",
  "performance_index": 8.7
}
```

## 2. Fasi del laboratorio (pipeline)

```
SNAPSHOT → BASELINE (N run) → CANDIDATE_SELECTION → TEST_LOOP → SYNERGY_PASS → VALIDATION_REAL_GAME → REPORT
```

### Fase 1 — Snapshot
- Dump completo di: registro chiavi rilevanti, driver installati+versione, servizi attivi, power plan, config GPU (clock/curve), programmi in startup, scheduler task, BIOS settings rilevabili via WMI.
- Salvato come blob versionato (`snapshot_v1`, `snapshot_v2`...) associato a `lab_session_id`. È il target per ogni rollback.
- Creare anche un restore point di sistema Windows come rete di sicurezza secondaria (non sostituisce lo snapshot mirato, ma copre l'imprevisto).

### Fase 2 — Baseline
- Eseguire **3 run** del benchmark standardizzato (non 1).
- Calcolare media + deviazione standard per ogni metrica.
- Se la deviazione standard tra i 3 run supera una soglia (es. CV > 5%), eseguire un 4° run ed eliminare l'outlier — il punto zero deve essere stabile prima di procedere.

### Fase 3 — Candidate selection (motore AI)
Pseudocodice:

```python
def select_candidates(hw_profile, game_profile, risk_level, tweak_registry):
    candidates = []
    for tweak in tweak_registry:
        if tweak.risk_level > risk_level:          # rispetta il livello scelto dall'utente
            continue
        if not applicability_rules_match(tweak, hw_profile):
            continue
        prior = estimate_prior(tweak, hw_profile, game_profile, aggregate_stats_db)
        if prior > 0.10:                            # soglia 10%
            candidates.append((tweak, prior))
    return sorted(candidates, key=lambda x: -x[1])  # testa prima i più promettenti
```

`estimate_prior` combina il prior statico del tweak (1.3) con lo storico aggregato anonimizzato di utenti con hardware simile (se disponibile), pesato più dello statico quando il campione è sufficiente (es. >30 utenti simili).

### Fase 4 — Test loop (una variabile alla volta)

```python
for tweak, prior in candidates_sorted:
    if tweak.requires_reboot:
        schedule_reboot_and_pause(lab_session_id, tweak.tweak_id)
        return  # l'agent riprende dopo il riavvio

    apply_tweak(tweak)
    runs = run_benchmark(n=3)
    result = compute_delta(runs, baseline)
    sig = significance_test(runs, baseline.runs)

    stability_ok = run_stability_check()  # stress test breve / game loop check

    if sig.significant and result.is_improvement and stability_ok:
        decision = "kept"
        update_baseline(result)          # il nuovo stato diventa il riferimento per il prossimo test
        adapt_priors(tweak, result)       # es. RAM tweak ha funzionato -> alza prior su altri tweak RAM
    else:
        decision = "rolled_back"
        rollback_to_snapshot(pre_tweak_snapshot)

    persist_test_result(tweak, runs, sig, decision)

    if auto_stop_check(recent_results):
        break
```

`adapt_priors`: se un tweak di una famiglia (es. RAM/memoria) ha avuto successo, aumenta temporaneamente il prior degli altri tweak della stessa famiglia ancora in coda (es. Memory Context Restore dopo XMP riuscito); se ha fallito, deprioritizza o salta il resto della famiglia.

### Fase 5 — Synergy pass
Non testare tutte le combinazioni. Solo tra i tweak "kept" nella fase 4 (greedy, non forza bruta):

```python
kept_tweaks = [t for t in tested if t.decision == "kept"]
for pair in combinations(kept_tweaks, 2):
    combined_result = apply_and_test(pair)
    individual_sum = pair[0].result.fps_delta + pair[1].result.fps_delta
    if combined_result.fps_delta > individual_sum * 1.15:  # soglia sinergia: +15% oltre la somma
        flag_as_synergy(pair, combined_result)
```

Se ci sono più di ~6 tweak "kept", limitare le coppie testate a quelle senza conflitto noto (`conflicts_with`) e con categoria complementare (es. hardware+software, non hardware+hardware dello stesso sottosistema).

### Fase 6 — Validazione nel gioco reale
- Applicare la configurazione finale vincente.
- Eseguire una sessione di gioco reale monitorata (non solo benchmark sintetico) di durata minima (es. 5-10 minuti) per confermare che i guadagni si riflettano in condizioni reali (networking, scene variabili).
- Se il guadagno reale è significativamente inferiore al benchmark (es. <50% del delta previsto), segnalarlo nel report come discrepanza, senza nasconderla.

### Fase 7 — Auto-stop

```python
def auto_stop_check(recent_results, window=3):
    recent = recent_results[-window:]
    total_gain_so_far = sum(r.delta.fps_avg_pct for r in all_results if r.decision == "kept")
    recent_gain = sum(r.delta.fps_avg_pct for r in recent if r.decision == "kept")
    if all(not r.significance.significant for r in recent):
        return True   # ultimi N test statisticamente non significativi
    if total_gain_so_far > 0 and recent_gain / total_gain_so_far < 0.03:
        return True   # rendimenti marginali < 3% del guadagno totale
    return False
```

## 3. Rollback

- Ogni tweak applicato genera uno snapshot puntuale pre-applicazione (diff incrementale rispetto allo snapshot di Fase 1, non un dump completo ogni volta — per performance).
- `reversible: "auto"` → rollback eseguito dall'agent senza intervento utente.
- `reversible: "manual"` → al termine del laboratorio, se il tweak non viene mantenuto, il report deve elencare esplicitamente i passi manuali richiesti (es. "rientra in BIOS e riporta XMP su Auto").
- `reversible: "partial"` → alcuni sotto-parametri sono automatici, altri no; specificare quali nel registro tweak.

## 4. Report finale (schema output)

```json
{
  "lab_session_id": "uuid",
  "total_duration_min": 42,
  "reboots_required": 2,
  "baseline": {"fps_avg": 198, "fps_p1": 165},
  "final": {"fps_avg": 226, "fps_p1": 201},
  "total_gain_pct": 14.1,
  "steps": [
    {"tweak": "XMP", "before": 198, "after": 214, "delta_pct": 8.1, "decision": "kept", "reason": "significativo (p=0.01), stabile"},
    {"tweak": "Driver Update", "before": 214, "after": 221, "delta_pct": 3.3, "decision": "kept", "reason": "significativo (p=0.03)"},
    {"tweak": "HAGS", "before": 221, "after": 220, "delta_pct": -0.5, "decision": "rolled_back", "reason": "non significativo (p=0.41)"},
    {"tweak": "Core Isolation", "before": 221, "after": 226, "delta_pct": 2.3, "decision": "kept", "reason": "significativo (p=0.02)"}
  ],
  "synergies_found": [
    {"tweaks": ["XMP", "PBO"], "combined_delta_pct": 12.4, "sum_of_individual_pct": 8.9, "synergy": true}
  ],
  "performance_index": {"prestazioni": 8, "fluidita": 9, "stabilita": 8, "consumi": -2, "voto_finale": 8.4},
  "real_game_validation": {"expected_gain_pct": 14.1, "observed_gain_pct": 11.8, "note": "leggera discrepanza, plausibile per variabilità in-game"},
  "manual_steps_required": []
}
```

## 5. Fonti dati per benchmark

### Capture frametime/FPS
- **PresentMon** (Intel, open source) — già in uso nell'agent. Standard de facto per capture frame-by-frame su Windows, dati grezzi via CSV/API da cui derivare p99, 1% low, 0.1% low, frametime variance.
- **CapFrameX** — costruito su PresentMon, utile come riferimento per le metriche derivate già standardizzate nel settore, anche se la pipeline custom resta preferibile per integrazione col referto AI.

### Telemetria hardware sincronizzata
- **HWiNFO64** — Shared Memory API per leggere in tempo reale clock GPU/CPU, temperature, power draw, VRAM; allineare via timestamp ai dati PresentMon.
- **LibreHardwareMonitor** (open source) — alternativa più leggera, libreria .NET integrabile direttamente nell'agent senza dipendenza da software esterno closed-source.

### Workload standardizzato
- **Giochi con benchmark nativo** (es. Cyberpunk 2077, Shadow of the Tomb Raider): prima scelta per il set di giochi "ufficialmente supportati", perché garantiscono un replay deterministico (stessa scena, stessa durata).
- **Giochi senza benchmark nativo** (es. Warzone, la maggior parte degli FPS competitivi): usare workload proxy standardizzata — bot match/firing range/training mode con sequenza di input scriptata (es. via AutoHotkey) per ripetibilità, oppure aumentare il numero di run (5+) e privilegiare percentili sulla media per compensare il rumore residuo. Il report deve segnalare esplicitamente quando si tratta di "benchmark proxy" e non gameplay reale.

### Statistica
- Nessun tool esterno necessario: Welch's t-test o Mann-Whitney U (per campioni piccoli, es. 3 run) implementabili direttamente nel backend come funzione condivisa riusabile in tutte le fasi (test loop, synergy pass, validazione).

## 6. Registro tweak candidati (per categoria di rischio)

### Sicuri (auto-apply consigliato, rollback sempre automatico)
- Power Plan (Balanced → High Performance/Ultimate Performance)
- Game Mode Windows (on/off)
- Disattivazione overlay di terze parti durante il gaming (Discord, GeForce Experience, Xbox Game Bar)
- Pulizia/gestione cache shader
- Gestione programmi in startup (disabilitazione non essenziali)
- Fan curve custom (se il tool di controllo lo supporta senza rischio termico)
- Aggiornamento driver GPU/chipset

### Medi (rollback automatico, ma con check di stabilità obbligatorio)
- HAGS – Hardware-Accelerated GPU Scheduling (on/off)
- Core Isolation / Memory Integrity (on/off, impatto su alcuni giochi con anti-cheat)
- HPET – High Precision Event Timer (enable/disable)
- Ultimate Performance power plan (variante nascosta di Windows)
- Timer Resolution (impostazione via API, non permanente di default)
- Memory Context Restore (se applicabile a piattaforma RAM specifica)
- Disattivazione servizi Windows non essenziali durante il gaming (telemetria, ricerca indicizzazione)

### Esperti (richiedono più cautela, alcuni con rollback parziale/manuale)
- Modifiche al registro per priorità processi/giochi
- Scheduler affinity (assegnazione core CPU specifici al processo di gioco)
- MSI Mode per GPU/periferiche (Message Signaled Interrupts)
- Priorità interrupt di rete/USB per periferiche di input
- Regolazione priorità processo (High/Realtime per il gioco)
- Disattivazione C-states CPU (impatto su power/temperature, da monitorare con check stabilità rafforzato)

### Hardware (richiedono reboot, rollback spesso manuale o parziale)
- XMP/EXPO (profili RAM)
- PBO – Precision Boost Overdrive (AMD) / analogo Intel
- Resizable BAR (richiede supporto BIOS+GPU+driver)
- Undervolt/overclock GPU (se il laboratorio decide di includerlo — richiede check di stabilità molto più stringente e va probabilmente escluso dalla v1 per rischio)
- Modifiche a impostazioni BIOS rilevabili via WMI ma non modificabili via software (segnalare come "richiede intervento manuale in BIOS")

## 7. Note implementative trasversali

- Tutte le run di benchmark devono passare per lo stesso harness (stessa scena/replay, stesso durata) per essere comparabili — se il gioco non supporto un replay deterministico, standardizzare almeno durata e tipo di attività (es. stesso match type in Warzone).
- Loggare temperatura ambiente/PC a inizio sessione se disponibile: utile per spiegare eventuali anomalie nei test successivi di una lunga sequenza.
- Il motore di significatività statistica (Welch's t-test o equivalente non parametrico se il campione è piccolo) deve essere una funzione condivisa riusabile sia nel test loop che nella synergy pass che nella validazione finale — non reimplementarla in tre posti diversi.
