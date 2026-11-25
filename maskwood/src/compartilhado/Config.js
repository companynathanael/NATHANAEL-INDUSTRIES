// Config — números de balanceamento do MASKWOOD: 100 Noites.
// Equivalente ao ModuleScript "Config" do Roblox: todo ajuste de jogo fica aqui,
// e tanto o servidor quanto o cliente leem daqui (pasta compartilhado/ = ReplicatedStorage).

function congelar(obj) {
  for (const valor of Object.values(obj)) {
    if (valor && typeof valor === 'object') congelar(valor);
  }
  return Object.freeze(obj);
}

export const Config = congelar({
  servidor: {
    TICK_HZ: 20,            // passos de simulação por segundo
    ESTADO_HZ: 10,          // quantas vezes por segundo o estado vai para os clientes
    MAX_JOGADORES: 4,
    DT_MAXIMO: 0.5,         // s — se a aba travar, o servidor não dá um "salto" gigante
    PAUSA_SOLO: true,       // jogando sozinho, abrir o menu pausa o jogo (no co-op, não)
    PERMITIR_DEBUG: true,   // botões de teste do protótipo. DESLIGAR no servidor online.
  },

  ciclo: {
    DURACAO_DIA: 240,       // s (~4 min): hora de coletar
    DURACAO_NOITE: 300,     // s (~5 min): hora de sobreviver
    NOITE_FINAL: 100,
    ENTARDECER_S: 30,       // últimos segundos do dia em que o céu escurece
    AMANHECER_S: 25,        // últimos segundos da noite em que o céu clareia
    ACELERACOES_DEBUG: [1, 10, 30],
  },

  chama: {
    OLEO_MAX: 100,
    OLEO_INICIAL: 100,
    CONSUMO_DIA: 0.12,      // óleo por segundo (≈ 29 num dia inteiro)
    CONSUMO_NOITE: 0.22,    // óleo por segundo (≈ 66 numa noite inteira)
    OLEO_BAIXO: 20,         // abaixo disso: aviso "a Chama está fraca"
    RAIO_MAX: 24,           // m — raio seguro com o tanque cheio
    RAIO_MIN: 7,            // m — raio seguro quando o óleo está quase no fim
    OLEO_DEBUG: 25,         // quanto o botão de teste põe na Chama
  },

  jogador: {
    VEL_ANDAR: 4.2,         // m/s
    VEL_CORRER: 7.2,
    VEL_AGACHADO: 1.9,
    RAIO: 0.4,              // raio do corpo (colisão)
    ALTURA_OLHOS: 1.62,
    ALTURA_AGACHADO: 1.0,
    ENVIO_HZ: 10,           // posições enviadas ao servidor por segundo
    TOLERANCIA_VEL: 1.4,    // folga do anti-teleporte (x velocidade de corrida)
    FOLGA_M: 0.75,          // metros extras aceitos por mensagem (atraso da rede)
    RAIO_NASCER: 5,         // distância da Chama onde os jogadores aparecem
  },

  mapa: {
    SEMENTE: 1987,          // o ano em que Pedra Alta sumiu
    RAIO_MUNDO: 150,        // limite andável
    RAIO_FLORESTA_FIM: 168, // árvores vão um pouco além do limite (parede visual)
    RAIO_CLAREIRA: 30,
    RAIO_VILA_MIN: 12,
    RAIO_VILA_MAX: 22,
    NUM_CASAS: 6,
    NUM_TRILHAS: 4,
    LARGURA_TRILHA: 2.4,
    NUM_ARVORES: 2400,
    DIST_MIN_ARVORES: 2.7,
    NUM_MASCARAS_DECORATIVAS: 18,
    NUM_PEDRAS: 70,
    NUM_CAIXOTES: 7,
    DIST_TORRE: 128,        // torre de rádio quebrada (objetivo final, fora do protótipo)
    CELULA_GRADE: 4,        // m — grade espacial dos colisores
  },
});
