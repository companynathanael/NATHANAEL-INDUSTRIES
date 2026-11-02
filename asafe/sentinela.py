"""Sentinela: roda em cada servidor e mantém o Asafe informado.

A cada intervalo envia um sinal com CPU, memória e disco, e recebe comandos
(reiniciar, parar, atualizar, limpar_cache, coletar_logs).

Por segurança, o sentinela só executa um comando se o dono da máquina tiver
configurado o que ele faz, numa variável de ambiente:

    SENTINELA_CMD_REINICIAR="systemctl restart minha-ia"
    SENTINELA_CMD_LIMPAR_CACHE="rm -rf /var/cache/minha-ia/*"

Comando sem configuração é respondido como "não configurado" (nada é executado).

Uso:
    ASAFE_URL=http://10.0.0.2:8000 ASAFE_TOKEN=asf_... SENTINELA_NOME=srv-01 \\
    SENTINELA_ENDERECO=10.0.0.5 python -m asafe.sentinela
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request


# ---------------------------------------------------------------- métricas (sem dependências extras)
def _cpu_pct() -> float | None:
    def ler():
        with open("/proc/stat") as f:
            v = [int(x) for x in f.readline().split()[1:]]
        return v[3] + v[4], sum(v)  # ocioso (idle+iowait), total
    try:
        o1, t1 = ler()
        time.sleep(0.5)
        o2, t2 = ler()
        return round(100 * (1 - (o2 - o1) / max(t2 - t1, 1)), 1)
    except (OSError, ValueError, IndexError):
        try:
            return round(100 * os.getloadavg()[0] / (os.cpu_count() or 1), 1)
        except OSError:
            return None


def _memoria_pct() -> float | None:
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for linha in f:
                k, v = linha.split(":")
                info[k] = int(v.split()[0])
        return round(100 * (1 - info["MemAvailable"] / info["MemTotal"]), 1)
    except (OSError, KeyError, ValueError):
        return None


def _disco_pct(caminho: str = "/") -> float | None:
    try:
        u = shutil.disk_usage(caminho)
        return round(100 * u.used / u.total, 1)
    except OSError:
        return None


def coletar() -> dict:
    return {"cpu": _cpu_pct(), "memoria": _memoria_pct(),
            "disco": _disco_pct(os.environ.get("SENTINELA_DISCO", "/"))}


# ---------------------------------------------------------------- comunicação
def _post(url: str, token: str, caminho: str, corpo: dict) -> dict:
    req = urllib.request.Request(url + caminho, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def executar(cmd: dict) -> tuple[bool, str]:
    configurado = os.environ.get("SENTINELA_CMD_" + cmd["comando"].upper())
    if not configurado:
        return False, f"comando '{cmd['comando']}' não configurado neste servidor"
    try:
        p = subprocess.run(shlex.split(configurado), capture_output=True, text=True, timeout=300)
        return p.returncode == 0, (p.stdout + p.stderr)[-5000:]
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def ciclo(url: str, token: str, nome: str, endereco: str) -> list[dict]:
    resp = _post(url, token, "/servidores/sinal",
                 {"nome": nome, "endereco": endereco, "info": {"sentinela": "1"}, **coletar()})
    for cmd in resp.get("comandos", []):
        ok, saida = executar(cmd)
        _post(url, token, f"/servidores/{nome}/comandos/{cmd['id']}/resultado", {"ok": ok, "saida": saida})
    return resp.get("comandos", [])


def main() -> int:
    url = os.environ.get("ASAFE_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("ASAFE_TOKEN")
    nome = os.environ.get("SENTINELA_NOME")
    if not token or not nome:
        print("Defina ASAFE_TOKEN e SENTINELA_NOME.", file=sys.stderr)
        return 1
    endereco = os.environ.get("SENTINELA_ENDERECO", "desconhecido")
    intervalo = float(os.environ.get("SENTINELA_INTERVALO", 30))
    print(f"Sentinela de {nome} enviando sinal para {url} a cada {intervalo:.0f}s")
    while True:
        try:
            for c in ciclo(url, token, nome, endereco):
                print(f"Comando recebido: {c['comando']} (#{c['id']})")
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"Asafe indisponível: {e}", file=sys.stderr)
        time.sleep(intervalo)


if __name__ == "__main__":
    sys.exit(main())
