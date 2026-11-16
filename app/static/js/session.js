// Cronômetro da sessão AWS (Requirement 12.4 e 12.5).
//
// O servidor é a fonte da verdade: `GET /api/session` a cada 60 s. Entre as
// sincronizações o tempo restante é contado localmente a cada segundo. Com 600 s
// ou menos aparece um aviso; ao expirar (status do servidor ou resposta 401
// SESSION_EXPIRED de qualquer rota) as ações Validar, Deploy e Teardown ficam
// bloqueadas e a tela mostra o comando de renovação com botão de copiar.

import { api } from "./api.js";
import { el, replaceContent } from "./dom.js";

export const REFRESH_COMMAND = "python start.py --refresh";
export const SYNC_INTERVAL_MS = 60000;
export const EXPIRING_THRESHOLD_S = 600;
export const EXPIRED_REASON =
  "Sessão AWS expirada. Esta ação está bloqueada até você renovar o login e executar o comando de renovação.";

let secondsAtSync = 0;
let syncedAt = 0;
let known = false; // houve ao menos uma resposta do servidor
let forcedExpired = false; // 401 SESSION_EXPIRED visto antes da próxima sincronização
let timerView = null;
let bannerView = null;
let tickHandle = null;
let syncHandle = null;
let lastStatus = null;
const listeners = new Set();
const guarded = new Set();

export function formatRemaining(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  const two = (n) => String(n).padStart(2, "0");
  return hours > 0 ? `${hours}:${two(minutes)}:${two(seconds)}` : `${two(minutes)}:${two(seconds)}`;
}

export function secondsRemaining(now = Date.now()) {
  if (forcedExpired) return 0;
  if (!known) return null;
  return Math.max(0, secondsAtSync - Math.floor((now - syncedAt) / 1000));
}

/** `unknown` até a primeira resposta do servidor; depois `valid`, `expiring` ou `expired`. */
export function sessionStatus(now = Date.now()) {
  const remaining = secondsRemaining(now);
  if (remaining === null) return "unknown";
  if (remaining <= 0) return "expired";
  return remaining <= EXPIRING_THRESHOLD_S ? "expiring" : "valid";
}

export const isSessionExpired = () => sessionStatus() === "expired";

/** Aplica uma resposta de `GET /api/session`. */
export function applyServerState(data) {
  const remaining = Number(data && data.seconds_remaining);
  secondsAtSync = Number.isFinite(remaining) ? Math.max(0, Math.floor(remaining)) : 0;
  if (data && data.status === "expired") secondsAtSync = 0;
  syncedAt = Date.now();
  known = true;
  forcedExpired = false;
  update();
}

/** Registra que uma rota respondeu 401 SESSION_EXPIRED. */
export function reportApiError(err) {
  if (err && err.code === "SESSION_EXPIRED") {
    forcedExpired = true;
    update();
    return true;
  }
  return false;
}

export function onSessionChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Bloqueia o botão enquanto a sessão estiver expirada. Chame `button.disabled =
 * isSessionExpired()` ao reabilitar depois de uma operação.
 */
export function guardAction(button) {
  guarded.add(button);
  applyGuard(button);
  return button;
}

/** Remove os botões registrados (chamado a cada troca de rota). */
export function resetGuards() {
  guarded.clear();
}

function applyGuard(button) {
  const expired = isSessionExpired();
  if (expired) {
    button.disabled = true;
    button.setAttribute("title", EXPIRED_REASON);
  } else if (button.getAttribute("title") === EXPIRED_REASON) {
    button.disabled = false;
    button.setAttribute("title", "");
  }
}

async function copyCommand(button) {
  try {
    await navigator.clipboard.writeText(REFRESH_COMMAND);
    button.textContent = "Copiado";
  } catch (err) {
    button.textContent = "Selecione e copie o comando";
  }
  setTimeout(() => {
    button.textContent = "Copiar comando";
  }, 3000);
}

function expiredBanner() {
  const copy = el("button", { type: "button", class: "btn" }, "Copiar comando");
  copy.addEventListener("click", () => copyCommand(copy));
  return el(
    "div",
    { class: "banner banner--error", role: "alert" },
    el("div", { class: "banner__title" }, "Sessão AWS expirada"),
    el(
      "p",
      null,
      "Validar, Deploy e Teardown estão bloqueados porque as credenciais temporárias expiraram. " +
        "O conteúdo dos labs e a navegação continuam disponíveis. Renove o login no host e execute:"
    ),
    el("p", null, el("code", { class: "session-command" }, REFRESH_COMMAND), " ", copy)
  );
}

function expiringBanner(remaining) {
  return el(
    "div",
    { class: "banner banner--warning" },
    el("div", { class: "banner__title" }, "\u26A0 Sessão AWS expirando"),
    el(
      "div",
      null,
      `Restam ${formatRemaining(remaining)}. Renove o login no host com \`${REFRESH_COMMAND}\` antes de perder o trabalho.`
    )
  );
}

function update() {
  const status = sessionStatus();
  const remaining = secondsRemaining();
  if (timerView) {
    const label =
      status === "unknown"
        ? "Sessão AWS: verificando..."
        : status === "expired"
          ? "Sessão AWS: expirada"
          : `Sessão AWS: ${formatRemaining(remaining)}${status === "expiring" ? " (expirando)" : ""}`;
    timerView.className = `session-timer session-timer--${status}`;
    timerView.textContent = label;
  }
  if (status !== lastStatus) {
    // O banner só é refeito quando o status muda, para não roubar o foco do botão de copiar.
    lastStatus = status;
    if (bannerView) {
      if (status === "expired") replaceContent(bannerView, expiredBanner());
      else if (status === "expiring") replaceContent(bannerView, expiringBanner(remaining));
      else replaceContent(bannerView);
      bannerView.hidden = status !== "expired" && status !== "expiring";
    }
    for (const button of guarded) applyGuard(button);
    for (const fn of listeners) fn(status);
  }
}

export async function syncSession() {
  try {
    applyServerState(await api("GET", "/api/session"));
  } catch (err) {
    // Sem resposta do servidor: mantém a contagem local.
    reportApiError(err);
    update();
  }
}

/** Liga o cronômetro aos elementos do cabeçalho e inicia sincronização e contagem. */
export function initSession({ timerElement, bannerElement }) {
  timerView = timerElement;
  bannerView = bannerElement;
  lastStatus = null;
  update();
  if (tickHandle === null) tickHandle = setInterval(update, 1000);
  if (syncHandle === null) syncHandle = setInterval(syncSession, SYNC_INTERVAL_MS);
  return syncSession();
}
