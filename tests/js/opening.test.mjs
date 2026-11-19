import assert from 'node:assert/strict';
import { test } from 'node:test';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkOpening } from '../../js/narration/opening.mjs';
import { takes } from '../../js/narration/takes.mjs';
import { buy } from '../../js/narration/buy.mjs';

const make = (intro = 'one two three four') => takes({ dir: '.', script: {
  intro: { en: intro }, chapters: { 1: { card: { en: 'proof here' }, result: { en: 'done' } } },
  outro: { en: 'bye' },
  opening: { words_per_minute: { en: 12 }, proof: { en: { take: 'chapter-1', before_word: 0 } } },
} });

test('VM29: a proof at 20 seconds passes and one word later fails', () => {
  assert.equal(checkOpening({ narration: make() })[0].seconds, 20);
  assert.throws(() => checkOpening({ narration: make('one two three four five') }), /25.0 s/);
});

test('VM29: proof can occur inside the intro; delivery tags do not consume words', () => {
  const narration = make('[happy] one two three four');
  narration.script.opening.proof.en = { take: 'intro', before_word: 1 };
  assert.equal(checkOpening({ narration })[0].seconds, 5);
});

test('VM29: Unicode words and pronunciation substitutions determine the estimate', () => {
  const narration = make('[happy] Olá, CMS!');
  narration.script.pronounce = { en: { CMS: 'content management system' } };
  assert.equal(checkOpening({ narration })[0].words, 4);
  assert.equal(checkOpening({ narration })[0].seconds, 20);
});

test('VM29: missing chapter translations cannot shorten the proof estimate silently', () => {
  const narration = make();
  narration.script.opening.proof.en = { take: 'chapter-1-result', before_word: 0 };
  delete narration.script.chapters[1].card.en;
  assert.throws(() => checkOpening({ narration }), /missing text for chapter-1/);
});

test('VM29: missing or invalid proof declarations are refused', () => {
  for (const proof of [undefined, { take: 'missing', before_word: 0 },
    { take: 'intro', before_word: -1 }, { take: 'intro', before_word: 4 },
    { take: 'intro', before_word: 0.5 }]) {
    const narration = make();
    narration.script.opening.proof.en = proof;
    assert.throws(() => checkOpening({ narration }), /proof/);
  }
  for (const pace of [0, -1, NaN, Infinity, '120']) {
    const narration = make();
    narration.script.opening.words_per_minute.en = pace;
    assert.throws(() => checkOpening({ narration }), /positive words_per_minute/);
  }
});

test('VM29: locale selection checks the purchased translation only', () => {
  const narration = make();
  narration.script.intro['pt-BR'] = 'Hoje eu quero te contar uma história.';
  assert.equal(checkOpening({ narration, locale: 'en' }).length, 1);
  assert.throws(() => checkOpening({ narration }), /preamble/);
  assert.throws(() => checkOpening({ narration, locale: 'fr' }), /no intro text/);
});

test('VM29: legacy scripts still reject preambles without a timing declaration', () => {
  for (const intro of ['Hoje eu quero te contar, com calma. Vem comigo!',
    'Today we will explain the product.', 'Subscribe to our channel.']) {
    const narration = make(intro);
    delete narration.script.opening;
    assert.throws(() => checkOpening({ narration }), /preamble/);
  }
  const narration = make('The product finds the answer.');
  delete narration.script.opening;
  assert.deepEqual(checkOpening({ narration }), []);
});

test('VM29: an invalid opening never reaches purchase or writes the lines file', () => {
  const root = mkdtempSync(join(tmpdir(), 'vm29-'));
  try {
    assert.throws(() => buy({ root, narration: make('Vem comigo!'), linesFile: 'lines.json' }), /preamble/);
    assert.equal(existsSync(join(root, 'lines.json')), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
