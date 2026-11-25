// Salvamento — equivalente ao DataStore do Roblox.
// O servidor só conhece esta interface: carregar(chave) e salvar(chave, valor).
//   • SalvamentoMemoria   → testes.
//   • SalvamentoNavegador → modo solo (localStorage do navegador).
//   • (etapa 7) SalvamentoArquivo → servidor online em Node, grava em disco.

export class SalvamentoMemoria {
  constructor() {
    this.dados = new Map();
  }

  async carregar(chave) {
    return this.dados.has(chave) ? structuredClone(this.dados.get(chave)) : null;
  }

  async salvar(chave, valor) {
    this.dados.set(chave, structuredClone(valor));
    return true;
  }
}

export class SalvamentoNavegador {
  constructor(prefixo = 'maskwood:') {
    this.prefixo = prefixo;
  }

  async carregar(chave) {
    try {
      const texto = globalThis.localStorage?.getItem(this.prefixo + chave);
      return texto ? JSON.parse(texto) : null;
    } catch {
      return null; // janela anônima, armazenamento bloqueado ou dado corrompido
    }
  }

  async salvar(chave, valor) {
    try {
      globalThis.localStorage?.setItem(this.prefixo + chave, JSON.stringify(valor));
      return true;
    } catch {
      return false;
    }
  }
}
