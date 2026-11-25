// ChamaVisual — a lanterna da Chama-Mãe, a luz que ela joga e o anel do raio seguro.
// Só desenha: quem decide óleo e raio é o servidor. O anel no chão mostra exatamente
// até onde a luz protege (a morte nunca pode parecer injusta).

import * as THREE from 'three';
import { misturar } from '../compartilhado/Matematica.js';

const lambert = (opcoes) => new THREE.MeshLambertMaterial({ flatShading: true, ...opcoes });

function texturaRadial(interna, externa) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const g = canvas.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, interna);
  grad.addColorStop(1, externa);
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const ADITIVO = { transparent: true, blending: THREE.AdditiveBlending, depthWrite: false };
const INTENSIDADE_BASE = 60; // candelas (luz física do Three.js)
const ALTURA_FOGO = 3.35;

export class ChamaVisual {
  constructor(cena, posicao) {
    this.grupo = new THREE.Group();
    this.grupo.name = 'ChamaMae';
    this.grupo.position.set(posicao.x, 0, posicao.z);
    cena.add(this.grupo);

    const pedra = lambert({ color: 0x5f5c55 });
    const ferro = lambert({ color: 0x242325 });
    const add = (geo, mat, x, y, z) => {
      const m = new THREE.Mesh(geo, mat);
      m.position.set(x, y, z);
      this.grupo.add(m);
      return m;
    };

    // Pedestal de pedra em dois degraus + poste de ferro + lanterna de quatro vidros.
    add(new THREE.CylinderGeometry(1.0, 1.2, 0.8, 7), pedra, 0, 0.4, 0);
    add(new THREE.CylinderGeometry(0.55, 0.75, 0.5, 7), pedra, 0, 1.05, 0);
    add(new THREE.BoxGeometry(0.16, 1.7, 0.16), ferro, 0, 2.1, 0);
    add(new THREE.BoxGeometry(0.66, 0.08, 0.66), ferro, 0, 2.95, 0);
    for (const [x, z] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
      add(new THREE.BoxGeometry(0.05, 0.8, 0.05), ferro, x * 0.28, ALTURA_FOGO, z * 0.28);
    }
    add(new THREE.ConeGeometry(0.52, 0.45, 4), ferro, 0, 3.98, 0).rotation.y = Math.PI / 4;
    add(new THREE.TorusGeometry(0.1, 0.025, 4, 10), ferro, 0, 4.28, 0);
    this.vidro = add(
      new THREE.BoxGeometry(0.5, 0.76, 0.5),
      new THREE.MeshBasicMaterial({ color: 0xffb566, transparent: true, opacity: 0.22, depthWrite: false }),
      0, ALTURA_FOGO, 0,
    );

    // Fogo: dois cones (externo laranja, núcleo claro).
    this.fogo = new THREE.Group();
    this.fogo.position.set(0, 3.06, 0);
    this.grupo.add(this.fogo);
    const externo = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.42, 6), new THREE.MeshBasicMaterial({ color: 0xffa040 }));
    externo.position.y = 0.21;
    const nucleo = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.24, 5), new THREE.MeshBasicMaterial({ color: 0xfff1c9 }));
    nucleo.position.y = 0.13;
    this.fogo.add(externo, nucleo);

    // Halo em volta da lanterna (brilho sem pós-processamento: leve no celular).
    this.halo = new THREE.Sprite(new THREE.SpriteMaterial({
      map: texturaRadial('rgba(255,196,120,1)', 'rgba(255,140,60,0)'), ...ADITIVO, opacity: 0.8,
    }));
    this.halo.position.y = ALTURA_FOGO;
    this.grupo.add(this.halo);

    this.luz = new THREE.PointLight(0xffa24f, INTENSIDADE_BASE, 40, 1.0);
    this.luz.position.y = ALTURA_FOGO;
    this.grupo.add(this.luz);

    // Poça de luz no chão e o anel que marca o limite seguro.
    const geoBrilho = new THREE.PlaneGeometry(2, 2);
    geoBrilho.rotateX(-Math.PI / 2);
    this.brilho = new THREE.Mesh(geoBrilho, new THREE.MeshBasicMaterial({
      map: texturaRadial('rgba(255,160,80,0.9)', 'rgba(255,120,40,0)'), ...ADITIVO, opacity: 0.3,
    }));
    this.brilho.position.y = 0.06;
    const geoAnel = new THREE.RingGeometry(0.986, 1, 160);
    geoAnel.rotateX(-Math.PI / 2);
    this.anel = new THREE.Mesh(geoAnel, new THREE.MeshBasicMaterial({ color: 0xffb25a, ...ADITIVO, opacity: 0.3, side: THREE.DoubleSide }));
    this.anel.position.y = 0.09;
    this.grupo.add(this.brilho, this.anel);

    // Brasas subindo.
    const N = 28;
    this.brasasDados = Array.from({ length: N }, () => this.#novaBrasa(Math.random() * 2.6));
    this.geoBrasas = new THREE.BufferGeometry();
    this.geoBrasas.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    this.brasas = new THREE.Points(this.geoBrasas, new THREE.PointsMaterial({
      color: 0xffb35a, size: 0.09, map: texturaRadial('rgba(255,220,160,1)', 'rgba(255,140,60,0)'), ...ADITIVO, opacity: 0.9,
    }));
    this.brasas.position.y = ALTURA_FOGO + 0.6;
    this.brasas.frustumCulled = false;
    this.grupo.add(this.brasas);

    this.raioVisual = 0;
  }

  #novaBrasa(y = 0) {
    return { x: (Math.random() - 0.5) * 0.3, z: (Math.random() - 0.5) * 0.3, y, vel: 0.35 + Math.random() * 0.6, fase: Math.random() * 6 };
  }

  /** chama = { oleo, oleoMax, raio, acesa } vindo do servidor; fn = fator noite (0..1). */
  atualizar(dt, t, chama, fn) {
    const fr = chama.oleoMax ? chama.oleo / chama.oleoMax : 0;
    const baixo = chama.acesa && fr < 0.2;
    let tremor = 1 + 0.08 * Math.sin(t * 11.3) + 0.05 * Math.sin(t * 17.9 + 1.7) + 0.04 * Math.sin(t * 29.1 + 0.4);
    if (baixo && Math.sin(t * 0.9) > 0.55) tremor *= 0.55 + 0.45 * Math.abs(Math.sin(t * 7.3)); // engasga sem óleo

    // O raio no chão anda suave até o valor do servidor (sem "pulos" a cada pacote).
    this.raioVisual += (chama.raio - this.raioVisual) * Math.min(1, dt * 3);
    const visivel = chama.acesa || this.raioVisual > 0.3;

    this.fogo.visible = chama.acesa;
    this.fogo.scale.setScalar((0.55 + 0.45 * fr) * tremor);
    this.luz.visible = visivel;
    this.luz.intensity = chama.acesa ? INTENSIDADE_BASE * (0.4 + 0.6 * fr) * tremor * misturar(0.2, 1, fn) : 0;
    this.luz.distance = Math.max(4, this.raioVisual * 1.75);
    this.halo.visible = chama.acesa;
    this.halo.scale.setScalar(2.4 * (0.6 + 0.4 * fr) * tremor);
    this.halo.material.opacity = misturar(0.35, 0.85, fn);
    this.vidro.material.opacity = chama.acesa ? 0.22 : 0.08;

    this.anel.visible = this.raioVisual > 0.5;
    this.anel.scale.setScalar(Math.max(0.01, this.raioVisual));
    const pulso = baixo ? 0.55 + 0.45 * Math.sin(t * 6) : 1;
    this.anel.material.opacity = misturar(0.1, 0.55, fn) * pulso;
    this.brilho.visible = this.anel.visible;
    this.brilho.scale.setScalar(Math.max(0.01, this.raioVisual * 1.2));
    this.brilho.material.opacity = misturar(0.05, 0.4, fn) * (0.5 + 0.5 * fr) * tremor;

    this.brasas.visible = chama.acesa;
    if (chama.acesa) {
      const p = this.geoBrasas.attributes.position;
      this.brasasDados.forEach((b, i) => {
        b.y += b.vel * dt;
        b.x += Math.sin(t * 2 + b.fase) * 0.15 * dt;
        if (b.y > 2.6) Object.assign(b, this.#novaBrasa());
        p.setXYZ(i, b.x, b.y, b.z);
      });
      p.needsUpdate = true;
      this.brasas.material.opacity = 0.9 * (1 - fn * 0.1);
    }
  }
}
