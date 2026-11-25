import test from 'node:test';
import assert from 'node:assert/strict';
import { Config } from '../src/compartilhado/Config.js';
import { gerarMapa, distanciaTrilhas } from '../src/compartilhado/Mapa.js';
import { moverCirculo, sobrepoeColisor } from '../src/compartilhado/Fisica.js';

const mapa = gerarMapa(Config.mapa);
const cfg = Config.mapa;

test('a mesma semente gera o mesmo mapa (servidor e cliente concordam)', () => {
  const outro = gerarMapa(Config.mapa);
  assert.deepEqual(outro.arvores.slice(0, 50), mapa.arvores.slice(0, 50));
  assert.deepEqual(outro.caixas, mapa.caixas);
  assert.deepEqual(outro.nascimentos, mapa.nascimentos);
});

test('outra semente gera outro mapa', () => {
  const outro = gerarMapa({ ...Config.mapa, SEMENTE: 42 });
  assert.notDeepEqual(outro.arvores.slice(0, 5), mapa.arvores.slice(0, 5));
});

test('floresta densa: planta pelo menos 85% das árvores pedidas', () => {
  assert.ok(mapa.arvores.length >= cfg.NUM_ARVORES * 0.85, `só ${mapa.arvores.length} árvores`);
});

test('a vila tem 6 casas em ruínas com paredes, poço e árvore seca', () => {
  assert.equal(mapa.casas.length, cfg.NUM_CASAS);
  assert.ok(mapa.caixas.filter((c) => c.tipo === 'parede').length > 30);
  assert.ok(mapa.poco);
  assert.ok(mapa.arvores.some((a) => a.naVila));
});

test('a clareira não tem árvores (fora a árvore seca da vila)', () => {
  for (const a of mapa.arvores) {
    if (a.naVila) continue;
    assert.ok(Math.hypot(a.x, a.z) >= cfg.RAIO_CLAREIRA - 5, `árvore em ${a.x.toFixed(1)}, ${a.z.toFixed(1)}`);
  }
});

test('as trilhas ficam livres de árvores', () => {
  for (const a of mapa.arvores) {
    assert.ok(distanciaTrilhas(mapa.trilhas, a.x, a.z) > cfg.LARGURA_TRILHA / 2 + a.rTronco);
  }
});

test('há 4 pontos de nascimento livres em volta da Chama', () => {
  assert.equal(mapa.nascimentos.length, Config.servidor.MAX_JOGADORES);
  for (const n of mapa.nascimentos) {
    assert.equal(sobrepoeColisor(mapa, n.x, n.z, Config.jogador.RAIO), false);
    assert.ok(Math.abs(Math.hypot(n.x, n.z) - Config.jogador.RAIO_NASCER) < 0.01);
  }
});

test('máscaras decorativas penduradas e viradas para a vila', () => {
  assert.ok(mapa.mascarasDecorativas.length >= cfg.NUM_MASCARAS_DECORATIVAS);
  for (const m of mapa.mascarasDecorativas) {
    const paraChama = Math.atan2(-m.x, -m.z);
    const dif = Math.abs(Math.atan2(Math.sin(m.rot - paraChama), Math.cos(m.rot - paraChama)));
    assert.ok(dif < 0.5);
  }
});

test('física: não atravessa o tronco de uma árvore', () => {
  const a = mapa.arvores.find((x) => !x.naVila && Math.hypot(x.x, x.z) < 60);
  // Começa 3 m antes da árvore e tenta passar por dentro dela.
  const r = Math.hypot(a.x, a.z);
  const dx = a.x / r, dz = a.z / r;
  let p = { x: a.x - dx * 3, z: a.z - dz * 3 };
  for (let i = 0; i < 60; i++) p = moverCirculo(mapa, p.x, p.z, dx * 0.1, dz * 0.1, Config.jogador.RAIO);
  assert.ok(Math.hypot(p.x - a.x, p.z - a.z) >= a.rTronco + Config.jogador.RAIO - 0.01);
});

test('física: não atravessa uma parede de ruína', () => {
  const parede = mapa.caixas.find((c) => c.tipo === 'parede' && c.hx > 0.6);
  const cs = Math.cos(parede.rot), sn = Math.sin(parede.rot);
  // normal local +z da parede no mundo = (sin, cos)
  const nx = sn, nz = cs;
  let p = { x: parede.x + nx * 2, z: parede.z + nz * 2 };
  for (let i = 0; i < 60; i++) p = moverCirculo(mapa, p.x, p.z, -nx * 0.1, -nz * 0.1, Config.jogador.RAIO);
  const lado = (p.x - parede.x) * nx + (p.z - parede.z) * nz;
  assert.ok(lado > parede.hz, `atravessou: ${lado}`);
});

test('física: o limite do mundo segura o jogador', () => {
  let p = { x: 0, z: cfg.RAIO_MUNDO - 3 };
  for (let i = 0; i < 100; i++) p = moverCirculo(mapa, p.x, p.z, 0, 0.5, Config.jogador.RAIO);
  assert.ok(Math.hypot(p.x, p.z) <= cfg.RAIO_MUNDO);
});
