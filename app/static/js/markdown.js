// Renderizador de Markdown local. Constrói nós de DOM (sem innerHTML), então
// todo texto é escapado por construção. Só gera tags conhecidas: títulos,
// parágrafos, listas, code, blocos de código, links http(s) ou relativos,
// negrito, itálico, tabelas simples, citações, Destaques (`> [!EXAM]` etc.),
// imagens locais do módulo e linhas horizontais.

import { el } from "./dom.js";

const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

/** Destaques aceitos: marcador -> título exibido (Requirement 4.7). */
export const CALLOUTS = Object.freeze({
  EXAM: "Na prova",
  COST: "Custo",
  TIP: "Boas práticas",
  WARNING: "Atenção",
});
const CALLOUT = /^\[!([A-Z]+)\][ \t]*(.*)$/;

// Mesma regra da rota de assets no servidor: um único nome, sem `..`, `/`,
// `\`, `:`, query ou fragmento, com extensão .svg ou .png (Requirement 4.8).
const ASSET_PATH = /^assets\/([A-Za-z0-9][A-Za-z0-9_-]{0,63}\.(?:svg|png))$/;
const LAB_ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;

/**
 * URL da imagem local, ou `null` se o caminho não passa na regra de imagens.
 * O `src` sempre aponta para `/api/labs/<lab_id>/assets/`.
 */
export function localImageSrc(path, labId) {
  if (typeof labId !== "string" || !LAB_ID.test(labId)) return null;
  const match = ASSET_PATH.exec(String(path));
  if (!match) return null;
  return `/api/labs/${labId}/assets/${match[1]}`;
}

/** Aceita somente http(s) ou caminhos relativos/âncoras. */
export function isSafeHref(href) {
  const value = String(href).trim();
  if (!value) return false;
  if (value.startsWith("//")) return false;
  if (SCHEME.test(value)) return /^https?:/i.test(value);
  return true;
}

const INLINE =
  /`([^`]+)`|!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)|\*\*(.+?)\*\*|(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])|(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])/g;

function appendInline(parent, text, ctx) {
  // `INLINE` é global e as chamadas recursivas reiniciam `lastIndex`: cada
  // chamada usa a própria instância.
  const pattern = new RegExp(INLINE.source, INLINE.flags);
  let last = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parent.append(text.slice(last, match.index));
    const whole = match[0];
    if (match[1] !== undefined) {
      parent.append(el("code", null, match[1]));
    } else if (match[3] !== undefined) {
      const label = match[2];
      if (whole.startsWith("!")) {
        // Só imagens locais do módulo com texto alternativo; o resto vira texto.
        const src = label.trim() ? localImageSrc(match[3], ctx.labId) : null;
        if (src) parent.append(el("img", { src, alt: label.trim(), loading: "lazy" }));
        else parent.append(label);
      } else if (isSafeHref(match[3])) {
        const external = /^https?:/i.test(match[3]);
        const link = el(
          "a",
          {
            href: match[3],
            target: external ? "_blank" : null,
            rel: external ? "noopener noreferrer" : null,
          }
        );
        appendInline(link, label || match[3], ctx);
        parent.append(link);
      } else {
        parent.append(label || "");
      }
    } else if (match[4] !== undefined) {
      const strong = el("strong");
      appendInline(strong, match[4], ctx);
      parent.append(strong);
    } else {
      const em = el("em");
      appendInline(em, match[5] !== undefined ? match[5] : match[6], ctx);
      parent.append(em);
    }
    last = match.index + whole.length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = el("textarea", { class: "visually-hidden", "aria-hidden": "true" });
  area.value = text;
  document.body.append(area);
  area.select();
  try {
    document.execCommand("copy");
  } finally {
    area.remove();
  }
}

function codeBlock(code, lang) {
  const pre = el("pre", null, el("code", lang ? { class: `language-${lang.replace(/[^\w-]/g, "")}` } : null, code));
  const button = el(
    "button",
    { type: "button", class: "code-block__copy", "aria-label": "Copiar código" },
    "Copiar"
  );
  button.addEventListener("click", async () => {
    try {
      await copyText(code);
      button.textContent = "Copiado";
      button.dataset.copied = "true";
    } catch (err) {
      button.textContent = "Falhou";
    }
    setTimeout(() => {
      button.textContent = "Copiar";
      delete button.dataset.copied;
    }, 1800);
  });
  return el("div", { class: "code-block" }, button, pre);
}

const FENCE = /^\s*(```+|~~~+)\s*([\w+-]*)\s*$/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const HR = /^\s*([-*_])(\s*\1){2,}\s*$/;
const LIST_ITEM = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function splitRow(line) {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|")) row = row.slice(0, -1);
  return row.split("|").map((cell) => cell.trim());
}

function startsBlock(line, next) {
  return (
    FENCE.test(line) ||
    HEADING.test(line) ||
    HR.test(line) ||
    /^\s*>/.test(line) ||
    LIST_ITEM.test(line) ||
    (line.includes("|") && next !== undefined && TABLE_SEP.test(next))
  );
}

