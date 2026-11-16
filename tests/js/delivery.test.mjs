import assert from 'node:assert/strict';
import { test } from 'node:test';
import { linesDocument } from '../../narration/buy.mjs';

const lines = [ { key: 'intro', locale: 'pt-BR', text: 'Oi' } ];

test( 'VM71: a declared speed reaches the lines file voice.lines reads', () => {
	const doc = linesDocument( { voice: 'v', model: 'eleven_v3', speed: 1.12 }, 'n/{locale}/{key}.mp3', lines );
	assert.equal( doc.speed, 1.12 );
	assert.equal( doc.voice, 'v' );
	assert.deepEqual( doc.lines, lines );
} );

test( 'VM71: undeclared delivery is left out, so existing takes stay current', () => {
	const doc = linesDocument( { voice: 'v', model: 'eleven_v3', narrator: 'calm' }, 'o', lines );
	assert.deepEqual( Object.keys( doc ), [ 'voice', 'model', 'out', 'lines' ] );
} );

test( 'VM71: every delivery key polyweave knows is carried, as numbers', () => {
	const doc = linesDocument(
		{ voice: 'v', model: 'm', stability: '0.4', similarity: 0.8, style: 0, speed: 1.1 }, 'o', lines );
	assert.deepEqual( [ doc.stability, doc.similarity, doc.style, doc.speed ], [ 0.4, 0.8, 0, 1.1 ] );
} );
