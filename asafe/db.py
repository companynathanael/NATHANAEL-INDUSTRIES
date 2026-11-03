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
CREATE TABLE IF NOT EXISTS arquivos (
    agente      TEXT NOT NULL,
    nome        TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    tamanho     INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    caminho     TEXT NOT NULL,          -- relativo à pasta de arquivos; nunca derivado do nome
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (agente, nome)
);
CREATE TABLE IF NOT EXISTS metricas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    servidor    TEXT NOT NULL,
    cpu         REAL,
    memoria     REAL,
    disco       REAL,
    momento     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metricas_servidor ON metricas (servidor, id);
CREATE TABLE IF NOT EXISTS alertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    servidor    TEXT NOT NULL,
    tipo        TEXT NOT NULL,          -- caiu | voltou | cpu | memoria | disco
    mensagem    TEXT NOT NULL,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now')),
    resolvido_em TEXT
);
CREATE TABLE IF NOT EXISTS energia (
    id          INTEGER PRIMARY KEY CHECK (id = 1),   -- uma linha só: o estado das caixas
    estado      TEXT NOT NULL,                        -- JSON
    atualizado_em REAL NOT NULL                       -- epoch da última atualização (para descarregar em tempo real)
);
CREATE TABLE IF NOT EXISTS energia_eventos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,          -- nivel | queda | retorno | backup | desligamento | fonte
    nivel       TEXT,
    mensagem    TEXT NOT NULL,
    origem      TEXT NOT NULL,          -- simulacao | <nome do servidor> | asafe
    criado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS energia_fontes (
    servidor    TEXT PRIMARY KEY,       -- servidor que mandou o estado de energia no sinal
    na_rede     INTEGER NOT NULL,
    bateria_pct REAL,
    autonomia_min REAL,
    nivel       TEXT NOT NULL,
    momento     REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS comandos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    servidor    TEXT NOT NULL,
    comando     TEXT NOT NULL,
    args        TEXT NOT NULL DEFAULT '{}',
    estado      TEXT NOT NULL DEFAULT 'pendente',   -- pendente | entregue | concluido | falhou
    resultado   TEXT,
    pedido_por  TEXT NOT NULL,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Colunas acrescentadas depois da primeira versão (bancos antigos são migrados ao abrir).
MIGRACOES = {
    "servidores": {
        "sinal_em": "REAL",                         # epoch do último sinal
        "intervalo": "INTEGER NOT NULL DEFAULT 30", # segundos esperados entre sinais
        "limites": "TEXT NOT NULL DEFAULT '{}'",    # {"cpu": 90, "memoria": 90, "disco": 90}
        "manutencao": "INTEGER NOT NULL DEFAULT 0",
        "estado": "TEXT NOT NULL DEFAULT 'online'", # último estado conhecido (para detectar quedas)
        "responsavel": "TEXT",
        "cpu": "REAL", "memoria": "REAL", "disco": "REAL",
        "provedor": "TEXT",       # local | oracle | NULL (máquina cadastrada à mão)
        "maquina_id": "TEXT",     # id da máquina no provedor
        "agente_sinal": "TEXT",   # agente cujo token o servidor usa para mandar sinal
    },
}


class Banco:
    """Acesso simples e thread-safe ao SQLite."""

    def __init__(self, caminho: str | Path):
        self._con = sqlite3.connect(str(caminho), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._con.executescript(SCHEMA)
            for tabela, colunas in MIGRACOES.items():
                existentes = {r[1] for r in self._con.execute(f"PRAGMA table_info({tabela})")}
                for coluna, tipo in colunas.items():
                    if coluna not in existentes:
                        self._con.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
            self._con.commit()

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

    def backup_para(self, destino: str | Path) -> None:
        """Cópia consistente do banco (API de backup do SQLite), mesmo com o Asafe rodando."""
        dest = sqlite3.connect(str(destino))
        try:
            with self._lock:
                self._con.backup(dest)
        finally:
            dest.close()

    def fechar(self) -> None:
        with self._lock:
            self._con.close()
