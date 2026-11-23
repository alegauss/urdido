# Set aside

## Block A — Package foundation (urdido installable from PyPI)

- ⏸ **UR19** (deps: UR18 ✅, UR24 ✅) **A version cannot reach PyPI except by a hand-run upload with a token** — set aside (Waits on PyPI trusted publishers, a release.): Releasing 0.1.0 still needs the trusted publishers registered on PyPI and TestPyPI, and a wheel that carries urdido build and its package data. → §UR19

## Block B — The engine extracted (videomaker without marketing)

- ⏸ **UR30** (deps: UR21 ✅) **The Python build shells out to node for the opening gate, and the JavaScript helpers have no install path** — set aside (Needs npm publish.): urdido-record is published to the npm registry, so marketing's scripts and the e2e specs install it by name rather than from the checkout. → §UR30
- ⏸ **UR34** (deps: —) **Polyweave's open tasks PW712 to PW716 describe video composition that urdido now owns** — set aside (Needs PW712-716 narrowed in polyweave.): Two roadmaps planning the same preflight, preview, progress and claims will build them twice or wait on each other. → §UR34
- ⏸ **UR43** (deps: UR21 ✅) **The imported modules pass ruff only through a per-file baseline of ignored rules and unformatted files** — set aside (Paid as modules move): The E501 entries and the 87 format exclusions still need paying down module by module, ideally with the change that next touches each module. → §UR43

## Block C — Adoption in marketing (video-maker replaced by urdido)

- ⏸ **UR41** (deps: UR37 ✅, UR38 ✅, UR39 ✅) **Nothing proves that each published video comes out the same when built by urdido instead of video-maker** — set aside (Turing demo must be re-recorded.): The Turing WordPress demo's story and developer cuts, once recorded again on the demo stack. → §UR41

## Block D — Inherited from video-maker (marketing Block B)

- ⏸ **UR15** (deps: marketing VM3) **The recording driver and the pointer exist in three copies, and the copies already differ** — set aside (Needs the demo stacks up and a commit in Turing.): The story, the walkthrough and Viglet Shio's scenes each carry their own pointer. → §UR15
