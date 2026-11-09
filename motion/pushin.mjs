// The push-in that follows the action (D292, VM13): for each element a chapter marked (`focus` in
// chapters.json), the frame eases in on that element's box while the step runs and back out before
// the next. Pure functions of the frame size and the chapter's marks, read by the MP4's zoompan
// and the Resolve project's transform keyframes alike; video-maker/videomaker/motion/pushin.py is
// their Python port, held to these by tests/test_motion.py.

// The most the frame zooms, so text stays sharp from a 1080p source; the room kept around the
// element; and how long the move takes either way: slow, while the narrator talks, up to `slow`
// seconds each way when the step lasts long enough, never under `ease`. A focus with less time
// than both short moves and a hold is left at the full frame. `over` is how much the recording
// is enlarged before zoompan, which crops at whole pixels of its input: at 1x those steps showed
// as a shake on a slow move.
export const pushIn = {
	cap: 1.6,
	margin: 1.25,
	ease: 0.8,
	slow: 2.5,
	hold: 0.5,
	over: 2,
};

/**
 * A chapter's push-ins: one window per focused element it holds long enough, with its zoom and
 * centre, in seconds from the chapter's start. A vertical cut is already a phone's page, so it
 * has none.
 *
 * @param {{start: number, end: number, focus?: Array<{at: number, box?: Object}>}} chapter Its timings.
 * @param {{width: number, height: number}}                                       size    The frame.
 * @param {boolean}                                                               vertical Whether the cut is 9:16.
 * @return {Array<{from: number, to: number, zoom: number, cx: number, cy: number, ease: number}>} The windows.
 */
export const pushWindows = ( { start, end, focus = [] }, size, vertical = false ) =>
	vertical
		? []
		: focus
				.map( ( { at, box }, n ) => ( { at, box, n } ) )
				// A mark with no box is a release: it only ends the window before it.
				.filter( ( { box } ) => box )
				.map( ( { at, box, n } ) => ( {
					from: at - start,
					to: ( focus[ n + 1 ]?.at ?? end ) - start,
					zoom: Math.min(
						pushIn.cap,
						size.width / ( box.width * pushIn.margin ),
						size.height / ( box.height * pushIn.margin )
					),
					cx: Math.min(
						size.width,
						Math.max( 0, box.x + box.width / 2 )
					),
					cy: Math.min(
						size.height,
						Math.max( 0, box.y + box.height / 2 )
					),
				} ) )
				.filter(
					( w ) =>
						w.zoom >= 1.1 &&
						w.to - w.from >= 2 * pushIn.ease + pushIn.hold
				)
				.map( ( w ) => ( {
					...w,
					ease: Math.min(
						pushIn.slow,
						Math.max(
							pushIn.ease,
							( w.to - w.from - pushIn.hold ) / 2
						)
					),
				} ) );

/**
 * The push-in at a moment, as zoompan draws it: the zoom, and the point of the page at the
 * frame's centre, clamped so the frame never leaves the page.
 *
 * @param {Array<Object>}                   windows The chapter's windows.
 * @param {number}                          t       Seconds from its start.
 * @param {{width: number, height: number}} size    The frame.
 * @return {{zoom: number, x: number, y: number}} The zoom and the centre shown.
 */
export const pushAt = ( windows, t, size ) => {
	const weights = windows.map( ( { from, to, ease } ) => {
		const ramp = Math.min(
			1,
			Math.max( 0, Math.min( ( t - from ) / ease, ( to - t ) / ease ) )
		);
		return ramp * ramp * ( 3 - 2 * ramp );
	} );
	const zoom =
		1 +
		windows.reduce( ( s, w, n ) => s + ( w.zoom - 1 ) * weights[ n ], 0 );
	const centre = ( axis, half ) =>
		half +
		windows.reduce(
			( s, w, n ) => s + ( w[ axis ] - half ) * weights[ n ],
			0
		);
	const shown = ( axis, extent ) => {
		const half = extent / zoom / 2;
		return Math.min(
			extent - half,
			Math.max( half, centre( axis, extent / 2 ) )
		);
	};
	return {
		zoom,
		x: shown( 'cx', size.width ),
		y: shown( 'cy', size.height ),
	};
};

