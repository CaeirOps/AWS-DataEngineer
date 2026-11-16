// Deploy e teardown de stacks CloudFormation com polling de status.

import { api } from "./api.js";
import { el, errorBanner, errorMessage, replaceContent } from "./dom.js";
import { guardAction, isSessionExpired, reportApiError } from "./session.js";

const POLL_INTERVAL_MS = 5000;
const enc = encodeURIComponent;

const timers = new Set();

/** Cancela todo polling ativo (chamado a cada troca de rota). */
export function stopAllPolling() {
  for (const timer of timers) clearTimeout(timer);
  timers.clear();
}

export const isInProgress = (status) => typeof status === "string" && status.endsWith("_IN_PROGRESS");
export const isFailure = (status) =>
  typeof status === "string" &&
  (status.endsWith("_FAILED") || status === "ROLLBACK_COMPLETE" || status === "UPDATE_ROLLBACK_COMPLETE");

function statusView(data) {
  const status = data.status;
  const busy = isInProgress(status);
  const failed = isFailure(status);
  const view = el("div");
  view.append(
    el(
      "p",
      null,
      "Status da stack: ",
      el("span", { class: `stack-status${busy ? " stack-status--busy" : ""}` }, status)
    )
  );
  if (busy) {
    view.append(el("p", { class: "card__meta" }, "Atualizando a cada 5 segundos. Você pode aguardar nesta tela."));
  }
  if (failed) {
    view.append(
      el(
        "div",
        { class: "banner banner--error", role: "alert" },
        el("div", { class: "banner__title" }, "A operação da stack falhou"),
        el("div", null, data.status_reason || "A AWS não informou o motivo. Consulte os eventos da stack no CloudFormation.")
      )
    );
  } else if (data.status_reason && !busy) {
    view.append(el("p", { class: "card__meta" }, data.status_reason));
  }
  const outputs = Object.entries(data.outputs || {});
  if (outputs.length > 0) {
    view.append(
      el("h4", null, "Outputs"),
      el(
        "table",
        null,
        el("thead", null, el("tr", null, el("th", null, "Chave"), el("th", null, "Valor"))),
        el(
          "tbody",
          null,
          outputs.map(([key, value]) => el("tr", null, el("td", null, key), el("td", null, String(value))))
        )
      )
    );
  }
  return view;
}

/**
 * Painel base: mostra o status e faz polling enquanto `*_IN_PROGRESS`.
 * `notFoundText`: texto exibido quando a stack não existe (404 STACK_NOT_FOUND).
 */
function createStackPanel(labId, notFoundText) {
  const box = el("div", { "aria-live": "polite" });
  let current = null;
  let generation = 0;

  async function refresh() {
    const ticket = generation;
    try {
      const data = await api("GET", `/api/stack-status/${enc(labId)}`);
      if (ticket !== generation) return null;
      current = data.status;
      replaceContent(box, statusView(data));
      schedule(data.status);
      return data;
    } catch (err) {
      if (ticket !== generation) return null;
      current = null;
      reportApiError(err);
      if (err.code === "STACK_NOT_FOUND") {
        replaceContent(box, el("p", { class: "card__meta" }, notFoundText));
      } else {
        replaceContent(box, errorBanner(err, "Não foi possível consultar a stack"));
      }
      return null;
    }
  }

  function schedule(status) {
    if (!isInProgress(status)) return;
    const timer = setTimeout(() => {
      timers.delete(timer);
      refresh();
    }, POLL_INTERVAL_MS);
    timers.add(timer);
  }

  return {
    box,
    refresh() {
      generation += 1;
      return refresh();
    },
    showStatus(status, message) {
      generation += 1;
      current = status;
      replaceContent(box, statusView({ status, status_reason: message, outputs: {} }));
      schedule(status);
    },
    get status() {
      return current;
    },
  };
}

