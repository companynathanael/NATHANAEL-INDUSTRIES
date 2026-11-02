"""Tokens e permissões dos agentes."""

import hashlib
import hmac
import secrets

# Permissões conhecidas pelo Asafe. "*" = acesso total (Sr. Nathanael).
PERMISSOES = {
    "agentes:ler",
    "mensagens:enviar",
    "mensagens:ler",
    "dados:ler",
    "dados:escrever",
    "auditoria:ler",
    "servidores:gerenciar",
    "servidores:sinal",     # só enviar sinal/métricas e responder comandos (para o próprio servidor)
}

NOME_ADMIN = "nathanael"


def gerar_token() -> str:
    return "asf_" + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_iguais(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def tem_permissao(permissoes: set[str], necessaria: str) -> bool:
    return "*" in permissoes or necessaria in permissoes


def tem_alguma(permissoes: set[str], *necessarias: str) -> bool:
    return any(tem_permissao(permissoes, n) for n in necessarias)
