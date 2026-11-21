// A Claude Code session, replayed as a terminal scene from its own record (claude -p
// --output-format stream-json). Nothing on screen is written by hand: every line is a request,
// a tool call, a tool answer or the agent's own text from the session, so the scene is the real
// session sped up, never staged.
//
//   import { sessionLines, filmTerminal } from "../../../video-maker/terminal-replay.mjs";
//   const lines = sessionLines(readFileSync("agent.jsonl", "utf8"), { toolPrefix: "mcp__plugin_shio_shio__" });
//   await filmTerminal(browser, { lines: lines.filter(...), title: "Claude Code", out: "chapter-5.webm" });
//
// A line is { kind: "prompt" | "init" | "call" | "answer" | "error" | "text", text }. A prompt is
// typed key by key; the others appear one after another at a reading pace. Which lines a chapter
// shows is the video's declaration (`chooseLines`), never a line typed into a script.

/** The session's lines, in order, from its stream-json record. */
export function sessionLines(jsonl, { toolPrefix = "", answerLines = 6, width = 110 } = {}) {
  const events = jsonl.split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
  const answers = new Map();
  for (const e of events) {
    if (e.type !== "user") continue;
    for (const c of e.message?.content ?? []) {
      if (c?.type !== "tool_result") continue;
      const text = typeof c.content === "string" ? c.content : (c.content ?? []).map((x) => x.text ?? "").join("\n");
      answers.set(c.tool_use_id, { error: Boolean(c.is_error) || /\berror https?:\/\//.test(text), text });
    }
  }
  const clip = (s) => (s.length > width ? `${s.slice(0, width - 1)}…` : s);
  const out = [];
  const first = events.find((e) => e.type === "user" && typeof e.message?.content === "string");
  if (first) out.push({ kind: "prompt", text: first.message.content.trim() });
  for (const e of events) {
    if (e.type !== "assistant") continue;
    for (const c of e.message?.content ?? []) {
      if (c.type === "text" && c.text.trim()) out.push({ kind: "text", text: c.text.trim() });
      if (c.type !== "tool_use" || c.name === "ToolSearch") continue;
      const name = c.name.replace(toolPrefix, "");
      const args = Object.entries(c.input ?? {})
        .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(" ");
      out.push({ kind: "call", tool: name, text: clip(`${name} ${args}`) });
      const a = answers.get(c.id);
      if (a) {
        const lines = a.text.split("\n").map((l) => l.trimEnd()).filter(Boolean);
        const shown = lines.slice(0, answerLines).map(clip);
        if (lines.length > answerLines) shown.push(`… ${lines.length - answerLines} more line(s)`);
        out.push({ kind: a.error ? "error" : "answer", tool: name, text: shown.join("\n") });
      }
    }
  }
  return out;
}

/**
 * The session's start, as its own `init` event records it, for one plugin only: its name and
 * version, its MCP server and its skills. Nothing else from the event is shown: it also lists
 * the machine's other connectors, folders and settings, which are not the scene's (VM11).
 *
 * @param {string} jsonl  The session's stream-json record.
 * @param {string} plugin The plugin the scene is about, as the event names it.
 * @return {?{kind: "init", text: string}} The line, or null when the record has no such plugin.
 */
export function initLine(jsonl, plugin) {
  const init = jsonl.split("\n").filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } })
    .find((e) => e?.type === "system" && e.subtype === "init");
  const found = init?.plugins?.find((p) => p.name === plugin);
  if (!found) return null;
  const server = (init.mcp_servers ?? []).find((s) => s.name === `plugin:${plugin}:${plugin}`);
  const skills = (init.skills ?? []).filter((s) => s.startsWith(`${plugin}:`));
  return {
    kind: "init",
    text: [
      `plugin ${found.name}${found.version ? ` ${found.version}` : ""}`,
      server ? `MCP ${server.name}` : null,
      skills.length ? `skills ${skills.join(", ")}` : null,
    ].filter(Boolean).join(" · "),
  };
}

