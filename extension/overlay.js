// Overlay1: dumb renderer. Ring, pointer, bubble, avatar as St actors in addTopChrome containers.
// Only the avatar and bubble buttons are reactive; nothing takes key focus (ADR-0023 §5).
import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {OBJECT_PATH, deny} from './peers.js';

const IFACE = 'io.github.ahmedyousrisobhi.YaBro.Shell.Overlay1';
const CORE_ONLY = ['Core'];
const EVENT_PEERS = ['Core', 'Actuator'];
const DEAD_MAN_SECONDS = 6;
const MAX_TEXT = 280;
// Labels come from the extension, never from the caller (anti-spoofing, ADR-0023 §11.6).
const BUTTONS = {
    next: 'Next', repeat: 'Repeat', why: 'Why?', do_it: 'Do it', stop: 'Stop',
    yes: 'Yes', no: 'No', not_for_app: 'Not for this app',
};

const XML = `<node><interface name="${IFACE}">
  <method name="ShowStep"><arg type="a{sv}" direction="in"/><arg type="u" direction="out"/></method>
  <method name="FlyPointer"><arg type="(ii)" direction="in"/><arg type="u" direction="in"/><arg type="u" direction="out"/></method>
  <method name="SetAvatar"><arg type="a{sv}" direction="in"/></method>
  <method name="SetIndicators"><arg type="as" direction="in"/></method>
  <method name="Hide"/>
  <property name="Visible" type="b" access="read"/>
  <method name="Ping"><arg type="u" direction="in"/><arg type="u" direction="out"/></method>
  <signal name="UserEvent"><arg type="s"/><arg type="s"/><arg type="u"/></signal>
</interface></node>`;

export class Overlay {
    constructor(connection, peers) {
        this._peers = peers;
        this._serial = 0;
        this._follow = {window: 0, serial: 0};
        this._containers = [];
        this._lastPing = GLib.get_monotonic_time();
        this._draws = [];
        this._visible = false;
        this._signals = [];

        this._dbus = Gio.DBusExportedObject.wrapJSObject(XML, this);
        this._dbus.export(connection, OBJECT_PATH);

        this._buildContainers();
        this._signals.push([Main.layoutManager, Main.layoutManager.connect('monitors-changed', () => {
            this.hide();
            this._buildContainers();
        })]);
        this._signals.push([Main.overview, Main.overview.connect('showing', () => this._setHidden(true))]);
        this._signals.push([Main.overview, Main.overview.connect('hiding', () => this._setHidden(false))]);

        this._deadMan = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            const silent = (GLib.get_monotonic_time() - this._lastPing) / 1e6 > DEAD_MAN_SECONDS;
            if (this._visible && (silent || !this._peers.hasCore()))
                this.hide();
            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        if (this._deadMan)
            GLib.source_remove(this._deadMan);
        this._deadMan = 0;
        for (const [obj, id] of this._signals.splice(0))
            obj.disconnect(id);
        this._destroyContainers();
        this._dbus.unexport();
        this._dbus = null;
    }

    get Visible() {
        return this._visible;
    }

    stepMatches(windowId, serial) {
        return this._visible && this._follow.window === windowId && this._follow.serial === serial;
    }

    // Local hide, also used by the stop key. Idempotent.
    hide() {
        this._visible = false;
        for (const c of this._containers) {
            c.ring.hide();
            c.bubble.hide();
            c.pointer.hide();
            c.avatar.hide();
        }
        this._follow = {window: 0, serial: 0};
    }

    _setHidden(hidden) {
        for (const c of this._containers)
            c.root.visible = !hidden;
    }

    _buildContainers() {
        this._destroyContainers();
        for (const m of Main.layoutManager.monitors) {
            const root = new St.Widget({reactive: false, x: m.x, y: m.y, width: m.width, height: m.height});
            const ring = new St.Widget({style_class: 'yabro-ring', reactive: false, visible: false});
            const pointer = new St.Widget({style_class: 'yabro-pointer', reactive: false, visible: false});
            const label = new St.Label({style_class: 'yabro-bubble-label', reactive: false});
            label.clutter_text.line_wrap = true;
            const buttons = new St.BoxLayout({reactive: false});
            const bubble = new St.BoxLayout({style_class: 'yabro-bubble', vertical: true, reactive: false, visible: false});
            bubble.add_child(label);
            bubble.add_child(buttons);
            const avatar = new St.Button({
                style_class: 'yabro-avatar', label: 'Ya', reactive: true, can_focus: false,
                track_hover: false, visible: false,
            });
            avatar.connect('clicked', () => this._event('avatar_click', ''));
            for (const a of [ring, pointer, bubble, avatar])
                root.add_child(a);
            Main.layoutManager.addTopChrome(root, {affectsStruts: false, trackFullscreen: false});
            this._containers.push({monitor: m, root, ring, pointer, label, buttons, bubble, avatar});
        }
    }

    _destroyContainers() {
        for (const c of this._containers) {
            Main.layoutManager.removeChrome(c.root);
            c.root.destroy();
        }
        this._containers = [];
    }

