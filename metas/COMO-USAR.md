# Planilha de Metas — como usar

Arquivo: [`METAS.csv`](METAS.csv) (o GitHub mostra como tabela e permite editar pelo navegador/celular).

## Sr. Nathanael
Adicione uma linha por meta do dia, com `status` = `pendente`:

```
2026-11-04,Gather,Descrever a meta aqui,pendente,,,
```

- `data`: AAAA-MM-DD
- `ia`: `Asafe`, `Gather`, `Horácio`, `Miquéias` ou outra IA nova
- `meta`: o que deve ser feito (evite vírgulas; use `;`)

## Claude (fluxo em toda conversa)
1. Ler `METAS.csv` e pegar as metas com `status` = `pendente` ou `em_andamento`, priorizando a data de hoje.
2. Identificar **qual IA** é a meta do dia e trabalhar só no código/documentos dela.
3. Marcar `em_andamento` ao começar e `concluida` (ou `bloqueada`, com motivo em `observacoes`) ao terminar.
4. Rodar `python ferramentas/relatorio.py`: gera `relatorios/AAAA-MM-DD.md` e informa testes ok/falha por IA.
5. Preencher `testes_ok` e `testes_falha` na linha da meta.
6. Commit + push e enviar ao Sr. Nathanael o **relatório resumido** (testes positivos e negativos).

Status válidos: `pendente`, `em_andamento`, `concluida`, `bloqueada`.
