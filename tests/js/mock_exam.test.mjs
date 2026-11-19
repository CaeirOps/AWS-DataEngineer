// Testes de DOM do Simulado (task 15P.3): início, navegação, cronômetro
// opcional, confirmação de questões sem resposta, resultado por domínio e histórico.
// Valida: Requirements 18.3, 18.4.
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, findButton, installGlobals } from "./fake_dom.mjs";

let currentFetch;
installGlobals({ onReplaceState() {}, fetchImpl: (url, options) => currentFetch(url, options) });
const { renderMockExam, stopMockExamTimer, formatRemaining } = await import("../../app/static/js/mock_exam.js");

const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const tick = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise((r) => setTimeout(r, 0));
};

const INFO = {
  available: 2, available_by_domain: { D1: 1, D2: 1, D3: 0, D4: 0 }, default_count: 65, max_count: 200,
  duration_minutes: 130, weights: { D1: 0.34, D2: 0.26, D3: 0.22, D4: 0.18 },
  attempts: [
    { attempt_id: "a1", finished_at: "2026-11-18T10:00:00Z", score: 0.5, right: 1, total: 2,
      by_domain: { D1: { score: 1 }, D2: { score: 0 }, D3: { score: null }, D4: { score: null } } },
    { attempt_id: "a2", finished_at: null, score: null },
  ],
};
const ATTEMPT = {
  attempt_id: "f".repeat(32), started_at: "2026-11-18T11:00:00Z", duration_minutes: 130, requested: 2,
  adjusted: true, message: "O catálogo não tem questões suficientes.",
  questions: [
    { id: "lab-a/q1", type: "single", prompt: "Primeira?", select: 1, options: ["a", "b", "c", "d"].map((id) => ({ id, text: `A${id}` })) },
    { id: "lab-b/q1", type: "multiple", prompt: "Segunda?", select: 2, options: ["a", "b", "c", "d", "e"].map((id) => ({ id, text: `B${id}` })) },
  ],
};
const RESULT = {
  attempt_id: ATTEMPT.attempt_id, finished_at: "2026-11-18T11:30:00Z", score: 0.5, right: 1, total: 2,
  by_domain: { D1: { right: 1, total: 1, score: 1 }, D2: { right: 0, total: 1, score: 0 }, D3: { right: 0, total: 0, score: null }, D4: { right: 0, total: 0, score: null } },
  results: [
    { id: "lab-a/q1", prompt: "Primeira?", correct: ["b"], selected: ["b"], right: true, options: ["a", "b", "c", "d"].map((id) => ({ id, text: `A${id}`, explanation: `Explica A${id}` })) },
    { id: "lab-b/q1", prompt: "Segunda?", correct: ["a", "c"], selected: [], right: false, options: ["a", "b", "c", "d", "e"].map((id) => ({ id, text: `B${id}`, explanation: `Explica B${id}` })) },
  ],
};

function setup() {
  const calls = [];
  currentFetch = async (url, options) => {
    const method = options.method || "GET";
    calls.push({ method, url, body: options.body ? JSON.parse(options.body) : undefined });
    if (method === "GET" && url === "/api/mock-exam") return json(INFO);
    if (method === "POST" && url === "/api/mock-exam") return json(ATTEMPT);
    if (method === "POST" && url.endsWith("/submit")) return json(RESULT);
    throw new Error(`Chamada inesperada: ${method} ${url}`);
  };
  return calls;
}

const inputsOf = (root) => findAll(root, (n) => n.tag === "input" && n.dataset.optionId);
const check = (input) => {
  input.checked = true;
  input.dispatch("change");
};

test("formatRemaining mostra horas, minutos e segundos", () => {
  assert.equal(formatRemaining(130 * 60 * 1000), "2:10:00");
  assert.equal(formatRemaining(59 * 1000), "00:59");
  assert.equal(formatRemaining(-5), "00:00");
});

test("tela inicial mostra pesos, cronômetro opcional e só tentativas concluídas no histórico", async () => {
  setup();
  const root = await renderMockExam({ setIntervalFn: () => 0 });
  await tick();
  assert.match(root.textContent, /D1 34%, D2 26%, D3 22%, D4 18%/);
  assert.match(root.textContent, /cronômetro de 130 minutos \(opcional\)/);
  const rows = findAll(root, (n) => n.tag === "tr").slice(1);
  assert.equal(rows.length, 1);
  assert.match(rows[0].textContent, /50% \(1 de 2\)100%0%n\/dn\/d/);
  assert.equal(findAll(root, (n) => n.getAttribute("id") === "mock-count")[0].value, "2");
});

test("simulado completo: navegação, cronômetro, confirmação, envio e resultado por domínio", async () => {
  const calls = setup();
  let clock = 0;
  let ticker = null;
  const root = await renderMockExam({ now: () => clock, setIntervalFn: (fn) => { ticker = fn; return 1; } });
  await tick();
  findButton(root, "Iniciar simulado").click();
  await tick();
  assert.deepEqual(calls.find((c) => c.method === "POST").body, { count: 2 });
  assert.match(root.textContent, /O catálogo não tem questões suficientes\./);
  assert.match(root.textContent, /Tempo restante: 2:10:00/);
  clock = 130 * 60 * 1000;
  ticker();
  assert.match(root.textContent, /Tempo esgotado\./);

  assert.match(root.textContent, /Questão 1 de 2\. Primeira\?/);
  check(inputsOf(root)[1]);
  findButton(root, "Próxima").click();
  assert.match(root.textContent, /Marque 2 alternativas\./);
  findButton(root, "Anterior").click();
  assert.equal(inputsOf(root)[1].checked, true, "a resposta da questão 1 fica guardada");
  const answered = findAll(root, (n) => n.tag === "button" && n.className.includes("--answered"));
  assert.deepEqual(answered.map((b) => b.textContent), ["1"]);

  findButton(root, "Finalizar simulado").click();
  await tick();
  assert.equal(calls.filter((c) => c.url.endsWith("/submit")).length, 0);
  assert.match(root.textContent, /1 questões sem resposta contam como erradas/);
  findButton(root, "Finalizar simulado").click();
  await tick();
  const submit = calls.find((c) => c.url.endsWith("/submit"));
  assert.equal(submit.url, `/api/mock-exam/${"f".repeat(32)}/submit`);
  assert.deepEqual(submit.body, { answers: { "lab-a/q1": ["b"], "lab-b/q1": [] } });
  assert.match(root.textContent, /Nota geral: 50% \(1 de 2\)\./);
  const d1 = findAll(root, (n) => n.tag === "tr" && n.dataset.domain === "D1")[0];
  assert.match(d1.textContent, /D11 de 1100%/);
  assert.match(root.textContent, /Explica Bc/);
  stopMockExamTimer();
});

test("sem cronômetro não há contagem regressiva", async () => {
  setup();
  let started = false;
  const root = await renderMockExam({ setIntervalFn: () => { started = true; return 1; } });
  await tick();
  findAll(root, (n) => n.getAttribute("id") === "mock-timer")[0].checked = false;
  findButton(root, "Iniciar simulado").click();
  await tick();
  assert.equal(started, false);
  assert.ok(!/Tempo restante/.test(root.textContent));
});
