// Ciclo dia/noite — roda só no servidor (ele é o dono do relógio do mundo).
// Dia N (coletar) → Noite N (sobreviver) → Dia N+1 ...

import { Config } from '../compartilhado/Config.js';

const TOLERANCIA = 1e-9; // evita travar por arredondamento de ponto flutuante

export class CicloDiaNoite {
  constructor(cfg = Config.ciclo, inicial = {}) {
    this.cfg = cfg;
    this.noite = inicial.noite ?? 1;
    this.fase = inicial.fase ?? 'dia';
    this.decorrido = inicial.decorrido ?? 0;
  }

  get duracao() {
    return this.fase === 'dia' ? this.cfg.DURACAO_DIA : this.cfg.DURACAO_NOITE;
  }

  get restante() {
    return Math.max(0, this.duracao - this.decorrido);
  }

  /** Avança o relógio e devolve os eventos que aconteceram (vários, se `dt` for grande). */
  avancar(dt) {
    const eventos = [];
    this.decorrido += dt;
    while (this.decorrido >= this.duracao - TOLERANCIA) {
      this.decorrido = Math.max(0, this.decorrido - this.duracao);
      if (this.fase === 'dia') {
        this.fase = 'noite';
        eventos.push({ tipo: 'anoiteceu', noite: this.noite });
      } else {
        const sobrevivida = this.noite;
        this.fase = 'dia';
        this.noite += 1;
        eventos.push({ tipo: 'amanheceu', noite: this.noite, sobrevivida });
      }
    }
    return eventos;
  }

  /** Teste: pula para alguns segundos antes do fim da fase atual. */
  pularParaFim(segundosAntes = 3) {
    this.decorrido = Math.max(this.decorrido, this.duracao - segundosAntes);
  }

  estado() {
    return { fase: this.fase, noite: this.noite, decorrido: this.decorrido, duracao: this.duracao };
  }
}
