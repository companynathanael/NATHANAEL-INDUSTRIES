// Mundo — desenha o mapa (gerado pela mesma semente do servidor) com peças low-poly simples.
// Tudo que se repete (árvores, paredes, pedras, máscaras) usa InstancedMesh: poucas chamadas
// de desenho, leve no celular. Arte final substitui estas peças depois.

import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { criarAleatorio } from '../compartilhado/Aleatorio.js';
import { misturar, suave } from '../compartilhado/Matematica.js';

const PALETA = {
  musgo: [0x27311f, 0x2d3723, 0x222b1b, 0x313b26, 0x2a3320],
  terra: [0x4a4034, 0x524636, 0x43392d, 0x4d4235],
  trilha: 0x3e352a,
  tronco: 0x34281f,
  copa: [0x1c2b21, 0x223326, 0x19261d, 0x27382a],
  seca: [0x4c463e, 0x403b34, 0x59524b],
  muro: [0x6b6860, 0x5f5c55, 0x76736b, 0x66625a],
  madeira: [0x4b3a2c, 0x56432f, 0x45352a],
  rocha: [0x4f504b, 0x5a5a54, 0x47483f],
  ferro: 0x2b2a28,
};

const lambert = (opcoes = {}) => new THREE.MeshLambertMaterial({ flatShading: true, ...opcoes });

/** Ruído barato e determinístico (0..1) para relevo e cores. */
function ruido(x, z) {
  const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453;
  return s - Math.floor(s);
}

export function construirMundo(cena, mapa) {
  const rng = criarAleatorio((mapa.semente ^ 0x9e3779b9) >>> 0); // aleatório só visual
  const grupo = new THREE.Group();
  grupo.name = 'Mundo';
  cena.add(grupo);

  grupo.add(criarChao(mapa, rng));
  grupo.add(criarTrilhas(mapa, rng));
  for (const malha of criarArvores(mapa, rng)) grupo.add(malha);
  grupo.add(criarCaixas(mapa, rng));
  if (mapa.vigas.length) grupo.add(criarVigas(mapa, rng));
  if (mapa.poco) grupo.add(criarPoco(mapa.poco));
  grupo.add(criarPedras(mapa, rng));
  const mascaras = criarMascaras(mapa);
  grupo.add(mascaras.grupo);
  grupo.add(criarTorre(mapa.torre));

  return {
    grupo,
    /** fn = fator noite (0 dia, 1 noite): a porcelana "acende" no escuro. */
    atualizar(fn) {
      mascaras.material.emissiveIntensity = misturar(0.04, 0.55, fn);
    },
  };
}

// ------------------------------------------------------------------ chão

function criarChao(mapa, rng) {
  const R = mapa.raioFloresta + 14;
  const segmentos = 84;
  let g = new THREE.PlaneGeometry(R * 2, R * 2, segmentos, segmentos);
  g.rotateX(-Math.PI / 2);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), z = p.getZ(i);
    const fora = suave(mapa.raioClareira - 6, mapa.raioClareira + 6, Math.hypot(x, z));
    p.setY(i, -fora * (0.05 + 0.35 * ruido(x, z))); // só para baixo: trilhas nunca somem
  }
  g = g.toNonIndexed();
  const pos = g.attributes.position;
  const cores = new Float32Array(pos.count * 3);
  const c = new THREE.Color();
  for (let i = 0; i < pos.count; i += 3) {
    const cx = (pos.getX(i) + pos.getX(i + 1) + pos.getX(i + 2)) / 3;
    const cz = (pos.getZ(i) + pos.getZ(i + 1) + pos.getZ(i + 2)) / 3;
    const r = Math.hypot(cx, cz);
    const borda = mapa.raioClareira - 3 + 2.5 * Math.sin(Math.atan2(cx, cz) * 5 + 1.3);
    let lista = PALETA.musgo;
    if (r < borda - 3) lista = PALETA.terra;
    else if (r < borda + 3) lista = rng.chance(0.5) ? PALETA.terra : PALETA.musgo;
    c.setHex(rng.escolher(lista));
    for (let k = 0; k < 3; k++) c.toArray(cores, (i + k) * 3);
  }
  g.setAttribute('color', new THREE.BufferAttribute(cores, 3));
  g.computeVertexNormals();
  const malha = new THREE.Mesh(g, lambert({ vertexColors: true }));
  malha.name = 'Chao';
  return malha;
}

