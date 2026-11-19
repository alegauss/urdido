# Improvements

## Block A — Package foundation (urdido installable from PyPI)

## Block B — The engine extracted (videomaker without marketing)

## Block C — Adoption in marketing (video-maker replaced by urdido)

## Block D — Inherited from video-maker (marketing Block B)

### §UR1 Titles and thumbnails checked as a pair (was marketing VM30)

The Scion thumbnail says "O Git não aguentou" and "30 mil merges por dia"; its title is
"30 mil merges por dia: o Git não aguentou e a Anthropic...", which the Studio list
itself shows cut. The two say the same thing twice and the end of the title is never
read.

Rules from youtube-agent-skill's title linter and the thumbnail guides of claude-youtube
and youtube-agent-pro, read on 2026-11-12:

- a title keeps its point inside 60 characters (desktop search) and ideally 40 (the phone feed); 100 is only YouTube's hard limit;
- a number, a name or a date in it; at most two words in capitals; no empty superlatives;
- the thumbnail shares no meaningful word with the title: it adds what the title leaves out (a picture of the stakes, a number the title does not say);
- three words on the thumbnail at most, legible at about 168 x 94 px, one face or one object, two or three colours;
- the first five seconds of the video continue the thumbnail's promise;
- a Short's title stays under 60 characters, with 3 to 5 hashtags in the description.

The check runs where the thumbnail and the description are made, and refuses a pair that
breaks the first three rules. The Google Ads limits already written in japode/brand
stay.

Done when the Scion and Docker titles and thumbnails pass the check, or are rewritten
until they do.

### §UR2 Shorts cut by the framework (was marketing VM31)

