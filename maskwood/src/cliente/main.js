// main.js — ponto de partida do cliente (equivalente aos LocalScripts do StarterPlayerScripts).
// Modo solo: o Servidor roda dentro desta página e conversa com o cliente só por mensagens
// (TransporteLocal). No co-op online (etapa 7) o mesmo Servidor roda em Node e só o transporte muda.

import * as THREE from 'three';
import { Config } from '../compartilhado/Config.js';
import { Eventos } from '../compartilhado/Eventos.js';
import { gerarMapa } from '../compartilhado/Mapa.js';
import { criarConexaoLocal } from '../compartilhado/TransporteLocal.js';
import { Servidor } from '../servidor/Servidor.js';
import { SalvamentoNavegador } from '../servidor/Salvamento.js';
import { construirMundo } from './Mundo.js';
import { ChamaVisual } from './ChamaVisual.js';
import { Iluminacao, fatorNoite } from './Iluminacao.js';
import { Controles } from './Controles.js';
import { JogadorLocal } from './JogadorLocal.js';
import { Interface } from './Interface.js';

const $ = (id) => document.getElementById(id);
const agoraS = () => performance.now() / 1000;

class Jogo {
  constructor() {
    this.ui = new Interface();
    this.ehToque = window.matchMedia?.('(pointer: coarse)').matches ?? false;
    this.estado = null;
    this.recebidoEm = 0;
    this.mapa = null;
    this.meuId = null;
    this.debug = false;
    this.entrando = false;
    this.jogando = false;
    this.menuAberto = false;
    this.ultimoEnvio = 0;
    this.ultimoQuadro = null;
    this.quadro = this.quadro.bind(this);
  }

  async iniciar() {
    this.#criarRenderizador();
    this.controles = new Controles({
      canvas: this.canvas,
      zonaAndar: $('zona-andar'), zonaOlhar: $('zona-olhar'),
      analogico: $('analogico'), pino: $('analogico-pino'),
      btnCorrer: $('btn-correr'), btnAgachar: $('btn-agachar'),
    });
    this.controles.aoMenu = () => (this.menuAberto ? this.fecharMenu() : this.abrirMenu());
    this.#ligarInterface();

    this.servidor = new Servidor({ salvamento: new SalvamentoNavegador() });
    await this.servidor.iniciar();
    this.servidor.iniciarLaco();
    this.rede = criarConexaoLocal(this.servidor);
    this.rede.aoReceber((tipo, dados) => this.receber(tipo, dados));
    requestAnimationFrame(this.quadro);
  }

