// Testes de DOM do seletor de Trilha (Console | CLI) da tela de lab.
// Usa um DOM mínimo escrito aqui mesmo (sem jsdom, sem node_modules) e um
// `fetch` simulado que registra todas as chamadas.
// Valida: Requisitos 11.2, 11.3, 11.5, 11.6.

import test from "node:test";
import assert from "node:assert/strict";

import {
  FakeNode,
  FakeElement,
  findAll,
  findTab,
  findButton,
  installGlobals,
} from "./fake_dom.mjs";

let currentFetch;
let navigations;

installGlobals({
  onReplaceState: (...args) => navigations.push(["replaceState", ...args]),
  fetchImpl: (url, options) => currentFetch(url, options),
});

const { renderLab } = await import("../../app/static/js/lab.js");

// ----------------------------------------------------------- API simulada

const jsonResponse = (body) => ({ ok: true, status: 200, json: async () => body });

function makeLab({ paths = ["console", "cli"], unavailable = {}, attempts = 0, hintThreshold = 2 } = {}) {
  return {
    lab_id: "lab-01",
    title: "Lab de teste",
    description: "Descrição",
    difficulty: "iniciante",
    estimated_duration_minutes: 10,
    estimated_cost_usd: 0,
    dea_domains: ["D1"],
    dea_tasks: ["1.1"],
    prerequisites: [],
    status: "in_progress",
    resume_step: "t1",
    steps: [
      {
        step_id: "t1",
        type: "task",
        title: "Tarefa 1",
        status: attempts > 0 ? "failed" : "not_visited",
        attempts,
        hint_threshold: hintThreshold,
        paths,
        unavailable_paths: unavailable,
      },
    ],
  };
}

/** Instala o fetch simulado e devolve o registro de chamadas. */
function setupApi({ lab, preferredPath }) {
  const calls = [];
  navigations = [];
  currentFetch = async (url, options) => {
    const method = options.method || "GET";
    calls.push({ method, url, body: options.body ? JSON.parse(options.body) : undefined });
    const parsed = new URL(url, "http://localhost");
    const path = parsed.searchParams.get("path");
    if (method === "GET" && url === "/api/labs/lab-01") return jsonResponse(lab);
    if (method === "GET" && url === "/api/progress") {
      return jsonResponse(preferredPath ? { preferences: { path: preferredPath } } : { preferences: {} });
    }
    if (method === "PUT" && url === "/api/progress") return jsonResponse({ ok: true });
    if (method === "GET" && parsed.pathname.endsWith("/content")) {
      return jsonResponse({ markdown: `Instruções da Trilha ${path}` });
    }
    if (method === "GET" && parsed.pathname.endsWith("/hint")) {
      return jsonResponse({ hint: `Dica da Trilha ${path}` });
    }
    if (method === "POST" && url === "/api/validate/lab-01/t1") {
      return jsonResponse({
        passed: false,
        message: "Bucket não encontrado",
        attempt_count: 1,
        step_status: "failed",
        show_hint_button: false,
        hint: null,
      });
    }
    throw new Error(`Chamada inesperada: ${method} ${url}`);
  };
  return calls;
}

const tick = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
};

const contentCalls = (calls) => calls.filter((c) => c.url.includes("/content"));
const hintCalls = (calls) => calls.filter((c) => c.url.includes("/hint"));
const putCalls = (calls) => calls.filter((c) => c.method === "PUT");

async function mount(options) {
  const calls = setupApi(options);
  const root = await renderLab({ labId: "lab-01", stepId: "t1", navigate: () => navigations.push(["navigate"]) });
  await tick();
  return { root, calls };
}

// ------------------------------------------------------------------ testes

