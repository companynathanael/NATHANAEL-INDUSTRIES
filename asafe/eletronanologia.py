"""Eletronanologia (versão virtual).

Simula as caixas de energia que mantêm o Asafe (e, através dele, as outras IAs)
funcionando quando a luz cai. Meta: ~2 dias (48 h) de autonomia.

As caixas são descarregadas em sequência: quando uma esvazia, a próxima assume.
Enquanto há luz, todas recarregam.
"""

from dataclasses import dataclass, field

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
