"""Esqueleto do Gather. Nada aqui está implementado ainda."""

from dataclasses import dataclass, field


@dataclass
class API:
    nome: str
    url_base: str
    descricao: str = ""
    capacidades: list[str] = field(default_factory=list)   # ex.: ["clima", "cotacoes"]
    credencial_ref: str | None = None                       # referência a um segredo, nunca o segredo


class Gather:
    # 1. Registro e gerenciamento de APIs
    def registrar(self, api: API) -> None:
        raise NotImplementedError

    def remover(self, nome: str) -> None:
        raise NotImplementedError

    # 2. Integração de serviços e ferramentas
    def chamar(self, nome: str, rota: str, **params):
        raise NotImplementedError

    # 3. Gerenciamento de credenciais de acesso (guardadas no Asafe)
    def definir_credencial(self, nome: str, segredo: str) -> None:
        raise NotImplementedError

    # 4. Monitoramento de disponibilidade e desempenho
    def verificar(self, nome: str) -> dict:
        raise NotImplementedError

    # 5. Seleção de APIs conforme a necessidade das IAs
    def escolher(self, capacidade: str) -> API:
        raise NotImplementedError

    # 6. Compatibilidade entre diferentes serviços
    def adaptar(self, nome: str, resposta: dict) -> dict:
        raise NotImplementedError
