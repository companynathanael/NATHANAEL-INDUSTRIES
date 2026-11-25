// Funções matemáticas pequenas usadas em todo o jogo.

export const limitar = (v, min, max) => Math.min(max, Math.max(min, v));

/** Interpolação linear (lerp). */
export const misturar = (a, b, t) => a + (b - a) * t;

/** Curva suave entre `a` e `b` (smoothstep): 0 antes de a, 1 depois de b. */
export function suave(a, b, x) {
  const t = limitar((x - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
}

/** Distância do ponto P ao segmento AB, no plano XZ. */
export function distanciaPontoSegmento(px, pz, ax, az, bx, bz) {
  const abx = bx - ax, abz = bz - az;
  const comp2 = abx * abx + abz * abz;
  const t = comp2 > 0 ? limitar(((px - ax) * abx + (pz - az) * abz) / comp2, 0, 1) : 0;
  return Math.hypot(px - (ax + abx * t), pz - (az + abz * t));
}

/** 75 → "1:15" */
export function formatarTempo(segundos) {
  const s = Math.max(0, Math.ceil(segundos));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export const arredondar = (v, casas = 2) => {
  const f = 10 ** casas;
  return Math.round(v * f) / f;
};
