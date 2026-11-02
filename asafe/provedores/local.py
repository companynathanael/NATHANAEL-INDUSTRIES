"""Provedor "local": o "servidor" é um processo do sentinela rodando na própria máquina do Asafe.

Serve para testar a criação de servidores de ponta a ponta sem conta em nuvem.
Desligue com ASAFE_PROVEDOR_LOCAL=0.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

from . import ErroProvedor, Maquina, Pedido, Provedor

RAIZ = Path(__file__).resolve().parents[2]  # pasta que contém o pacote asafe/


class ProvedorLocal(Provedor):
    nome = "local"
    descricao = "Processo na própria máquina do Asafe (para testes)"

    def __init__(self):
        self._processos: dict[str, subprocess.Popen] = {}

    def configurado(self):
        if os.environ.get("ASAFE_PROVEDOR_LOCAL", "1") == "0":
            return False, "Desligado (ASAFE_PROVEDOR_LOCAL=0)"
        return True, ""

    def criar(self, pedido: Pedido) -> Maquina:
        ok, motivo = self.configurado()
        if not ok:
            raise ErroProvedor(motivo)
        # Ambiente limpo: o processo não herda segredos nem comandos configurados do Asafe.
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(RAIZ),
            "ASAFE_URL": pedido.asafe_url,
            "ASAFE_TOKEN": pedido.token,
            "SENTINELA_NOME": pedido.nome,
            "SENTINELA_ENDERECO": "127.0.0.1",
            "SENTINELA_INTERVALO": str(pedido.intervalo),
        }
        try:
            p = subprocess.Popen([sys.executable, "-m", "asafe.sentinela"], env=env, cwd=str(RAIZ),
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            raise ErroProvedor(f"Não foi possível iniciar o processo: {e}") from e
        mid = f"local-{p.pid}"
        self._processos[mid] = p
        return Maquina(id=mid, endereco="127.0.0.1", estado="rodando", detalhes={"pid": p.pid})

    def destruir(self, maquina_id: str) -> None:
        p = self._processos.pop(maquina_id, None)
        if p:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
            return
        try:  # processo de uma execução anterior do Asafe
            os.kill(int(maquina_id.removeprefix("local-")), signal.SIGTERM)
        except (ValueError, ProcessLookupError, PermissionError):
            pass

    def estado(self, maquina_id: str) -> Maquina:
        p = self._processos.get(maquina_id)
        if p is None:
            return Maquina(id=maquina_id, estado="desconhecido")
        return Maquina(id=maquina_id, endereco="127.0.0.1", estado="rodando" if p.poll() is None else "parada")
