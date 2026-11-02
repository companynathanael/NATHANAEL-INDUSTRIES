"""API principal do Asafe.

Cobre: registro de agentes, permissões, comunicação entre IAs, armazenamento
(dados, arquivos, cota e backups), auditoria das ações e gestão de servidores
(métricas, alertas, manutenção e comandos).
"""

import asyncio
import contextlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import __version__
from .armazenamento import (
    NOME_ARQUIVO,
    NOME_BACKUP,
    ArquivoGrande,
    Arquivos,
    CotaExcedida,
    criar_backup,
    limpar_backups,
    listar_backups,
)
from .db import Banco
from .eletronanologia import MENSAGENS, SistemaEletro
from .modelos import (
    AtualizarPermissoes,
    AtualizarServidor,
    NovaMaquina,
    NovaMensagem,
    NovoAgente,
    NovoComando,
    NovoServidor,
    ResultadoComando,
    Sinal,
    Valor,
)
from .seguranca import (
    NOME_ADMIN,
    PERMISSOES,
    gerar_token,
    hash_token,
    tem_alguma,
    tem_permissao,
    tokens_iguais,
)
from .provedores import ErroProvedor, Pedido, carregar_provedores
from .servidores import GestaoServidores

log = logging.getLogger("asafe")
MB = 1024 * 1024


def _env_num(nome: str, padrao: float) -> float:
    return float(os.environ.get(nome, padrao))


@dataclass
class Agente:
    nome: str
    permissoes: set[str]


def _validar_permissoes(perms: list[str]) -> None:
    invalidas = set(perms) - PERMISSOES
    if invalidas:
        raise HTTPException(422, f"Permissões desconhecidas: {sorted(invalidas)}")


