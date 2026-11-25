import test from 'node:test';
import assert from 'node:assert/strict';
import { Config } from '../src/compartilhado/Config.js';
import { Eventos } from '../src/compartilhado/Eventos.js';
import { gerarMapa } from '../src/compartilhado/Mapa.js';
import { criarConexaoLocal } from '../src/compartilhado/TransporteLocal.js';
import { Servidor, sanitizarMundo, CHAVE_MUNDO } from '../src/servidor/Servidor.js';
import { SalvamentoMemoria } from '../src/servidor/Salvamento.js';

const mapa = gerarMapa(Config.mapa); // gera uma vez só para todos os testes

function relogioFalso() {
  let t = 0;
  const f = () => t;
  f.andar = (s) => { t += s; };
  return f;
}

function conexaoFalsa(id) {
  const c = { id, recebidas: [], aoReceber(f) { this.mandar = f; }, aoFechar(f) { this.fechar = f; } };
  c.enviar = (tipo, dados) => c.recebidas.push({ tipo, dados: structuredClone(dados) });
  c.ultima = (tipo) => c.recebidas.filter((m) => m.tipo === tipo).at(-1)?.dados;
  return c;
}

async function criar({ config = Config, salvamento = new SalvamentoMemoria() } = {}) {
  const relogio = relogioFalso();
  const s = await new Servidor({ config, salvamento, relogio, mapa }).iniciar();
  return { s, relogio, salvamento };
}

function entrar(s, id = 'a') {
  const c = conexaoFalsa(id);
  s.conectar(c);
  c.mandar(Eventos.ENTRAR, { nome: `Jogador ${id}` });
  return c;
}

/** Simula `segundos` com passos de 50 ms (igual ao laço real de 20 Hz). */
function rodar(s, relogio, segundos) {
  const passos = Math.round(segundos / 0.05);
  for (let i = 0; i < passos; i++) { relogio.andar(0.05); s.passo(0.05); }
}

test('manda o Mundo ao conectar e BemVindo ao entrar', async () => {
  const { s } = await criar();
  const c = conexaoFalsa('a');
  s.conectar(c);
  assert.equal(c.ultima(Eventos.MUNDO).semente, Config.mapa.SEMENTE);
  c.mandar(Eventos.ENTRAR, { nome: 'Ana' });
  const bv = c.ultima(Eventos.BEM_VINDO);
  assert.equal(bv.id, 'a');
  assert.ok(Number.isFinite(bv.jogador.x));
});

test('sem ninguém na clareira o tempo não passa e o óleo não cai', async () => {
  const { s, relogio } = await criar();
  rodar(s, relogio, 10);
  assert.equal(s.ciclo.decorrido, 0);
  assert.equal(s.chama.oleo, Config.chama.OLEO_INICIAL);
});

test('depois do dia, anoitece e todos recebem FaseMudou', async () => {
  const cfg = { ...Config, ciclo: { ...Config.ciclo, DURACAO_DIA: 2, DURACAO_NOITE: 3 } };
  const { s, relogio } = await criar({ config: cfg });
  const c = entrar(s);
  rodar(s, relogio, 2.1);
  assert.equal(s.ciclo.fase, 'noite');
  assert.deepEqual(c.ultima(Eventos.FASE_MUDOU), { fase: 'noite', noite: 1 });
  rodar(s, relogio, 0.2);
  assert.equal(c.ultima(Eventos.ESTADO).fase, 'noite');
});

test('ao amanhecer salva o progresso, e um servidor novo continua do mesmo dia', async () => {
  const cfg = { ...Config, ciclo: { ...Config.ciclo, DURACAO_DIA: 2, DURACAO_NOITE: 3 } };
  const { s, relogio, salvamento } = await criar({ config: cfg });
  entrar(s);
  rodar(s, relogio, 5.1);
  await s.ultimoSalvamento;
  const salvo = await salvamento.carregar(CHAVE_MUNDO);
  assert.equal(salvo.noite, 2);
  assert.ok(salvo.oleo < Config.chama.OLEO_INICIAL);
  const { s: novo } = await criar({ config: cfg, salvamento });
  assert.equal(novo.ciclo.noite, 2);
  assert.equal(novo.ciclo.fase, 'dia');
  assert.equal(novo.chama.oleo, salvo.oleo);
});

