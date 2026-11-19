// A media file's length, for the recording side (VM17): the narration reader Turing's specs
// import and the scene listings a recording writes. The assembly is Python (videomaker/media.py).
import { execFileSync } from 'node:child_process';

/**
 * A file's length in seconds.
 *
 * @param {string} file A media file.
 * @return {number} Its length.
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
