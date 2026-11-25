// Interface — HUD (Dia/Noite X, relógio, óleo da Chama, bússola), avisos, tela de entrada e menu.
// Só mexe no DOM quando o texto muda (leve no celular).

import { formatarTempo } from '../compartilhado/Matematica.js';

const $ = (id) => document.getElementById(id);

export class Interface {
  constructor() {
    this.el = {
      hud: $('hud'), faseNome: $('fase-nome'), faseRelogio: $('fase-relogio'),
      oleo: $('oleo'), oleoPreenchido: $('oleo-preenchido'), oleoValor: $('oleo-valor'),
      bussola: $('bussola'), bussolaSeta: $('bussola-seta'), bussolaTexto: $('bussola-texto'),
      luz: $('luz'), postura: $('postura'), pausado: $('pausado'),
      cartao: $('cartao'), cartaoTitulo: $('cartao-titulo'), cartaoTexto: $('cartao-texto'),
      avisos: $('avisos'), toque: $('toque'),
      entrada: $('entrada'), btnJogar: $('btn-jogar'), entradaProgresso: $('entrada-progresso'), dica: $('dica-controles'),
      menu: $('menu'), menuTeste: $('menu-teste'), btnTempo: $('btn-tempo'), btnPular: $('btn-pular'),
      confirmar: $('confirmar-apagar'), btnApagar: $('btn-apagar'), menuControles: $('menu-controles'),
      erro: $('erro'),
    };
  }

