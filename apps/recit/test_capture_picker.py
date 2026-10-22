"""Target selection and cancellation with synthetic screens and mocked OBS only."""
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog
from capture_picker import (CaptureTarget, CapturePicker, RegionOverlay,
    monitor_targets, drag_region, validate_region)
import test_app
qt = test_app.qt


def screen(name='DP-1', bounds=(-1200, 0, 800, 600), ratio=1.5):
    return SimpleNamespace(name=lambda:name, geometry=lambda:QRect(*bounds), devicePixelRatio=lambda:ratio)


class TargetTests(unittest.TestCase):
    def test_identity_does_not_follow_enumeration_and_keeps_negative_origin(self):
        a, b = screen(), screen('HDMI-1', (0, 0, 800, 600), 1)
        options = [('Screen HDMI-1 (800x600 @ 0,0)', 7), ('Screen DP-1 (1200x900 @ -1200,0)', 3)]
        targets = monitor_targets(options, [a,b])
        self.assertEqual([t.obs_index for t, _ in targets], [7,3])
        self.assertEqual(targets[1][0].bounds, (-1200,0,1200,900))
        self.assertEqual(monitor_targets(options, [b,a]), targets)
        self.assertEqual(monitor_targets(options[1:], [b]), [])
        self.assertEqual(monitor_targets([('Screen DP-1 (800x600 @ 0,0)', 0)], [a]), [])
        with self.assertRaises(FrozenInstanceError):
            targets[0][0].obs_index = 99

    def test_ambiguous_or_unknown_monitor_labels_fail_closed(self):
        self.assertEqual(monitor_targets([('unknown format', 0)], [screen()]), [])
        self.assertEqual(monitor_targets([('Screen DP-1 (1200x900 @ -1200,0)', 0)], [screen(),screen()]), [])

    def test_backwards_drag_fractional_scaling_and_edge_clamping(self):
        self.assertEqual(drag_region(QPoint(300,200), QPoint(10,20), 1.5, (1200,900)), (15,30,435,270))
        self.assertEqual(drag_region(QPoint(-5,-5), QPoint(900,800), 1.5, (1200,900)), (0,0,1200,900))
        for region in [(0,0,0,20),(-1,0,20,20),(1190,0,20,20),(0,0,1.2,20),None]:
            with self.subTest(region=region), self.assertRaises(ValueError):
                validate_region(region, (1200,900))
        target = CaptureTarget('region','DP-1',3,(-1200,0,1200,900),region=(15,30,435,270)).validate()
        self.assertEqual(target.pointer(-2000,-20), (0,0))
        self.assertEqual(target.pointer(100,1000), (1,1))
        self.assertEqual(target.pointer(-1185,30), (0,0))

    def test_overlay_escape_and_zero_drag_never_accept(self):
        target = CaptureTarget('screen','DP-1',0,(0,0,1200,900))
        overlay = RegionOverlay(target, screen(bounds=(0,0,800,600)))
        overlay.show()
        QTest.mouseClick(overlay, Qt.LeftButton, pos=QPoint(10,10))
        self.assertIsNone(overlay.region)
        QTest.keyClick(overlay, Qt.Key_Escape)
        self.assertEqual(overlay.result(), QDialog.Rejected)
        overlay.close()

    def test_picker_refresh_preserves_exact_id_and_cancel_has_no_target(self):
        engine, catalog = Mock(), Mock()
        engine.screen_options.return_value = []
        catalog.list.return_value = [('First',12),('Second',34)]
        picker = CapturePicker(engine,catalog,CaptureTarget('window',window_id=34))
        self.assertEqual(picker.choices.currentData().window_id,34)
        catalog.list.return_value = [('First',12)]
        picker.refresh()
        self.assertIsNone(picker.choices.currentData())
        picker.choose()
        self.assertIsNone(picker.target)
        picker.reject()


