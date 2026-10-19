import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from Xlib import X, error
from windows import WindowCatalog


class WindowChecks(unittest.TestCase):
    def test_list_excludes_own_windows_and_keeps_titles_as_text(self):
        catalog = WindowCatalog()
        connection = catalog.connection = Mock()
        connection.intern_atom.side_effect = lambda name: name
        root = connection.screen.return_value.root
        root.get_full_property.return_value = SimpleNamespace(value=[1, 2])
        own, target = Mock(), Mock()
        own.get_attributes.return_value.map_state = X.IsViewable
        target.get_attributes.return_value.map_state = X.IsViewable
        def properties(pid, title):
            values = {'_NET_WM_PID': SimpleNamespace(value=[pid]), '_NET_WM_NAME': SimpleNamespace(value=title)}
            return lambda atom, kind: values.get(atom)
        own.get_full_property.side_effect = properties(os.getpid(), b'RecIt')
        target.get_full_property.side_effect = properties(os.getpid()+100, b'Notes $(not a command)')
        target.get_wm_class.return_value = ('notes', 'Notes')
        connection.create_resource_object.side_effect = lambda kind, wid: {1: own, 2: target}[wid]
        self.assertEqual(catalog.list(), [('Notes $(not a command) · Notes', 2)])

    def test_minimized_window_is_unavailable(self):
        catalog = WindowCatalog()
        catalog.connection = Mock()
        window = catalog.connection.create_resource_object.return_value
        window.get_attributes.return_value.map_state = X.IsUnmapped
        self.assertIsNone(catalog.geometry(123))

    def test_geometry_uses_window_content_coordinates(self):
        catalog = WindowCatalog()
        catalog.connection = Mock()
        window = catalog.connection.create_resource_object.return_value
        window.get_attributes.return_value.map_state = X.IsViewable
        window.get_geometry.return_value = SimpleNamespace(width=800, height=600)
        root = catalog.connection.screen.return_value.root
        root.translate_coords.return_value = SimpleNamespace(x=120, y=80)
        self.assertEqual(catalog.geometry(123), (120, 80, 800, 600))
        root.translate_coords.assert_called_once_with(window, 0, 0)


if __name__ == '__main__':
    unittest.main()
