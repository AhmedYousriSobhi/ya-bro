// Bridge1: window geometry, focus, monitors, pointer. Read-only, content-free (no titles in lists).
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {OBJECT_PATH, deny} from './peers.js';

export const API = 1;
const IFACE = 'io.github.ahmedyousrisobhi.YaBro.Shell.Bridge1';
const READERS = ['Core', 'Perceiver'];
const SIGNAL_PEERS = ['Core', 'Perceiver'];

const XML = `<node><interface name="${IFACE}">
  <method name="GetInfo"><arg type="a{sv}" direction="out"/></method>
  <method name="ListWindows"><arg type="aa{sv}" direction="out"/></method>
  <method name="GetWindowTitle"><arg type="t" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="out"/></method>
  <method name="GetMonitors"><arg type="a(iiiiidb)" direction="out"/></method>
  <method name="GetPointer"><arg type="(ii)" direction="out"/></method>
  <signal name="WindowsChanged"><arg type="at"/><arg type="at"/></signal>
  <signal name="GeometryChanged"><arg type="t"/><arg type="(iiii)"/><arg type="(iiii)"/></signal>
  <signal name="FocusChanged"><arg type="t"/></signal>
  <signal name="MonitorsChanged"/>
  <signal name="OverviewChanged"><arg type="b"/></signal>
</interface></node>`;

const rect = r => [r.x, r.y, r.width, r.height];
const V = (sig, val) => new GLib.Variant(sig, val);

export class Bridge {
    constructor(connection, peers, overlay, shellVersion, extVersion) {
        this._peers = peers;
        this._overlay = overlay;
        this._shellVersion = shellVersion;
        this._extVersion = extVersion;
        this._pointerTimes = [];
        this._signals = [];
        this._pendingGeometry = new Map();
        this._idle = 0;
        this._perWindow = new Map();

        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(connection, OBJECT_PATH);

        const display = global.display;
        this._connect(display, 'notify::focus-window', () => this._onFocus());
        this._connect(display, 'window-created', (_d, w) => this._track(w, true));
        this._connect(Main.layoutManager, 'monitors-changed',
            () => this._peers.emit(IFACE, 'MonitorsChanged', null, SIGNAL_PEERS));
        this._connect(Main.overview, 'showing', () => this._emitOverview(true));
        this._connect(Main.overview, 'hiding', () => this._emitOverview(false));
        for (const actor of global.get_window_actors())
            this._track(actor.meta_window, false);
    }

    destroy() {
        if (this._idle)
            GLib.source_remove(this._idle);
        this._idle = 0;
        for (const [obj, id] of this._signals.splice(0))
            obj.disconnect(id);
        for (const [win, ids] of this._perWindow)
            ids.forEach(id => win.disconnect(id));
        this._perWindow.clear();
        this._dbus.unexport();
        this._dbus = null;
    }

    _connect(obj, name, fn) {
        this._signals.push([obj, obj.connect(name, (...a) => {
            try {
                fn(...a);
            } catch (e) {
                console.error(`ya-bro: ${name} handler: ${e.message}`);
            }
        })]);
    }

    _emitOverview(shown) {
        this._peers.emit(IFACE, 'OverviewChanged', V('(b)', [shown]), SIGNAL_PEERS);
    }

    _onFocus() {
        const w = global.display.focus_window;
        this._peers.emit(IFACE, 'FocusChanged', V('(t)', [w ? w.get_id() : 0]), SIGNAL_PEERS);
    }

    _track(win, announce) {
        if (!win || this._perWindow.has(win))
            return;
        const ids = [];
        const geo = () => this._queueGeometry(win);
        ids.push(win.connect('position-changed', geo));
        ids.push(win.connect('size-changed', geo));
        ids.push(win.connect('unmanaged', () => {
            this._perWindow.delete(win);
            this._peers.emit(IFACE, 'WindowsChanged', V('(atat)', [[], [win.get_id()]]), SIGNAL_PEERS);
        }));
        this._perWindow.set(win, ids);
        if (announce)
            this._peers.emit(IFACE, 'WindowsChanged', V('(atat)', [[win.get_id()], []]), SIGNAL_PEERS);
    }

