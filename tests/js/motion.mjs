// What motion/pushin.mjs and edit/stretch.mjs compute for every chapter of the golden fixtures,
// as JSON for tests/test_motion.py: the push-in windows, the zoompan filter, the moments an editor
// keys and the transform at each, the kept stretches and where sample moments land past the cuts.
//
//   node motion.mjs
import { readFileSync } from 'node:fs';
import {
	pushKey,
	pushMoments,
	pushWindows,
	zoompanFilter,
} from '../../motion/pushin.mjs';
import { along, kept } from '../../edit/stretch.mjs';

const fixtures = {
	story: { size: { width: 1920, height: 1080 }, vertical: false },
	'story-vertical': { size: { width: 1080, height: 1920 }, vertical: true },
	developer: { size: { width: 1920, height: 1080 }, vertical: false },
};
const fps = 30;

const out = {};
for ( const [ name, { size, vertical } ] of Object.entries( fixtures ) ) {
	const { chapters } = JSON.parse(
		readFileSync(
			new URL( `../../test/golden/fixtures/${ name }.json`, import.meta.url ),
			'utf8'
		)
	);
	out[ name ] = chapters.map( ( chapter ) => {
		const length = chapter.end - chapter.start;
		const windows = pushWindows( chapter, size, vertical );
		// The whole clip keyed from its start, and a piece of it from a second in.
		const keyed = [
			[ 0, length ],
			[ 1, length / 2 ],
		].map( ( [ inChapter, span ] ) =>
			windows.length
				? pushMoments( windows, inChapter, span, fps ).map( ( t ) => ( {
						t,
						...pushKey( windows, t, size ),
					} ) )
				: []
		);
		const stretches = kept( chapter, length );
		const samples = [
			0,
			length / 3,
			length,
			...( chapter.skip ?? [] ).flatMap( ( s ) => [
				s.from - chapter.start,
				s.to - chapter.start,
			] ),
			...[ chapter.voice, chapter.result ]
				.filter( Boolean )
				.map( ( line ) => line.at - chapter.start ),
		];
		return {
			windows,
			zoompan: windows.length ? zoompanFilter( windows, size ) : null,
			keyed,
			stretches,
			along: samples.map( ( t ) => [ t, along( stretches, t ) ] ),
		};
	} );
}
process.stdout.write( JSON.stringify( out ) );
