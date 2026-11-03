from fastapi.testclient import TestClient

from asafe.app import criar_app
from asafe.eletronanologia import SistemaEletro

ADMIN = {"Authorization": "Bearer adm"}


def test_dimensionamento_cobre_48h():
    s = SistemaEletro.padrao(n_caixas=4, consumo_w=60)
    assert len(s.caixas) == 4
    assert s.autonomia_horas == 48.0


def test_descarga_sequencial_e_niveis():
    s = SistemaEletro.padrao(n_caixas=4, consumo_w=60)
    s.queda_de_luz()
    assert s.avancar(0) == "bateria"
    s.avancar(12)                                # 1ª caixa esvazia
    assert [c.pct for c in s.caixas] == [0.0, 100.0, 100.0, 100.0]
    assert s.avancar(24) == "aviso"              # 36 h -> 25%
    assert s.avancar(8) == "critico"             # 44 h -> ~8%
    assert s.avancar(10) == "desligado"
    s.retorno_da_luz()
    assert s.avancar(1) == "normal" and s.carga_wh > 0


def test_api_energia_e_alertas_para_nathanael(tmp_path):
    c = TestClient(criar_app(str(tmp_path / "t.db"), "adm"))
    assert c.get("/energia", headers=ADMIN).json()["nivel"] == "normal"
    assert c.post("/energia/queda", headers=ADMIN).json()["nivel"] == "bateria"
    assert c.post("/energia/avancar?horas=40", headers=ADMIN).json()["nivel"] == "aviso"
    alertas = [m["conteudo"] for m in c.get("/mensagens", headers=ADMIN).json()]
    assert len(alertas) == 2 and "A luz caiu" in alertas[0]
    assert c.post("/energia/retorno", headers=ADMIN).json()["nivel"] == "normal"
    assert c.post("/energia/avancar?horas=0", headers=ADMIN).status_code == 422


# ====================================================================== versão completa (03/11)
import pytest

from asafe.eletronanologia import nivel_da_fonte


class Relogio:
    def __init__(self):
        self.t = 1_800_000_000.0

    def __call__(self):
        return self.t

    def horas(self, h):
        self.t += h * 3600


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    for v in ("ELETRO_CAIXAS", "ELETRO_CONSUMO_W", "ASAFE_ENERGIA_CMD_DESLIGAR"):
        monkeypatch.delenv(v, raising=False)
    rel = Relogio()

    def novo_app():
        return TestClient(criar_app(str(tmp_path / "t.db"), "adm", pasta_arquivos=tmp_path / "arq",
                                    pasta_backups=tmp_path / "bkp", relogio=rel))
    return {"rel": rel, "novo": novo_app, "bkp": tmp_path / "bkp"}


def msgs(c):
    return [m["conteudo"] for m in c.get("/mensagens?apenas_nao_lidas=false", headers=ADMIN).json()]


def test_estado_sobrevive_a_reinicio(ambiente):
    c = ambiente["novo"]()
    c.post("/energia/queda", headers=ADMIN)
    c.post("/energia/avancar?horas=12", headers=ADMIN)
    antes = c.get("/energia", headers=ADMIN).json()
    assert antes["carga_pct"] == 75.0 and antes["na_rede_eletrica"] is False

    c2 = ambiente["novo"]()  # Asafe reiniciou
    depois = c2.get("/energia", headers=ADMIN).json()
    assert depois["carga_pct"] == 75.0 and depois["nivel"] == "bateria"
    assert [x["carga_pct"] for x in depois["caixas"]] == [0.0, 100.0, 100.0, 100.0]


def test_descarga_em_tempo_real(ambiente):
    c = ambiente["novo"]()
    c.post("/energia/queda", headers=ADMIN)
    ambiente["rel"].horas(24)  # um dia sem luz, sem ninguém simular nada
    e = c.get("/energia", headers=ADMIN).json()
    assert e["carga_pct"] == 50.0 and e["horas_sem_luz"] == 24.0 and e["autonomia_horas"] == 24.0
    c.post("/energia/retorno", headers=ADMIN)
    ambiente["rel"].horas(2)   # com luz, recarrega
    assert c.get("/energia", headers=ADMIN).json()["carga_pct"] > 50.0


