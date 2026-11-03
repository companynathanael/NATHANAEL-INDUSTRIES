"""Eletronanologia (versão virtual).

Simula as caixas de energia que mantêm o Asafe (e, através dele, as outras IAs)
funcionando quando a luz cai. Meta: ~2 dias (48 h) de autonomia.

As caixas são descarregadas em sequência: quando uma esvazia, a próxima assume.
Enquanto há luz, todas recarregam.
"""

import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Callable

META_HORAS = 48.0
AVISO_PCT = 25.0        # avisa o Sr. Nathanael
CRITICO_PCT = 10.0      # salvar dados e desligar com segurança


@dataclass
class Caixa:
    nome: str
    capacidade_wh: float
    carga_wh: float | None = None

    def __post_init__(self):
        if self.carga_wh is None:
            self.carga_wh = self.capacidade_wh

    @property
    def pct(self) -> float:
        return round(100 * self.carga_wh / self.capacidade_wh, 1)


@dataclass
class SistemaEletro:
    caixas: list[Caixa]
    consumo_w: float                       # consumo do Asafe + servidores das IAs
    recarga_w: float = 300.0               # potência de recarga quando há luz
    na_rede: bool = True
    horas_sem_luz: float = 0.0
    _nivel_anterior: str = field(default="normal", repr=False)

    @classmethod
    def padrao(cls, n_caixas: int = 4, consumo_w: float = 60.0) -> "SistemaEletro":
        """Dimensiona as caixas para cobrir a meta de 48 h com esse consumo."""
        por_caixa = consumo_w * META_HORAS / n_caixas
        return cls([Caixa(f"caixa-{i + 1}", por_caixa) for i in range(n_caixas)], consumo_w)

    # ---- leitura ----
    @property
    def capacidade_wh(self) -> float:
        return sum(c.capacidade_wh for c in self.caixas)

    @property
    def carga_wh(self) -> float:
        return sum(c.carga_wh for c in self.caixas)

    @property
    def pct(self) -> float:
        return round(100 * self.carga_wh / self.capacidade_wh, 1)

    @property
    def autonomia_horas(self) -> float:
        return round(self.carga_wh / self.consumo_w, 1) if self.consumo_w else float("inf")

    @property
    def nivel(self) -> str:
        if self.na_rede:
            return "normal"
        if self.carga_wh <= 0:
            return "desligado"
        if self.pct <= CRITICO_PCT:
            return "critico"
        if self.pct <= AVISO_PCT:
            return "aviso"
        return "bateria"

    def estado(self) -> dict:
        return {
            "na_rede_eletrica": self.na_rede,
            "nivel": self.nivel,
            "carga_pct": self.pct,
            "autonomia_horas": self.autonomia_horas,
            "meta_horas": META_HORAS,
            "horas_sem_luz": round(self.horas_sem_luz, 2),
            "consumo_w": self.consumo_w,
            "caixas": [{"nome": c.nome, "capacidade_wh": round(c.capacidade_wh, 1),
                        "carga_pct": c.pct} for c in self.caixas],
        }

    # ---- eventos ----
    def para_dict(self) -> dict:
        return {"caixas": [{"nome": c.nome, "capacidade_wh": c.capacidade_wh, "carga_wh": c.carga_wh} for c in self.caixas],
                "consumo_w": self.consumo_w, "recarga_w": self.recarga_w, "na_rede": self.na_rede,
                "horas_sem_luz": self.horas_sem_luz, "nivel_anterior": self._nivel_anterior}

    @classmethod
    def de_dict(cls, d: dict) -> "SistemaEletro":
        s = cls([Caixa(c["nome"], c["capacidade_wh"], c["carga_wh"]) for c in d["caixas"]], d["consumo_w"],
                d.get("recarga_w", 300.0), d["na_rede"], d.get("horas_sem_luz", 0.0))
        s._nivel_anterior = d.get("nivel_anterior", "normal")
        return s

    def queda_de_luz(self) -> None:
        self.na_rede = False
        self.horas_sem_luz = 0.0

    def retorno_da_luz(self) -> None:
        self.na_rede = True

    def avancar(self, horas: float) -> str | None:
        """Avança o tempo. Retorna o novo nível se ele mudou (para gerar alerta)."""
        if self.na_rede:
            energia = self.recarga_w * horas
            for c in self.caixas:
                entra = min(energia, c.capacidade_wh - c.carga_wh)
                c.carga_wh += entra
                energia -= entra
        else:
            self.horas_sem_luz += horas
            falta = self.consumo_w * horas
            for c in self.caixas:
                sai = min(falta, c.carga_wh)
                c.carga_wh -= sai
                falta -= sai
        novo = self.nivel
        if novo != self._nivel_anterior:
            self._nivel_anterior = novo
            return novo
        return None


