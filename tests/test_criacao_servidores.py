"""Criação de servidores: cadastro com token, provedores (local e Oracle) e acesso do painel."""

import base64
import os
import sys
import time
import types

import pytest
from fastapi.testclient import TestClient

from asafe.app import criar_app
from asafe.provedores import Pedido, script_inicial

ADMIN = "token-do-nathanael"


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    for v in ("OCI_COMPARTMENT_ID", "OCI_SUBNET_ID", "OCI_IMAGE_ID", "OCI_AVAILABILITY_DOMAIN",
              "ASAFE_PROVEDOR_LOCAL", "ASAFE_URL_PUBLICA"):
        monkeypatch.delenv(v, raising=False)


@pytest.fixture
def cliente(tmp_path):
    return TestClient(criar_app(str(tmp_path / "t.db"), ADMIN, pasta_arquivos=tmp_path / "a",
                                pasta_backups=tmp_path / "b"))


def registrar(c, nome, perms):
    r = c.post("/agentes", headers=h(ADMIN),
               json={"nome": nome, "categoria": "desenvolvedor", "versao": "1", "permissoes": perms})
    return r.json()["token"]


# ------------------------------------------------------------------ cadastro com token
def test_cadastrar_gera_token_e_comando_do_sentinela(cliente):
    r = cliente.post("/servidores?gerar_token_sinal=true", headers=h(ADMIN),
                     json={"nome": "srv-01", "endereco": "10.0.0.5", "intervalo": 20})
    assert r.status_code == 201
    d = r.json()
    assert d["token"].startswith("asf_") and d["agente_sinal"] == "srv-srv-01"
    assert "sentinela.py" in d["comando_sentinela"] and d["token"] in d["comando_sentinela"]
    assert "SENTINELA_INTERVALO=20" in d["comando_sentinela"]

    # o token só serve para mandar sinal
    t = d["token"]
    ok = cliente.post("/servidores/sinal", headers=h(t), json={"nome": "srv-01", "endereco": "10.0.0.5", "cpu": 5})
    assert ok.status_code == 200
    assert cliente.get("/servidores", headers=h(t)).status_code == 403
    assert cliente.get("/servidores/srv-01", headers=h(ADMIN)).json()["status"] == "online"

    # remover o servidor desativa o token dele
    cliente.delete("/servidores/srv-01", headers=h(ADMIN))
    assert cliente.post("/servidores/sinal", headers=h(t), json={"nome": "srv-01", "endereco": "x"}).status_code == 401


def test_sentinela_e_baixado_sem_token(cliente):
    r = cliente.get("/sentinela.py")
    assert r.status_code == 200 and "def ciclo" in r.text