def test_critico_faz_backup_e_desligamento_seguro(ambiente):
    c = ambiente["novo"]()
    r = c.post("/agentes", headers=ADMIN, json={"nome": "horacio", "categoria": "auxiliar", "versao": "1",
                                               "permissoes": ["dados:escrever", "dados:ler"]})
    th = {"Authorization": f"Bearer {r.json()['token']}"}
    assert c.put("/dados/x", headers=th, json={"valor": 1}).status_code == 200

    c.post("/energia/queda", headers=ADMIN)
    e = c.post("/energia/avancar?horas=44", headers=ADMIN).json()
    assert e["nivel"] == "critico" and e["modo_protegido"] is True
    assert list(ambiente["bkp"].glob("asafe-*.zip")), "backup de emergência não foi criado"
    tipos = [ev["tipo"] for ev in c.get("/energia/eventos", headers=ADMIN).json()]
    assert "backup" in tipos and "desligamento" in tipos
    assert any("Energia crítica" in m for m in msgs(c))

    # modo protegido: IAs não gravam; leitura, sinal dos servidores e o Sr. Nathanael continuam
    bloq = c.put("/dados/x", headers=th, json={"valor": 2})
    assert bloq.status_code == 503 and "modo protegido" in bloq.json()["detail"]
    assert c.get("/dados/x", headers=th).json()["valor"] == 1
    assert c.post("/servidores/sinal", headers=ADMIN, json={"nome": "srv-01", "endereco": "x"}).status_code == 200
    assert c.put("/dados/y", headers=ADMIN, json={"valor": 1}).status_code == 200

    c.post("/energia/retorno", headers=ADMIN)
    assert c.get("/energia", headers=ADMIN).json()["modo_protegido"] is False
    assert c.put("/dados/x", headers=th, json={"valor": 3}).status_code == 200


def test_comando_de_desligamento_configurado(ambiente, monkeypatch):
    monkeypatch.setenv("ASAFE_ENERGIA_CMD_DESLIGAR", "echo desligando")
    c = ambiente["novo"]()
    c.post("/energia/queda", headers=ADMIN)
    c.post("/energia/avancar?horas=44", headers=ADMIN)
    deslig = [ev for ev in c.get("/energia/eventos", headers=ADMIN).json() if ev["tipo"] == "desligamento"]
    assert "código 0" in deslig[0]["mensagem"]


def test_asafe_desligado_muito_tempo_nao_pula_o_critico(ambiente):
    c = ambiente["novo"]()
    c.post("/energia/queda", headers=ADMIN)
    ambiente["rel"].horas(60)  # mais que as 48 h de autonomia
    e = c.get("/energia", headers=ADMIN).json()
    assert e["nivel"] == "desligado" and e["carga_pct"] == 0.0
    niveis = [ev["nivel"] for ev in c.get("/energia/eventos", headers=ADMIN).json() if ev["tipo"] == "nivel"]
    assert niveis[::-1] == ["bateria", "aviso", "critico", "desligado"]
    assert list(ambiente["bkp"].glob("asafe-*.zip"))


def test_energia_real_vinda_do_sinal_dos_servidores(ambiente):
    c = ambiente["novo"]()

    def sinal(info):
        r = c.post("/servidores/sinal", headers=ADMIN, json={"nome": "eletro-01", "endereco": "10.0.0.20", "info": info})
        assert r.status_code == 200

    sinal({"na_rede_eletrica": True, "bateria_pct": 100, "autonomia_min": 120})
    assert c.get("/energia", headers=ADMIN).json()["na_rede_eletrica"] is True

    sinal({"na_rede_eletrica": False, "bateria_pct": 72, "autonomia_min": 95})  # a luz caiu de verdade
    e = c.get("/energia", headers=ADMIN).json()
    assert e["na_rede_eletrica"] is False and e["nivel"] == "bateria"  # as caixas do Asafe assumem
    fonte = e["fontes"][0]
    assert fonte["servidor"] == "eletro-01" and fonte["nivel"] == "bateria" and fonte["autonomia_min"] == 95
    assert any("[eletro-01]" in m and "72%" in m for m in msgs(c))

    sinal({"na_rede_eletrica": False, "bateria_pct": 20, "autonomia_min": 25})
    assert c.get("/energia", headers=ADMIN).json()["fontes"][0]["nivel"] == "aviso"
    assert any("[eletro-01]" in m and "25%" in m for m in msgs(c))

    sinal({"na_rede_eletrica": True, "bateria_pct": 21})  # luz voltou
    e = c.get("/energia", headers=ADMIN).json()
    assert e["na_rede_eletrica"] is True and e["fontes"][0]["nivel"] == "normal"


def test_sinal_sem_energia_nao_muda_nada(ambiente):
    c = ambiente["novo"]()
    c.post("/servidores/sinal", headers=ADMIN, json={"nome": "srv-01", "endereco": "x", "info": {"papel": "ia"}})
    e = c.get("/energia", headers=ADMIN).json()
    assert e["fontes"] == [] and e["na_rede_eletrica"] is True


def test_mudar_numero_de_caixas_mantem_a_carga(ambiente, monkeypatch):
    c = ambiente["novo"]()
    c.post("/energia/queda", headers=ADMIN)
    c.post("/energia/avancar?horas=12", headers=ADMIN)  # 75%
    monkeypatch.setenv("ELETRO_CAIXAS", "3")
    e = ambiente["novo"]().get("/energia", headers=ADMIN).json()
    assert len(e["caixas"]) == 3 and e["carga_pct"] == 75.0 and e["autonomia_horas"] == 36.0


def test_nivel_da_fonte():
    assert nivel_da_fonte(True, 5) == "normal"
    assert nivel_da_fonte(False, None) == "bateria"
    assert [nivel_da_fonte(False, p) for p in (80, 25, 10, 0)] == ["bateria", "aviso", "critico", "desligado"]
