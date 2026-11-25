// Gerador pseudoaleatório com semente (mulberry32).
// Com a mesma semente, servidor e cliente geram exatamente o mesmo mapa.

export function criarAleatorio(semente) {
  let a = semente >>> 0;
  const proximo = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return {
    proximo,
    entre: (min, max) => min + (max - min) * proximo(),
    inteiro: (min, max) => Math.floor(min + (max - min + 1) * proximo()),
    escolher: (lista) => lista[Math.floor(proximo() * lista.length)],
    chance: (p) => proximo() < p,
    embaralhar(lista) {
      for (let i = lista.length - 1; i > 0; i--) {
        const j = Math.floor(proximo() * (i + 1));
        [lista[i], lista[j]] = [lista[j], lista[i]];
      }
      return lista;
    },
  };
}
