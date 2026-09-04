// RNF-003: Compatibilidade dinâmica entre ambiente local e deploy no GitHub Pages[cite: 1]
const API_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
  ? "http://localhost:8000/api"
  : "https://seu-backend-producao.onrender.com/api";

const state = {
  usuario_id: null,
  nome: "",
  email: "",
  sexo: "",
  data_nascimento: "",
  altura_cm: 0,
  peso_kg: 0,
  objetivo: "",
  nivel_atividade: "",
  tmb_kcal: 0,
  get_kcal: 0,
  meta_kcal: 0,
  macros_meta: { proteina_g: 0, carboidrato_g: 0, gordura_g: 0 },
  historico: []
};

// Instâncias de gráficos do Chart.js (RF-003 e RF-005)[cite: 1]
let chartMacrosInstance = null;
let chartCaloriasInstance = null;
let chartPesoInstance = null;

// RF-005: Sugestões e Substituições Alimentares (Low Carb / Saudáveis)[cite: 1]
const catalogoSubstituicoes = [
  {
    refeicao: "Café da Manhã",
    convencional: "Pão francês com margarina e café com açúcar",
    substituicao: "Ovos mexidos com espinafre e café sem açúcar",
    beneficio: "Estabiliza o índice glicêmico matinal e aumenta a saciedade."
  },
  {
    refeicao: "Almoço",
    convencional: "Arroz branco (150g), feijão e carne frita",
    substituicao: "Arroz de couve-flor, filé de frango grelhado e salada verde",
    beneficio: "Aporte de fibras com baixa densidade calórica."
  },
  {
    refeicao: "Lanche da Tarde",
    convencional: "Biscoitos recheados ou salgados assados",
    substituicao: "Mix de castanhas e nozes (30g) ou iogurte natural integral",
    beneficio: "Gorduras monoinsaturadas para equilíbrio hormonal."
  },
  {
    refeicao: "Jantar",
    convencional: "Macarrão tradicional com molho industrializado",
    substituicao: "Espaguete de abobrinha com molho de tomate caseiro e patinho moído",
    beneficio: "Digestão leve sem excesso de carboidratos rápidos à noite."
  }
];

// Navegação SPA entre Views
function goTo(viewId) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  const target = document.querySelector("#" + viewId);
  if (target) target.classList.add("active");
}

// Toast de Notificações
function showToast(msg) {
  const toast = document.querySelector("#toast");
  if (!toast) return;
  toast.innerText = typeof msg === "object" ? JSON.stringify(msg) : String(msg);
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3500);
}

// RN-002: Classificação em 3 estados com base no limiar estrito de ±8%[cite: 1]
function classificarMargem8Pct(consumo, meta, statusIaBackend = null) {
  if (statusIaBackend === "dentro_meta") {
    return { status: "Dentro da Meta (±8%)", classe: "status-verde", badge: "tag-verde" };
  } else if (statusIaBackend === "abaixo_meta") {
    return { status: "Abaixo da Meta (< -8%)", classe: "status-azul", badge: "tag-azul" };
  } else if (statusIaBackend === "acima_meta") {
    return { status: "Acima da Meta (> +8%)", classe: "status-vermelho", badge: "tag-vermelho" };
  }

  if (!meta || meta <= 0) return { status: "Indefinido", classe: "status-cinza", badge: "tag-cinza" };
  const aderencia = (consumo / meta) * 100;

  if (aderencia >= 92 && aderencia <= 108) {
    return { status: "Dentro da Meta (±8%)", classe: "status-verde", badge: "tag-verde" };
  } else if (aderencia < 92) {
    return { status: "Abaixo da Meta (< -8%)", classe: "status-azul", badge: "tag-azul" };
  } else {
    return { status: "Acima da Meta (> +8%)", classe: "status-vermelho", badge: "tag-vermelho" };
  }
}

