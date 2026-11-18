// Testes de DOM do avanço entre steps (rota `visit`) e da tela de conclusão.
// Reaproveita o DOM falso de `fake_dom.mjs`, que NÃO expõe `sessionStorage`:
// qualquer uso desse objeto pelo código da tela lança ReferenceError.
// Valida: Requisitos 2.4, 2.6, 3.2 (task 15A.4) e a exibição de `services` (task 15B.3).

import test from "node:test";
import assert from "node:assert/strict";

import { findAll, findButton, installGlobals } from "./fake_dom.mjs";

let currentFetch;
let events;

installGlobals({
  onReplaceState: (...args) => events.push(["replaceState", ...args]),
  fetchImpl: (url, options) => currentFetch(url, options),
});

assert.equal(typeof globalThis.sessionStorage, "undefined");

const { renderLab } = await import("../../app/static/js/lab.js");

const jsonResponse = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const tick = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
};

function makeLab(overrides = {}) {
  return {
    lab_id: "lab-01",
    title: "Lab de teste",
    description: "Descrição",
    difficulty: "iniciante",
    estimated_duration_minutes: 10,
    dea_domains: ["D1", "D3"],
    dea_tasks: ["1.1"],
    services: ["Amazon S3", "AWS Glue"],
    prerequisites: [],
    status: "in_progress",
    resume_step: "intro",
    steps: [
      { step_id: "intro", type: "info", title: "Introdução", status: "not_visited", attempts: 0, content: "Texto" },
      {
        step_id: "t1",
        type: "task",
        title: "Tarefa 1",
        status: "not_visited",
        attempts: 0,
        hint_threshold: 2,
        paths: ["console", "cli"],
        unavailable_paths: {},
      },
      { step_id: "fim", type: "completion", title: "Conclusão", status: "not_visited", attempts: 0, content: "Fim" },
    ],
    ...overrides,
  };
}

/** Instala o fetch simulado; `visitResponse` define a resposta da rota visit. */
function setupApi({ lab, visitResponse }) {
  const calls = [];
  events = [];
  currentFetch = async (url, options) => {
    const method = options.method || "GET";
    const mutating = ["POST", "PUT", "DELETE"].includes(method);
    if (mutating) {
      assert.equal(options.headers["Content-Type"], "application/json");
      assert.equal(options.headers["X-Workshop-Request"], "1");
      assert.equal(options.credentials, "same-origin");
      assert.equal(typeof options.body, "string");
    } else {
      assert.equal(options.body, undefined);
    }
    calls.push({ method, url });
    events.push(["fetch", method, url]);
    if (method === "GET" && url === "/api/labs/lab-01") return jsonResponse(lab);
    if (method === "GET" && url === "/api/progress") return jsonResponse({ preferences: { path: "console" } });
    if (method === "GET" && url.includes("/content")) return jsonResponse({ markdown: "Instruções" });
    if (method === "POST" && url.endsWith("/visit")) return visitResponse();
    throw new Error(`Chamada inesperada: ${method} ${url}`);
  };
  return calls;
}

async function mount({ lab, stepId, visitResponse }) {
  const calls = setupApi({ lab, visitResponse });
  const root = await renderLab({
    labId: "lab-01",
    stepId,
    navigate: (url) => events.push(["navigate", url]),
  });
  await tick();
  return { root, calls };
}

const visitCalls = (calls) => calls.filter((c) => c.url.endsWith("/visit"));
const wizardItems = (root) => findAll(root, (n) => n.className.startsWith("wizard__item"));

test("avançar de step não task chama visit antes de navegar e atualiza o wizard", async () => {
  const { root, calls } = await mount({
    lab: makeLab(),
    stepId: "intro",
    visitResponse: () =>
      jsonResponse({
        lab_id: "lab-01",
        step_id: "intro",
        step_status: "passed",
        attempt_count: 0,
        lab_status: "in_progress",
        resume_step: "t1",
      }),
  });
  assert.match(wizardItems(root)[0].className, /--in_progress/);

  findButton(root, "Avançar").click();
  await tick();

  assert.equal(visitCalls(calls).length, 1);
  assert.equal(visitCalls(calls)[0].method, "POST");
  assert.equal(visitCalls(calls)[0].url, "/api/labs/lab-01/steps/intro/visit");

  const visitIdx = events.findIndex((e) => e[0] === "fetch" && e[2].endsWith("/visit"));
  const navIdx = events.findIndex((e) => e[0] === "navigate");
  assert.ok(visitIdx >= 0 && navIdx > visitIdx, "navegação deve ocorrer depois do visit");
  assert.deepEqual(events[navIdx], ["navigate", "/lab/lab-01/t1"]);
  assert.match(wizardItems(root)[0].className, /--passed/);
});

test("erro da API em visit mostra a mensagem e não navega", async () => {
  const { root, calls } = await mount({
    lab: makeLab(),
    stepId: "intro",
    visitResponse: () =>
      jsonResponse(
        { error: true, code: "INTERNAL_ERROR", message: "Falha ao gravar progresso", http_status: 500 },
        500
      ),
  });

  findButton(root, "Avançar").click();
  await tick();

  assert.equal(visitCalls(calls).length, 1);
  assert.equal(events.filter((e) => e[0] === "navigate").length, 0);
  const alerts = findAll(root, (n) => n.getAttribute("role") === "alert");
  assert.ok(alerts.some((n) => n.textContent.includes("Falha ao gravar progresso")));
  assert.match(wizardItems(root)[0].className, /--in_progress/);
});

test("avançar de step task não chama visit", async () => {
  const lab = makeLab({ resume_step: "t1" });
  lab.steps[0].status = "passed";
  const { root, calls } = await mount({
    lab,
    stepId: "t1",
    visitResponse: () => {
      throw new Error("visit não deveria ser chamado");
    },
  });

  findButton(root, "Avançar").click();
  await tick();

  assert.equal(visitCalls(calls).length, 0);
  assert.deepEqual(events.filter((e) => e[0] === "navigate"), [["navigate", "/lab/lab-01/fim"]]);
});

function completionLab(extra) {
  const lab = makeLab({ resume_step: "fim", ...extra });
  lab.steps = [lab.steps[2]];
  return lab;
}

test("a tela de conclusão lista services e domínios do lab", async () => {
  const { root } = await mount({ lab: completionLab(), stepId: "fim", visitResponse: () => jsonResponse({}) });
  const text = root.textContent;
  assert.match(text, /Serviços AWS: Amazon S3AWS Glue/);
  assert.match(text, /Domínios DEA-C01: D1D3/);
});

test("a tela de conclusão mostra n/d quando services está ausente", async () => {
  const lab = completionLab();
  delete lab.services;
  const { root } = await mount({ lab, stepId: "fim", visitResponse: () => jsonResponse({}) });
  assert.match(root.textContent, /Serviços AWS: n\/d/);
});