function criarTrilhas(mapa, rng) {
  const geos = [];
  for (const t of mapa.trilhas) {
    const curva = new THREE.CatmullRomCurve3(t.pontos.map((q) => new THREE.Vector3(q.x, 0, q.z)));
    const pts = curva.getSpacedPoints(Math.ceil(curva.getLength() / 1.5));
    const vertices = [];
    const indices = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
      let tx = b.x - a.x, tz = b.z - a.z;
      const l = Math.hypot(tx, tz) || 1;
      tx /= l; tz /= l;
      const meia = (t.largura / 2) * rng.entre(0.8, 1.15);
      vertices.push(pts[i].x - tz * meia, 0.035, pts[i].z + tx * meia, pts[i].x + tz * meia, 0.035, pts[i].z - tx * meia);
      if (i > 0) {
        const k = (i - 1) * 2;
        indices.push(k, k + 2, k + 1, k + 1, k + 2, k + 3);
      }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    g.setIndex(indices);
    g.computeVertexNormals();
    geos.push(g);
  }
  const malha = new THREE.Mesh(
    mergeGeometries(geos),
    lambert({ color: PALETA.trilha, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
  );
  malha.name = 'Trilhas';
  return malha;
}

// ------------------------------------------------------------------ árvores

function geoPinheiro() {
  // Copa começa alta (≈2,6 m): na altura dos olhos só há troncos, dá para ver entre eles.
  const camadas = [[2.4, 3.6, 4.4], [1.9, 3.2, 6.0], [1.3, 2.8, 7.7]].map(([r, h, y]) => {
    const g = new THREE.ConeGeometry(r, h, 6);
    g.translate(0, y, 0);
    return g;
  });
  return mergeGeometries(camadas);
}

function geoArvoreSeca() {
  const tronco = new THREE.CylinderGeometry(0.12, 0.32, 7, 5);
  tronco.translate(0, 3.5, 0);
  const galho = (comp, raio, y, angY, incl) => {
    const g = new THREE.CylinderGeometry(raio * 0.4, raio, comp, 4);
    g.translate(0, comp / 2, 0);
    g.rotateZ(-incl);
    g.rotateY(angY);
    g.translate(0, y, 0);
    return g;
  };
  return mergeGeometries([
    tronco,
    galho(2.4, 0.09, 3.4, 0.3, 1.0),
    galho(2.0, 0.08, 4.5, 2.4, 0.9),
    galho(1.8, 0.07, 5.4, 4.3, 0.8),
    galho(1.4, 0.06, 6.1, 1.2, 0.6),
  ]);
}

/** Divide a floresta em setores (fatias × anéis): cada setor é um InstancedMesh próprio,
 *  e o Three.js deixa de desenhar os setores fora da câmera (bem mais leve no celular). */
function setorDe(a) {
  const FATIAS = 10;
  const fatia = Math.floor(((Math.atan2(a.x, a.z) + Math.PI) / (Math.PI * 2)) * FATIAS) % FATIAS;
  const anel = Math.hypot(a.x, a.z) < 75 ? 0 : 1;
  return fatia * 2 + anel;
}

function criarArvores(mapa, rng) {
  const geoTronco = new THREE.CylinderGeometry(0.22, 0.4, 5, 5);
  geoTronco.translate(0, 2.5, 0);
  const geoCopa = geoPinheiro();
  const geoSeca = geoArvoreSeca();
  const matTronco = lambert(), matCopa = lambert(), matSeca = lambert();
  const d = new THREE.Object3D();
  const c = new THREE.Color();

  const setores = new Map();
  for (const a of mapa.arvores) {
    const s = setorDe(a);
    if (!setores.has(s)) setores.set(s, { pinheiros: [], secas: [] });
    setores.get(s)[a.tipo === 'pinheiro' ? 'pinheiros' : 'secas'].push(a);
  }

  const posicionar = (a) => {
    d.position.set(a.x, 0, a.z);
    d.rotation.set(0, a.rot, 0);
    d.scale.setScalar(a.escala);
    d.updateMatrix();
    return d.matrix;
  };

  const malhas = [];
  for (const { pinheiros, secas } of setores.values()) {
    if (pinheiros.length) {
      const troncos = new THREE.InstancedMesh(geoTronco, matTronco, pinheiros.length);
      const copas = new THREE.InstancedMesh(geoCopa, matCopa, pinheiros.length);
      pinheiros.forEach((a, i) => {
        const m = posicionar(a);
        troncos.setMatrixAt(i, m);
        copas.setMatrixAt(i, m);
        troncos.setColorAt(i, c.setHex(PALETA.tronco).offsetHSL(0, 0, rng.entre(-0.02, 0.03)));
        copas.setColorAt(i, c.setHex(rng.escolher(PALETA.copa)));
      });
      malhas.push(troncos, copas);
    }
    if (secas.length) {
      const mortas = new THREE.InstancedMesh(geoSeca, matSeca, secas.length);
      secas.forEach((a, i) => {
        mortas.setMatrixAt(i, posicionar(a));
        mortas.setColorAt(i, c.setHex(rng.escolher(PALETA.seca)));
      });
      malhas.push(mortas);
    }
  }
  for (const m of malhas) m.computeBoundingSphere();
  return malhas;
}

// ------------------------------------------------------------------ vila

function criarCaixas(mapa, rng) {
  const geo = new THREE.BoxGeometry(1, 1, 1);
  geo.translate(0, 0.5, 0);
  const malha = new THREE.InstancedMesh(geo, lambert(), mapa.caixas.length);
  const d = new THREE.Object3D();
  const c = new THREE.Color();
  mapa.caixas.forEach((cx, i) => {
    d.position.set(cx.x, 0, cx.z);
    d.rotation.set(0, cx.rot, 0);
    d.scale.set(cx.hx * 2, cx.altura, cx.hz * 2);
    d.updateMatrix();
    malha.setMatrixAt(i, d.matrix);
    malha.setColorAt(i, c.setHex(rng.escolher(cx.tipo === 'parede' ? PALETA.muro : PALETA.madeira)));
  });
  malha.computeBoundingSphere();
  malha.name = 'Ruinas';
  return malha;
}

function criarVigas(mapa, rng) {
  const malha = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 0.24, 0.24), lambert(), mapa.vigas.length);
  const d = new THREE.Object3D();
  d.rotation.order = 'YZX'; // inclina primeiro, depois gira
  const c = new THREE.Color();
  mapa.vigas.forEach((v, i) => {
    d.position.set(v.x, v.y, v.z);
    d.rotation.set(0, v.rotY, v.incl);
    d.scale.set(v.comp, 1, 1);
    d.updateMatrix();
    malha.setMatrixAt(i, d.matrix);
    malha.setColorAt(i, c.setHex(rng.escolher(PALETA.madeira)));
  });
  malha.computeBoundingSphere();
  return malha;
}

