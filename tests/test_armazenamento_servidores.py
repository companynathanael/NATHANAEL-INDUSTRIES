"""Testes das partes que estavam parciais: Armazenamento e Servidores."""

import zipfile

import pytest
from fastapi.testclient import TestClient

from asafe import backup as cli_backup
from asafe import sentinela
from asafe.app import criar_app
from asafe.armazenamento import restaurar_backup
from asafe.db import Banco

ADMIN = "token-do-nathanael"


class Relogio:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def avancar(self, seg):
        self.t += seg


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def pastas(tmp_path):
    return {"db": tmp_path / "asafe.db", "arq": tmp_path / "arquivos", "bkp": tmp_path / "backups"}


@pytest.fixture
def cliente(pastas, relogio, monkeypatch):
    monkeypatch.setenv("ASAFE_COTA_MB", "1")          # cota pequena para testar
    monkeypatch.setenv("ASAFE_MAX_ARQUIVO_MB", "0.5")
    monkeypatch.setenv("ASAFE_BACKUP_MANTER", "2")
    return TestClient(criar_app(str(pastas["db"]), ADMIN, pasta_arquivos=pastas["arq"],
                                pasta_backups=pastas["bkp"], relogio=relogio))


def h(token):
    return {"Authorization": f"Bearer {token}"}


def registrar(c, nome, perms, categoria="auxiliar"):
    r = c.post("/agentes", headers=h(ADMIN),
               json={"nome": nome, "categoria": categoria, "versao": "1.0", "permissoes": perms})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def caixa_admin(c):
    return [m["conteudo"] for m in c.get("/mensagens", headers=h(ADMIN)).json()]


# ====================================================================== ARMAZENAMENTO
def test_arquivos_enviar_baixar_substituir_apagar(cliente, pastas):
    t = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    r = cliente.put("/arquivos/relatorio.txt", headers={**h(t), "Content-Type": "text/plain"}, content=b"ola mundo")
    assert r.status_code == 201 and r.json()["tamanho"] == 9

    baixado = cliente.get("/arquivos/relatorio.txt", headers=h(t))
    assert baixado.content == b"ola mundo" and baixado.headers["content-type"].startswith("text/plain")
    assert [a["nome"] for a in cliente.get("/arquivos", headers=h(t)).json()] == ["relatorio.txt"]

    cliente.put("/arquivos/relatorio.txt", headers=h(t), content=b"v2")  # substitui
    assert cliente.get("/arquivos/relatorio.txt", headers=h(t)).content == b"v2"
    assert len([p for p in pastas["arq"].rglob("*") if p.is_file()]) == 1  # versão antiga apagada do disco

    assert cliente.delete("/arquivos/relatorio.txt", headers=h(t)).status_code == 200
    assert cliente.get("/arquivos/relatorio.txt", headers=h(t)).status_code == 404
    assert not [p for p in pastas["arq"].rglob("*") if p.is_file()]


def test_arquivos_isolados_e_permissoes(cliente):
    ta = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    tb = registrar(cliente, "miqueias", ["dados:ler"])
    cliente.put("/arquivos/segredo.txt", headers=h(ta), content=b"so do horacio")
    assert cliente.get("/arquivos/segredo.txt", headers=h(tb)).status_code == 404
    assert cliente.get("/arquivos", headers=h(tb)).json() == []
    assert cliente.put("/arquivos/x.txt", headers=h(tb), content=b"x").status_code == 403


def test_nome_de_arquivo_nao_escapa_da_pasta(cliente, pastas):
    t = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    for nome in ("..", ".oculto", "a%2Fb", "..%2F..%2Fetc"):
        assert cliente.put(f"/arquivos/{nome}", headers=h(t), content=b"x").status_code in (404, 405, 422)
    assert not any(p.is_file() for p in pastas["db"].parent.glob("*") if p.name not in ("asafe.db",))


def test_limite_de_tamanho_e_cota(cliente):
    t = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    meio_mb = 512 * 1024
    assert cliente.put("/arquivos/grande.bin", headers=h(t), content=b"0" * (meio_mb + 1)).status_code == 413
    assert cliente.put("/arquivos/a.bin", headers=h(t), content=b"0" * (meio_mb - 10)).status_code == 201
    assert cliente.put("/arquivos/b.bin", headers=h(t), content=b"0" * (meio_mb - 10)).status_code == 201
    r = cliente.put("/arquivos/c.bin", headers=h(t), content=b"0" * 100)  # passaria da cota de 1 MB
    assert r.status_code == 413 and "Cota" in r.json()["detail"]
    # substituir um arquivo existente desconta o tamanho antigo
    assert cliente.put("/arquivos/a.bin", headers=h(t), content=b"0" * 100).status_code == 201
    uso = cliente.get("/armazenamento/uso", headers=h(t)).json()
    assert uso["arquivos"]["quantidade"] == 2 and uso["cota_bytes"] == 1024 * 1024
    assert uso["total_bytes"] == uso["arquivos"]["bytes"] + uso["dados"]["bytes"]
    assert cliente.get("/armazenamento/uso/todos", headers=h(t)).status_code == 403
    assert [u["agente"] for u in cliente.get("/armazenamento/uso/todos", headers=h(ADMIN)).json()] == ["horacio"]


