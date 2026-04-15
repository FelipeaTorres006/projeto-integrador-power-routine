const state = {
  nome: "",
  idade: "",
  peso: "",
  altura: "",
  objetivo: ""
};

function goTo(viewId) {
  const views = document.querySelectorAll(".view");

  views.forEach(function(view) {
    view.classList.remove("active");
  });

  document.querySelector("#" + viewId).classList.add("active");
}

function showToast(msg) {
  const toast = document.querySelector("#toast");
  toast.innerText = msg;
  toast.classList.add("show");

  setTimeout(function() {
    toast.classList.remove("show");
  }, 2000);
}

function calcularIMC(peso, altura) {
  let alturaMetro = altura / 100;
  let imc = peso / (alturaMetro * alturaMetro);
  return imc.toFixed(1);
}

function classificarIMC(imc) {
  if (imc < 18.5) {
    return "Baixo";
  } else if (imc < 25) {
    return "Normal";
  } else if (imc < 30) {
    return "Sobrepeso";
  } else {
    return "Alto";
  }
}

function preencherDashboard() {
  const imc = calcularIMC(Number(state.peso), Number(state.altura));
  const status = classificarIMC(Number(imc));

  document.querySelector("#sb-nome").innerText = state.nome;
  document.querySelector("#d-nome").innerText = state.nome;
  document.querySelector("#d-idade").innerText = state.idade;
  document.querySelector("#d-peso").innerText = state.peso;
  document.querySelector("#d-altura").innerText = state.altura;

  document.querySelector("#info-nome").innerText = state.nome;
  document.querySelector("#info-objetivo").innerText = state.objetivo;
  document.querySelector("#info-imc").innerText = imc;

  document.querySelector("#p-imc").innerText = imc;
  document.querySelector("#p-objetivo").innerText = state.objetivo;
  document.querySelector("#p-status").innerText = status;
  document.querySelector("#p-peso").innerText = state.peso + " kg";
  document.querySelector("#p-altura").innerText = state.altura + " cm";
  document.querySelector("#p-idade").innerText = state.idade + " anos";
}

function gerarPlano() {
  const planoOutput = document.querySelector("#plano-output");

  let cafe = "";
  let almoco = "";
  let jantar = "";

  if (state.objetivo === "Emagrecer") {
    cafe = "Frutas, iogurte e aveia";
    almoco = "Frango grelhado, arroz e salada";
    jantar = "Sopa de legumes com ovo";
  } else if (state.objetivo === "Ganhar massa") {
    cafe = "Ovos, pão integral e vitamina";
    almoco = "Arroz, feijão, carne e batata";
    jantar = "Macarrão com frango";
  } else {
    cafe = "Pão integral e café";
    almoco = "Arroz, feijão, frango e salada";
    jantar = "Omelete com legumes";
  }

  planoOutput.innerHTML = `
    <div class="plano-dia">
      <h3>Plano do dia</h3>
      <p><strong>Café da manhã:</strong> ${cafe}</p>
      <p><strong>Almoço:</strong> ${almoco}</p>
      <p><strong>Jantar:</strong> ${jantar}</p>
    </div>
  `;

  showToast("Plano gerado com sucesso");
}

const loginForm = document.querySelector("#loginForm");
loginForm.addEventListener("submit", function(event) {
  event.preventDefault();

  const email = document.querySelector("#email").value;
  const senha = document.querySelector("#senha").value;

  if (email === "" || senha === "") {
    showToast("Preencha e-mail e senha");
    return;
  }

  goTo("view-form");
});

const infoForm = document.querySelector("#infoForm");
infoForm.addEventListener("submit", function(event) {
  event.preventDefault();

  const nome = document.querySelector("#nome").value;
  const idade = document.querySelector("#idade").value;
  const peso = document.querySelector("#peso").value;
  const altura = document.querySelector("#altura").value;
  const objetivo = document.querySelector("#objetivo").value;

  if (nome === "" || idade === "" || peso === "" || altura === "" || objetivo === "") {
    showToast("Preencha todos os campos");
    return;
  }

  state.nome = nome;
  state.idade = idade;
  state.peso = peso;
  state.altura = altura;
  state.objetivo = objetivo;

  preencherDashboard();
  goTo("view-dash");
});

const btnSair = document.querySelector("#btnSair");
btnSair.addEventListener("click", function() {
  goTo("view-login");
  showToast("Você saiu do sistema");
});

const navItems = document.querySelectorAll(".nav-item");
const tabs = document.querySelectorAll(".tab-content");

navItems.forEach(function(botao) {
  botao.addEventListener("click", function() {
    const tabId = botao.getAttribute("data-tab");

    navItems.forEach(function(item) {
      item.classList.remove("active");
    });

    tabs.forEach(function(tab) {
      tab.classList.remove("active");
    });

    botao.classList.add("active");
    document.querySelector("#" + tabId).classList.add("active");
  });
});

const btnGerarPlano = document.querySelector("#btnGerarPlano");
btnGerarPlano.addEventListener("click", function() {
  gerarPlano();
});