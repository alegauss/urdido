// The time maps of a chapter's clip (VM13): the waits a story marked (`skip` in chapters.json,
// from `skipping()` in the spec) cut out, and where a moment lands once they are. Pure functions;
// video-maker/videomaker/edit/stretch.py is their Python port, held to these by
// tests/test_motion.py.

// An AI answer being written is a wait a viewer should not sit through. A moment of it is kept
// either side, so the cut reads as the answer arriving rather than a jump; a wait shorter than a
// second stays.
export const skipKeep = { before: 0.6, after: 0.3, least: 1 };

/**
 * The stretches of a chapter's clip the video keeps, in seconds from its start: all of it, less
 * the waits it marked.
 *
 * @param {{start: number, skip?: Array<{from: number, to: number}>}} chapter Its timings.
 * @param {number}                                                    length  Its clip's length.
 * @return {Array<Array<number>>} The kept stretches, in order.
 */
export const kept = ( { start, skip = [] }, length ) => {
	const stretches = [];
	let from = 0;
	for ( const wait of skip ) {
		const a = wait.from - start + skipKeep.before;
		const b = Math.min( length, wait.to - start - skipKeep.after );
		if ( b - a >= skipKeep.least && a > from ) {
			stretches.push( [ from, a ] );
			from = b;
		}
	}
	stretches.push( [ from, length ] );
	return stretches;
};

/**
 * Where a moment of the chapter falls once its waits are cut.
 *
 * @param {Array<Array<number>>} stretches The kept stretches.
 * @param {number}               t         Seconds from the chapter's start, as recorded.
 * @return {number} Seconds from the chapter's start, as the video plays it.
 */
export const along = ( stretches, t ) =>
	stretches.reduce(
		( sum, [ a, b ] ) => sum + Math.max( 0, Math.min( b, t ) - a ),
		0
	);
