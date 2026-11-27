const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");
const welcome = document.getElementById("welcome");
const apiStatus = document.getElementById("api-status");
const apiStatusText = document.getElementById("api-status-text");

// Auto-resize textarea
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
  sendBtn.disabled = !input.value.trim();
});

// Enter to send
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (input.value.trim()) form.dispatchEvent(new Event("submit"));
  }
});

// Example buttons
document.querySelectorAll(".example-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    input.value = btn.dataset.msg;
    input.dispatchEvent(new Event("input"));
    input.focus();
  });
});

clearBtn.addEventListener("click", () => {
  chat.innerHTML = "";
  chat.appendChild(welcome);
  welcome.style.display = "block";
});

// Health check
async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      apiStatus.classList.add("online");
      apiStatus.classList.remove("offline");
      apiStatusText.textContent = "API online";
    } else {
      throw new Error();
    }
  } catch {
    apiStatus.classList.add("offline");
    apiStatus.classList.remove("online");
    apiStatusText.textContent = "API offline";
  }
}
checkHealth();
setInterval(checkHealth, 30000);

function hideWelcome() {
  if (welcome) welcome.style.display = "none";
}

function appendUserMessage(text) {
  hideWelcome();
  const el = document.createElement("div");
  el.className = "message user";
  el.innerHTML = `
    <div class="avatar">CS</div>
    <div class="bubble">${escapeHtml(text)}</div>
  `;
  chat.appendChild(el);
  scrollToBottom();
}

function appendTyping() {
  const el = document.createElement("div");
  el.className = "message assistant";
  el.id = "typing-indicator";
  el.innerHTML = `
    <div class="avatar">AI</div>
    <div class="bubble">
      <div class="typing"><span></span><span></span><span></span></div>
    </div>
  `;
  chat.appendChild(el);
  scrollToBottom();
}

function removeTyping() {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
}

function appendResponseCard(data) {
  hideWelcome();
  removeTyping();

  const parecer = (data.parecer || "erro").toLowerCase();
  const dados = data.dados_consultados || {};
  const op = data.operacao_creditos || {};

  const labels = {
    sucesso: "✓ Operação realizada",
    recusa: "✕ Operação recusada",
    ambiguidade: "⚠ Ambiguidade detectada",
    erro: "✕ Erro na execução",
  };

  let opHtml = "";
  if (op.solicitada) {
    if (op.realizada) {
      opHtml = `<span class="op-badge ok">+${op.quantidade ?? "?"} créditos incluídos</span>`;
    } else {
      opHtml = `<span class="op-badge fail">Créditos não incluídos${op.motivo_recusa ? ": " + escapeHtml(op.motivo_recusa) : ""}</span>`;
    }
  } else {
    opHtml = `<span class="op-badge skip">Sem solicitação de créditos</span>`;
  }

  const fields = [
    ["Empresa", dados.nome_empresa || (dados.empresa_id ? `ID ${dados.empresa_id}` : null)],
    ["Assinatura", dados.assinatura_id ? `ID ${dados.assinatura_id}` : null],
    ["Plano", dados.plano],
    ["Status", dados.status_assinatura],
    ["Saldo anterior", dados.saldo_anterior != null ? dados.saldo_anterior.toLocaleString("pt-BR") : null],
    ["Saldo atual", dados.saldo_atual != null ? dados.saldo_atual.toLocaleString("pt-BR") : null],
  ].filter(([, v]) => v != null && v !== "");

  const gridHtml = fields.length
    ? `<div class="data-grid">${fields
        .map(
          ([l, v]) =>
            `<div class="data-item"><div class="label">${l}</div><div class="value">${escapeHtml(String(v))}</div></div>`
        )
        .join("")}</div>`
    : "";

  const el = document.createElement("div");
  el.className = "message assistant";
  el.innerHTML = `
    <div class="avatar">AI</div>
    <div class="response-card">
      <div class="card-header ${parecer}">${labels[parecer] || labels.erro}</div>
      <div class="card-body">
        <div class="card-msg">${escapeHtml(data.mensagem || "Sem mensagem.")}</div>
        ${gridHtml}
        <div>${opHtml}</div>
      </div>
    </div>
  `;
  chat.appendChild(el);
  scrollToBottom();
}

function appendError(msg) {
  removeTyping();
  appendResponseCard({
    parecer: "erro",
    mensagem: msg,
    dados_consultados: {},
    operacao_creditos: { solicitada: false, realizada: false },
  });
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chat.scrollTop = chat.scrollHeight;
  });
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  appendUserMessage(text);
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;
  appendTyping();

  try {
    const res = await fetch("/agent/executar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mensagem: text }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Erro HTTP ${res.status}`);
    }

    const data = await res.json();
    appendResponseCard(data);
  } catch (err) {
    appendError(err.message || "Falha na comunicação com o agente.");
  }
});