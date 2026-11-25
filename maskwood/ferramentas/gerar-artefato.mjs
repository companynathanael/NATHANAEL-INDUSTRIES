// Gera a versão do index.html usada para publicar o jogo como página no claude.ai (Artifact).
// A plataforma já coloca <!doctype>, <html>, <head>, <body>, charset e viewport; aqui só tiramos isso.
// Uso: node ferramentas/gerar-artefato.mjs [saida.html]   (padrão: dist/artefato.html)

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const saida = resolve(process.argv[2] ?? resolve(raiz, 'dist/artefato.html'));

let html = readFileSync(resolve(raiz, 'index.html'), 'utf8');
html = html
  .replace(/<!doctype html>\s*/i, '')
  .replace(/<\/?html[^>]*>\s*/gi, '')
  .replace(/<\/?head>\s*/gi, '')
  .replace(/<\/?body[^>]*>\s*/gi, '')
  .replace(/<meta charset[^>]*>\s*/i, '')
  .replace(/<meta name="viewport"[^>]*>\s*/i, '');

mkdirSync(dirname(saida), { recursive: true });
writeFileSync(saida, `${html.trim()}\n`);
console.log(`Gerado: ${saida}`);