export function createDeployPanel(labId) {
  const stack = createStackPanel(labId, "A stack ainda não foi criada. Clique em \"Iniciar deploy\".");
  const messageBox = el("div");
  const button = el("button", { type: "button", class: "btn btn--primary" }, "Iniciar deploy");

  guardAction(button);
  button.addEventListener("click", async () => {
    if (isSessionExpired()) return;
    button.disabled = true;
    replaceContent(messageBox);
    try {
      const data = await api("POST", `/api/deploy/${enc(labId)}`);
      replaceContent(messageBox, el("div", { class: "banner banner--info" }, data.message));
      stack.showStatus(data.status);
      if (!isInProgress(data.status)) await stack.refresh();
    } catch (err) {
      reportApiError(err);
      replaceContent(messageBox, errorBanner(err, "Falha ao iniciar o deploy"));
    } finally {
      button.disabled = isSessionExpired();
    }
  });

  const node = el(
    "section",
    { class: "deploy-panel", "aria-label": "Deploy da stack" },
    el("h3", null, "Stack CloudFormation"),
    el("p", null, button),
    messageBox,
    stack.box
  );
  stack.refresh();
  return { node };
}

function residualScreen(residual) {
  const items = residual || [];
  return el(
    "div",
    { class: "banner banner--warning", role: "alert" },
    el("div", { class: "banner__title" }, "Recursos residuais: verifique e exclua manualmente"),
    el(
      "p",
      null,
      "A exclusão da stack não remove os recursos abaixo. Confirme no console da AWS que eles não geram custo."
    ),
    items.length > 0
      ? el("ul", { class: "checklist" }, items.map((item) => el("li", null, item)))
      : el("p", null, "Este lab não declara recursos residuais.")
  );
}

function confirmModal(stackLabId) {
  return new Promise((resolve) => {
    const opener = document.activeElement;
    const cancel = el("button", { type: "button", class: "btn" }, "Cancelar");
    const confirm = el("button", { type: "button", class: "btn btn--danger" }, "Sim, excluir a stack");
    const titleId = "teardown-modal-title";
    const modal = el(
      "div",
      { class: "modal", role: "dialog", "aria-modal": "true", "aria-labelledby": titleId },
      el("h3", { id: titleId }, "Excluir a stack do lab?"),
      el(
        "p",
        null,
        `Esta ação exclui a stack workshop-${stackLabId} e os recursos que ela gerencia. Recursos criados manualmente não são removidos.`
      ),
      el("div", { class: "modal__actions" }, cancel, confirm)
    );
    const backdrop = el("div", { class: "modal-backdrop" }, modal);

    function close(result) {
      document.removeEventListener("keydown", onKey, true);
      backdrop.remove();
      if (opener && opener.focus) opener.focus();
      resolve(result);
    }
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        close(false);
      } else if (event.key === "Tab") {
        const focusable = [cancel, confirm];
        const index = focusable.indexOf(document.activeElement);
        event.preventDefault();
        const next = event.shiftKey ? index - 1 : index + 1;
        focusable[(next + focusable.length) % focusable.length].focus();
      }
    }
    cancel.addEventListener("click", () => close(false));
    confirm.addEventListener("click", () => close(true));
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop) close(false);
    });
    document.addEventListener("keydown", onKey, true);
    document.body.append(backdrop);
    cancel.focus();
  });
}

export function createTeardownPanel(labId) {
  const stack = createStackPanel(labId, "A stack não existe (já excluída ou nunca criada).");
  const messageBox = el("div");
  const residualBox = el("div");
  const button = el("button", { type: "button", class: "btn btn--danger" }, "Excluir stack");

  guardAction(button);
  button.addEventListener("click", async () => {
    if (isSessionExpired()) return;
    const confirmed = await confirmModal(labId);
    if (!confirmed || isSessionExpired()) return;
    button.disabled = true;
    replaceContent(messageBox);
    try {
      const data = await api("POST", `/api/teardown/${enc(labId)}`, { confirm: true });
      replaceContent(messageBox, el("div", { class: "banner banner--info" }, data.message));
      // Os recursos residuais aparecem após a confirmação, qualquer que seja o status da exclusão.
      replaceContent(residualBox, residualScreen(data.residual_resources));
      stack.showStatus(data.status);
      if (!isInProgress(data.status)) await stack.refresh();
    } catch (err) {
      reportApiError(err);
      replaceContent(messageBox, errorBanner(err, "Falha ao excluir a stack"));
    } finally {
      button.disabled = isSessionExpired();
    }
  });

  const node = el(
    "section",
    { class: "teardown-panel", "aria-label": "Exclusão da stack" },
    el("h3", null, "Excluir stack CloudFormation"),
    el("p", null, button),
    messageBox,
    stack.box,
    residualBox
  );
  stack.refresh();
  return { node };
}

export { errorMessage };
