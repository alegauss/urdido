// How a filmed scene moves, the way the Viglet Turing WordPress demo moves (its
// tests/e2e/story/shopper.story.mjs, in the Turing repository): a visible pointer that a headless
// recording would leave out, a quick hand-like move to what is about to be clicked, and a slow,
// eased scroll so a page is read on the way down rather than jumped over.
//
//   const moves = await storyMoves(page);   // before the first navigation
//   await moves.click(locator);             // move to it, ring, click
//   await moves.type(locator, "quilhara");  // move to it, click, type at a hand's pace
//   await moves.glide(locator);             // scroll slowly until it shows
//   await moves.scrollBy(900);              // scroll slowly by a distance

/**
 * Draws the pointer and rings it on a click. Runs in the page before its own scripts. A copy of
 * pointer() in the WordPress demo, so both videos move the same way.
 */
function pointer() {
  document.addEventListener("focusin", (event) => {
    if ("spellcheck" in event.target) event.target.spellcheck = false;
  }, true);
  let place = null;
  window.addEventListener("DOMContentLoaded", () => {
    const dot = document.createElement("div");
    dot.setAttribute("aria-hidden", "true");
    dot.style.cssText = "position:fixed;z-index:2147483647;left:0;top:0;pointer-events:none;"
      + "will-change:transform;transform:translate3d(-40px,-40px,0)";
    const ring = document.createElement("div");
    ring.style.cssText = "width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;"
      + "background:rgba(232,93,4,.45);border:2px solid #E85D04;box-sizing:border-box;transition:transform .15s";
    dot.append(ring);
    document.body.append(dot);
    place = (x, y) => { dot.style.transform = `translate3d(${x}px,${y}px,0)`; };
    const last = window.__storyCursor;
    if (last) place(last.x, last.y);
    document.addEventListener("mousemove", (event) => place(event.clientX, event.clientY));
    document.addEventListener("mousedown", () => { ring.style.transform = "scale(1.8)"; });
    document.addEventListener("mouseup", () => { ring.style.transform = ""; });
  });
  // A hand's move: a minimum-jerk curve (quick away, settling onto the target) along a slight arc.
  window.__storyGlide = (from, to, ms) => new Promise((done) => {
    if (!place) { done(); return; }
    const dx = to.x - from.x, dy = to.y - from.y, bend = 0.12;
    const control = { x: from.x + dx / 2 - dy * bend, y: from.y + dy / 2 + dx * bend };
    const t0 = performance.now();
    const step = (now) => {
      const t = Math.min(1, (now - t0) / ms);
      const s = t * t * t * (10 - 15 * t + 6 * t * t), u = 1 - s;
      place(u * u * from.x + 2 * u * s * control.x + s * s * to.x, u * u * from.y + 2 * u * s * control.y + s * s * to.y);
      if (t < 1) window.requestAnimationFrame(step); else done();
    };
    window.requestAnimationFrame(step);
  });
}

/** A slow scroll by `distance` px, eased at both ends: about 200 px a second, 3 to 12 s. */
async function scrollByEased(page, distance, given = 0) {
  await page.evaluate(([dist, givenMs]) => new Promise((done) => {
    const from = window.scrollY;
    const target = Math.max(0, Math.min(from + dist, document.documentElement.scrollHeight - window.innerHeight));
    const d = target - from;
    const ms = givenMs || Math.min(12000, Math.max(3000, (Math.abs(d) / 200) * 1000));
    const t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / ms);
      const eased = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo({ top: from + d * eased, behavior: "instant" });
      if (k < 1) window.requestAnimationFrame(step); else done();
    };
    window.requestAnimationFrame(step);
  }), [distance, given]);
}

export async function storyMoves(page) {
  await page.addInitScript(pointer);
  let cursor = { x: 960, y: 540 };

  /** Scroll slowly until the element sits in the window, all of it where it fits. */
  const glide = async (locator) => {
    const distance = await locator.evaluate((el) => {
      const box = el.getBoundingClientRect();
      const bottom = box.bottom - window.innerHeight + 160;
      return Math.min(bottom, box.top - 24);
    });
    if (Math.abs(distance) > 4) await scrollByEased(page, distance);
  };

  /** The pointer moved to a control before it is used, so the eye follows it there. */
  const reach = async (locator) => {
    await locator.waitFor({ state: "visible" });
    let box = await locator.boundingBox();
    const { height } = page.viewportSize();
    if (box && (box.y < 0 || box.y + box.height > height)) {
      await glide(locator);
      box = await locator.boundingBox();
    }
    if (!box) return;
    const to = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
    const ms = Math.min(900, Math.max(350, 250 + Math.hypot(to.x - cursor.x, to.y - cursor.y) * 0.45));
    await page.evaluate(([from, target, length]) => window.__storyGlide?.(from, target, length), [cursor, to, ms]);
    await page.mouse.move(to.x, to.y);
    cursor = to;
    await page.evaluate((c) => { window.__storyCursor = c; }, cursor);
    await page.waitForTimeout(150);
  };

  return {
    glide,
    reach,
    scrollBy: (distance, ms = 0) => scrollByEased(page, distance, ms),
    click: async (locator) => { await reach(locator); await locator.click(); },
    type: async (locator, text) => {
      await reach(locator);
      await locator.click();
      await locator.pressSequentially(text, { delay: 120 });
    },
    /** Park the pointer somewhere neutral, quickly, as a hand rests. */
    rest: async (x = 1500, y = 900) => {
      const to = { x, y };
      await page.evaluate(([from, target]) => window.__storyGlide?.(from, target, 500), [cursor, to]);
      await page.mouse.move(x, y);
      cursor = to;
    },
  };
}
