# ADR-0029: Terminal companion (snippet, Copy, Write it)

- Status: Accepted for bash on GNOME; verified in a real VTE terminal (isolated session), not on the maintainer's live desktop
- Date: 2026-11-23
- Issue: #115
- Depends on: ADR-0009, ADR-0014, ADR-0021, ADR-0023, ADR-0025

## Context
`broctl ask --pack workbench` (#114) showed plain prose in a window. A terminal tool needs the bro beside the terminal, showing the command to type, with a way to copy it and a way to have it typed for you.

## Decision
1. **Plans carry commands.** A step has an optional `command` (one printable line, at most 200 characters, validated in `plans.py`). Narration no longer holds the command. `ClaudeBrain` still strips commands from model text; model-proposed commands are out of scope.
2. **The bubble shows the snippet** in monospace, always left to right, with buttons Copy, Write it, Next, Why?, Stop. The extension draws it (`snippet` in `ShowStep`, two new button names) and does Copy itself with `St.Clipboard` and the text already on screen: no new D-Bus method, nothing is read from the clipboard.
3. **Write it uses no key injection.** Core writes a private suggestion file, then writes the terminal status query `ESC [ 5 n` to the terminal's tty. The terminal answers `ESC [ 0 n` on the shell's input; the hook binds that sequence (`bind -x`) and puts the file's line at the prompt **only when the line is empty**. Enter is never pressed: the user's own Enter is the R2 confirmation (ADR-0009). Rejected: TIOCSTI (disabled in current kernels), portal + libei (consent dialog, unverified S7), injection from the extension (ADR-0023 §11).
4. **Guards, all checked before anything touches the tty:** the command is valid and not R3 by `command_risk` (an R3 command gets Copy only); the hook has marked exactly one terminal idle (prompt showing, shell alive, `/proc/PID/fd/0` is that tty); the tty is a character device under `/dev/pts` owned by the user; more than one idle terminal means Copy only. A silent terminal or a late answer leaves nothing behind (the suggestion file is removed). Under pytest the real tty opener refuses.
5. **Idle marker.** While core runs (`$XDG_RUNTIME_DIR/ya-bro` exists) the hook writes `idle PID` or `busy PID` to `prompt.<tty>` at each prompt and command start. Still nothing is written when Bro is not running.
6. **The step moves on by itself** when the hook records that command's name finishing: exit 0 advances, another exit code says so and waits for a re-run. The plan's commands are the only names the hook records during the run.
7. **Hovering.** With an allowed terminal window, the bubble is placed in the terminal's top-right corner; without one it is a plain window. `broctl ask --pack` runs in the background so the terminal's prompt comes back (Write it and the command both need an idle prompt); `--wait` keeps it in the foreground.

## Open question for the maintainer
Hovering needs the terminal app allowed (`broctl apps allow <terminal id>`), which lets the extension report that app's windows (position, not content). ADR-0025 prefers a target scoped to one tab or tool. A terminal has no tab origin; the consistent option is for the hook to put a scope token in the terminal title (OSC 2) and scope by title, as for web pages. Not built: it needs the title to follow OSC 2 in Ptyxis, unverified.

## Consequences
- Works with any terminal that answers the status query (VTE does; others unverified) and bash with the hook installed. zsh, fish, and a raw `read`/vim prompt are not covered; the idle marker keeps the query away from running programs.
- Extension changes (new buttons, snippet) need `broctl load` or a new login on a live desktop.
