"""Modelos de entrada/saída da API do Asafe."""

from typing import Any, Literal

from pydantic import BaseModel, Field

NOME = r"^[a-z0-9_-]{2,40}$"


class NovoAgente(BaseModel):
    nome: str = Field(pattern=NOME)
    categoria: Literal["auxiliar", "desenvolvedor"]
    versao: str = Field(min_length=1, max_length=20)
    permissoes: list[str] = []


class AtualizarPermissoes(BaseModel):
    permissoes: list[str]


class NovaMensagem(BaseModel):
    para: str = Field(pattern=NOME)
    conteudo: str = Field(min_length=1, max_length=20_000)


class Valor(BaseModel):
    valor: Any


Porcentagem = Field(default=None, ge=0, le=100)


class Sinal(BaseModel):
    """Batimento enviado periodicamente por um servidor (com métricas opcionais)."""
    nome: str = Field(pattern=NOME)
    endereco: str = Field(min_length=1, max_length=200)
    info: dict[str, Any] = {}
    cpu: float | None = Porcentagem
    memoria: float | None = Porcentagem
    disco: float | None = Porcentagem


class Limites(BaseModel):
    cpu: float = Field(default=90, gt=0, le=100)
    memoria: float = Field(default=90, gt=0, le=100)
    disco: float = Field(default=90, gt=0, le=100)


class NovoServidor(BaseModel):
    nome: str = Field(pattern=NOME)
    endereco: str = Field(min_length=1, max_length=200)
    intervalo: int = Field(default=30, ge=5, le=3600)
    limites: Limites = Limites()
    responsavel: str | None = Field(default=None, pattern=NOME)


class AtualizarServidor(BaseModel):
    endereco: str | None = Field(default=None, min_length=1, max_length=200)
    intervalo: int | None = Field(default=None, ge=5, le=3600)
    limites: Limites | None = None
    manutencao: bool | None = None
    responsavel: str | None = Field(default=None, pattern=NOME)


COMANDOS = ("reiniciar", "parar", "atualizar", "limpar_cache", "coletar_logs")


class NovoComando(BaseModel):
    comando: Literal[COMANDOS]
    args: dict[str, Any] = {}


class ResultadoComando(BaseModel):
    ok: bool
    saida: str = Field(default="", max_length=20_000)
