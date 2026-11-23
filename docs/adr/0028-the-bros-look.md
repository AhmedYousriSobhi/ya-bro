# ADR-0028: The bro's look, and how the extension draws it

- Status: Accepted for the mechanism; the look is **provisional** (maintainer decides)
- Date: 2026-11-23
- Issue: #96
- Related: ADR-0006 (overlay), ADR-0013 (tone), ADR-0023 (extension), [docs/design/BRO_IDENTITY.md](../design/BRO_IDENTITY.md)

## Context
SPEC §2 said the bro's look was not decided, so the overlay drew a placeholder amber circle labelled "Ya" and the README showed none. An identity study produced five original candidates; the maintainer rejected two (Yaya, which reads as a worm, and Fenn, which reads as a rabbit) and has not chosen among Pip, Orbit and Brim.

## Decision
1. **Provisional look: Brim** (a round teal head with a dark cap whose visor points at the ring), the study's first choice, used in the README, the demo GIF and the extension until the maintainer decides. Changing it later means replacing six SVG files; nothing else depends on the shape.
2. **The extension draws it from six SVG files** in `extension/assets/bro/` (`idle`, `pointing`, `thinking`, `happy`, `teasing`, `quiet`), as a 48 px `St.Icon` left of the bubble (`AVATAR_GAP` 56). They are copies of `docs/assets/identity/states/` (a test keeps them identical), plain vector with no scripts, images or links (a test checks).
3. **`ShowStep` takes an optional `mood`** from that fixed list. Anything else falls back to `pointing` with a target and `idle` without, and the mood is never used as a path. `GetState` reports it. Core passes it through `Overlay.show_step(..., mood=)`; "" lets the overlay choose.
4. **Moods in the step loop:** `pointing` while a step waits, `thinking` when the target cannot be found, `teasing` after a wrong action (and its Why? explanation; never at `humour = 0`, which uses plain lines but the same face, see the note), `idle` for the "already done", "not yet" and "still here" lines, and `happy` for a short "all done" bubble when a plan ends (`Timing.done_hold`, 1.5 s in `broctl show`, 0 elsewhere). `quiet` is for the struggle detector's back-off and is not wired yet.
5. The light variant is used everywhere: its light halo keeps the silhouette on any background, and St does not apply the SVGs' dark-mode media block.

## Consequences
- The demo GIF shows the real overlay, bro included.
- At `humour = 0` the face still teases (an eyebrow and a flipped cap); the design note says the teasing frame should not be shown there. Not enforced yet.
- Moving the avatar (48 px, gap 56) changed the bubble's minimum left margin; the click-through and placement tests were updated.

## Not done
Gaze rotation toward the ring and mirroring for right-to-left, the cross-fade and the single hop (frames swap instantly), the favicon and about-dialog use, enforcing no teasing at humour 0, the `quiet` mood, and the maintainer's final choice of look.
