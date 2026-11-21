# Source kinds

A video's `[source] kind` says what it is made of, and so which pipeline builds it.
Each kind needs the keys listed in [the declaration reference](specs/declaration.md#source-kinds).

## explainer

Narration over footage, the way the Japode videos are made. `[source] shots` names a
JSON file listing, for each take, the shots that play under it: a source id with its
start second, and optionally a fixed `dur`, a `speed` and a crop `box`. Shots without
`dur` share what is left of the line. Footage is read from `<footage>/src/<id>.mp4`
(`footage` defaults to `footage`), or from a film of your own named `<kind>:<scene>`,
read from `<footage>/<kind>/<scene>.webm`.

A `terminal:<scene>` film is made from the declaration. `[terminal.scenes.<scene>]
commands` lists what to type. `urdido terminal video.toml` runs each command for real
in a cleared folder and keeps what it printed (`[terminal] keep` trims a long output
to the lines worth reading). Then `node film-terminal.mjs terminal/session.json
footage/terminal`, from the `urdido-record` npm package, types each command and shows
its output in the terminal replay's window. Declare both as `[[record.step]]`s and
`urdido record` makes them in order. Nothing on screen is typed by hand, and a command
that fails refuses the session.

Keywords declared under `callouts` in the shots file appear when the take says them,
found in the take's word times; one with a `def` stays longer and shows its
definition. The title, the callouts and the closing card are drawn in the styles
`[source] styles` names, with the closing words from `[source.closing.<language>]`.
`[description]` with `[source] sources` writes the description with chapters and the
credits of the clips the cut shows. [The quickstart](quickstart.md) builds one.

## scenes

A product filmed scene by scene. `[source] listing` names the scene list a recording
leaves; each line plays over its own scene, held on its last frame when the scene is
short or played faster when it is long. `[[record.step]]` declares the commands that
record the scenes, and `urdido record` runs them in order, stopping at the first
failure without touching the last complete recording.

## illustrated

Editorial illustrations: `[source] declaration` names a storyboard of beats per take,
each a card layout or a clip of declared media with its licence. This kind runs the
most checks before it renders anything: see [the checks](checks.md).

## chaptered

One recording of a product, cut into chapters. `[source] folder`, `recording` and
`chapters` name the recording, its `chapters.json` and how many chapters it holds. The
build adds the cards, the opening, push-ins on what the recording marked, and the cuts
(the full video, a teaser, a chapter clip and its vertical cut).

## A kind of your own

A package adds a kind by registering a function `pipeline(build) -> int` under the
entry point group `urdido.sources`. `[source] kind` then names it, and the build hands
it the loaded declaration with its roots, folders and finishing stages.

## Variants

Any video can be built as a variant of another: `[video] base = "../published"` lays
the variant's tables over the base's and reads its files from a view of the base folder
with the variant's own files laid over, made of hard links so no footage is copied. A
JSON side file both hold is merged, so a variant storyboard can carry only the scene
lists it changes.
