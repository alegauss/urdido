// The Viglet Shio promo's terminal chapters as its declaration chooses them (VM11), beside the
// selection story-terminal.mjs made by hand before it, as JSON for tests/test_terminal.py.
//
//   node terminal.mjs
import { readFileSync } from 'node:fs';
import { chooseLines, initLine, markdownHtml, sessionLines } from '../../terminal-replay.mjs';

const promo = new URL( '../../../shio/promo/', import.meta.url );
const declared = JSON.parse( readFileSync( new URL( 'demo/agent/terminal.json', promo ), 'utf8' ) );
const record = readFileSync( new URL( 'recordings/pt/agent.jsonl', promo ), 'utf8' );
const prompt = readFileSync( new URL( 'demo/agent/prompt.pt-BR.md', promo ), 'utf8' ).trim();
const lines = sessionLines( record, {
	toolPrefix: declared.toolPrefix,
	answerLines: declared.answerLines,
} );
const init = initLine( record, declared.plugin );

const declaredChapters = Object.fromEntries(
	Object.entries( declared.chapters ).map( ( [ id, selectors ] ) => [
		id,
		chooseLines( lines, selectors, { prompt, init } ),
	] )
);

// The selection as story-terminal.mjs wrote it by hand before VM11, its typed note left out, and its
// errors narrowed to Viglet Shio's own writing tools, as the declaration now asks.
const calls = ( tools ) => lines.filter( ( l ) => tools.includes( l.tool ) );
const before = {
	'chapter-3': [ ...lines.filter( ( l ) => l.tool === 'Skill' ), ...calls( [ 'shio_context' ] ) ],
	'chapter-4': [ { kind: 'prompt', text: prompt } ],
	'chapter-5': [
		...calls( [ 'shio_find', 'shio_read' ] ).slice( 0, 6 ),
		...lines.filter( ( l ) => l.kind === 'text' && /dry run|escrev|writ/i.test( l.text ) ),
		...calls( [ 'shio_write' ] ),
		...lines.filter( ( l ) => l.kind === 'error' && [ 'shio_write', 'shio_apply', 'shio_publish' ].includes( l.tool ) ),
	],
	'chapter-6': [
		...calls( [ 'shio_verify', 'shio_digest' ] ).slice( 0, 6 ),
		...lines.filter( ( l ) => l.kind === 'text' ).slice( -1 ),
	],
};

// The report that closes chapter 6, as the scene shows it (formatted, not raw Markdown).
const report = declaredChapters[ 'chapter-6' ].at( -1 );
const shown = markdownHtml( report.text );
// VM65: formatting coverage must survive a retake whose report uses different Markdown.
const fixture = readFileSync( new URL( '../fixtures/terminal-report.md', import.meta.url ), 'utf8' );
const formattedFixture = markdownHtml( fixture );

process.stdout.write( JSON.stringify( { declared: declaredChapters, before, init, record, shown, formattedFixture } ) );
