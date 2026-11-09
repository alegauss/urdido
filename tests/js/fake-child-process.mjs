// Stands in for node:child_process under ffmpeg-args.mjs: records each ffmpeg call's
// arguments and runs nothing.
export const calls = [];

export const execFileSync = ( command, args ) => {
	calls.push( args );
	return Buffer.from( '' );
};

export const spawn = () => {
	throw new Error( 'spawn is not recorded' );
};

export const spawnSync = () => ( { status: 1, stderr: '' } );
