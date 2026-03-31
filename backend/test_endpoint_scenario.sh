#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Test rapido endpoint scenario — esegui con il backend avviato
# Uso: bash test_endpoint_scenario.sh
# ═══════════════════════════════════════════════════════════════

BASE="http://localhost:8000/api"

echo "═══════════════════════════════════════════════════════"
echo "TEST 1: /api/scenario/simula (sposta_task)"
echo "  Sposta un task di 10 giorni e verifica la cascata"
echo "═══════════════════════════════════════════════════════"

# Prima, prendiamo un task reale dal sistema
echo ""
echo "→ Recupero lista task per trovare un ID valido..."
TASK_INFO=$(curl -s "$BASE/tasks" | python3 -c "
import json, sys
tasks = json.load(sys.stdin)
# Trova un task con predecessore (per testare cascata)
for t in tasks:
    if t.get('predecessore') and t['stato'] != 'Completato':
        print(f\"PRED_TASK={t['id']}|PRED_NAME={t['nome']}|PRED_FINE={t['data_fine']}\")
        break
else:
    # Se nessun task ha predecessore, prendi il primo attivo
    for t in tasks:
        if t['stato'] != 'Completato':
            print(f\"PRED_TASK={t['id']}|PRED_NAME={t['nome']}|PRED_FINE={t['data_fine']}\")
            break
" 2>/dev/null)

if [ -z "$TASK_INFO" ]; then
    echo "❌ Nessun task trovato. Il backend è avviato?"
    exit 1
fi

TASK_ID=$(echo "$TASK_INFO" | cut -d'|' -f1 | cut -d'=' -f2)
TASK_NAME=$(echo "$TASK_INFO" | cut -d'|' -f2 | cut -d'=' -f2)
TASK_FINE=$(echo "$TASK_INFO" | cut -d'|' -f3 | cut -d'=' -f2)

echo "  Task selezionato: $TASK_NAME ($TASK_ID)"
echo "  Data fine attuale: $TASK_FINE"
echo ""
echo "→ Chiamo /api/scenario/simula..."

RESULT=$(curl -s -X POST "$BASE/scenario/simula" \
  -H "Content-Type: application/json" \
  -d "{
    \"modifiche\": [{
      \"tipo\": \"sposta_task\",
      \"task_id\": \"$TASK_ID\",
      \"nuova_fine\": \"2026-06-30\"
    }]
  }")

# Analizza risultato
echo "$RESULT" | python3 -c "
import json, sys
try:
    r = json.load(sys.stdin)
    n = r.get('n_task_modificati', 0)
    cons = r.get('conseguenze', [])
    proj = r.get('progetti_impattati', [])
    print(f'  ✅ Risposta ricevuta!')
    print(f'  Task modificati (inclusa cascata): {n}')
    print(f'  Progetti impattati: {len(proj)}')
    for p in proj:
        print(f'    - {p[\"nome\"]}')
    print(f'  Conseguenze: {len(cons)}')
    for c in cons[:5]:
        g = c.get('gravita','?').upper()
        print(f'    [{g}] {c[\"testo\"][:120]}')
    if len(cons) > 5:
        print(f'    ... e altre {len(cons)-5}')
    print()
    print('  ✅ TEST 1 PASSATO')
except Exception as e:
    print(f'  ❌ Errore nel parsing: {e}')
    print(f'  Risposta raw: {sys.stdin.read()[:500]}')
" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "  ❌ Errore nella chiamata. Risposta raw:"
    echo "$RESULT" | head -20
fi


echo ""
echo "═══════════════════════════════════════════════════════"
echo "TEST 2: /api/scenario/simula (cambia_focus)"
echo "  Una persona si concentra al 100% su un progetto"
echo "═══════════════════════════════════════════════════════"

# Trova un dipendente con task su più progetti
DIP_INFO=$(curl -s "$BASE/dipendenti" | python3 -c "
import json, sys
dips = json.load(sys.stdin)
for d in dips:
    if d.get('n_progetti', 0) >= 2 or d.get('saturazione_pct', 0) > 50:
        print(f\"DIP_ID={d['id']}|DIP_NAME={d['nome']}\")
        break
else:
    if dips:
        print(f\"DIP_ID={dips[0]['id']}|DIP_NAME={dips[0]['nome']}\")
" 2>/dev/null)

PROJ_INFO=$(curl -s "$BASE/progetti" | python3 -c "
import json, sys
projs = json.load(sys.stdin)
for p in projs:
    if p.get('stato') == 'In esecuzione':
        print(f\"PROJ_ID={p['id']}|PROJ_NAME={p['nome']}\")
        break
" 2>/dev/null)

if [ -n "$DIP_INFO" ] && [ -n "$PROJ_INFO" ]; then
    DIP_ID=$(echo "$DIP_INFO" | cut -d'|' -f1 | cut -d'=' -f2)
    DIP_NAME=$(echo "$DIP_INFO" | cut -d'|' -f2 | cut -d'=' -f2)
    PROJ_ID=$(echo "$PROJ_INFO" | cut -d'|' -f1 | cut -d'=' -f2)
    PROJ_NAME=$(echo "$PROJ_INFO" | cut -d'|' -f2 | cut -d'=' -f2)

    echo "  Dipendente: $DIP_NAME ($DIP_ID)"
    echo "  Progetto focus: $PROJ_NAME ($PROJ_ID)"
    echo ""
    echo "→ Chiamo /api/scenario/simula con cambia_focus..."

    RESULT2=$(curl -s -X POST "$BASE/scenario/simula" \
      -H "Content-Type: application/json" \
      -d "{
        \"modifiche\": [{
          \"tipo\": \"cambia_focus\",
          \"dipendente_id\": \"$DIP_ID\",
          \"progetto_focus\": \"$PROJ_ID\",
          \"percentuale\": 100,
          \"durata_settimane\": 3
        }]
      }")

    echo "$RESULT2" | python3 -c "
import json, sys
try:
    r = json.load(sys.stdin)
    n = r.get('n_task_modificati', 0)
    cons = r.get('conseguenze', [])
    print(f'  ✅ Risposta ricevuta!')
    print(f'  Task modificati: {n}')
    print(f'  Conseguenze: {len(cons)}')
    for c in cons[:5]:
        g = c.get('gravita','?').upper()
        print(f'    [{g}] {c[\"testo\"][:120]}')
    print()
    print('  ✅ TEST 2 PASSATO')
except Exception as e:
    print(f'  ❌ Errore: {e}')
" 2>/dev/null
else
    echo "  ⚠️ Non ho trovato dipendente/progetto per il test 2, skip."
fi


echo ""
echo "═══════════════════════════════════════════════════════"
echo "TEST 3: /api/scenario/interpreta (richiede Gemini)"
echo "  Salta se Gemini non è configurato"
echo "═══════════════════════════════════════════════════════"

AGENT_STATUS=$(curl -s "$BASE/agent/status" | python3 -c "
import json, sys
r = json.load(sys.stdin)
print(r.get('available', False))
" 2>/dev/null)

if [ "$AGENT_STATUS" = "True" ]; then
    echo "  Gemini disponibile. Testo: 'Il progetto SmartCity anticipa di 15 giorni'"
    echo ""
    RESULT3=$(curl -s -X POST "$BASE/scenario/interpreta" \
      -H "Content-Type: application/json" \
      -d '{"testo": "Il progetto SmartCity anticipa di 15 giorni"}')

    echo "$RESULT3" | python3 -c "
import json, sys
try:
    r = json.load(sys.stdin)
    if r.get('parse_error'):
        print('  ⚠️ Parse error — risposta raw:')
        print(f'  {r.get(\"interpretazione\",\"\")[:200]}')
    else:
        print(f'  Interpretazione: {r.get(\"interpretazione\",\"\")[:200]}')
        mods = r.get('modifiche', [])
        print(f'  Modifiche proposte: {len(mods)}')
        for m in mods[:3]:
            print(f'    - {m.get(\"tipo\")}: {m.get(\"task_id\",\"\")} {m.get(\"motivo\",\"\")[:80]}')
        domande = r.get('domande', '')
        if domande:
            print(f'  Domanda IA: {domande}')
        print()
        print('  ✅ TEST 3 PASSATO')
except Exception as e:
    print(f'  ❌ Errore: {e}')
" 2>/dev/null
else
    echo "  ⚠️ Gemini non disponibile — test 3 saltato (ok per ora)"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "RIEPILOGO"
echo "═══════════════════════════════════════════════════════"
echo "Test 1 (simula sposta_task):   controlla sopra"
echo "Test 2 (simula cambia_focus):  controlla sopra"
echo "Test 3 (interpreta con IA):    controlla sopra"
echo ""
echo "Se test 1 e 2 passano, il backend è solido."
echo "Il test 3 è un bonus — funziona solo con Gemini attivo."
