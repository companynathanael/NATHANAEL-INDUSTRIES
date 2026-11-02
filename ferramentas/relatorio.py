"""Roda os testes e gera o relatório do dia, separado por IA.

Uso:  python ferramentas/relatorio.py
Saída: relatorios/AAAA-MM-DD.md (e resumo no terminal)
"""

import csv
import datetime as dt
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Arquivo de teste -> IA. Testes sem correspondência entram como "Geral".
IA_POR_ARQUIVO = {
    "test_asafe": "Asafe",
    "test_eletronanologia": "Asafe",
    "test_gather": "Gather",
}


def ia_do_teste(classname: str) -> str:
    for prefixo, ia in IA_POR_ARQUIVO.items():
        if prefixo in classname:
            return ia
    return "Geral"


def rodar_testes():
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "r.xml"
        subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"],
                       cwd=RAIZ, capture_output=True, text=True)
        if not xml.exists():
            raise SystemExit("pytest não gerou resultados (erro de coleta?).")
        casos = ET.parse(xml).getroot().iter("testcase")
        res = defaultdict(lambda: {"ok": [], "falha": []})
        for c in casos:
            ia = ia_do_teste(c.get("classname", ""))
            nome = c.get("name")
            erro = c.find("failure") if c.find("failure") is not None else c.find("error")
            if c.find("skipped") is not None:
                continue
            if erro is not None:
                msg = (erro.get("message") or "").splitlines()[0][:150] if erro.get("message") else "erro"
                res[ia]["falha"].append((nome, msg))
            else:
                res[ia]["ok"].append(nome)
        return res


def metas_de_hoje(hoje: str):
    arq = RAIZ / "metas" / "METAS.csv"
    with arq.open(encoding="utf-8") as f:
        return [m for m in csv.DictReader(f)
                if m["data"] == hoje or m["status"] in ("pendente", "em_andamento")]


def main():
    hoje = dt.date.today().isoformat()
    res = rodar_testes()
    total_ok = sum(len(r["ok"]) for r in res.values())
    total_falha = sum(len(r["falha"]) for r in res.values())

    linhas = [f"# Relatório — {hoje}", "",
              f"**Resultado geral:** ✅ {total_ok} positivos · ❌ {total_falha} negativos", "",
              "## Metas", "", "| IA | Meta | Status |", "|---|---|---|"]
    for m in metas_de_hoje(hoje):
        linhas.append(f"| {m['ia']} | {m['meta']} | {m['status']} |")
    linhas += ["", "## Testes por IA", ""]
    for ia in sorted(res):
        r = res[ia]
        linhas.append(f"### {ia} — ✅ {len(r['ok'])} · ❌ {len(r['falha'])}")
        for nome, msg in r["falha"]:
            linhas.append(f"- ❌ `{nome}`: {msg}")
        if r["ok"]:
            linhas.append(f"- ✅ {', '.join(f'`{n}`' for n in r['ok'])}")
        linhas.append("")

    saida = RAIZ / "relatorios" / f"{hoje}.md"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text("\n".join(linhas), encoding="utf-8")
    for ia in sorted(res):
        print(f"{ia}: {len(res[ia]['ok'])} ok, {len(res[ia]['falha'])} falha")
    print(f"Relatório: {saida.relative_to(RAIZ)}")
    sys.exit(1 if total_falha else 0)


if __name__ == "__main__":
    main()
