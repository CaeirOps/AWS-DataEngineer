// Dashboard: lista os labs com progresso e ponto de retomada.

import { api } from "./api.js";
import { el, errorBanner, domainBadge, difficultyBadge } from "./dom.js";

const STATUS_LABELS = {
  completed: "Concluído",
  in_progress: "Em andamento",
  not_started: "Não iniciado",
};

function labCard(lab) {
  const total = lab.total_steps || 0;
  const done = lab.completed_steps || 0;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  const status = lab.status || "not_started";
  const action =
    status === "completed" ? "Revisar" : status === "in_progress" ? "Continuar" : "Iniciar";

  const bar = el("div", {
    class: "progress__bar",
  });
  bar.style.width = `${percent}%`;

  return el(
    "article",
    { class: "card" },
    el("h2", { class: "card__title" }, lab.title),
    el(
      "div",
      { class: "badge-list" },
      difficultyBadge(lab.difficulty),
      (lab.dea_domains || []).map(domainBadge),
      el("span", { class: `badge badge--status-${status}` }, STATUS_LABELS[status] || status)
    ),
    el("p", { class: "card__body" }, lab.description),
    el(
      "p",
      { class: "card__meta" },
      `${lab.estimated_duration_minutes} min`
    ),
    el(
      "div",
      null,
      el(
        "div",
        {
          class: "progress",
          role: "progressbar",
          "aria-valuemin": "0",
          "aria-valuemax": String(total),
          "aria-valuenow": String(done),
          "aria-label": `Progresso de ${lab.title}`,
        },
        bar
      ),
      el("div", { class: "progress__label" }, `${done} de ${total} steps concluídos`)
    ),
    el(
      "div",
      { class: "card__footer" },
      el(
        "a",
        { class: "btn btn--primary", href: `/lab/${encodeURIComponent(lab.lab_id)}`, "data-link": "" },
        action
      )
    )
  );
}

export async function renderDashboard() {
  const view = el("div", null, el("h1", null, "Labs do workshop"));
  try {
    const data = await api("GET", "/api/labs");
    const labs = data.labs || [];
    if (labs.length === 0) {
      view.append(el("p", null, "Nenhum lab disponível no catálogo."));
    } else {
      const done = labs.filter((lab) => lab.status === "completed").length;
      view.append(
        el("p", { class: "card__meta" }, `${done} de ${labs.length} labs concluídos`),
        el("div", { class: "card-grid" }, labs.map(labCard))
      );
    }
  } catch (err) {
    view.append(errorBanner(err, "Não foi possível carregar os labs"));
  }
  return view;
}