function criarPoco(poco) {
  const g = new THREE.Group();
  g.position.set(poco.x, 0, poco.z);
  g.rotation.y = poco.rot;
  const pedra = lambert({ color: 0x625f58, side: THREE.DoubleSide });
  const madeira = lambert({ color: 0x47372a });
  const anel = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.2, 0.9, 9, 1, true), pedra);
  anel.position.y = 0.45;
  const fundo = new THREE.Mesh(new THREE.CircleGeometry(1.08, 9), new THREE.MeshBasicMaterial({ color: 0x030303 }));
  fundo.rotation.x = -Math.PI / 2;
  fundo.position.y = 0.3;
  g.add(anel, fundo);
  for (const lado of [-1, 1]) {
    const poste = new THREE.Mesh(new THREE.BoxGeometry(0.14, 2.1, 0.14), madeira);
    poste.position.set(lado * 0.98, 1.05, 0);
    g.add(poste);
  }
  const travessa = new THREE.Mesh(new THREE.BoxGeometry(2.1, 0.14, 0.14), madeira);
  travessa.position.y = 2.0;
  const balde = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.13, 0.28, 6), lambert({ color: 0x3a3632 }));
  balde.position.y = 1.25;
  g.add(travessa, balde);
  return g;
}

function criarPedras(mapa, rng) {
  const malha = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(1, 0), lambert(), mapa.pedras.length);
  const d = new THREE.Object3D();
  const c = new THREE.Color();
  mapa.pedras.forEach((p, i) => {
    d.position.set(p.x, -0.15 * p.r, p.z);
    d.rotation.set(rng.entre(0, 0.4), p.rot, rng.entre(0, 0.4));
    d.scale.set(p.r, p.r * p.altura, p.r * rng.entre(0.8, 1.2));
    d.updateMatrix();
    malha.setMatrixAt(i, d.matrix);
    malha.setColorAt(i, c.setHex(rng.escolher(PALETA.rocha)));
  });
  malha.computeBoundingSphere();
  return malha;
}

// ------------------------------------------------------------------ máscaras de porcelana