test('o óleo usa a taxa da noite depois da virada, mesmo num passo só', async () => {
  const cfg = { ...Config, servidor: { ...Config.servidor, DT_MAXIMO: 1000 } };
  const { s } = await criar({ config: cfg });
  entrar(s);
  s.passo(Config.ciclo.DURACAO_DIA + 100);
  const esperado = Config.chama.OLEO_INICIAL - Config.chama.CONSUMO_DIA * Config.ciclo.DURACAO_DIA - Config.chama.CONSUMO_NOITE * 100;
  assert.ok(Math.abs(s.chama.oleo - esperado) < 1e-6);
});

test('recusa o 5º jogador', async () => {
  const { s } = await criar();
  for (const id of ['a', 'b', 'c', 'd']) entrar(s, id);
  const quinto = entrar(s, 'e');
  assert.ok(quinto.ultima(Eventos.RECUSADO));
  assert.equal(s.jogadores.quantidade, 4);
});

test('cada jogador nasce num ponto diferente', async () => {
  const { s } = await criar();
  const pos = ['a', 'b', 'c', 'd'].map((id) => entrar(s, id).ultima(Eventos.BEM_VINDO).jogador);
  const unicos = new Set(pos.map((p) => `${p.x.toFixed(2)},${p.z.toFixed(2)}`));
  assert.equal(unicos.size, 4);
});

test('aceita um passo normal', async () => {
  const { s, relogio } = await criar();
  const c = entrar(s);
  const j = s.jogadores.obter('a');
  const { x, z } = j;
  relogio.andar(0.1);
  c.mandar(Eventos.MOVER, { x: x + 0.3, z, ry: 1 });
  assert.ok(Math.abs(j.x - (x + 0.3)) < 1e-9);
  assert.equal(c.ultima(Eventos.CORRIGIR), undefined);
});

test('anti-exploit: recusa teletransporte e manda Corrigir', async () => {
  const { s, relogio } = await criar();
  const c = entrar(s);
  const j = s.jogadores.obter('a');
  const { x, z } = j;
  relogio.andar(0.1);
  c.mandar(Eventos.MOVER, { x: x + 40, z, ry: 0 });
  assert.equal(j.x, x);
  assert.deepEqual(c.ultima(Eventos.CORRIGIR), { x, z });
});

test('anti-exploit: recusa posição dentro do pedestal da Chama e valores inválidos', async () => {
  const { s, relogio } = await criar();
  const c = entrar(s);
  const j = s.jogadores.obter('a');
  // chega perto do pedestal aos poucos (passos válidos) e tenta entrar nele
  const alvo = { x: 0.3, z: 0.3 };
  const antes = { x: j.x, z: j.z };
  for (let i = 0; i < 30; i++) {
    relogio.andar(0.5);
    c.mandar(Eventos.MOVER, { x: antes.x + (alvo.x - antes.x) * (i + 1) / 30, z: antes.z + (alvo.z - antes.z) * (i + 1) / 30 });
  }
  assert.ok(Math.hypot(j.x, j.z) > mapa.chama.raioPedestal);
  relogio.andar(0.1);
  c.mandar(Eventos.MOVER, { x: 'abc', z: null });
  assert.ok(Number.isFinite(j.x) && Number.isFinite(j.z));
});

test('modo solo: o menu pausa o jogo; com 2 jogadores, não', async () => {
  const { s, relogio } = await criar();
  const a = entrar(s, 'a');
  a.mandar(Eventos.PAUSAR, { pausado: true });
  rodar(s, relogio, 2);
  assert.equal(s.ciclo.decorrido, 0);
  entrar(s, 'b');
  rodar(s, relogio, 2);
  assert.ok(s.ciclo.decorrido > 1.9);
});