  #texto(el, texto) {
    if (el.__texto !== texto) {
      el.textContent = texto;
      el.__texto = texto;
    }
  }

  #classe(el, nome, ligada) {
    if (el.classList.contains(nome) !== ligada) el.classList.toggle(nome, ligada);
  }

  textoControles(ehToque) {
    return ehToque
      ? 'Arraste no lado esquerdo para andar e no direito para olhar. Correr e Agachar ficam no canto.'
      : 'WASD anda · mouse olha (clique para travar) · Shift corre · C agacha · Esc pausa';
  }

  // ------------------------------------------------------------------ entrada

  mostrarEntrada(estado, ehToque) {
    const { btnJogar, entradaProgresso, dica } = this.el;
    btnJogar.disabled = false;
    if (estado.noite > 1) {
      btnJogar.textContent = `Continuar · Dia ${estado.noite}`;
      entradaProgresso.textContent = `${estado.noite - 1} ${estado.noite === 2 ? 'noite sobrevivida' : 'noites sobrevividas'} de 100.`;
    } else {
      btnJogar.textContent = 'Entrar na floresta';
      entradaProgresso.textContent = 'Nenhuma noite sobrevivida ainda.';
    }
    dica.textContent = this.textoControles(ehToque);
  }

  esconderEntrada() {
    this.el.entrada.hidden = true;
  }

  mostrarHud(ehToque) {
    this.el.hud.hidden = false;
    this.definirToque(ehToque);
  }

  definirToque(ehToque) {
    this.el.toque.hidden = !ehToque;
    this.el.menuControles.textContent = this.textoControles(ehToque);
  }

  // ------------------------------------------------------------------ HUD

  atualizarHud(e, jogador, fn) {
    const { el } = this;
    const noite = e.fase === 'noite';
    this.#texto(el.faseNome, `${noite ? 'Noite' : 'Dia'} ${e.noite}`);
    const verbo = noite ? 'amanhece em' : 'anoitece em';
    const ritmo = e.aceleracao > 1 ? ` · ${e.aceleracao}×` : '';
    this.#texto(el.faseRelogio, `${verbo} ${formatarTempo(e.duracao - e.decorrido)}${ritmo}`);
    this.#classe(el.hud, 'noite', fn > 0.5);

    // Óleo
    const ch = e.chama;
    const pct = ch.oleoMax ? (ch.oleo / ch.oleoMax) * 100 : 0;
    el.oleoPreenchido.style.transform = `scaleX(${pct / 100})`;
    this.#texto(el.oleoValor, ch.acesa ? `${Math.ceil(pct)}%` : 'apagada');
    this.#classe(el.oleo, 'baixo', ch.acesa && pct < 20);
    this.#classe(el.oleo, 'apagada', !ch.acesa);

    // Bússola até a Chama (some quando ela está perto)
    const vx = -jogador.x, vz = -jogador.z;
    const dist = Math.hypot(vx, vz);
    const longe = dist > 9;
    this.#classe(el.bussola, 'visivel', longe);
    if (longe) {
      const s = Math.sin(jogador.yaw), c = Math.cos(jogador.yaw);
      const frente = vx * -s + vz * -c, direita = vx * c + vz * -s;
      el.bussolaSeta.style.transform = `rotate(${Math.atan2(direita, frente)}rad)`;
      this.#texto(el.bussolaTexto, `Chama-Mãe · ${Math.round(dist)} m`);
    }

    // Dentro/fora da luz (mostra quando escurece)
    const naLuz = ch.raio > 0 && dist <= ch.raio;
    this.#classe(el.luz, 'visivel', fn > 0.35);
    this.#classe(el.luz, 'fora', !naLuz);
    this.#texto(el.luz, naLuz ? 'Na luz da Chama' : ch.acesa ? 'Fora da luz' : 'A Chama apagou');

    this.#texto(el.postura, jogador.agachado ? 'Agachado' : jogador.correndo ? 'Correndo' : '');
    this.#classe(el.pausado, 'visivel', Boolean(e.pausado));
  }

  cartaoFase({ fase, noite, sobrevivida, reinicio }) {
    let titulo = `Dia ${noite}`;
    let texto = noite === 1 ? 'Conheça a vila antes de escurecer.' : 'Busque óleo antes de escurecer.';
    if (fase === 'noite') {
      titulo = `Noite ${noite}`;
      texto = 'Não desvie o olhar.';
    } else if (reinicio) {
      texto = 'Progresso apagado. A Chama-Mãe foi abastecida.';
    } else if (sobrevivida) {
      texto = `Você sobreviveu à noite ${sobrevivida}. Busque óleo antes de escurecer.`;
    }
    const { cartao, cartaoTitulo, cartaoTexto } = this.el;
    cartaoTitulo.textContent = titulo;
    cartaoTexto.textContent = texto;
    cartao.classList.toggle('noite', fase === 'noite');
    cartao.classList.remove('mostrar');
    void cartao.offsetWidth; // reinicia a animação
    cartao.classList.add('mostrar');
  }

  avisoChama(tipo) {
    const textos = {
      baixo: ['A Chama-Mãe está fraca. O óleo está no fim.', 'alerta'],
      apagou: ['A Chama-Mãe apagou. A vila está sem proteção.', 'perigo'],
      reacendeu: ['A Chama-Mãe voltou a arder.', 'bom'],
    };
    const [texto, estilo] = textos[tipo] ?? [];
    if (texto) this.aviso(texto, estilo);
  }

  aviso(texto, estilo = '') {
    const div = document.createElement('div');
    div.className = `aviso ${estilo}`;
    div.textContent = texto;
    this.el.avisos.append(div);
    while (this.el.avisos.children.length > 3) this.el.avisos.firstElementChild.remove();
    setTimeout(() => div.remove(), 4800);
  }

  // ------------------------------------------------------------------ menu

  abrirMenu(estado, debug) {
    this.el.menu.hidden = false;
    this.el.menuTeste.hidden = !debug;
    this.el.confirmar.hidden = true;
    this.el.btnApagar.hidden = false;
    this.atualizarMenu(estado);
  }

  atualizarMenu(estado) {
    if (this.el.menu.hidden || !estado) return;
    this.#texto(this.el.btnTempo, `Velocidade do tempo: ${estado.aceleracao}×`);
    this.#texto(this.el.btnPular, estado.fase === 'dia' ? 'Pular para o fim do dia' : 'Pular para o fim da noite');
  }

  fecharMenu() {
    this.el.menu.hidden = true;
  }

  pedirConfirmacaoApagar(mostrar) {
    this.el.confirmar.hidden = !mostrar;
    this.el.btnApagar.hidden = mostrar;
  }

  erro(mensagem) {
    this.el.erro.textContent = mensagem;
    this.el.erro.hidden = false;
  }
}
