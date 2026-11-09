// Buys a narration's takes (VM3) through polyweave's voice.lines (PW665): it plans every line
// and language, skips each take whose spoken line, voice and model are unchanged, spends inside
// the budget in the project's polyweave.toml, and records each take's provenance beside it. A
// rerun buys nothing. Needs ELEVENLABS_API_KEY and polyweave (`python -m polyweave`).
import { execFileSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';

/**
 * polyweave, answering as data.
 *
 * @param {string}    root The project whose ledger and budget it spends against.
 * @param {...string} args The verb and its arguments.
 */
export const polyweave = ( root, ...args ) =>
	JSON.parse(
		execFileSync( 'python', [ '-m', 'polyweave', ...args, '--root', root, '--json' ], {
			encoding: 'utf8',
		} )
	);

/**
 * Buy what is missing, or with `dry` only plan it.
 *
 * @param {Object}                     options
 * @param {string}                     options.root      The project (its polyweave.toml).
 * @param {ReturnType<import('./takes.mjs').takes>} options.narration The narration, from `takes()`.
 * @param {string}                     options.linesFile Where the lines file voice.lines reads goes,
 *                                                       relative to the root; rewritten every run.
 * @param {?string}                    options.locale    One language only; all when null.
 * @param {boolean}                    options.dry       Plan, spend nothing.
 * @param {boolean}                    options.adopt     Take over the takes sound.speak bought for
 *                                                       the same words, voice and model (PW691),
 *                                                       buying none: a person's call, made after
 *                                                       hearing the dry answer's `adoptable`.
 * @return {{planned: Array<{key: string, locale: string}>, current: Array, adoptable: Array}}
 *         What it bought (or would buy), what was current, and what it could adopt.
 */
export const buy = ( {
	root,
	narration,
	linesFile,
	locale = null,
	dry = false,
	adopt = false,
} ) => {
	const { script, lines, spoken, dir } = narration;
	const all = lines().flatMap( ( [ key, texts ] ) =>
		Object.entries( texts ).map( ( [ language, text ] ) => ( {
			key,
			locale: language,
			text: spoken( language, text ),
		} ) )
	);
	const out = `${ relative( root, dir ).replace( /\\/g, '/' ) }/{locale}/{key}.mp3`;
	mkdirSync( dirname( join( root, linesFile ) ), { recursive: true } );
	writeFileSync(
		join( root, linesFile ),
		JSON.stringify( { voice: script.voice, model: script.model, out, lines: all }, null, 2 ) +
			'\n'
	);
	const answer = polyweave(
		root,
		'voice.lines',
		'--script',
		linesFile,
		...( locale ? [ '--locale', locale ] : [] ),
		'--spend',
		dry ? 'false' : 'true',
		...( adopt ? [ '--adopt', 'true' ] : [] )
	);
	return {
		planned: answer.voice ?? [],
		current: answer.current ?? [],
		adoptable: answer.adoptable ?? [],
	};
};
