# Asafe 0.1 — Progresso

Meta da etapa atual: **Asafe 50% completo**.

## Como rodar

```bash
pip install -r requirements.txt
ASAFE_ADMIN_TOKEN=um-token-secreto python -m asafe          # API em http://127.0.0.1:8000/docs
ASAFE_ADMIN_TOKEN=um-token-secreto python -m asafe.semear   # registra horacio, miqueias e gather
python -m pytest -q                                         # testes
```

O token de administrador é o do Sr. Nathanael (acesso total). Cada IA recebe seu próprio token ao ser registrada.

## Responsabilidades × status

| # | Responsabilidade | Status | O que existe |
|---|---|---|---|
| 1 | Criação de APIs | ✅ Base pronta | API REST (FastAPI) com documentação automática em `/docs` |
| 2 | Gerenciamento de permissões | ✅ Base pronta | Tokens por IA, 7 permissões, admin, desativar IA, trocar token |
| 3 | Conexão entre IAs | ✅ Base pronta | Caixa de mensagens entre IAs (e para o Sr. Nathanael) |
| 4 | Monitoramento das ações dos agentes | ✅ Base pronta | Auditoria automática de toda requisição (inclusive as negadas) |
| 5 | Armazenamento de dados | 🟡 Parcial | Dados por IA, isolados (SQLite). Falta: arquivos, backup |
| 6 | Servidores | 🟡 Parcial | Registro de servidores por sinal (heartbeat) e status online. Falta: gestão real |
| 7 | Eletronanologia (energia de reserva quando a luz cai) | ⏳ Pendente (meta de quarta, 04/11) | Rascunho virtual: 4 caixas, 48 h, alertas. Ver [ELETRONANOLOGIA.md](ELETRONANOLOGIA.md) |

## Próxima metade (50% → 100%)
- [ ] Mensagens em tempo real (WebSocket) em vez de só consulta.
- [ ] Armazenamento de arquivos e backups automáticos.
- [ ] Gestão de servidores: métricas, alertas quando um servidor cai.
- [ ] Banco de produção (PostgreSQL) e HTTPS.
- [ ] Integração com o Gather (credenciais de APIs guardadas no Asafe).
- [ ] Painel visual para o Sr. Nathanael acompanhar as IAs.
