// Mapa — gera a clareira de Pedra Alta e a floresta em volta a partir de uma SEMENTE.
// Servidor e cliente rodam esta mesma função: o servidor usa os colisores (física e, na etapa 3,
// o caminho dos Sem-Rosto) e o cliente usa os mesmos dados para desenhar as peças 3D.
// Unidades em metros, chão no plano XZ, Chama-Mãe em (0, 0).

import { Config } from './Config.js';
import { criarAleatorio } from './Aleatorio.js';
import { distanciaPontoSegmento } from './Matematica.js';
import { construirGrade, sobrepoeColisor } from './Fisica.js';

const TAU = Math.PI * 2;

/** Ponto local (lx, lz) de uma peça girada em `rot` → mundo (mesma convenção do rotation.y do Three.js). */
export function localParaMundo(cx, cz, rot, lx, lz) {
  const c = Math.cos(rot), s = Math.sin(rot);
  return { x: cx + lx * c + lz * s, z: cz - lx * s + lz * c };
}

export function distanciaTrilhas(trilhas, x, z) {
  let menor = Infinity;
  for (const t of trilhas) {
    for (let k = 1; k < t.pontos.length; k++) {
      const a = t.pontos[k - 1], b = t.pontos[k];
      menor = Math.min(menor, distanciaPontoSegmento(x, z, a.x, a.z, b.x, b.z));
    }
  }
  return menor;
}

/** Marca, numa grade de 1 m, tudo o que fica a até `margem` de alguma trilha (consulta O(1)). */
function marcarFaixaTrilhas(trilhas, margem) {
  const marcadas = new Set();
  const k = (i, j) => i * 100003 + j;
  for (const t of trilhas) {
    for (let n = 1; n < t.pontos.length; n++) {
      const a = t.pontos[n - 1], b = t.pontos[n];
      const x0 = Math.floor(Math.min(a.x, b.x) - margem), x1 = Math.ceil(Math.max(a.x, b.x) + margem);
      const z0 = Math.floor(Math.min(a.z, b.z) - margem), z1 = Math.ceil(Math.max(a.z, b.z) + margem);
      for (let i = x0; i <= x1; i++) {
        for (let j = z0; j <= z1; j++) {
          if (distanciaPontoSegmento(i + 0.5, j + 0.5, a.x, a.z, b.x, b.z) <= margem + 0.71) marcadas.add(k(i, j));
        }
      }
    }
  }
  return (x, z) => marcadas.has(k(Math.floor(x), Math.floor(z)));
}

