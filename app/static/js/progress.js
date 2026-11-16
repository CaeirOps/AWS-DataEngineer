// Acesso ao progresso via API e controle de steps alcançados na sessão.

import { api } from "./api.js";

export const PATHS = ["console", "cli"];

export function getProgress() {
  return api("GET", "/api/progress");
}

/** Trilha preferida; `console` quando o arquivo não tem preferências. */
export function preferredPathOf(progress) {
  const path = progress && progress.preferences && progress.preferences.path;
  return PATHS.includes(path) ? path : "console";
}

export function setPreferredPath(path) {
  return api("PUT", "/api/progress", { preferences: { path } });
}

/** Registra a visita a um step que não é `task`; devolve a resposta da API. */
export function visitStep(labId, stepId) {
  return api(
    "POST",
    `/api/labs/${encodeURIComponent(labId)}/steps/${encodeURIComponent(stepId)}/visit`
  );
}
