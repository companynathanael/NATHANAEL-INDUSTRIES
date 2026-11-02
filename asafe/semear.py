"""Registra as IAs atuais da Nathanael Industries no Asafe.

Uso:  ASAFE_URL=http://127.0.0.1:8000 ASAFE_ADMIN_TOKEN=... python -m asafe.semear
"""

import json
import os
import urllib.request

AGENTES = [
    {"nome": "horacio", "categoria": "auxiliar", "versao": "HoV 1.1",
     "permissoes": ["mensagens:enviar", "mensagens:ler", "dados:ler", "dados:escrever", "agentes:ler"]},
    {"nome": "miqueias", "categoria": "auxiliar", "versao": "JpG 1.0",
     "permissoes": ["mensagens:enviar", "mensagens:ler", "dados:ler", "dados:escrever"]},
    {"nome": "gather", "categoria": "desenvolvedor", "versao": "0.1",
     "permissoes": ["mensagens:enviar", "mensagens:ler", "dados:ler", "dados:escrever",
                    "agentes:ler", "servidores:gerenciar"]},
]


def main() -> None:
    url = os.environ.get("ASAFE_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ["ASAFE_ADMIN_TOKEN"]
    for ag in AGENTES:
        req = urllib.request.Request(
            f"{url}/agentes", data=json.dumps(ag).encode(), method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                print(f"{ag['nome']}: {json.loads(r.read())['token']}")
        except urllib.error.HTTPError as e:
            print(f"{ag['nome']}: erro {e.code} ({e.read().decode()})")


if __name__ == "__main__":
    main()
