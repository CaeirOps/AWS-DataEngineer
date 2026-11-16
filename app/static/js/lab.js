// Tela de lab: wizard de steps, abas Console | CLI, validação e deploy/teardown.

import { api } from "./api.js";
import { el, errorBanner, errorMessage, replaceContent, formatCost, domainBadge, difficultyBadge } from "./dom.js";
import { renderMarkdown } from "./markdown.js";
import { PATHS, getProgress, preferredPathOf, setPreferredPath, visitStep } from "./progress.js";
import { createValidatorPanel } from "./validator.js";
import { createDeployPanel, createTeardownPanel } from "./cloudformation.js";

const enc = encodeURIComponent;
const PATH_LABELS = { console: "Console", cli: "CLI" };

const stepUrl = (labId, stepId) => `/lab/${enc(labId)}/${enc(stepId)}`;

function listOf(value) {
  if (Array.isArray(value)) return value;
  return [];
}

function itemText(item) {
  if (item && typeof item === "object") return item.title || item.name || item.description || JSON.stringify(item);
  return String(item);
}

function prerequisitesView(prerequisites) {
  const groups = [];
  if (Array.isArray(prerequisites)) {
    groups.push(["Pré-requisitos", prerequisites]);
  } else if (prerequisites && typeof prerequisites === "object") {
    groups.push(["Pré-requisitos obrigatórios", listOf(prerequisites.hard)]);
    groups.push(["Pré-requisitos recomendados", listOf(prerequisites.recommended)]);
  }
  const visible = groups.filter(([, items]) => items.length > 0);
  return el(
    "section",
    { "aria-label": "Pré-requisitos" },
    visible.length === 0
      ? el("p", { class: "card__meta" }, "Este lab não declara pré-requisitos adicionais.")
      : visible.map(([title, items]) =>
          el("div", null, el("h3", null, title), el("ul", { class: "checklist" }, items.map((i) => el("li", null, itemText(i)))))
        )
  );
}

function overviewView(lab) {
  return el(
    "section",
    { class: "banner banner--info", "aria-label": "Visão geral do lab" },
    el("div", { class: "banner__title" }, "Visão geral"),
    el("p", null, lab.description),
    el(
      "p",
      null,
      `Duração estimada: ${lab.estimated_duration_minutes} min. Custo estimado: ${formatCost(lab.estimated_cost_usd)}.`
    ),
    el(
      "p",
      null,
      el("strong", null, "Tasks DEA-C01 cobertas: "),
      listOf(lab.dea_tasks).length > 0 ? listOf(lab.dea_tasks).join(", ") : "n/d"
    ),
    prerequisitesView(lab.prerequisites)
  );
}

function costBanner(lab) {
  return el(
    "div",
    { class: "banner banner--cost", role: "note" },
    el("div", { class: "banner__title" }, "Aviso de custos"),
    el("p", null, `Custo estimado deste lab: ${formatCost(lab.estimated_cost_usd)}.`),
    el("p", null, lab.cost_disclaimer || "Os recursos provisionados neste lab podem gerar custos na sua conta AWS.")
  );
}

