// Iluminação e clima do ciclo dia/noite: céu, neblina, luz ambiente e sol/lua.
// O dia é nublado e cinza-esverdeado; o entardecer puxa para o cobre; a noite é azul-breu.

import * as THREE from 'three';
import { misturar, suave } from '../compartilhado/Matematica.js';

/** 0 = dia claro, 1 = noite fechada. Escurece no fim do dia e clareia no fim da noite. */
export function fatorNoite(fase, decorrido, duracao, cfgCiclo) {
  if (fase === 'dia') return suave(duracao - cfgCiclo.ENTARDECER_S, duracao, decorrido);
  return 1 - suave(duracao - cfgCiclo.AMANHECER_S, duracao, decorrido);
}

const PALETAS = {
  dia: { ceu: 0x8c9891, nevoa: 0.0145, hemiCeu: 0xc8d0c8, hemiChao: 0x5c5846, hemi: 2.0, sol: 0xe8dfca, solInt: 1.6 },
  crepusculo: { ceu: 0x5a4642, nevoa: 0.024, hemiCeu: 0x8c6f66, hemiChao: 0x231c18, hemi: 1.1, sol: 0xd98a5a, solInt: 0.8 },
  noite: { ceu: 0x0b1019, nevoa: 0.036, hemiCeu: 0x4d6290, hemiChao: 0x15171d, hemi: 0.95, sol: 0x8ea2cc, solInt: 0.5 },
};

function preparar(p) {
  return { ...p, ceu: new THREE.Color(p.ceu), hemiCeu: new THREE.Color(p.hemiCeu), hemiChao: new THREE.Color(p.hemiChao), sol: new THREE.Color(p.sol) };
}

// "Olhos acostumados ao escuro": luz fria e fraca presa à câmera, só à noite.
// Sem ela o chão longe da Chama fica preto e o jogador não veria o que chega perto
// (regra de design: a morte nunca pode parecer injusta).
const OLHOS_INTENSIDADE = 24;

export class Iluminacao {
  constructor(cena, camera) {
    this.cena = cena;
    this.olhos = new THREE.PointLight(0x8698c2, 0, 18, 1.2);
    this.olhos.position.set(0, 0.4, 0);
    camera.add(this.olhos);
    cena.add(camera);
    this.paletas = { dia: preparar(PALETAS.dia), crepusculo: preparar(PALETAS.crepusculo), noite: preparar(PALETAS.noite) };
    this.hemi = new THREE.HemisphereLight(0xffffff, 0x000000, 1);
    this.sol = new THREE.DirectionalLight(0xffffff, 1);
    cena.add(this.hemi, this.sol, this.sol.target);
    cena.background = new THREE.Color();
    cena.fog = new THREE.FogExp2(0x000000, 0.02);
  }

  atualizar(estado, fn) {
    const { dia, crepusculo, noite } = this.paletas;
    const [a, b, t] = fn < 0.5 ? [dia, crepusculo, fn * 2] : [crepusculo, noite, (fn - 0.5) * 2];

    this.cena.background.lerpColors(a.ceu, b.ceu, t);
    this.cena.fog.color.copy(this.cena.background);
    this.cena.fog.density = misturar(a.nevoa, b.nevoa, t);
    this.hemi.color.lerpColors(a.hemiCeu, b.hemiCeu, t);
    this.hemi.groundColor.lerpColors(a.hemiChao, b.hemiChao, t);
    this.hemi.intensity = misturar(a.hemi, b.hemi, t);
    this.sol.color.lerpColors(a.sol, b.sol, t);
    this.sol.intensity = misturar(a.solInt, b.solInt, t);
    this.olhos.intensity = OLHOS_INTENSIDADE * fn;

    // Sol cruza o céu durante o dia; à noite a lua fica alta e fria.
    if (estado.fase === 'dia') {
      const ang = (estado.decorrido / estado.duracao) * Math.PI;
      this.sol.position.set(Math.cos(ang) * 80, 15 + Math.sin(ang) * 70, -30);
    } else {
      this.sol.position.set(-40, 70, 50);
    }
  }
}
