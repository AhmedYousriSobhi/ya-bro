# workbench (benchctl)

workbench is a pretend HPC cluster for one laptop: real Slurm in small containers, fake BMCs, GPUs, Jira and BCM, named faults, and a memory governor that refuses to start what will not fit. The command is `benchctl` (`./scripts/benchctl` inside the repo); it also serves a web page.

## Words
- **governor**: protects the machine's memory; it can say no.
- **REFUSED**: the governor said no. A decision, not a bug.
- **fault**: a named problem injected into a node (hot BMC, GPU XID, InfiniBand or NIC trouble).
- **scenario**: a scripted run of faults and checks (`benchctl scenario list`).
- **lab**: a config A/B replay through the governor (`benchctl run lab`).
- **profile**: a size preset (`benchctl get profiles`).

## The verbs
`start`, `stop`, `plan`, `describe workbench`, `get faults|endpoints|traffic|scenario-status`, `clear faults`, `scenario run NAME`, `wait ready`, `export profile|test-report|lab-report`, `run lab`. Read verbs take `--json`.

## Common mistakes
- Retrying after REFUSED in a loop. Run `benchctl plan`, free memory or pick a smaller profile.
- Polling instead of `benchctl wait ready`.
- Forgetting `benchctl stop` for what you started.
- Using sudo (never needed) or editing `compose/generated/`.
- Printing or copying a credential. The endpoints table names a file; point at the file, never its contents.

## For the bro
- Never set `BENCHCTL_AGENT=1` in the user's shell: it changes `--yes` and log behaviour.
- `stop`, `clear faults` and anything with `--yes` change or remove running state: the user presses Enter, not the bro.
- Error codes (`WB-...`) are explained in `fixits.toml`. Exit codes alone do not say which code it was; ask the user to show the line.