The Docker and Scion Shorts are cut by scripts copied into each video
(japode/*/bin/short.py); only the Scion copy carries what was learned on 2026-11-12.

What the Scion cutter does now, and every video's Shorts should:

- no frozen end card: a Short is replayed in a loop and replays count, so the last word runs straight back into the hook; the pointer to the full video replaces the hook for the last 2.6 s, over the moving picture;
- a visual change every 2 to 4 s: a shot longer than 3.6 s is punched in to 1.1 at its middle (never a terminal, whose lines the 4:3 cut already trims);
- the voice 1.1 times faster, pitch kept, and 0.35 s after the last word;
- captions burned in, word-timed, 20 characters a line, numbers in the brand's green, inside the safe area (clear of the right 140 px from y 900 to 1700 and of the bottom 420 px);
- the channel's look: night green with the glow, green rules around the picture;
- loudness near -14 LUFS, true peak under -1 dBTP;
- three Shorts per long video, posted a day or more apart, each self-contained, 20 to 55 s, opening on a number.

Sources: Melvynx/video-agent-skills, Ansub/long-to-shorts, youtube-agent-skill.
claude-youtube adds that a Short's related-video link converts under 1%: Shorts get the
channel found, they do not feed the long video.

Done when video-maker cuts the Shorts from any built video's plan and both Japode videos
use it.

### §UR3 End screens and cards (was marketing VM33)

Neither the Docker nor the Scion video has an end screen or a card, so a viewer who
reaches the end of one is offered nothing from the channel, and YouTube's own suggestion
takes them elsewhere.

Rules from youtube-agent-pro's yt-endscreen and claude-youtube, read on 2026-11-12:

- the end screen covers the last 5 to 20 s, so the video's closing card leaves that space free of text;
- it points at the video that continues the subject (Docker to Scion, a Viglet demo to the next step), never just the newest upload;
- at most one video element and one subscribe element;
- 0 to 2 cards, placed just before a known drop on the retention curve, never on a peak;
- the narration's last line sets it up ("the next one is about...") instead of a bare like-and-subscribe.

The build writes, beside the description, which video the end screen points at and the
second each card goes in, so the Alexandre sets them in Studio in one pass.

### §UR4 The explainer video on video-maker (was marketing VM34)

video-maker was grown from the recorded product demo (Viglet Turing for WordPress,
Viglet Shio), and the first video of another kind went around it. The Japode Docker and
Scion videos each carry their own build.py, narration.mjs, check-takes.py, capture and
film scripts, thumbnail.py and short.py, and the two copies already differ (the Scion
one has the brand and the new Shorts rules, the Docker one does not).

What an explainer needs from the framework, all of it already working in japode/scion:

- shots from Creative Commons footage, each a source, a start second, a duration, a speed and a box that keeps an author's own text out, panned slowly;
- a web page filmed with a highlighter drawn over the quoted sentence, and a terminal session captured for real and filmed;
- callouts timed to the words said, with a one-line definition for a new term;
- a channel theme (japode/brand: fonts, colours, logo, thumbnail layout) as the cards theme is for the product videos;
- the description with chapters and the CC BY credits of the clips actually used;
- the Shorts, through VM31.

Done when the Docker and Scion videos are each a video.toml built by `python -m
videomaker build`, their copied bin/ scripts are removed, and the published cuts are
reproduced (the golden-check rule of Block B). This is also the condition for giving
video-maker a repository of its own: two owners, Viglet and Japode, using it.

### §UR5 A video cannot be built as a variant of another (was marketing VM68)

Where it happened: the published WordPress episode (`japode/wordpress`) lost most of its
audience between 8 s and 19 s (YouTube Studio, 2026-11-16: 94% to 58% at 8 s, under 30%
at 19 s). The owner asked for a second cut with a new opening to re-upload and compare
retention.

What was done by hand: `robocopy japode\wordpress japode\wordpress2` copied 722 MB of
footage, takes, ledgers, instance records and the whole declaration, only to change
three takes (intro, chapter-1, chapter-1-result), two scene lists in `storyboard.json`,
two highlight lists, three caption translations and one claim. A throwaway script in the
scratchpad rewrote those JSON files. From now on the two folders drift apart: any
credit, claim or source fix in one must be repeated in the other, and nothing says which
is the published cut.

What video-maker should do: let a declaration build a variant of another video, for
example `[video] base = "../wordpress"` plus overrides for the takes, scenes and
highlights that differ. It should reuse the base's media, takes and ledgers without
copying them, write its output to its own folder, and record in the review which variant
was uploaded and against which retention report it is being compared (with VM32).

### §UR6 A rejected asset can return to a cut (was marketing VM69)

Where it happened: `japode/wordpress2`, a second opening for the WordPress episode
(`python -m videomaker build japode/wordpress2/video.toml --language pt-BR`). The new
chapter-1 scene put the `code` stock clip under "Como o código era aberto". The cut
built cleanly.

What was caught by hand: a contact sheet of the first 45 s showed the clip is the
"hacker" terminal (ACCESS TO SYSTEM, SECURITY ALERT, Encrypting) that the VM38 review of
the first cut had already removed because it contradicted the narration. That decision
lives only in prose, in `japode/wordpress/README.md`. The asset stayed in the `media`
list of `storyboard.json`, so nothing stopped it from coming back.

What video-maker should do: let the storyboard mark a media entry as rejected, with the
reason and optionally the time range (`rejected = "terminal de hacker com SECURITY
ALERT; contradiz a fala"`). `build` and `--plan` should then refuse any scene that uses
it, citing that reason.

### §UR7 A take cannot be re-rolled with the same text (was marketing VM70)

Where it happened: `japode/wordpress2`, the chapter-1 take bought on 2026-11-16
(eleven_v3, Leo Antonio, pt-BR). The owner heard European Portuguese between 0:28 and
0:35 of the cut. The build, the Scribe transcription and the QA all passed. Scribe
reports only `por`, so nothing told Brazilian from European Portuguese.

What was done by hand: the narration buyer has no way to buy a take again when its text
has not changed (`video-maker/narration/buy.mjs` treats the take as current). To get a
new take, the text had to be rewritten. That worked here because more Brazilian phrasing
("fazia meses que ninguém atualizava") also helps the accent, but a take with good text
could not be re-rolled at all.

What video-maker should do:
- let a take be marked for re-purchase (`retake = ["chapter-1"]`, or a `--retake` option), with
  the reason kept in the ledger;
- record which takes the owner flagged for accent, so a voice or model that keeps drifting shows
  up across videos.

### §UR8 A thumbnail picture is not checked against the video (was marketing VM73)

Where it happened: `japode/wordpress2`, on 2026-11-16 (`python -m videomaker thumbnail
japode/wordpress2/video.toml --language pt-BR`). The owner asked for the WordPress logo
alone in place of Matt Mullenweg.

What happened: the only large logo in the video's sources is inside the 20th-anniversary
emblem (`wp20.webm`). Cropping the W alone would have stretched about 140 px to 660. So
the official mark was downloaded by hand from wordpress.org/about/logos into
`footage/wordpress-wmark-white.png`, with a hand-written `.prov.json` (trademark policy,
URL, hash). It does not appear in the cut. `thumbnail.py` says every picture is a frame
of the video's own sources, but it checks only that the file exists. The white mark on
transparent landed well on the layout's background by luck: nothing declares how a
graphic is placed (size, margin, background).

What video-maker should do:
- check that `thumbnail.picture` and `thumbnail.proof` are media the storyboard declares, or
  sources the cut shows, and refuse otherwise unless the declaration marks them as thumbnail-only
  with a reason;
- require their provenance (license, author, URL) like any storyboard media;
- let a graphic declare its placement instead of the photo-style `cover` crop.

### §UR9 Descriptions for scene videos (was marketing VM80)

`[description]` writes a ready description with measured chapter times, but only for the
illustrated source (`sources/illustrated.py`). The Viglet Shio promo is made of filmed
scenes, so on 2026-11-17 its chapter times were read by hand: the first caption of each
chapter's card line, matched by its first words in promo.pt-BR.srt. Two takes bought
later the same day moved five chapters by a second, and the draft had to be corrected
again.

The timeline already knows where each chapter starts; the scenes build should write the
same description file from it, with the chapter titles from the script and the notes
from `[description]`.

**Done when** the Viglet Shio promo's build writes its description with chapter times,
and the draft in alegauss/visibility takes them from it.

### §UR10 One command records a scene video (was marketing VM81)

Recording the Viglet Shio promo is six commands from its README, in an order that
matters: the first scenes on a fresh instance, the agent's session, the terminal
replays, the later scenes on the same instance with --reuse, the cold open, then the
instance down. On 2026-11-17 they were chained by hand with `&&` behind `| tail`, so
when the chapter-2 scene timed out on a new image the agent still ran, on an instance
with no Quilhara, and wrote a useless session over the good one. The previous recordings
had to be copied aside by hand first, because a re-recording overwrites them.

`videomaker record` should run the steps declared in video.toml (each a command and the
scenes it makes), stop at the first failure, keep the last complete recording until the
new one is complete, and say which step to resume from.

**Done when** the Viglet Shio promo is recorded with one command, and a failing scene
leaves the previous recording intact.

### §UR11 A session checked against its chapters (was marketing VM82)

The Viglet Shio promo's chapters 3 to 6 replay a real Claude Code session, and the
narration says what happens in it: the plugin's skill loads, the agent asks Viglet Shio
what is there, a call goes wrong and Viglet Shio says how to fix it, the agent checks
its work once before saying it is done. On 2026-11-17 three sessions were recorded and
read by hand with one-off Python: one had no skill and no verify, the next no skill and
no error, and the agent wrote one line in English in a Portuguese session. The fourth,
on the new image, did have Viglet Shio's teaching errors (inside shio_read's answer),
but the hand check missed them because the text was escaped in the JSON, and a correct
line was rewritten and bought twice before the cut showed them in red.

terminal.json's selectors already name what each chapter shows. A selector marked
required should refuse a session where it picks nothing, a count should refuse two
reports where one is wanted, and lines in the wrong language should be reported, so a
session is judged before anything is filmed after it.

**Done when** a session missing a required beat is refused with the chapter and the
selector that found nothing.

### §UR12 A review sheet for scene videos (was marketing VM83)

`videomaker build --plan` prints a review sheet for illustrated videos (`review.sheet`),
one frame per beat with its line. A video made of filmed scenes has none. On 2026-11-17
every check of the Viglet Shio promo was a frame grabbed by hand: the corner mark over
the console and over a light page, the purple closing card, the Marketplace search, the
agent's prompt and its final report, the thumbnail at 320x180 and 168x94. Each was an
ffmpeg call with a guessed second and a stacked image in the scratchpad.

The build knows where each chapter, card and line sits. It should write a contact sheet
for a scene video: a frame at the start, the middle and the end of each chapter with its
title and spoken line, the cold open, and the closing card, and the thumbnail at the two
feed sizes beside it.

**Done when** the Viglet Shio promo's build writes a sheet that shows each of those
without a hand-picked second.

### §UR13 Takes heard back (was marketing VM84)

`pronounce` in a script changes what is sent to the voice, but nothing listens to what
came back. On 2026-11-17 the Alexandre heard "agentes de Ía" at the start of the Viglet
Shio promo; "IA" went into the pt-BR pronounce map as "iá" and three takes were bought
again, and the only proof was the text sent (lines.json), not the sound. No
speech-to-text is installed on this machine.

After a take is bought, a transcription of it should be compared with the line: words
missing or added, and every word the pronounce map names, reported per take with its
second, so a take that says something else is refused before it is cut in. The
transcriber is a declared dependency of video-maker, not something each session
installs.

**Done when** the Viglet Shio promo's takes are transcribed on purchase and a take that
drops or garbles a mapped word is reported.

### §UR14 A flash refused before the owner sees it (was marketing VM86)

On 2026-11-17 the Alexandre saw the Viglet Shio promo flash at 0:40. One frame at 40.667
s averaged 234 in luma between frames of 26 to 43: the first frame of chapter-2.webm,
which Playwright films as the empty white page before the scene's first navigation
paints. Six of the sixteen scene clips start on that white frame; the others did not
show because the page after them is light too. The recording now cuts each clip at its
first paint, but nothing in the build would have refused the flash.

After that fix the Alexandre still saw 0:40 flash: one frame of the console's loading
dashboard, the same brightness as its neighbours (luma 39 against 43) but a different
picture (ffmpeg YDIF 7.6, then 7.9 back), which a brightness scan let through. The final
verification should compare each frame with its neighbours, by picture difference and
not only brightness, and refuse a change that lasts a frame or two and comes back (a
flash), naming the second and the clip it came from, so a blank frame from any source is
refused rather than published. polyweave's `measure.flashes` may already be the
measurement.

**Done when** the build refuses a cut with a one-frame white flash between dark frames,
and the Viglet Shio promo passes.

### §UR15 One recording driver (was marketing VM16)

`tests/e2e/story/shopper.story.mjs` and `developer/install.developer.mjs` in the Turing
repository copy the driver (`speak`, `tell`, `until`, `focus`, `release`, `skipping`,
`highlight`, `chapter`), the developer copy without `skip` or `tell`;
`video-maker/story-moves.mjs` copies the pointer and has drifted (`__storyCursor`, no
deadline pacing). Make `video-maker/recording/`: `moves.mjs` (pointer, reach, glide with
a deadline, scrollBy, layoutAt) and `storyClock`, which writes `chapters.json`
byte-compatible. The driver also records each clicked element's box as a `focus` mark,
in `cenas.json` for a scene: Viglet Shio's 9:16 shorts (VM12) crop its scenes at the
centre today and cut the console's left edge, and would follow the box instead.

The plugin's specs reach it through `tests/e2e/marketing.mjs`, whose contract is that
"only a recording needs it; the stories run as tests without it". Keep that contract:
the driver is loaded only when recording, and without the marketing repository the specs
fall back to plain steps with no pointer or pacing. This edits Turing's specs, so it
ships with a commit there too.

**Done when** the three recordings use the one driver, a re-recording produces the same
`chapters.json` shape, and Turing's stories pass as tests with
`VIGLET_MARKETING_WORDPRESS` pointing nowhere.
