"""
Le migration e il modello descrivono lo stesso schema.

Il rischio che presidia: si cambia `models.py` e si dimentica la baseline, o il
contrario. `alembic check` non basta: confronta il modello con lo schema, ma
non vede i CHECK, ed è così che i vincoli sugli stati erano spariti dal
database senza che nessuno se ne accorgesse (`_check_in` in models.py).

Come: dentro gantt_test, in due schemi separati, si costruisce lo schema due
volte, con `alembic upgrade head` (la stessa funzione di
`scripts/ricostruisci_db.py`) e con `Base.metadata.create_all`. Poi si
confronta un'interrogazione normalizzata del catalogo: colonne con tipo,
nullabilità, default e identity; vincoli con la loro definizione; indici;
viste; sequenze con i loro parametri. L'ordine delle colonne resta fuori: la
baseline e il modello non devono doverlo tenere uguale.

`alembic_version` esiste solo dove sono passate le migration, e si esclude.
"""

import difflib
import os

import pytest
from sqlalchemy import text

SCHEMA_MIGRATION = "allineamento_migration"
SCHEMA_MODELLO = "allineamento_modello"

# Una riga per oggetto, con il nome dello schema mai scritto: si interroga
# current_schema(), e lo stesso testo vale per i due schemi.
CATALOGO = """
SELECT 'TABLE  ' || c.relname || ' ' || c.relkind::text
FROM pg_class c
WHERE c.relnamespace = current_schema()::regnamespace AND c.relkind IN ('r', 'v')
UNION ALL
SELECT 'COLUMN ' || c.table_name || '.' || c.column_name || ' ' ||
       format_type(a.atttypid, a.atttypmod) ||
       CASE WHEN c.is_nullable = 'NO' THEN ' NOT NULL' ELSE ' NULL' END ||
       COALESCE(' DEFAULT ' || c.column_default, '') ||
       CASE WHEN c.is_identity = 'YES' THEN ' IDENTITY ' || c.identity_generation ELSE '' END
FROM information_schema.columns c
JOIN pg_class t ON t.relname = c.table_name AND t.relnamespace = current_schema()::regnamespace
JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = c.column_name
WHERE c.table_schema = current_schema()
UNION ALL
SELECT 'CONSTR ' || conrelid::regclass::text || ' ' || contype::text || ' ' ||
       conname || ' ' || pg_get_constraintdef(oid)
FROM pg_constraint
WHERE connamespace = current_schema()::regnamespace
UNION ALL
SELECT 'INDEX  ' || tablename || ' ' || indexname || ' ' ||
       regexp_replace(indexdef, '^CREATE (UNIQUE )?INDEX \\S+ ON \\S+ ', '\\1')
FROM pg_indexes
WHERE schemaname = current_schema()
UNION ALL
SELECT 'VIEW   ' || viewname || ' ' ||
       regexp_replace(pg_get_viewdef((current_schema() || '.' || viewname)::regclass, true), '\\s+', ' ', 'g')
FROM pg_views
WHERE schemaname = current_schema()
UNION ALL
SELECT 'SEQ    ' || sequencename || ' ' || data_type || ' start ' || start_value ||
       ' min ' || min_value || ' max ' || max_value || ' incr ' || increment_by ||
       ' cycle ' || cycle
FROM pg_sequences
WHERE schemaname = current_schema()
UNION ALL
SELECT 'TRIG   ' || event_object_table || ' ' || trigger_name
FROM information_schema.triggers
WHERE trigger_schema = current_schema()
UNION ALL
SELECT 'FUNC   ' || p.proname
FROM pg_proc p
WHERE p.pronamespace = current_schema()::regnamespace
ORDER BY 1
"""


def _catalogo(conn, schema):
    conn.execute(text(f"SET LOCAL search_path TO {schema}"))
    return [riga for (riga,) in conn.execute(text(CATALOGO))
            if "alembic_version" not in riga]


def _togli_schemi(conn):
    for schema in (SCHEMA_MIGRATION, SCHEMA_MODELLO):
        conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))


@pytest.fixture
def due_schemi():
    """I due schemi di confronto, creati vuoti e tolti alla fine (anche se il
    test fallisce). Il nome del database si controlla prima di ogni scrittura."""
    import models

    def connessione():
        conn = models.engine.connect()
        assert conn.execute(text("SELECT current_database()")).scalar() == "gantt_test"
        conn.rollback()  # chiude la transazione aperta dal controllo
        return conn

    with connessione() as conn, conn.begin():
        _togli_schemi(conn)
        for schema in (SCHEMA_MIGRATION, SCHEMA_MODELLO):
            conn.execute(text(f"CREATE SCHEMA {schema}"))
    try:
        yield connessione
    finally:
        with connessione() as conn, conn.begin():
            _togli_schemi(conn)


def test_baseline_e_modello_producono_lo_stesso_schema(due_schemi):
    import models
    from scripts.ricostruisci_db import applica_migration

    applica_migration(os.environ["DATABASE_URL"], schema=SCHEMA_MIGRATION)
    with due_schemi() as conn, conn.begin():
        conn.execute(text(f"SET LOCAL search_path TO {SCHEMA_MODELLO}"))
        models.Base.metadata.create_all(conn, checkfirst=False)

    with due_schemi() as conn, conn.begin():
        da_migration = _catalogo(conn, SCHEMA_MIGRATION)
        da_modello = _catalogo(conn, SCHEMA_MODELLO)

    assert any(r.startswith("TABLE  progetti") for r in da_migration), \
        "le migration non hanno costruito niente nello schema di confronto"
    differenze = list(difflib.unified_diff(
        da_migration, da_modello, "migration", "modello", lineterm="", n=0))
    assert not differenze, (
        "Baseline e modello descrivono schemi diversi:\n" + "\n".join(differenze))
