# Eletronanologia

> Tecnologia-símbolo do Asafe. **Status: conceito / pesquisa.**

## O que é
Um sistema que **armazena eletricidade** para que, **quando a luz cair**, as IAs da
Nathanael Industries continuem funcionando normalmente.

Ela **não gera** eletricidade nem internet por conta própria: ela **guarda energia**
enquanto há luz e **entrega essa energia** quando a luz acaba.

## Como funciona
1. **Com luz:** a rede elétrica alimenta os equipamentos e, ao mesmo tempo, carrega as baterias.
2. **Luz caiu:** a troca para a bateria é instantânea. Servidores e IAs não desligam.
3. **Durante a queda:** o Asafe acompanha a carga restante da bateria.
4. **Bateria acabando:** o Asafe avisa o Sr. Nathanael, salva os dados e desliga tudo com segurança, sem perder nada.
5. **Luz voltou:** os equipamentos voltam a usar a rede elétrica e as baterias recarregam.

## O que precisa ficar ligado na bateria
- O(s) servidor(es) onde rodam o Asafe e as IAs.
- O **roteador/modem**. Sem ele não há internet, mesmo com o servidor ligado.

> Observação: se a queda de luz atingir também a operadora de internet, o roteador
> fica ligado mas sem sinal. Um chip 4G/5G de reserva resolve esse caso (opcional).

## Integração com o Asafe
Cada unidade de eletronanologia envia seu estado ao Asafe pelo endpoint
`/servidores/sinal`, no campo `info`. Exemplo:

```json
{ "nome": "eletro-01", "endereco": "10.0.0.20",
  "info": { "na_rede_eletrica": false, "bateria_pct": 72, "autonomia_min": 95 } }
```

## Decisões do Sr. Nathanael
- **Autonomia:** ~**2 dias (48 h)** sem luz.
- **Estrutura:** **3 a 4 caixas virtuais** de geradores (padrão: 4). Quando uma esvazia, a próxima assume.
- **O que fica ligado:** **apenas o Asafe**. As outras IAs funcionam através dele.
- **Orçamento:** **R$ 0**. Por isso a eletronanologia começa **virtual** (em software).

## Versão virtual (já implementada)
Código em `asafe/eletronanologia.py`, com rotas na API do Asafe:

| Rota | O que faz |
|---|---|
| `GET /energia` | Estado das caixas: carga, autonomia restante, nível |
| `POST /energia/queda` | Simula uma queda de luz |
| `POST /energia/retorno` | Simula a volta da luz (as caixas recarregam) |
| `POST /energia/avancar?horas=N` | Avança o tempo da simulação |

Níveis: `normal` → `bateria` → `aviso` (≤25%) → `critico` (≤10%, salvar e desligar) → `desligado`.
A cada mudança de nível, o Asafe **envia uma mensagem automática ao Sr. Nathanael**.

Configuração: `ELETRO_CAIXAS` (padrão 4) e `ELETRO_CONSUMO_W` (consumo estimado, padrão 60 W).
As caixas são dimensionadas automaticamente para cobrir 48 h.

## Referência para a versão física (futuro)
Energia necessária = consumo × 48 h. Exemplos:
- Mini PC / notebook (~15–20 W): ~0,7–1 kWh → 4 caixas de ~250 Wh.
- PC comum (~60 W): ~2,9 kWh → 4 caixas de ~720 Wh.
- Servidor (~150 W): ~7,2 kWh → 4 caixas de ~1,8 kWh.

> Dica de custo zero: um **notebook** já tem bateria própria (é uma "caixa" embutida),
> e hospedar o Asafe em um **serviço de nuvem gratuito** elimina o problema da queda de
> luz local, pois os data centers já têm geradores próprios.

## Fases
1. **Virtual:** ✅ simulação das caixas, alertas e níveis dentro do Asafe.
2. **Protótipo físico:** quando houver recursos, um nobreak (UPS) com bateria alimentando o servidor do Asafe + roteador.
3. **Monitoramento real:** o Asafe lê o estado da bateria e envia alertas.
4. **Desligamento inteligente:** o Asafe salva tudo e desliga com segurança antes da bateria zerar.
5. **Expansão:** mais baterias, maior autonomia e, opcionalmente, recarga solar.
6. **Miniaturização ("nano"):** linha de pesquisa para unidades menores e mais eficientes.

## Questões em aberto
- Em que máquina o Asafe vai rodar (para trocar o consumo estimado de 60 W pelo real)?