class CaptureFlowTests(unittest.TestCase):
    setUp = test_app.AppChecks.setUp
    tearDown = test_app.AppChecks.tearDown

    def window_target(self):
        test_app.AppChecks.window_target(self)

    def test_refresh_does_not_select_another_window(self):
        self.window_target()
        w = self.window
        w.window_catalog.list.return_value = [('Other',456)]
        w.refresh_windows()
        self.assertIsNone(w.capture_window.currentData())
        w.configure()
        self.assertFalse(w.configuration_valid)

    def test_target_change_cancels_countdown_and_stale_start(self):
        w = self.window
        w.toggle_record()
        old = w._target_generation
        w.target_changed()
        self.assertFalse(w.counting)
        self.assertGreater(w._target_generation,old)
        w.start()
        w.engine.start.assert_not_called()
        w.audio_prepared(None,'')
        w.engine.start.assert_not_called()

    def test_window_closed_during_preparation_never_starts_or_falls_back(self):
        self.window_target()
        w = self.window
        w.window_catalog.geometry.return_value = None
        w.audio_prepared(None,'')
        self.assertFalse(w.configuration_valid)
        w.engine.start.assert_not_called()

    def test_region_has_crop_parameters_and_camera_only_in_composition(self):
        w = self.window
        w.set_mode('screen')
        w.capture_kind.setCurrentIndex(w.capture_kind.findData('region'))
        sw, sh = qt.primaryScreen().geometry().width(), qt.primaryScreen().geometry().height()
        w.capture_target = CaptureTarget('region','Test-monitor',0,(0,0,sw,sh),region=(10,10,100,80))
        with patch.object(w,'show_bubble') as bubble:
            w.configure()
        self.assertTrue(w.configuration_valid)
        self.assertEqual(w.engine.configure.call_args.kwargs['region'], (10,10,100,80))
        self.assertFalse(w.engine.configure.call_args.kwargs['floating_camera'])
        bubble.assert_not_called()

    def test_monitor_removed_or_reindexed_invalidates_without_redirect(self):
        w = self.window
        w.set_mode('screen'); w.configure()
        target = w.capture_target
        w.engine.screen_options.return_value = []
        with self.assertRaises(ValueError):
            w.resolve_target()
        w.engine.screen_options.return_value = [('Screen Test-monitor (800x800 @ 0,0)', 9)]
        with self.assertRaises(ValueError):
            w.resolve_target()
        self.assertEqual(w.capture_target,target)

    def test_monitor_geometry_signal_cancels_preparation_and_recording(self):
        w = self.window
        w.set_mode('screen'); w.configure()
        w.preparing_audio = w.busy = True
        w.monitor_changed()
        self.assertFalse(w.preparing_audio)
        self.assertFalse(w.configuration_valid)
        with self.assertRaises(ValueError):
            w.resolve_target()
        w.target_changed(); w.configure()
        w.recording = True
        with patch.object(w,'stop') as stop:
            w.monitor_changed()
            stop.assert_called_once()
        self.assertIn('saved',w.recording_error)

    def test_tab_target_disables_native_record_and_releases_native_sources(self):
        w = self.window
        w.set_mode('screen')
        w.capture_kind.setCurrentIndex(w.capture_kind.findData('tab'))
        w.configure()
        w.engine.clear_capture.assert_called_once()
        self.assertFalse(w.record_button.isEnabled())
        self.assertFalse(w.idle_audio.wanted())
        w.toggle_record()
        self.assertFalse(w.counting)
        w.engine.start.assert_not_called()


class RegionEngineTests(unittest.TestCase):
    from test_engine import CameraPreviewTests
    setUp = CameraPreviewTests.setUp
    configure = CameraPreviewTests.configure

    def test_crop_filter_precedes_fit_and_camera_is_added_once(self):
        e = self.engine
        order = Mock()
        order.attach_mock(e._filter,'filter')
        order.attach_mock(e._obs.obs_scene_add,'add')
        e._place = Mock()
        order.attach_mock(e._place,'place')
        self.configure(region=(100,80,800,600),monitor_bounds=(0,0,1920,1080),floating_camera=True)
        calls = order.mock_calls
        crop = next(i for i,c in enumerate(calls) if c[0] == 'filter' and c.args[1] == 'crop_filter')
        fit = next(i for i,c in enumerate(calls) if c[0] == 'place')
        self.assertLess(crop,fit)
        self.assertEqual(e._screen_dimensions,(800,600))
        self.assertEqual(e._obs.obs_scene_add.call_count,2)
        self.assertEqual(e._filter.call_args_list[0].args[3],
            {'relative':False,'left':100,'top':80,'cx':800,'cy':600})
        e.set_screen_zoom(2,1,1)
        self.assertEqual(e._screen_dimensions,(800,600))

    def test_invalid_region_rejected_before_old_scene_is_destroyed(self):
        e = self.engine
        with patch.object(e,'_clear_scene') as clear:
            for region in [(0,0,0,10),(1900,0,100,10),(-1,0,10,10)]:
                with self.assertRaises(ValueError):
                    self.configure(region=region,monitor_bounds=(0,0,1920,1080))
            clear.assert_not_called()

    def test_screen_catalogue_uses_obs_integer_values_and_releases_probe(self):
        e = self.engine
        o = e._obs
        o.obs_property_list_item_count.return_value = 2
        o.obs_property_list_item_disabled.side_effect = [False,True]
        o.obs_property_list_item_name.return_value = b'Screen DP-1 (1920x1080 @ 0,0)'
        o.obs_property_list_item_int.return_value = 17
        self.assertEqual(e.screen_options(), [('Screen DP-1 (1920x1080 @ 0,0)',17)])
        e._source.assert_called_once_with('xshm_input','RecIt monitor catalogue',{'screen':-1})
        o.obs_source_release.assert_called_once_with(301)
        o.obs_properties_destroy.assert_called_once()
        o.obs_scene_add.assert_not_called()

    def test_screen_catalogue_borrows_current_source_without_releasing_it(self):
        e = self.engine
        e._screen_source = 123
        e._obs.obs_property_list_item_count.return_value = 0
        self.assertEqual(e.screen_options(), [])
        e._source.assert_not_called()
        e._obs.obs_source_properties.assert_called_once_with(123)
        e._obs.obs_source_release.assert_not_called()

    def test_screen_catalogue_failure_still_releases_temporary_source(self):
        e = self.engine
        e._obs.obs_source_properties.side_effect = RuntimeError('synthetic property failure')
        with self.assertRaises(RuntimeError):
            e.screen_options()
        e._obs.obs_source_release.assert_called_once_with(301)
