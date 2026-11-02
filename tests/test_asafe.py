import pytest
from fastapi.testclient import TestClient

from asafe.app import criar_app

ADMIN = "token-do-nathanael"


@pytest.fixture
def cliente(tmp_path):
    return TestClient(criar_app(str(tmp_path / "t.db"), ADMIN))


def h(token):
    return {"Authorization": f"Bearer {token}"}


def registrar(c, nome, perms, categoria="auxiliar"):
    r = c.post("/agentes", headers=h(ADMIN),
               json={"nome": nome, "categoria": categoria, "versao": "1.0", "permissoes": perms})
    assert r.status_code == 201, r.text
    return r.json()["token"]


def test_saude(cliente):
    assert cliente.get("/saude").json()["status"] == "ok"


def test_sem_token_e_token_invalido(cliente):
    assert cliente.get("/eu").status_code == 401
    assert cliente.get("/eu", headers=h("falso")).status_code == 401


def test_so_admin_registra_agentes(cliente):
    t = registrar(cliente, "horacio", ["agentes:ler"])
    r = cliente.post("/agentes", headers=h(t),
                     json={"nome": "x1", "categoria": "auxiliar", "versao": "1", "permissoes": []})
    assert r.status_code == 403
    assert registrar(cliente, "miqueias", [])  # admin consegue
    dup = cliente.post("/agentes", headers=h(ADMIN),
                       json={"nome": "horacio", "categoria": "auxiliar", "versao": "1", "permissoes": []})
    assert dup.status_code == 409


def test_permissao_desconhecida(cliente):
    r = cliente.post("/agentes", headers=h(ADMIN),
                     json={"nome": "y1", "categoria": "auxiliar", "versao": "1", "permissoes": ["voar"]})
    assert r.status_code == 422


def test_mensagens_entre_ias(cliente):
    th = registrar(cliente, "horacio", ["mensagens:enviar", "mensagens:ler"])
    tm = registrar(cliente, "miqueias", ["mensagens:ler"])
    assert cliente.post("/mensagens", headers=h(th), json={"para": "miqueias", "conteudo": "calcule 2+2"}).status_code == 201
    assert cliente.post("/mensagens", headers=h(tm), json={"para": "horacio", "conteudo": "4"}).status_code == 403
    caixa = cliente.get("/mensagens", headers=h(tm)).json()
    assert [m["conteudo"] for m in caixa] == ["calcule 2+2"] and caixa[0]["de"] == "horacio"
    assert cliente.get("/mensagens", headers=h(tm)).json() == []  # já lida
    assert cliente.post("/mensagens", headers=h(th), json={"para": "ninguem", "conteudo": "oi"}).status_code == 404
    assert cliente.post("/mensagens", headers=h(th), json={"para": "nathanael", "conteudo": "relatório"}).status_code == 201
    assert cliente.get("/mensagens", headers=h(ADMIN)).json()[0]["conteudo"] == "relatório"


def test_dados_isolados_por_agente(cliente):
    ta = registrar(cliente, "horacio", ["dados:ler", "dados:escrever"])
    tb = registrar(cliente, "miqueias", ["dados:ler", "dados:escrever"])
    cliente.put("/dados/agenda", headers=h(ta), json={"valor": {"reuniao": "10h"}})
    assert cliente.get("/dados/agenda", headers=h(ta)).json()["valor"] == {"reuniao": "10h"}
    assert cliente.get("/dados/agenda", headers=h(tb)).status_code == 404
    assert cliente.get("/dados", headers=h(ta)).json() == ["agenda"]
    assert cliente.delete("/dados/agenda", headers=h(ta)).status_code == 200
    assert cliente.get("/dados/agenda", headers=h(ta)).status_code == 404


def test_desativar_e_trocar_permissoes(cliente):
    t = registrar(cliente, "horacio", [])
    assert cliente.get("/agentes", headers=h(t)).status_code == 403
    cliente.put("/agentes/horacio/permissoes", headers=h(ADMIN), json={"permissoes": ["agentes:ler"]})
    assert cliente.get("/agentes", headers=h(t)).status_code == 200
    cliente.post("/agentes/horacio/ativo?ativo=false", headers=h(ADMIN))
    assert cliente.get("/eu", headers=h(t)).status_code == 401
    cliente.post("/agentes/horacio/ativo?ativo=true", headers=h(ADMIN))
    novo = cliente.post("/agentes/horacio/novo-token", headers=h(ADMIN)).json()["token"]
    assert cliente.get("/eu", headers=h(t)).status_code == 401
    assert cliente.get("/eu", headers=h(novo)).json()["nome"] == "horacio"


def test_auditoria_registra_acoes(cliente):
    t = registrar(cliente, "horacio", [])
    cliente.get("/agentes", headers=h(t))  # negado, mas registrado
    log = cliente.get("/auditoria?agente=horacio", headers=h(ADMIN)).json()
    assert log[0]["alvo"] == "/agentes" and log[0]["status"] == 403


def test_servidores(cliente):
    t = registrar(cliente, "gather", ["servidores:gerenciar"], "desenvolvedor")
    cliente.post("/servidores/sinal", headers=h(t), json={"nome": "srv-01", "endereco": "10.0.0.5", "info": {"cpu": 12}})
    s = cliente.get("/servidores", headers=h(t)).json()
    assert s[0]["nome"] == "srv-01" and s[0]["online"] is True and s[0]["info"] == {"cpu": 12}