/**
 * The push-ins as ffmpeg's video filter: the clip enlarged, then zoompan along the windows, each
 * weighted at the frame's time by a smoothstep.
 *
 * @param {Array<Object>}                   windows The chapter's windows, at least one.
 * @param {{width: number, height: number}} size    The frame.
 * @return {string} The `-vf` value.
 */
export const zoompanFilter = ( windows, size ) => {
	const time = 'in/30';
	const weight = ( { from, to, ease } ) => {
		const ramp = `clip(min((${ time }-${ from.toFixed( 3 ) })/${ ease.toFixed(
			3
		) },(${ to.toFixed( 3 ) }-${ time })/${ ease.toFixed( 3 ) }),0,1)`;
		return `(${ ramp }*${ ramp }*(3-2*${ ramp }))`;
	};
	const sum = ( term ) => windows.map( term ).join( '+' );
	const zoom = `1+${ sum(
		( w ) => `${ ( w.zoom - 1 ).toFixed( 4 ) }*${ weight( w ) }`
	) }`;
	// Centres in the enlarged input's pixels.
	const { over } = pushIn;
	const centre = ( axis, half ) =>
		`${ half * over }+${ sum(
			( w ) =>
				`${ ( ( w[ axis ] - half ) * over ).toFixed( 1 ) }*${ weight( w ) }`
		) }`;
	return (
		`scale=${ size.width * over }:${ size.height * over }:flags=lanczos,` +
		`zoompan=z='${ zoom }':` +
		`x='clip(${ centre( 'cx', size.width / 2 ) }-iw/zoom/2,0,iw-iw/zoom)':` +
		`y='clip(${ centre( 'cy', size.height / 2 ) }-ih/zoom/2,0,ih-ih/zoom)':` +
		`d=1:s=${ size.width }x${ size.height }:fps=30,format=yuv420p`
	);
};

/**
 * The moments a clip's push-ins are keyed at in an editor: its start and end, and where each move
 * starts, is halfway and ends, one key per frame.
 *
 * @param {Array<Object>} windows   The chapter's windows.
 * @param {number}        inChapter Where the clip starts, in seconds from the chapter's start.
 * @param {number}        length    How long the clip plays.
 * @param {number}        fps       The timeline's frame rate.
 * @return {number[]} The moments, in seconds from the chapter's start.
 */
export const pushMoments = ( windows, inChapter, length, fps ) => {
	const until = inChapter + length;
	return [
		inChapter,
		...windows.flatMap( ( w ) => [
			w.from,
			w.from + w.ease / 2,
			w.from + w.ease,
			w.to - w.ease,
			w.to - w.ease / 2,
			w.to,
		] ),
		until,
	]
		.filter( ( t ) => t >= inChapter && t <= until )
		.sort( ( a, b ) => a - b )
		// One key per frame: two windows that meet would key the same frame twice.
		.filter(
			( t, n, all ) =>
				0 === n ||
				Math.round( t * fps ) !== Math.round( all[ n - 1 ] * fps )
		);
};

/**
 * The push-in at a moment as FCPXML's transform: scale, and position in a hundredth of the frame's
 * height with y up.
 *
 * @param {Array<Object>}                   windows The chapter's windows.
 * @param {number}                          t       Seconds from the chapter's start.
 * @param {{width: number, height: number}} size    The frame.
 * @return {{scale: string, position: string}} The two keyframe values.
 */
export const pushKey = ( windows, t, size ) => {
	const { zoom, x, y } = pushAt( windows, t, size );
	const unit = 100 / size.height;
	return {
		scale: `${ zoom.toFixed( 4 ) } ${ zoom.toFixed( 4 ) }`,
		position: `${ ( -zoom * ( x - size.width / 2 ) * unit ).toFixed( 3 ) } ${ (
			zoom *
			( y - size.height / 2 ) *
			unit
		).toFixed( 3 ) }`,
	};
};
