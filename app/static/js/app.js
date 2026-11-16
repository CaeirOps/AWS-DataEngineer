// Ponto de entrada da SPA: roteamento client-side com a History API.
//   /                     -> Dashboard
//   /lab/{id}             -> Lab (abre no step de retomada)
//   /lab/{id}/{step}      -> Step específico (somente se já visitado)

import { el, replaceContent } from "./dom.js";
import { renderDashboard } from "./dashboard.js";
import { renderLab } from "./lab.js";
import { stopAllPolling } from "./cloudformation.js";
import { initSession, resetGuards } from "./session.js";

const root = document.getElementById("app");
let renderTicket = 0;

function parseRoute(pathname) {
  const parts = pathname.split("/").filter(Boolean).map((p) => decodeURIComponent(p));
  if (parts.length === 0) return { name: "dashboard" };
  if (parts[0] === "lab" && parts.length >= 2 && parts.length <= 3) {
    return { name: "lab", labId: parts[1], stepId: parts[2] || null };
  }
  return { name: "not-found" };
}

export function navigate(url, { replace = false } = {}) {
  if (url !== location.pathname + location.search) {
    if (replace) history.replaceState(null, "", url);
    else history.pushState(null, "", url);
  }
  return render();
}

async function render() {
  const ticket = ++renderTicket;
  stopAllPolling();
  resetGuards();
  const route = parseRoute(location.pathname);
  replaceContent(root, el("p", { class: "loading" }, "Carregando..."));

  let view;
  if (route.name === "dashboard") {
    document.title = "Workshop AWS Data Engineer";
    view = await renderDashboard();
  } else if (route.name === "lab") {
    document.title = `${route.labId} | Workshop AWS Data Engineer`;
    view = await renderLab({ labId: route.labId, stepId: route.stepId, navigate });
  } else {
    view = el(
      "div",
      null,
      el("h1", null, "Página não encontrada"),
      el("a", { class: "btn", href: "/", "data-link": "" }, "Ir para o Dashboard")
    );
  }
  if (ticket !== renderTicket) return; // uma navegação mais nova assumiu
  replaceContent(root, view);
  window.scrollTo(0, 0);
  root.focus({ preventScroll: true });
}

document.addEventListener("click", (event) => {
  if (event.defaultPrevented || event.button !== 0) return;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const link = event.target.closest && event.target.closest("a[data-link]");
  if (!link || !link.getAttribute("href")) return;
  const url = new URL(link.href, location.origin);
  if (url.origin !== location.origin) return;
  event.preventDefault();
  navigate(url.pathname + url.search);
});

window.addEventListener("popstate", render);

initSession({
  timerElement: document.getElementById("session-timer"),
  bannerElement: document.getElementById("session-banner"),
});

render();