def test_painel_pode_chamar_a_api(cliente):
    r = cliente.options("/servidores", headers={"Origin": "http://localhost:5500",
                                                 "Access-Control-Request-Method": "GET",
                                                 "Access-Control-Request-Headers": "authorization"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] in ("*", "http://localhost:5500")


def test_painel_servido_pelo_asafe(tmp_path, monkeypatch):
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<title>Asafe</title>")
    monkeypatch.setenv("ASAFE_PAINEL", str(tmp_path / "site"))
    c = TestClient(criar_app(str(tmp_path / "t.db"), ADMIN))
    assert "<title>Asafe</title>" in c.get("/painel/").text


# ------------------------------------------------------------------ provedores
def test_lista_provedores(cliente):
    p = {x["nome"]: x for x in cliente.get("/provedores", headers=h(ADMIN)).json()}
    assert p["local"]["configurado"] is True
    assert p["oracle"]["configurado"] is False and p["oracle"]["motivo"]


def test_script_inicial_instala_o_sentinela():
    s = script_inicial(Pedido(nome="srv-09", asafe_url="https://asafe.exemplo.com/", token="asf_x", intervalo=15))
    assert "https://asafe.exemplo.com/sentinela.py" in s
    assert "ASAFE_TOKEN=asf_x" in s and "SENTINELA_NOME=srv-09" in s and "SENTINELA_INTERVALO=15" in s
    assert "systemctl enable --now asafe-sentinela" in s


def test_so_o_admin_cria_maquinas(cliente):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"])
    r = cliente.post("/servidores/criar", headers=h(tg), json={"nome": "srv-02", "provedor": "local"})
    assert r.status_code == 403


def test_provedor_desconhecido_ou_nao_configurado(cliente):
    assert cliente.post("/servidores/criar", headers=h(ADMIN),
                        json={"nome": "srv-02", "provedor": "marte"}).status_code == 422
    r = cliente.post("/servidores/criar", headers=h(ADMIN), json={"nome": "srv-02", "provedor": "oracle"})
    assert r.status_code == 409 and "não configurado" in r.json()["detail"]
    assert cliente.get("/servidores/srv-02", headers=h(ADMIN)).status_code == 404  # nada ficou pela metade


def test_provedor_local_cria_e_destroi_processo(cliente):
    r = cliente.post("/servidores/criar", headers=h(ADMIN),
                     json={"nome": "srv-local", "provedor": "local", "intervalo": 5})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["status"] == "criando" and d["provedor"] == "local" and d["maquina_id"].startswith("local-")
    pid = int(d["maquina_id"].removeprefix("local-"))
    os.kill(pid, 0)  # o processo existe

    r = cliente.delete("/servidores/srv-local?destruir_maquina=true", headers=h(ADMIN))
    assert r.json()["maquina_destruida"] is True
    for _ in range(50):
        try:
            os.kill(pid, 0)
            time.sleep(0.05)
        except ProcessLookupError:
            break
    else:
        pytest.fail("processo do provedor local não foi encerrado")


def test_gerenciar_nao_destroi_maquina(cliente):
    tg = registrar(cliente, "gather", ["servidores:gerenciar"])
    cliente.post("/servidores/criar", headers=h(ADMIN), json={"nome": "srv-local", "provedor": "local"})
    assert cliente.delete("/servidores/srv-local?destruir_maquina=true", headers=h(tg)).status_code == 403
    cliente.delete("/servidores/srv-local?destruir_maquina=true", headers=h(ADMIN))


# ------------------------------------------------------------------ Oracle (cliente falso)
class FakeCompute:
    def __init__(self, falhar=False):
        self.lancadas, self.encerradas, self.falhar = [], [], falhar

    def launch_instance(self, detalhes):
        if self.falhar:
            raise RuntimeError("Out of host capacity")
        self.lancadas.append(detalhes)
        return types.SimpleNamespace(data=types.SimpleNamespace(id="ocid1.instance.xyz", lifecycle_state="PROVISIONING"))

    def terminate_instance(self, mid):
        self.encerradas.append(mid)

    def get_instance(self, mid):
        return types.SimpleNamespace(data=types.SimpleNamespace(lifecycle_state="RUNNING"))


def _oci_falso(compute):
    class Modelo:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    models = types.SimpleNamespace(**{n: Modelo for n in (
        "LaunchInstanceDetails", "InstanceSourceViaImageDetails", "CreateVnicDetails",
        "LaunchInstanceShapeConfigDetails")})
    return types.SimpleNamespace(
        config=types.SimpleNamespace(from_file=lambda *a: {}),
        core=types.SimpleNamespace(models=models, ComputeClient=lambda cfg: compute))


@pytest.fixture
def oracle(monkeypatch):
    compute = FakeCompute()
    monkeypatch.setitem(sys.modules, "oci", _oci_falso(compute))
    for v, val in {"OCI_COMPARTMENT_ID": "ocid1.compartment", "OCI_SUBNET_ID": "ocid1.subnet",
                   "OCI_IMAGE_ID": "ocid1.image", "OCI_AVAILABILITY_DOMAIN": "xx:SA-SAOPAULO-1-AD-1"}.items():
        monkeypatch.setenv(v, val)
    monkeypatch.setenv("ASAFE_URL_PUBLICA", "https://asafe.exemplo.com")
    return compute


def test_oracle_cria_maquina_que_liga_o_sentinela(oracle, cliente):
    r = cliente.post("/servidores/criar", headers=h(ADMIN),
                     json={"nome": "srv-nuvem", "provedor": "oracle", "intervalo": 30})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["maquina_id"] == "ocid1.instance.xyz" and d["status"] == "criando"
    det = oracle.lancadas[0]
    assert det.shape == "VM.Standard.E2.1.Micro" and det.create_vnic_details.assign_public_ip is True
    script = base64.b64decode(det.metadata["user_data"]).decode()
    assert "https://asafe.exemplo.com/sentinela.py" in script and "SENTINELA_NOME=srv-nuvem" in script

    # a máquina liga e manda o primeiro sinal com o token que foi no script
    token = script.split("ASAFE_TOKEN=")[1].split()[0]
    cliente.post("/servidores/sinal", headers=h(token), json={"nome": "srv-nuvem", "endereco": "150.1.2.3", "cpu": 3})
    s = cliente.get("/servidores/srv-nuvem", headers=h(ADMIN)).json()
    assert s["status"] == "online" and s["endereco"] == "150.1.2.3"

    cliente.delete("/servidores/srv-nuvem?destruir_maquina=true", headers=h(ADMIN))
    assert oracle.encerradas == ["ocid1.instance.xyz"]


def test_oracle_recusa_e_nada_fica_pela_metade(oracle, cliente):
    oracle.falhar = True
    r = cliente.post("/servidores/criar", headers=h(ADMIN), json={"nome": "srv-nuvem", "provedor": "oracle"})
    assert r.status_code == 502 and "capacity" in r.json()["detail"]
    assert cliente.get("/servidores/srv-nuvem", headers=h(ADMIN)).status_code == 404
    agentes = {a["nome"]: a for a in cliente.get("/agentes", headers=h(ADMIN)).json()}
    assert agentes["srv-srv-nuvem"]["ativo"] is False


def test_sinal_sem_endereco_nao_apaga_o_conhecido(cliente):
    cliente.post("/servidores", headers=h(ADMIN), json={"nome": "srv-01", "endereco": "10.0.0.5"})
    cliente.post("/servidores/sinal", headers=h(ADMIN), json={"nome": "srv-01", "endereco": "desconhecido"})
    assert cliente.get("/servidores/srv-01", headers=h(ADMIN)).json()["endereco"] == "10.0.0.5"
    cliente.post("/servidores/sinal", headers=h(ADMIN), json={"nome": "srv-01", "endereco": "10.0.0.9"})
    assert cliente.get("/servidores/srv-01", headers=h(ADMIN)).json()["endereco"] == "10.0.0.9"


def test_uso_todos_ignora_agentes_de_servidor(cliente):
    registrar(cliente, "horacio", ["dados:ler"])
    cliente.post("/servidores?gerar_token_sinal=true", headers=h(ADMIN), json={"nome": "srv-01", "endereco": "x"})
    assert [u["agente"] for u in cliente.get("/armazenamento/uso/todos", headers=h(ADMIN)).json()] == ["horacio"]


def test_sentinela_descobre_o_proprio_endereco():
    from asafe.sentinela import descobrir_endereco
    assert descobrir_endereco("http://127.0.0.1:8000") == "127.0.0.1"
