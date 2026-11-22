# S9: AT-SPI window extents can be a constant off (GNOME Calculator)

Found in the first live trial of `broctl show` (#66): the ring sat about 12 px right and down of the Calculator key.

**Measured (isolated headless shell, GNOME 50.1, GTK 4.22.4, real `gnome-calculator`, scale 1.0).** The visible key face (found by pixel flood-fill from a point inside the key) has the same size as the AT-SPI rectangle but starts exactly 12 px up and 12 px left of `frame origin + WINDOW extents`, for every keypad key (12 of 12). The window's own node reports `(0, 0, 360, 616)`, equal to the frame, so nothing in the node says why. The Mutter buffer origin is 25 px up-left of the frame, so the buffer origin does not explain it either (S1: the plain GTK4 fixture matches the frame exactly).

**Not known:** whether this is a libadwaita window quirk or Calculator's own layout. Text Editor and Files exposed no buttons to the probe, so they were not measured.

**What we did:** a per-plan `extents_offset = [dx, dy]` (plan data, no app code in core), set to `[-12, -12]` in `examples/plans/calculator.toml`. It fixes that one app only.

**Open (needs a decision):** a general way to catch a wrong rectangle: pixel check of the target (needs screen capture consent), click calibration, or per-app data in packs (#8). ADR-0007 says a wrong ring is worse than none, so an unverified rectangle should eventually lower the ring's confidence.
