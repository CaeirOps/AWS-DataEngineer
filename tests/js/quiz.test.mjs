// Testes de DOM da Verificação de conhecimento (task 15N.4).
// Valida: Requirements 17.1, 17.3 (rádio ou caixas, envio, resultado, nova tentativa).
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, findButton, installGlobals } from "./fake_dom.mjs";

let currentFetch;
installGlobals({ onReplaceState() {}, fetchImpl: (url, options) => currentFetch(url, options) });
const { createQuizPanel } = await import("../../app/static/js/quiz.js");

const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const tick = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise((r) => setTimeout(r, 0));
};

const QUIZ = {
  lab_id: "lab-03",
  step_id: "step-06",
  pass_score: 0.7,
  status: "not_visited",
  attempts: 0,
  best_score: null,
  questions: [
    { id: "q1", type: "single", prompt: "Pergunta única?", select: 1,
      options: ["a", "b", "c", "d"].map((id) => ({ id, text: `Opção ${id}` })) },
    { id: "q2", type: "multiple", prompt: "Pergunta múltipla?", select: 2,
      options: ["a", "b", "c", "d", "e"].map((id) => ({ id, text: `Item ${id}` })) },
  ],
};

function result(passed) {
  return {
    score: passed ? 1 : 0.5, passed, right: passed ? 2 : 1, total: 2, pass_score: 0.7,
    attempts: 1, attempt_count: 1, best_score: passed ? 1 : 0.5, last_score: passed ? 1 : 0.5,
    step_status: passed ? "passed" : "failed", lab_status: passed ? "completed" : "in_progress",
    resume_step: "step-07",
    results: [
      { id: "q1", prompt: "Pergunta única?", correct: ["b"], selected: ["b"], right: true,
        options: ["a", "b", "c", "d"].map((id) => ({ id, text: `Opção ${id}`, explanation: `Porque ${id}` })) },
      { id: "q2", prompt: "Pergunta múltipla?", correct: ["a", "c"], selected: passed ? ["a", "c"] : ["a"], right: passed,
        options: ["a", "b", "c", "d", "e"].map((id) => ({ id, text: `Item ${id}`, explanation: `Motivo ${id}` })) },
    ],
  };
}

const inputs = (root, qid) =>
  findAll(root, (n) => n.tag === "fieldset" && n.dataset.questionId === qid)
    .flatMap((f) => findAll(f, (n) => n.tag === "input"));

test("questões usam rádio ou caixas, avisam quantas marcar e não mostram gabarito", async () => {
  const calls = [];
  currentFetch = async (url, options) => {
    calls.push([url, options.method]);
    return json(QUIZ);
  };
  const root = createQuizPanel({ labId: "lab-03", step: { step_id: "step-06" } });
  await tick();
  assert.deepEqual(calls, [["/api/labs/lab-03/steps/step-06/quiz", "GET"]]);
  assert.ok(inputs(root, "q1").every((i) => i.getAttribute("type") === "radio"));
  assert.ok(inputs(root, "q2").every((i) => i.getAttribute("type") === "checkbox"));
  assert.equal(inputs(root, "q1").length, 4);
  assert.match(root.textContent, /Marque 2 alternativas\./);
  assert.match(root.textContent, /Nota mínima: 70%/);
  assert.ok(!/Porque|Motivo|correta/.test(root.textContent));
});

test("envio manda as alternativas marcadas e mostra o resultado com explicações", async () => {
  let sent;
  currentFetch = async (url, options) => {
    if (options.method === "POST") {
      sent = { url, headers: options.headers, body: JSON.parse(options.body) };
      return json(result(false));
    }
    return json(QUIZ);
  };
  const received = [];
  const root = createQuizPanel({ labId: "lab-03", step: { step_id: "step-06" }, onResult: (r) => received.push(r) });
  await tick();
  inputs(root, "q1")[1].checked = true;
  inputs(root, "q2")[0].checked = true;
  findButton(root, "Enviar respostas").click();
  await tick();
  assert.equal(sent.url, "/api/labs/lab-03/steps/step-06/quiz");
  assert.equal(sent.headers["X-Workshop-Request"], "1");
  assert.deepEqual(sent.body, { answers: { q1: ["b"], q2: ["a"] } });
  assert.equal(received.length, 1);
  assert.match(root.textContent, /Nota: 50% \(1 de 2\)\./);
  assert.match(root.textContent, /A nota mínima é 70%/);
  assert.match(root.textContent, /Porque a/);
  assert.match(root.textContent, /Motivo e/);
  const wrong = findAll(root, (n) => n.className === "quiz__result quiz__result--wrong");
  assert.equal(wrong.length, 1);
  assert.equal(wrong[0].dataset.questionId, "q2");
  assert.match(wrong[0].textContent, /Item a \(correta, sua resposta\)/);
  assert.match(wrong[0].textContent, /Item c \(correta\)/);

  findButton(root, "Tentar novamente").click();
  assert.equal(inputs(root, "q1").length, 4);
  assert.ok(inputs(root, "q1").every((i) => !i.checked));
  assert.match(root.textContent, /Tentativas: 1\. Melhor nota: 50%\./);
});

test("nota aprovada e erro da API aparecem na tela", async () => {
  currentFetch = async (url, options) => json(options.method === "POST" ? result(true) : QUIZ);
  const root = createQuizPanel({ labId: "lab-03", step: { step_id: "step-06" } });
  await tick();
  findButton(root, "Enviar respostas").click();
  await tick();
  assert.match(root.textContent, /Você atingiu a nota mínima\./);
  assert.equal(findAll(root, (n) => n.className === "feedback feedback--passed").length, 1);

  currentFetch = async (url, options) =>
    options.method === "POST"
      ? json({ error: true, code: "INVALID_ANSWER", message: "Resposta inválida.", http_status: 400 }, 400)
      : json(QUIZ);
  const other = createQuizPanel({ labId: "lab-03", step: { step_id: "step-06" } });
  await tick();
  findButton(other, "Enviar respostas").click();
  await tick();
  assert.match(other.textContent, /Não foi possível corrigir as respostas/);
  assert.match(other.textContent, /INVALID_ANSWER/);
  assert.equal(findButton(other, "Enviar respostas").disabled, false);
});
