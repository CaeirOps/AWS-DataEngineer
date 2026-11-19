// Testes do renderizador de Markdown: Destaques e imagens locais (task 15M.3).
// **Property 27: Imagens do conteúdo são sempre locais**
// Valida: Requirements 4.7, 4.8, 8.2.
import test from "node:test";
import assert from "node:assert/strict";
import { FakeElement, findAll, installGlobals } from "./fake_dom.mjs";

installGlobals({ onReplaceState() {}, fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({}) }) });
const { renderMarkdown, localImageSrc, CALLOUTS } = await import("../../app/static/js/markdown.js");

const LAB = "lab-03";
const imgs = (root) => findAll(root, (n) => n.tag === "img");
const asides = (root) => findAll(root, (n) => n.tag === "aside");
const tags = (root) => findAll(root, () => true).map((n) => n.tag);

// ---------------------------------------------------------------- escape

test("texto com HTML vira nó de texto, sem gerar tags", () => {
  const root = renderMarkdown('<script>alert(1)</script> <img src=x onerror=alert(1)>\n\n> [!TIP] <b>x</b>', { labId: LAB });
  assert.ok(root.textContent.includes("<script>alert(1)</script>"));
  assert.ok(root.textContent.includes("<b>x</b>"));
  for (const tag of tags(root)) assert.ok(!["script", "img", "b"].includes(tag), tag);
});

// ---------------------------------------------------------------- Destaques

for (const [marker, title] of Object.entries({ EXAM: "Na prova", COST: "Custo", TIP: "Boas práticas", WARNING: "Atenção" })) {
  test(`> [!${marker}] vira aside.callout--${marker.toLowerCase()} com o título "${title}"`, () => {
    assert.equal(CALLOUTS[marker], title);
    const root = renderMarkdown(`> [!${marker}] Primeira linha com **negrito**.\n> Segunda linha.`);
    const [aside] = asides(root);
    assert.ok(aside, "aside ausente");
    assert.equal(aside.className, `callout callout--${marker.toLowerCase()}`);
    assert.equal(aside.getAttribute("role"), "note");
    const [titleNode] = findAll(aside, (n) => n.className === "callout__title");
    assert.equal(titleNode.textContent, title);
    const body = findAll(aside, (n) => n.className === "callout__body")[0];
    assert.match(body.textContent, /Primeira linha com negrito\. Segunda linha\./);
    assert.equal(findAll(aside, (n) => n.tag === "strong").length, 1);
    assert.ok(!body.textContent.includes("[!"));
  });
}

test("marcador sozinho na primeira linha usa as linhas seguintes como corpo", () => {
  const [aside] = asides(renderMarkdown("> [!COST]\n> O Athena cobra por TB escaneado."));
  assert.match(aside.textContent, /^CustoO Athena cobra por TB escaneado\.$/);
});

for (const source of ["> [!NOTE] texto", "> [!exam] texto", "> [!CONSTRUCTOR] texto", "> texto comum", "> [!EXAM texto"]) {
  test(`marcador desconhecido ou malformado vira citação comum: ${source}`, () => {
    const root = renderMarkdown(source);
    assert.equal(asides(root).length, 0);
    assert.equal(findAll(root, (n) => n.tag === "blockquote").length, 1);
    assert.equal(root.textContent, source.slice(2));
  });
}

// ---------------------------------------------------------------- imagens

test("imagem local com texto alternativo vira <img> com src da rota de assets", () => {
  const [img] = imgs(renderMarkdown("Veja ![Fluxo do pipeline](assets/pipeline-01.svg) abaixo.", { labId: LAB }));
  assert.equal(img.getAttribute("src"), "/api/labs/lab-03/assets/pipeline-01.svg");
  assert.equal(img.getAttribute("alt"), "Fluxo do pipeline");
  assert.equal(imgs(renderMarkdown("![Diagrama](assets/d.png)", { labId: LAB })).length, 1);
});

