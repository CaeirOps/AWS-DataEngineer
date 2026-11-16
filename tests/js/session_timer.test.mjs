// Testes de DOM do cronômetro da sessão AWS (Requirements 12.2, 12.4 e 12.5).
// Usa o DOM falso de `fake_dom.mjs` e relógio/timers falsos de `node:test`.
// O módulo `session.js` guarda estado global, então cada teste importa uma cópia nova.

import test, { mock } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { FakeElement, findAll, findButton, installGlobals } from "./fake_dom.mjs";

let currentFetch;
let fetchCalls;
let clipboardWrites;

installGlobals({
  onReplaceState: () => {},
  fetchImpl: (url, options) => currentFetch(url, options),
});
Object.defineProperty(globalThis, "navigator", {
  value: { clipboard: { writeText: async (text) => clipboardWrites.push(text) } },
  configurable: true,
  writable: true,
});

const jsonResponse = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });
// `setImmediate` não é simulado, então serve para esperar as promessas pendentes.
const flush = async () => {
  for (let i = 0; i < 5; i += 1) await new Promise((resolve) => setImmediate(resolve));
};
const advance = async (ms) => {
  mock.timers.tick(ms);
  await flush();
};

let importCounter = 0;
/**
 * Prepara timers falsos, o fetch simulado e uma cópia nova de `session.js`.
 * `responses` é a fila de corpos de `/api/session`; o último se repete.
 */
async function setup(responses) {
  mock.timers.enable({ apis: ["setInterval", "setTimeout", "Date"], now: 1_000_000 });
  fetchCalls = [];
  clipboardWrites = [];
  const queue = [...responses];
  currentFetch = async (url) => {
    fetchCalls.push(url);
    const body = queue.length > 1 ? queue.shift() : queue[0];
    return jsonResponse(body);
  };
  importCounter += 1;
  const session = await import(`../../app/static/js/session.js?case=${importCounter}`);
  const timerElement = new FakeElement("span");
  const bannerElement = new FakeElement("div");
  bannerElement.hidden = true;
  await session.initSession({ timerElement, bannerElement });
  return { session, timerElement, bannerElement };
}

const state = (seconds, status) => ({
  expires_at: "2030-01-01T12:00:00Z",
  seconds_remaining: seconds,
  status,
});

test.afterEach(() => mock.timers.reset());

test("sincroniza com /api/session no início e a cada 60 s", async () => {
  await setup([state(7200, "valid")]);
  assert.deepEqual(fetchCalls, ["/api/session"]);
  await advance(59_000);
  assert.equal(fetchCalls.length, 1);
  await advance(1_000);
  assert.equal(fetchCalls.length, 2);
  await advance(60_000);
  assert.equal(fetchCalls.length, 3);
});

test("conta localmente entre as sincronizações e reajusta pelo servidor", async () => {
  const { timerElement } = await setup([state(3700, "valid"), state(3000, "valid")]);
  assert.equal(timerElement.textContent, "Sessão AWS: 1:01:40");
  await advance(5_000);
  assert.equal(timerElement.textContent, "Sessão AWS: 1:01:35");
  assert.equal(fetchCalls.length, 1);
  await advance(55_000);
  // Nova resposta do servidor: 3000 s (50:00) no instante da sincronização.
  assert.equal(fetchCalls.length, 2);
  assert.equal(timerElement.textContent, "Sessão AWS: 50:00");
});

test("sessão válida não mostra aviso nem bloqueia ações", async () => {
  const { session, bannerElement } = await setup([state(7200, "valid")]);
  const button = session.guardAction(new FakeElement("button"));
  assert.equal(bannerElement.hidden, true);
  assert.equal(button.disabled, false);
});