function texturaMascara() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const g = canvas.getContext('2d');
  g.fillStyle = '#efe9dc';
  g.fillRect(0, 0, 128, 128);
  // sombra suave nas bordas (porcelana curva)
  const grad = g.createRadialGradient(64, 60, 20, 64, 64, 80);
  grad.addColorStop(0, 'rgba(0,0,0,0)');
  grad.addColorStop(1, 'rgba(60,50,40,0.35)');
  g.fillStyle = grad;
  g.fillRect(0, 0, 128, 128);
  // olhos amendoados, vazados
  g.fillStyle = '#070707';
  for (const lado of [-1, 1]) {
    g.beginPath();
    g.ellipse(64 + lado * 23, 58, 12, 6.5, lado * 0.22, 0, Math.PI * 2);
    g.fill();
  }
  // boca: um traço fino e reto (sem expressão)
  g.strokeStyle = '#2a2826';
  g.lineWidth = 2.5;
  g.beginPath();
  g.moveTo(52, 94);
  g.lineTo(76, 94);
  g.stroke();
  // rachadura
  g.strokeStyle = '#8c8477';
  g.lineWidth = 1.4;
  g.beginPath();
  g.moveTo(82, 8);
  g.lineTo(75, 28);
  g.lineTo(83, 41);
  g.lineTo(79, 50);
  g.stroke();
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function criarMascaras(mapa) {
  const grupo = new THREE.Group();
  grupo.name = 'Mascaras';
  const lista = mapa.mascarasDecorativas;
  const textura = texturaMascara();
  const geo = new THREE.SphereGeometry(0.2, 12, 10, 0, Math.PI); // meia esfera virada para +z
  geo.scale(1, 1.3, 0.5);
  const material = new THREE.MeshLambertMaterial({
    map: textura,
    emissive: 0xd8d1c3,
    emissiveMap: textura,
    emissiveIntensity: 0.05,
    side: THREE.DoubleSide,
  });
  const malha = new THREE.InstancedMesh(geo, material, lista.length);
  const d = new THREE.Object3D();
  d.rotation.order = 'YZX';
  const fios = [];
  lista.forEach((m, i) => {
    d.position.set(m.x, m.y, m.z);
    d.rotation.set(0, m.rot, m.incl);
    d.updateMatrix();
    malha.setMatrixAt(i, d.matrix);
    fios.push(m.x, m.y + 0.25, m.z, m.x, m.y + 0.85, m.z);
  });
  malha.computeBoundingSphere();
  const geoFios = new THREE.BufferGeometry();
  geoFios.setAttribute('position', new THREE.Float32BufferAttribute(fios, 3));
  grupo.add(malha, new THREE.LineSegments(geoFios, new THREE.LineBasicMaterial({ color: 0x1a1816 })));
  return { grupo, material };
}

// ------------------------------------------------------------------ torre de rádio

function barra(a, b, espessura) {
  const dir = new THREE.Vector3().subVectors(b, a);
  const comp = dir.length();
  const g = new THREE.BoxGeometry(espessura, comp, espessura);
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  g.applyMatrix4(new THREE.Matrix4().compose(new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5), q, new THREE.Vector3(1, 1, 1)));
  return g;
}

function criarTorre(t) {
  const V = (x, y, z) => new THREE.Vector3(x, y, z);
  const cantos = (m, y) => [V(-m, y, -m), V(m, y, -m), V(m, y, m), V(-m, y, m)];
  const geos = [];
  const H = t.altura, topo = 0.45, niveis = 6;
  const base = cantos(t.base, 0), alto = cantos(topo, H);
  for (let i = 0; i < 4; i++) geos.push(barra(base[i], alto[i], 0.22));
  for (let n = 1; n <= niveis; n++) {
    const a = cantos(misturar(t.base, topo, (n - 1) / niveis), (H * (n - 1)) / niveis);
    const b = cantos(misturar(t.base, topo, n / niveis), (H * n) / niveis);
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      if (!(n === 4 && i === 2)) geos.push(barra(b[i], b[j], 0.1)); // uma travessa faltando
      geos.push(barra(a[i], b[j], 0.07));
    }
  }
  geos.push(barra(V(0, H, 0), V(0, H + 5, 0), 0.12));             // antena
  geos.push(barra(V(topo, H - 2, 0), V(topo + 2.6, H - 5.5, 0.8), 0.1)); // braço torto
  const torre = new THREE.Mesh(mergeGeometries(geos), lambert({ color: PALETA.ferro }));
  torre.position.set(t.x, 0, t.z);
  torre.rotation.y = t.rot;
  const luz = new THREE.Mesh(new THREE.SphereGeometry(0.25, 6, 4), new THREE.MeshBasicMaterial({ color: 0x3b0f0c }));
  luz.position.y = H + 5.2;
  torre.add(luz);
  torre.name = 'TorreDeRadio';
  return torre;
}
