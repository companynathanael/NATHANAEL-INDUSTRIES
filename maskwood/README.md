# MASKWOOD: 100 Noites

> **Não desvie o olhar.**

Terror de sobrevivência co-op (1 a 4 jogadores) com "regras da floresta". Sem sangue, público 10+.
Em 1987 a vila de Pedra Alta sumiu numa noite; só ficaram máscaras de porcelana penduradas nas árvores.
Os jogadores são uma equipe de resgate presa na floresta. A única proteção é a **Chama-Mãe**, uma lanterna
antiga no centro da vila. À noite saem os **Sem-Rosto**.

**Plataforma:** navegador (PC e celular), não Roblox. 3D com [Three.js](https://threejs.org) 0.160, sem build:
módulos ES puros. O "servidor" é JavaScript puro (sem DOM), então roda dentro da página no modo solo e,
na etapa de co-op, em Node com WebSocket, sem reescrever a lógica.

## Como jogar (protótipo)

```bash
cd maskwood
python3 -m http.server 8080      # ou: npm start
# abra http://localhost:8080
```

| | PC | Celular |
|---|---|---|
| Andar | WASD / setas | arrastar no lado esquerdo |
| Olhar | mouse (clique trava o cursor; sem trava, arraste) | arrastar no lado direito |
| Correr | Shift | botão **Correr** |
| Agachar | C | botão **Agachar** |
| Pausa / opções | Esc ou M | botão ☰ |

No menu de pausa há **testes do protótipo**: acelerar o tempo (1×/10×/30×), pular para o fim do dia/noite
e pôr óleo na Chama. Eles só funcionam com `PERMITIR_DEBUG` ligado no `Config`.

## Testes

```bash
cd maskwood && npm test          # node --test (38 testes: ciclo, Chama, mapa, física, servidor)
```

Os testes também entram no relatório diário (`python ferramentas/relatorio.py`, IA "Maskwood").

---

## Arquitetura

Mesma divisão de um projeto Rojo do Roblox, traduzida para a web:

| Roblox | Aqui | O que vai lá |
|---|---|---|
| `ServerScriptService` | `src/servidor/` | Autoridade: tempo, óleo, posições oficiais, salvamento, (depois) coleta, IA, dano |
| `StarterPlayerScripts` | `src/cliente/` | Desenho 3D, câmera, controles, HUD. Só manda **intenções** |
| `ReplicatedStorage` | `src/compartilhado/` | `Config`, nomes dos eventos, gerador do mapa, física |
| `RemoteEvent` | mensagens do `Transporte` | Toda conversa cliente ↔ servidor (cópias, nunca objetos compartilhados) |
| `DataStore` | `Salvamento` | `localStorage` no solo; arquivo em disco no servidor online |
| `default.project.json` | `index.html` + `package.json` | Sem build: o navegador carrega os módulos direto |

### Scripts

**Compartilhado** (`src/compartilhado/`)
- `Config.js`: todos os números de balanceamento (tempos, consumo de óleo, raio da luz, velocidades, mapa).
- `Eventos.js`: nomes de todas as mensagens (os "RemoteEvents").
- `Mapa.js`: gera vila, trilhas, floresta, máscaras decorativas e torre de rádio a partir de uma **semente**
  (1987). Servidor e cliente geram o mesmo mapa.
- `Fisica.js`: colisão círculo × (círculo | caixa girada) com grade espacial.
- `TransporteLocal.js`: liga cliente e servidor na mesma página; copia cada mensagem (`structuredClone`).
- `Aleatorio.js`, `Matematica.js`: utilitários.

**Servidor** (`src/servidor/`)
- `Servidor.js`: laço de 20 Hz, recebe mensagens, valida tudo, transmite o estado 10×/s, salva ao amanhecer.
- `CicloDiaNoite.js`: Dia N (4 min) → Noite N (5 min) → Dia N+1.
- `ChamaMae.js`: óleo, consumo (dia/noite), raio seguro, eventos "óleo baixo", "apagou", "reacendeu".
- `Jogadores.js`: posição oficial de cada jogador; anti-teleporte e anti-atravessar-parede.
- `Salvamento.js`: `SalvamentoMemoria` (testes) e `SalvamentoNavegador` (solo).

**Cliente** (`src/cliente/`)
- `main.js`: liga tudo; no solo, cria o `Servidor` dentro da página.
- `Mundo.js`: chão, trilhas, árvores (em setores, para o celular desenhar só o que a câmera vê), ruínas, poço,
  pedras, máscaras e torre.
- `ChamaVisual.js`: lanterna, luz, halo, brasas e o **anel no chão** que mostra o limite seguro.
- `Iluminacao.js`: céu, neblina, sol/lua; entardecer e amanhecer suaves; luz fraca de "olhos acostumados" à noite.
- `JogadorLocal.js`: primeira pessoa; move na hora com a mesma física do servidor.
- `Controles.js`: teclado, mouse e toque (analógico + olhar + botões).
- `Interface.js`: HUD, cartões "Noite X", avisos, entrada e menu.

### Eventos (RemoteEvents)

| Evento | Direção | Dados | Etapa |
|---|---|---|---|
| `Entrar` | cliente → servidor | `{ nome }` | 1 ✅ |
| `Mover` | cliente → servidor | `{ x, z, ry, agachado, correndo }` ~10×/s | 1 ✅ |
| `Pausar` | cliente → servidor | `{ pausado }` (só jogando sozinho) | 1 ✅ |
| `Reiniciar` | cliente → servidor | apagar progresso (só jogando sozinho) | 1 ✅ |
| `Debug` | cliente → servidor | `{ acao: 'acelerar' \| 'pular' \| 'oleo' }` | 1 ✅ |
| `Interagir` | cliente → servidor | `{ alvo }` pegar óleo/madeira, entregar na Chama | 2 |
| `EstouOlhando` | cliente → servidor | `{ ids }` Sem-Rosto na tela, sem obstáculo | 3 |
| `VolumeVoz` | cliente → servidor | `{ nivel }` volume do microfone | 4 |
| `Mundo` | servidor → cliente | `{ semente, estado, debug }` ao conectar | 1 ✅ |
| `BemVindo` | servidor → cliente | `{ id, jogador }` | 1 ✅ |
| `Recusado` | servidor → cliente | `{ motivo }` (ex.: clareira cheia) | 1 ✅ |
| `Estado` | servidor → cliente | fase, noite, relógio, Chama, jogadores ~10×/s | 1 ✅ |
| `Corrigir` | servidor → cliente | `{ x, z }` posição recusada | 1 ✅ |
| `FaseMudou` | servidor → cliente | `{ fase, noite, sobrevivida? }` | 1 ✅ |
| `Chama` | servidor → cliente | `{ tipo: 'baixo' \| 'apagou' \| 'reacendeu' }` | 1 ✅ |
| `Aviso` | servidor → cliente | `{ texto }` | 1 ✅ |

### Autoridade (anti-exploit)
- O cliente nunca altera o mundo: só manda input. Óleo, relógio, coleta, IA e dano ficam no servidor.
- O cliente move o próprio personagem (como no Roblox) e o servidor confere: velocidade máxima,
  limite do mundo e "dentro de parede". Se recusar, manda `Corrigir`.
- Dados salvos passam por `sanitizarMundo` (valor mexido à mão volta para algo seguro).
- Botões de teste só funcionam com `PERMITIR_DEBUG`. Desligar no servidor online.

---

## Plano em etapas

| # | Etapa | Status |
|---|---|---|
| 1 | Mapa placeholder (vila em ruínas, floresta densa, neblina, trilhas, torre), Chama-Mãe (óleo, raio seguro, anel), ciclo dia/noite, contador "Dia/Noite X", salvamento, controles PC e celular | ✅ |
| 2 | Coleta de dia: latas de óleo e madeira na floresta, botão "Pegar" por proximidade, carregar e entregar na Chama (servidor valida distância) | ⏳ próxima |
| 3 | Sem-Rosto: IA no servidor com caminho em grade (A*), andam até o jogador mais próximo fora da luz **só quando ninguém olha**; visão = ângulo da câmera + raio sem obstáculo, enviada pelo cliente e conferida no servidor; congelam na hora; toque = jogador cai e vira espectador até o dia; som de aviso antes de aparecer | |
| 4 | Barulho: correr e quebrar coisas criam pontos de barulho que atraem; agachado é silencioso; microfone (Web Audio `AnalyserNode`) para gritos, com permissão do jogador | |
| 5 | 5 máscaras escondidas: pegar mostra um trecho da história e salva no álbum | |
| 6 | Áudio e clima: passos, respiração, vento, aviso dos Sem-Rosto, música de dia e de noite (Web Audio) | |
| 7 | Co-op online: servidor em Node + WebSocket (1 a 4 jogadores), outros jogadores visíveis, salvamento em arquivo | |
| 8 | Polimento para celular e desempenho (qualidade automática, testes em aparelhos reais) | |

## Números principais (`Config.js`)

| | Valor |
|---|---|
| Dia / noite | 240 s / 300 s |
| Óleo | 100 máx.; consome 0,12/s de dia e 0,22/s à noite (≈ 29 por dia, 66 por noite) |
| Com o tanque cheio | aguenta o Dia 1 e a Noite 1; sem coleta, apaga no Dia 2 |
| Raio seguro | 24 m (cheia) → 7 m (quase vazia) → 0 (apagada) |
| Velocidades | andar 4,2 m/s · correr 7,2 · agachado 1,9 |
| Mapa | clareira de 30 m, 6 casas, 4 trilhas, ~2.400 árvores, limite de 150 m |
