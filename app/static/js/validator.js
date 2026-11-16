// Validação de steps `task`: chamada à API, feedback sem reload e dica por Trilha.

import { api, el, errorMessage, replaceContent } from "./dom.js";
import { renderMarkdown } from "./markdown.js";

const enc = encodeURIComponent;

function feedback(passed, message, attempts, hint) {
  return el(
    "div",
    { class: `feedback ${passed ? "feedback--passed" : "feedback--failed"}`, role: passed ? "status" : "alert" },
    el("span", { class: "feedback__icon", "aria-hidden": "true" }, passed ? "\u2713" : "\u2717"),
    el(
      "div",
      { class: "feedback__body" },
      el("p", { class: "feedback__message" }, message),
      hint ? el("p", { class: "feedback__message" }, el("strong", null, "Dica: "), hint) : null,
      attempts !== null && attempts !== undefined
        ? el("p", { class: "feedback__attempts" }, `Tentativas: ${attempts}`)
        : null
    )
  );
}

/**
 * Painel de validação de um step.
 * @param {object} opts
 *   labId, step: dados do step (`attempts`, `hint_threshold`, `status`)
 *   getPath: função que devolve a Trilha ativa (usada somente para buscar a dica)
 *   onResult: callback com a resposta da validação
 */
export function createValidatorPanel({ labId, step, getPath, onResult }) {
  let attempts = step.attempts || 0;
  let hintVisible = false;
  let hintRequest = 0;

  const resultBox = el("div", { "aria-live": "polite" });
  const hintBox = el("div", { class: "hint-box", hidden: true });
  const attemptsLabel = el("span", { class: "card__meta" });
  const validateButton = el("button", { type: "button", class: "btn btn--primary" }, "Validar");
  const hintButton = el("button", { type: "button", class: "btn", hidden: true, "aria-expanded": "false" }, "Ver Dica Detalhada");

  function updateAttempts() {
    attemptsLabel.textContent = `Tentativas: ${attempts}`;
  }
  updateAttempts();

  function showHintButton(show) {
    hintButton.hidden = !show;
    if (!show) closeHint();
  }
  showHintButton(
    step.status !== "passed" && attempts >= (step.hint_threshold || 0) && attempts > 0
  );

  function closeHint() {
    hintVisible = false;
    hintBox.hidden = true;
    hintButton.setAttribute("aria-expanded", "false");
    hintButton.textContent = "Ver Dica Detalhada";
  }

  async function loadHint() {
    const ticket = ++hintRequest;
    replaceContent(hintBox, el("p", { class: "loading" }, "Carregando dica..."));
    try {
      const path = getPath();
      const data = await api(
        "GET",
        `/api/labs/${enc(labId)}/steps/${enc(step.step_id)}/hint?path=${enc(path)}`
      );
      if (ticket !== hintRequest) return;
      replaceContent(hintBox, el("h4", null, "Dica detalhada"), renderMarkdown(data.hint));
    } catch (err) {
      if (ticket !== hintRequest) return;
      replaceContent(hintBox, el("p", null, errorMessage(err)));
    }
  }

  hintButton.addEventListener("click", () => {
    if (hintVisible) {
      closeHint();
      return;
    }
    hintVisible = true;
    hintBox.hidden = false;
    hintButton.setAttribute("aria-expanded", "true");
    hintButton.textContent = "Ocultar Dica Detalhada";
    loadHint();
  });

  validateButton.addEventListener("click", async () => {
    validateButton.disabled = true;
    validateButton.textContent = "Validando...";
    try {
      // A Trilha não é enviada: o resultado é o mesmo para Console e CLI.
      const result = await api("POST", `/api/validate/${enc(labId)}/${enc(step.step_id)}`, {
        context: {},
      });
      attempts = result.attempt_count;
      updateAttempts();
      replaceContent(resultBox, feedback(result.passed, result.message, attempts, result.hint));
      showHintButton(Boolean(result.show_hint_button) && !result.passed);
      if (onResult) onResult(result);
    } catch (err) {
      replaceContent(resultBox, feedback(false, errorMessage(err), null, null));
    } finally {
      validateButton.disabled = false;
      validateButton.textContent = "Validar";
    }
  });

  const node = el(
    "section",
    { class: "validator", "aria-label": "Validação do step" },
    el("div", { class: "card__footer" }, el("div", null, validateButton, " ", hintButton), attemptsLabel),
    resultBox,
    hintBox
  );

  return {
    node,
    /** Recarrega a dica na Trilha ativa quando ela está aberta (troca de aba). */
    refreshHint() {
      if (hintVisible) loadHint();
    },
  };
}
