# Asafe 0.1 — Progresso

Meta da etapa atual: **Asafe 50% completo**.

## Como rodar

```bash
pip install -r requirements.txt
ASAFE_ADMIN_TOKEN=um-token-secreto python -m asafe          # API em http://127.0.0.1:8000/docs
ASAFE_ADMIN_TOKEN=um-token-secreto python -m asafe.semear   # registra horacio, miqueias e gather
python -m asafe.backup criar                                # backup manual (também há backup automático)
python -m pytest -q                                         # testes
```

Em cada servidor que o Asafe deve vigiar, rode o **sentinela** (manda sinal + métricas e recebe comandos):

```bash
ASAFE_URL=http://IP-DO-ASAFE:8000 ASAFE_TOKEN=asf_... SENTINELA_NOME=srv-01 \
SENTINELA_ENDERECO=10.0.0.5 python -m asafe.sentinela
```

O token de administrador é o do Sr. Nathanael (acesso total). Cada IA recebe seu próprio token ao ser registrada.

## Responsabilidades × status

| # | Responsabilidade | Status | O que existe |
|---|---|---|---|
| 1 | Criação de APIs | ✅ Base pronta | API REST (FastAPI) com documentação automática em `/docs` |
| 2 | Gerenciamento de permissões | ✅ Base pronta | Tokens por IA, 8 permissões, admin, desativar IA, trocar token |
| 3 | Conexão entre IAs | ✅ Base pronta | Caixa de mensagens entre IAs (e para o Sr. Nathanael) |
| 4 | Monitoramento das ações dos agentes | ✅ Base pronta | Auditoria automática de toda requisição (inclusive as negadas) |
| 5 | Armazenamento de dados | ✅ Base pronta | Dados e **arquivos** por IA (isolados), limite por arquivo e **cota** por IA, **backups** manuais e automáticos com retenção, **restauração** |
| 6 | Servidores | ✅ Base pronta | Cadastro, **métricas** (CPU/memória/disco) com histórico, estados online/offline/manutenção, **alertas** automáticos (caiu, voltou, limite passado) com aviso ao Sr. Nathanael, **comandos remotos** e **sentinela** |
| 7 | Eletronanologia (energia de reserva quando a luz cai) | ⏳ Pendente (meta de quarta, 04/11) | Rascunho virtual: 4 caixas, 48 h, alertas. Ver [ELETRONANOLOGIA.md](ELETRONANOLOGIA.md) |

## Próxima metade (50% → 100%)
- [ ] Mensagens em tempo real (WebSocket) em vez de só consulta.
- [x] Armazenamento de arquivos e backups automáticos.
- [x] Gestão de servidores: métricas, alertas quando um servidor cai.
- [ ] Banco de produção (PostgreSQL) e HTTPS.
- [ ] Integração com o Gather (credenciais de APIs guardadas no Asafe).
- [ ] Painel visual para o Sr. Nathanael acompanhar as IAs.

## Armazenamento

Cada IA (com `dados:ler` / `dados:escrever`) guarda dados (chave → JSON) e arquivos, sem ver os das outras.

| Rota | O que faz |
|---|---|
| `PUT /arquivos/{nome}` | Envia um arquivo (corpo da requisição = conteúdo; `Content-Type` é guardado) |
| `GET /arquivos` · `GET /arquivos/{nome}` · `DELETE /arquivos/{nome}` | Lista, baixa e apaga |
| `GET /armazenamento/uso` | Espaço usado pela IA e quanto falta da cota |
| `GET /armazenamento/uso/todos` | Uso de todas as IAs (só o Sr. Nathanael) |
| `POST /backups` · `GET /backups` · `GET/DELETE /backups/{nome}` | Backups (só o Sr. Nathanael) |

- No disco, o arquivo recebe um nome aleatório; o nome escolhido pela IA fica só no banco (nenhum nome consegue sair da pasta).
- Backup = `.zip` com cópia consistente do banco + todos os arquivos + `manifesto.json`. Feito com o Asafe rodando.
- Restauração: com o Asafe **parado**, `python -m asafe.backup restaurar asafe-AAAAMMDD-HHMMSS.zip`. O estado anterior é guardado ao lado (`*.antes-restauracao-*`).

## Servidores

| Rota | Quem | O que faz |
|---|---|---|
| `POST /servidores/sinal` | servidor (`servidores:sinal`) | Batimento com métricas; a resposta traz comandos pendentes |
| `POST /servidores/{nome}/comandos/{id}/resultado` | servidor | Informa se o comando deu certo |
| `POST /servidores` · `GET /servidores` · `GET/PATCH/DELETE /servidores/{nome}` | `servidores:gerenciar` | Cadastro, intervalo, limites, manutenção, remoção |
| `GET /servidores/{nome}/metricas` | `servidores:gerenciar` | Histórico de métricas (últimas 1000) |
| `POST /servidores/{nome}/comandos` · `GET .../comandos` | `servidores:gerenciar` | Pede `reiniciar`, `parar`, `atualizar`, `limpar_cache` ou `coletar_logs` |
| `GET /alertas` · `POST /alertas/{id}/resolver` | `servidores:gerenciar` | Alertas abertos/histórico |
| `POST /servidores/verificar` | `servidores:gerenciar` | Força a checagem agora |

- **Offline** = 2 intervalos sem sinal (intervalo padrão 30 s). Um vigia roda sozinho a cada 15 s.
- **Alertas:** `caiu`, `voltou`, `cpu`, `memoria`, `disco` (limite padrão 90%). Não se repetem enquanto estão abertos e se resolvem sozinhos quando a situação normaliza. Cada alerta vira mensagem para o Sr. Nathanael (de `asafe`).
- **Manutenção:** silencia alertas do servidor.
- **Comandos:** o sentinela só executa um comando se o dono da máquina o configurou (`SENTINELA_CMD_REINICIAR="systemctl restart ..."`); senão responde "não configurado".
- A eletronanologia pode usar o mesmo sinal (campo `info`), como em [ELETRONANOLOGIA.md](ELETRONANOLOGIA.md).

## Configuração (variáveis de ambiente)

| Variável | Padrão | |
|---|---|---|
| `ASAFE_ARQUIVOS` / `ASAFE_BACKUPS` | `asafe_arquivos/`, `asafe_backups/` ao lado do banco | Pastas |
| `ASAFE_MAX_ARQUIVO_MB` | 50 | Tamanho máximo de um arquivo |
| `ASAFE_COTA_MB` | 1024 | Espaço por IA (dados + arquivos) |
| `ASAFE_BACKUP_HORAS` | 24 | Backup automático (0 desliga) |
| `ASAFE_BACKUP_MANTER` | 7 | Quantos backups guardar |
| `ASAFE_VIGIA_SEG` | 15 | Frequência da checagem de servidores |