const REJECTED = [
  "https://example.com/a.svg",
  "http://example.com/a.png",
  "//example.com/a.svg",
  "data:image/svg+xml;base64,PHN2Zz4=",
  "javascript:alert`1`",
  "assets/../metadata.json",
  "assets/../../x.svg",
  "assets/sub/a.svg",
  "assets//a.svg",
  "assets\\a.svg",
  "assets/a.svg?x=1",
  "assets/a.svg#frag",
  "assets/c:a.svg",
  "/assets/a.svg",
  "./assets/a.svg",
  "assets/a.gif",
  "assets/a.SVG",
  "assets/a.svg.html",
  "assets/.svg",
  "img/a.svg",
  "a.svg",
];
for (const path of REJECTED) {
  test(`imagem recusada mostra só o texto alternativo: ${path}`, () => {
    const root = renderMarkdown(`![Alt](${path})`, { labId: LAB });
    assert.equal(imgs(root).length, 0);
    assert.equal(root.textContent, "Alt");
  });
}

test("texto alternativo vazio recusa a imagem", () => {
  for (const alt of ["", "   "]) {
    const root = renderMarkdown(`![${alt}](assets/a.svg)`, { labId: LAB });
    assert.equal(imgs(root).length, 0);
  }
});

test("sem labId válido nenhuma imagem é gerada", () => {
  for (const labId of [undefined, "", "../lab", "lab/01", 3]) {
    assert.equal(imgs(renderMarkdown("![Alt](assets/a.svg)", { labId })).length, 0);
  }
});

test("imagens em listas, tabelas, Destaques e negrito também seguem a regra", () => {
  const md = [
    "- ![Lista](assets/a.svg)",
    "",
    "| A |",
    "| --- |",
    "| ![Tabela](assets/b.png) |",
    "",
    "> [!TIP] ![Destaque](assets/c.svg) e ![Externa](https://x.example/c.svg)",
    "",
    "**![Negrito](assets/d.svg)**",
  ].join("\n");
  const found = imgs(renderMarkdown(md, { labId: LAB })).map((n) => n.getAttribute("src"));
  assert.deepEqual(found, [
    "/api/labs/lab-03/assets/a.svg",
    "/api/labs/lab-03/assets/b.png",
    "/api/labs/lab-03/assets/c.svg",
    "/api/labs/lab-03/assets/d.svg",
  ]);
});

// ---------------------------------------------------------------- Property 27

// Gerador pseudoaleatório com semente fixa: o teste é reproduzível.
function rng(seed) {
  let x = seed >>> 0;
  return () => {
    x ^= x << 13; x >>>= 0;
    x ^= x >>> 17;
    x ^= x << 5; x >>>= 0;
    return x / 0x100000000;
  };
}
const PIECES = ["assets/", "a", "Z", "0", "-", "_", ".", "..", "/", "//", "\\", ":", "?", "#", "%2e", "svg", "png", ".svg", ".png", "http:", "https://", "data:", " ", "~", "é"];
const ASSET_RULE = /^assets\/[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.(svg|png)$/;

test("Property 27: para qualquer caminho, <img> só sai de assets/ local e aponta para a rota", () => {
  const next = rng(27);
  const pick = (list) => list[Math.floor(next() * list.length)];
  let accepted = 0;
  for (let i = 0; i < 3000; i += 1) {
    const n = 1 + Math.floor(next() * 6);
    let path = next() < 0.5 ? "assets/" : "";
    for (let j = 0; j < n; j += 1) path += pick(PIECES);
    const root = renderMarkdown(`texto ![alt ${i}](${path}) fim`, { labId: LAB });
    const found = imgs(root);
    const valid = ASSET_RULE.test(path);
    assert.equal(localImageSrc(path, LAB) !== null, valid, path);
    if (path.includes(" ") || path.includes(")")) continue; // não é sintaxe de imagem
    assert.equal(found.length, valid ? 1 : 0, path);
    for (const img of found) {
      accepted += 1;
      assert.ok(img.getAttribute("src").startsWith(`/api/labs/${LAB}/assets/`));
      assert.ok(!img.getAttribute("src").includes(".."));
    }
  }
  assert.ok(accepted > 0, "o gerador não produziu nenhum caminho válido");
});

test("FakeElement é usado (sanidade do DOM falso)", () => {
  assert.ok(renderMarkdown("x") instanceof FakeElement);
});
