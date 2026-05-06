"""
═══════════════════════════════════════════════════════════════════════════
backend/alembic/env.py — Configurazione Alembic per IMC-Group GANTT Agent
═══════════════════════════════════════════════════════════════════════════

Cosa fa questo file:
- Carica DATABASE_URL dal file .env (leggendolo come fa il backend)
- Importa Base.metadata da models.py (è il "target" delle migration:
  Alembic confronta lo stato del db con quello che dice models.py)
- Esegue le migration in modalità online (con engine SQLAlchemy attivo)
  o offline (genera solo SQL, senza eseguire — utile per produzione
  quando il DBA vuole vedere lo SQL prima di applicarlo)

Modifiche al template originale Alembic:
1. Aggiunto load_dotenv() per leggere .env
2. Configurato sqlalchemy.url da os.getenv("DATABASE_URL")
3. Importato Base da models e settato target_metadata = Base.metadata
═══════════════════════════════════════════════════════════════════════════
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Aggiungi backend/ al path Python così possiamo importare models
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carica variabili d'ambiente dal .env (DATABASE_URL ecc.)
load_dotenv()

# Importa il modello SQLAlchemy del progetto: tutto è in Base.metadata
from models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Setta dinamicamente sqlalchemy.url da DATABASE_URL del .env
# Così alembic.ini non contiene credenziali e tutti i tool (alembic, backend, ecc.)
# leggono la connessione dalla stessa fonte.
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
# Alembic confronta lo stato attuale del db con questo metadata e
# genera le migration come 'diff'.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Esegue migration in modalità 'offline' (genera solo SQL).

    Utile in produzione: il DBA può ispezionare lo script SQL prima di
    applicarlo. Comando: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Esegue migration in modalità 'online' (apre connessione e applica).

    Modalità tipica in dev: alembic upgrade head
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
