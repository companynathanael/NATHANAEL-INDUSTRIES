// Servidor — a autoridade do jogo (equivalente ao ServerScriptService do Roblox).
// Tempo, óleo, posições oficiais, salvamento e (próximas etapas) coleta, IA e dano ficam AQUI.
// Não usa nada do navegador: o mesmo código roda dentro da página (solo) ou em Node (co-op online).

import { Config } from '../compartilhado/Config.js';
import { Eventos } from '../compartilhado/Eventos.js';
import { gerarMapa } from '../compartilhado/Mapa.js';
import { arredondar, limitar } from '../compartilhado/Matematica.js';
import { CicloDiaNoite } from './CicloDiaNoite.js';
import { ChamaMae } from './ChamaMae.js';
import { Jogadores } from './Jogadores.js';
import { SalvamentoMemoria } from './Salvamento.js';

export const CHAVE_MUNDO = 'mundo';
const VERSAO_SALVAMENTO = 1;

/** Confere o que veio do salvamento (pode estar corrompido ou ter sido mexido à mão). */
export function sanitizarMundo(dados, config = Config) {
  const { ciclo, chama } = config;
  const noite = Number.isInteger(dados?.noite) && dados.noite >= 1 && dados.noite <= ciclo.NOITE_FINAL ? dados.noite : 1;
  const oleo = typeof dados?.oleo === 'number' && Number.isFinite(dados.oleo)
    ? limitar(dados.oleo, 0, chama.OLEO_MAX)
    : chama.OLEO_INICIAL;
  return { noite, oleo };
}

export class Servidor {
  constructor({
    config = Config,
    salvamento = new SalvamentoMemoria(),
    relogio = () => performance.now() / 1000,
    mapa = null,
  } = {}) {
    this.config = config;
    this.salvamento = salvamento;
    this.relogio = relogio;
    this.mapa = mapa ?? gerarMapa(config.mapa);
    this.conexoes = new Map();
    this.jogadores = new Jogadores(config.jogador, this.mapa, relogio);
    this.pausas = new Set();
    this.aceleracao = 1;
    this.acumuladoEstado = 0;
    this.ciclo = null;
    this.chama = null;
    this.ultimoSalvamento = Promise.resolve(true);
  }

  async iniciar() {
    let salvo = null;
    try {
      salvo = await this.salvamento.carregar(CHAVE_MUNDO);
    } catch (erro) {
      console.warn('[Servidor] não consegui ler o salvamento:', erro);
    }
    const { noite, oleo } = sanitizarMundo(salvo, this.config);
    this.ciclo = new CicloDiaNoite(this.config.ciclo, { noite });
    this.chama = new ChamaMae(this.config.chama, oleo, this.mapa.chama);
    return this;
  }

  /** Laço automático (no navegador ou no Node). Nos testes, chama-se passo() à mão. */
  iniciarLaco() {
    let ultimo = this.relogio();
    this._laco = setInterval(() => {
      const agora = this.relogio();
      this.passo(agora - ultimo);
      ultimo = agora;
    }, 1000 / this.config.servidor.TICK_HZ);
  }

  parar() {
    clearInterval(this._laco);
  }

  /** O mundo só anda com alguém dentro; jogando sozinho, o menu também pausa. */
  get pausado() {
    const n = this.jogadores.quantidade;
    if (n === 0) return true;
    return this.config.servidor.PAUSA_SOLO && n === 1 && this.pausas.size > 0;
  }

  // ------------------------------------------------------------------ conexões

  conectar(conexao) {
    const id = conexao.id;
    this.conexoes.set(id, conexao);
    conexao.aoReceber((tipo, dados) => this.receber(id, tipo, dados));
    conexao.aoFechar?.(() => this.desconectar(id));
    conexao.enviar(Eventos.MUNDO, {
      semente: this.mapa.semente,
      estado: this.estado(),
      debug: this.config.servidor.PERMITIR_DEBUG,
      maxJogadores: this.config.servidor.MAX_JOGADORES,
    });
  }

  desconectar(id) {
    const j = this.jogadores.obter(id);
    this.conexoes.delete(id);
    this.jogadores.remover(id);
    this.pausas.delete(id);
    if (j && this.jogadores.quantidade > 0) this.transmitir(Eventos.AVISO, { texto: `${j.nome} saiu da clareira.` });
  }

  enviarPara(id, tipo, dados) {
    this.conexoes.get(id)?.enviar(tipo, dados);
  }

  transmitir(tipo, dados) {
    for (const c of this.conexoes.values()) c.enviar(tipo, dados);
  }

  /** Toda mensagem do cliente entra por aqui. Nada do que vem dele é confiável. */
  receber(id, tipo, dados) {
    try {
      switch (tipo) {
        case Eventos.ENTRAR: return this.#aoEntrar(id, dados);
        case Eventos.MOVER: return this.#aoMover(id, dados);
        case Eventos.PAUSAR: return this.#aoPausar(id, dados);
        case Eventos.REINICIAR: return this.#aoReiniciar(id);
        case Eventos.DEBUG: return this.#aoDebug(id, dados);
        default: return undefined; // evento desconhecido: ignora
      }
    } catch (erro) {
      console.warn(`[Servidor] mensagem inválida (${tipo}) de ${id}:`, erro);
      return undefined;
    }
  }

