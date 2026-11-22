// Tracks which D-Bus peers may talk to the extension (ADR-0023 §11): core, perceiver, actuator.
import Gio from 'gi://Gio';

const PREFIX = 'io.github.ahmedyousrisobhi.YaBro.';
export const OBJECT_PATH = '/io/github/ahmedyousrisobhi/YaBro/Shell';

export class Peers {
    constructor(connection) {
        this._connection = connection;
        this._owners = new Map();
        this._watches = [];
        for (const role of ['Core', 'Perceiver', 'Actuator']) {
            const id = Gio.bus_watch_name_on_connection(
                connection, PREFIX + role, Gio.BusNameWatcherFlags.NONE,
                (_c, _n, owner) => this._owners.set(role, owner),
                () => this._owners.delete(role));
            this._watches.push(id);
        }
    }

    destroy() {
        this._watches.forEach(id => Gio.bus_unwatch_name(id));
        this._watches = [];
        this._owners.clear();
    }

    hasCore() {
        return this._owners.has('Core');
    }

    // Returns true if `sender` currently owns one of `roles`.
    allowed(sender, roles) {
        return roles.some(r => this._owners.get(r) === sender);
    }

    // Signals are unicast to allowed peers only: a broadcast would leak window ids to any
    // same-uid process holding a match rule.
    emit(iface, signal, params, roles) {
        for (const role of roles) {
            const dest = this._owners.get(role);
            if (!dest)
                continue;
            try {
                this._connection.emit_signal(dest, OBJECT_PATH, iface, signal, params);
            } catch (e) {
                console.error(`ya-bro: emit ${signal} failed: ${e.message}`);
            }
        }
    }
}

export function deny(invocation) {
    invocation.return_dbus_error('org.freedesktop.DBus.Error.AccessDenied', 'Caller not allowed');
}
