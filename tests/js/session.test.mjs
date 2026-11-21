// UR11: a recorded session judged against what its chapters say it shows.
import assert from 'node:assert/strict';
import test from 'node:test';

import { checkSession, chooseLines, guessLanguage, searchable, sessionLines } from '../../js/terminal-replay.mjs';

const event = ( type, content ) => JSON.stringify( { type, message: { content } } );
const call = ( id, name, input = {} ) => event( 'assistant', [ { type: 'tool_use', id, name, input } ] );
const answer = ( id, text, isError = false ) =>
	event( 'user', [ { type: 'tool_result', tool_use_id: id, content: text, is_error: isError } ] );
const say = ( text ) => event( 'assistant', [ { type: 'text', text } ] );

// A session with no skill and no verify, a teaching error escaped inside a JSON answer, and one
// line of the agent's in English.
const record = [
	event( 'user', 'Publique a trilha.' ),
	call( '1', 'mcp__shio__shio_find' ),
	answer( '1', '{"hint":"o campo n\\u00e3o existe; use \\"title\\""}' ),
	call( '2', 'mcp__shio__shio_write' ),
	answer( '2', 'ok' ),
	say( 'Escrevi a trilha e conferi o resultado no site, tudo certo com a publicação.' ),
	say( 'I have now written the trail and all of the fields are done.' ),
].join( '\n' );
const lines = sessionLines( record, { toolPrefix: 'mcp__shio__' } );

const chapters = {
	'chapter-3': [ { tools: [ 'Skill' ], required: true } ],
	'chapter-5': [ { tools: [ 'shio_find' ], match: 'não existe', required: true }, { tools: [ 'shio_write' ] } ],
	'chapter-6': [ { tools: [ 'shio_verify' ], required: true }, { kind: 'text', count: 1 } ],
};

test( 'a session missing a required beat is refused with its chapter and selector', () => {
	const checked = checkSession( lines, chapters, { language: 'pt-BR' } );
	assert.equal( checked.passed, false );
	const where = checked.findings.map( ( f ) => `${ f.chapter }#${ f.selector } ${ f.rule }` );
	assert.deepEqual( where, [ 'chapter-3#0 required', 'chapter-6#0 required', 'chapter-6#1 count' ] );
	assert.match( checked.findings[ 0 ].message, /chapter-3: selector 0 .*"Skill".* finds nothing/ );
	assert.equal( checked.findings[ 2 ].found, 2 );
} );

test( 'a match finds words a tool returned as escaped JSON', () => {
	assert.equal( searchable( 'n\\u00e3o \\"x\\"' ), 'não "x"' );
	const picked = chooseLines( lines, chapters[ 'chapter-5' ], { chapter: 'chapter-5' } );
	assert.deepEqual( [ picked[ 0 ].kind, picked[ 0 ].tool ], [ 'answer', 'shio_find' ] );
	assert.equal( picked.length, 3 ); // the find's answer, then the write's call and answer
} );

test( 'choosing a chapter refuses the same way, naming the chapter', () => {
	assert.throws( () => chooseLines( lines, chapters[ 'chapter-3' ], { chapter: 'chapter-3' } ),
		/chapter-3: selector 0 .* is required and finds nothing/ );
	assert.deepEqual( chooseLines( lines, [ { tools: [ 'Skill' ] } ] ), [] );
} );

test( 'the agent writing in another language is reported, not refused', () => {
	const checked = checkSession( lines, { 'chapter-5': [ { tools: [ 'shio_write' ], required: true } ] },
		{ language: 'pt-BR' } );
	assert.equal( checked.passed, true );
	assert.deepEqual( checked.language.map( ( l ) => l.language ), [ 'en' ] );
	assert.equal( guessLanguage( 'ok' ), null );
	assert.equal( guessLanguage( 'O agente não conferiu o que escreveu na trilha' ), 'pt' );
} );
