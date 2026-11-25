// JogadorLocal — o resgatista controlado por esta tela, em primeira pessoa.
// Move na hora (sem esperar o servidor) usando a mesma física do servidor;
// se o servidor recusar a posição, ele manda CORRIGIR e o jogador volta.

import { moverCirculo } from '../compartilhado/Fisica.js';
import { limitar } from '../compartilhado/Matematica.js';

const LIMITE_OLHAR = 1.35; // ~77° para cima/baixo

export class JogadorLocal {
  constructor(camera, mapa, cfg) {
    this.camera = camera;
    this.mapa = mapa;
    this.cfg = cfg;
    this.x = 0;
    this.z = 0;
    this.yaw = 0;
    this.pitch = 0;
    this.altura = cfg.ALTURA_OLHOS;
    this.fasePasso = 0;
    this.velocidade = 0;
    this.agachado = false;
    this.correndo = false;
  }

  posicionar(x, z, yaw) {
    this.x = x;
    this.z = z;
    if (typeof yaw === 'number') {
      this.yaw = yaw;
      this.pitch = -0.05;
    }
    this.#aplicarCamera(0);
  }

  atualizar(dt, controles) {
    const { dx, dy } = controles.consumirOlhar();
    this.yaw -= dx;
    this.pitch = limitar(this.pitch - dy, -LIMITE_OLHAR, LIMITE_OLHAR);

    const eixo = controles.eixo;
    this.agachado = controles.agachado;
    this.correndo = controles.correndo && Math.hypot(eixo.x, eixo.y) > 0.1;
    const vel = this.agachado ? this.cfg.VEL_AGACHADO : this.correndo ? this.cfg.VEL_CORRER : this.cfg.VEL_ANDAR;

    // frente = (−sen yaw, −cos yaw); direita = (cos yaw, −sen yaw)
    const s = Math.sin(this.yaw), c = Math.cos(this.yaw);
    const mx = c * eixo.x + s * eixo.y;
    const mz = -s * eixo.x + c * eixo.y;
    const antes = { x: this.x, z: this.z };
    ({ x: this.x, z: this.z } = moverCirculo(this.mapa, this.x, this.z, mx * vel * dt, mz * vel * dt, this.cfg.RAIO));
    this.velocidade = dt > 0 ? Math.hypot(this.x - antes.x, this.z - antes.z) / dt : 0;

    const alvo = this.agachado ? this.cfg.ALTURA_AGACHADO : this.cfg.ALTURA_OLHOS;
    this.altura += (alvo - this.altura) * Math.min(1, dt * 10);
    this.#aplicarCamera(dt);
  }

  #aplicarCamera(dt) {
    // Balanço da cabeça ao andar (mais forte correndo, quase nada agachado).
    let balanco = 0;
    if (this.velocidade > 0.3) {
      this.fasePasso += dt * this.velocidade * 1.9;
      const amp = this.correndo ? 0.07 : this.agachado ? 0.02 : 0.04;
      balanco = Math.sin(this.fasePasso * 2) * amp;
    }
    this.camera.position.set(this.x, this.altura + balanco, this.z);
    this.camera.rotation.set(this.pitch, this.yaw, 0, 'YXZ');
  }
}
