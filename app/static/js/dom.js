// Utilitários de DOM. Nunca usa innerHTML: todo texto vindo
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
