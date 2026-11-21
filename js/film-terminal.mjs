#!/usr/bin/env node
// Films each scene `urdido terminal` recorded as a terminal scene (UR53): the session's commands
// typed key by key and the lines they really printed, in the terminal replay's window.
//
//   node film-terminal.mjs terminal/session.json footage/terminal [--title "Terminal"] [--scene NAME]
//
// One <out>/<scene>.webm per scene. Playwright comes from the project that runs it, as for every
// other recording step; ffmpeg trims the browser's blank first frames.

import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { commandLines, filmTerminal } from "./terminal-replay.mjs";

export async function filmSession(sessionFile, out, { title = "Terminal", scene = null } = {}) {
  const session = JSON.parse(readFileSync(sessionFile, "utf8"));
  const names = scene ? [scene] : Object.keys(session);
  for (const name of names) {
    if (!session[name]) throw new Error(`film-terminal: ${sessionFile} has no scene ${name}`);
  }
  const { chromium } = await import("playwright");
  const browser = await chromium.launch();
  try {
    for (const name of names) {
      const file = join(out, `${name}.webm`);
      await filmTerminal(browser, { lines: commandLines(session[name]), title, out: file, zoom: 1.1 });
      console.log(`filmed ${file}`);
    }
  } finally {
    await browser.close();
  }
}

const [, script, sessionFile, out, ...rest] = process.argv;
if (script && resolve(script) === fileURLToPath(import.meta.url)) {
  if (!sessionFile || !out) {
    console.error("usage: node film-terminal.mjs <session.json> <out folder> [--title T] [--scene NAME]");
    process.exit(2);
  }
  const option = (name) => { const i = rest.indexOf(name); return i >= 0 ? rest[i + 1] : undefined; };
  await filmSession(sessionFile, out, { title: option("--title"), scene: option("--scene") });
}
