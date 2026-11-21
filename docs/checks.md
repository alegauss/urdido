# What urdido checks

urdido refuses what it can catch before it spends time or money, and measures what it
made before it says it is done. Each check below names what refuses and what fixes it.

## Before anything is built

- **The declaration.** `urdido check` and every build refuse a key no table takes, with
  the nearest valid name, a missing required key, and a source without what its kind
  needs. It follows the declaration into its narration script and storyboard and
  refuses a misspelled key there too, with the file and the nearest name. See
  [the declaration reference](specs/declaration.md).
- **The opening.** Before any take is bought, an intro that opens on a preamble ("today
  we will…") or a first proof later than 20 seconds at the narrator's declared pace is
  refused.
- **The takes heard back.** Each bought take's transcript is aligned with its line. A
  word the script's `pronounce` map names that is missing or misheard refuses the take,
  with the second it should have been said; other differences are listed for review.
- **Text.** `[text_checks]` refuses corrupted encoding, a glyph the declared font lacks,
  and text that overflows its box or splits a protected token.
- **Claims.** `[claims]` binds each spoken claim to its evidence and review.
- **Pauses and repetition.** An illustrated cut refuses a still held too long and
  footage reused past its limit.
- **Rejected media.** A beat that uses media a review rejected is refused, citing the
  review.
- **A recorded session.** A terminal chapter's selectors can be `required` or carry a
  `count`; a session that misses one is refused, naming the chapter and the selector.

## While and after it builds

- **Safe areas.** `[captions.safe_area]` holds captions out of the band a player covers;
  Shorts are held to the platform's controls where the provider runs.
- **Loudness and peaks.** The mix is held to `[audio]`'s target and true-peak ceiling,
  read off the finished file.
- **Flashes.** The final verification looks for a picture change that lasts one or two
  frames and comes back. A strong one (a white page between dark frames) is refused,
  naming its second and the clip; a faint one (a clip's own light leak) is reported for
  you to look at. `[qa] flash_refuse` and `flash_threshold` move the two levels.
- **Shorts.** A Short over a minute, a title over 60 characters, or the wrong number of
  hashtags is refused; one outside 20 to 55 seconds is advised.

## What goes out with the video

- **The thumbnail and its title.** Checked as a pair: a title over 60 characters, with
  no number, name or date, more than two words in capitals or an empty superlative, or
  a thumbnail that repeats a word of the title, is refused.
- **The thumbnail's pictures.** Each is media the storyboard declares, or is declared
  thumbnail-only with its reason, licence, author and URL.
- **The description.** Kept within the platform's limit without dropping a required
  credit.
