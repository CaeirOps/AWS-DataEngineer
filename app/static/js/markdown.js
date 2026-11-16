// Renderizador de Markdown local. Constrói nós de DOM (sem innerHTML), então
// todo texto é escapado por construção. Só gera tags conhecidas: títulos,
// parágrafos, listas, code, blocos de código, links http(s) ou relativos,
// negrito, itálico, tabelas simples, citações e linhas horizontais.

import { el } from "./dom.js";

const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

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

function appendInline(parent, text) {
  INLINE.lastIndex = 0;
  let last = 0;
  let match;
  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) parent.append(text.slice(last, match.index));
    const whole = match[0];
    if (match[1] !== undefined) {
      parent.append(el("code", null, match[1]));
    } else if (match[3] !== undefined) {
      const label = match[2];
      if (whole.startsWith("!")) {
        // Imagens não são renderizadas: mostra apenas o texto alternativo.
        parent.append(label);
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
        appendInline(link, label || match[3]);
        parent.append(link);
      } else {
        parent.append(label || "");
      }
    } else if (match[4] !== undefined) {
      const strong = el("strong");
      appendInline(strong, match[4]);
      parent.append(strong);
    } else {
      const em = el("em");
      appendInline(em, match[5] !== undefined ? match[5] : match[6]);
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

function parseList(lines, start) {
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
      const [sub, next] = parseList(lines, i);
      const lastItem = list.lastElementChild;
      if (lastItem) lastItem.append(sub);
      else list.append(el("li", null, sub));
      i = next;
      continue;
    }
    const item = el("li");
    appendInline(item, m[3]);
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
      appendInline(item, lines[i].trim());
      i += 1;
    }
  }
  return [list, i];
}

function renderBlocks(lines, parent) {
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
      appendInline(node, heading[2]);
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
      const quote = el("blockquote");
      renderBlocks(buffer, quote);
      parent.append(quote);
      continue;
    }

    if (LIST_ITEM.test(line)) {
      const [list, next] = parseList(lines, i);
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
        appendInline(th, cell);
        headRow.append(th);
      }
      table.append(el("thead", null, headRow));
      const body = el("tbody");
      i += 2;
      while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
        const row = el("tr");
        for (const cell of splitRow(lines[i])) {
          const td = el("td");
          appendInline(td, cell);
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
    appendInline(p, buffer.join(" "));
    parent.append(p);
  }
}

/** Converte Markdown em um <div class="markdown"> montado só com nós de DOM. */
export function renderMarkdown(text) {
  const root = el("div", { class: "markdown" });
  const source = String(text === null || text === undefined ? "" : text).replace(/\r\n?/g, "\n");
  renderBlocks(source.split("\n"), root);
  return root;
}