/** Seção de abas e conteúdo de um step `task`. */
function taskView(lab, step, preferred, onValidated) {
  const available = listOf(step.paths);
  const unavailable = step.unavailable_paths || {};
  // Preferência indisponível neste step: abre a outra Trilha sem alterar a preferência salva.
  let active = available.includes(preferred) ? preferred : available[0];

  const content = el("div", { id: "path-content", role: "tabpanel", "aria-live": "polite" });
  const notice = el("div");
  let contentTicket = 0;

  const validator = createValidatorPanel({
    labId: lab.lab_id,
    step,
    getPath: () => active,
    onResult: onValidated,
  });

  const tabs = el("div", { class: "tabs", role: "tablist", "aria-label": "Trilha de instruções" });
  const tabButtons = new Map();

  function syncTabs() {
    for (const [path, button] of tabButtons) {
      const selected = path === active;
      button.setAttribute("aria-selected", String(selected));
      button.tabIndex = selected ? 0 : -1;
    }
  }

  async function loadContent() {
    const ticket = ++contentTicket;
    replaceContent(content, el("p", { class: "loading" }, "Carregando instruções..."));
    try {
      const data = await api(
        "GET",
        `/api/labs/${enc(lab.lab_id)}/steps/${enc(step.step_id)}/content?path=${enc(active)}`
      );
      if (ticket !== contentTicket) return;
      replaceContent(content, renderMarkdown(data.markdown));
    } catch (err) {
      if (ticket !== contentTicket) return;
      replaceContent(content, errorBanner(err, "Não foi possível carregar as instruções"));
    }
  }

  async function selectPath(path) {
    if (path === active) return;
    active = path;
    syncTabs();
    replaceContent(notice);
    loadContent();
    validator.refreshHint();
    try {
      await setPreferredPath(path);
    } catch (err) {
      replaceContent(notice, errorBanner(err, "Não foi possível salvar a Trilha preferida"));
    }
  }

  for (const path of PATHS) {
    const isAvailable = available.includes(path);
    const reason = unavailable[path] || "Trilha indisponível neste step.";
    const button = el(
      "button",
      {
        type: "button",
        class: "tab",
        role: "tab",
        "aria-controls": "path-content",
        "aria-disabled": isAvailable ? null : "true",
        "data-reason": isAvailable ? null : reason,
        title: isAvailable ? null : reason,
      },
      isAvailable ? PATH_LABELS[path] : `${PATH_LABELS[path]} (indisponível)`
    );
    button.addEventListener("click", () => {
      if (!isAvailable) return;
      selectPath(path);
    });
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      const enabled = PATHS.filter((p) => available.includes(p));
      const next = enabled[(enabled.indexOf(active) + 1) % enabled.length];
      if (next && next !== active) {
        event.preventDefault();
        selectPath(next);
        tabButtons.get(next).focus();
      }
    });
    tabButtons.set(path, button);
    tabs.append(button);
  }
  syncTabs();

  const unavailableNotes = PATHS.filter((p) => !available.includes(p)).map((p) =>
    el(
      "p",
      { class: "tab-note" },
      `Trilha ${PATH_LABELS[p]} indisponível neste step: ${unavailable[p] || "sem motivo informado."}`
    )
  );

  loadContent();
  return el("div", null, tabs, unavailableNotes, notice, content, validator.node);
}

function completionView(lab) {
  const tasks = lab.steps.filter((s) => s.type === "task");
  return el(
    "section",
    { "aria-label": "Resumo do lab" },
    el("h3", null, "Resumo"),
    el("p", null, el("strong", null, "Domínios DEA-C01: "), listOf(lab.dea_domains).map(domainBadge)),
    el(
      "p",
      null,
      el("strong", null, "Tasks DEA-C01: "),
      listOf(lab.dea_tasks).length > 0 ? listOf(lab.dea_tasks).join(", ") : "n/d"
    ),
    el(
      "p",
      null,
      el("strong", null, "Serviços AWS: "),
      listOf(lab.services).length > 0
        ? el("span", { class: "badge-list" }, listOf(lab.services).map((s) => el("span", { class: "badge" }, itemText(s))))
        : "n/d"
    ),
    el("h3", null, "Tarefas do lab"),
    el(
      "ul",
      { class: "checklist" },
      tasks.map((t) => el("li", null, `${t.status === "passed" ? "\u2713" : "\u2022"} ${t.title}`))
    )
  );
}

function wizardItemStatus(step, index, current) {
  if (step.status === "passed" || step.status === "failed") return step.status;
  return index === current ? "in_progress" : "not_visited";
}