// RF-003: Renderização dos Gráficos Interativos (Macronutrientes e Calorias)[cite: 1]
function renderizarGraficosPainel() {
  const ctxMacros = document.querySelector("#chartMacros")?.getContext("2d");
  const ctxCalorias = document.querySelector("#chartCalorias")?.getContext("2d");

  // Gráfico de Rosca de Macronutrientes (com trava de proporção mobile)
  if (ctxMacros && typeof Chart !== "undefined") {
    if (chartMacrosInstance) chartMacrosInstance.destroy();
    chartMacrosInstance = new Chart(ctxMacros, {
      type: "doughnut",
      data: {
        labels: ["Proteínas (g)", "Carboidratos (g)", "Gorduras (g)"],
        datasets: [{
          data: [
            state.macros_meta.proteina_g || 0,
            state.macros_meta.carboidrato_g || 0,
            state.macros_meta.gordura_g || 0
          ],
          backgroundColor: ["#39FF14", "#2979ff", "#ffd000"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: window.innerWidth < 768 ? 1.1 : 1.5,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#f0f0f0", boxWidth: 12, font: { size: 11 } }
          }
        }
      }
    });
  }

  // Gráfico de Barras: Meta Diária vs Consumo Atual
  if (ctxCalorias && typeof Chart !== "undefined") {
    const ultimo = state.historico[0];
    const consumoRecente = ultimo ? ultimo.consumido_kcal : 0;
    const corConsumo = consumoRecente > state.meta_kcal * 1.08 ? "#ff3838" : "#39FF14";

    if (chartCaloriasInstance) chartCaloriasInstance.destroy();
    chartCaloriasInstance = new Chart(ctxCalorias, {
      type: "bar",
      data: {
        labels: ["Meta Calórica", "Consumo Recente"],
        datasets: [{
          label: "Calorias (kcal)",
          data: [Math.round(state.meta_kcal), Math.round(consumoRecente)],
          backgroundColor: ["#2e2e2e", corConsumo]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: window.innerWidth < 768 ? 1.2 : 1.6,
        scales: {
          y: { beginAtZero: true, ticks: { color: "#888" } },
          x: { ticks: { color: "#888" } }
        },
        plugins: {
          legend: { labels: { color: "#f0f0f0" } }
        }
      }
    });
  }
}

// RF-005: Gráfico de Evolução de Peso Corporal (sem trepidação de layout)[cite: 1]
function renderizarGraficoEvolucaoPeso() {
  const ctxPeso = document.querySelector("#chartPeso")?.getContext("2d");
  if (!ctxPeso || typeof Chart === "undefined" || state.historico.length === 0) return;

  const ordenados = [...state.historico].reverse();
  const labels = ordenados.map(r => r.data);
  const dataPesos = ordenados.map(r => r.peso_kg || state.peso_kg);

  if (chartPesoInstance) chartPesoInstance.destroy();
  chartPesoInstance = new Chart(ctxPeso, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Evolução do Peso (kg)",
        data: dataPesos,
        borderColor: "#39FF14",
        backgroundColor: "rgba(57, 255, 20, 0.15)",
        fill: true,
        tension: 0.3,
        pointBackgroundColor: "#39FF14"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 250 },
      scales: {
        y: { ticks: { color: "#888" } },
        x: { ticks: { color: "#888" } }
      },
      plugins: {
        legend: { labels: { color: "#f0f0f0" } }
      }
    }
  });
}

// RF-005: Renderização do Plano Alimentar e Substituições[cite: 1]
function renderizarSubstituicoes() {
  const container = document.querySelector("#substituicoes-output");
  if (!container) return;

  container.innerHTML = catalogoSubstituicoes.map(s => `
    <div class="sub-card">
      <h4><i class="fa-solid fa-utensils"></i> ${s.refeicao}</h4>
      <p><strong>Convencional:</strong> ${s.convencional}</p>
      <p class="sub-destaque"><strong>Opção Low Carb:</strong> ${s.substituicao}</p>
      <small><em>Benefício: ${s.beneficio}</em></small>
    </div>
  `).join("");
}

// Atualização de Valores no Painel Geral
function atualizarDashboard() {
  const setTxt = (id, val) => {
    const el = document.querySelector(id);
    if (el) el.innerText = val;
  };

  setTxt("#sb-nome", state.nome);
  setTxt("#d-nome", state.nome);
  setTxt("#d-tmb", Math.round(state.tmb_kcal));
  setTxt("#d-get", Math.round(state.get_kcal));
  setTxt("#d-meta", Math.round(state.meta_kcal));

  setTxt("#info-prot", `${state.macros_meta.proteina_g} g`);
  setTxt("#info-carb", `${state.macros_meta.carboidrato_g} g`);
  setTxt("#info-gord", `${state.macros_meta.gordura_g} g`);

  renderizarGraficosPainel();
}

