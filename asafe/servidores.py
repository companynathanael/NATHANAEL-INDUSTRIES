"""Gestão de servidores do Asafe.

Cada servidor manda um "sinal" (batimento) a cada `intervalo` segundos, com
métricas opcionais (cpu, memória, disco em %). O Asafe:
  - marca o servidor como offline se ficar 2 intervalos sem sinal;
  - abre alertas quando um servidor cai, volta ou passa de um limite de métrica,
    e avisa o Sr. Nathanael por mensagem;
  - guarda o histórico de métricas;
  - entrega comandos (reiniciar, parar, ...) na resposta do sinal.
"""

import json
from typing import Callable

from .db import Banco
from .seguranca import NOME_ADMIN

LIMITES_PADRAO = {"cpu": 90.0, "memoria": 90.0, "disco": 90.0}
METRICAS = ("cpu", "memoria", "disco")
NOMES_METRICAS = {"cpu": "CPU", "memoria": "memória", "disco": "disco"}
MAX_METRICAS_POR_SERVIDOR = 1000
FOLGA = 2  # quantos intervalos sem sinal até considerar offline


class GestaoServidores:
    def __init__(self, banco: Banco, relogio: Callable[[], float]):
        self.banco = banco
        self.relogio = relogio

    # ------------------------------------------------------------ consulta
    def status(self, row: dict) -> str:
        if row["manutencao"]:
            return "manutencao"
        if row.get("provedor") and row["sinal_em"] is None:
            return "criando"   # máquina criada pelo Asafe, ainda ligando
        if row["sinal_em"] is None or self.relogio() - row["sinal_em"] > row["intervalo"] * FOLGA:
            return "offline"
        return "online"

    def _formatar(self, row: dict) -> dict:
        r = dict(row)
        r["info"] = json.loads(r["info"])
        r["limites"] = {**LIMITES_PADRAO, **json.loads(r["limites"] or "{}")}
        r["manutencao"] = bool(r["manutencao"])
        r["status"] = self.status(row)
        r["online"] = r["status"] == "online"
        r["segundos_sem_sinal"] = None if row["sinal_em"] is None else round(self.relogio() - row["sinal_em"], 1)
        r["metricas"] = {m: r.pop(m) for m in METRICAS}
        r.pop("estado", None)
        r.pop("ultimo_sinal", None)
        return r

    def listar(self) -> list[dict]:
        return [self._formatar(r) for r in self.banco.todos("SELECT * FROM servidores ORDER BY nome")]

    def obter(self, nome: str) -> dict | None:
        row = self.banco.um("SELECT * FROM servidores WHERE nome=?", (nome,))
        return self._formatar(row) if row else None

    def historico(self, nome: str, limite: int = 100) -> list[dict]:
        return self.banco.todos(
            "SELECT cpu, memoria, disco, momento FROM metricas WHERE servidor=? ORDER BY id DESC LIMIT ?",
            (nome, max(1, min(limite, MAX_METRICAS_POR_SERVIDOR))))

    # ------------------------------------------------------------ cadastro
    def cadastrar(self, nome: str, endereco: str, intervalo: int, limites: dict, responsavel: str | None,
                  provedor: str | None = None) -> bool:
        if self.banco.um("SELECT 1 FROM servidores WHERE nome=?", (nome,)):
            return False
        self.banco.executar(
            "INSERT INTO servidores (nome, endereco, intervalo, limites, responsavel, estado, provedor) "
            "VALUES (?,?,?,?,?, 'offline', ?)",
            (nome, endereco, intervalo, json.dumps(limites), responsavel, provedor))
        return True

    def atualizar(self, nome: str, campos: dict) -> None:
        if "limites" in campos:
            campos["limites"] = json.dumps(campos["limites"])
        if "manutencao" in campos:
            campos["manutencao"] = int(campos["manutencao"])
        if campos:
            sets = ", ".join(f"{k}=?" for k in campos)
            self.banco.executar(f"UPDATE servidores SET {sets} WHERE nome=?", (*campos.values(), nome))

    def remover(self, nome: str) -> bool:
        cur = self.banco.executar("DELETE FROM servidores WHERE nome=?", (nome,))
        if cur.rowcount:
            self.banco.executar("DELETE FROM metricas WHERE servidor=?", (nome,))
            self.banco.executar("UPDATE comandos SET estado='falhou', resultado='servidor removido' "
                                "WHERE servidor=? AND estado IN ('pendente','entregue')", (nome,))
            self._resolver(nome)
        return bool(cur.rowcount)

    # ------------------------------------------------------------ sinal
    def receber_sinal(self, nome: str, endereco: str, info: dict, metricas: dict) -> list[dict]:
        agora = self.relogio()
        anterior = self.banco.um("SELECT * FROM servidores WHERE nome=?", (nome,))
        valores = {m: metricas.get(m) for m in METRICAS}
        self.banco.executar(
            "INSERT INTO servidores (nome, endereco, info, sinal_em, cpu, memoria, disco, estado) "
            "VALUES (?,?,?,?,?,?,?, 'online') "
            "ON CONFLICT(nome) DO UPDATE SET endereco=excluded.endereco, info=excluded.info, "
            "sinal_em=excluded.sinal_em, cpu=excluded.cpu, memoria=excluded.memoria, disco=excluded.disco, "
            "estado='online', ultimo_sinal=datetime('now')",
            (nome, endereco, json.dumps(info, ensure_ascii=False), agora, *valores.values()))

        if any(v is not None for v in valores.values()):
            self.banco.executar("INSERT INTO metricas (servidor, cpu, memoria, disco, momento) VALUES (?,?,?,?,?)",
                                (nome, *valores.values(), agora))
            self.banco.executar(
                "DELETE FROM metricas WHERE servidor=? AND id NOT IN "
                "(SELECT id FROM metricas WHERE servidor=? ORDER BY id DESC LIMIT ?)",
                (nome, nome, MAX_METRICAS_POR_SERVIDOR))

        if anterior and anterior["estado"] == "offline" and anterior["sinal_em"] is not None:
            self._resolver(nome, "caiu")
            if not anterior["manutencao"]:
                self._alertar(nome, "voltou", f"Servidor {nome} voltou a responder.", resolvido=True)

        limites = {**LIMITES_PADRAO, **json.loads((anterior or {}).get("limites") or "{}")}
        for m in METRICAS:
            v = valores[m]
            if v is None:
                continue
            if v >= limites[m]:
                if not self._aberto(nome, m) and not (anterior and anterior["manutencao"]):
                    self._alertar(nome, m, f"Servidor {nome}: {NOMES_METRICAS[m]} em {v:.0f}% "
                                           f"(limite {limites[m]:.0f}%).")
            else:
                self._resolver(nome, m)

        return self._entregar_comandos(nome)

    # ------------------------------------------------------------ vigia
    def verificar(self) -> list[dict]:
        """Procura servidores que pararam de mandar sinal. Chamado periodicamente."""
        novos = []
        for row in self.banco.todos("SELECT * FROM servidores WHERE estado='online' AND manutencao=0"):
            if self.status(row) == "offline":
                self.banco.executar("UPDATE servidores SET estado='offline' WHERE nome=?", (row["nome"],))
                seg = int(self.relogio() - row["sinal_em"]) if row["sinal_em"] else None
                novos.append(self._alertar(
                    row["nome"], "caiu",
                    f"Servidor {row['nome']} parou de responder" + (f" há {seg}s." if seg is not None else ".")))
        return novos

    # ------------------------------------------------------------ alertas
    def _aberto(self, servidor: str, tipo: str) -> bool:
        return bool(self.banco.um("SELECT 1 FROM alertas WHERE servidor=? AND tipo=? AND resolvido_em IS NULL",
                                  (servidor, tipo)))

    def _alertar(self, servidor: str, tipo: str, mensagem: str, resolvido: bool = False) -> dict:
        cur = self.banco.executar(
            "INSERT INTO alertas (servidor, tipo, mensagem, resolvido_em) VALUES (?,?,?, "
            + ("datetime('now')" if resolvido else "NULL") + ")", (servidor, tipo, mensagem))
        self.banco.executar("INSERT INTO mensagens (de, para, conteudo) VALUES (?,?,?)",
                            ("asafe", NOME_ADMIN, f"[alerta] {mensagem}"))
        return {"id": cur.lastrowid, "servidor": servidor, "tipo": tipo, "mensagem": mensagem}

    def _resolver(self, servidor: str, tipo: str | None = None) -> None:
        if tipo:
            self.banco.executar("UPDATE alertas SET resolvido_em=datetime('now') "
                                "WHERE servidor=? AND tipo=? AND resolvido_em IS NULL", (servidor, tipo))
        else:
            self.banco.executar("UPDATE alertas SET resolvido_em=datetime('now') "
                                "WHERE servidor=? AND resolvido_em IS NULL", (servidor,))

    def alertas(self, abertos: bool, servidor: str | None, limite: int) -> list[dict]:
        sql, params = "SELECT * FROM alertas WHERE 1=1", []
        if abertos:
            sql += " AND resolvido_em IS NULL"
        if servidor:
            sql += " AND servidor=?"
            params.append(servidor)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(limite, 1000)))
        return self.banco.todos(sql, tuple(params))

    def resolver_alerta(self, alerta_id: int) -> bool:
        cur = self.banco.executar("UPDATE alertas SET resolvido_em=datetime('now') "
                                  "WHERE id=? AND resolvido_em IS NULL", (alerta_id,))
        return bool(cur.rowcount)

    # ------------------------------------------------------------ comandos
    def pedir_comando(self, servidor: str, comando: str, args: dict, pedido_por: str) -> dict:
        cur = self.banco.executar(
            "INSERT INTO comandos (servidor, comando, args, pedido_por) VALUES (?,?,?,?)",
            (servidor, comando, json.dumps(args, ensure_ascii=False), pedido_por))
        return {"id": cur.lastrowid, "servidor": servidor, "comando": comando, "estado": "pendente"}

    def _entregar_comandos(self, servidor: str) -> list[dict]:
        rows = self.banco.todos("SELECT id, comando, args FROM comandos WHERE servidor=? AND estado='pendente' "
                                "ORDER BY id", (servidor,))
        if rows:
            ids = [r["id"] for r in rows]
            self.banco.executar(f"UPDATE comandos SET estado='entregue', atualizado_em=datetime('now') "
                                f"WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
        return [{"id": r["id"], "comando": r["comando"], "args": json.loads(r["args"])} for r in rows]

    def concluir_comando(self, servidor: str, comando_id: int, ok: bool, saida: str) -> bool:
        cur = self.banco.executar(
            "UPDATE comandos SET estado=?, resultado=?, atualizado_em=datetime('now') "
            "WHERE id=? AND servidor=? AND estado='entregue'",
            ("concluido" if ok else "falhou", saida, comando_id, servidor))
        return bool(cur.rowcount)

    def comandos(self, servidor: str, limite: int = 50) -> list[dict]:
        rows = self.banco.todos("SELECT * FROM comandos WHERE servidor=? ORDER BY id DESC LIMIT ?",
                                (servidor, max(1, min(limite, 500))))
        for r in rows:
            r["args"] = json.loads(r["args"])
        return rows
