// Ya-Bro Shell extension entry point. Constructor does nothing; enable() builds, disable() undoes.
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {PACKAGE_VERSION} from 'resource:///org/gnome/shell/misc/config.js';

import {Peers} from './peers.js';
import {Bridge} from './bridge.js';
import {Overlay} from './overlay.js';

export default class YaBroExtension extends Extension {
    enable() {
        const connection = Gio.DBus.session;
        this._settings = this.getSettings();
        this._peers = new Peers(connection);
        this._overlay = new Overlay(connection, this._peers, this.path);
        this._bridge = new Bridge(connection, this._peers, this._overlay,
            this._settings, PACKAGE_VERSION, this.metadata['version-name'] ?? '');
        this._ownName = Gio.bus_own_name_on_connection(connection,
            'io.github.ahmedyousrisobhi.YaBro.Shell', Gio.BusNameOwnerFlags.NONE, null, null);
        // Works even when core is hung: hide locally first, then tell core.
        const stop = () => {
            this._overlay.hide();
            this._overlay.emitStopKey();
        };
        Main.wm.addKeybinding('stop-key', this._settings, Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL, stop);
        // Safety net: Mutter sometimes lets a shell-added binding through to the stage unconsumed
        // (S1: about half of fresh sessions). When it does, the stage still sees the key with the right
        // modifiers, so match the default combo here. If the binding fired, the stage never sees the key.
        const want = Clutter.ModifierType.SHIFT_MASK | Clutter.ModifierType.MOD4_MASK;
        this._stageKey = global.stage.connect('captured-event', (_actor, event) => {
            try {
                if (event.type() === Clutter.EventType.KEY_PRESS &&
                    event.get_key_symbol() === Clutter.KEY_Escape &&
                    (event.get_state() & want) === want) {
                    stop();
                    return Clutter.EVENT_STOP;
                }
            } catch (e) {
                console.error(`ya-bro: stop-key fallback: ${e.message}`);
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    disable() {
        if (this._stageKey)
            global.stage.disconnect(this._stageKey);
        this._stageKey = 0;
        Main.wm.removeKeybinding('stop-key');
        if (this._ownName)
            Gio.bus_unown_name(this._ownName);
        this._ownName = 0;
        this._bridge?.destroy();
        this._bridge = null;
        this._overlay?.destroy();
        this._overlay = null;
        this._peers?.destroy();
        this._peers = null;
        this._settings = null;
    }
}
