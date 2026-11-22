#!/usr/bin/env bash
# Run the Ya-Bro extension in an isolated headless gnome-shell and execute a command inside it.
# Never touches the live session: private session bus, config, data and runtime dirs.
# Usage: scripts/dev/headless-shell.sh <command> [args...]   (command runs with the shell up)
# Env: YB_X11=1 enables XWayland; YB_SCALE=<f> enables fractional scaling support; YB_MONITOR=WxH sets the
# virtual monitor size (default 1280x800); YB_DEVKIT=1 runs a nested shell in a mutter-devkit window on the real
# desktop instead of a headless one (needs mutter-dev-bin); YB_GDK sets GDK_BACKEND for the command (default wayland).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
UUID="ya-bro@ahmedyousrisobhi.github.io"

export YB_ROOT="$ROOT" YB_UUID="$UUID"
exec dbus-run-session -- bash -c '
set -euo pipefail
HOST_WL=${WAYLAND_DISPLAY:-}; HOST_RT=${XDG_RUNTIME_DIR:-}
unset DISPLAY WAYLAND_DISPLAY XAUTHORITY
T=$(mktemp -d); SHELL_PID=; PW_PID=; WP_PID=; YB_XDISP=
trap "kill \$SHELL_PID \$WP_PID \$PW_PID 2>/dev/null; sleep 0.5; [ -n \"\${YB_XDISP:-}\" ] && rm -f /tmp/.X11-unix/X\${YB_XDISP#:} /tmp/.X\${YB_XDISP#:}-lock; rm -rf $T" EXIT
mkdir -p $T/run && chmod 700 $T/run
export XDG_RUNTIME_DIR=$T/run
export XDG_DATA_HOME=$T/data XDG_CONFIG_HOME=$T/config XDG_CACHE_HOME=$T/cache
export GSETTINGS_BACKEND=keyfile
mkdir -p $XDG_DATA_HOME/gnome-shell/extensions $XDG_CONFIG_HOME $XDG_CACHE_HOME
glib-compile-schemas "$YB_ROOT/extension/schemas"
ln -s "$YB_ROOT/extension" "$XDG_DATA_HOME/gnome-shell/extensions/$YB_UUID"
gsettings set org.gnome.shell disable-user-extensions false 2>/dev/null || true
gsettings set org.gnome.desktop.interface toolkit-accessibility true 2>/dev/null || true
if [ "${YB_SCALE:-1}" != "1" ]; then gsettings set org.gnome.mutter experimental-features "[\"scale-monitor-framebuffer\"]" 2>/dev/null || true; fi
pipewire >$T/pipewire.log 2>&1 &
PW_PID=$!
# ScreenCast frame grabs need a session manager to link the stream, so run WirePlumber, but never let it
# reach the camera (an unmasked run once lit the webcam LED): video-capture/audio/bluetooth features are
# off, AND every /dev/video* and /dev/media* node is replaced by /dev/null inside a bwrap mount namespace.
command -v bwrap >/dev/null || { echo "bwrap is required to run WirePlumber safely" >&2; exit 1; }
mkdir -p $XDG_CONFIG_HOME/wireplumber/wireplumber.conf.d
cat > $XDG_CONFIG_HOME/wireplumber/wireplumber.conf.d/90-ya-bro.conf <<WPEOF
wireplumber.profiles = {
  main = {
    hardware.audio = disabled
    hardware.bluetooth = disabled
    hardware.video-capture = disabled
  }
}
WPEOF
MASK=()
for d in /dev/video* /dev/media*; do [ -e "$d" ] && MASK+=(--ro-bind /dev/null "$d"); done
if [ "${YB_NO_WP:-0}" != 1 ]; then
bwrap --die-with-parent --dev-bind / / "${MASK[@]}" wireplumber >$T/wireplumber.log 2>&1 &
WP_PID=$!
fi
sleep 1
if [ -n "$WP_PID" ] && ls -l /proc/$WP_PID/fd /proc/$(pgrep -P $WP_PID | head -1)/fd 2>/dev/null | grep -qE "/dev/(video|media)"; then
  echo "WirePlumber holds a video/media device; aborting" >&2; exit 1
fi
sleep 1
gsettings set org.gnome.shell enabled-extensions "[\"$YB_UUID\"]" 2>/dev/null || true
export GSETTINGS_SCHEMA_DIR=
if [ "${YB_DEVKIT:-0}" = 1 ]; then
  # Nested shell shown in a mutter-devkit window on the real desktop. Only this process sees the host
  # socket (absolute path); everything else stays on the private display.
  [ -n "$HOST_WL" ] && [ -S "$HOST_RT/$HOST_WL" ] || { echo "devkit mode needs a running Wayland session" >&2; exit 1; }
  WAYLAND_DISPLAY="$HOST_RT/$HOST_WL" gnome-shell --devkit --wayland --wayland-display=yabro-test $([ "${YB_X11:-0}" = 1 ] || echo --no-x11) >$T/shell.log 2>&1 &
else
  gnome-shell --headless --wayland --wayland-display=yabro-test $([ "${YB_X11:-0}" = 1 ] || echo --no-x11) --virtual-monitor ${YB_MONITOR:-1280x800} >$T/shell.log 2>&1 &
fi
SHELL_PID=$!
for i in $(seq 1 60); do
  gdbus call -e -d org.gnome.Shell -o /org/gnome/Shell -m org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1 && break
  sleep 0.5
done
if [ "${YB_X11:-0}" = 1 ]; then
  # Our private Xwayland is a child of our own gnome-shell; never guess from /tmp/.X11-unix.
  for i in $(seq 1 20); do
    XLINE=$(pgrep -P $SHELL_PID -a Xwayland || true)
    [ -n "$XLINE" ] && break; sleep 0.5
  done
  YB_XDISP=$(echo "$XLINE" | grep -oE " :[0-9]+" | head -1 | tr -d " ")
  YB_XAUTH=$(echo "$XLINE" | grep -oE "\-auth [^ ]+" | cut -d" " -f2)
  [ -n "${YB_DEBUG:-}" ] && echo "xdbg display=$YB_XDISP auth=$YB_XAUTH" >&2
  export YB_XDISPLAY=$YB_XDISP YB_XAUTH
fi
export YB_SHELL_LOG=$T/shell.log WAYLAND_DISPLAY=yabro-test GDK_BACKEND=${YB_GDK:-wayland}
"$@" || { rc=$?; echo "--- shell log tail ---"; tail -40 $T/shell.log; exit $rc; }
' _ "$@"
