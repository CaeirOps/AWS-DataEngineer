// Testes do cliente de API: cabeçalhos, corpo JSON e ponto único de `fetch`.
// Valida: Requisitos 13.1, 13.2, 13.3, 13.4.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const chamadas = [];
globalThis.fetch = async (url, options) => {
  chamadas.push({ url, options });
  return { ok: true, status: 200, json: async () => ({ ok: true }) };
};
const { api } = await import("../../app/static/js/api.js");

test.beforeEach(() => {
  chamadas.length = 0;
});

for (const metodo of ["POST", "PUT", "DELETE"]) {
  test(`${metodo} envia Content-Type, X-Workshop-Request e corpo JSON`, async () => {
    await api(metodo, "/api/x", { a: 1 });
    const { options } = chamadas[0];
    assert.equal(options.method, metodo);
    assert.equal(options.headers["Content-Type"], "application/json");
    assert.equal(options.headers["X-Workshop-Request"], "1");
    assert.equal(options.body, JSON.stringify({ a: 1 }));
  });

  test(`${metodo} sem corpo envia {}`, async () => {
    await api(metodo, "/api/x");
    assert.equal(chamadas[0].options.body, "{}");
  });
}

test("método em minúsculas também é tratado como mutação", async () => {
  await api("post", "/api/x", {});
  assert.equal(chamadas[0].options.headers["X-Workshop-Request"], "1");
});

test("GET não envia corpo nem cabeçalhos de mutação", async () => {
  await api("GET", "/api/x");
  const { options } = chamadas[0];
  assert.equal(options.method, "GET");
  assert.equal("body" in options, false);
  assert.equal("X-Workshop-Request" in options.headers, false);
  assert.equal("Content-Type" in options.headers, false);
});

test("nenhum outro módulo de app/static/js chama fetch", () => {
  const dir = join(dirname(fileURLToPath(import.meta.url)), "../../app/static/js");
  const arquivos = readdirSync(dir).filter((f) => f.endsWith(".js") && f !== "api.js");
  assert.ok(arquivos.length > 0);
  for (const arquivo of arquivos) {
    const codigo = readFileSync(join(dir, arquivo), "utf8")
      // Ignora comentários de bloco e de linha.
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/^\s*\/\/.*$/gm, "");
    assert.doesNotMatch(codigo, /\bfetch\s*\(/, `${arquivo} chama fetch`);
    assert.doesNotMatch(codigo, /\bXMLHttpRequest\b/, `${arquivo} usa XMLHttpRequest`);
  }
});
