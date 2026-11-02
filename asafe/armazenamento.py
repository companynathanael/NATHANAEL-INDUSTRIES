"""Armazenamento do Asafe: arquivos por IA, cota de espaço e backups.

- Cada IA tem sua própria pasta de arquivos. O nome que a IA dá ao arquivo
  fica só no banco; no disco o arquivo é salvo com um nome aleatório, então
  um nome como "../../x" nunca escapa da pasta.
- Backup = um .zip com uma cópia consistente do banco + todos os arquivos.
- A restauração é feita com o Asafe parado:  python -m asafe.backup restaurar <zip>
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from . import __version__
from .db import Banco

NOME_ARQUIVO = re.compile(r"^[\w][\w .\-()]{0,119}$")
NOME_BACKUP = re.compile(r"^asafe-\d{8}-\d{6}(-\d+)?\.zip$")


class CotaExcedida(Exception):
    pass


class ArquivoGrande(Exception):
    pass


# ---------------------------------------------------------------- arquivos
class Arquivos:
    def __init__(self, banco: Banco, pasta: str | Path, max_bytes: int, cota_bytes: int):
        self.banco = banco
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.cota_bytes = cota_bytes

    def uso(self, agente: str) -> dict:
        arq = self.banco.um("SELECT COUNT(*) n, COALESCE(SUM(tamanho),0) b FROM arquivos WHERE agente=?", (agente,))
        dad = self.banco.um("SELECT COUNT(*) n, COALESCE(SUM(LENGTH(valor)),0) b FROM dados WHERE agente=?", (agente,))
        total = arq["b"] + dad["b"]
        return {
            "agente": agente,
            "arquivos": {"quantidade": arq["n"], "bytes": arq["b"]},
            "dados": {"quantidade": dad["n"], "bytes": dad["b"]},
            "total_bytes": total,
            "cota_bytes": self.cota_bytes,
            "livre_bytes": max(0, self.cota_bytes - total),
        }

    async def salvar(self, agente: str, nome: str, tipo: str, partes) -> dict:
        """Grava o arquivo em streaming, respeitando o tamanho máximo e a cota."""
        antigo = self.banco.um("SELECT tamanho, caminho FROM arquivos WHERE agente=? AND nome=?", (agente, nome))
        disponivel = self.cota_bytes - self.uso(agente)["total_bytes"] + (antigo["tamanho"] if antigo else 0)
        limite = min(self.max_bytes, disponivel)

        pasta = self.pasta / agente
        pasta.mkdir(parents=True, exist_ok=True)
        relativo = f"{agente}/{uuid.uuid4().hex}"
        destino = self.pasta / relativo
        tmp = destino.with_suffix(".parcial")
        sha, tamanho = hashlib.sha256(), 0
        try:
            with open(tmp, "wb") as f:
                async for parte in partes:
                    tamanho += len(parte)
                    if tamanho > limite:
                        if tamanho > self.max_bytes:
                            raise ArquivoGrande()
                        raise CotaExcedida()
                    sha.update(parte)
                    f.write(parte)
            os.replace(tmp, destino)
        finally:
            tmp.unlink(missing_ok=True)

        self.banco.executar(
            "INSERT INTO arquivos (agente, nome, tipo, tamanho, sha256, caminho) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(agente, nome) DO UPDATE SET tipo=excluded.tipo, tamanho=excluded.tamanho, "
            "sha256=excluded.sha256, caminho=excluded.caminho, atualizado_em=datetime('now')",
            (agente, nome, tipo, tamanho, sha.hexdigest(), relativo),
        )
        if antigo:
            (self.pasta / antigo["caminho"]).unlink(missing_ok=True)
        return {"nome": nome, "tipo": tipo, "tamanho": tamanho, "sha256": sha.hexdigest()}

    def listar(self, agente: str) -> list[dict]:
        return self.banco.todos(
            "SELECT nome, tipo, tamanho, sha256, atualizado_em FROM arquivos WHERE agente=? ORDER BY nome", (agente,))

    def abrir(self, agente: str, nome: str) -> tuple[Path, dict] | None:
        row = self.banco.um("SELECT * FROM arquivos WHERE agente=? AND nome=?", (agente, nome))
        if not row:
            return None
        return self.pasta / row["caminho"], row

    def apagar(self, agente: str, nome: str) -> bool:
        row = self.banco.um("SELECT caminho FROM arquivos WHERE agente=? AND nome=?", (agente, nome))
        if not row:
            return False
        self.banco.executar("DELETE FROM arquivos WHERE agente=? AND nome=?", (agente, nome))
        (self.pasta / row["caminho"]).unlink(missing_ok=True)
        return True


# ---------------------------------------------------------------- backups
def criar_backup(banco: Banco, pasta_arquivos: Path, pasta_backups: Path, agora: float | None = None) -> dict:
    pasta_backups.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.fromtimestamp(agora if agora is not None else time.time()).strftime("%Y%m%d-%H%M%S")
    nome, n = f"asafe-{carimbo}.zip", 1
    while (pasta_backups / nome).exists():
        nome, n = f"asafe-{carimbo}-{n}.zip", n + 1

    with tempfile.TemporaryDirectory() as tmp:
        copia_db = Path(tmp) / "asafe.db"
        banco.backup_para(copia_db)
        parcial = pasta_backups / (nome + ".parcial")
        qtd_arquivos = 0
        with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia_db, "asafe.db")
            if pasta_arquivos.exists():
                for p in sorted(pasta_arquivos.rglob("*")):
                    if p.is_file() and not p.name.endswith(".parcial"):
                        z.write(p, "arquivos/" + p.relative_to(pasta_arquivos).as_posix())
                        qtd_arquivos += 1
            z.writestr("manifesto.json", json.dumps({
                "servico": "asafe", "versao": __version__, "criado_em": carimbo, "arquivos": qtd_arquivos,
            }, ensure_ascii=False))
        os.replace(parcial, pasta_backups / nome)
    return info_backup(pasta_backups / nome)


def info_backup(caminho: Path) -> dict:
    st = caminho.stat()
    return {"nome": caminho.name, "tamanho": st.st_size,
            "criado_em": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


def listar_backups(pasta_backups: Path) -> list[dict]:
    if not pasta_backups.exists():
        return []
    return [info_backup(p) for p in sorted(pasta_backups.glob("asafe-*.zip"), reverse=True)
            if NOME_BACKUP.match(p.name)]


def limpar_backups(pasta_backups: Path, manter: int) -> list[str]:
    """Mantém só os `manter` backups mais recentes; devolve os nomes apagados."""
    todos = sorted((p for p in pasta_backups.glob("asafe-*.zip") if NOME_BACKUP.match(p.name)),
                   key=lambda p: p.name, reverse=True)
    apagados = []
    for p in todos[max(manter, 1):]:
        p.unlink(missing_ok=True)
        apagados.append(p.name)
    return apagados


def restaurar_backup(zip_path: Path, caminho_db: Path, pasta_arquivos: Path) -> dict:
    """Restaura banco + arquivos. Use com o Asafe PARADO. Guarda o estado anterior ao lado."""
    with zipfile.ZipFile(zip_path) as z:
        nomes = z.namelist()
        if "asafe.db" not in nomes or "manifesto.json" not in nomes:
            raise ValueError("Arquivo não é um backup do Asafe")
        for n in nomes:
            partes = PurePosixPath(n).parts
            if n.startswith("/") or ".." in partes or (n not in ("asafe.db", "manifesto.json")
                                                       and partes[0] != "arquivos"):
                raise ValueError(f"Entrada suspeita no backup: {n}")
        manifesto = json.loads(z.read("manifesto.json"))

        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
        if caminho_db.exists():
            shutil.move(caminho_db, caminho_db.with_name(f"{caminho_db.name}.antes-restauracao-{carimbo}"))
        if pasta_arquivos.exists():
            shutil.move(pasta_arquivos, pasta_arquivos.with_name(f"{pasta_arquivos.name}.antes-restauracao-{carimbo}"))
        pasta_arquivos.mkdir(parents=True, exist_ok=True)

        with z.open("asafe.db") as src, open(caminho_db, "wb") as dst:
            shutil.copyfileobj(src, dst)
        for n in nomes:
            if n.startswith("arquivos/") and not n.endswith("/"):
                destino = pasta_arquivos / PurePosixPath(n).relative_to("arquivos")
                destino.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(destino, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return manifesto
