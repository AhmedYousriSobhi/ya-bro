# Ya-Bro shell hook for bash (ADR-0021). Content-free: for a command you allowed (broctl targets
# allow --command NAME) it records only the command's name, exit code, duration and tty, one JSON
# line, when the command finishes. No arguments, no output, no stderr. It does nothing at all when
# Ya-Bro is not running (no spool file), in non-interactive shells, or for any other command.
# Add to ~/.bashrc with `broctl hook install`; remove with `broctl hook uninstall`.

[[ $- == *i* ]] || return 0
[[ -z ${_YB_HOOK:-} ]] || return 0
_YB_HOOK=1

_yb_tty=$(tty 2>/dev/null) || _yb_tty=
_yb_tty=${_yb_tty#/dev/}
_yb_dir=${XDG_RUNTIME_DIR:-/nonexistent}/ya-bro
_yb_mark=$_yb_dir/prompt.${_yb_tty//\//_}   # "idle|busy PID" for this terminal (ADR-0029)
_yb_armed=
_yb_ran=
_yb_a0=
_yb_t0=

# true when $1 is a line of $XDG_RUNTIME_DIR/ya-bro/commands (core writes it from the allowed targets)
_yb_allowed() {
  local line
  [[ -r ${XDG_RUNTIME_DIR:-/nonexistent}/ya-bro/commands ]] || return 1
  while IFS= read -r line; do
    [[ $line == "$1" ]] && return 0
  done <"$XDG_RUNTIME_DIR/ya-bro/commands"
  return 1
}

# DEBUG trap: runs before every simple command; only the first one after a prompt counts.
_yb_debug() {
  [[ -n $_yb_armed ]] || return 0
  [[ $BASH_COMMAND == _yb_* ]] && return 0
  _yb_armed=
  [[ -d $_yb_dir ]] && printf 'busy %s\n' "$$" >"$_yb_mark" 2>/dev/null
  _yb_ran=1
  _yb_t0=${EPOCHREALTIME/./}
  _yb_a0=${BASH_COMMAND%% *}
  _yb_a0=${_yb_a0##*/}
}

# First in PROMPT_COMMAND: $? here is the command's exit code.
_yb_post() {
  local rc=$? spool=${XDG_RUNTIME_DIR:-/nonexistent}/ya-bro/shell.spool now
  if [[ -n $_yb_ran ]]; then
    _yb_ran=
    if [[ -w $spool ]] && _yb_allowed "$_yb_a0"; then
      now=${EPOCHREALTIME/./}
      printf '{"v":1,"ts":%d,"argv0":"%s","exit":%d,"ms":%d,"tty":"%s"}\n' \
        "$((now / 1000))" "$_yb_a0" "$rc" "$(((now - _yb_t0) / 1000))" "$_yb_tty" >>"$spool"
    fi
  fi
  return "$rc"
}

# While a run holds a scope token (ADR-0029 §8) it goes into the terminal title (OSC 2), so the
# extension reports this terminal's window only while Bro runs, without allowing the whole app.
# Distro prompts (Ubuntu's PS1) set the title themselves AFTER PROMPT_COMMAND, so the sequence is
# also appended to the END of PS1 (below), where nothing can overwrite it.
_yb_title() {
  local t
  [[ -r $_yb_dir/scope-token ]] || return 0
  IFS= read -r t <"$_yb_dir/scope-token"
  [[ $t =~ ^yb-[0-9a-f]{32}$ ]] && printf '\033]2;ya-bro %s\007' "$t"
  return 0
}

[[ $PS1 == *'_yb_title)'* ]] || PS1+='\[$(_yb_title)\]'

# Last in PROMPT_COMMAND: from here on the next simple command is the user's.
_yb_arm() {
  _yb_armed=1
  _yb_title
  [[ -d $_yb_dir ]] && printf 'idle %s\n' "$$" >"$_yb_mark" 2>/dev/null
  return 0
}

# "Write it" (ADR-0029): core asks the terminal for a status report (ESC [ 5 n); the terminal answers
# ESC [ 0 n on our input, which lands here. The suggestion is put at the prompt only when the line is
# empty, and Enter is never pressed. The outcome goes to a result file core reads.
_yb_insert() {
  local f=$_yb_dir/suggest.${_yb_tty//\//_} s= r=nothing
  _yb_title
  [[ -r $f ]] && IFS= read -r s <"$f"
  if [[ -n $s ]]; then
    if [[ -z $READLINE_LINE ]]; then
      READLINE_LINE=$s
      READLINE_POINT=${#s}
      r=ok
    else
      r=line-not-empty
    fi
    : >"$f"
  fi
  printf '%s\n' "$r" >"$f.result" 2>/dev/null
}
bind -x '"\e[0n": _yb_insert' 2>/dev/null

# An existing DEBUG trap must keep working, but `trap -p DEBUG` shows nothing inside a sourced file
# or a function, so the first prompt reads it from the top level (this string is eval'd there).
_yb_init='_yb_f=$(mktemp 2>/dev/null) && trap -p DEBUG >"$_yb_f" && _yb_old_debug=$(<"$_yb_f")
rm -f "$_yb_f"; _yb_f=; _yb_install; _yb_inited=1'

_yb_install() {
  if [[ -n $_yb_old_debug ]]; then
    _yb_old_debug=${_yb_old_debug#"trap -- '"}
    _yb_old_debug=${_yb_old_debug%"' DEBUG"}
    eval "_yb_chain() { _yb_debug; $_yb_old_debug; }"
    trap '_yb_chain' DEBUG
  else
    trap '_yb_debug' DEBUG
  fi
}

_yb_inited=
if [[ $(declare -p PROMPT_COMMAND 2>/dev/null) == "declare -a"* ]]; then
  PROMPT_COMMAND=(_yb_post '[[ -n $_yb_inited ]] || eval "$_yb_init"' "${PROMPT_COMMAND[@]}" _yb_arm)
else
  PROMPT_COMMAND="_yb_post;[[ -n \$_yb_inited ]] || eval \"\$_yb_init\"${PROMPT_COMMAND:+;$PROMPT_COMMAND};_yb_arm"
fi
