// Teste de fumaça da Última Centelha.
// Uso: node jogos/ultima-centelha/teste_fumaca.js [pasta-para-capturas]
// Abre o jogo num navegador sem tela, joga as noites em velocidade acelerada
// e confere que nada quebra. Sai com código 1 se algum teste falhar.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ARQ = path.join(__dirname, 'index.html');
const SAIDA = process.argv[2] || null;
const resultados = [];
const teste = async (nome, fn) => {
  try { await fn(); resultados.push([nome, true]); console.log('ok   ', nome); }
  catch (e) { resultados.push([nome, false, e.message]); console.log('FALHA', nome, '→', e.message); }
};
const verifica = (cond, msg) => { if (!cond) throw new Error(msg); };

(async () => {
  // Mesmo esqueleto que a publicação acrescenta em volta da página.
  const corpo = fs.readFileSync(ARQ, 'utf8');
  const html = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>' + corpo + '</body></html>';
  const tmp = path.join(require('os').tmpdir(), 'ultima-centelha-teste.html');
  fs.writeFileSync(tmp, html);

  const browser = await chromium.launch();
  const erros = [];
  const abrir = async (viewport) => {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
    page.on('pageerror', e => erros.push(String(e)));
    page.on('console', m => { if (m.type() === 'error' && !/fonts\.g/.test(m.text())) erros.push(m.text()); });
    await page.goto('file://' + tmp);
    await page.waitForTimeout(400);
    return page;
  };
  const foto = async (page, nome) => { if (SAIDA) await page.screenshot({ path: path.join(SAIDA, nome + '.png') }); };
  const avancar = (page, seg) => page.evaluate(s => window.__uc.avancar(s), seg);
  const invencivel = page => page.evaluate(() => window.__uc.deus());

  const page = await abrir({ width: 1280, height: 800 });

  await teste('tela inicial aparece', async () => {
    verifica(await page.isVisible('#tInicio'), 'tela inicial escondida');
    verifica((await page.textContent('#bJogarTxt')).includes('Noite 1'), 'botão sem noite');
    await foto(page, '01-inicio');
  });

  await teste('prólogo abre e pode ser pulado', async () => {
    await page.click('#bJogar');
    await page.waitForTimeout(1500);
    verifica(await page.isVisible('#tPrologo'), 'prólogo não abriu');
    await foto(page, '02-prologo');
    await page.click('#bPular');
    await page.waitForTimeout(200);
    verifica(await page.evaluate(() => !!window.__uc.R), 'partida não começou');
  });

  await teste('movimento pelo teclado', async () => {
    const x0 = await page.evaluate(() => window.__uc.R.p.x);
    await page.keyboard.down('d'); await page.waitForTimeout(700); await page.keyboard.up('d');
    const x1 = await page.evaluate(() => window.__uc.R.p.x);
    verifica(x1 > x0 + 40, `não andou (${x0} → ${x1})`);
  });

  await teste('noite 1 avança: inimigos, níveis e armas', async () => {
    await invencivel(page);
    await avancar(page, 70);
    const r = await page.evaluate(() => { const R = window.__uc.R; return { en: R.en.length, lvl: R.lvl, kills: R.kills, armas: Object.keys(R.armas).length }; });
    verifica(r.en > 10, 'poucos inimigos: ' + r.en);
    verifica(r.lvl >= 2, 'não subiu de nível: ' + r.lvl);
    verifica(r.kills > 30, 'poucos abates: ' + r.kills);
    await page.waitForTimeout(300);
    await foto(page, '03-jogo');
  });

  await teste('tela de subir de nível', async () => {
    await page.evaluate(() => window.__uc.xp(window.__uc.R.prox + 1));
    await page.waitForTimeout(250);
    verifica(await page.isVisible('#tNivel'), 'cartas não apareceram');
    verifica((await page.$$('#nCartas .carta')).length >= 2, 'menos de 2 cartas');
    await foto(page, '04-nivel');
    await page.waitForTimeout(450);
    await page.keyboard.press('1');
    await page.waitForTimeout(150);
    verifica(!(await page.isVisible('#tNivel')), 'cartas não fecharam');
  });

  await teste('chefe aparece e a noite amanhece', async () => {
    await invencivel(page);
    await avancar(page, 70);
    const chefe = await page.evaluate(() => { const R = window.__uc.R; return R.chefeFeito; });
    verifica(chefe, 'chefe não apareceu');
    await page.waitForTimeout(200);
    await foto(page, '05-chefe');
    await avancar(page, 45);
    await page.waitForTimeout(1000);
    verifica(await page.isVisible('#tFim'), 'tela de fim não apareceu');
    verifica((await page.textContent('#fTitulo')).includes('Amanheceu'), 'não amanheceu');
    const S = await page.evaluate(() => window.__uc.S);
    verifica(S.noiteMax === 2, 'noite 2 não liberada');
    verifica(S.registros.r05 && S.registros.r01, 'registros 001/005 não recuperados');
    await page.waitForTimeout(2500);
    await foto(page, '06-amanheceu');
  });

  await teste('morte na noite 2 mostra a identidade da luz', async () => {
    await page.click('#bDeNovo');
    await page.waitForTimeout(200);
    const n = await page.evaluate(() => window.__uc.R.n);
    verifica(n === 2, 'não foi para a noite 2: ' + n);
    await avancar(page, 20);
    await page.evaluate(() => { const R = window.__uc.R; R.p.hp = 1; R.p.inv = 0; });
    for (let i = 0; i < 40 && !(await page.isVisible('#tFim')); i++) await avancar(page, 1);
    await page.waitForTimeout(400);
    verifica(await page.isVisible('#tFim'), 'não morreu');
    verifica((await page.textContent('#fTitulo')).includes('Apagada'), 'título errado');
    verifica((await page.textContent('#fId')).includes('unidade de luz'), 'sem identidade');
    await page.waitForTimeout(2000);
    await foto(page, '07-apagada');
  });

  await teste('forja compra melhoria', async () => {
    await page.click('#bFimForja');
    const antes = await page.evaluate(() => window.__uc.S.brasas);
    await page.click('#fo-ima');
    const depois = await page.evaluate(() => ({ b: window.__uc.S.brasas, l: window.__uc.S.forja.ima }));
    verifica(depois.l === 1 && depois.b < antes, 'compra não aconteceu');
    await foto(page, '08-forja');
    await page.click('#bFoVoltar');
    verifica(await page.isVisible('#tFim'), 'não voltou ao fim');
  });

  await teste('noites 2 a 5, revelação e escolha final', async () => {
    for (let n = 2; n <= 5; n++) {
      await page.evaluate(k => { window.__uc.S.noiteSel = k; }, n);
      await page.click('#bFimMenu');
      await page.click('#bJogar');
      await page.waitForTimeout(100);
      await invencivel(page);
      for (let i = 0; i < 40 && await page.evaluate(() => window.__uc.R && window.__uc.R.modo !== 'fim'); i++) { await avancar(page, 10); await invencivel(page); }
      await page.waitForTimeout(900);
      if (n < 5) verifica(await page.isVisible('#tFim'), 'fim da noite ' + n + ' não apareceu');
    }
    verifica(await page.isVisible('#tFinal'), 'escolha final não apareceu');
    await foto(page, '09-escolha');
    const S = await page.evaluate(() => window.__uc.S);
    verifica(S.registros.r12, 'confissão (r12) não recuperada');
    verifica(S.registros.r13, 'registro 013 não recuperado');
    await page.click('#bDevolver');
    await page.waitForTimeout(2500);
    verifica(await page.isVisible('#tEpilogo'), 'epílogo não apareceu');
    await foto(page, '10-devolver');
    await page.click('#bEpFim');
    verifica(await page.evaluate(() => window.__uc.S.noiteMax === 6), 'noites eternas não liberadas');
  });

  await teste('depois da revelação a morte mostra o nome', async () => {
    await page.evaluate(() => { window.__uc.S.noiteSel = 1; });
    await page.click('#bJogar');
    await page.evaluate(() => { const R = window.__uc.R; R.p.hp = 1; });
    for (let i = 0; i < 170 && !(await page.isVisible('#tFim')); i++) await avancar(page, 1);
    await page.waitForTimeout(400);
    verifica((await page.textContent('#fId')).includes('Esta luz era'), 'nome não revelado');
  });

  await teste('registros listam 18 entradas', async () => {
    await page.click('#bFimMenu');
    await foto(page, '11-inicio-depois');
    await page.click('#bRegs');
    verifica((await page.$$('#rgLista .reg')).length === 18, 'quantidade errada');
    await foto(page, '12-registros');
    await page.click('#bRgVoltar');
  });

  await teste('noites eternas rodam com chefe repetido', async () => {
    await page.evaluate(() => { window.__uc.S.noiteSel = 6; });
    await page.click('#bFimMenu').catch(() => {});
    await page.evaluate(() => document.querySelector('#bJogar').click());
    await page.waitForTimeout(100);
    await invencivel(page);
    for (let i = 0; i < 32; i++) { await avancar(page, 10); await invencivel(page); }
    const r = await page.evaluate(() => ({ n: window.__uc.R.n, t: window.__uc.R.t, en: window.__uc.R.en.length, ch: window.__uc.R.chefesMortos + (window.__uc.R.chefe ? 1 : 0) }));
    verifica(r.n === 6 && r.t > 300, 'eterna não avançou');
    verifica(r.ch >= 1, 'nenhum chefe nas eternas');
    verifica(r.en <= 420, 'inimigos acima do limite: ' + r.en);
  });

  await teste('desempenho do quadro com a tela cheia', async () => {
    const ms = await page.evaluate(() => new Promise(res => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (n < 60) requestAnimationFrame(f); else res((performance.now() - t0) / 60); }; requestAnimationFrame(f); }));
    const en = await page.evaluate(() => window.__uc.R.en.length);
    console.log(`      ${en} inimigos · ${ms.toFixed(1)} ms por quadro (navegador sem GPU)`);
    await foto(page, '13-eternas');
  });

  const cel = await abrir({ width: 390, height: 844 });
  await teste('celular: início, jogo e cartas cabem na tela', async () => {
    await foto(cel, '14-cel-inicio');
    await cel.evaluate(() => { window.__uc.S.prologo = true; });
    await cel.click('#bJogar');
    await cel.mouse.move(195, 600); await cel.mouse.down(); await cel.mouse.move(260, 600, { steps: 5 }); await cel.waitForTimeout(500);
    const x = await cel.evaluate(() => window.__uc.R.p.x);
    await cel.mouse.up();
    verifica(x > 20, 'joystick não moveu: ' + x);
    await invencivel(cel); await avancar(cel, 60);
    await cel.waitForTimeout(300); await foto(cel, '15-cel-jogo');
    await cel.evaluate(() => window.__uc.xp(window.__uc.R.prox + 1));
    await cel.waitForTimeout(500); await foto(cel, '16-cel-nivel');
    const larg = await cel.evaluate(() => document.documentElement.scrollWidth);
    verifica(larg <= 390, 'rolagem horizontal: ' + larg);
  });

  await teste('sem erros no console', async () => { verifica(erros.length === 0, erros.slice(0, 3).join(' | ')); });

  await browser.close();
  const falhas = resultados.filter(r => !r[1]).length;
  console.log(`\n${resultados.length - falhas} ok · ${falhas} falha(s)`);
  process.exit(falhas ? 1 : 0);
})();