/**
 * A chapter's lines, chosen from the session by its declaration (VM11): each selector adds the
 * lines it picks, in the session's order, so nothing on screen is written by hand.
 *
 * - `{ "init": true }`               the session's start (`initLine`)
 * - `{ "prompt": true }`             the request, from the prompt file the session was sent
 * - `{ "tools": [...], "first": n }` the calls (and their answers) of these tools
 * - `{ "kind": "text", "match": "re", "last": n }` lines of a kind, matching, first or last n
 *
 * Any selector may add `"required": true` (the session must hold a line it picks) and
 * `"count": n` (the session must hold exactly n, before `first`/`last`); a session that fails
 * either is refused, naming the chapter and the selector (UR11, `checkSession`).
 *
 * @param {Array<Object>} lines     The session's lines (`sessionLines`).
 * @param {Array<Object>} selectors The chapter's declaration.
 * @param {{prompt?: string, init?: ?Object}} from The prompt file's text and the init line.
 */
export function chooseLines(lines, selectors, { prompt, init, chapter } = {}) {
  const missing = selectorFindings(lines, selectors, { init, chapter: chapter ?? "a chapter" });
  if (missing.length) throw new Error(`terminal-replay: ${missing.map((f) => f.message).join("; ")}`);
  const chosen = [];
  for (const s of selectors) {
    if (s.init) {
      if (!init) throw new Error("terminal-replay: the declaration asks for the init line, the record has none");
      chosen.push(init);
      continue;
    }
    if (s.prompt) {
      chosen.push({ kind: "prompt", text: prompt });
      continue;
    }
    let picked = matching(lines, s);
    if (s.first !== undefined) picked = picked.slice(0, s.first);
    if (s.last !== undefined) picked = picked.slice(-s.last);
    chosen.push(...picked);
  }
  return chosen;
}

/**
 * A tool's answer as its words read: JSON escapes (`é`, `\n`, `\"`) undone, so a selector
 * matching "não" finds it inside an answer the tool returned as escaped JSON (UR11).
 */
export function searchable(text) {
  return text
    .replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/\\n/g, "\n")
    .replace(/\\"/g, '"');
}

/** Every line one selector picks, before `first` or `last` narrows them. */
function matching(lines, s) {
  const pattern = s.match ? new RegExp(s.match, s.flags ?? "i") : null;
  return lines.filter((l) =>
    (!s.tools || s.tools.includes(l.tool)) && (!s.kind || l.kind === s.kind)
    && (!pattern || pattern.test(l.text) || pattern.test(searchable(l.text))));
}

/** What one chapter's selectors find wanting: a `required` one that picks nothing, a `count` missed. */
function selectorFindings(lines, selectors, { init, chapter }) {
  const found = [];
  selectors.forEach((s, index) => {
    const what = JSON.stringify(s);
    if (s.prompt) return;
    const picked = s.init ? (init ? [init] : []) : matching(lines, s);
    if (s.required && picked.length === 0) {
      found.push({ chapter, selector: index, rule: "required",
        message: `${chapter}: selector ${index} ${what} is required and finds nothing in the session` });
    }
    if (s.count !== undefined && picked.length !== s.count) {
      found.push({ chapter, selector: index, rule: "count", found: picked.length,
        message: `${chapter}: selector ${index} ${what} wants ${s.count} line(s) and finds ${picked.length}` });
    }
  });
  return found;
}

const STOPWORDS = {
  pt: new Set(["o", "a", "os", "as", "de", "do", "da", "dos", "das", "que", "e", "em", "no", "na", "um", "uma",
    "para", "com", "não", "por", "mais", "se", "como", "mas", "já", "está", "também", "isso", "você", "foi", "ao"]),
  en: new Set(["the", "and", "is", "are", "to", "of", "in", "it", "that", "for", "with", "on", "this", "was",
    "be", "as", "at", "by", "not", "have", "you", "will", "now", "all", "done", "i", "an", "or", "from"]),
};

