import test from 'node:test';
import assert from 'node:assert/strict';
import { CicloDiaNoite } from '../src/servidor/CicloDiaNoite.js';

const cfg = { DURACAO_DIA: 240, DURACAO_NOITE: 300 };

test('começa no Dia 1', () => {
  const c = new CicloDiaNoite(cfg);
  assert.equal(c.fase, 'dia');
  assert.equal(c.noite, 1);
  assert.equal(c.restante, 240);
});

test('anoitece depois de 4 minutos de dia', () => {
  const c = new CicloDiaNoite(cfg);
  assert.deepEqual(c.avancar(239.9), []);
  const eventos = c.avancar(0.2);
  assert.deepEqual(eventos.map((e) => e.tipo), ['anoiteceu']);
  assert.equal(c.fase, 'noite');
  assert.equal(c.noite, 1);
  assert.ok(Math.abs(c.decorrido - 0.1) < 1e-6);
});

test('amanhece depois de 5 minutos de noite e passa para o Dia 2', () => {
  const c = new CicloDiaNoite(cfg, { fase: 'noite', noite: 1 });
  const [ev] = c.avancar(300);
  assert.equal(ev.tipo, 'amanheceu');
  assert.equal(ev.sobrevivida, 1);
  assert.equal(c.noite, 2);
  assert.equal(c.fase, 'dia');
});

test('um salto grande atravessa várias fases sem perder eventos', () => {
  const c = new CicloDiaNoite(cfg);
  const eventos = c.avancar(240 + 300 + 240 + 10);
  assert.deepEqual(eventos.map((e) => e.tipo), ['anoiteceu', 'amanheceu', 'anoiteceu']);
  assert.equal(c.noite, 2);
  assert.equal(c.fase, 'noite');
  assert.ok(Math.abs(c.decorrido - 10) < 1e-6);
});

test('pularParaFim deixa só alguns segundos na fase', () => {
  const c = new CicloDiaNoite(cfg);
  c.pularParaFim(3);
  assert.equal(c.restante, 3);
});