MENSAGENS = {
    "bateria": "⚡ A luz caiu. Asafe e IAs funcionando pelas caixas de energia.",
    "aviso": "🟠 Energia de reserva abaixo de 25%. Prepare-se para desligamento.",
    "critico": "🔴 Energia crítica (≤10%). Salvando dados e desligando com segurança.",
    "desligado": "⛔ Caixas de energia esgotadas. Sistemas desligados.",
    "normal": "✅ A luz voltou. Caixas de energia recarregando.",
}


def nivel_da_fonte(na_rede: bool, bateria_pct: float | None) -> str:
    """Mesmos níveis das caixas virtuais, aplicados a uma bateria física (nobreak)."""
    if na_rede:
        return "normal"
    if bateria_pct is None:
        return "bateria"
    if bateria_pct <= 0:
        return "desligado"
    if bateria_pct <= CRITICO_PCT:
        return "critico"
    if bateria_pct <= AVISO_PCT:
        return "aviso"
    return "bateria"


NIVEIS_PROTEGIDOS = ("critico", "desligado")


class GestaoEnergia:
    """Eletronanologia completa: caixas virtuais guardadas no banco, descarga em tempo real,
    alertas, desligamento seguro e leitura das fontes físicas que os servidores informam."""

    def __init__(self, banco, relogio: Callable[[], float], n_caixas: int, consumo_w: float,
                 ao_salvar: Callable[[], dict] | None = None, cmd_desligar: str | None = None):
        self.banco = banco
        self.relogio = relogio
        self.ao_salvar = ao_salvar          # cria o backup antes de desligar
        self.cmd_desligar = cmd_desligar    # opcional: comando que o dono da máquina configurou
        row = banco.um("SELECT estado, atualizado_em FROM energia WHERE id=1")
        if row:
            self.sistema = SistemaEletro.de_dict(json.loads(row["estado"]))
            if len(self.sistema.caixas) != n_caixas or self.sistema.consumo_w != consumo_w:
                self.sistema = self._redimensionar(self.sistema, n_caixas, consumo_w)
            self.atualizado_em = row["atualizado_em"]
        else:
            self.sistema = SistemaEletro.padrao(n_caixas=n_caixas, consumo_w=consumo_w)
            self.atualizado_em = relogio()
        self._salvar()

    @staticmethod
    def _redimensionar(antigo: SistemaEletro, n: int, consumo: float) -> SistemaEletro:
        """Configuração mudou (nº de caixas ou consumo): refaz as caixas mantendo a carga em %."""
        novo = SistemaEletro.padrao(n_caixas=n, consumo_w=consumo)
        falta = novo.capacidade_wh * (1 - antigo.pct / 100)
        for c in reversed(novo.caixas):
            sai = min(falta, c.carga_wh)
            c.carga_wh -= sai
            falta -= sai
        novo.na_rede, novo.horas_sem_luz = antigo.na_rede, antigo.horas_sem_luz
        novo._nivel_anterior = antigo._nivel_anterior
        return novo

    # ------------------------------------------------------------ estado
    def _salvar(self) -> None:
        self.banco.executar(
            "INSERT INTO energia (id, estado, atualizado_em) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET estado=excluded.estado, atualizado_em=excluded.atualizado_em",
            (json.dumps(self.sistema.para_dict()), self.atualizado_em))

    def sincronizar(self) -> None:
        """Aplica o tempo real que passou desde a última atualização (descarrega ou recarrega)."""
        agora = self.relogio()
        horas = max(0.0, (agora - self.atualizado_em) / 3600)
        self.atualizado_em = agora
        self._em_passos(horas, "asafe")

    def _em_passos(self, horas: float, origem: str) -> None:
        """Avança em passos de meia hora para nunca pular um nível (e o desligamento seguro do crítico)."""
        if horas <= 0:
            return self._aplicar(self.sistema.avancar(0), origem)
        while horas > 1e-9:
            passo = min(horas, 0.5)
            self._aplicar(self.sistema.avancar(passo), origem)
            horas -= passo

    @property
    def protegido(self) -> bool:
        return self.sistema.nivel in NIVEIS_PROTEGIDOS

    def estado(self) -> dict:
        e = self.sistema.estado()
        e["modo_protegido"] = self.protegido
        e["fontes"] = self.fontes()
        e["ultimos_eventos"] = self.eventos(10)
        return e

    # ------------------------------------------------------------ eventos
    def _evento(self, tipo: str, mensagem: str, origem: str, nivel: str | None = None, avisar: bool = True) -> None:
        self.banco.executar("INSERT INTO energia_eventos (tipo, nivel, mensagem, origem) VALUES (?,?,?,?)",
                            (tipo, nivel, mensagem, origem))
        if avisar:
            from .seguranca import NOME_ADMIN
            self.banco.executar("INSERT INTO mensagens (de, para, conteudo) VALUES (?,?,?)",
                                ("asafe", NOME_ADMIN, mensagem))

    def _aplicar(self, novo_nivel: str | None, origem: str) -> None:
        if novo_nivel:
            self._evento("nivel", MENSAGENS[novo_nivel], origem, novo_nivel)
            if novo_nivel == "critico":
                self._desligamento_seguro(origem)
        self._salvar()

    def _desligamento_seguro(self, origem: str) -> None:
        """Nível crítico: salva tudo (backup) e registra o desligamento seguro."""
        if self.ao_salvar:
            try:
                b = self.ao_salvar()
                self._evento("backup", f"💾 Backup de emergência criado: {b['nome']}", origem, "critico", avisar=False)
            except Exception as e:  # o desligamento segue mesmo se o backup falhar
                self._evento("backup", f"⚠️ Backup de emergência falhou: {e}", origem, "critico")
        msg = "🛑 Desligamento seguro: dados salvos; IAs em modo protegido (sem gravações) até a luz voltar."
        if self.cmd_desligar:
            try:
                p = subprocess.run(shlex.split(self.cmd_desligar), capture_output=True, text=True, timeout=120)
                msg += f" Comando de desligamento executado (código {p.returncode})."
            except (OSError, subprocess.TimeoutExpired) as e:
                msg += f" Comando de desligamento falhou: {e}."
        self._evento("desligamento", msg, origem, "critico", avisar=False)

    def eventos(self, limite: int = 50) -> list[dict]:
        return self.banco.todos("SELECT * FROM energia_eventos ORDER BY id DESC LIMIT ?", (max(1, min(limite, 500)),))

    # ------------------------------------------------------------ ações
    def queda(self, origem: str = "simulacao") -> None:
        self.sincronizar()
        if self.sistema.na_rede:
            self.sistema.queda_de_luz()
            self._evento("queda", f"Queda de luz detectada ({origem}).", origem, avisar=False)
        self._aplicar(self.sistema.avancar(0), origem)

    def retorno(self, origem: str = "simulacao") -> None:
        self.sincronizar()
        if not self.sistema.na_rede:
            self.sistema.retorno_da_luz()
            self._evento("retorno", f"A luz voltou ({origem}).", origem, avisar=False)
        self._aplicar(self.sistema.avancar(0), origem)

    def avancar(self, horas: float) -> None:
        """Simulação: adianta o tempo."""
        self.sincronizar()
        self._em_passos(horas, "simulacao")

    # ------------------------------------------------------------ fontes físicas (sinal dos servidores)
    def receber_fonte(self, servidor: str, info: dict) -> None:
        if "na_rede_eletrica" not in info:
            return
        na_rede = bool(info["na_rede_eletrica"])
        bat = info.get("bateria_pct")
        bat = float(bat) if isinstance(bat, (int, float)) else None
        aut = info.get("autonomia_min")
        aut = float(aut) if isinstance(aut, (int, float)) else None
        nivel = nivel_da_fonte(na_rede, bat)
        antes = self.banco.um("SELECT nivel FROM energia_fontes WHERE servidor=?", (servidor,))
        self.banco.executar(
            "INSERT INTO energia_fontes (servidor, na_rede, bateria_pct, autonomia_min, nivel, momento) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(servidor) DO UPDATE SET na_rede=excluded.na_rede, "
            "bateria_pct=excluded.bateria_pct, autonomia_min=excluded.autonomia_min, nivel=excluded.nivel, "
            "momento=excluded.momento", (servidor, int(na_rede), bat, aut, nivel, self.relogio()))
        if (antes["nivel"] if antes else "normal") != nivel:
            extra = f" Bateria {bat:.0f}%." if bat is not None else ""
            extra += f" Autonomia {aut:.0f} min." if aut is not None else ""
            self._evento("fonte", f"[{servidor}] {MENSAGENS[nivel]}{extra}", servidor, nivel)
        # a luz caiu de verdade: as caixas do Asafe assumem; volta quando todas as fontes estiverem na rede
        if not na_rede:
            self.queda(origem=servidor)
        elif not self.sistema.na_rede and not self.banco.um("SELECT 1 FROM energia_fontes WHERE na_rede=0"):
            self.retorno(origem=servidor)

    def fontes(self) -> list[dict]:
        rows = self.banco.todos("SELECT * FROM energia_fontes ORDER BY servidor")
        for r in rows:
            r["na_rede"] = bool(r["na_rede"])
        return rows


def comando_desligar_configurado() -> str | None:
    return os.environ.get("ASAFE_ENERGIA_CMD_DESLIGAR") or None
