// The ffmpeg runtime every video-maker module sits on (VM2): running ffmpeg quietly or side by
// side, a pool that bounds how many encodes run at once, the encoder (NVENC where the machine
// has one, x264 elsewhere), reading a file's length and a mix's loudness, and the cuts, held
// frames and joins a timeline is made of. Nothing here knows which video it serves: the frame
// size, the frame rate and the folder the pieces go to are a context's, from `media()`.
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { availableParallelism } from 'node:os';
import { writeFileSync } from 'node:fs';
import { basename, join } from 'node:path';

// STORY_TIMING=1 prints each encode that takes over two seconds, to see where a build goes.
const timing = !! process.env.STORY_TIMING;
const timed = ( started, args ) => {
	const took = ( Date.now() - started ) / 1000;
	if ( timing && took > 2 ) {
		process.stderr.write(
			`[timing] ${ took.toFixed( 1 ) }s ${ basename( String( args.at( -1 ) ) ) }\n`
		);
	}
};

/**
 * Run ffmpeg quietly, failing loudly.
 *
 * @param {string[]} args Its arguments.
 */
export const ffmpeg = ( args ) => {
	const started = Date.now();
	const done = execFileSync( 'ffmpeg', [ '-y', '-loglevel', 'error', ...args ], {
		stdio: [ 'ignore', 'inherit', 'inherit' ],
	} );
	timed( started, args );
	return done;
};

/**
 * ffmpeg without waiting on it, for the pieces that do not depend on one another.
 *
 * @param {string[]} args Its arguments.
 * @return {Promise<void>} Settled when it exits; rejected on a failure.
 */
export const ffmpegAsync = ( args ) =>
	new Promise( ( done, fail ) => {
		const started = Date.now();
		const run = spawn( 'ffmpeg', [ '-y', '-loglevel', 'error', ...args ], {
			stdio: [ 'ignore', 'inherit', 'inherit' ],
		} );
		run.on( 'error', fail );
		run.on( 'close', ( code ) => {
			timed( started, args );
			if ( 0 === code ) {
				done();
			} else {
				fail( new Error( `ffmpeg exited ${ code }: ${ args.at( -1 ) }` ) );
			}
		} );
	} );

// How many encodes run at once. Most of a build is filters that use one core each (zoompan)
// run one after another, which left the rest of the machine idle; six at a time also stays
// under a consumer NVIDIA card's limit on concurrent encode sessions.
export const parallel = Math.max(
	1,
	Math.min( 6, Math.floor( availableParallelism() / 4 ) )
);

/**
 * Run tasks with at most `limit` of them at once, keeping their results in order.
 *
 * @param {Array<function(): Promise<*>>} tasks The tasks.
 * @param {number}                        limit How many run at once.
 * @return {Promise<Array<*>>} Their results, in the tasks' order.
 */
export const pool = async ( tasks, limit = parallel ) => {
	const results = new Array( tasks.length );
	let next = 0;
	const worker = async () => {
		while ( next < tasks.length ) {
			const n = next++;
			results[ n ] = await tasks[ n ]();
		}
	};
	await Promise.all(
		Array.from( { length: Math.min( limit, tasks.length ) }, worker )
	);
	return results;
};

/**
 * The video encoder: NVIDIA's NVENC where this machine has one, several times faster than x264
 * on a build that encodes every card, clip and dissolve; x264 elsewhere. STORY_ENCODER=x264 or
 * =nvenc forces one.
 *
 * @return {'nvenc'|'x264'} The encoder.
 */
export const detectEncoder = () => {
	const forced = process.env.STORY_ENCODER;
	if ( forced ) {
		return 'nvenc' === forced ? 'nvenc' : 'x264';
	}
	const probe = spawnSync(
		'ffmpeg',
		[
			'-hide_banner',
			'-loglevel',
			'error',
			'-f',
			'lavfi',
			'-i',
			'color=c=black:s=256x256:d=0.1',
			'-c:v',
			'h264_nvenc',
			'-f',
			'null',
			'-',
		],
		{ encoding: 'utf8' }
	);
	return 0 === probe.status ? 'nvenc' : 'x264';
};

// A keyframe every half second exactly (15 frames at 30 fps), on every piece: a dissolve then
// re-encodes only the half second it blends and copies the rest, cut on a keyframe. Without
// it, a dissolve into a chapter re-encoded the whole chapter, twenty seconds a time.
export const keyEvery = 15;

/**
 * The encoder arguments, at a quality: x264's CRF, or NVENC's constant quality at the same
 * number, which lands at about the same size and look. Every encode goes through it, so the
 * pieces stay one codec and still join without another encode.
 *
 * @param {'nvenc'|'x264'} encoder The encoder.
 * @param {number}         quality 18 to 20 here; lower is better.
 * @return {string[]} ffmpeg's video codec arguments.
 */
