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


class Sinal(BaseModel):
    nome: str = Field(pattern=NOME)
    endereco: str = Field(min_length=1, max_length=200)
    info: dict[str, Any] = {}