// Carregamento de Registros e Status via API
async function carregarResumoDiario() {
  if (!state.usuario_id) return;

  try {
    const res = await fetch(`${API_URL}/diario/${state.usuario_id}`);
    if (!res.ok) return;

    const data = await res.json();
    state.historico = data.registros || [];
    const container = document.querySelector("#historico-output");

    if (state.historico.length === 0) {
      if (container) {
        container.innerHTML = `<div class="empty-state"><p>Nenhum consumo registrado ainda.</p></div>`;
      }
      return;
    }

    const ultimo = state.historico[0];
    const avaliacao = classificarMargem8Pct(ultimo.consumido_kcal, ultimo.meta_kcal, ultimo.status_ia);

    const elConsumo = document.querySelector("#p-consumo");
    const elAderencia = document.querySelector("#p-aderencia");
    const cardStatus = document.querySelector("#card-status-ia");
    const elStatus = document.querySelector("#p-status");

    if (elConsumo) elConsumo.innerText = Math.round(ultimo.consumido_kcal);
    if (elAderencia) elAderencia.innerText = `${ultimo.aderencia_percentual}%`;
    if (cardStatus) cardStatus.className = `stat-card ${avaliacao.classe}`;
    if (elStatus) elStatus.innerText = avaliacao.status;

    if (container) {
      container.innerHTML = state.historico.map(r => {
        const tag = classificarMargem8Pct(r.consumido_kcal, r.meta_kcal, r.status_ia);
        return `
          <div class="plano-dia">
            <div>
              <h4>${r.data} • <strong>${r.consumido_kcal} kcal</strong></h4>
              <span>Meta: ${r.meta_kcal} kcal (Dif: ${r.diferenca_kcal} kcal) | Aderência: ${r.aderencia_percentual}%</span>
            </div>
            <span class="tag-status ${tag.badge}">${tag.status}</span>
          </div>
        `;
      }).join("");
    }

    renderizarGraficoEvolucaoPeso();
    renderizarGraficosPainel();

  } catch (err) {
    console.error("Erro ao carregar diário:", err);
  }
}

// RF-004: Exportação em PDF com jsPDF[cite: 1]
document.querySelector("#btnExportarPdf")?.addEventListener("click", function() {
  if (!window.jspdf) {
    showToast("Biblioteca jsPDF indisponível no momento.");
    return;
  }
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF();

  doc.setFontSize(18);
  doc.text("Power Routine — Relatório de Nutrição", 14, 20);

  doc.setFontSize(12);
  doc.text(`Usuário: ${state.nome} (${state.email})`, 14, 30);
  doc.text(`TMB: ${Math.round(state.tmb_kcal)} kcal | GET: ${Math.round(state.get_kcal)} kcal | Meta: ${Math.round(state.meta_kcal)} kcal`, 14, 38);
  doc.text(`Macronutrientes: Proteínas: ${state.macros_meta.proteina_g}g | Carboidratos: ${state.macros_meta.carboidrato_g}g | Gorduras: ${state.macros_meta.gordura_g}g`, 14, 46);

  doc.line(14, 52, 196, 52);
  doc.text("Histórico de Consumo Registrado (Tolerância ±8%):", 14, 60);

  let posY = 70;
  state.historico.slice(0, 15).forEach(r => {
    const texto = `${r.data} - Ingestão: ${r.consumido_kcal} kcal | Meta: ${r.meta_kcal} kcal | Aderência: ${r.aderencia_percentual}%`;
    doc.text(texto, 14, posY);
    posY += 8;
  });

  doc.save(`relatorio_${state.nome.toLowerCase().replace(/\s+/g, "_")}.pdf`);
  showToast("Relatório PDF baixado com sucesso!");
});

// Tratamento unificado de erros (evita [object Object])
async function extrairErro(res) {
  try {
    const err = await res.json();
    if (typeof err.detail === "string") return err.detail;
    if (Array.isArray(err.detail)) {
      return err.detail.map(d => `${d.loc ? d.loc.slice(-1)[0] : "Campo"}: ${d.msg}`).join(" | ");
    }
    if (typeof err.detail === "object" && err.detail !== null) return JSON.stringify(err.detail);
    return `Erro na requisição (${res.status})`;
  } catch {
    return `Falha no servidor (${res.status})`;
  }
}

// Eventos de Autenticação / Troca de Tela
document.querySelector("#loginForm")?.addEventListener("submit", function(e) {
  e.preventDefault();
  goTo("view-form");
});

document.querySelector("#link-cadastro")?.addEventListener("click", function(e) {
  e.preventDefault();
  goTo("view-form");
});