    _event(kind, id) {
        this._peers.emit(IFACE, 'UserEvent', new GLib.Variant('(ssu)', [kind, id, this._serial]), EVENT_PEERS);
    }

    emitStopKey() {
        this._event('stop_key', '');
    }

    _allowDraw() {
        const now = GLib.get_monotonic_time();
        this._draws = this._draws.filter(t => now - t < 1e6);
        if (this._draws.length >= 60)
            return false;
        this._draws.push(now);
        return true;
    }

    _guard(invocation, fn) {
        if (!this._peers.allowed(invocation.get_sender(), CORE_ONLY))
            return deny(invocation);
        if (!this._allowDraw()) {
            invocation.return_dbus_error('org.freedesktop.DBus.Error.LimitsExceeded', 'rate limited');
            return;
        }
        try {
            invocation.return_value(fn());
        } catch (e) {
            console.error(`ya-bro: Overlay1 call failed: ${e.message}`);
            invocation.return_dbus_error('org.freedesktop.DBus.Error.Failed', 'internal error');
        }
    }

    _containerFor(x, y) {
        return this._containers.find(c => x >= c.monitor.x && x < c.monitor.x + c.monitor.width &&
            y >= c.monitor.y && y < c.monitor.y + c.monitor.height) ?? this._containers[0];
    }

    ShowStepAsync([rawArgs], invocation) {
        this._guard(invocation, () => {
            // a{sv} values arrive as GLib.Variant; unpack them once, here.
            const args = Object.fromEntries(Object.entries(rawArgs).map(([k, v]) => [k, v.recursiveUnpack()]));
            this._lastPing = GLib.get_monotonic_time();
            this.hide();
            const serial = ++this._serial;
            const target = args.target;            // [x, y, w, h] stage coordinates or undefined
            const text = String(args.text ?? '').slice(0, MAX_TEXT);
            const ringStyle = args.ring ?? 'none';
            const anchor = target ? [target[0] + target[2] / 2, target[1] + target[3] / 2] : [0, 0];
            const c = this._containerFor(...anchor);
            if (!c)
                return new GLib.Variant('(u)', [serial]);

            if (target && ringStyle !== 'none') {
                c.ring.style_class = ringStyle === 'dashed' ? 'yabro-ring yabro-ring-dashed' : 'yabro-ring';
                c.ring.set_position(target[0] - c.monitor.x, target[1] - c.monitor.y);
                c.ring.set_size(target[2], target[3]);
                c.ring.show();
            }
            c.label.text = text;   // plain text, never markup
            c.buttons.destroy_all_children();
            for (const b of (args.buttons ?? []).filter(k => k in BUTTONS)) {
                const btn = new St.Button({style_class: 'yabro-button', label: BUTTONS[b], reactive: true, can_focus: false});
                btn.connect('clicked', () => this._event(`button:${b}`, b));
                c.buttons.add_child(btn);
            }
            // RTL: only the direction is set here; full ADR-0019 handling is deferred.
            c.bubble.set_text_direction(args.dir === 'rtl' ? Clutter.TextDirection.RTL : Clutter.TextDirection.LTR);
            const at = args.bubble_at ?? (target ? [target[0], target[1] + target[3] + 12] : [c.monitor.x + 40, c.monitor.y + 40]);
            c.bubble.set_position(at[0] - c.monitor.x, at[1] - c.monitor.y);
            c.bubble.show();
            c.avatar.set_position(at[0] - c.monitor.x - 40, at[1] - c.monitor.y);
            c.avatar.show();
            this._follow = {window: args.follow_window ?? 0, serial};
            this._visible = true;
            return new GLib.Variant('(u)', [serial]);
        });
    }

    FlyPointerAsync([[x, y], ms], invocation) {
        this._guard(invocation, () => {
            this._lastPing = GLib.get_monotonic_time();
            const c = this._containerFor(x, y);
            const serial = ++this._serial;
            if (c) {
                if (!c.pointer.visible)
                    c.pointer.set_position(c.monitor.width / 2, c.monitor.height / 2);
                c.pointer.show();
                c.pointer.ease({
                    x: x - c.monitor.x, y: y - c.monitor.y, duration: Math.min(Math.max(ms, 100), 1500),
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                });
                this._visible = true;
            }
            return new GLib.Variant('(u)', [serial]);
        });
    }

    SetAvatarAsync(_p, invocation) {
        this._guard(invocation, () => null);
    }

    SetIndicatorsAsync(_p, invocation) {
        this._guard(invocation, () => null);
    }

    HideAsync(_p, invocation) {
        if (!this._peers.allowed(invocation.get_sender(), CORE_ONLY))
            return deny(invocation);
        this.hide();
        invocation.return_value(null);
    }

    PingAsync([n], invocation) {
        if (!this._peers.allowed(invocation.get_sender(), CORE_ONLY))
            return deny(invocation);
        this._lastPing = GLib.get_monotonic_time();
        invocation.return_value(new GLib.Variant('(u)', [n]));
    }
}
