// Chama-Mãe — a lanterna antiga no centro da vila. Roda só no servidor.
// O óleo cai com o tempo (mais rápido à noite) e o raio de luz seguro encolhe junto.
// Se o óleo zerar, a Chama apaga e (etapa 3) os Sem-Rosto podem entrar na vila.

import { Config } from '../compartilhado/Config.js';
import { limitar, misturar } from '../compartilhado/Matematica.js';

export class ChamaMae {
  constructor(cfg = Config.chama, oleo = cfg.OLEO_INICIAL, posicao = { x: 0, z: 0 }) {
    this.cfg = cfg;
    this.posicao = { x: posicao.x, z: posicao.z };
    this.oleo = limitar(oleo, 0, cfg.OLEO_MAX);
    this.avisouBaixo = this.oleo <= cfg.OLEO_BAIXO;
  }

  get acesa() {
    return this.oleo > 0;
  }

  get fracao() {
    return this.oleo / this.cfg.OLEO_MAX;
  }

  /** Raio seguro: vai de RAIO_MAX (cheia) a RAIO_MIN (quase vazia); 0 quando apagada. */
  get raio() {
    if (!this.acesa) return 0;
    return misturar(this.cfg.RAIO_MIN, this.cfg.RAIO_MAX, this.fracao);
  }

  consumoPorSegundo(fase) {
    return fase === 'noite' ? this.cfg.CONSUMO_NOITE : this.cfg.CONSUMO_DIA;
  }

  avancar(dt, fase) {
    const eventos = [];
    if (!this.acesa) return eventos;
    this.oleo = Math.max(0, this.oleo - this.consumoPorSegundo(fase) * dt);
    if (!this.avisouBaixo && this.oleo > 0 && this.oleo <= this.cfg.OLEO_BAIXO) {
      this.avisouBaixo = true;
      eventos.push({ tipo: 'oleoBaixo', oleo: this.oleo });
    }
    if (this.oleo === 0) eventos.push({ tipo: 'apagou' });
    return eventos;
  }

  /** Entregar óleo (etapa 2: latas coletadas de dia). */
  adicionarOleo(quantidade) {
    const estavaApagada = !this.acesa;
    const antes = this.oleo;
    this.oleo = limitar(this.oleo + Math.max(0, quantidade), 0, this.cfg.OLEO_MAX);
    if (this.oleo > this.cfg.OLEO_BAIXO) this.avisouBaixo = false;
    const eventos = [{ tipo: 'abastecida', quantidade: this.oleo - antes }];
    if (estavaApagada && this.acesa) eventos.push({ tipo: 'reacendeu' });
    return eventos;
  }

  /** O ponto (x, z) está dentro da luz segura? */
  contem(x, z) {
    const r = this.raio;
    const dx = x - this.posicao.x, dz = z - this.posicao.z;
    return r > 0 && dx * dx + dz * dz <= r * r;
  }

  estado() {
    return {
      oleo: Math.round(this.oleo * 100) / 100,
      oleoMax: this.cfg.OLEO_MAX,
      raio: Math.round(this.raio * 100) / 100,
      acesa: this.acesa,
    };
  }
}