test('debug: acelerar, pular e pôr óleo; e nada disso com PERMITIR_DEBUG desligado', async () => {
  const { s, relogio } = await criar();
  const c = entrar(s);
  c.mandar(Eventos.DEBUG, { acao: 'acelerar' });
  assert.equal(s.aceleracao, 10);
  rodar(s, relogio, 1);
  assert.ok(Math.abs(s.ciclo.decorrido - 10) < 1e-6);
  c.mandar(Eventos.DEBUG, { acao: 'pular' });
  assert.ok(s.ciclo.restante <= 3);
  s.chama.oleo = 10;
  c.mandar(Eventos.DEBUG, { acao: 'oleo' });
  assert.equal(s.chama.oleo, 10 + Config.chama.OLEO_DEBUG);

  const cfg = { ...Config, servidor: { ...Config.servidor, PERMITIR_DEBUG: false } };
  const { s: producao } = await criar({ config: cfg });
  const p = entrar(producao);
  p.mandar(Eventos.DEBUG, { acao: 'acelerar' });
  assert.equal(producao.aceleracao, 1);
});

test('a Chama apagando avisa os jogadores', async () => {
  const { s, relogio } = await criar();
  const c = entrar(s);
  s.chama.oleo = 0.01;
  rodar(s, relogio, 1);
  assert.deepEqual(c.ultima(Eventos.CHAMA), { tipo: 'apagou' });
  assert.equal(c.ultima(Eventos.ESTADO).chama.raio, 0);
});

test('apagar progresso volta para o Dia 1 com a Chama cheia (só jogando sozinho)', async () => {
  const { s, relogio, salvamento } = await criar();
  const c = entrar(s);
  s.ciclo.noite = 7;
  s.chama.oleo = 3;
  c.mandar(Eventos.REINICIAR, {});
  await s.ultimoSalvamento;
  assert.equal(s.ciclo.noite, 1);
  assert.equal(s.chama.oleo, Config.chama.OLEO_INICIAL);
  assert.equal((await salvamento.carregar(CHAVE_MUNDO)).noite, 1);
  assert.equal(c.ultima(Eventos.FASE_MUDOU).reinicio, true);
  rodar(s, relogio, 0.2);
  entrar(s, 'b');
  s.ciclo.noite = 4;
  c.mandar(Eventos.REINICIAR, {});
  assert.equal(s.ciclo.noite, 4);
});

test('salvamento corrompido ou mexido volta para valores seguros', () => {
  assert.deepEqual(sanitizarMundo(null), { noite: 1, oleo: Config.chama.OLEO_INICIAL });
  assert.deepEqual(sanitizarMundo({ noite: 9999, oleo: 1e9 }), { noite: 1, oleo: Config.chama.OLEO_MAX });
  assert.deepEqual(sanitizarMundo({ noite: '5', oleo: 'muito' }), { noite: 1, oleo: Config.chama.OLEO_INICIAL });
  assert.deepEqual(sanitizarMundo({ noite: 12, oleo: 40 }), { noite: 12, oleo: 40 });
});

test('transporte local: as mensagens são cópias (cliente não mexe no objeto do servidor)', async () => {
  const { s } = await criar();
  const cliente = criarConexaoLocal(s);
  const recebidas = [];
  cliente.aoReceber((tipo, dados) => recebidas.push({ tipo, dados }));
  const dados = { nome: 'Bia' };
  cliente.enviar(Eventos.ENTRAR, dados);
  dados.nome = 'Hacker';
  await new Promise((r) => setTimeout(r, 10));
  assert.equal(s.jogadores.lista()[0].nome, 'Bia');
  const mundo = recebidas.find((m) => m.tipo === Eventos.MUNDO).dados;
  mundo.estado.chama.oleo = 9999;
  assert.equal(s.chama.oleo, Config.chama.OLEO_INICIAL);
  cliente.fechar();
  assert.equal(s.jogadores.quantidade, 0);
});
