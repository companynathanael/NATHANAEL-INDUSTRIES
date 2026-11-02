/* Bezalel — aparência com dados de demonstração (sem back-end) */
(() => {
  const $ = (s) => document.querySelector(s);
  const ic = (n, c = "sm") => `<svg class="ic ${c}"><use href="#i-${n}"/></svg>`;

  const ETAPAS = ["Definição", "Montagem", "Prova de fogo", "Liberada"];
  const IAS = [
    { id: "horacio", nome: "Horácio", versao: "HoV 1.1", cat: "Auxiliar", etapa: 1,
      proposito: "Assistente pessoal do Sr. Nathanael: auxilia, interage e executa tarefas autorizadas.",
      personalidade: "Cordial, direto e discreto. Sempre confirma antes de agir.",
      regras: ["Só executa tarefas autorizadas pelo Sr. Nathanael", "Registra toda ação no Asafe", "Nunca compartilha dados pessoais"],
      permissoes: ["mensagens:enviar", "mensagens:ler", "dados:ler", "dados:escrever", "agentes:ler"],
      habilidades: ["Agenda e lembretes", "Resumo de mensagens", "Pesquisa rápida"] },
    { id: "miqueias", nome: "Miquéias", versao: "JpG 1.0", cat: "Auxiliar", etapa: 0,
      proposito: "Tarefista, calculista e trading: execução de tarefas, cálculos e análises.",
      personalidade: "Analítico, preciso e objetivo. Mostra os números antes da opinião.",
      regras: ["Nenhuma operação financeira sem aprovação", "Explica cada cálculo", "Alerta sobre riscos"],
      permissoes: ["mensagens:enviar", "mensagens:ler", "dados:ler", "dados:escrever"],
      habilidades: ["Acompanhar ação", "Calculadora financeira", "Relatório de mercado"] },
  ];

  /* ---------- splash ---------- */
  const msgs = ["acendendo a oficina", "aquecendo a bigorna", "carregando receitas de IAs", "pronto"];
  let i = 0;
  const tick = setInterval(() => {
    i++;
    $("#splash-bar").style.width = `${(i / msgs.length) * 100}%`;
    $("#splash-status").textContent = msgs[Math.min(i, msgs.length - 1)];
    if (i >= msgs.length) {
      clearInterval(tick);
      $("#splash").classList.add("ready");
      setTimeout(() => { $("#splash").classList.add("done"); setTimeout(() => $("#splash").remove(), 800); }, 450);
    }
  }, 380);

  /* ---------- abas ---------- */
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${t.dataset.view}`));
  }));
  setInterval(() => ($("#clock").textContent = new Date().toLocaleTimeString("pt-BR")), 1000);

  const etapas = (n) => `<div class="etapas">${ETAPAS.map((_, k) => `<i class="${k <= n ? "on" : ""}"></i>`).join("")}</div>`;
  const tagEtapa = (n) => `<span class="tag ${n === 3 ? "solid" : ""}">${ETAPAS[n]}</span>`;

  /* ---------- painel ---------- */
  $("#kpis").innerHTML = [
    ["Em construção", 2, "IAs"], ["Ativas", 0, "IAs"], ["Próximas versões", 2, "planejadas"], ["Aposentadas", 0, "IAs"],
  ].map(([l, v, d]) => `<div class="kpi glass"><div class="k-label">${l}</div><div class="k-val">${v}<small>${d}</small></div></div>`).join("");
  $("#alertas").innerHTML = [
    "Horácio aguardando habilidades fundidas pela Fornalha",
    "Miquéias em definição: regras de trading pendentes de aprovação",
    "Fornalha e Gather ainda em produção: montagem limitada",
  ].map((t) => `<li>${t}</li>`).join("");
  $("#proximas").innerHTML = `<tr><th>IA</th><th>Atual</th><th>Próxima</th></tr>` +
    `<tr><td><b>Horácio</b></td><td class="mono">HoV 1.1</td><td class="mono">HoV 1.2</td></tr>` +
    `<tr><td><b>Miquéias</b></td><td class="mono">JpG 1.0</td><td class="mono">JpG 1.1</td></tr>`;

  /* ---------- bigorna ---------- */
  $("#kanban").innerHTML = ETAPAS.map((nome, k) => {
    const itens = IAS.filter((a) => a.etapa === k);
    return `<div class="col glass"><div class="col-head">${nome}<span class="count">${itens.length}</span></div>
      ${itens.length ? itens.map((a) => `<div class="srv glass-2">
        <div class="srv-head"><span class="avatar red">${a.nome[0]}</span><div class="t"><b>${a.nome}</b><span>${a.versao} · ${a.cat}</span></div></div>
        ${etapas(a.etapa)}</div>`).join("") : `<div class="empty muted" style="text-align:center">vazio</div>`}
    </div>`;
  }).join("");

  /* ---------- definição ---------- */
  const ficha = (a) => {
    $("#def-nome").textContent = `${a.nome} · ${a.versao}`;
    $("#ficha").innerHTML = `
      <div class="card glass full"><div class="card-title">Propósito ${tagEtapa(a.etapa)}</div><p style="color:var(--text-2);line-height:1.6">${a.proposito}</p></div>
      <div class="card glass"><div class="card-title">Personalidade</div><p style="color:var(--text-2);line-height:1.6">${a.personalidade}</p></div>
      <div class="card glass"><div class="card-title">Regras</div><ul class="lista">${a.regras.map((r) => `<li>${r}</li>`).join("")}</ul></div>
      <div class="card glass"><div class="card-title">Permissões <span class="tag dim">do Asafe</span></div><div style="display:flex;flex-wrap:wrap;gap:6px">${a.permissoes.map((p) => `<span class="chip">${ic("shield", "xs")}${p}</span>`).join("")}</div></div>
      <div class="card glass"><div class="card-title">Habilidades <span class="tag dim">da Fornalha</span></div><div style="display:flex;flex-wrap:wrap;gap:6px">${a.habilidades.map((h) => `<span class="chip red">${ic("anvil", "xs")}${h}</span>`).join("")}</div></div>`;
    document.querySelectorAll("#def-sel .seg").forEach((b) => b.classList.toggle("active", b.dataset.id === a.id));
  };
  $("#def-sel").innerHTML = IAS.map((a) => `<button class="seg" data-id="${a.id}">${a.nome}</button>`).join("");
  $("#def-sel").addEventListener("click", (e) => { const b = e.target.closest(".seg"); if (b) ficha(IAS.find((a) => a.id === b.dataset.id)); });
  ficha(IAS[0]);

  /* ---------- catálogo ---------- */
  $("#catalogo").innerHTML = IAS.map((a) => `<div class="srv glass">
    <div class="srv-head"><span class="avatar lg red">${a.nome[0]}</span><div class="t"><b>${a.nome}</b><span>${a.proposito}</span></div></div>
    <dl class="kv"><dt>Versão</dt><dd class="mono">${a.versao}</dd><dt>Categoria</dt><dd>${a.cat}</dd><dt>Status</dt><dd>Em construção</dd></dl>
    ${etapas(a.etapa)}</div>`).join("");

  /* ---------- versões ---------- */
  $("#timeline").innerHTML = [
    ["hoje", "Horácio HoV 1.1 entrou em montagem", ""],
    ["hoje", "Miquéias JpG 1.0 em definição", ""],
    ["futuro", "Horácio HoV 1.2 (planejada)", "dim"],
    ["—", "Nenhuma IA aposentada", "dim"],
  ].map(([q, t, c]) => `<div class="tl"><span class="dotv ${c}"></span><div><b>${t}</b><div class="muted mono" style="font-size:11px">${q}</div></div></div>`).join("");
  $("#versoes").innerHTML = `<tr><th>IA</th><th>Versão</th><th>Status</th></tr>` +
    `<tr><td><b>Horácio</b></td><td class="mono">HoV 1.1</td><td>${tagEtapa(1)}</td></tr>` +
    `<tr><td><b>Horácio</b></td><td class="mono">HoV 1.2</td><td><span class="tag dim">planejada</span></td></tr>` +
    `<tr><td><b>Miquéias</b></td><td class="mono">JpG 1.0</td><td>${tagEtapa(0)}</td></tr>`;

  /* ---------- submotores ---------- */
  $("#subs").innerHTML = [
    ["Baluarte", "Continuidade", "Nenhuma IA em construção se perde: salva o progresso e retoma a criação."],
    ["Baú", "Memória", "Guarda a receita de cada IA criada e aprende com as criações anteriores."],
    ["Bússola", "Autonomia", "Propõe melhorias e novas versões das IAs sem esperar pedido."],
  ].map(([n, p, d]) => `<div class="srv glass soon">
    <div class="srv-head"><span class="avatar lg">${n[0]}</span><div class="t"><b>${n}</b><span>${p}</span></div><span class="tag dim">em breve</span></div>
    <p style="color:var(--text-2);font-size:13px;line-height:1.6">${d}</p></div>`).join("");
})();