  #criarRenderizador() {
    this.canvas = $('tela');
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: !this.ehToque, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, this.ehToque ? 1.5 : 2));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.cena = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(70, 1, 0.1, 260);
    this.camera.rotation.order = 'YXZ';
    this.#redimensionar();
    addEventListener('resize', () => this.#redimensionar());
  }

  #redimensionar() {
    const w = innerWidth, h = innerHeight;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.fov = w / h < 1 ? 82 : 70; // celular em pé: campo de visão mais aberto
    this.camera.updateProjectionMatrix();
  }

  #construirCena(semente) {
    if (this.mapa) return;
    this.mapa = gerarMapa({ ...Config.mapa, SEMENTE: semente });
    this.iluminacao = new Iluminacao(this.cena, this.camera);
    this.mundo = construirMundo(this.cena, this.mapa);
    this.chamaVisual = new ChamaVisual(this.cena, this.mapa.chama);
    this.jogador = new JogadorLocal(this.camera, this.mapa, Config.jogador);
  }

  // ------------------------------------------------------------------ rede

  receber(tipo, dados) {
    switch (tipo) {
      case Eventos.MUNDO:
        this.debug = dados.debug;
        this.#construirCena(dados.semente);
        this.#guardarEstado(dados.estado);
        this.ui.mostrarEntrada(dados.estado, this.ehToque);
        break;
      case Eventos.ESTADO:
        this.#guardarEstado(dados);
        this.ui.atualizarMenu(dados);
        break;
      case Eventos.BEM_VINDO:
        this.meuId = dados.id;
        this.jogador.posicionar(dados.jogador.x, dados.jogador.z, dados.jogador.ry);
        this.jogando = true;
        this.entrando = false;
        this.controles.definirAtivo(!this.menuAberto);
        this.ui.cartaoFase({ fase: this.estado.fase, noite: this.estado.noite });
        break;
      case Eventos.CORRIGIR:
        this.jogador.posicionar(dados.x, dados.z, dados.ry);
        break;
      case Eventos.FASE_MUDOU:
        if (this.jogando) this.ui.cartaoFase(dados);
        break;
      case Eventos.CHAMA:
        if (this.jogando) this.ui.avisoChama(dados.tipo);
        break;
      case Eventos.AVISO:
        this.ui.aviso(dados.texto);
        break;
      case Eventos.RECUSADO:
        this.ui.erro(dados.motivo);
        break;
      default:
        break;
    }
  }

  #guardarEstado(estado) {
    this.estado = estado;
    this.recebidoEm = agoraS();
  }

  /** Estado do servidor "adiantado" até agora (o relógio anda suave entre pacotes). */
  #estadoAtual() {
    const e = this.estado;
    const ritmo = e.pausado ? 0 : e.aceleracao;
    return { ...e, decorrido: Math.min(e.duracao, e.decorrido + (agoraS() - this.recebidoEm) * ritmo) };
  }

  // ------------------------------------------------------------------ entrar, menu

  entrar() {
    if (this.entrando || this.jogando || !this.mapa) return;
    this.entrando = true;
    this.ui.esconderEntrada();
    this.ui.mostrarHud(this.ehToque);
    this.#travarMouse();
    this.rede.enviar(Eventos.ENTRAR, { nome: 'Resgatista' });
  }

  abrirMenu() {
    if (!this.jogando || this.menuAberto) return;
    this.menuAberto = true;
    this.controles.definirAtivo(false);
    this.ui.abrirMenu(this.estado, this.debug);
    this.rede.enviar(Eventos.PAUSAR, { pausado: true });
    if (document.pointerLockElement) document.exitPointerLock?.();
  }

  fecharMenu() {
    if (!this.menuAberto) return;
    this.menuAberto = false;
    this.ui.fecharMenu();
    this.controles.definirAtivo(true);
    this.rede.enviar(Eventos.PAUSAR, { pausado: false });
    this.#travarMouse();
  }

  #travarMouse() {
    if (this.ehToque) return;
    try {
      const p = this.canvas.requestPointerLock?.();
      p?.catch?.(() => {}); // sem trava (ex.: dentro de um iframe): olha arrastando com o mouse
    } catch {
      /* idem */
    }
  }

  #ligarInterface() {
    $('btn-jogar').addEventListener('click', () => this.entrar());
    $('btn-menu').addEventListener('click', () => this.abrirMenu());
    $('btn-continuar').addEventListener('click', () => this.fecharMenu());
    $('btn-tempo').addEventListener('click', () => this.rede.enviar(Eventos.DEBUG, { acao: 'acelerar' }));
    $('btn-pular').addEventListener('click', () => this.rede.enviar(Eventos.DEBUG, { acao: 'pular' }));
    $('btn-oleo').addEventListener('click', () => this.rede.enviar(Eventos.DEBUG, { acao: 'oleo' }));
    $('btn-apagar').addEventListener('click', () => this.ui.pedirConfirmacaoApagar(true));
    $('btn-apagar-nao').addEventListener('click', () => this.ui.pedirConfirmacaoApagar(false));
    $('btn-apagar-sim').addEventListener('click', () => {
      this.rede.enviar(Eventos.REINICIAR, {});
      this.fecharMenu();
    });

    this.canvas.addEventListener('click', () => {
      if (this.jogando && !this.menuAberto && !document.pointerLockElement) this.#travarMouse();
    });
    document.addEventListener('pointerlockchange', () => {
      if (!document.pointerLockElement && this.jogando && !this.menuAberto) this.abrirMenu();
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.abrirMenu();
    });
    // Um toque de verdade liga os controles de toque (tablet/notebook com tela sensível).
    addEventListener('touchstart', () => {
      if (this.ehToque) return;
      this.ehToque = true;
      if (this.jogando) this.ui.definirToque(true);
    }, { passive: true });
  }

  // ------------------------------------------------------------------ quadro

  quadro(tMs) {
    requestAnimationFrame(this.quadro);
    if (!this.mapa || !this.estado) return;
    const agora = tMs / 1000;
    // Limite de 0,1 s: num celular lento (10 fps) o jogador ainda anda na velocidade certa.
    const dt = Math.min(0.1, Math.max(0, agora - (this.ultimoQuadro ?? agora)));
    this.ultimoQuadro = agora;

    const e = this.#estadoAtual();
    const fn = fatorNoite(e.fase, e.decorrido, e.duracao, Config.ciclo);

    if (this.jogando) {
      if (!this.menuAberto) {
        this.jogador.atualizar(dt, this.controles);
        this.#enviarMovimento(agora);
      }
    } else {
      this.#orbitar(agora);
    }

    this.iluminacao.atualizar(e, fn);
    this.chamaVisual.atualizar(dt, agora, e.chama, fn);
    this.mundo.atualizar(fn);
    if (this.jogando) this.ui.atualizarHud(e, this.jogador, fn);
    this.renderer.render(this.cena, this.camera);
  }

  #enviarMovimento(agora) {
    if (agora - this.ultimoEnvio < 1 / Config.jogador.ENVIO_HZ) return;
    this.ultimoEnvio = agora;
    const j = this.jogador;
    this.rede.enviar(Eventos.MOVER, { x: j.x, z: j.z, ry: j.yaw, agachado: j.agachado, correndo: j.correndo });
  }

  /** Tela de entrada: a câmera dá voltas lentas em volta da Chama-Mãe. */
  #orbitar(agora) {
    const ang = agora * 0.045 + 0.8;
    this.camera.position.set(Math.sin(ang) * 12, 3.2, Math.cos(ang) * 12);
    this.camera.lookAt(0, 2.4, 0);
  }
}

const jogo = new Jogo();
window.maskwood = jogo; // ajuda a testar pelo console
jogo.iniciar().catch((erro) => {
  console.error(erro);
  jogo.ui.erro('Este navegador não conseguiu abrir o 3D (WebGL). Tente o Chrome, o Safari ou o Firefox atualizados.');
});
