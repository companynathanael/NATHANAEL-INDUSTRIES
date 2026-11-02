"""Provedores de máquinas: como o Asafe cria (e destrói) servidores de verdade.

Cada provedor sabe criar uma máquina que, ao ligar, já roda o sentinela e
começa a mandar sinal para o Asafe. Assim o servidor aparece sozinho no painel.

Provedores disponíveis:
  - local:  roda o sentinela como processo na própria máquina do Asafe (para testar, sem conta nenhuma)
  - oracle: cria uma máquina na Oracle Cloud (tem máquinas gratuitas para sempre)
"""

import shlex
from dataclasses import dataclass, field


@dataclass
class Pedido:
    """O que o Asafe pede a um provedor."""
    nome: str
    asafe_url: str            # endereço do Asafe que a máquina vai usar para mandar sinal
    token: str                # token do servidor (só pode mandar sinal)
    intervalo: int = 30
    opcoes: dict = field(default_factory=dict)  # específicas do provedor (tamanho, região...)


@dataclass
class Maquina:
    id: str
    endereco: str | None = None
    estado: str = "criando"    # criando | rodando | parada | destruida | erro
    detalhes: dict = field(default_factory=dict)


class ErroProvedor(Exception):
    pass


class Provedor:
    nome = "base"
    descricao = ""

    def configurado(self) -> tuple[bool, str]:
        """(pronto?, motivo se não estiver)"""
        raise NotImplementedError

    def criar(self, pedido: Pedido) -> Maquina:
        raise NotImplementedError

    def destruir(self, maquina_id: str) -> None:
        raise NotImplementedError

    def estado(self, maquina_id: str) -> Maquina:
        raise NotImplementedError

    def info(self) -> dict:
        ok, motivo = self.configurado()
        return {"nome": self.nome, "descricao": self.descricao, "configurado": ok, "motivo": None if ok else motivo}


def script_inicial(pedido: Pedido) -> str:
    """Script (cloud-init) que a máquina nova roda ao ligar: instala e liga o sentinela como serviço."""
    q = shlex.quote
    url = pedido.asafe_url.rstrip("/")
    return f"""#!/bin/bash
# Gerado pelo Asafe para o servidor {pedido.nome}
set -e
mkdir -p /opt/asafe-sentinela
for i in $(seq 1 30); do
  curl -fsSL {q(url + '/sentinela.py')} -o /opt/asafe-sentinela/sentinela.py && break || sleep 10
done
ENDERECO=$(hostname -I 2>/dev/null | awk '{{print $1}}')
cat > /etc/systemd/system/asafe-sentinela.service <<SERVICO
[Unit]
Description=Sentinela do Asafe ({pedido.nome})
After=network-online.target
Wants=network-online.target

[Service]
Environment=ASAFE_URL={url}
Environment=ASAFE_TOKEN={pedido.token}
Environment=SENTINELA_NOME={pedido.nome}
Environment=SENTINELA_ENDERECO=$ENDERECO
Environment=SENTINELA_INTERVALO={pedido.intervalo}
ExecStart=/usr/bin/python3 /opt/asafe-sentinela/sentinela.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICO
chmod 600 /etc/systemd/system/asafe-sentinela.service
systemctl daemon-reload
systemctl enable --now asafe-sentinela
"""


def carregar_provedores() -> dict[str, Provedor]:
    from .local import ProvedorLocal
    from .oracle import ProvedorOracle
    return {p.nome: p for p in (ProvedorLocal(), ProvedorOracle())}
