// Ya-Bro Shell extension entry point. Constructor does nothing; enable() builds, disable() undoes.
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
        this._overlay = new Overlay(connection, this._peers);
        this._bridge = new Bridge(connection, this._peers, this._overlay,
            PACKAGE_VERSION, this.metadata['version-name'] ?? '');
        this._ownName = Gio.bus_own_name_on_connection(connection,
            'io.github.ahmedyousrisobhi.YaBro.Shell', Gio.BusNameOwnerFlags.NONE, null, null);
        // Works even when core is hung: hide locally first, then tell core.
        Main.wm.addKeybinding('stop-key', this._settings, Meta.KeyBindingFlags.NONE,
            Shell.ActionMode.ALL, () => {
                this._overlay.hide();
                this._overlay.emitStopKey();
            });
    }

    disable() {
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
