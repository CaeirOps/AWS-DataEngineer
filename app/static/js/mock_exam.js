// Simulado final (`/mock-exam`). As questões chegam sem gabarito; a correção,
// a nota por domínio e as explicações vêm só do envio (Requirement 18).

import { api } from "./api.js";
import { el, errorBanner, replaceContent } from "./dom.js";
import { resultItem } from "./quiz.js";

const DOMAINS = ["D1", "D2", "D3", "D4"];
const percent = (value) => (value === null || value === undefined ? "n/d" : `${Math.round(Number(value) * 100)}%`);
let timerHandle = null;

/** Para o cronômetro; chamado pelo roteador a cada troca de tela. */
export function stopMockExamTimer() {
  if (timerHandle !== null) clearInterval(timerHandle);
  timerHandle = null;
}

export function formatRemaining(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

function formatDate(iso) {
  return iso ? String(iso).replace("T", " ").replace("Z", " UTC") : "n/d";
}

function historyView(attempts) {
  const finished = (attempts || []).filter((a) => a.finished_at);
  if (finished.length === 0) return el("p", { class: "card__meta" }, "Nenhuma tentativa concluída ainda.");
  return el(
    "table",
    { class: "mock-exam__history" },
    el("thead", null, el("tr", null, el("th", null, "Data"), el("th", null, "Nota"), DOMAINS.map((d) => el("th", null, d)))),
    el(
      "tbody",
      null,
      finished.map((a) =>
        el(
          "tr",
          null,
          el("td", null, formatDate(a.finished_at)),
          el("td", null, `${percent(a.score)} (${a.right} de ${a.total})`),
          DOMAINS.map((d) => el("td", null, percent(((a.by_domain || {})[d] || {}).score)))
        )
      )
    )
  );
}

function domainTable(byDomain) {
  return el(
    "table",
    { class: "mock-exam__domains" },
    el("thead", null, el("tr", null, el("th", null, "Domínio"), el("th", null, "Acertos"), el("th", null, "Nota"))),
    el(
      "tbody",
      null,
      DOMAINS.map((d) => {
        const item = (byDomain || {})[d] || { right: 0, total: 0, score: null };
        return el("tr", { dataset: { domain: d } }, el("td", null, d), el("td", null, `${item.right} de ${item.total}`), el("td", null, percent(item.score)));
      })
    )
  );
}

/**
 * Tela do Simulado. `now` e `setIntervalFn` são injetáveis nos testes.
 */
export async function renderMockExam({ now = () => Date.now(), setIntervalFn = setInterval } = {}) {
  stopMockExamTimer();
  const root = el("div", { class: "mock-exam" });
  const header = [
    el("a", { class: "back-link", href: "/", "data-link": "" }, "\u2190 Voltar ao Dashboard"),
    el("h1", null, "Simulado final"),
  ];

  async function showIntro() {
    stopMockExamTimer();
    let info;
    try {
      info = await api("GET", "/api/mock-exam");
    } catch (err) {
      replaceContent(root, header, errorBanner(err, "Não foi possível carregar o Simulado"));
      return;
    }
    const max = Math.min(info.max_count, Math.max(info.available, 1));
    const countInput = el("input", { type: "number", min: "1", max: String(max), id: "mock-count", class: "input" });
    countInput.value = String(Math.min(info.default_count, max));
    const timerInput = el("input", { type: "checkbox", id: "mock-timer" });
    timerInput.checked = true;
    const message = el("div");
    const start = el("button", { type: "button", class: "btn btn--primary", disabled: info.available === 0 }, "Iniciar simulado");
    start.addEventListener("click", async () => {
      start.disabled = true;
      const count = Number.parseInt(countInput.value, 10);
      try {
        const attempt = await api("POST", "/api/mock-exam", { count: Number.isFinite(count) ? count : info.default_count });
        showExam(attempt, timerInput.checked);
      } catch (err) {
        replaceContent(message, errorBanner(err, "Não foi possível iniciar o Simulado"));
        start.disabled = false;
      }
    });
    const weights = DOMAINS.map((d) => `${d} ${Math.round((info.weights || {})[d] * 100)}%`).join(", ");
    replaceContent(
      root,
      header,
      el(
        "section",
        { class: "banner banner--info", "aria-label": "Sobre o Simulado" },
        el("p", null, `Questões sorteadas das Verificações de conhecimento, sem repetição, com a distribuição do exame: ${weights}.`),
        el("p", null, `Questões disponíveis no catálogo: ${info.available}. O exame real tem 65 questões em ${info.duration_minutes} minutos.`),
        el("p", null, "O Simulado não usa a AWS e não gera custos.")
      ),
      info.available === 0 ? el("p", null, "Ainda não há questões no catálogo.") : null,
      el("p", null, el("label", { for: "mock-count" }, "Quantidade de questões: "), countInput),
      el("p", null, el("label", null, timerInput, ` Usar cronômetro de ${info.duration_minutes} minutos (opcional)`)),
      message,
      el("div", { class: "step-nav" }, start),
      el("h2", null, "Tentativas anteriores"),
      historyView(info.attempts)
    );
  }

  function showExam(attempt, useTimer) {
    const questions = attempt.questions;
    const answers = new Map(questions.map((q) => [q.id, new Set()]));
    let current = 0;
    let submitting = false;
    let confirmPending = false;
    const timerBox = el("p", { class: "mock-exam__timer", role: "timer", "aria-live": "off" });
    const questionBox = el("div");
    const nav = el("ol", { class: "mock-exam__nav", "aria-label": "Questões" });
    const message = el("div");
    const deadline = now() + attempt.duration_minutes * 60 * 1000;

    function tick() {
      const remaining = deadline - now();
      replaceContent(timerBox, `Tempo restante: ${formatRemaining(remaining)}`);
      if (remaining <= 0) {
        stopMockExamTimer();
        replaceContent(timerBox, el("strong", null, "Tempo esgotado."), " Você ainda pode finalizar e ver a nota.");
      }
    }
    if (useTimer) {
      tick();
      timerHandle = setIntervalFn(tick, 1000);
    }

    function answeredCount() {
      return [...answers.values()].filter((s) => s.size > 0).length;
    }

    function renderNav() {
      replaceContent(
        nav,
        questions.map((q, i) => {
          const button = el(
            "button",
            {
              type: "button",
              class: `mock-exam__nav-item${answers.get(q.id).size ? " mock-exam__nav-item--answered" : ""}`,
              "aria-current": i === current ? "step" : null,
              "aria-label": `Questão ${i + 1}`,
            },
            String(i + 1)
          );
          button.addEventListener("click", () => {
            current = i;
            renderQuestion();
          });
          return el("li", null, button);
        })
      );
    }

    function renderQuestion() {
      const q = questions[current];
      const selected = answers.get(q.id);
      const multiple = q.type === "multiple";
      const fieldset = el(
        "fieldset",
        { class: "quiz__question", dataset: { questionId: q.id } },
        el("legend", null, `Questão ${current + 1} de ${questions.length}. ${q.prompt}`),
        multiple ? el("p", { class: "quiz__select" }, `Marque ${q.select} alternativas.`) : null
      );
      for (const option of q.options) {
        const input = el("input", { type: multiple ? "checkbox" : "radio", name: `mock-${current}`, dataset: { optionId: option.id } });
        input.checked = selected.has(option.id);
        input.addEventListener("change", () => {
          if (!multiple) selected.clear();
          if (input.checked) selected.add(option.id);
          else selected.delete(option.id);
          confirmPending = false;
          renderNav();
        });
        fieldset.append(el("label", { class: "quiz__option" }, input, " ", option.text));
      }
      const prev = el("button", { type: "button", class: "btn", disabled: current === 0 }, "Anterior");
      prev.addEventListener("click", () => {
        current -= 1;
        renderQuestion();
      });
      const next = el("button", { type: "button", class: "btn", disabled: current === questions.length - 1 }, "Próxima");
      next.addEventListener("click", () => {
        current += 1;
        renderQuestion();
      });
      replaceContent(questionBox, fieldset, el("div", { class: "step-nav" }, prev, next));
      renderNav();
    }

    const finish = el("button", { type: "button", class: "btn btn--primary" }, "Finalizar simulado");
    finish.addEventListener("click", async () => {
      if (submitting) return;
      const missing = questions.length - answeredCount();
      if (missing > 0 && !confirmPending) {
        confirmPending = true;
        replaceContent(
          message,
          el("div", { class: "banner banner--warning", role: "alert" }, `${missing} questões sem resposta contam como erradas. Clique de novo em "Finalizar simulado" para confirmar.`)
        );
        return;
      }
      submitting = true;
      finish.disabled = true;
      const body = {};
      for (const [id, set] of answers) body[id] = [...set];
      try {
        const result = await api("POST", `/api/mock-exam/${encodeURIComponent(attempt.attempt_id)}/submit`, { answers: body });
        stopMockExamTimer();
        showResult(result);
      } catch (err) {
        replaceContent(message, errorBanner(err, "Não foi possível corrigir o Simulado"));
        submitting = false;
        finish.disabled = false;
      }
    });

    replaceContent(
      root,
      header,
      attempt.message ? el("div", { class: "banner banner--warning", role: "note" }, attempt.message) : null,
      useTimer ? timerBox : null,
      nav,
      questionBox,
      message,
      el("div", { class: "step-nav" }, finish)
    );
    renderQuestion();
  }

  function showResult(result) {
    const again = el("button", { type: "button", class: "btn btn--primary" }, "Voltar ao início do Simulado");
    again.addEventListener("click", showIntro);
    replaceContent(
      root,
      header,
      el(
        "div",
        { class: "feedback feedback--passed", role: "status" },
        el("strong", null, `Nota geral: ${percent(result.score)} (${result.right} de ${result.total}).`)
      ),
      el("h2", null, "Nota por domínio"),
      domainTable(result.by_domain),
      el("h2", null, "Correção"),
      el("ol", { class: "quiz__results" }, (result.results || []).map(resultItem)),
      el("div", { class: "step-nav" }, again)
    );
  }

  await showIntro();
  return root;
}