/** The language a line reads in, by its common words, or null when too short to tell. */
export function guessLanguage(text) {
  const words = text.toLowerCase().match(/[\p{L}']+/gu) ?? [];
  if (words.length < 4) return null;
  const scores = Object.entries(STOPWORDS).map(([lang, set]) => [lang, words.filter((w) => set.has(w)).length]);
  scores.sort((x, y) => y[1] - x[1]);
  const [[best, top], [, next]] = scores;
  return top >= 2 && top > next ? best : null;
}

/**
 * A session judged against its chapters before anything is filmed after it (UR11): each chapter's
 * `required` selectors must pick a line and each `count` must match, and the agent's text lines in
 * another language than the video's are reported. `passed` is false only for the first two.
 *
 * @param {Array<Object>} lines    The session's lines (`sessionLines`).
 * @param {Object} chapters        The declaration's chapters, id to selectors.
 * @param {{init?: ?Object, language?: string}} from The init line, and the video's language.
 * @return {{passed: boolean, findings: Array<Object>, language: Array<Object>}}
 */
export function checkSession(lines, chapters, { init, language } = {}) {
  const findings = Object.entries(chapters).flatMap(([chapter, selectors]) =>
    selectorFindings(lines, selectors, { init, chapter }));
  const want = language ? language.split("-")[0].toLowerCase() : null;
  const foreign = want ? lines.filter((l) => l.kind === "text").map((l) => ({ text: l.text, language: guessLanguage(l.text) }))
    .filter((l) => l.language && l.language !== want) : [];
  return { passed: findings.length === 0, findings, language: foreign };
}

const escape = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const inline = (s) => escape(s)
  .replace(/`([^`]+)`/g, "<code>$1</code>")
  .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
  .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");

/**
 * The agent's text as Claude Code shows it: its Markdown formatted (headings, bold, inline code,
 * lists, tables), not its raw `**` and `|`, so a viewer who does not read Markdown reads the
 * report. The words are the session's, untouched.
 *
 * @param {string} text The agent's text, Markdown.
 * @return {string} HTML, escaped.
 */
export function markdownHtml(text) {
  const out = [];
  const rows = text.split("\n");
  for (let i = 0; i < rows.length;) {
    const row = rows[i];
    if (/^\s*\|/.test(row)) {
      const table = [];
      while (i < rows.length && /^\s*\|/.test(rows[i])) table.push(rows[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const body = table.filter((r) => !/^\s*\|[\s:|-]+\|\s*$/.test(r));
      const [head, ...rest] = body;
      out.push(`<table><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr>${
        rest.map((r) => `<tr>${cells(r).map((c, k) => `<${k ? "td" : "th"}>${inline(c)}</${k ? "td" : "th"}>`).join("")}</tr>`).join("")}</table>`);
      continue;
    }
    if (/^\s*[-*] /.test(row)) {
      const items = [];
      while (i < rows.length && /^\s*[-*] /.test(rows[i])) items.push(rows[i++].replace(/^\s*[-*] /, ""));
      out.push(`<ul>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ul>`);
      continue;
    }
    if (/^\s*\d+\. /.test(row)) {
      const items = [];
      while (i < rows.length && /^\s*\d+\. /.test(rows[i])) items.push(rows[i++].replace(/^\s*\d+\. /, ""));
      out.push(`<ol>${items.map((t) => `<li>${inline(t)}</li>`).join("")}</ol>`);
      continue;
    }
    const heading = row.match(/^(#{1,6})\s+(.*)$/);
    if (heading) out.push(`<h4>${inline(heading[2])}</h4>`);
    else if (row.trim()) out.push(`<div>${inline(row)}</div>`);
    i++;
  }
  return out.join("");
}

/**
 * A shell session's lines, from one scene of what `urdido terminal` recorded (UR53): each
 * command typed as a prompt, then the printed lines its declaration keeps (`shown`), never
 * a line written here.
 */
export function commandLines(steps) {
  return steps.flatMap((s) => [
    { kind: "prompt", text: s.command },
    ...(s.shown?.length ? [{ kind: "answer", text: s.shown.join("\n") }] : []),
  ]);
}

// The terminal is a window on a desktop, the way a screen recording of the app looks, filling the
// top of the frame and leaving the bottom band (where a video's captions sit) to the desktop.
const PAGE = (title, zoom = 1) => `<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;height:100%;color:#e6edf3;font:22px/1.45 "Cascadia Mono","Consolas",monospace;
  background:radial-gradient(ellipse 80% 70% at 50% 30%,#1c2433 0%,#0b0f17 70%,#07090d 100%)}
.win{position:absolute;left:5.5%;right:5.5%;top:3.5%;height:74%;display:flex;flex-direction:column;
  background:#0d1117;border:1px solid #30363d;border-radius:14px;overflow:hidden;
  box-shadow:0 30px 80px rgba(0,0,0,.55),0 0 0 1px rgba(255,255,255,.03)}
.bar{flex:none;height:44px;background:#161b22;display:flex;align-items:center;gap:10px;padding:0 18px;color:#8b949e;font:18px system-ui}
.bar i{width:13px;height:13px;border-radius:50%;display:inline-block}
#out{flex:1;padding:26px 36px 10px;overflow:hidden}
${zoom !== 1 ? `#out{zoom:${zoom}}` : ""}
.l{white-space:pre-wrap;margin:0 0 10px}
.prompt{color:#e6edf3}.prompt:before{content:"> ";color:#d2a8ff}
.call{color:#79c0ff}.call:before{content:"● ";color:#3fb950}
.answer{color:#8b949e;border-left:3px solid #30363d;padding-left:14px}
.error{color:#ffa198;border-left:3px solid #f85149;padding-left:14px}
.text{color:#e6edf3;white-space:normal;font:24px/1.5 system-ui,"Segoe UI",sans-serif;position:relative;padding-left:34px}
.text:before{content:"✻";color:#E85D04;position:absolute;left:0;top:0;font-family:"Cascadia Mono",monospace}
.text>*{margin:0 0 8px}.text b{color:#fff;font-weight:700}.text i{font-style:italic}
.text code{font:21px "Cascadia Mono",Consolas,monospace;color:#d2a8ff;background:#161b22;padding:1px 7px;border-radius:5px}
.text h4{font-size:26px;color:#fff;margin:6px 0 8px}
.text ul,.text ol{padding-left:28px}.text li{margin:0 0 6px}.text li::marker{color:#E85D04}
.text table{border-collapse:collapse;margin:6px 0 12px}.text th,.text td{border:1px solid #30363d;padding:6px 16px;text-align:left}
.text tr:first-child th{background:#161b22;color:#8b949e;font-weight:600}
.note{color:#8b949e;font-style:italic}
.init{color:#8b949e}.init:before{content:"✓ ";color:#3fb950}
</style><div class="win"><div class="bar"><i style="background:#f85149"></i><i style="background:#d29922"></i><i style="background:#3fb950"></i><span>${title}</span></div><div id="out"></div></div>`;

/**
 * Films lines as a terminal: a prompt typed at `typeMs` a key, every other line shown after a
 * pause that grows with its length (`readMs` per line of text, at least `minMs`). The lines run
 * from the top of the window, as in a terminal; one that does not fit is scrolled through slowly
 * while it is read. A short session reads better larger: `zoom`.
 */
export async function filmTerminal(browser, { lines, title = "Claude Code", out, typeMs = 18, readMs = 650, minMs = 700, hold = 2500, size = { width: 1920, height: 1080 }, targetMs = null, zoom = 1 }) {
  // Paced to a length (the lines spoken over the scene): the reading pauses stretch or shrink
  // together, within reason, so the session reads at the narration's pace; whatever is left past
  // that is held on the last screen.
  const typed = lines.filter((l) => l.kind === "prompt").reduce((s, l) => s + l.text.length * typeMs + 900, 0);
  const reading = lines.filter((l) => l.kind !== "prompt").reduce((s, l) => s + Math.max(minMs, readMs * l.text.split("\n").length), 0);
  let scale = 1;
  if (targetMs && reading > 0) {
    scale = Math.min(4, Math.max(0.35, (targetMs - 800 - typed - hold) / reading));
    hold = Math.max(hold, targetMs - 800 - typed - reading * scale);
    readMs *= scale;
    minMs *= scale;
  }
  const { mkdirSync, readdirSync, rmSync } = await import("node:fs");
  const { dirname, join } = await import("node:path");
  const tmp = `${out}.tmp`;
  rmSync(tmp, { recursive: true, force: true });
  mkdirSync(tmp, { recursive: true });
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: tmp, size } });
  const page = await ctx.newPage();
  const born = Date.now();
  await page.setContent(PAGE(title, zoom));
  // The browser films its empty white page until the terminal paints: the clip is cut just past it,
  // or the replay opens on a white frame (the Viglet Shio promo's chapter 6, 2026-11-17, VM86).
  const blank = (Date.now() - born) / 1000 + 0.1;
  await page.waitForTimeout(800);
  for (const line of lines) {
    const wait = line.kind === "prompt" ? 0 : Math.max(minMs, readMs * line.text.split("\n").length);
    await page.evaluate(({ kind, text, html, wait }) => {
      const out = document.getElementById("out");
      const p = document.createElement(kind === "text" ? "div" : "p");
      p.className = `l ${kind}`;
      p.dataset.full = text;
      if (kind === "text") p.innerHTML = html;
      else p.textContent = kind === "prompt" ? "" : text;
      out.append(p);
      // The window keeps the newest line in view: a line that fits is scrolled to at once, as a
      // terminal does; one taller than what is left is shown from its top and scrolled through,
      // eased, over most of its reading time.
      const end = out.scrollHeight - out.clientHeight;
      if (end <= out.scrollTop) return;
      const top = Math.min(end, p.offsetTop - out.offsetTop - 12);
      if (top >= end || !wait) { out.scrollTop = end; return; }
      out.scrollTop = Math.max(out.scrollTop, top);
      const from = out.scrollTop, ms = wait * 0.8, t0 = performance.now() + wait * 0.1;
      const step = (now) => {
        const k = Math.max(0, Math.min(1, (now - t0) / ms));
        out.scrollTop = from + (end - from) * (k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }, { ...line, html: line.kind === "text" ? markdownHtml(line.text) : null, wait });
    if (line.kind === "prompt") {
      await page.evaluate(async (ms) => {
        const p = [...document.querySelectorAll(".prompt")].pop();
        for (const ch of p.dataset.full) { p.textContent += ch; await new Promise((r) => setTimeout(r, ms)); }
      }, typeMs);
      await page.waitForTimeout(900);
    } else {
      await page.waitForTimeout(wait);
    }
  }
  await page.waitForTimeout(hold);
  await ctx.close();
  const [webm] = readdirSync(tmp).filter((f) => f.endsWith(".webm"));
  mkdirSync(dirname(out), { recursive: true });
  rmSync(out, { force: true });
  const { execFileSync } = await import("node:child_process");
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-ss", blank.toFixed(3), "-i", join(tmp, webm),
    "-c:v", "libvpx", "-b:v", "8M", "-crf", "8", "-deadline", "good", "-cpu-used", "4", "-an", out],
    { stdio: ["ignore", "pipe", "pipe"] });
  rmSync(tmp, { recursive: true, force: true });
}
