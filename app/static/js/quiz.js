// Verificação de conhecimento (step `quiz`). As questões chegam sem gabarito;
// a correção e as explicações vêm só da resposta do POST (Requirement 17).

import { api } from "./api.js";
import { el, errorBanner, replaceContent } from "./dom.js";

const enc = encodeURIComponent;
const percent = (value) => `${Math.round(Number(value) * 100)}%`;

function quizUrl(labId, stepId) {
  return `/api/labs/${enc(labId)}/steps/${enc(stepId)}/quiz`;
}

/** Uma questão com rádio (escolha única) ou caixas de seleção (múltipla). */
function questionField(question, index) {
  const multiple = question.type === "multiple";
  const name = `quiz-${question.id}`;
  const inputs = [];
  const fieldset = el(
    "fieldset",
    { class: "quiz__question", dataset: { questionId: question.id } },
    el("legend", null, `${index + 1}. ${question.prompt}`),
    multiple
      ? el("p", { class: "quiz__select" }, `Marque ${question.select} alternativas.`)
      : null
  );
  for (const option of question.options) {
    const input = el("input", {
      type: multiple ? "checkbox" : "radio",
      name,
      value: option.id,
      dataset: { optionId: option.id },
    });
    inputs.push([option.id, input]);
    fieldset.append(el("label", { class: "quiz__option" }, input, " ", option.text));
  }
  return { fieldset, selected: () => inputs.filter(([, i]) => i.checked).map(([id]) => id) };
}

/** Resultado de uma questão: certa ou errada, e a explicação de cada alternativa. */
function resultItem(result, index) {
  const correct = new Set(result.correct);
  const selected = new Set(result.selected);
  return el(
    "li",
    { class: `quiz__result quiz__result--${result.right ? "right" : "wrong"}`, dataset: { questionId: result.id } },
    el("p", { class: "quiz__result-title" }, `${index + 1}. ${result.right ? "Correta" : "Incorreta"}: ${result.prompt}`),
    el(
      "ul",
      null,
      result.options.map((option) => {
        const tags = [];
        if (correct.has(option.id)) tags.push("correta");
        if (selected.has(option.id)) tags.push("sua resposta");
        return el(
          "li",
          { class: correct.has(option.id) ? "quiz__option--correct" : null, dataset: { optionId: option.id } },
          el("strong", null, option.text),
          tags.length ? ` (${tags.join(", ")})` : "",
          el("div", { class: "quiz__explanation" }, option.explanation)
        );
      })
    )
  );
}

/**
 * Painel do quiz. `onResult(result)` recebe a resposta do POST, com
 * `step_status`, `lab_status` e `resume_step` para atualizar a tela.
 */
export function createQuizPanel({ labId, step, onResult }) {
  const root = el("section", { class: "quiz", "aria-label": "Verificação de conhecimento" });
  let quiz = null;
  let busy = false;

  function renderForm() {
    const fields = quiz.questions.map(questionField);
    const message = el("div");
    const submit = el("button", { type: "button", class: "btn btn--primary" }, "Enviar respostas");
    submit.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      submit.disabled = true;
      const answers = {};
      quiz.questions.forEach((q, i) => {
        answers[q.id] = fields[i].selected();
      });
      try {
        const result = await api("POST", quizUrl(labId, step.step_id), { answers });
        quiz.attempts = result.attempts;
        quiz.best_score = result.best_score;
        quiz.status = result.step_status;
        renderResult(result);
        if (onResult) onResult(result);
      } catch (err) {
        replaceContent(message, errorBanner(err, "Não foi possível corrigir as respostas"));
        submit.disabled = false;
      } finally {
        busy = false;
      }
    });
    replaceContent(
      root,
      summary(),
      fields.map((f) => f.fieldset),
      message,
      el("div", { class: "step-nav" }, submit)
    );
  }

  function summary() {
    const parts = [`${quiz.questions.length} questões. Nota mínima: ${percent(quiz.pass_score)}.`];
    if (quiz.attempts > 0) parts.push(`Tentativas: ${quiz.attempts}. Melhor nota: ${percent(quiz.best_score || 0)}.`);
    if (quiz.status === "passed") parts.push("Verificação concluída.");
    return el("p", { class: "card__meta quiz__summary" }, parts.join(" "));
  }

  function renderResult(result) {
    const retry = el("button", { type: "button", class: "btn" }, "Tentar novamente");
    retry.addEventListener("click", renderForm);
    replaceContent(
      root,
      el(
        "div",
        { class: `feedback feedback--${result.passed ? "passed" : "failed"}`, role: "status" },
        el(
          "div",
          null,
          el("strong", null, `Nota: ${percent(result.score)} (${result.right} de ${result.total}).`),
          " ",
          result.passed
            ? "Você atingiu a nota mínima."
            : `A nota mínima é ${percent(result.pass_score)}. Revise as explicações e tente novamente.`
        )
      ),
      summary(),
      el("ol", { class: "quiz__results" }, result.results.map(resultItem)),
      el("div", { class: "step-nav" }, retry)
    );
  }

  async function load() {
    replaceContent(root, el("p", { class: "loading" }, "Carregando questões..."));
    try {
      quiz = await api("GET", quizUrl(labId, step.step_id));
      renderForm();
    } catch (err) {
      replaceContent(root, errorBanner(err, "Não foi possível carregar a verificação de conhecimento"));
    }
  }

  load();
  return root;
}
