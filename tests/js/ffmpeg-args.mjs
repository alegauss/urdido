// What media/ffmpeg.mjs builds for one context, printed as JSON for tests/test_media.py.
// child_process is swapped for a recorder before the module loads, so freeze and concat
// hand over their ffmpeg arguments instead of running them.
//
//   node ffmpeg-args.mjs '{"width":1920,"height":1080,"fps":30,"workDir":"...","encoder":"x264"}'
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const fake = new URL( './fake-child-process.mjs', import.meta.url ).href;
registerHooks( {
	resolve: ( specifier, context, next ) =>
		'node:child_process' === specifier && context.parentURL?.endsWith( '/ffmpeg.mjs' )
			? { url: fake, shortCircuit: true }
			: next( specifier, context ),
} );

const { media, videoCodec } = await import( '../../media/ffmpeg.mjs' );
const { calls } = await import( fake );

const { width, height, fps, workDir, encoder } = JSON.parse( process.argv[ 2 ] );
const m = media( { size: { width, height }, fps, workDir, encoder } );

const out = {
	encode: m.encode,
	videoCodec: { nvenc: videoCodec( 'nvenc', 18 ), x264: videoCodec( 'x264', 18 ) },
	cutJob: m.cutJob( 'chapter-3.mp4', [ '-ss', '12.500', '-t', '4.250', '-i', 'take.webm' ] ),
};

calls.length = 0;
out.freeze = { file: m.freeze( 'clip.mp4', 2.3456, 1.5, 'held-1' ), calls: [ ...calls ] };

calls.length = 0;
const segments = [ join( workDir, 'a.mp4' ), join( workDir, 'b.mp4' ) ];
const joined = m.concat( segments, 'joined.mp4' );
out.concat = {
	file: joined,
	calls: [ ...calls ],
	list: readFileSync( join( workDir, 'joined.mp4.txt' ), 'utf8' ),
	segments,
};

process.stdout.write( JSON.stringify( out ) );
