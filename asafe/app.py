"""API principal do Asafe.

Cobre: registro de agentes, permissões, comunicação entre IAs, armazenamento
de dados por agente, auditoria das ações e registro de servidores.
"""

import json
import os
from dataclasses import dataclass

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import __version__
from .db import Banco
from .eletronanologia import MENSAGENS, SistemaEletro
from .modelos import AtualizarPermissoes, NovaMensagem, NovoAgente, Sinal, Valor
from .seguranca import (
    NOME_ADMIN,
    PERMISSOES,
    gerar_token,
    hash_token,
    tem_permissao,
    tokens_iguais,
)


@dataclass
class Agente:
    nome: str
    permissoes: set[str]


def _validar_permissoes(perms: list[str]) -> None:
    invalidas = set(perms) - PERMISSOES
    if invalidas:
        raise HTTPException(422, f"Permissões desconhecidas: {sorted(invalidas)}")


def criar_app(caminho_db: str | None = None, token_admin: str | None = None) -> FastAPI:
    caminho_db = caminho_db or os.environ.get("ASAFE_DB", "asafe.db")
    token_admin = token_admin or os.environ.get("ASAFE_ADMIN_TOKEN")
    if not token_admin:
        raise RuntimeError("Defina ASAFE_ADMIN_TOKEN (token do Sr. Nathanael).")

    banco = Banco(caminho_db)
    energia = SistemaEletro.padrao(
        n_caixas=int(os.environ.get("ELETRO_CAIXAS", "4")),
        consumo_w=float(os.environ.get("ELETRO_CONSUMO_W", "60")),
    )
    app = FastAPI(title="Asafe", version=__version__,
                  description="Infraestrutura inteligente da Nathanael Industries")
    bearer = HTTPBearer(auto_error=False)
    app.state.energia = energia

    # ---------- Monitoramento: toda requisição vira registro de auditoria ----------
    @app.middleware("http")
    async def auditar(request: Request, call_next):
        resposta = await call_next(request)
        if request.url.path not in ("/saude", "/docs", "/openapi.json"):
            agente = getattr(request.state, "agente", "anonimo")
            banco.executar(
                "INSERT INTO auditoria (agente, acao, alvo, status) VALUES (?,?,?,?)",
                (agente, request.method, request.url.path, resposta.status_code),
            )
        return resposta

    # ---------- Autenticação e permissões ----------
    def agente_atual(request: Request,
                     cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Agente:
        if cred is None:
            raise HTTPException(401, "Token ausente")
        token = cred.credentials
        if tokens_iguais(token, token_admin):
            ag = Agente(NOME_ADMIN, {"*"})
        else:
            row = banco.um("SELECT nome, permissoes, ativo FROM agentes WHERE token_hash=?",
                           (hash_token(token),))
            if not row or not row["ativo"]:
                raise HTTPException(401, "Token inválido ou agente desativado")
            ag = Agente(row["nome"], set(filter(None, row["permissoes"].split(","))))
        request.state.agente = ag.nome
        return ag

    def exige(permissao: str):
        def dep(ag: Agente = Depends(agente_atual)) -> Agente:
            if not tem_permissao(ag.permissoes, permissao):
                raise HTTPException(403, f"Permissão necessária: {permissao}")
            return ag
        return dep

    def so_admin(ag: Agente = Depends(agente_atual)) -> Agente:
        if "*" not in ag.permissoes:
            raise HTTPException(403, "Apenas o Sr. Nathanael")
        return ag

    # ---------- Saúde ----------
    @app.get("/saude")
    def saude():
        return {"status": "ok", "servico": "asafe", "versao": __version__}

    @app.get("/eu")
    def eu(ag: Agente = Depends(agente_atual)):
        return {"nome": ag.nome, "permissoes": sorted(ag.permissoes)}

    # ---------- Agentes ----------
    @app.post("/agentes", status_code=201)
    def registrar_agente(dados: NovoAgente, _: Agente = Depends(so_admin)):
        _validar_permissoes(dados.permissoes)
        if dados.nome == NOME_ADMIN or banco.um("SELECT 1 FROM agentes WHERE nome=?", (dados.nome,)):
            raise HTTPException(409, "Agente já existe")
        token = gerar_token()
        banco.executar(
            "INSERT INTO agentes (nome, categoria, versao, token_hash, permissoes) VALUES (?,?,?,?,?)",
            (dados.nome, dados.categoria, dados.versao, hash_token(token), ",".join(dados.permissoes)),
        )
        return {"nome": dados.nome, "token": token,
                "aviso": "Guarde este token: ele não será exibido novamente."}

    @app.get("/agentes")
    def listar_agentes(_: Agente = Depends(exige("agentes:ler"))):
        rows = banco.todos("SELECT nome, categoria, versao, permissoes, ativo, criado_em FROM agentes ORDER BY nome")
        for r in rows:
            r["permissoes"] = list(filter(None, r["permissoes"].split(",")))
            r["ativo"] = bool(r["ativo"])
        return rows

    def _agente_existe(nome: str) -> None:
        if not banco.um("SELECT 1 FROM agentes WHERE nome=?", (nome,)):
            raise HTTPException(404, "Agente não encontrado")

    @app.put("/agentes/{nome}/permissoes")
    def mudar_permissoes(nome: str, dados: AtualizarPermissoes, _: Agente = Depends(so_admin)):
        _agente_existe(nome)
        _validar_permissoes(dados.permissoes)
        banco.executar("UPDATE agentes SET permissoes=? WHERE nome=?", (",".join(dados.permissoes), nome))
        return {"nome": nome, "permissoes": dados.permissoes}

    @app.post("/agentes/{nome}/ativo")
    def definir_ativo(nome: str, ativo: bool, _: Agente = Depends(so_admin)):
        _agente_existe(nome)
        banco.executar("UPDATE agentes SET ativo=? WHERE nome=?", (int(ativo), nome))
        return {"nome": nome, "ativo": ativo}

    @app.post("/agentes/{nome}/novo-token")
    def renovar_token(nome: str, _: Agente = Depends(so_admin)):
        _agente_existe(nome)
        token = gerar_token()
        banco.executar("UPDATE agentes SET token_hash=? WHERE nome=?", (hash_token(token), nome))
        return {"nome": nome, "token": token}

    # ---------- Comunicação entre IAs ----------
    @app.post("/mensagens", status_code=201)
    def enviar(msg: NovaMensagem, ag: Agente = Depends(exige("mensagens:enviar"))):
        if msg.para != NOME_ADMIN:
            _agente_existe(msg.para)
        cur = banco.executar("INSERT INTO mensagens (de, para, conteudo) VALUES (?,?,?)",
                             (ag.nome, msg.para, msg.conteudo))
        return {"id": cur.lastrowid, "de": ag.nome, "para": msg.para}

    @app.get("/mensagens")
    def caixa_de_entrada(apenas_nao_lidas: bool = True, ag: Agente = Depends(exige("mensagens:ler"))):
        filtro = " AND lida=0" if apenas_nao_lidas else ""
        rows = banco.todos(f"SELECT * FROM mensagens WHERE para=?{filtro} ORDER BY id", (ag.nome,))
        if rows:
            ids = [r["id"] for r in rows]
            banco.executar(f"UPDATE mensagens SET lida=1 WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
        for r in rows:
            r["lida"] = bool(r["lida"])
        return rows

    # ---------- Armazenamento de dados (cada agente tem seu espaço) ----------
    @app.put("/dados/{chave}")
    def gravar(chave: str, dados: Valor, ag: Agente = Depends(exige("dados:escrever"))):
        banco.executar(
            "INSERT INTO dados (agente, chave, valor) VALUES (?,?,?) "
            "ON CONFLICT(agente, chave) DO UPDATE SET valor=excluded.valor, atualizado_em=datetime('now')",
            (ag.nome, chave, json.dumps(dados.valor, ensure_ascii=False)),
        )
        return {"chave": chave, "ok": True}

    @app.get("/dados")
    def listar_chaves(ag: Agente = Depends(exige("dados:ler"))):
        return [r["chave"] for r in banco.todos("SELECT chave FROM dados WHERE agente=? ORDER BY chave", (ag.nome,))]

    @app.get("/dados/{chave}")
    def ler(chave: str, ag: Agente = Depends(exige("dados:ler"))):
        row = banco.um("SELECT valor, atualizado_em FROM dados WHERE agente=? AND chave=?", (ag.nome, chave))
        if not row:
            raise HTTPException(404, "Chave não encontrada")
        return {"chave": chave, "valor": json.loads(row["valor"]), "atualizado_em": row["atualizado_em"]}

    @app.delete("/dados/{chave}")
    def apagar(chave: str, ag: Agente = Depends(exige("dados:escrever"))):
        cur = banco.executar("DELETE FROM dados WHERE agente=? AND chave=?", (ag.nome, chave))
        if cur.rowcount == 0:
            raise HTTPException(404, "Chave não encontrada")
        return {"chave": chave, "apagada": True}

    # ---------- Monitoramento ----------
    @app.get("/auditoria")
    def auditoria(agente: str | None = None, limite: int = 100,
                  _: Agente = Depends(exige("auditoria:ler"))):
        limite = max(1, min(limite, 1000))
        if agente:
            return banco.todos("SELECT * FROM auditoria WHERE agente=? ORDER BY id DESC LIMIT ?", (agente, limite))
        return banco.todos("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,))

    # ---------- Servidores (registro inicial; gestão completa na fase 2) ----------
    @app.post("/servidores/sinal")
    def sinal(s: Sinal, _: Agente = Depends(exige("servidores:gerenciar"))):
        banco.executar(
            "INSERT INTO servidores (nome, endereco, info) VALUES (?,?,?) "
            "ON CONFLICT(nome) DO UPDATE SET endereco=excluded.endereco, info=excluded.info, "
            "ultimo_sinal=datetime('now')",
            (s.nome, s.endereco, json.dumps(s.info, ensure_ascii=False)),
        )
        return {"nome": s.nome, "ok": True}

    @app.get("/servidores")
    def servidores(_: Agente = Depends(exige("servidores:gerenciar"))):
        rows = banco.todos(
            "SELECT *, (strftime('%s','now') - strftime('%s', ultimo_sinal)) AS segundos_sem_sinal "
            "FROM servidores ORDER BY nome")
        for r in rows:
            r["info"] = json.loads(r["info"])
            r["online"] = r["segundos_sem_sinal"] <= 60
        return rows

    # ---------- Eletronanologia (caixas virtuais de energia) ----------
    def _evento_energia(nivel: str | None) -> None:
        if nivel:
            banco.executar("INSERT INTO mensagens (de, para, conteudo) VALUES (?,?,?)",
                           ("asafe", NOME_ADMIN, MENSAGENS[nivel]))

    @app.get("/energia")
    def estado_energia(_: Agente = Depends(agente_atual)):
        return energia.estado()

    @app.post("/energia/queda")
    def queda(_: Agente = Depends(exige("servidores:gerenciar"))):
        energia.queda_de_luz()
        _evento_energia(energia.avancar(0))
        return energia.estado()

    @app.post("/energia/retorno")
    def retorno(_: Agente = Depends(exige("servidores:gerenciar"))):
        energia.retorno_da_luz()
        _evento_energia(energia.avancar(0))
        return energia.estado()

    @app.post("/energia/avancar")
    def avancar(horas: float, _: Agente = Depends(exige("servidores:gerenciar"))):
        if not 0 < horas <= 240:
            raise HTTPException(422, "horas deve estar entre 0 e 240")
        _evento_energia(energia.avancar(horas))
        return energia.estado()

    return app
