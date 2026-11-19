// VM29 / PW706: refuse opening problems before voice.lines can spend on a take.
import { caption } from './takes.mjs';

const preamble = /\b(?:hoje\s+(?:eu\s+)?(?:quero|vou|vamos)|vem\s+comigo|inscreva-se|se\s+inscreva|today\s+(?:I|we)\s+(?:want|will|are\s+going)|let['’]s\s+get\s+started|subscribe\s+to\s+(?:my|our|the)\s+channel)\b/iu;
const words = (text) => caption(text).match(/[\p{L}\p{N}]+(?:['’/-][\p{L}\p{N}]+)*/gu) ?? [];

/** Check selected languages. Timing is an estimate at the declared narrator pace,
 * and proof is an editor's declared first visual, never inferred from the prose. */
export function checkOpening({ narration, locale = null }) {
  const { script } = narration;
  const languages = locale ? [locale] : Object.keys(script.intro);
  const report = [];
  for (const language of languages) {
    const intro = script.intro[language];
    if (typeof intro !== 'string') throw new Error(`opening ${language}: no intro text`);
    const found = caption(intro).match(preamble);
    if (found) throw new Error(`opening ${language}: remove the preamble "${found[0]}" before buying narration`);
    if (!script.opening) continue;
    const pace = script.opening.words_per_minute?.[language];
    const proof = script.opening.proof?.[language];
    if (!Number.isFinite(pace) || pace <= 0) {
      throw new Error(`opening ${language}: declare a positive words_per_minute for the narrator`);
    }
    if (!proof || !Number.isInteger(proof.before_word) || proof.before_word < 0) {
      throw new Error(`opening ${language}: declare proof.take and a zero-based proof.before_word`);
    }
    let count = 0;
    let reached = false;
    for (const [key, texts] of narration.lines()) {
      if (typeof texts?.[language] !== 'string') {
        throw new Error(`opening ${language}: missing text for ${key}`);
      }
      const length = words(narration.spoken(language, texts[language])).length;
      if (key === proof.take) {
        if (proof.before_word >= length) throw new Error(`opening ${language}: proof word is outside ${key}`);
        count += proof.before_word;
        reached = true;
        break;
      }
      count += length;
    }
    if (!reached) throw new Error(`opening ${language}: unknown proof take ${proof.take}`);
    const seconds = count * 60 / pace;
    if (seconds > 20) {
      throw new Error(`opening ${language}: first proof estimated at ${seconds.toFixed(1)} s; move it within 20 s before buying narration`);
    }
    report.push({ language, words: count, seconds });
  }
  return report;
}