def test_backup_criar_listar_baixar_reter(cliente, relogio):
    t = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    cliente.put("/dados/agenda", headers=h(t), json={"valor": {"reuniao": "10h"}})
    cliente.put("/arquivos/foto.png", headers=h(t), content=b"\x89PNG...")
    assert cliente.post("/backups", headers=h(t)).status_code == 403  # só o Sr. Nathanael

    nomes = []
    for _ in range(3):
        nomes.append(cliente.post("/backups", headers=h(ADMIN)).json()["nome"])
        relogio.avancar(3600)
    lista = cliente.get("/backups", headers=h(ADMIN)).json()["backups"]
    assert [b["nome"] for b in lista] == nomes[:0:-1]  # só os 2 mais recentes (MANTER=2)

    zipado = cliente.get(f"/backups/{nomes[-1]}", headers=h(ADMIN))
    assert zipado.status_code == 200
    assert cliente.get("/backups/..%2Fasafe.db", headers=h(ADMIN)).status_code == 404
    assert cliente.delete(f"/backups/{nomes[-1]}", headers=h(ADMIN)).status_code == 200


def test_restaurar_backup(cliente, pastas, relogio):
    t = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    cliente.put("/dados/agenda", headers=h(t), json={"valor": "original"})
    cliente.put("/arquivos/doc.txt", headers=h(t), content=b"original")
    nome = cliente.post("/backups", headers=h(ADMIN)).json()["nome"]

    # depois do backup, tudo muda
    cliente.put("/dados/agenda", headers=h(t), json={"valor": "estragado"})
    cliente.delete("/arquivos/doc.txt", headers=h(t))

    m = restaurar_backup(pastas["bkp"] / nome, pastas["db"], pastas["arq"])
    assert m["arquivos"] == 1
    novo = TestClient(criar_app(str(pastas["db"]), ADMIN, pasta_arquivos=pastas["arq"],
                                pasta_backups=pastas["bkp"], relogio=relogio))
    assert novo.get("/dados/agenda", headers=h(t)).json()["valor"] == "original"
    assert novo.get("/arquivos/doc.txt", headers=h(t)).content == b"original"
    assert list(pastas["db"].parent.glob("asafe.db.antes-restauracao-*"))  # estado anterior guardado


def test_restaurar_recusa_zip_malicioso(tmp_path):
    ruim = tmp_path / "ruim.zip"
    with zipfile.ZipFile(ruim, "w") as z:
        z.writestr("asafe.db", b"")
        z.writestr("manifesto.json", "{}")
        z.writestr("arquivos/../../fora.txt", "x")
    with pytest.raises(ValueError):
        restaurar_backup(ruim, tmp_path / "db.db", tmp_path / "arq")
    assert not (tmp_path.parent / "fora.txt").exists()


def test_cli_backup(pastas, monkeypatch, capsys):
    monkeypatch.setenv("ASAFE_DB", str(pastas["db"]))
    monkeypatch.setenv("ASAFE_ARQUIVOS", str(pastas["arq"]))
    monkeypatch.setenv("ASAFE_BACKUPS", str(pastas["bkp"]))
    Banco(pastas["db"]).executar("INSERT INTO dados (agente, chave, valor) VALUES ('h','k','1')")
    assert cli_backup.main(["criar"]) == 0
    assert cli_backup.main(["listar"]) == 0
    nome = next(pastas["bkp"].glob("asafe-*.zip")).name
    assert nome in capsys.readouterr().out
    Banco(pastas["db"]).executar("DELETE FROM dados")
    assert cli_backup.main(["restaurar", nome, "--sim"]) == 0
    assert Banco(pastas["db"]).um("SELECT valor FROM dados WHERE chave='k'")["valor"] == "1"


