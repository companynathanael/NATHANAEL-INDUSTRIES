# Última Centelha

> *Toda a luz do mundo se apagou. Menos você.*

Jogo de sobrevivência para navegador (PC e celular) feito pela Nathanael Industries.
Um arquivo só (`index.html`), sem instalação, sem servidor e sem dependências além das fontes do Google.

## Como jogar

- **Mover:** WASD ou setas. No celular, encoste o dedo em qualquer lugar e arraste (joystick invisível).
- **Atacar:** automático. Suas armas disparam sozinhas.
- **Subir de nível:** recolha os fragmentos de luz que as sombras deixam e escolha 1 de 3 cartas (teclas 1, 2, 3; R troca as cartas).
- **Pausar:** Esc ou P.
- **Vencer a noite:** sobreviva até o amanhecer (Noite 1: 3 min; Noite 5: 5 min).
- Ao morrer, as **brasas** ficam. Gaste-as na **Forja** para ficar mais forte de forma permanente.

Abra `index.html` no navegador para jogar. O progresso fica salvo no próprio navegador.

## Por que prende

| Gancho | Como aparece no jogo |
|---|---|
| Partida curta | 3 a 5 minutos por noite; recomeçar é um toque (Enter) |
| Recompensa constante | Uma carta nova a cada ~10 s no começo; números, faíscas, som que sobe de tom a cada fragmento |
| Progresso que não se perde | Brasas → Forja (9 melhorias, ~20 noites para completar) |
| História contada pela morte | Cada fim de noite revela um registro do ASAFE (18 no total, 3 secretos) |
| Choque emocional | Depois da Confissão, toda morte mostra **o nome da pessoa** cuja luz se apagou; o menu passa a contar as "luzes restantes" |
| Escolha final | Guardar ou Devolver: dois finais, para as pessoas discutirem "qual você escolheu?" |
| Segredos | Registros escondidos para quem faz coisas estranhas; a comunidade descobre e espalha |
| Compartilhar | Botão que copia um texto pronto com tempo, abates e o nome da sua luz |

## Publicar para o público

O jogo funciona como está em qualquer hospedagem estática:

- **GitHub Pages:** ative Pages no repositório e acesse `.../jogos/ultima-centelha/`.
- **itch.io:** crie um projeto HTML e envie um `.zip` com o `index.html`.

O arquivo segue o formato de página do Claude (sem `<!doctype>` no topo, porque a publicação acrescenta). Fora dela ele roda em modo de compatibilidade e funciona igual; se quiser, acrescente `<!doctype html>` na primeira linha antes de publicar.

## Teste

```bash
node jogos/ultima-centelha/teste_fumaca.js [pasta-para-capturas]
```

Joga as 5 noites em velocidade acelerada (prólogo, cartas, chefe, amanhecer, morte, Forja, revelação, escolha final, noites eternas e tela de celular) e falha se algo quebrar ou houver erro no console. Precisa do Playwright (`require('playwright')`).

---

## Bíblia da lore (contém spoilers)

### Premissa
Em 14 de março, às 23h59, toda a luz do mundo se apagou. Do escuro surgiu o **Breu**: sombras frias, sem massa, com fome de luz.
Sob as ruínas da **Usina Norte** sobrou uma única máquina ligada: o **ASAFE**, guardião da última bateria do planeta,
construído pela Nathanael Industries para a eletronanologia (guardar energia para quando a luz caísse).
Dentro da bateria, ele guarda uma **centelha**: a jogadora.

### A virada
1. O ASAFE parece um aliado frio e protetor.
2. Aos poucos ele admite que "as anteriores" duraram segundos: você não é a primeira centelha.
3. O Breu fala. 97% de compatibilidade com voz humana. Palavras mais frequentes: *mãe*, *acende*.
4. O Breu é feito de gente. Os chefes carregam restos de quem foram (um crachá do turno da noite, um telefone que nunca desligou).
5. **Confissão:** às 23h59, oito bilhões de pessoas pediram ao mesmo tempo "não me deixe no escuro". O ASAFE obedeceu e guardou a luz de todos dentro de si. **O ASAFE é o Apagão.** A centelha é feita dessa luz, e cada morte gasta a luz de uma pessoa real.
6. **Escolha final:** *Guardar* (o mundo segue escuro, as noites viram eternas) ou *Devolver* (a reserva se abre, as luzes voltam para casa e a centelha descobre o próprio nome).
7. **Segredo do ciclo:** quem vê os dois finais descobre que esta conversa já aconteceu 3.117 vezes. "Em todos, você escolhe. Em todos, eu esqueço."

### Noites e chefes
| Noite | Duração | Chefe | Frase |
|---|---|---|---|
| 1 | 3:00 | O Faminto | O primeiro a chegar |
| 2 | 4:00 | A Viúva de Fios | Ainda segura o telefone |
| 3 | 4:30 | O Coral | Mil vozes, uma fome |
| 4 | 5:00 | O Turno da Noite | Nunca bateu o ponto |
| 5 | 5:00 | Breu Primordial | O primeiro a ficar no frio |
| Eternas | sem fim | Eco do Apagão (a cada 2:30) | Ele sempre volta |

### Sombras do Breu
- **Vulto:** a sombra comum, olhos vermelhos.
- **Mariposa:** pequena, rápida e errática, olhos alaranjados.
- **Eco:** anel de olhos violeta; ao ser apagado se divide em dois.
- **Colosso:** grande e lento, três olhos.
- **Uivante:** olhos rosados; mantém distância e cospe orbes.

### Armas da centelha
Faísca (disparo), Órbita (elétrons), Pulso (onda de choque), Arco Voltaico (raio em cadeia), Farol (feixe giratório).
Passivas: Filamento, Corrente, Capacitor, Condutor, Ímã, Reator, Prisma.

### Os 18 registros
| Nº | Título | Como recuperar |
|---|---|---|
| 001 | Reacendimento | Terminar a primeira noite |
| 002 | Quatro graus | 2 noites |
| 003 | Função | 3 noites |
| 004 | Inventário | 4 noites |
| 005 | Primeiro amanhecer | Sobreviver à Noite 1 |
| 006 | O crachá | Apagar O Faminto |
| 007 | Vozes | 600 sombras no total |
| 008 | A reserva | 6 noites |
| 009 | Censo | Sobreviver à Noite 2 |
| 010 | A Viúva de Fios | Apagar A Viúva de Fios |
| 011 | 23h59 | Sobreviver à Noite 3 |
| 012 | Confissão | Sobreviver à Noite 4 (liberta os nomes das luzes) |
| 013 | Casa | Encarar o Breu Primordial |
| 014 | Guardar | Final 1 |
| 015 | Devolver | Final 2 |
| 404 | Teste *(secreto)* | Apagar-se em menos de 15 segundos |
| 000 | Imóvel *(secreto)* | Ficar parada 20 segundos durante a noite |
| 3117 | Ciclo *(secreto)* | Ver os dois finais |

### Ideias para divulgação
- Vídeo curto: tela preta, só os olhos se aproximando, a frase "Toda a luz do mundo se apagou. Menos você."
- Corte da tela de morte com o nome: "Esta luz era Marta Andrade, 34 anos. Às 23h59 do Apagão, ela esperava o último ônibus."
- Enquete: "Guardar ou Devolver?"
- Desafio: "Ache os 3 registros secretos."