export async function renderLab({ labId, stepId, navigate }) {
  let lab;
  let progress;
  try {
    [lab, progress] = await Promise.all([api("GET", `/api/labs/${enc(labId)}`), getProgress()]);
  } catch (err) {
    return el(
      "div",
      null,
      el("a", { class: "back-link", href: "/", "data-link": "" }, "\u2190 Voltar ao Dashboard"),
      errorBanner(err, "Não foi possível carregar o lab")
    );
  }

  const steps = lab.steps;
  const last = steps.length - 1;
  let resume = steps.findIndex((s) => s.step_id === lab.resume_step);
  if (resume < 0) resume = lab.status === "completed" ? last : 0;

  // Navegável: step já visitado/validado (status do servidor) ou step de retomada.
  const isReachable = (i) =>
    lab.status === "completed" || steps[i].status !== "not_visited" || i === resume;

  let index = stepId ? steps.findIndex((s) => s.step_id === stepId) : resume;
  if (index < 0 || !isReachable(index)) {
    // Step inexistente ou ainda não visitado: volta ao ponto de retomada.
    index = resume;
    history.replaceState(null, "", stepUrl(labId, steps[index].step_id));
  } else if (!stepId) {
    history.replaceState(null, "", stepUrl(labId, steps[index].step_id));
  }

  const step = steps[index];
  const preferred = preferredPathOf(progress);

  // --- Wizard ---
  const wizard = el("ol", { class: "wizard", "aria-label": "Steps do lab" });
  function buildWizard() {
    replaceContent(
      wizard,
      steps.map((s, i) => {
        const status = wizardItemStatus(s, i, index);
        const reachable = i === index || isReachable(i);
        const icon = status === "passed" ? "\u2713" : status === "failed" ? "!" : String(i + 1);
        const link = el(
          reachable ? "a" : "span",
          {
            class: "wizard__link",
            href: reachable ? stepUrl(labId, s.step_id) : null,
            "data-link": reachable ? "" : null,
            "aria-current": i === index ? "step" : null,
            "aria-disabled": reachable ? null : "true",
          },
          el("span", { class: "wizard__icon", "aria-hidden": "true" }, icon),
          el("span", null, s.title)
        );
        return el("li", { class: `wizard__item wizard__item--${status}` }, link);
      })
    );
  }
  buildWizard();

  // --- Painel do step ---
  const panel = el("section", { class: "step-panel", "aria-labelledby": "step-title" });
  panel.append(
    el("p", { class: "card__meta" }, `Step ${index + 1} de ${steps.length}`),
    el("h2", { id: "step-title" }, step.title)
  );

  const hasDeploy = steps.some((s) => s.type === "deploy");
  const firstTask = steps.findIndex((s) => s.type === "task");
  if (step.type === "deploy" || (!hasDeploy && index === firstTask)) panel.append(costBanner(lab));

  if (step.type === "task") {
    panel.append(
      taskView(lab, step, preferred, (result) => {
        step.status = result.step_status;
        step.attempts = result.attempt_count;
        buildWizard();
      })
    );
  } else {
    panel.append(renderMarkdown(step.content));
    if (step.type === "deploy") panel.append(createDeployPanel(labId).node);
    if (step.type === "teardown") panel.append(createTeardownPanel(labId).node);
    if (step.type === "completion") panel.append(completionView(lab));
  }

  // --- Navegação ---
  const warning = el("div");
  const prev = el("button", { type: "button", class: "btn", disabled: index === 0 }, "Anterior");
  prev.addEventListener("click", () => {
    if (index > 0) navigate(stepUrl(labId, steps[index - 1].step_id));
  });
  const isLast = index === last;
  const next = el("button", { type: "button", class: "btn btn--primary" }, isLast ? "Finalizar Lab" : "Avançar");
  let busy = false;
  next.addEventListener("click", async () => {
    if (busy) return;
    if (isLast) {
      const pending = steps.filter((s) => s.type === "task" && s.status !== "passed");
      if (pending.length > 0) {
        replaceContent(
          warning,
          el(
            "div",
            { class: "banner banner--warning", role: "alert" },
            el("div", { class: "banner__title" }, "Ainda há tarefas sem validação"),
            el("ul", null, pending.map((s) => el("li", null, s.title)))
          )
        );
        return;
      }
    }
    if (step.type !== "task") {
      busy = true;
      next.disabled = true;
      try {
        const result = await visitStep(labId, step.step_id);
        step.status = result.step_status;
        step.attempts = result.attempt_count;
        lab.status = result.lab_status;
        lab.resume_step = result.resume_step;
        buildWizard();
      } catch (err) {
        busy = false;
        next.disabled = false;
        replaceContent(warning, errorBanner(err, "Não foi possível registrar o avanço"));
        return;
      }
      busy = false;
      next.disabled = false;
    }
    replaceContent(warning);
    navigate(isLast ? "/" : stepUrl(labId, steps[index + 1].step_id));
  });
  panel.append(warning, el("div", { class: "step-nav" }, prev, next));

  // --- Cabeçalho ---
  const header = el(
    "div",
    null,
    el("a", { class: "back-link", href: "/", "data-link": "" }, "\u2190 Voltar ao Dashboard"),
    el("h1", null, lab.title),
    el("div", { class: "badge-list" }, difficultyBadge(lab.difficulty), listOf(lab.dea_domains).map(domainBadge))
  );

  return el(
    "div",
    null,
    header,
    index === 0 ? overviewView(lab) : null,
    el("div", { class: "lab-layout" }, wizard, panel)
  );
}

export { errorMessage };