def test_banco_antigo_e_migrado(tmp_path):
    import sqlite3
    caminho = tmp_path / "antigo.db"
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE servidores (nome TEXT PRIMARY KEY, endereco TEXT NOT NULL, "
                "info TEXT NOT NULL DEFAULT '{}', ultimo_sinal TEXT NOT NULL DEFAULT (datetime('now')))")
    con.execute("INSERT INTO servidores (nome, endereco) VALUES ('velho', '1.1.1.1')")
    con.commit()
    con.close()
    c = TestClient(criar_app(str(caminho), ADMIN))
    s = c.get("/servidores", headers=h(ADMIN)).json()
    assert s[0]["nome"] == "velho" and s[0]["status"] == "offline" and s[0]["intervalo"] == 30


# ====================================================================== SERVIDORES
def sinal(c, token, nome="srv-01", **metricas):
    r = c.post("/servidores/sinal", headers=h(token),
               json={"nome": nome, "endereco": "10.0.0.5", "info": {"papel": "ia"}, **metricas})
    assert r.status_code == 200, r.text
    return r.json()


def test_cadastro_e_estados(cliente, relogio):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    r = cliente.post("/servidores", headers=h(tg), json={"nome": "srv-01", "endereco": "10.0.0.5", "intervalo": 10})
    assert r.status_code == 201 and r.json()["status"] == "offline"  # ainda não mandou sinal
    assert cliente.post("/servidores", headers=h(tg), json={"nome": "srv-01", "endereco": "x"}).status_code == 409

    sinal(cliente, tg, cpu=10, memoria=20, disco=30)
    s = cliente.get("/servidores/srv-01", headers=h(tg)).json()
    assert s["status"] == "online" and s["metricas"] == {"cpu": 10, "memoria": 20, "disco": 30}
    assert s["intervalo"] == 10 and s["historico"][0]["cpu"] == 10

    relogio.avancar(15)   # 1,5 intervalo: ainda online
    assert cliente.get("/servidores/srv-01", headers=h(tg)).json()["status"] == "online"
    relogio.avancar(10)   # 2,5 intervalos sem sinal: offline
    assert cliente.get("/servidores/srv-01", headers=h(tg)).json()["status"] == "offline"


def test_alerta_quando_cai_e_quando_volta(cliente, relogio):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    sinal(cliente, tg)
    assert cliente.post("/servidores/verificar", headers=h(tg)).json()["novos_alertas"] == []

    relogio.avancar(61)
    novos = cliente.post("/servidores/verificar", headers=h(tg)).json()["novos_alertas"]
    assert [a["tipo"] for a in novos] == ["caiu"]
    assert cliente.post("/servidores/verificar", headers=h(tg)).json()["novos_alertas"] == []  # não repete
    assert [a["tipo"] for a in cliente.get("/alertas", headers=h(tg)).json()] == ["caiu"]
    assert any("parou de responder" in m for m in caixa_admin(cliente))  # Sr. Nathanael avisado

    sinal(cliente, tg)  # voltou
    assert cliente.get("/alertas", headers=h(tg)).json() == []  # "caiu" resolvido
    historico = cliente.get("/alertas?abertos=false", headers=h(tg)).json()
    assert [a["tipo"] for a in historico] == ["voltou", "caiu"]
    assert any("voltou a responder" in m for m in caixa_admin(cliente))


def test_alertas_de_metricas_e_limites(cliente):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    cliente.post("/servidores", headers=h(tg),
                 json={"nome": "srv-01", "endereco": "10.0.0.5", "limites": {"cpu": 80}})
    sinal(cliente, tg, cpu=85, disco=95)
    assert sorted(a["tipo"] for a in cliente.get("/alertas", headers=h(tg)).json()) == ["cpu", "disco"]
    sinal(cliente, tg, cpu=90, disco=96)  # continua alto: não duplica
    assert len(cliente.get("/alertas", headers=h(tg)).json()) == 2
    sinal(cliente, tg, cpu=40, disco=96)  # cpu normalizou
    assert [a["tipo"] for a in cliente.get("/alertas", headers=h(tg)).json()] == ["disco"]

    cliente.patch("/servidores/srv-01", headers=h(tg), json={"limites": {"disco": 99}})
    sinal(cliente, tg, cpu=40, disco=96)
    assert cliente.get("/alertas", headers=h(tg)).json() == []
    aid = cliente.get("/alertas?abertos=false", headers=h(tg)).json()[0]["id"]
    assert cliente.post(f"/alertas/{aid}/resolver", headers=h(tg)).status_code == 404  # já resolvido
    assert len(cliente.get("/servidores/srv-01/metricas", headers=h(tg)).json()) == 4


