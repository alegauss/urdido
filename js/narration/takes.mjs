// A video's narration (VM3): its script, the takes that speak it and whether each is current.
// Every video's script.json has one shape: `voice` and `model`, an `intro`, per chapter a `card`
// (the line over the action) and a `result`, an `outro`, each a text by language; optionally
// chapter `title`s and `pronounce`, a map of whole words per language spelled as the voice must
// say them (Viglet Shio is said "xiô", eleven_v3 takes no phoneme markup). The captions keep the
// written words; `spoken()` is what the voice says and what a take's provenance records.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { seconds } from '../recording/seconds.mjs';

/**
 * A narration script, read from its file.
 *
 * @param {string} file The script.json.
 * @return {Object} The script.
 */
export const loadScript = ( file ) => JSON.parse( readFileSync( file, 'utf8' ) );

/**
 * What the captions show for a line: the delivery tags ([happy], [laughs]) taken out.
 *
 * @param {string} text The line as written.
 */
export const caption = ( text ) => text.replace( /\[[^\]]+\]\s*/g, '' ).trim();

/**
 * One narration's takes.
 *
 * @param {{script: Object, dir: string}} narration The script, and the folder its takes are in,
 *                                                  one subfolder per language.
 */
export const takes = ( { script, dir } ) => {
	/**
	 * What the voice says for a line: each word of `pronounce` spelled as it sounds.
	 *
	 * @param {string} language The language, as the script names it.
	 * @param {string} text     The line as written.
	 */
	const spoken = ( language, text ) =>
		Object.entries( script.pronounce?.[ language ] ?? {} ).reduce(
			( said, [ word, sound ] ) =>
				said.replace( new RegExp( String.raw`\b${ word }\b`, 'g' ), sound ),
			text
		);
	return {
		script,
		dir,
		spoken,
		caption,
		/**
		 * Every line the video speaks, by its take's name: the opening, each chapter's line over
		 * its action and the one about its result, and the closing.
		 *
		 * @return {Array<[string, Object<string, string>]>} Each take's name and its text by language.
		 */
		lines: () => [
			[ 'intro', script.intro ],
			...Object.entries( script.chapters ).flatMap( ( [ n, chapter ] ) => [
				[ `chapter-${ n }`, chapter.card ],
				[ `chapter-${ n }-result`, chapter.result ],
			] ),
			[ 'outro', script.outro ],
		],
		/**
		 * Where a take lives.
		 *
		 * @param {string} language The language, as the script names it.
		 * @param {string} name     The take's name.
		 */
		takeFile: ( language, name ) => join( dir, language, `${ name }.mp3` ),
		/**
		 * Whether a take already says this line, in this voice and model: a take of an older script
		 * is neither placed in the video nor kept from being bought again.
		 *
		 * @param {string}  file     The take.
		 * @param {?string} language The line's language; it picks the pronunciation map.
		 * @param {string}  text     The line as written.
		 */
		current: ( file, language, text ) => {
			const record = `${ file }.prov.json`;
			if ( ! existsSync( file ) || ! existsSync( record ) ) {
				return false;
			}
			const prov = JSON.parse( readFileSync( record, 'utf8' ) );
			return (
				prov.prompt === spoken( language, text ) &&
				prov.details?.voice === script.voice &&
				prov.engine?.model === script.model
			);
		},
		length: seconds,
	};
};
