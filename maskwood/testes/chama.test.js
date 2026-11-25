import test from 'node:test';
import assert from 'node:assert/strict';
import { Config } from '../src/compartilhado/Config.js';
import { ChamaMae } from '../src/servidor/ChamaMae.js';

const cfg = Config.chama;

test('o óleo cai mais rápido à noite do que de dia', () => {
  const dia = new ChamaMae(cfg, 100);
  const noite = new ChamaMae(cfg, 100);
  dia.avancar(60, 'dia');
  noite.avancar(60, 'noite');
  assert.ok(Math.abs(dia.oleo - (100 - cfg.CONSUMO_DIA * 60)) < 1e-9);
  assert.ok(noite.oleo < dia.oleo);
});

test('o raio seguro encolhe com o óleo e zera quando a Chama apaga', () => {
  const c = new ChamaMae(cfg, 100);
  assert.equal(c.raio, cfg.RAIO_MAX);
  c.oleo = 50;
  assert.ok(c.raio < cfg.RAIO_MAX && c.raio > cfg.RAIO_MIN);
  c.oleo = 0.001;
  assert.ok(Math.abs(c.raio - cfg.RAIO_MIN) < 0.01);
  c.oleo = 0;
  assert.equal(c.raio, 0);
  assert.equal(c.acesa, false);
});

test('avisa "óleo baixo" e "apagou" uma vez só', () => {
  const c = new ChamaMae(cfg, cfg.OLEO_BAIXO + 1);
  const tipos = [];
  for (let i = 0; i < 400; i++) tipos.push(...c.avancar(1, 'noite').map((e) => e.tipo));
  assert.deepEqual(tipos, ['oleoBaixo', 'apagou']);
  assert.equal(c.oleo, 0);
});

test('reacende ao receber óleo e não passa do máximo', () => {
  const c = new ChamaMae(cfg, 0);
  const tipos = c.adicionarOleo(30).map((e) => e.tipo);
  assert.ok(tipos.includes('reacendeu'));
  assert.equal(c.acesa, true);
  c.adicionarOleo(500);
  assert.equal(c.oleo, cfg.OLEO_MAX);
});

test('contem() diz quem está dentro da luz', () => {
  const c = new ChamaMae(cfg, 100);
  assert.equal(c.contem(0, cfg.RAIO_MAX - 0.5), true);
  assert.equal(c.contem(cfg.RAIO_MAX + 0.5, 0), false);
  c.oleo = 0;
  assert.equal(c.contem(0, 1), false);
});

test('com o tanque cheio a Chama aguenta o Dia 1 e a Noite 1, mas não o Dia 2', () => {
  const c = new ChamaMae(cfg, cfg.OLEO_INICIAL);
  c.avancar(Config.ciclo.DURACAO_DIA, 'dia');
  c.avancar(Config.ciclo.DURACAO_NOITE, 'noite');
  assert.equal(c.acesa, true, 'precisa sobreviver à primeira noite sem coleta');
  c.avancar(Config.ciclo.DURACAO_DIA, 'dia');
  assert.equal(c.acesa, false, 'sem buscar óleo, apaga no Dia 2');
});
