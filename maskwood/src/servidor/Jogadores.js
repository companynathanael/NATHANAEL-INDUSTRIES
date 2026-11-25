// Jogadores — o servidor guarda a posição "oficial" de cada um.
// O cliente move o próprio personagem (para não sentir atraso) e manda a posição;
// o servidor só aceita se for possível (velocidade, limite do mundo, sem estar dentro de parede).
// É o mesmo modelo do Roblox: o cliente é dono da física do personagem, o servidor confere.

import { Config } from '../compartilhado/Config.js';
import { sobrepoeColisor } from '../compartilhado/Fisica.js';

const numero = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);

export class Jogadores {
  constructor(cfg = Config.jogador, mapa, relogio = () => performance.now() / 1000) {
    this.cfg = cfg;
    this.mapa = mapa;
    this.relogio = relogio;
    this.porId = new Map();
  }

  get quantidade() {
    return this.porId.size;
  }

  lista() {
    return [...this.porId.values()];
  }

  obter(id) {
    return this.porId.get(id);
  }

  /** Primeiro ponto de nascimento que ninguém está usando. */
  #nascimentoLivre() {
    const usados = new Set(this.lista().map((j) => j.vaga));
    const total = this.mapa.nascimentos.length;
    for (let v = 0; v < total; v++) if (!usados.has(v)) return v;
    return this.porId.size % total;
  }

  adicionar(id, { nome }) {
    const vaga = this.#nascimentoLivre();
    const n = this.mapa.nascimentos[vaga];
    const jogador = {
      id, nome, vaga,
      x: n.x, z: n.z, ry: n.ry,
      agachado: false, correndo: false, vivo: true,
      ultimoMovimento: this.relogio(),
    };
    this.porId.set(id, jogador);
    return jogador;
  }

  renascer(id) {
    const j = this.porId.get(id);
    if (!j) return null;
    const n = this.mapa.nascimentos[j.vaga];
    Object.assign(j, { x: n.x, z: n.z, ry: n.ry, vivo: true, agachado: false, correndo: false, ultimoMovimento: this.relogio() });
    return j;
  }

  remover(id) {
    this.porId.delete(id);
  }

  /** Valida a posição que o cliente mandou. Devolve { aceito, corrigir }. */
  mover(id, dados) {
    const j = this.porId.get(id);
    if (!j || !j.vivo) return { aceito: false, corrigir: false };

    const ry = numero(dados?.ry);
    if (ry !== null) j.ry = ry;
    j.agachado = Boolean(dados?.agachado);
    j.correndo = Boolean(dados?.correndo) && !j.agachado;

    const x = numero(dados?.x), z = numero(dados?.z);
    const agora = this.relogio();
    const dt = Math.min(1, Math.max(0.05, agora - j.ultimoMovimento));
    j.ultimoMovimento = agora;
    if (x === null || z === null) return { aceito: false, corrigir: true };

    const alcance = this.cfg.VEL_CORRER * this.cfg.TOLERANCIA_VEL * dt + this.cfg.FOLGA_M;
    const longeDemais = Math.hypot(x - j.x, z - j.z) > alcance;
    const foraDoMundo = Math.hypot(x, z) > this.mapa.raioMundo;
    const dentroDeAlgo = sobrepoeColisor(this.mapa, x, z, this.cfg.RAIO * 0.6);
    if (longeDemais || foraDoMundo || dentroDeAlgo) return { aceito: false, corrigir: true };

    j.x = x;
    j.z = z;
    return { aceito: true, corrigir: false };
  }
}
