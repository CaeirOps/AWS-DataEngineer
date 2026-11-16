// Utilitários de DOM e de chamada à API. Nunca usa innerHTML: todo texto vindo
// da API entra no DOM como nó de texto.

/** Cria um elemento. `attrs` aceita class, dataset, aria-*, on* (funções) e atributos comuns. */
export function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, String(value));
  }
  append(node, children);
  return node;
}

export function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function replaceContent(node, ...children) {
  clear(node);
  return append(node, children);
}

/** Erro da API com o schema `{error, code, message, http_status}`. */
export class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

/** Chamada JSON à API. Lança ApiError com a mensagem original do servidor. */
export async function api(method, url, body) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(url, options);
  } catch (err) {
    throw new ApiError(
      "Não foi possível conectar ao servidor do workshop. Verifique se os containers estão em execução.",
      "NETWORK_ERROR",
      0
    );
  }
  let data = null;
  try {
    data = await response.json();
  } catch (err) {
    data = null;
  }
  if (!response.ok || (data && data.error === true)) {
    const message =
      (data && data.message) || `Erro ${response.status} ao acessar ${url}.`;
    throw new ApiError(message, data && data.code, response.status);
  }
  return data;
}

export function errorMessage(err) {
  return err && err.message ? err.message : "Erro inesperado.";
}

/** Banner de erro com a mensagem da API (inclui a mensagem original de credenciais). */
export function errorBanner(err, title) {
  return el(
    "div",
    { class: "banner banner--error", role: "alert" },
    el("div", { class: "banner__title" }, title || "Ocorreu um erro"),
    el("div", null, errorMessage(err)),
    err && err.code ? el("div", { class: "card__meta" }, `Código: ${err.code}`) : null
  );
}

export function formatCost(usd) {
  const value = Number(usd);
  if (!Number.isFinite(value)) return "n/d";
  return `US$ ${value.toFixed(2)}`;
}

export function domainBadge(domain) {
  const key = String(domain).toLowerCase();
  const cls = /^d[1-4]$/.test(key) ? ` badge--${key}` : "";
  return el("span", { class: `badge${cls}`, title: "Domínio DEA-C01" }, domain);
}

export function difficultyBadge(difficulty) {
  const key = String(difficulty || "").toLowerCase();
  const known = ["iniciante", "intermediario", "avancado"].includes(key);
  const labels = { iniciante: "Iniciante", intermediario: "Intermediário", avancado: "Avançado" };
  return el(
    "span",
    { class: `badge${known ? ` badge--${key}` : ""}` },
    labels[key] || difficulty || "n/d"
  );
}