def criar_app(caminho_db: str | None = None, token_admin: str | None = None, *,
              pasta_arquivos: str | Path | None = None, pasta_backups: str | Path | None = None,
              relogio: Callable[[], float] = time.time) -> FastAPI:
    caminho_db = caminho_db or os.environ.get("ASAFE_DB", "asafe.db")
    token_admin = token_admin or os.environ.get("ASAFE_ADMIN_TOKEN")
    if not token_admin:
        raise RuntimeError("Defina ASAFE_ADMIN_TOKEN (token do Sr. Nathanael).")
    base = Path(caminho_db).resolve().parent
    pasta_arquivos = Path(pasta_arquivos or os.environ.get("ASAFE_ARQUIVOS", base / "asafe_arquivos"))
    pasta_backups = Path(pasta_backups or os.environ.get("ASAFE_BACKUPS", base / "asafe_backups"))

    # Configuração (variáveis de ambiente, com padrões seguros)
    max_arquivo = int(_env_num("ASAFE_MAX_ARQUIVO_MB", 50) * MB)
    cota = int(_env_num("ASAFE_COTA_MB", 1024) * MB)
    vigia_seg = _env_num("ASAFE_VIGIA_SEG", 15)              # de quanto em quanto tempo checa servidores
    backup_horas = _env_num("ASAFE_BACKUP_HORAS", 24)        # 0 = sem backup automático
    backup_manter = int(_env_num("ASAFE_BACKUP_MANTER", 7))  # quantos backups guardar

    banco = Banco(caminho_db)
    energia = SistemaEletro.padrao(
        n_caixas=int(os.environ.get("ELETRO_CAIXAS", "4")),
        consumo_w=float(os.environ.get("ELETRO_CONSUMO_W", "60")),
    )
    arquivos = Arquivos(banco, pasta_arquivos, max_arquivo, cota)
    gestao = GestaoServidores(banco, relogio)
    provedores = carregar_provedores()
    url_publica = os.environ.get("ASAFE_URL_PUBLICA")  # endereço do Asafe visto pelas máquinas novas

    def fazer_backup() -> dict:
        b = criar_backup(banco, pasta_arquivos, pasta_backups, relogio())
        b["apagados"] = limpar_backups(pasta_backups, backup_manter)
        return b

    # ---------- Tarefas automáticas (rodam enquanto o Asafe estiver no ar) ----------
    async def vigia():
        while True:
            await asyncio.sleep(vigia_seg)
            try:
                for a in gestao.verificar():
                    log.warning("ALERTA: %s", a["mensagem"])
            except Exception:  # o vigia nunca pode morrer
                log.exception("Falha ao verificar servidores")

    async def backup_automatico():
        while True:
            await asyncio.sleep(backup_horas * 3600)
            try:
                b = await asyncio.to_thread(fazer_backup)
                log.info("Backup automático criado: %s", b["nome"])
            except Exception:
                log.exception("Falha no backup automático")

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI):
        tarefas = [asyncio.create_task(vigia())]
        if backup_horas > 0:
            tarefas.append(asyncio.create_task(backup_automatico()))
        try:
            yield
        finally:
            for t in tarefas:
                t.cancel()

    app = FastAPI(title="Asafe", version=__version__, lifespan=ciclo_de_vida,
                  description="Infraestrutura inteligente da Nathanael Industries")
    bearer = HTTPBearer(auto_error=False)

    # Painel (site) pode chamar a API de outro endereço. Tokens vão no cabeçalho, sem cookies.
    origens = [o.strip() for o in os.environ.get("ASAFE_CORS", "*").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origens, allow_methods=["*"],
                       allow_headers=["Authorization", "Content-Type"], expose_headers=["X-Sha256"])
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

    def exige_alguma(*permissoes: str):
        def dep(ag: Agente = Depends(agente_atual)) -> Agente:
            if not tem_alguma(ag.permissoes, *permissoes):
                raise HTTPException(403, f"Permissão necessária: {' ou '.join(permissoes)}")
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

    # ---------- Armazenamento: uso e cota ----------
    @app.get("/armazenamento/uso")
    def uso(ag: Agente = Depends(exige("dados:ler"))):
        return arquivos.uso(ag.nome)

    @app.get("/armazenamento/uso/todos")
    def uso_todos(_: Agente = Depends(so_admin)):
        nomes = [r["nome"] for r in banco.todos("SELECT nome FROM agentes WHERE categoria != 'servidor' ORDER BY nome")]
        return [arquivos.uso(n) for n in nomes]

    # ---------- Armazenamento: arquivos (cada IA tem sua pasta) ----------
    def _nome_arquivo(nome: str) -> str:
        if not NOME_ARQUIVO.match(nome):
            raise HTTPException(422, "Nome de arquivo inválido (use letras, números, espaço, . - _ ( ))")
        return nome

    @app.put("/arquivos/{nome}", status_code=201)
    async def enviar_arquivo(nome: str, request: Request, ag: Agente = Depends(exige("dados:escrever"))):
        _nome_arquivo(nome)
        tamanho = request.headers.get("content-length")
        if tamanho and tamanho.isdigit() and int(tamanho) > max_arquivo:
            raise HTTPException(413, f"Arquivo maior que o limite de {max_arquivo // MB} MB")
        tipo = request.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
        try:
            return await arquivos.salvar(ag.nome, nome, tipo or "application/octet-stream", request.stream())
        except ArquivoGrande:
            raise HTTPException(413, f"Arquivo maior que o limite de {max_arquivo // MB} MB")
        except CotaExcedida:
            raise HTTPException(413, "Cota de armazenamento excedida")

    @app.get("/arquivos")
    def listar_arquivos(ag: Agente = Depends(exige("dados:ler"))):
        return arquivos.listar(ag.nome)

    @app.get("/arquivos/{nome}")
    def baixar_arquivo(nome: str, ag: Agente = Depends(exige("dados:ler"))):
        achado = arquivos.abrir(ag.nome, _nome_arquivo(nome))
        if not achado or not achado[0].exists():
            raise HTTPException(404, "Arquivo não encontrado")
        caminho, meta = achado
        return FileResponse(caminho, media_type=meta["tipo"], filename=nome,
                            headers={"X-Sha256": meta["sha256"]})

    @app.delete("/arquivos/{nome}")
    def apagar_arquivo(nome: str, ag: Agente = Depends(exige("dados:escrever"))):
        if not arquivos.apagar(ag.nome, _nome_arquivo(nome)):
            raise HTTPException(404, "Arquivo não encontrado")
        return {"nome": nome, "apagado": True}

    # ---------- Armazenamento: backups (só o Sr. Nathanael) ----------
    def _backup(nome: str) -> Path:
        caminho = pasta_backups / nome
        if not NOME_BACKUP.match(nome) or not caminho.exists():
            raise HTTPException(404, "Backup não encontrado")
        return caminho

    @app.post("/backups", status_code=201)
    def novo_backup(_: Agente = Depends(so_admin)):
        return fazer_backup()

    @app.get("/backups")
    def backups(_: Agente = Depends(so_admin)):
        return {"backups": listar_backups(pasta_backups), "automatico_a_cada_horas": backup_horas or None,
                "manter": backup_manter}

    @app.get("/backups/{nome}")
    def baixar_backup(nome: str, _: Agente = Depends(so_admin)):
        return FileResponse(_backup(nome), media_type="application/zip", filename=nome)

    @app.delete("/backups/{nome}")
    def apagar_backup(nome: str, _: Agente = Depends(so_admin)):
        _backup(nome).unlink()
        return {"nome": nome, "apagado": True}

    # ---------- Servidores: sinal (enviado pelo próprio servidor) ----------
    @app.post("/servidores/sinal")
    def sinal(s: Sinal, _: Agente = Depends(exige_alguma("servidores:sinal", "servidores:gerenciar"))):
        comandos = gestao.receber_sinal(s.nome, s.endereco, s.info,
                                        {"cpu": s.cpu, "memoria": s.memoria, "disco": s.disco})
        return {"nome": s.nome, "ok": True, "comandos": comandos}

    @app.post("/servidores/{nome}/comandos/{comando_id}/resultado")
    def resultado_comando(nome: str, comando_id: int, r: ResultadoComando,
                          _: Agente = Depends(exige_alguma("servidores:sinal", "servidores:gerenciar"))):
        if not gestao.concluir_comando(nome, comando_id, r.ok, r.saida):
            raise HTTPException(404, "Comando não encontrado ou não entregue")
        return {"id": comando_id, "estado": "concluido" if r.ok else "falhou"}

    # ---------- Servidores: gestão ----------
    gerenciar = exige("servidores:gerenciar")

    def _servidor(nome: str) -> dict:
        s = gestao.obter(nome)
        if not s:
            raise HTTPException(404, "Servidor não encontrado")
        return s

    def _token_do_servidor(nome: str) -> tuple[str, str]:
        """Cria (ou renova) o agente que o servidor usa para mandar sinal. Só pode mandar sinal."""
        agente = ("srv-" + nome)[:40]
        token = gerar_token()
        if banco.um("SELECT 1 FROM agentes WHERE nome=?", (agente,)):
            banco.executar("UPDATE agentes SET token_hash=?, ativo=1 WHERE nome=?", (hash_token(token), agente))
        else:
            banco.executar("INSERT INTO agentes (nome, categoria, versao, token_hash, permissoes) "
                           "VALUES (?, 'servidor', '-', ?, 'servidores:sinal')", (agente, hash_token(token)))
        banco.executar("UPDATE servidores SET agente_sinal=? WHERE nome=?", (agente, nome))
        return agente, token

    def _comando_sentinela(request: Request, nome: str, token: str, intervalo: int) -> str:
        url = (url_publica or str(request.base_url)).rstrip("/")
        return (f"curl -fsSL {url}/sentinela.py -o sentinela.py && "
                f"ASAFE_URL={url} ASAFE_TOKEN={token} SENTINELA_NOME={nome} "
                f"SENTINELA_INTERVALO={intervalo} python3 sentinela.py")

    @app.post("/servidores", status_code=201)
    def cadastrar_servidor(s: NovoServidor, request: Request, gerar_token_sinal: bool = False,
                           _: Agente = Depends(gerenciar)):
        if not gestao.cadastrar(s.nome, s.endereco, s.intervalo, s.limites.model_dump(), s.responsavel):
            raise HTTPException(409, "Servidor já existe")
        resposta = gestao.obter(s.nome)
        if gerar_token_sinal:
            agente, token = _token_do_servidor(s.nome)
            resposta |= {"token": token, "agente_sinal": agente,
                         "comando_sentinela": _comando_sentinela(request, s.nome, token, s.intervalo),
                         "aviso": "Guarde o token: ele não será exibido novamente."}
        return resposta

    # ---------- Criação de máquinas (provedores) ----------
    @app.get("/provedores")
    def listar_provedores(_: Agente = Depends(gerenciar)):
        return [p.info() for p in provedores.values()]

    @app.post("/servidores/criar", status_code=201)
    def criar_maquina(s: NovaMaquina, request: Request, _: Agente = Depends(so_admin)):
        prov = provedores.get(s.provedor)
        if not prov:
            raise HTTPException(422, f"Provedor desconhecido: {s.provedor}")
        ok, motivo = prov.configurado()
        if not ok:
            raise HTTPException(409, f"Provedor {s.provedor} não configurado: {motivo}")
        if not gestao.cadastrar(s.nome, s.endereco, s.intervalo, s.limites.model_dump(), s.responsavel,
                                provedor=s.provedor):
            raise HTTPException(409, "Servidor já existe")
        agente, token = _token_do_servidor(s.nome)
        url = (url_publica or str(request.base_url)).rstrip("/")
        try:
            maq = prov.criar(Pedido(nome=s.nome, asafe_url=url, token=token, intervalo=s.intervalo, opcoes=s.opcoes))
        except ErroProvedor as e:
            gestao.remover(s.nome)
            banco.executar("UPDATE agentes SET ativo=0 WHERE nome=?", (agente,))
            raise HTTPException(502, str(e))
        campos = {"maquina_id": maq.id}
        if maq.endereco:
            campos["endereco"] = maq.endereco
        gestao.atualizar(s.nome, campos)
        return gestao.obter(s.nome) | {"maquina": {"id": maq.id, "estado": maq.estado, **maq.detalhes}}

    painel = os.environ.get("ASAFE_PAINEL")  # pasta do site do Asafe (opcional): abre em /painel/
    if painel and Path(painel).is_dir():
        app.mount("/painel", StaticFiles(directory=painel, html=True), name="painel")

    @app.get("/sentinela.py", response_class=PlainTextResponse)
    def baixar_sentinela():
        """Programa que roda em cada servidor (público: não contém segredos)."""
        return (Path(__file__).parent / "sentinela.py").read_text(encoding="utf-8")

    @app.get("/servidores")
    def servidores(_: Agente = Depends(gerenciar)):
        return gestao.listar()

    @app.get("/servidores/{nome}")
    def detalhes_servidor(nome: str, _: Agente = Depends(gerenciar)):
        s = _servidor(nome)
        s["historico"] = gestao.historico(nome, 20)
        s["alertas_abertos"] = gestao.alertas(True, nome, 50)
        return s

    @app.patch("/servidores/{nome}")
    def atualizar_servidor(nome: str, dados: AtualizarServidor, _: Agente = Depends(gerenciar)):
        _servidor(nome)
        campos = dados.model_dump(exclude_none=True)
        gestao.atualizar(nome, campos)
        return gestao.obter(nome)

    @app.delete("/servidores/{nome}")
    def remover_servidor(nome: str, destruir_maquina: bool = False, ag: Agente = Depends(gerenciar)):
        s = _servidor(nome)
        destruida = False
        if destruir_maquina and s.get("provedor") and s.get("maquina_id"):
            if "*" not in ag.permissoes:
                raise HTTPException(403, "Apenas o Sr. Nathanael pode destruir máquinas")
            prov = provedores.get(s["provedor"])
            if prov:
                try:
                    prov.destruir(s["maquina_id"])
                    destruida = True
                except ErroProvedor as e:
                    raise HTTPException(502, str(e))
        gestao.remover(nome)
        if s.get("agente_sinal"):
            banco.executar("UPDATE agentes SET ativo=0 WHERE nome=?", (s["agente_sinal"],))
        return {"nome": nome, "removido": True, "maquina_destruida": destruida}

    @app.get("/servidores/{nome}/metricas")
    def metricas_servidor(nome: str, limite: int = 100, _: Agente = Depends(gerenciar)):
        _servidor(nome)
        return gestao.historico(nome, limite)

    @app.post("/servidores/{nome}/comandos", status_code=201)
    def pedir_comando(nome: str, c: NovoComando, ag: Agente = Depends(gerenciar)):
        _servidor(nome)
        return gestao.pedir_comando(nome, c.comando, c.args, ag.nome)

    @app.get("/servidores/{nome}/comandos")
    def listar_comandos(nome: str, _: Agente = Depends(gerenciar)):
        _servidor(nome)
        return gestao.comandos(nome)

    @app.post("/servidores/verificar")
    def verificar_agora(_: Agente = Depends(gerenciar)):
        return {"novos_alertas": gestao.verificar()}

    # ---------- Alertas ----------
    @app.get("/alertas")
    def alertas(abertos: bool = True, servidor: str | None = None, limite: int = 100,
                _: Agente = Depends(gerenciar)):
        return gestao.alertas(abertos, servidor, limite)

    @app.post("/alertas/{alerta_id}/resolver")
    def resolver_alerta(alerta_id: int, _: Agente = Depends(gerenciar)):
        if not gestao.resolver_alerta(alerta_id):
            raise HTTPException(404, "Alerta não encontrado ou já resolvido")
        return {"id": alerta_id, "resolvido": True}

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
