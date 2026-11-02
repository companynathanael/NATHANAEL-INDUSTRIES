# Nathanael Industries — Memória do Projeto

Este repositório guarda as ideias centrais da Nathanael Industries.
Responda ao usuário em português.

## ⚠️ Fluxo diário obrigatório (conversas do Asafe, do Gather e de qualquer IA)
1. **Antes de tudo**, ler `metas/METAS.csv` e achar a meta do dia (status `pendente`/`em_andamento`).
2. Ver **qual IA** é a meta do dia e trabalhar somente nela.
3. Atualizar o status na planilha (`em_andamento` → `concluida` ou `bloqueada`).
4. Ao final, rodar `python ferramentas/relatorio.py`, preencher `testes_ok`/`testes_falha` na planilha, commit + push.
5. Enviar ao Sr. Nathanael um **relatório resumido**: testes positivos e negativos, por IA.
Detalhes: @metas/COMO-USAR.md

## Documentos de referência (sempre consultar)
- @docs/ORGANIZACAO-IAS.md — Organização das IAs (Auxiliares: Horácio, Miquéias; Desenvolvedores: Asafe, Gather).
- @docs/ROADMAP.md — **Ordem de criação:** Asafe → Gather → Submotores (subs do Asafe e do Gather) → Horácio e Miquéias.
- @docs/ASAFE.md — Progresso do Asafe (meta atual: 50%) e como rodar.
- @docs/ELETRONANOLOGIA.md — Tecnologia-símbolo do Asafe: armazena eletricidade para as IAs seguirem funcionando quando a luz cai. Em pesquisa.

## Resumo rápido
- **Auxiliares:** Horácio HoV 1.1 (assistente pessoal do Sr. Nathanael, em desenvolvimento); Miquéias JpG 1.0 (tarefas, cálculos e trading, em desenvolvimento).
- **Desenvolvedores:** Asafe 0.1 (infraestrutura inteligente, em recriação); Gather 0.1 (orquestração de APIs, em planejamento).

## Estrutura
- **Motores:** Asafe e Gather.
- **Submotores:** Asafe 3 · Gather 3 · total 6. São peças de **sustentação**: NÃO tiram funções do motor; sustentam a diferença entre IA básica e motor. Pilares confirmados: Continuidade, Memória, Autonomia. Nomes temporários: Asafe → Âncora, Anais, Arbítrio; Gather → Guardião, Gravador, Guia. Ainda não produzidos.

## Código
- `asafe/` — API do Asafe (Python/FastAPI + SQLite). Testes em `tests/` (`python -m pytest -q`).
  - `armazenamento.py` (arquivos, cota, backups), `servidores.py` (métricas, alertas, comandos), `backup.py` (CLI), `sentinela.py` (roda em cada servidor).
- `ferramentas/relatorio.py` — roda os testes e gera `relatorios/AAAA-MM-DD.md` por IA.
- `gather/` — apenas esqueleto; implementação completa planejada para a próxima etapa.
