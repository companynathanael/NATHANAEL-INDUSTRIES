// Transporte local: liga um cliente a um Servidor que roda na mesma página (modo solo,
// como o "Play Solo" do Roblox Studio).
// Cliente e servidor NUNCA compartilham objetos: toda mensagem é copiada (structuredClone)
// na hora do envio e entregue depois (assíncrona), igual a uma rede de verdade.
// Na etapa de co-op online, um TransporteWebSocket terá exatamente esta interface.

let proximoId = 1;

export function criarConexaoLocal(servidor, { latenciaMs = 0 } = {}) {
  const id = `local-${proximoId++}`;
  const ouvintesCliente = new Set();
  const ouvintesServidor = new Set();
  const ouvintesFechar = new Set();
  let aberta = true;

  const entregar = (ouvintes, tipo, dados) => {
    if (!aberta) return;
    const copia = dados === undefined ? undefined : structuredClone(dados);
    setTimeout(() => {
      if (!aberta) return;
      for (const f of ouvintes) f(tipo, copia);
    }, latenciaMs);
  };

  const ladoServidor = {
    id,
    enviar: (tipo, dados) => entregar(ouvintesCliente, tipo, dados),
    aoReceber: (f) => ouvintesServidor.add(f),
    aoFechar: (f) => ouvintesFechar.add(f),
  };

  const ladoCliente = {
    id,
    enviar: (tipo, dados) => entregar(ouvintesServidor, tipo, dados),
    aoReceber: (f) => ouvintesCliente.add(f),
    fechar() {
      if (!aberta) return;
      aberta = false;
      for (const f of ouvintesFechar) f();
    },
  };

  servidor.conectar(ladoServidor);
  return ladoCliente;
}