test("com 10 minutos ou menos mostra aviso e o contêiner do aviso tem aria-live", async () => {
  const { session, timerElement, bannerElement } = await setup([state(601, "valid")]);
  assert.equal(bannerElement.hidden, true);
  await advance(1_000);
  assert.equal(session.sessionStatus(), "expiring");
  assert.equal(bannerElement.hidden, false);
  assert.match(bannerElement.textContent, /Sessão AWS expirando/);
  assert.match(bannerElement.textContent, /Restam 10:00/);
  assert.match(bannerElement.textContent, /python start\.py --refresh/);
  assert.match(timerElement.textContent, /\(expirando\)/);
  assert.equal(timerElement.className, "session-timer session-timer--expiring");

  // O banner real é o `#session-banner` do index.html, que deve ser uma região aria-live.
  const html = readFileSync(new URL("../../app/static/index.html", import.meta.url), "utf8");
  const tag = html.match(/<div[^>]*id="session-banner"[^>]*>/);
  assert.ok(tag, "index.html deve conter #session-banner");
  assert.match(tag[0], /aria-live="polite"/);
});

test("ao expirar pelo servidor bloqueia Validar, Deploy e Teardown e mostra o comando", async () => {
  const { session, bannerElement } = await setup([state(2, "expiring")]);
  const buttons = ["Validar", "Deploy", "Teardown"].map((label) => {
    const button = new FakeElement("button");
    button.textContent = label;
    return session.guardAction(button);
  });
  assert.ok(buttons.every((b) => !b.disabled));

  await advance(2_000);
  assert.equal(session.isSessionExpired(), true);
  for (const button of buttons) {
    assert.equal(button.disabled, true);
    assert.equal(button.getAttribute("title"), session.EXPIRED_REASON);
  }
  assert.equal(bannerElement.hidden, false);
  assert.equal(bannerElement.getAttribute("role"), null);
  const banner = bannerElement.children[0];
  assert.equal(banner.getAttribute("role"), "alert");
  assert.match(bannerElement.textContent, /Sessão AWS expirada/);
  const code = findAll(bannerElement, (n) => n.tag === "code")[0];
  assert.equal(code.textContent, "python start.py --refresh");
  assert.ok(findButton(bannerElement, "Copiar comando"));
});

test("botão de copiar grava o comando de renovação na área de transferência", async () => {
  const { bannerElement } = await setup([state(0, "expired")]);
  const copy = findButton(bannerElement, "Copiar comando");
  copy.click();
  await flush();
  assert.deepEqual(clipboardWrites, ["python start.py --refresh"]);
  assert.equal(copy.textContent, "Copiado");
  await advance(3_000);
  assert.equal(copy.textContent, "Copiar comando");
});

test("401 SESSION_EXPIRED de qualquer rota expira a sessão antes da próxima sincronização", async () => {
  const { session, bannerElement } = await setup([state(3000, "valid")]);
  const { api } = await import("../../app/static/js/api.js");
  const button = session.guardAction(new FakeElement("button"));
  assert.equal(button.disabled, false);

  currentFetch = async () =>
    jsonResponse(
      { error: true, code: "SESSION_EXPIRED", message: "Sessão AWS expirada.", http_status: 401 },
      401
    );
  const err = await api("POST", "/api/validate/lab-01/t1", {}).catch((e) => e);
  assert.equal(session.reportApiError(err), true);

  assert.equal(session.sessionStatus(), "expired");
  assert.equal(button.disabled, true);
  assert.equal(button.getAttribute("title"), session.EXPIRED_REASON);
  assert.equal(bannerElement.hidden, false);
  assert.match(bannerElement.textContent, /python start\.py --refresh/);
});

test("outros erros da API não expiram a sessão", async () => {
  const { session } = await setup([state(3000, "valid")]);
  assert.equal(session.reportApiError({ code: "INVALID_PAYLOAD" }), false);
  assert.equal(session.sessionStatus(), "valid");
});

test("depois de renovar, a próxima sincronização reabilita as ações", async () => {
  const { session, bannerElement } = await setup([state(0, "expired"), state(3600, "valid")]);
  const button = session.guardAction(new FakeElement("button"));
  assert.equal(button.disabled, true);
  await advance(60_000);
  assert.equal(session.sessionStatus(), "valid");
  assert.equal(button.disabled, false);
  assert.equal(bannerElement.hidden, true);
});