    // Coalesce to at most one GeometryChanged per window per main-loop iteration.
    _queueGeometry(win) {
        this._pendingGeometry.set(win, true);
        if (this._idle)
            return;
        this._idle = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this._idle = 0;
            for (const w of this._pendingGeometry.keys()) {
                try {
                    this._peers.emit(IFACE, 'GeometryChanged',
                        V('(t(iiii)(iiii))', [w.get_id(), rect(w.get_frame_rect()), rect(w.get_buffer_rect())]),
                        SIGNAL_PEERS);
                } catch (e) {
                    console.error(`ya-bro: geometry emit: ${e.message}`);
                }
            }
            this._pendingGeometry.clear();
            return GLib.SOURCE_REMOVE;
        });
    }

    _windowDict(win, stack) {
        const appId = win.get_gtk_application_id() ?? win.get_sandboxed_app_id() ?? win.get_wm_class() ?? '';
        return {
            id: V('t', win.get_id()),
            seq: V('u', win.get_stable_sequence()),
            pid: V('i', win.get_pid()),
            app_id: V('s', appId),
            type: V('u', win.get_window_type()),
            client: V('s', win.get_client_type() === Meta.WindowClientType.WAYLAND ? 'wayland' : 'x11'),
            frame: V('(iiii)', rect(win.get_frame_rect())),
            buffer: V('(iiii)', rect(win.get_buffer_rect())),
            monitor: V('i', win.get_monitor()),
            fullscreen: V('b', win.is_fullscreen()),
            focused: V('b', win.has_focus()),
            transient_for: V('t', win.get_transient_for()?.get_id() ?? 0),
            stack: V('u', stack),
        };
    }

    _guard(invocation, fn) {
        if (!this._peers.allowed(invocation.get_sender(), READERS))
            return deny(invocation);
        try {
            invocation.return_value(fn());
        } catch (e) {
            console.error(`ya-bro: Bridge1 call failed: ${e.message}`);
            invocation.return_dbus_error('org.freedesktop.DBus.Error.Failed', 'internal error');
        }
    }

    GetInfoAsync(_p, invocation) {
        this._guard(invocation, () => V('(a{sv})', [{
            api: V('u', API),
            shell_version: V('s', this._shellVersion),
            extension_version: V('s', this._extVersion),
            layout_mode: V('s', Meta.is_stage_views_scaled?.() ? 'logical' : 'physical'),
            capabilities: V('as', ['windows', 'geometry', 'focus', 'monitors', 'pointer']),
        }]));
    }

    ListWindowsAsync(_p, invocation) {
        this._guard(invocation, () => {
            const ordered = global.display.sort_windows_by_stacking(
                global.get_window_actors().map(a => a.meta_window));
            return V('(aa{sv})', [ordered.map((w, i) => this._windowDict(w, i))]);
        });
    }

    GetWindowTitleAsync([id, serial], invocation) {
        this._guard(invocation, () => {
            const win = global.get_window_actors().map(a => a.meta_window).find(w => w.get_id() === id);
            const ok = win && (win.has_focus() || this._overlay.stepMatches(id, serial));
            return V('(s)', [ok ? win.get_title() ?? '' : '']);
        });
    }

    GetMonitorsAsync(_p, invocation) {
        this._guard(invocation, () => {
            const mons = Main.layoutManager.monitors.map(m => [
                m.index, m.x, m.y, m.width, m.height, m.geometry_scale ?? 1, m.index === Main.layoutManager.primaryIndex]);
            return V('(a(iiiiidb))', [mons]);
        });
    }

    GetPointerAsync(_p, invocation) {
        this._guard(invocation, () => {
            const now = GLib.get_monotonic_time();
            this._pointerTimes = this._pointerTimes.filter(t => now - t < 1e6);
            if (this._pointerTimes.length >= 30)
                throw new Error('rate limited');
            this._pointerTimes.push(now);
            const [x, y] = global.get_pointer();
            return V('((ii))', [[x, y]]);
        });
    }
}