test("Trilha indisponível fica desabilitada e exibe o motivo", async () => {
  const reason = "Este step exige o Console da AWS";
  const { root, calls } = await mount({
    lab: makeLab({ paths: ["console"], unavailable: { cli: reason } }),
  });

  const cliTab = findTab(root, "CLI");
  assert.equal(cliTab.getAttribute("aria-disabled"), "true");
  assert.equal(cliTab.getAttribute("title"), reason);
  assert.match(cliTab.textContent, /indisponível/);
  const notes = findAll(root, (n) => n.className === "tab-note").map((n) => n.textContent);
  assert.ok(notes.some((t) => t.includes(reason)));

  const before = calls.length;
  cliTab.click();
  await tick();
  assert.equal(calls.length, before, "clicar na aba indisponível não deve gerar chamadas");
  assert.equal(findTab(root, "Console").getAttribute("aria-selected"), "true");
});

test("clicar em uma aba carrega o conteúdo, salva a preferência e mantém a validação", async () => {
  const { root, calls } = await mount({ lab: makeLab(), preferredPath: "console" });
  assert.equal(findTab(root, "Console").getAttribute("aria-selected"), "true");
  assert.equal(contentCalls(calls).length, 1);

  findButton(root, "Validar").click();
  await tick();
  const feedbackText = () => findAll(root, (n) => n.className.includes("feedback__message"))[0]?.textContent;
  assert.equal(feedbackText(), "Bucket não encontrado");

  const labFetchesBefore = calls.filter((c) => c.url === "/api/labs/lab-01").length;
  findTab(root, "CLI").click();
  await tick();

  const contents = contentCalls(calls);
  assert.equal(contents.length, 2);
  assert.match(contents[1].url, /path=cli$/);
  assert.deepEqual(putCalls(calls).map((c) => c.body), [{ preferences: { path: "cli" } }]);
  assert.equal(findTab(root, "CLI").getAttribute("aria-selected"), "true");
  assert.equal(findTab(root, "Console").getAttribute("aria-selected"), "false");
  assert.equal(
    findAll(root, (n) => n.getAttribute("id") === "path-content")[0].textContent,
    "Instruções da Trilha cli"
  );
  // Sem recarregar a página: o lab não é buscado de novo e não há navegação.
  assert.equal(calls.filter((c) => c.url === "/api/labs/lab-01").length, labFetchesBefore);
  assert.equal(navigations.filter(([kind]) => kind === "navigate").length, 0);
  // O resultado da última validação continua visível.
  assert.equal(feedbackText(), "Bucket não encontrado");
});

test("a aba inicial segue preferences.path", async () => {
  const { root, calls } = await mount({ lab: makeLab(), preferredPath: "cli" });
  assert.equal(findTab(root, "CLI").getAttribute("aria-selected"), "true");
  assert.match(contentCalls(calls)[0].url, /path=cli$/);
  assert.equal(putCalls(calls).length, 0);
});

test("preferência indisponível no step abre a outra Trilha sem alterar a preferência", async () => {
  const { root, calls } = await mount({
    lab: makeLab({ paths: ["console"], unavailable: { cli: "Somente Console" } }),
    preferredPath: "cli",
  });
  assert.equal(findTab(root, "Console").getAttribute("aria-selected"), "true");
  assert.match(contentCalls(calls)[0].url, /path=console$/);
  assert.equal(putCalls(calls).length, 0);
});

test("a dica detalhada usa a Trilha ativa e é recarregada ao trocar de aba", async () => {
  const { root, calls } = await mount({ lab: makeLab({ attempts: 3 }), preferredPath: "console" });

  const hintButton = findButton(root, "Ver Dica Detalhada");
  assert.equal(hintButton.hidden, false);
  hintButton.click();
  await tick();
  assert.equal(hintCalls(calls).length, 1);
  assert.match(hintCalls(calls)[0].url, /path=console$/);
  const hintBox = findAll(root, (n) => n.className === "hint-box")[0];
  assert.match(hintBox.textContent, /Dica da Trilha console/);

  findTab(root, "CLI").click();
  await tick();
  assert.equal(hintCalls(calls).length, 2);
  assert.match(hintCalls(calls)[1].url, /path=cli$/);
  assert.match(hintBox.textContent, /Dica da Trilha cli/);
});
