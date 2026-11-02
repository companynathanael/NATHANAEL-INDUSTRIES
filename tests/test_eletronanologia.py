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