def test_manutencao_silencia_alertas(cliente, relogio):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    sinal(cliente, tg)
    s = cliente.patch("/servidores/srv-01", headers=h(tg), json={"manutencao": True}).json()
    assert s["status"] == "manutencao"
    relogio.avancar(600)
    assert cliente.post("/servidores/verificar", headers=h(tg)).json()["novos_alertas"] == []
    sinal(cliente, tg, cpu=99)
    assert cliente.get("/alertas", headers=h(tg)).json() == []
    cliente.patch("/servidores/srv-01", headers=h(tg), json={"manutencao": False})
    assert cliente.get("/servidores/srv-01", headers=h(tg)).json()["status"] == "online"


def test_comandos_remotos(cliente):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    ts = registrar(cliente, "srv-agente", ["servidores:sinal"])  # token do próprio servidor
    sinal(cliente, ts)
    assert cliente.get("/servidores", headers=h(ts)).status_code == 403  # servidor não gerencia
    assert cliente.post("/servidores/srv-01/comandos", headers=h(tg), json={"comando": "formatar"}).status_code == 422
    c = cliente.post("/servidores/srv-01/comandos", headers=h(tg), json={"comando": "reiniciar"}).json()
    assert c["estado"] == "pendente"

    entregues = sinal(cliente, ts)["comandos"]
    assert [x["comando"] for x in entregues] == ["reiniciar"]
    assert sinal(cliente, ts)["comandos"] == []  # entregue uma vez só
    r = cliente.post(f"/servidores/srv-01/comandos/{c['id']}/resultado", headers=h(ts), json={"ok": True, "saida": "ok"})
    assert r.json()["estado"] == "concluido"
    hist = cliente.get("/servidores/srv-01/comandos", headers=h(tg)).json()
    assert hist[0]["estado"] == "concluido" and hist[0]["pedido_por"] == "gather"


def test_remover_servidor(cliente):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    sinal(cliente, tg, cpu=99)
    assert cliente.delete("/servidores/srv-01", headers=h(tg)).status_code == 200
    assert cliente.get("/servidores/srv-01", headers=h(tg)).status_code == 404
    assert cliente.get("/alertas", headers=h(tg)).json() == []


def test_sentinela_conversa_com_o_asafe(cliente, monkeypatch):
    """O sentinela real (sem rede): troca a chamada HTTP pelo TestClient."""
    tg = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    ts = registrar(cliente, "srv-agente", ["servidores:sinal"])

    def post_fake(_url, token, caminho, corpo):
        return cliente.post(caminho, headers=h(token), json=corpo).json()

    monkeypatch.setattr(sentinela, "_post", post_fake)
    monkeypatch.setattr(sentinela, "_cpu_pct", lambda: 12.5)
    monkeypatch.setenv("SENTINELA_CMD_LIMPAR_CACHE", "echo cache limpo")

    sentinela.ciclo("http://asafe", ts, "srv-01", "10.0.0.5")
    s = cliente.get("/servidores/srv-01", headers=h(tg)).json()
    assert s["status"] == "online" and s["metricas"]["cpu"] == 12.5

    cliente.post("/servidores/srv-01/comandos", headers=h(tg), json={"comando": "limpar_cache"})
    cliente.post("/servidores/srv-01/comandos", headers=h(tg), json={"comando": "parar"})
    sentinela.ciclo("http://asafe", ts, "srv-01", "10.0.0.5")
    hist = {c["comando"]: c for c in cliente.get("/servidores/srv-01/comandos", headers=h(tg)).json()}
    assert hist["limpar_cache"]["estado"] == "concluido" and "cache limpo" in hist["limpar_cache"]["resultado"]
    assert hist["parar"]["estado"] == "falhou" and "não configurado" in hist["parar"]["resultado"]


def test_vigia_automatico_roda_em_segundo_plano(pastas, relogio, monkeypatch):
    import time
    monkeypatch.setenv("ASAFE_VIGIA_SEG", "0.05")
    app = criar_app(str(pastas["db"]), ADMIN, pasta_arquivos=pastas["arq"],
                    pasta_backups=pastas["bkp"], relogio=relogio)
    with TestClient(app) as c:  # "with" liga as tarefas automáticas
        tg = registrar(c, "gather", ["servidores:gerenciar"], "desenvolvedor")
        sinal(c, tg)
        relogio.avancar(120)
        for _ in range(40):
            if c.get("/alertas", headers=h(tg)).json():
                break
            time.sleep(0.05)
        assert [a["tipo"] for a in c.get("/alertas", headers=h(tg)).json()] == ["caiu"]
