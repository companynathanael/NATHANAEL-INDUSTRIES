"""Camada de armazenamento do Asafe (SQLite)."""

import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS agentes (
    nome        TEXT PRIMARY KEY,
    categoria   TEXT NOT NULL,
    versao      TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    permissoes  TEXT NOT NULL,          -- lista separada por vírgula
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS mensagens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    de          TEXT NOT NULL,
    para        TEXT NOT NULL,
    conteudo    TEXT NOT NULL,
    lida        INTEGER NOT NULL DEFAULT 0,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS dados (
    agente      TEXT NOT NULL,
    chave       TEXT NOT NULL,
    valor       TEXT NOT NULL,          -- JSON
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agente, chave)
);
CREATE TABLE IF NOT EXISTS auditoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agente      TEXT NOT NULL,
    acao        TEXT NOT NULL,
    alvo        TEXT,
    status      INTEGER NOT NULL,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS servidores (
    nome        TEXT PRIMARY KEY,
    endereco    TEXT NOT NULL,
    info        TEXT NOT NULL DEFAULT '{}',
    ultimo_sinal TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class Banco:
    """Acesso simples e thread-safe ao SQLite."""

    def __init__(self, caminho: str | Path):
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(SCHEMA)

    def executar(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._con.execute(sql, params)
            self._con.commit()
            return cur

    def um(self, sql: str, params: tuple = ()) -> dict | None:
        with self._lock:
            row = self._con.execute(sql, params).fetchone()
        return dict(row) if row else None

    def todos(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            rows = self._con.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
