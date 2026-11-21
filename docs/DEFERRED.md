# Set aside

## Block A — Package foundation (urdido installable from PyPI)

- ⏸ **UR19** (deps: UR18 ✅, UR24 ✅) **A version cannot reach PyPI except by a hand-run upload with a token** — set aside (Waits on PyPI trusted publishers, a release.): Releasing 0.1.0 still needs the trusted publishers registered on PyPI and TestPyPI, and a wheel that carries urdido build and its package data. → §UR19

## Block B — The engine extracted (videomaker without marketing)

- ⏸ **UR30** (deps: UR21 ✅) **The Python build shells out to node for the opening gate, and the JavaScript helpers have no install path** — set aside (Needs npm publish.): urdido-record is published to the npm registry, so marketing's scripts and the e2e specs install it by name rather than from the checkout. → §UR30
- ⏸ **UR34** (deps: —) **Polyweave's open tasks PW712 to PW716 describe video composition that urdido now owns** — set aside (Needs PW712-716 narrowed in polyweave.): Two roadmaps planning the same preflight, preview, progress and claims will build them twice or wait on each other. → §UR34

## Block C — Adoption in marketing (video-maker replaced by urdido)

- ⏸ **UR36** (deps: UR21 ✅) **Marketing installs the framework from its own folder with pip -e, with no version pinned** — set aside (Needs edits in marketing's repo.): Replacing the folder needs an install that does not point into it, and a pin says which urdido a video was built with. → §UR36
- ⏸ **UR40** (deps: UR20 ✅) **Marketing's video-maker gate hook, friction skill and CLAUDE.md rules point at a folder and a Block B that will be gone** — set aside (Needs marketing repo edits.): The rule that every friction becomes a framework task stops working the day the folder leaves, unless it points here. → §UR40

## Block D — Inherited from video-maker (marketing Block B)

- ⏸ **UR15** (deps: marketing VM3) **The recording driver and the pointer exist in three copies, and the copies already differ** — set aside (Needs the demo stacks up and a commit in Turing.): The story, the walkthrough and Viglet Shio's scenes each carry their own pointer. → §UR15
