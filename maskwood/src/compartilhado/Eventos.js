// Eventos — nomes das mensagens entre cliente e servidor.
// É o equivalente aos RemoteEvents do Roblox: o cliente só manda INTENÇÕES (input, "estou olhando"),
// e o servidor decide tudo (tempo, óleo, coleta, IA, dano) e devolve o resultado.

export const Eventos = Object.freeze({
  // ---------- Cliente → Servidor ----------
  ENTRAR: 'Entrar',             // { nome }                                   etapa 1
  MOVER: 'Mover',               // { x, z, ry, agachado, correndo } ~10x/s    etapa 1
  PAUSAR: 'Pausar',             // { pausado } — só vale jogando sozinho      etapa 1
  REINICIAR: 'Reiniciar',       // {} apaga o progresso — só jogando sozinho  etapa 1
  DEBUG: 'Debug',               // { acao: 'acelerar' | 'pular' | 'oleo' }    etapa 1 (só com PERMITIR_DEBUG)
  // Próximas etapas (ainda não usados):
  INTERAGIR: 'Interagir',       // { alvo } pegar óleo/madeira, entregar na Chama        etapa 2
  ESTOU_OLHANDO: 'EstouOlhando',// { ids: [...] } Sem-Rosto que o jogador está vendo     etapa 3
  VOLUME_VOZ: 'VolumeVoz',      // { nivel } volume do microfone (grito = barulho)       etapa 4

  // ---------- Servidor → Cliente ----------
  MUNDO: 'Mundo',               // { semente, estado, debug } ao conectar
  BEM_VINDO: 'BemVindo',        // { id, jogador: { x, z, ry } } depois de ENTRAR
  RECUSADO: 'Recusado',         // { motivo } (ex.: servidor cheio)
  ESTADO: 'Estado',             // retrato do mundo ~10x/s
  CORRIGIR: 'Corrigir',         // { x, z, ry? } o servidor recusou a posição do cliente
  FASE_MUDOU: 'FaseMudou',      // { fase, noite, sobrevivida?, reinicio? }
  CHAMA: 'Chama',               // { tipo: 'baixo' | 'apagou' | 'reacendeu' }
  AVISO: 'Aviso',               // { texto }
});