export const videoCodec = ( encoder, quality ) =>
	'nvenc' === encoder
		? [
				'-c:v',
				'h264_nvenc',
				'-preset',
				'p5',
				'-rc',
				'vbr',
				'-cq',
				String( quality ),
				'-b:v',
				'0',
				'-g',
				String( keyEvery ),
				'-no-scenecut',
				'1',
			]
		: [
				'-c:v',
				'libx264',
				'-preset',
				'veryfast',
				'-crf',
				String( quality ),
				'-g',
				String( keyEvery ),
				'-keyint_min',
				String( keyEvery ),
				'-sc_threshold',
				'0',
			];

/**
 * A file's length in seconds.
 *
 * @param {string} file A media file.
 */
export const seconds = ( file ) =>
	Number(
		execFileSync( 'ffprobe', [
			'-v',
			'error',
			'-show_entries',
			'format=duration',
			'-of',
			'default=noprint_wrappers=1:nokey=1',
			file,
		] )
			.toString()
			.trim()
	);

/**
 * Run ffmpeg to measure, and read the JSON loudnorm prints at the end of its log.
 *
 * @param {string[]} args Its input and filter arguments.
 * @return {Object} loudnorm's report: input_i, input_tp, input_lra, input_thresh, target_offset.
 */
export const measureLoudness = ( args ) => {
	const log = spawnSync( 'ffmpeg', [ '-hide_banner', ...args, '-f', 'null', '-' ], {
		encoding: 'utf8',
		maxBuffer: 64 * 1024 * 1024,
	} ).stderr;
	// The report is the last brace block naming input_i; ffmpeg can print more after it.
	const reports = log.match( /\{[^{}]*"input_i"[^{}]*\}/g );
	if ( ! reports ) {
		throw new Error( `loudnorm printed no report:\n${ log.slice( -2000 ) }` );
	}
	return JSON.parse( reports.at( -1 ) );
};

/**
 * One video's media context: its frame, its encoder and the folder its pieces are written to,
 * with the operations that depend on them.
 *
 * @param {{size: {width: number, height: number}, fps?: number, workDir: string, encoder?: string}} context The video's.
 */
export const media = ( { size, fps = 30, workDir, encoder = detectEncoder() } ) => {
	const codec = ( quality ) => videoCodec( encoder, quality );
	// Each card and clip encoded alike, so they join without another encode.
	const encode = [
		'-vf',
		`scale=${ size.width }:${ size.height }:force_original_aspect_ratio=decrease,pad=${ size.width }:${ size.height }:(ow-iw)/2:(oh-ih)/2,fps=${ fps },format=yuv420p`,
		...codec( 20 ),
		'-an',
	];

	/**
	 * A segment cut from a file, encoded like the rest, without running it.
	 *
	 * @param {string}   name  The part's file name.
	 * @param {string[]} input ffmpeg's input arguments, seek included.
	 * @return {{file: string, args: string[]}} The part and ffmpeg's arguments.
	 */
	const cutJob = ( name, input ) => {
		const file = join( workDir, name );
		return { file, args: [ ...input, ...encode, file ] };
	};

	/**
	 * A segment cut from a file, encoded like the rest.
	 *
	 * @param {string}   name  The part's file name.
	 * @param {string[]} input ffmpeg's input arguments, seek included.
	 */
	const cut = ( name, input ) => {
		const { file, args } = cutJob( name, input );
		ffmpeg( args );
		return file;
	};

	/**
	 * One frame of a clip, held still for a while.
	 *
	 * @param {string} clip   The clip.
	 * @param {number} at     Where the frame is, in seconds into the clip.
	 * @param {number} length How long it holds.
	 * @param {string} name   The held still's file name, without a suffix.
	 */
	const freeze = ( clip, at, length, name ) => {
		const frame = join( workDir, `${ name }.png` );
		ffmpeg( [ '-ss', at.toFixed( 3 ), '-i', clip, '-frames:v', '1', frame ] );
		const file = join( workDir, `${ name }.mp4` );
		ffmpeg( [ '-loop', '1', '-t', length.toFixed( 3 ), '-i', frame, ...encode, file ] );
		return file;
	};

	/**
	 * Join segments without another encode.
	 *
	 * @param {string[]} segments The parts, in order.
	 * @param {string}   name     The joined file's name.
	 */
	const concat = ( segments, name ) => {
		const list = join( workDir, `${ name }.txt` );
		writeFileSync(
			list,
			segments.map( ( file ) => `file '${ file.replace( /\\/g, '/' ) }'` ).join( '\n' )
		);
		const file = join( workDir, name );
		ffmpeg( [ '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', file ] );
		return file;
	};

	return { size, fps, workDir, encoder, videoCodec: codec, encode, cutJob, cut, freeze, concat };
};
