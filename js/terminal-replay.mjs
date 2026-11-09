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
 * @param {Array<Object>} lines     The session's lines (`sessionLines`).
 * @param {Array<Object>} selectors The chapter's declaration.
 * @param {{prompt?: string, init?: ?Object}} from The prompt file's text and the init line.
 */
export function chooseLines(lines, selectors, { prompt, init } = {}) {
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
    const pattern = s.match ? new RegExp(s.match, s.flags ?? "i") : null;
    let picked = lines.filter((l) =>
      (!s.tools || s.tools.includes(l.tool)) && (!s.kind || l.kind === s.kind) && (!pattern || pattern.test(l.text)));
    if (s.first !== undefined) picked = picked.slice(0, s.first);
    if (s.last !== undefined) picked = picked.slice(-s.last);
    chosen.push(...picked);
  }
  return chosen;
}

const PAGE = (title) => `<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;background:#0d1117;color:#e6edf3;font:22px/1.45 "Cascadia Mono","Consolas",monospace}
.bar{height:44px;background:#161b22;display:flex;align-items:center;gap:10px;padding:0 18px;color:#8b949e;font:18px system-ui}
.bar i{width:13px;height:13px;border-radius:50%;display:inline-block}
#out{padding:22px 36px;height:calc(100vh - 88px);overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.l{white-space:pre-wrap;margin:0 0 10px}
.prompt{color:#e6edf3}.prompt:before{content:"> ";color:#d2a8ff}
.call{color:#79c0ff}.call:before{content:"● ";color:#3fb950}
.answer{color:#8b949e;border-left:3px solid #30363d;padding-left:14px}
.error{color:#ffa198;border-left:3px solid #f85149;padding-left:14px}
.text{color:#e6edf3}.text:before{content:"✻ ";color:#E85D04}
.note{color:#8b949e;font-style:italic}
.init{color:#8b949e}.init:before{content:"✓ ";color:#3fb950}
</style><div class="bar"><i style="background:#f85149"></i><i style="background:#d29922"></i><i style="background:#3fb950"></i><span>${title}</span></div><div id="out"></div>`;

/**
 * Films lines as a terminal: a prompt typed at `typeMs` a key, every other line shown after a
 * pause that grows with its length (`readMs` per line of text, at least `minMs`).
 */
export async function filmTerminal(browser, { lines, title = "Claude Code", out, typeMs = 18, readMs = 650, minMs = 700, hold = 2500, size = { width: 1920, height: 1080 } }) {
  const { mkdirSync, readdirSync, renameSync, rmSync } = await import("node:fs");
  const { dirname, join } = await import("node:path");
  const tmp = `${out}.tmp`;
  rmSync(tmp, { recursive: true, force: true });
  mkdirSync(tmp, { recursive: true });
  const ctx = await browser.newContext({ viewport: size, recordVideo: { dir: tmp, size } });
  const page = await ctx.newPage();
  await page.setContent(PAGE(title));
  await page.waitForTimeout(800);
  for (const line of lines) {
    await page.evaluate(({ kind, text }) => {
      const p = document.createElement("p");
      p.className = `l ${kind}`;
      p.dataset.full = text;
      p.textContent = kind === "prompt" ? "" : text;
      document.getElementById("out").append(p);
    }, line);
    if (line.kind === "prompt") {
      await page.evaluate(async (ms) => {
        const p = [...document.querySelectorAll(".prompt")].pop();
        for (const ch of p.dataset.full) { p.textContent += ch; await new Promise((r) => setTimeout(r, ms)); }
      }, typeMs);
      await page.waitForTimeout(900);
    } else {
      await page.waitForTimeout(Math.max(minMs, readMs * line.text.split("\n").length));
    }
  }
  await page.waitForTimeout(hold);
  await ctx.close();
  const [webm] = readdirSync(tmp).filter((f) => f.endsWith(".webm"));
  mkdirSync(dirname(out), { recursive: true });
  rmSync(out, { force: true });
  renameSync(join(tmp, webm), out);
  rmSync(tmp, { recursive: true, force: true });
}
