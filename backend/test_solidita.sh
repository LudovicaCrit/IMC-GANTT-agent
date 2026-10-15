#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Test di solidità — chiama TUTTI gli endpoint e verifica 200 OK
# Uso: bash test_solidita.sh
# Richiede: backend avviato su localhost:8000
# ═══════════════════════════════════════════════════════════════

BASE="http://localhost:8000/api"
PASS=0
FAIL=0
SKIP=0

function test_get() {
  local desc="$1"
  local url="$2"
  local status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
  if [ "$status" = "200" ]; then
    echo "  ✅ $desc ($status)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $desc ($status)"
    FAIL=$((FAIL + 1))
  fi
}

function test_post() {
  local desc="$1"
  local url="$2"
  local data="$3"
  local status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" -H "Content-Type: application/json" -d "$data")
  if [ "$status" = "200" ]; then
    echo "  ✅ $desc ($status)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $desc ($status)"
    FAIL=$((FAIL + 1))
  fi
}

echo "═══════════════════════════════════════════════════════"
echo "TEST DI SOLIDITÀ — $(date)"
echo "═══════════════════════════════════════════════════════"

echo ""
echo "── GET endpoints ──"
test_get "GET /dipendenti" "$BASE/dipendenti"
test_get "GET /dipendenti/D001" "$BASE/dipendenti/D001"
test_get "GET /progetti" "$BASE/progetti"
test_get "GET /tasks" "$BASE/tasks"
test_get "GET /tasks?progetto_id=P001" "$BASE/tasks?progetto_id=P001"
test_get "GET /gantt" "$BASE/gantt"
test_get "GET /gantt?progetto_id=P001" "$BASE/gantt?progetto_id=P001"
test_get "GET /risorse/carico" "$BASE/risorse/carico"
test_get "GET /segnalazioni" "$BASE/segnalazioni"

echo ""
echo "── POST endpoints (senza side effects) ──"

test_post "POST /task/anteprima-impatto" "$BASE/task/anteprima-impatto" \
  '{"modifiche": [{"task_id": "T003", "campo": "data_fine", "nuovo_valore": "2026-04-15"}], "nuovi_task": [], "progetto_id": ""}'

echo ""
echo "── Export endpoints ──"

EXPORT_PDF=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/gantt/export-pdf")
if [ "$EXPORT_PDF" = "200" ]; then
  echo "  ✅ GET /gantt/export-pdf ($EXPORT_PDF)"
  PASS=$((PASS + 1))
else
  echo "  ❌ GET /gantt/export-pdf ($EXPORT_PDF)"
  FAIL=$((FAIL + 1))
fi

EXPORT_EXCEL=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/gantt/export-excel")
if [ "$EXPORT_EXCEL" = "200" ]; then
  echo "  ✅ GET /gantt/export-excel ($EXPORT_EXCEL)"
  PASS=$((PASS + 1))
else
  echo "  ❌ GET /gantt/export-excel ($EXPORT_EXCEL)"
  FAIL=$((FAIL + 1))
fi

EXPORT_PNG=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/gantt/export-png")
if [ "$EXPORT_PNG" = "200" ]; then
  echo "  ✅ GET /gantt/export-png ($EXPORT_PNG)"
  PASS=$((PASS + 1))
else
  echo "  ⚠️  GET /gantt/export-png ($EXPORT_PNG) — richiede poppler-utils"
  SKIP=$((SKIP + 1))
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "RISULTATI"
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Passati:  $PASS"
echo "  ❌ Falliti:  $FAIL"
echo "  ⚠️  Saltati: $SKIP"
TOTAL=$((PASS + FAIL))
if [ "$FAIL" = "0" ]; then
  echo ""
  echo "  🎉 TUTTI I TEST PASSATI! ($PASS/$TOTAL)"
else
  echo ""
  echo "  ⚠️  $FAIL test falliti su $TOTAL"
fi
