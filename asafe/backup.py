"""Backups do Asafe pela linha de comando.

    python -m asafe.backup criar                 # cria um backup agora
    python -m asafe.backup listar                # lista os backups
    python -m asafe.backup restaurar <arquivo>   # restaura (com o Asafe PARADO)

Usa as mesmas variáveis do Asafe: ASAFE_DB, ASAFE_ARQUIVOS, ASAFE_BACKUPS.
O estado anterior à restauração é guardado ao lado ("*.antes-restauracao-<data>").
"""

import argparse
import os
import sys
from pathlib import Path

from .armazenamento import criar_backup, limpar_backups, listar_backups, restaurar_backup
from .db import Banco


def _caminhos() -> tuple[Path, Path, Path]:
    db = Path(os.environ.get("ASAFE_DB", "asafe.db")).resolve()
    arquivos = Path(os.environ.get("ASAFE_ARQUIVOS", db.parent / "asafe_arquivos"))
    backups = Path(os.environ.get("ASAFE_BACKUPS", db.parent / "asafe_backups"))
    return db, arquivos, backups


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asafe.backup", description="Backups do Asafe")
    sub = p.add_subparsers(dest="acao", required=True)
    sub.add_parser("criar")
    sub.add_parser("listar")
    r = sub.add_parser("restaurar")
    r.add_argument("arquivo")
    r.add_argument("--sim", action="store_true", help="não pedir confirmação")
    args = p.parse_args(argv)
    db, arquivos, backups = _caminhos()

    if args.acao == "criar":
        banco = Banco(db)
        try:
            b = criar_backup(banco, arquivos, backups)
        finally:
            banco.fechar()
        apagados = limpar_backups(backups, int(os.environ.get("ASAFE_BACKUP_MANTER", 7)))
        print(f"Backup criado: {backups / b['nome']} ({b['tamanho']} bytes)")
        for a in apagados:
            print(f"Backup antigo apagado: {a}")
    elif args.acao == "listar":
        for b in listar_backups(backups):
            print(f"{b['nome']}  {b['tamanho']:>12} bytes  {b['criado_em']}")
    else:
        zip_path = Path(args.arquivo)
        if not zip_path.exists():
            zip_path = backups / args.arquivo
        if not zip_path.exists():
            print(f"Backup não encontrado: {args.arquivo}", file=sys.stderr)
            return 1
        if not args.sim:
            resp = input(f"Restaurar {zip_path.name} sobre {db}? O Asafe precisa estar PARADO. [s/N] ")
            if resp.strip().lower() not in ("s", "sim"):
                print("Cancelado.")
                return 1
        m = restaurar_backup(zip_path, db, arquivos)
        print(f"Restaurado o backup de {m['criado_em']} ({m['arquivos']} arquivos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