  #aoEntrar(id, dados) {
    if (this.jogadores.obter(id)) return;
    if (this.jogadores.quantidade >= this.config.servidor.MAX_JOGADORES) {
      this.enviarPara(id, Eventos.RECUSADO, { motivo: `A clareira já tem ${this.config.servidor.MAX_JOGADORES} jogadores.` });
      return;
    }
    const nome = String(dados?.nome ?? '').trim().slice(0, 20) || 'Resgatista';
    const j = this.jogadores.adicionar(id, { nome });
    this.enviarPara(id, Eventos.BEM_VINDO, { id, jogador: { x: j.x, z: j.z, ry: j.ry } });
    if (this.jogadores.quantidade > 1) this.transmitir(Eventos.AVISO, { texto: `${nome} chegou à clareira.` });
  }

  #aoMover(id, dados) {
    const resultado = this.jogadores.mover(id, dados);
    if (resultado.corrigir) {
      const j = this.jogadores.obter(id);
      this.enviarPara(id, Eventos.CORRIGIR, { x: j.x, z: j.z });
    }
  }

  #aoPausar(id, dados) {
    if (!this.jogadores.obter(id)) return;
    if (dados?.pausado) this.pausas.add(id);
    else this.pausas.delete(id);
  }

  #aoReiniciar(id) {
    if (!this.jogadores.obter(id)) return;
    if (this.jogadores.quantidade > 1) {
      this.enviarPara(id, Eventos.AVISO, { texto: 'Só dá para apagar o progresso jogando sozinho.' });
      return;
    }
    this.ciclo = new CicloDiaNoite(this.config.ciclo, { noite: 1 });
    this.chama = new ChamaMae(this.config.chama, this.config.chama.OLEO_INICIAL, this.mapa.chama);
    this.aceleracao = 1;
    this.ultimoSalvamento = this.salvar();
    for (const j of this.jogadores.lista()) {
      this.jogadores.renascer(j.id);
      this.enviarPara(j.id, Eventos.CORRIGIR, { x: j.x, z: j.z, ry: j.ry });
    }
    this.transmitir(Eventos.FASE_MUDOU, { fase: 'dia', noite: 1, reinicio: true });
  }

  #aoDebug(id, dados) {
    if (!this.config.servidor.PERMITIR_DEBUG || !this.jogadores.obter(id)) return;
    switch (dados?.acao) {
      case 'acelerar': {
        const opcoes = this.config.ciclo.ACELERACOES_DEBUG;
        this.aceleracao = opcoes[(opcoes.indexOf(this.aceleracao) + 1) % opcoes.length];
        this.transmitir(Eventos.AVISO, { texto: `Tempo do teste: ${this.aceleracao}×` });
        break;
      }
      case 'pular':
        this.ciclo.pularParaFim(3);
        break;
      case 'oleo':
        this.#tratarChama(this.chama.adicionarOleo(this.config.chama.OLEO_DEBUG));
        break;
      default:
        break;
    }
  }

  // ------------------------------------------------------------------ simulação

  passo(dtReal) {
    if (!this.ciclo) return;
    const dt = limitar(dtReal, 0, this.config.servidor.DT_MAXIMO);
    if (!this.pausado) this.simular(dt * this.aceleracao);
    this.acumuladoEstado += dt;
    if (this.acumuladoEstado >= 1 / this.config.servidor.ESTADO_HZ) {
      this.acumuladoEstado = 0;
      this.transmitir(Eventos.ESTADO, this.estado());
    }
  }

  /** Avança `dt` segundos de jogo, quebrando o passo na virada dia↔noite (o óleo usa a taxa certa). */
  simular(dt) {
    let restante = dt;
    for (let guarda = 0; restante > 1e-9 && guarda < 1000; guarda++) {
      const d = Math.min(restante, this.ciclo.restante);
      this.#tratarChama(this.chama.avancar(d, this.ciclo.fase));
      this.#tratarCiclo(this.ciclo.avancar(d));
      restante -= d;
    }
  }

  #tratarCiclo(eventos) {
    for (const ev of eventos) {
      if (ev.tipo === 'anoiteceu') {
        this.transmitir(Eventos.FASE_MUDOU, { fase: 'noite', noite: ev.noite });
      } else if (ev.tipo === 'amanheceu') {
        this.transmitir(Eventos.FASE_MUDOU, { fase: 'dia', noite: ev.noite, sobrevivida: ev.sobrevivida });
        this.ultimoSalvamento = this.salvar(); // salva a cada noite sobrevivida
      }
    }
  }

  #tratarChama(eventos) {
    for (const ev of eventos) {
      if (ev.tipo === 'oleoBaixo') this.transmitir(Eventos.CHAMA, { tipo: 'baixo' });
      else if (ev.tipo === 'apagou') this.transmitir(Eventos.CHAMA, { tipo: 'apagou' });
      else if (ev.tipo === 'reacendeu') this.transmitir(Eventos.CHAMA, { tipo: 'reacendeu' });
    }
  }

  async salvar() {
    try {
      return await this.salvamento.salvar(CHAVE_MUNDO, {
        versao: VERSAO_SALVAMENTO,
        noite: this.ciclo.noite,
        oleo: arredondar(this.chama.oleo),
      });
    } catch (erro) {
      console.warn('[Servidor] não consegui salvar:', erro);
      return false;
    }
  }

  /** Retrato do mundo que vai para todos os clientes. */
  estado() {
    return {
      ...this.ciclo.estado(),
      aceleracao: this.aceleracao,
      pausado: this.pausado,
      chama: this.chama.estado(),
      jogadores: this.jogadores.lista().map((j) => ({
        id: j.id,
        nome: j.nome,
        x: arredondar(j.x),
        z: arredondar(j.z),
        ry: arredondar(j.ry, 3),
        agachado: j.agachado,
        correndo: j.correndo,
        vivo: j.vivo,
        naLuz: this.chama.contem(j.x, j.z),
      })),
    };
  }
}
