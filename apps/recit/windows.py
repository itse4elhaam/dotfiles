"""Small X11 window catalogue. Window titles never enter a shell command."""
import os
from Xlib import X, display, error


class WindowCatalog:
    def __init__(self):
        self.connection = None

    def _connect(self):
        if self.connection is None:
            self.connection = display.Display()
        return self.connection

    def list(self):
        connection = self._connect()
        root = connection.screen().root
        atom = connection.intern_atom
        prop = root.get_full_property(atom('_NET_CLIENT_LIST_STACKING'), X.AnyPropertyType)
        if prop is None:
            return []
        excluded = {atom('_NET_WM_WINDOW_TYPE_DESKTOP'), atom('_NET_WM_WINDOW_TYPE_DOCK'), atom('_NET_WM_WINDOW_TYPE_MENU'), atom('_NET_WM_WINDOW_TYPE_TOOLTIP')}
        result = []
        for wid in reversed(prop.value):
            try:
                window = connection.create_resource_object('window', int(wid))
                if window.get_attributes().map_state != X.IsViewable:
                    continue
                pid = window.get_full_property(atom('_NET_WM_PID'), X.AnyPropertyType)
                if pid is not None and len(pid.value) and int(pid.value[0]) == os.getpid():
                    continue
                types = window.get_full_property(atom('_NET_WM_WINDOW_TYPE'), X.AnyPropertyType)
                if types is not None and excluded.intersection(types.value):
                    continue
                title = window.get_full_property(atom('_NET_WM_NAME'), X.AnyPropertyType)
                title = title.value if title is not None else window.get_wm_name()
                if isinstance(title, bytes):
                    title = title.decode('utf-8', errors='replace')
                if not title:
                    continue
                classes = window.get_wm_class() or ()
                # Other RecIt process instances/test windows are not suitable capture targets.
                if any(value.lower() == 'recit' for value in classes):
                    continue
                app_name = classes[-1] if classes else ''
                result.append((f'{title} · {app_name}' if app_name else str(title), int(wid)))
            except error.XError:
                continue
        return result

    def geometry(self, wid):
        if not wid:
            return None
        connection = self._connect()
        try:
            window = connection.create_resource_object('window', int(wid))
            if window.get_attributes().map_state != X.IsViewable:
                return None
            geo = window.get_geometry()
            point = connection.screen().root.translate_coords(window, 0, 0)
            return point.x, point.y, geo.width, geo.height
        except error.XError:
            return None

    def pointer(self):
        point = self._connect().screen().root.query_pointer()
        return point.root_x, point.root_y

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
