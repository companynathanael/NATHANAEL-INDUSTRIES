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

## Fases
1. **Protótipo:** um nobreak (UPS) com bateria alimentando servidor + roteador, para validar a ideia.
2. **Monitoramento:** o Asafe lê o estado da bateria e envia alertas.
3. **Desligamento inteligente:** o Asafe salva tudo e desliga com segurança antes da bateria zerar.
4. **Expansão:** mais baterias, maior autonomia e, opcionalmente, recarga solar.
5. **Miniaturização ("nano"):** linha de pesquisa para unidades menores e mais eficientes.

## Questões em aberto
- Quanto tempo as IAs precisam continuar funcionando sem luz (30 min? 4 h? 1 dia?)?
- Quais equipamentos ficarão ligados (para calcular o tamanho da bateria)?
- Orçamento do primeiro protótipo.
