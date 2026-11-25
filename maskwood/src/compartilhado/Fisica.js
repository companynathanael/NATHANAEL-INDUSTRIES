// Física simples no plano XZ: o jogador é um círculo; árvores e pedras são círculos;
// paredes e caixotes são caixas giradas. O cliente usa para andar sem atravessar nada
// e o servidor usa para validar a posição recebida (anti-atravessar-parede).

import { limitar } from './Matematica.js';

const chave = (i, j) => i * 100003 + j;
let marcaGlobal = 0;
const temporario = [];

/** Grade espacial: cada célula guarda os colisores que encostam nela (busca rápida). */
export function construirGrade(colisores, tamanho) {
  const celulas = new Map();
  for (const c of colisores) {
    const raio = c.tipo === 'circulo' ? c.r : Math.hypot(c.hx, c.hz);
    const i0 = Math.floor((c.x - raio) / tamanho), i1 = Math.floor((c.x + raio) / tamanho);
    const j0 = Math.floor((c.z - raio) / tamanho), j1 = Math.floor((c.z + raio) / tamanho);
    for (let i = i0; i <= i1; i++) {
      for (let j = j0; j <= j1; j++) {
        const k = chave(i, j);
        let lista = celulas.get(k);
        if (!lista) celulas.set(k, (lista = []));
        lista.push(c);
      }
    }
  }
  return { tamanho, celulas };
}

/** Colisores perto de (x, z), sem repetidos. */
export function colisoresPerto(mapa, x, z, raio, saida = []) {
  saida.length = 0;
  const { tamanho, celulas } = mapa.grade;
  const marca = ++marcaGlobal;
  const i0 = Math.floor((x - raio) / tamanho), i1 = Math.floor((x + raio) / tamanho);
  const j0 = Math.floor((z - raio) / tamanho), j1 = Math.floor((z + raio) / tamanho);
  for (let i = i0; i <= i1; i++) {
    for (let j = j0; j <= j1; j++) {
      const lista = celulas.get(chave(i, j));
      if (!lista) continue;
      for (const c of lista) {
        if (c._marca === marca) continue;
        c._marca = marca;
        saida.push(c);
      }
    }
  }
  return saida;
}

/** Quanto empurrar um círculo (x, z, raio) para fora do colisor `c`; null se não encosta. */
export function empurrao(c, x, z, raio) {
  if (c.tipo === 'circulo') {
    const dx = x - c.x, dz = z - c.z;
    const d2 = dx * dx + dz * dz;
    const minimo = raio + c.r;
    if (d2 >= minimo * minimo) return null;
    if (d2 < 1e-12) return { x: minimo, z: 0 };
    const d = Math.sqrt(d2);
    return { x: (dx / d) * (minimo - d), z: (dz / d) * (minimo - d) };
  }
  // Caixa girada: leva o ponto para o espaço da caixa, resolve e volta para o mundo.
  const cs = Math.cos(c.rot), sn = Math.sin(c.rot);
  const dx = x - c.x, dz = z - c.z;
  const lx = dx * cs - dz * sn;
  const lz = dx * sn + dz * cs;
  const px = limitar(lx, -c.hx, c.hx), pz = limitar(lz, -c.hz, c.hz);
  const ex = lx - px, ez = lz - pz;
  const d2 = ex * ex + ez * ez;
  let nx, nz, p;
  if (d2 > 1e-12) {
    if (d2 >= raio * raio) return null;
    const d = Math.sqrt(d2);
    nx = ex / d; nz = ez / d; p = raio - d;
  } else {
    // O centro está dentro da caixa: sai pelo lado mais próximo.
    const sobraX = c.hx - Math.abs(lx), sobraZ = c.hz - Math.abs(lz);
    if (sobraX < sobraZ) { nx = Math.sign(lx) || 1; nz = 0; p = sobraX + raio; }
    else { nx = 0; nz = Math.sign(lz) || 1; p = sobraZ + raio; }
  }
  return { x: (nx * cs + nz * sn) * p, z: (-nx * sn + nz * cs) * p };
}

export function resolverColisoes(mapa, x, z, raio) {
  for (let iteracao = 0; iteracao < 3; iteracao++) {
    let moveu = false;
    for (const c of colisoresPerto(mapa, x, z, raio + 0.1, temporario)) {
      const e = empurrao(c, x, z, raio);
      if (e) { x += e.x; z += e.z; moveu = true; }
    }
    if (!moveu) break;
  }
  return { x, z };
}

/** Move um círculo em passos pequenos (não atravessa troncos finos) e respeita o limite do mundo. */
export function moverCirculo(mapa, x, z, dx, dz, raio) {
  const passos = Math.max(1, Math.ceil(Math.hypot(dx, dz) / (raio * 0.5)));
  for (let i = 0; i < passos; i++) {
    ({ x, z } = resolverColisoes(mapa, x + dx / passos, z + dz / passos, raio));
  }
  const limite = mapa.raioMundo - 1;
  const r = Math.hypot(x, z);
  if (r > limite) { x *= limite / r; z *= limite / r; }
  return { x, z };
}

export function sobrepoeColisor(mapa, x, z, raio) {
  for (const c of colisoresPerto(mapa, x, z, raio + 0.1, temporario)) {
    if (empurrao(c, x, z, raio)) return true;
  }
  return false;
}
