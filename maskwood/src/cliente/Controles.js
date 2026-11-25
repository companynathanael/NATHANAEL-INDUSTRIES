// Controles — junta teclado, mouse e toque num formato só, que o JogadorLocal entende.
// PC: WASD/setas andam, mouse olha (clique trava o cursor), Shift corre, C agacha, Esc/M menu.
// Celular: arraste no lado esquerdo = analógico; arraste no lado direito = olhar; botões Correr/Agachar.

const SENS_MOUSE = 0.0024;  // radianos por pixel
const SENS_TOQUE = 0.0058;
const RAIO_ANALOGICO = 56;  // px
const ZONA_MORTA = 0.12;

export class Controles {
  constructor({ canvas, zonaAndar, zonaOlhar, analogico, pino, btnCorrer, btnAgachar }) {
    this.canvas = canvas;
    this.el = { zonaAndar, zonaOlhar, analogico, pino, btnCorrer, btnAgachar };
    this.teclas = new Set();
    this.olharX = 0;
    this.olharY = 0;
    this.agachado = false;
    this.correrToque = false;
    this.analogico = { x: 0, y: 0 };
    this.ativo = false;
    this.mouseApertado = false;
    this.idAndar = null;
    this.idOlhar = null;
    this.aoMenu = () => {};
    this.aoPostura = () => {};
    this.#teclado();
    this.#mouse();
    this.#toque();
  }

  /** Direção pedida: x = lado (direita +), y = frente/trás (frente −). Comprimento ≤ 1. */
  get eixo() {
    const t = this.teclas;
    let x = this.analogico.x, y = this.analogico.y;
    if (t.has('KeyW') || t.has('ArrowUp')) y -= 1;
    if (t.has('KeyS') || t.has('ArrowDown')) y += 1;
    if (t.has('KeyA') || t.has('ArrowLeft')) x -= 1;
    if (t.has('KeyD') || t.has('ArrowRight')) x += 1;
    const comp = Math.hypot(x, y);
    if (comp > 1) { x /= comp; y /= comp; }
    return { x, y };
  }

  get correndo() {
    if (this.agachado) return false;
    return this.correrToque || this.teclas.has('ShiftLeft') || this.teclas.has('ShiftRight');
  }

  /** Quanto o jogador girou a visão desde o último quadro (em radianos). */
  consumirOlhar() {
    const r = { dx: this.olharX, dy: this.olharY };
    this.olharX = 0;
    this.olharY = 0;
    return r;
  }

  definirAtivo(ativo) {
    this.ativo = ativo;
    if (!ativo) {
      this.teclas.clear();
      this.#soltarAnalogico();
      this.idOlhar = null;
      this.olharX = this.olharY = 0;
    }
  }

  alternarAgachar() {
    this.agachado = !this.agachado;
    if (this.agachado) this.correrToque = false;
    this.#atualizarBotoes();
  }

  alternarCorrer() {
    this.correrToque = !this.correrToque;
    if (this.correrToque) this.agachado = false;
    this.#atualizarBotoes();
  }

  #atualizarBotoes() {
    this.el.btnAgachar?.setAttribute('aria-pressed', String(this.agachado));
    this.el.btnCorrer?.setAttribute('aria-pressed', String(this.correrToque));
    this.aoPostura();
  }

  #teclado() {
    addEventListener('keydown', (e) => {
      if (e.code === 'Escape' || e.code === 'KeyM') {
        // Com o cursor travado, quase sempre o navegador engole o Esc e quem abre o menu é o
        // "pointerlockchange" (main.js); se o Esc chegar aqui mesmo assim, abre por aqui.
        if (!e.repeat) this.aoMenu();
        return;
      }
      if (!this.ativo) return;
      if (e.code === 'KeyC' && !e.repeat) this.alternarAgachar();
      this.teclas.add(e.code);
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Space'].includes(e.code)) e.preventDefault();
    });
    addEventListener('keyup', (e) => this.teclas.delete(e.code));
    addEventListener('blur', () => this.teclas.clear());
  }

  #mouse() {
    this.canvas.addEventListener('mousedown', (e) => { if (e.button === 0) this.mouseApertado = true; });
    addEventListener('mouseup', () => { this.mouseApertado = false; });
    addEventListener('mousemove', (e) => {
      if (!this.ativo) return;
      // Com o cursor travado, qualquer movimento olha; sem trava, olha arrastando.
      if (document.pointerLockElement === this.canvas || this.mouseApertado) {
        this.olharX += e.movementX * SENS_MOUSE;
        this.olharY += e.movementY * SENS_MOUSE;
      }
    });
  }

  #toque() {
    const { zonaAndar, zonaOlhar, btnCorrer, btnAgachar } = this.el;
    if (!zonaAndar) return;

    zonaAndar.addEventListener('pointerdown', (e) => {
      if (!this.ativo || this.idAndar !== null) return;
      this.idAndar = e.pointerId;
      zonaAndar.setPointerCapture?.(e.pointerId);
      this.origem = { x: e.clientX, y: e.clientY };
      const { analogico } = this.el;
      analogico.style.left = `${e.clientX}px`;
      analogico.style.top = `${e.clientY}px`;
      analogico.hidden = false;
      this.#moverAnalogico(e);
    });
    zonaAndar.addEventListener('pointermove', (e) => { if (e.pointerId === this.idAndar) this.#moverAnalogico(e); });
    const soltarAndar = (e) => { if (e.pointerId === this.idAndar) this.#soltarAnalogico(); };
    zonaAndar.addEventListener('pointerup', soltarAndar);
    zonaAndar.addEventListener('pointercancel', soltarAndar);

    zonaOlhar.addEventListener('pointerdown', (e) => {
      if (!this.ativo || this.idOlhar !== null) return;
      this.idOlhar = e.pointerId;
      zonaOlhar.setPointerCapture?.(e.pointerId);
      this.ultimoToque = { x: e.clientX, y: e.clientY };
    });
    zonaOlhar.addEventListener('pointermove', (e) => {
      if (e.pointerId !== this.idOlhar || !this.ativo) return;
      this.olharX += (e.clientX - this.ultimoToque.x) * SENS_TOQUE;
      this.olharY += (e.clientY - this.ultimoToque.y) * SENS_TOQUE;
      this.ultimoToque = { x: e.clientX, y: e.clientY };
    });
    const soltarOlhar = (e) => { if (e.pointerId === this.idOlhar) this.idOlhar = null; };
    zonaOlhar.addEventListener('pointerup', soltarOlhar);
    zonaOlhar.addEventListener('pointercancel', soltarOlhar);

    btnCorrer.addEventListener('click', () => this.alternarCorrer());
    btnAgachar.addEventListener('click', () => this.alternarAgachar());
  }

  #moverAnalogico(e) {
    let dx = e.clientX - this.origem.x, dy = e.clientY - this.origem.y;
    const comp = Math.hypot(dx, dy);
    if (comp > RAIO_ANALOGICO) { dx *= RAIO_ANALOGICO / comp; dy *= RAIO_ANALOGICO / comp; }
    this.el.pino.style.transform = `translate(${dx}px, ${dy}px)`;
    const fx = dx / RAIO_ANALOGICO, fy = dy / RAIO_ANALOGICO;
    const forca = Math.hypot(fx, fy);
    this.analogico = forca < ZONA_MORTA ? { x: 0, y: 0 } : { x: fx, y: fy };
  }

  #soltarAnalogico() {
    this.idAndar = null;
    this.analogico = { x: 0, y: 0 };
    if (this.el.analogico) this.el.analogico.hidden = true;
    if (this.el.pino) this.el.pino.style.transform = '';
  }
}
