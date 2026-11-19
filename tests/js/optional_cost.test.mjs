// Testes de DOM do selo "Opcional", do Aviso de custo e da conclusão sem
// Prática opcional (task 15O.3). Valida: Requirements 4.3, 6.8, 19.1, 19.2, 19.4.
import test from "node:test";
import assert from "node:assert/strict";
import { findAll, findButton, installGlobals } from "./fake_dom.mjs";

let currentFetch;
let navigations;
installGlobals({ onReplaceState() {}, fetchImpl: (url, options) => currentFetch(url, options) });
const { renderLab } = await import("../../app/static/js/lab.js");

const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
const tick = async () => {
  for (let i = 0; i < 10; i += 1) await new Promise((r) => setTimeout(r, 0));
};

const task = (step_id, extra = {}) => ({
  step_id, type: "task", title: `Tarefa ${step_id}`, status: "not_visited", attempts: 0,
  hint_threshold: 3, paths: ["console", "cli"], unavailable_paths: {}, optional: false, skills: [], ...extra,
});

function moduleLab(overrides = {}) {
  return {
    lab_id: "lab-03", title: "Athena", description: "d", difficulty: "iniciante",
    estimated_duration_minutes: 60, dea_domains: ["D3"], dea_tasks: ["3.2"], services: ["Amazon Athena"],
    prerequisites: {}, skills: ["3.2.3"], has_infrastructure: true, cost_disclaimer: "",
    cost_notice: {
      services: [
        { name: "Amazon Athena", pricing_url: "https://aws.amazon.com/athena/pricing/" },
        { name: "Serviço suspeito", pricing_url: "https://evil.example/pricing" },
      ],
    },
    status: "in_progress", resume_step: "deploy",
    steps: [
      { step_id: "deploy", type: "deploy", title: "Deploy", status: "not_visited", attempts: 0, content: "Deploy", skills: [] },
      task("t1"),
      task("t2", { optional: true, cost_note: "Notebooks Spark cobram por DPU-hora." }),
      { step_id: "quiz", type: "quiz", title: "Verificação", status: "not_visited", attempts: 0, pass_score: 0.7, skills: [] },
      { step_id: "fim", type: "completion", title: "Conclusão", status: "not_visited", attempts: 0, content: "Fim", skills: [] },
    ],
    ...overrides,
  };
}

async function mount(lab, stepId) {
  navigations = [];
  currentFetch = async (url, options) => {
    const method = options.method || "GET";
    if (method === "GET" && url === `/api/labs/${lab.lab_id}`) return json(lab);
    if (method === "GET" && url === "/api/progress") return json({ preferences: { path: "console" } });
    if (method === "GET" && url.includes("/content")) return json({ markdown: "Instruções" });
    if (method === "GET" && url.endsWith("/quiz")) return json({ pass_score: 0.7, questions: [], attempts: 0 });
    if (method === "GET" && url.startsWith("/api/stack-status/")) {
      return json({ error: true, code: "STACK_NOT_FOUND", message: "Stack não encontrada.", http_status: 404 }, 404);
    }
    if (method === "POST" && url.endsWith("/visit")) {
      return json({ step_status: "passed", attempt_count: 0, lab_status: lab.status, resume_step: stepId });
    }
    throw new Error(`Chamada inesperada: ${method} ${url}`);
  };
  const root = await renderLab({ labId: lab.lab_id, stepId, navigate: (u) => navigations.push(u) });
  await tick();
  return root;
}

const costBanners = (root) => findAll(root, (n) => n.getAttribute("aria-label") === "Aviso de custo");
const optionalBanners = (root) => findAll(root, (n) => n.getAttribute("aria-label") === "Prática opcional");
const badges = (root) => findAll(root, (n) => n.className === "badge badge--optional");

test("o Aviso de custo do deploy lista os serviços com links oficiais e sem USD", async () => {
  const root = await mount(moduleLab(), "deploy");
  const [banner] = costBanners(root);
  assert.ok(banner);
  const links = findAll(banner, (n) => n.tag === "a");
  assert.equal(links.length, 1);
  assert.equal(links[0].getAttribute("href"), "https://aws.amazon.com/athena/pricing/");
  assert.equal(links[0].getAttribute("rel"), "noopener noreferrer");
  assert.match(banner.textContent, /Serviço suspeito/);
  assert.ok(!banner.textContent.includes("evil.example"));
  assert.ok(!/US\$|USD/.test(root.textContent));
});

test("a Prática opcional mostra o selo e o aviso de custo reforçado", async () => {
  const lab = moduleLab({ resume_step: "t2" });
  const root = await mount(lab, "t2");
  const [banner] = optionalBanners(root);
  assert.ok(banner);
  assert.match(banner.textContent, /Opcional/);
  assert.match(banner.textContent, /Notebooks Spark cobram por DPU-hora\./);
  assert.match(banner.textContent, /não bloqueia a conclusão/);
  // Selo também no wizard, só no step opcional.
  const wizardBadges = findAll(root, (n) => n.className.startsWith("wizard__item")).filter((n) => badges(n).length > 0);
  assert.equal(wizardBadges.length, 1);
  assert.match(wizardBadges[0].textContent, /Tarefa t2/);
});

test("task obrigatória não mostra o selo nem o aviso de Prática opcional", async () => {
  const root = await mount(moduleLab({ resume_step: "t1" }), "t1");
  assert.equal(optionalBanners(root).length, 0);
});

test("finalizar o módulo não exige a Prática opcional, mas exige task e quiz", async () => {
  const lab = moduleLab({ resume_step: "fim" });
  for (const s of lab.steps) if (s.step_id !== "t2") s.status = "passed";
  let root = await mount(lab, "fim");
  findButton(root, "Finalizar Lab").click();
  await tick();
  assert.deepEqual(navigations, ["/"]);
  assert.equal(findAll(root, (n) => n.getAttribute("role") === "alert").length, 0);

  const pending = moduleLab({ resume_step: "fim" });
  for (const s of pending.steps) if (!["t2", "quiz"].includes(s.step_id)) s.status = "passed";
  root = await mount(pending, "fim");
  findButton(root, "Finalizar Lab").click();
  await tick();
  assert.deepEqual(navigations, []);
  const [alert] = findAll(root, (n) => n.getAttribute("role") === "alert");
  assert.match(alert.textContent, /Verificação/);
  assert.ok(!alert.textContent.includes("Tarefa t2"));
});

test("módulo sem infraestrutura não mostra Aviso de custo nem controles de stack", async () => {
  const lab = moduleLab({ has_infrastructure: false, cost_notice: {}, resume_step: "t1" });
  lab.steps = lab.steps.filter((s) => s.type !== "deploy");
  const root = await mount(lab, "t1");
  assert.equal(costBanners(root).length, 0);
  assert.equal(findAll(root, (n) => n.className === "deploy-panel").length, 0);
  assert.equal(findButton(root, "Iniciar deploy"), undefined);
});