export function gerarMapa(cfg = Config.mapa) {
  const rng = criarAleatorio(cfg.SEMENTE);
  const mapa = {
    semente: cfg.SEMENTE,
    raioMundo: cfg.RAIO_MUNDO,
    raioClareira: cfg.RAIO_CLAREIRA,
    raioFloresta: cfg.RAIO_FLORESTA_FIM,
    chama: { x: 0, z: 0, raioPedestal: 1.1 },
    trilhas: [],
    casas: [],
    caixas: [],              // paredes e caixotes (visual + colisão)
    vigas: [],               // vigas caídas (só visual)
    pedras: [],
    arvores: [],
    mascarasDecorativas: [], // penduradas nas árvores (só clima; as 5 coletáveis vêm na etapa 5)
    poco: null,
    torre: null,
    nascimentos: [],
    colisores: [],
    grade: null,
  };
  const C = mapa.colisores;
  const circulo = (x, z, r, origem) => C.push({ tipo: 'circulo', x, z, r, origem });
  const caixaColisor = (x, z, hx, hz, rot, origem) => C.push({ tipo: 'caixa', x, z, hx, hz, rot, origem });

  // ---- Chama-Mãe: pedestal de pedra no centro da vila
  circulo(0, 0, mapa.chama.raioPedestal, 'chama');

  // ---- 1) Trilhas: saem da vila e entram na floresta, fazendo curvas
  const angInicial = rng.entre(0, TAU);
  for (let i = 0; i < cfg.NUM_TRILHAS; i++) {
    let ang = angInicial + (i * TAU) / cfg.NUM_TRILHAS + rng.entre(-0.2, 0.2);
    const pontos = [];
    for (let r = 4; r <= cfg.RAIO_FLORESTA_FIM + 4; r += 6) {
      pontos.push({ x: Math.sin(ang) * r, z: Math.cos(ang) * r });
      if (r > cfg.RAIO_CLAREIRA - 6) ang += rng.entre(-0.07, 0.07);
    }
    mapa.trilhas.push({ pontos, largura: cfg.LARGURA_TRILHA });
  }
  const pertoDeTrilha = marcarFaixaTrilhas(mapa.trilhas, cfg.LARGURA_TRILHA / 2 + 1.2);
  const distTrilha = (x, z) => distanciaTrilhas(mapa.trilhas, x, z);

  // ---- 2) Torre de rádio quebrada no fim da primeira trilha (objetivo final do jogo)
  {
    const p = mapa.trilhas[0].pontos;
    let idx = p.findIndex((q) => Math.hypot(q.x, q.z) >= cfg.DIST_TORRE);
    if (idx < 1) idx = p.length - 2;
    const a = p[idx - 1], b = p[idx];
    const comp = Math.hypot(b.x - a.x, b.z - a.z) || 1;
    const dx = (b.x - a.x) / comp, dz = (b.z - a.z) / comp;
    const torre = { x: b.x - dz * 7, z: b.z + dx * 7, rot: Math.atan2(dx, dz), altura: 30, base: 2.6 };
    mapa.torre = torre;
    for (const sx of [-1, 1]) {
      for (const sz of [-1, 1]) {
        const perna = localParaMundo(torre.x, torre.z, torre.rot, sx * torre.base, sz * torre.base);
        circulo(perna.x, perna.z, 0.4, 'torre');
      }
    }
  }

  // ---- 3) Vila de Pedra Alta: casas sem teto, paredes quebradas, porta virada para a Chama
  const adicionarCaixa = (cx, cz, rot, lx, lz, hx, hz, altura, tipo) => {
    const p = localParaMundo(cx, cz, rot, lx, lz);
    mapa.caixas.push({ tipo, x: p.x, z: p.z, hx, hz, rot, altura });
    caixaColisor(p.x, p.z, hx, hz, rot, tipo);
  };

  for (let k = 0; k < cfg.NUM_CASAS; k++) {
    for (let tentativa = 0; tentativa < 40; tentativa++) {
      const ang = (k * TAU) / cfg.NUM_CASAS + rng.entre(-0.35, 0.35) + tentativa * 0.07;
      const r = rng.entre(cfg.RAIO_VILA_MIN, cfg.RAIO_VILA_MAX);
      const x = Math.sin(ang) * r, z = Math.cos(ang) * r;
      const larg = rng.entre(5, 7), prof = rng.entre(4, 5.5);
      const raio = Math.hypot(larg, prof) / 2;
      if (distTrilha(x, z) < raio + 1.5) continue;
      if (mapa.casas.some((c) => Math.hypot(c.x - x, c.z - z) < c.raio + raio + 2.5)) continue;
      // rot = ang + π: o "+z" local da casa aponta para a Chama (é a frente, com a porta).
      const casa = { x, z, rot: ang + Math.PI, larg, prof, raio };
      mapa.casas.push(casa);

      const esp = 0.35;
      const lados = [
        { cx: 0, cz: prof / 2, comp: larg, eixo: 'x', porta: true },
        { cx: 0, cz: -prof / 2, comp: larg, eixo: 'x' },
        { cx: -larg / 2, cz: 0, comp: prof, eixo: 'z' },
        { cx: larg / 2, cz: 0, comp: prof, eixo: 'z' },
      ];
      for (const lado of lados) {
        const nSeg = Math.max(2, Math.round(lado.comp / 1.6));
        const tam = lado.comp / nSeg;
        for (let s = 0; s < nSeg; s++) {
          const centro = -lado.comp / 2 + tam * (s + 0.5);
          if (lado.porta && Math.abs(centro) < 0.9) continue; // vão da porta
          if (rng.chance(0.18)) continue;                      // pedaço de parede caído
          const canto = s === 0 || s === nSeg - 1;
          const altura = canto ? rng.entre(1.8, 3.0) : rng.entre(0.5, 2.4);
          const lx = lado.eixo === 'x' ? lado.cx + centro : lado.cx;
          const lz = lado.eixo === 'x' ? lado.cz : lado.cz + centro;
          const hx = lado.eixo === 'x' ? tam / 2 : esp / 2;
          const hz = lado.eixo === 'x' ? esp / 2 : tam / 2;
          adicionarCaixa(x, z, casa.rot, lx, lz, hx, hz, altura, 'parede');
        }
      }
      // Vigas do telhado caídas lá dentro (só visual).
      const nVigas = rng.inteiro(1, 2);
      for (let v = 0; v < nVigas; v++) {
        const p = localParaMundo(x, z, casa.rot, rng.entre(-larg / 5, larg / 5), rng.entre(-prof / 5, prof / 5));
        const incl = rng.entre(0.12, 0.42), comp = larg * 0.85;
        mapa.vigas.push({ x: p.x, z: p.z, y: 0.12 + (Math.sin(incl) * comp) / 2, comp, rotY: casa.rot + rng.entre(-0.6, 0.6), incl });
      }
      break;
    }
  }
  const pertoDeCasa = (x, z, folga) => mapa.casas.some((c) => Math.hypot(c.x - x, c.z - z) < c.raio + folga);

  // ---- 4) Poço da vila
  for (let tentativa = 0; tentativa < 60; tentativa++) {
    const ang = rng.entre(0, TAU), r = 8.5;
    const x = Math.sin(ang) * r, z = Math.cos(ang) * r;
    if (distTrilha(x, z) < 3.5 || pertoDeCasa(x, z, 2)) continue;
    mapa.poco = { x, z, rot: rng.entre(0, TAU) };
    circulo(x, z, 1.2, 'poco');
    break;
  }

  // ---- 5) Árvore seca da vila, com máscaras penduradas (a primeira coisa estranha que se vê)
  let arvoreVila = null;
  for (let tentativa = 0; tentativa < 80; tentativa++) {
    const ang = rng.entre(0, TAU), r = rng.entre(9, 11);
    const x = Math.sin(ang) * r, z = Math.cos(ang) * r;
    if (distTrilha(x, z) < 3 || pertoDeCasa(x, z, 2.5)) continue;
    if (mapa.poco && Math.hypot(mapa.poco.x - x, mapa.poco.z - z) < 5) continue;
    arvoreVila = { x, z, escala: 1.3, tipo: 'seca', rot: rng.entre(0, TAU), rTronco: 0.42, naVila: true };
    mapa.arvores.push(arvoreVila);
    circulo(x, z, arvoreVila.rTronco, 'arvore');
    break;
  }

  // ---- 6) Caixotes largados pela vila
  for (let n = 0, tentativa = 0; n < cfg.NUM_CAIXOTES && tentativa < 200; tentativa++) {
    const ang = rng.entre(0, TAU), r = rng.entre(6.5, 20);
    const x = Math.sin(ang) * r, z = Math.cos(ang) * r;
    if (distTrilha(x, z) < 2.4 || pertoDeCasa(x, z, 0.8)) continue;
    if (mapa.poco && Math.hypot(mapa.poco.x - x, mapa.poco.z - z) < 2.6) continue;
    if (arvoreVila && Math.hypot(arvoreVila.x - x, arvoreVila.z - z) < 2.2) continue;
    if (mapa.caixas.some((c) => c.tipo === 'caixote' && Math.hypot(c.x - x, c.z - z) < 1.4)) continue;
    const meio = rng.entre(0.32, 0.48);
    mapa.caixas.push({ tipo: 'caixote', x, z, hx: meio, hz: meio, rot: rng.entre(0, TAU), altura: meio * 2 });
    caixaColisor(x, z, meio, meio, mapa.caixas.at(-1).rot, 'caixote');
    n++;
  }

  // ---- 7) Floresta densa: amostragem com distância mínima entre as árvores
  {
    const R0 = cfg.RAIO_CLAREIRA, R1 = cfg.RAIO_FLORESTA_FIM;
    const celula = cfg.DIST_MIN_ARVORES * 1.5;
    const grade = new Map();
    const k = (i, j) => i * 100003 + j;
    const temVizinha = (x, z, dmin) => {
      const ci = Math.floor(x / celula), cj = Math.floor(z / celula);
      for (let i = ci - 1; i <= ci + 1; i++) {
        for (let j = cj - 1; j <= cj + 1; j++) {
          for (const a of grade.get(k(i, j)) ?? []) if (Math.hypot(a.x - x, a.z - z) < dmin) return true;
        }
      }
      return false;
    };
    const t = mapa.torre;
    let tentativas = 0, plantadas = 0;
    while (plantadas < cfg.NUM_ARVORES && tentativas++ < cfg.NUM_ARVORES * 30) {
      const r = Math.sqrt(rng.entre(R0 * R0 * 0.8, R1 * R1));
      const a = rng.entre(0, TAU);
      const borda = R0 + 3 * Math.sin(a * 5 + 1.3) + 2 * Math.sin(a * 11); // borda irregular da clareira
      if (r < borda) continue;
      const x = Math.sin(a) * r, z = Math.cos(a) * r;
      if (pertoDeTrilha(x, z)) continue;
      if (Math.hypot(x - t.x, z - t.z) < 9) continue;
      if (pertoDeCasa(x, z, 1.5)) continue;
      const dmin = r < R0 + 8 ? cfg.DIST_MIN_ARVORES * 1.5 : cfg.DIST_MIN_ARVORES; // borda mais rala
      if (temVizinha(x, z, dmin)) continue;
      const escala = rng.entre(0.75, 1.35);
      const tipo = rng.chance(0.22) ? 'seca' : 'pinheiro';
      const arvore = { x, z, escala, tipo, rot: rng.entre(0, TAU), rTronco: (tipo === 'seca' ? 0.3 : 0.38) * escala };
      mapa.arvores.push(arvore);
      const ck = k(Math.floor(x / celula), Math.floor(z / celula));
      if (!grade.has(ck)) grade.set(ck, []);
      grade.get(ck).push(arvore);
      if (r < cfg.RAIO_MUNDO + 3) circulo(x, z, arvore.rTronco, 'arvore');
      plantadas++;
    }
  }

  // ---- 8) Máscaras de porcelana penduradas, viradas para a vila
  {
    const viradaParaChama = (x, z) => Math.atan2(-x, -z);
    if (arvoreVila) {
      for (let m = 0; m < 3; m++) {
        const ang = arvoreVila.rot + (m * TAU) / 3;
        const x = arvoreVila.x + Math.sin(ang) * 1.0, z = arvoreVila.z + Math.cos(ang) * 1.0;
        mapa.mascarasDecorativas.push({ x, y: rng.entre(3.0, 4.0), z, rot: viradaParaChama(x, z), incl: rng.entre(-0.3, 0.3) });
      }
    }
    const candidatas = rng.embaralhar(mapa.arvores.filter((a) => !a.naVila && Math.hypot(a.x, a.z) < cfg.RAIO_CLAREIRA + 28));
    for (const a of candidatas.slice(0, cfg.NUM_MASCARAS_DECORATIVAS)) {
      const r = Math.hypot(a.x, a.z);
      const dx = -a.x / r, dz = -a.z / r; // direção da Chama
      const afast = a.rTronco + 0.14;
      const y = a.tipo === 'pinheiro' ? Math.min(2.3, 2.6 * a.escala - 0.4) - rng.entre(0, 0.35) : rng.entre(2.0, 3.2);
      mapa.mascarasDecorativas.push({ x: a.x + dx * afast, y, z: a.z + dz * afast, rot: Math.atan2(dx, dz), incl: rng.entre(-0.25, 0.25) });
    }
  }

  // ---- 9) Pedras
  for (let n = 0, tentativa = 0; n < cfg.NUM_PEDRAS && tentativa < cfg.NUM_PEDRAS * 20; tentativa++) {
    const r = Math.sqrt(rng.entre((cfg.RAIO_CLAREIRA - 4) ** 2, cfg.RAIO_FLORESTA_FIM ** 2));
    const a = rng.entre(0, TAU);
    const x = Math.sin(a) * r, z = Math.cos(a) * r;
    if (pertoDeTrilha(x, z) || pertoDeCasa(x, z, 1)) continue;
    const tam = rng.chance(0.25) ? rng.entre(1.0, 1.8) : rng.entre(0.35, 0.9);
    mapa.pedras.push({ x, z, r: tam, altura: rng.entre(0.45, 0.8), rot: rng.entre(0, TAU) });
    if (tam > 0.6 && r < cfg.RAIO_MUNDO + 3) circulo(x, z, tam * 0.85, 'pedra');
    n++;
  }

  // ---- Grade espacial + pontos de nascimento livres em volta da Chama
  mapa.grade = construirGrade(C, cfg.CELULA_GRADE);
  for (let n = 0; n < Config.servidor.MAX_JOGADORES; n++) {
    let ang = (n * TAU) / Config.servidor.MAX_JOGADORES + 0.4;
    const r = Config.jogador.RAIO_NASCER;
    for (let tentativa = 0; tentativa < 30; tentativa++) {
      const x = Math.sin(ang) * r, z = Math.cos(ang) * r;
      if (!sobrepoeColisor(mapa, x, z, Config.jogador.RAIO + 0.3)) {
        mapa.nascimentos.push({ x, z, ry: Math.atan2(x, z) }); // ry: olhando para a Chama
        break;
      }
      ang += 0.2;
    }
  }
  return mapa;
}
