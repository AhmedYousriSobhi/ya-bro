#!/usr/bin/env bash
# Run the Ya-Bro extension in an isolated headless gnome-shell and execute a command inside it.
# Never touches the live session: private session bus, config, data and runtime dirs.
# Usage: scripts/dev/headless-shell.sh <command> [args...]   (command runs with the shell up)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UUID="ya-bro@ahmedyousrisobhi.github.io"

export YB_ROOT="$ROOT" YB_UUID="$UUID"
exec dbus-run-session -- bash -c '
set -euo pipefail
T=$(mktemp -d); SHELL_PID=; trap "[ -n \"\$SHELL_PID\" ] && kill \$SHELL_PID 2>/dev/null; rm -rf $T" EXIT
mkdir -p $T/run && chmod 700 $T/run
export XDG_RUNTIME_DIR=$T/run
export XDG_DATA_HOME=$T/data XDG_CONFIG_HOME=$T/config XDG_CACHE_HOME=$T/cache
export GSETTINGS_BACKEND=keyfile
mkdir -p $XDG_DATA_HOME/gnome-shell/extensions $XDG_CONFIG_HOME $XDG_CACHE_HOME
glib-compile-schemas "$YB_ROOT/extension/schemas"
ln -s "$YB_ROOT/extension" "$XDG_DATA_HOME/gnome-shell/extensions/$YB_UUID"
gsettings set org.gnome.shell disable-user-extensions false 2>/dev/null || true
gsettings set org.gnome.shell enabled-extensions "[\"$YB_UUID\"]" 2>/dev/null || true
export GSETTINGS_SCHEMA_DIR=
gnome-shell --headless --wayland --wayland-display=yabro-test --no-x11 --virtual-monitor 1280x800 >$T/shell.log 2>&1 &
SHELL_PID=$!
for i in $(seq 1 60); do
  gdbus call -e -d org.gnome.Shell -o /org/gnome/Shell -m org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1 && break
  sleep 0.5
done
export YB_SHELL_LOG=$T/shell.log WAYLAND_DISPLAY=yabro-test GDK_BACKEND=wayland
"$@" || { rc=$?; echo "--- shell log tail ---"; tail -40 $T/shell.log; exit $rc; }
' _ "$@"