// Evento: Submissão de Biometria (RF-001 / RN-001)[cite: 1]
document.querySelector("#infoForm")?.addEventListener("submit", async function(e) {
  e.preventDefault();
  const btn = document.querySelector("#btnSalvarPerfil");
  btn.disabled = true;
  btn.innerText = "Processando cálculos...";

  const nome = document.querySelector("#nome").value;
  const email = document.querySelector("#email").value;
  const sexo = document.querySelector("#sexo").value;
  const data_nascimento = document.querySelector("#data_nascimento").value;
  const altura_cm = parseFloat(document.querySelector("#altura").value);
  const peso_kg = parseFloat(document.querySelector("#peso").value);
  const nivel_atividade = document.querySelector("#nivel_atividade").value;
  const objetivo = document.querySelector("#objetivo").value;

  try {
    // 1. Cadastrar Usuário
    const resUsuario = await fetch(`${API_URL}/usuarios`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome, email, sexo, data_nascimento, altura_cm })
    });

    let usuarioData;
    if (!resUsuario.ok) {
      throw new Error(await extrairErro(resUsuario));
    } else {
      usuarioData = await resUsuario.json();
    }

    state.usuario_id = usuarioData.id;
    state.nome = usuarioData.nome;
    state.email = usuarioData.email;
    state.peso_kg = peso_kg;

    // 2. Calcular Perfil via Harris-Benedict[cite: 1]
    const payloadPerfil = {
      usuario_id: state.usuario_id,
      peso_kg: peso_kg,
      peso_meta_kg: null,
      nivel_atividade: nivel_atividade,
      objetivo: objetivo
    };

    const resPerfil = await fetch(`${API_URL}/perfil/calcular`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadPerfil)
    });

    if (!resPerfil.ok) {
      throw new Error(await extrairErro(resPerfil));
    }

    const perfilData = await resPerfil.json();

    state.tmb_kcal = perfilData.tmb_kcal;
    state.get_kcal = perfilData.get_kcal;
    state.meta_kcal = perfilData.meta_kcal;
    state.macros_meta = perfilData.macros || { proteina_g: 0, carboidrato_g: 0, gordura_g: 0 };

    atualizarDashboard();

    const campoDataDiario = document.querySelector("#diario-data");
    if (campoDataDiario) {
      campoDataDiario.value = new Date().toISOString().split("T")[0];
    }

    goTo("view-dash");
    showToast("Perfil e metas calculados com sucesso!");

  } catch (error) {
    showToast(error.message);
  } finally {
    btn.disabled = false;
    btn.innerText = "Calcular Perfil e Entrar";
  }
});

// Evento: Submissão do Registro Diário (POST /api/diario/registro)
document.querySelector("#diarioForm")?.addEventListener("submit", async function(e) {
  e.preventDefault();

  if (!state.usuario_id) {
    showToast("Nenhum usuário ativo.");
    return;
  }

  const payloadDiario = {
    usuario_id: state.usuario_id,
    data: document.querySelector("#diario-data").value,
    peso_kg: parseFloat(document.querySelector("#diario-peso").value),
    calorias_kcal: parseFloat(document.querySelector("#diario-calorias").value),
    proteina_g: parseFloat(document.querySelector("#diario-prot").value),
    carboidrato_g: parseFloat(document.querySelector("#diario-carb").value),
    gordura_g: parseFloat(document.querySelector("#diario-gord").value),
    observacoes: null
  };

  try {
    const res = await fetch(`${API_URL}/diario/registro`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadDiario)
    });

    if (!res.ok) {
      throw new Error(await extrairErro(res));
    }

    showToast("Consumo diário registrado!");
    await carregarResumoDiario();

    // Redireciona para a aba de progresso
    document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
    document.querySelector('[data-tab="tab-progresso"]')?.classList.add("active");
    document.querySelector("#tab-progresso")?.classList.add("active");

  } catch (err) {
    showToast(err.message);
  }
});

// Navegação entre Abas do Dashboard
document.querySelectorAll(".nav-item").forEach(botao => {
  botao.addEventListener("click", function() {
    const tabId = this.getAttribute("data-tab");

    document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));

    this.classList.add("active");
    document.querySelector("#" + tabId)?.classList.add("active");

    if (tabId === "tab-progresso" || tabId === "tab-inicio") {
      carregarResumoDiario();
    }
    if (tabId === "tab-evolucao") {
      renderizarGraficoEvolucaoPeso();
    }
    if (tabId === "tab-substituicoes") {
      renderizarSubstituicoes();
    }
  });
});

// Sair do Sistema
document.querySelector("#btnSair")?.addEventListener("click", function() {
  goTo("view-login");
  showToast("Sessão finalizada");
});
