// DOM falso mínimo compartilhado pelos testes de tela (sem jsdom).

// ---------------------------------------------------------------- DOM falso

export class FakeNode {}

class FakeText extends FakeNode {
  constructor(data) {
    super();
    this.data = data;
  }
  get textContent() {
    return this.data;
  }
}

export class FakeElement extends FakeNode {
  constructor(tag) {
    super();
    this.tag = tag;
    this.attrs = new Map();
    this.children = [];
    this.listeners = new Map();
    this.dataset = {};
    this.className = "";
    this.tabIndex = 0;
    this.value = "";
  }
  setAttribute(name, value) {
    this.attrs.set(name, String(value));
  }
  getAttribute(name) {
    return this.attrs.has(name) ? this.attrs.get(name) : null;
  }
  get hidden() {
    return this.attrs.has("hidden");
  }
  set hidden(value) {
    if (value) this.attrs.set("hidden", "");
    else this.attrs.delete("hidden");
  }
  get disabled() {
    return this.attrs.has("disabled");
  }
  set disabled(value) {
    if (value) this.attrs.set("disabled", "");
    else this.attrs.delete("disabled");
  }
  get title() {
    return this.getAttribute("title");
  }
  get firstChild() {
    return this.children[0] || null;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.children.push(typeof node === "string" ? new FakeText(node) : node);
    }
  }
  removeChild(node) {
    this.children.splice(this.children.indexOf(node), 1);
    return node;
  }
  get textContent() {
    return this.children.map((c) => c.textContent).join("");
  }
  set textContent(value) {
    this.children = [new FakeText(String(value))];
  }
  addEventListener(type, fn) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(fn);
  }
  dispatch(type, extra) {
    const event = { type, target: this, preventDefault() {}, ...extra };
    for (const fn of this.listeners.get(type) || []) fn(event);
  }
  click() {
    if (this.disabled) return;
    this.dispatch("click");
  }
  focus() {}
}

export function walk(node, visit) {
  visit(node);
  for (const child of node.children || []) walk(child, visit);
}

export function findAll(root, predicate) {
  const found = [];
  walk(root, (n) => {
    if (n instanceof FakeElement && predicate(n)) found.push(n);
  });
  return found;
}

export const findTab = (root, label) =>
  findAll(root, (n) => n.getAttribute("role") === "tab").find((n) => n.textContent.startsWith(label));
export const findButton = (root, text) =>
  findAll(root, (n) => n.tag === "button" && n.textContent === text)[0];

/**
 * Instala o DOM falso em `globalThis`. `sessionStorage` e `localStorage`
 * ficam de fora de propósito: qualquer uso quebra o teste.
 */
export function installGlobals({ onReplaceState, fetchImpl }) {
  const define = (name, value) =>
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  define("Node", FakeNode);
  define("document", {
    createElement: (tag) => new FakeElement(tag),
    createTextNode: (data) => new FakeText(String(data)),
    body: new FakeElement("body"),
    addEventListener() {},
    removeEventListener() {},
  });
  define("history", { replaceState: (...args) => onReplaceState(...args) });
  define("fetch", (url, options) => fetchImpl(url, options || {}));
}