function parseList(lines, start, ctx) {
  const first = LIST_ITEM.exec(lines[start]);
  const baseIndent = first[1].length;
  const ordered = /\d/.test(first[2]);
  const list = el(ordered ? "ol" : "ul");
  let i = start;
  while (i < lines.length) {
    const m = LIST_ITEM.exec(lines[i]);
    if (!m) break;
    const indent = m[1].length;
    if (indent < baseIndent) break;
    if (indent > baseIndent) {
      // Sublista: anexa ao último item.
      const [sub, next] = parseList(lines, i, ctx);
      const lastItem = list.lastElementChild;
      if (lastItem) lastItem.append(sub);
      else list.append(el("li", null, sub));
      i = next;
      continue;
    }
    const item = el("li");
    appendInline(item, m[3], ctx);
    list.append(item);
    i += 1;
    // Linhas de continuação (indentadas, sem marcador).
    while (
      i < lines.length &&
      lines[i].trim() !== "" &&
      !LIST_ITEM.test(lines[i]) &&
      /^\s+/.test(lines[i]) &&
      !FENCE.test(lines[i])
    ) {
      item.append(" ");
      appendInline(item, lines[i].trim(), ctx);
      i += 1;
    }
  }
  return [list, i];
}

/** `aside.callout` para `[!MARCADOR]` conhecido; `null` para citação comum. */
function callout(buffer, ctx) {
  const match = CALLOUT.exec(buffer[0] || "");
  if (!match || !Object.prototype.hasOwnProperty.call(CALLOUTS, match[1])) return null;
  const kind = match[1].toLowerCase();
  const node = el(
    "aside",
    { class: `callout callout--${kind}`, role: "note", "aria-label": CALLOUTS[match[1]] },
    el("div", { class: "callout__title" }, CALLOUTS[match[1]])
  );
  const body = el("div", { class: "callout__body" });
  const rest = match[2] ? [match[2], ...buffer.slice(1)] : buffer.slice(1);
  renderBlocks(rest, body, ctx);
  node.append(body);
  return node;
}

function renderBlocks(lines, parent, ctx) {
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i += 1;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      const marker = fence[1];
      const buffer = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith(marker)) {
        buffer.push(lines[i]);
        i += 1;
      }
      i += 1; // fecha a cerca (ou fim do texto)
      parent.append(codeBlock(buffer.join("\n"), fence[2]));
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      const level = Math.min(heading[1].length + 1, 6); // h1 do Markdown vira h2 (a página já tem um h1)
      const node = el(`h${level}`);
      appendInline(node, heading[2], ctx);
      parent.append(node);
      i += 1;
      continue;
    }

    if (HR.test(line)) {
      parent.append(el("hr"));
      i += 1;
      continue;
    }

    if (/^\s*>/.test(line)) {
      const buffer = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        buffer.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      const aside = callout(buffer, ctx);
      if (aside) {
        parent.append(aside);
        continue;
      }
      const quote = el("blockquote");
      renderBlocks(buffer, quote, ctx);
      parent.append(quote);
      continue;
    }

    if (LIST_ITEM.test(line)) {
      const [list, next] = parseList(lines, i, ctx);
      parent.append(list);
      i = next;
      continue;
    }

    if (line.includes("|") && i + 1 < lines.length && TABLE_SEP.test(lines[i + 1])) {
      const head = splitRow(line);
      const table = el("table");
      const headRow = el("tr");
      for (const cell of head) {
        const th = el("th");
        appendInline(th, cell, ctx);
        headRow.append(th);
      }
      table.append(el("thead", null, headRow));
      const body = el("tbody");
      i += 2;
      while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
        const row = el("tr");
        for (const cell of splitRow(lines[i])) {
          const td = el("td");
          appendInline(td, cell, ctx);
          row.append(td);
        }
        body.append(row);
        i += 1;
      }
      table.append(body);
      parent.append(table);
      continue;
    }

    // Parágrafo
    const buffer = [line.trim()];
    i += 1;
    while (i < lines.length && lines[i].trim() !== "" && !startsBlock(lines[i], lines[i + 1])) {
      buffer.push(lines[i].trim());
      i += 1;
    }
    const p = el("p");
    appendInline(p, buffer.join(" "), ctx);
    parent.append(p);
  }
}

/**
 * Converte Markdown em um <div class="markdown"> montado só com nós de DOM.
 * `options.labId` habilita as imagens locais do módulo; sem ele, imagens
 * aparecem só como texto alternativo.
 */
export function renderMarkdown(text, options = {}) {
  const root = el("div", { class: "markdown" });
  const source = String(text === null || text === undefined ? "" : text).replace(/\r\n?/g, "\n");
  renderBlocks(source.split("\n"), root, { labId: options.labId });
  return root;
}
