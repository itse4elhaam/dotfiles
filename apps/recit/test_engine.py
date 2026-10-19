"""Run safe unit checks with `python -m unittest discover -s apps/recit`.

Opt-in live smoke (captures actual display/audio/camera; deletes recording):
  QT_QPA_PLATFORM=xcb python apps/recit/test_engine.py --capture
  QT_QPA_PLATFORM=xcb python apps/recit/test_engine.py --capture --camera /dev/video0
Camera-free native source renderer smoke:
  QT_QPA_PLATFORM=xcb python apps/recit/test_engine.py --preview-smoke
Camera-free XComposite capture and encoding smoke:
  QT_QPA_PLATFORM=xcb python apps/recit/test_engine.py --window-smoke
Qt-free GLX initialization and explicit EGL fallback smoke:
  python apps/recit/test_engine.py --backend-smoke
Add --platform egl to --preview-smoke to check the fallback renderer.
"""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, call, patch

from engine import Engine, EngineError, _DisplayInfo, _Draw, _VideoInfo, _Window, screen_transform


class ScreenTransformTests(unittest.TestCase):
    def test_fit_and_reset_ignore_pointer_position(self):
        for center in (0, .5, 1):
            self.assertEqual(screen_transform(1920, 1080, 3840, 2160, 1, center, center), (0, 0, .5))
            self.assertEqual(screen_transform(1920, 1080, 1280, 1024, 1, center, center), (285, 0, 1.0546875))

    def test_zoom_centers_requested_source_point(self):
        self.assertEqual(screen_transform(1920, 1080, 3840, 2160, 2, .5, .5), (-960, -540, 1))
        self.assertEqual(screen_transform(1920, 1080, 3840, 2160, 2, .4, .6), (-576, -756, 1))

    def test_edges_and_input_clamping(self):
        self.assertEqual(screen_transform(1920, 1080, 1920, 1080, 9, -2, 4), (0, -2160, 3))
        self.assertEqual(screen_transform(1920, 1080, 1920, 1080, -3, .9, .1), (0, 0, 1))

    def test_portrait_keeps_horizontal_letterbox_until_filled(self):
        self.assertEqual(screen_transform(1920, 1080, 1080, 1920, 2, 0, 1), (352.5, -1080, 1.125))

    def test_ultrawide_keeps_vertical_letterbox_until_filled(self):
        self.assertEqual(screen_transform(1920, 1080, 3840, 1080, 1.5, 1, 0), (-960, 135, .75))

    def test_clamping_never_exposes_new_blank_edges(self):
        for sw, sh in ((3840, 2160), (1080, 1920), (3440, 1440), (1024, 1024)):
            for factor in (1, 1.1, 2, 3):
                for center in (0, .1, .5, .9, 1):
                    x, y, scale = screen_transform(1920, 1080, sw, sh, factor, center, center)
                    for pos, extent, canvas in ((x, sw * scale, 1920), (y, sh * scale, 1080)):
                        if extent >= canvas:
                            self.assertLessEqual(pos, 0)
                            self.assertGreaterEqual(pos + extent, canvas)
                        else:
                            self.assertAlmostEqual(pos, (canvas - extent) / 2)

    def test_invalid_numbers(self):
        for dims in ((0, 1080, 1920, 1080), (1920, -1, 1920, 1080)):
            with self.assertRaises(EngineError):
                screen_transform(*dims, 1, .5, .5)
        for index in range(7):
            for value in (float("nan"), float("inf")):
                args = [1920, 1080, 3840, 2160, 2, .5, .5]
                args[index] = value
                with self.assertRaises(EngineError):
                    screen_transform(*args)


class CameraPreviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = e = Engine.__new__(Engine)
        e._obs = Mock()
        e._closed = False
        e._started_obs = True
        e._output = None
        e._scene = None
        e._sources = []
        e._camera_display = None
        e._camera_source = None
        e._camera_item = None
        e._camera_display_size = None
        e._camera_preview_enabled = False
        e._camera_mirror = False
        e._screen_item = None
        e._screen_source = None
        e._window_id = None
        e._screen_dimensions = None
        e._xdisplay = 10
        e.width, e.height = 1920, 1080
        e.errors = []
        e._camera_draw_callback = _Draw(e._draw_camera)
        e._obs.obs_display_create.side_effect = [101, 102]
        e._obs.obs_scene_add.side_effect = [201, 202]
        e._source = Mock(side_effect=[301, 302])
        e.source_types = {"xshm_input", "xcomposite_input", "v4l2_input"}
        e._dimensions = Mock(return_value=(1920, 1080))
        e._obs.obs_source_get_width.return_value = 1920
        e._obs.obs_source_get_height.return_value = 1080
        e._filter = Mock()
        e._mask = Mock(return_value="mask.png")

    def configure(self, **kwargs):
        with patch("engine.os.access", return_value=True):
            self.engine.configure(camera="/dev/fake-camera", microphone=None, **kwargs)

    def test_floating_camera_is_filtered_but_not_composited(self):
        self.configure(floating_camera=True)
        e = self.engine
        self.assertEqual(e._camera_source, 302)
        e._obs.obs_scene_add.assert_called_once_with(e._scene, 301)
        self.assertEqual([c.args[1] for c in e._filter.call_args_list], ["crop_filter"])
        self.assertEqual(e._source.call_count, 2)

    def test_mirrored_floating_custom_shape_is_applied_only_by_window(self):
        self.configure(floating_camera=True, shape="custom", mask_path="left-half.png", mirror=True)
        self.engine._mask.assert_not_called()
        self.assertEqual([c.args[1] for c in self.engine._filter.call_args_list], ["crop_filter"])

    def test_default_still_composites_camera(self):
        self.configure()
        self.assertEqual(self.engine._obs.obs_scene_add.call_count, 2)

    def test_window_uses_exact_decimal_id_and_keeps_floating_camera_mask(self):
        self.configure(window_id=0x123AB, floating_camera=True, shape="custom", mask_path="left-half.png")
        e = self.engine
        self.assertEqual(e._source.call_args_list[0], call("xcomposite_input", "RecIt window", {
            "capture_window": "74667", "show_cursor": True, "include_border": False}))
        self.assertEqual(e._obs.obs_scene_add.call_count, 2)
        e._mask.assert_called_once_with("custom", "left-half.png", 1080, 1080)
        self.assertEqual([c.args[1] for c in e._filter.call_args_list], ["crop_filter", "mask_filter_v2"])
        self.assertTrue(e._camera_mirror)

    def test_invalid_window_id_preserves_existing_scene(self):
        self.configure()
        e = self.engine
        e._obs.reset_mock()
        for window_id in (0, -1, 2**32, True, "123", 1.5):
            with self.subTest(window_id=window_id), self.assertRaisesRegex(EngineError, "32-bit X11"):
                self.configure(window_id=window_id)
        e._obs.obs_scene_release.assert_not_called()

    def test_desktop_keeps_xshm_and_has_no_window_dimensions(self):
        self.configure(screen=1)
        self.assertEqual(self.engine._source.call_args_list[0],
                         call("xshm_input", "RecIt screen", {"screen": 1, "show_cursor": True}))
        self.assertIsNone(self.engine.window_dimensions())

    def test_unavailable_window_capture_preserves_existing_scene(self):
        self.configure()
        e = self.engine
        e._obs.reset_mock()
        e.source_types.remove("xcomposite_input")
        with self.assertRaisesRegex(EngineError, "GLX backend"):
            self.configure(window_id=123)
        e._obs.obs_scene_release.assert_not_called()

    def test_camera_only_ignores_selected_window(self):
        self.configure(mode="camera", window_id=123)
        self.assertEqual(self.engine._source.call_args_list[0].args[0], "v4l2_input")
        self.assertIsNone(self.engine.window_dimensions())

    def test_window_zoom_refreshes_size_and_retains_last_size_during_resize(self):
        self.configure(window_id=123)
        e = self.engine
        e._place = Mock()
        e._obs.obs_source_get_width.return_value = 1280
        e._obs.obs_source_get_height.return_value = 720
        self.assertEqual(e.window_dimensions(), (1280, 720))
        e.set_screen_zoom(2, .5, .5)
        e._place.assert_called_with(201, -960, -540, 3)
        e._obs.obs_source_get_width.return_value = 0
        self.assertEqual(e.window_dimensions(), (0, 720))
        e.restore_screen_zoom()
        e._place.assert_called_with(201, 0, 0, 1.5)
        e._clear_scene()
        self.assertIsNone(e.window_dimensions())

    def test_camera_drag_moves_only_overlay_with_mirror_preserved(self):
        self.configure(window_id=123, floating_camera=True, size=.2, mirror=True)
        e = self.engine
        e._obs.obs_source_get_width.return_value = 1080
        e._place = Mock()
        e.set_camera_position(1.5, -1)
        e._place.assert_called_once_with(202, 1704, 0, .2, True, 216)
        e.set_camera_position(.5, 1)
        e._place.assert_called_with(202, 852, 864, .2, True, 216)
        for x, y in ((float("nan"), 0), (0, float("inf"))):
            with self.assertRaises(EngineError):
                e.set_camera_position(x, y)
        e._clear_scene()
        e._place.reset_mock()
        e.set_camera_position(0, 0)
        e._place.assert_not_called()

    def test_camera_drag_does_not_move_fullscreen_or_desktop_floating_camera(self):
        for kwargs in ({"mode": "camera"}, {"floating_camera": True}):
            self.setUp()
            self.configure(**kwargs)
            self.engine._place = Mock()
            self.engine.set_camera_position(.3, .7)
            self.engine._place.assert_not_called()

    def test_floating_flag_preserves_camera_only_mode(self):
        self.configure(mode="camera", floating_camera=True)
        e = self.engine
        self.assertEqual(e._camera_source, 301)
        e._obs.obs_scene_add.assert_called_once_with(e._scene, 301)
        self.assertIsNone(e._screen_item)

    def test_replacing_hiding_and_detaching_balances_showing(self):
        e = self.engine
        e._camera_source = 302
        e.attach_camera_preview(20, 200, 200)
        e.attach_camera_preview(21, 200, 200)
        e.set_camera_preview_enabled(False)
        e.set_camera_preview_enabled(False)
        e.set_camera_preview_enabled(True)
        e.detach_camera_preview()
        e.detach_camera_preview()
        self.assertEqual(e._obs.obs_source_inc_showing.call_args_list, [call(302)] * 3)
        self.assertEqual(e._obs.obs_source_dec_showing.call_args_list, [call(302)] * 3)
        self.assertEqual(e._obs.obs_display_destroy.call_args_list, [call(101), call(102)])
        self.assertFalse(e._camera_preview_enabled)
        self.assertIsNone(e._camera_display)

    def test_clear_detaches_before_releasing_camera(self):
        self.configure(floating_camera=True)
        e = self.engine
        e.attach_camera_preview(20, 200, 200)
        e._obs.reset_mock()
        e._clear_scene()
        calls = e._obs.mock_calls
        removed = calls.index(call.obs_display_remove_draw_callback(101, e._camera_draw_callback, None))
        destroyed = calls.index(call.obs_display_destroy(101))
        hidden = calls.index(call.obs_source_dec_showing(302))
        released = calls.index(call.obs_source_release(302))
        self.assertLess(removed, destroyed)
        self.assertLess(destroyed, hidden)
        self.assertLess(hidden, released)
        self.assertIsNone(e._camera_source)
        self.assertIsNone(e._screen_item)

    def test_failed_display_does_not_claim_showing_reference(self):
        e = self.engine
        e._camera_source = 302
        e._obs.obs_display_create.side_effect = [None]
        with self.assertRaisesRegex(EngineError, "native X11"):
            e.attach_camera_preview(20, 200, 200)
        e._obs.obs_source_inc_showing.assert_not_called()
        e.detach_camera_preview()
        e._obs.obs_source_dec_showing.assert_not_called()

    def test_invalid_attach_preserves_existing_display(self):
        e = self.engine
        with self.assertRaisesRegex(EngineError, "Configure a camera"):
            e.attach_camera_preview(20, 200, 200)
        e._camera_source = 302
        e.attach_camera_preview(20, 200, 200)
        for wid, width, height in ((0, 200, 200), (2**32, 200, 200), (20, 0, 200), (20, 200, -1)):
            with self.assertRaisesRegex(EngineError, "native X11"):
                e.attach_camera_preview(wid, width, height)
        e._obs.obs_display_destroy.assert_not_called()

    def test_renderer_uses_filtered_source_dimensions_and_mirror(self):
        e = self.engine
        e._camera_source = 302
        e._camera_preview_enabled = True
        e._obs.obs_source_get_width.return_value = 640
        e._obs.obs_source_get_height.return_value = 480
        for mirror in (False, True):
            e._obs.reset_mock()
            e._camera_mirror = mirror
            e._draw_camera(None, 200, 200)
            e._obs.gs_set_viewport.assert_called_once_with(0, 25, 200, 150)
            e._obs.gs_ortho.assert_called_once_with(640 if mirror else 0, 0 if mirror else 640, 0, 480, -100, 100)
            e._obs.obs_source_video_render.assert_called_once_with(302)
            e._obs.obs_render_main_texture.assert_not_called()
        e._obs.reset_mock()
        e._camera_preview_enabled = False
        e._draw_camera(None, 200, 200)
        e._obs.obs_source_video_render.assert_not_called()

    def test_zoom_updates_only_screen_item_and_restores_fit(self):
        self.configure(floating_camera=True)
        e = self.engine
        e._obs.reset_mock()
        positions, scales = [], []
        e._obs.obs_sceneitem_set_pos.side_effect = lambda item, vec: positions.append((item, vec._obj.x, vec._obj.y))
        e._obs.obs_sceneitem_set_scale.side_effect = lambda item, vec: scales.append((item, vec._obj.x, vec._obj.y))
        e.set_screen_zoom(2, .5, .5)
        e.restore_screen_zoom()
        self.assertEqual(positions, [(201, -960, -540), (201, 0, 0)])
        self.assertEqual(scales, [(201, 2, 2), (201, 1, 1)])
        self.assertEqual(e._obs.obs_sceneitem_defer_update_begin.call_args_list, [call(201)] * 2)
        self.assertEqual(e._obs.obs_sceneitem_defer_update_end.call_args_list, [call(201)] * 2)
        e._obs.obs_source_update.assert_not_called()

    def test_zoom_defer_ends_even_on_error(self):
        self.configure(floating_camera=True)
        e = self.engine
        e._obs.reset_mock()
        e._obs.obs_sceneitem_set_pos.side_effect = RuntimeError("failure")
        with self.assertRaises(RuntimeError):
            e.set_screen_zoom(2, .5, .5)
        e._obs.obs_sceneitem_defer_update_end.assert_called_once_with(201)


class EngineContracts(unittest.TestCase):
    def test_linux_64_bit_abi(self):
        self.assertEqual(ctypes.sizeof(ctypes.c_void_p), 8)
        self.assertEqual(ctypes.sizeof(_VideoInfo), 56)
        self.assertEqual(_VideoInfo.gpu_conversion.offset, 40)
        self.assertEqual(_VideoInfo.colorspace.offset, 44)
        self.assertEqual(ctypes.sizeof(_Window), 16)
        self.assertEqual(_Window.display.offset, 8)
        self.assertEqual(ctypes.sizeof(_DisplayInfo), 40)

    def test_stop_timeout_retains_live_resources(self):
        engine = Engine.__new__(Engine)
        engine._output = 123
        engine._obs = Mock()
        engine._obs.obs_output_paused.return_value = False
        engine._stop_event = Mock()
        engine._stop_event.is_set.return_value = False
        engine._stop_event.wait.return_value = False
        engine.errors = []
        engine._release_recording = Mock()
        with self.assertRaisesRegex(EngineError, "10 seconds"):
            engine.stop()
        engine._obs.obs_output_stop.assert_called_once_with(123)
        engine._obs.obs_output_force_stop.assert_called_once_with(123)
        waits = [call.args[0] for call in engine._stop_event.wait.call_args_list]
        self.assertEqual(len(waits), 2)
        self.assertLessEqual(waits[0], 8.0)
        self.assertLessEqual(waits[1], 10.0)
        engine._release_recording.assert_not_called()
        self.assertEqual(engine._output, 123)

    def test_invalid_canvas_does_not_claim_obs(self):
        with self.assertRaises(EngineError):
            Engine(0, 1921, 1080)
        self.assertIsNone(Engine._instance)

    def test_invalid_platform_does_not_claim_obs(self):
        with self.assertRaisesRegex(EngineError, "graphics platform"):
            Engine(0, 320, 240, platform="wayland")
        self.assertIsNone(Engine._instance)


def preview_smoke(platform="glx"):
    """Check real asynchronous OBS drawing with a synthetic image, no camera."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    class Preview(QWidget):
        def paintEngine(self):
            return None

        def paintEvent(self, event):
            pass

    app = QApplication([])
    widgets = [Preview(), Preview()]
    for index, widget in enumerate(widgets):
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        for attribute in (Qt.WidgetAttribute.WA_NativeWindow,
                          Qt.WidgetAttribute.WA_PaintOnScreen,
                          Qt.WidgetAttribute.WA_NoSystemBackground):
            widget.setAttribute(attribute)
        widget.setWindowTitle("RecIt synthetic renderer test")
        widget.setGeometry(100 + 350 * index, 100, 240, 240)
        widget.show()
    app.processEvents()

    def tick(duration=.3):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    def pixel(widget, x, y):
        image = widget.screen().grabWindow(int(widget.winId())).toImage()
        return image.pixelColor(round(x * image.width() / 240), round(y * image.height() / 240))

    def physical_size(widget):
        ratio = widget.devicePixelRatioF()
        return round(widget.width() * ratio), round(widget.height() * ratio)

    main, camera = widgets
    engine = Engine(int(main.winId()), 320, 240, platform=platform)
    try:
        engine.resize_preview(*physical_size(main))
        with tempfile.TemporaryDirectory(prefix="recit-preview-smoke-") as directory:
            path = Path(directory) / "colors.png"
            image = QImage(320, 240, QImage.Format.Format_ARGB32)
            image.fill(QColor("red"))
            painter = QPainter(image)
            painter.fillRect(160, 0, 160, 240, QColor("lime"))
            painter.end()
            assert image.save(str(path))
            source = engine._source("image_source", "Synthetic camera", {"file": str(path)})
            engine._sources.append(source)
            engine._camera_source = source
            engine._filter(source, "crop_filter", "Synthetic crop", {
                "relative": False, "left": 40, "top": 0, "cx": 240, "cy": 240})
            mask = engine._mask("circle", None, 240, 240)
            engine._filter(source, "mask_filter_v2", "Synthetic mask", {
                "image_path": mask, "type": "mask_alpha_filter.effect",
                "opacity": 1.0, "color": 0xFFFFFF, "stretch": True})
            engine.attach_camera_preview(int(camera.winId()), *physical_size(camera))
            tick(.7)
            assert engine._dimensions(source, "Synthetic camera") == (240, 240)
            left, right = pixel(camera, 60, 120), pixel(camera, 180, 120)
            assert left.red() > 200 and left.green() < 30, left.name()
            assert right.green() > 200 and right.red() < 30, right.name()
            assert pixel(camera, 0, 0).lightness() < 20, "Camera mask was not rendered"
            assert pixel(main, 120, 120).lightness() < 30, "Camera leaked into the main composition"
            engine._camera_mirror = True
            engine.attach_camera_preview(int(camera.winId()), *physical_size(camera))
            tick()
            left, right = pixel(camera, 60, 120), pixel(camera, 180, 120)
            assert left.green() > 200 and left.red() < 30, left.name()
            assert right.red() > 200 and right.green() < 30, right.name()
            engine.set_camera_preview_enabled(False)
            tick(.1)
            engine.set_camera_preview_enabled(True)
            tick()
            assert pixel(camera, 60, 120).green() > 200
            # Exercise callback teardown while the render thread is running.
            engine._clear_scene()
            tick(.1)
    finally:
        engine.close()
        for widget in widgets:
            widget.close()
        app.processEvents()
    print("Native source-only preview passed: asynchronous rendering, crop, mask, mirror, replacement, hide/resume, teardown.")


def window_smoke():
    """Real XComposite preview and recording; no camera/audio devices opened."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import QApplication, QWidget

    class Target(QWidget):
        def paintEvent(self, event):
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("red"))
            painter.fillRect(self.width() // 2, 0, self.width() // 2, self.height(), QColor("lime"))
            painter.end()

    class Preview(QWidget):
        def paintEngine(self):
            return None

        def paintEvent(self, event):
            pass

    app = QApplication([])
    target, preview, dummy = Target(), Preview(), QWidget()
    widgets = (target, preview, dummy)
    for widget in widgets:
        widget.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    for attribute in (Qt.WidgetAttribute.WA_PaintOnScreen, Qt.WidgetAttribute.WA_NoSystemBackground):
        preview.setAttribute(attribute)
    target.setWindowTitle("RecIt synthetic capture target")
    target.setGeometry(100, 100, 320, 240)
    preview.setGeometry(800, 100, 320, 240)
    dummy.setGeometry(130, 130, 80, 80)
    dummy.setStyleSheet("background: blue")
    for widget in widgets:
        widget.show()
    dummy.raise_()

    def tick(duration=.4):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    def pixel(x, y):
        image = preview.screen().grabWindow(int(preview.winId())).toImage()
        return image.pixelColor(round(x * image.width() / 320), round(y * image.height() / 240))

    def target_dimensions():
        ratio = target.devicePixelRatioF()
        return round(target.width() * ratio), round(target.height() * ratio)

    def red(color):
        assert color.red() > 200 and color.green() < 30 and color.blue() < 30, color.name()

    def green(color):
        assert color.green() > 200 and color.red() < 30 and color.blue() < 30, color.name()

    tick()
    engine = Engine(int(preview.winId()), 320, 240)
    try:
        ratio = preview.devicePixelRatioF()
        engine.resize_preview(round(preview.width() * ratio), round(preview.height() * ratio))
        engine.configure(window_id=int(target.winId()), camera=None, microphone=None)
        tick(.8)
        assert engine.window_dimensions() == target_dimensions(), engine.window_dimensions()
        # Prove the dummy covers the selected content on the desktop, while
        # XComposite still renders the selected window's own red pixels.
        desktop = target.screen().grabWindow(0).toImage()
        point = dummy.mapToGlobal(dummy.rect().center())
        origin = target.screen().geometry().topLeft()
        ratio = target.screen().devicePixelRatio()
        covered = desktop.pixelColor(round((point.x() - origin.x()) * ratio),
                                     round((point.y() - origin.y()) * ratio))
        assert covered.blue() > 200 and covered.red() < 30, covered.name()
        red(pixel(60, 60))
        green(pixel(240, 120))
        engine.set_screen_zoom(2, .25, .5)
        tick()
        red(pixel(240, 120))
        engine.restore_screen_zoom()
        tick()
        green(pixel(240, 120))
        target.resize(640, 240)
        tick(.8)
        assert engine.window_dimensions() == target_dimensions(), engine.window_dimensions()
        engine.restore_screen_zoom()
        tick()
        red(pixel(60, 120))
        green(pixel(240, 120))
        assert pixel(160, 20).lightness() < 30, "Resized window did not letterbox"
        engine.set_screen_zoom(2, .5, .5)
        tick()
        red(pixel(60, 20))
        green(pixel(240, 20))
        with tempfile.TemporaryDirectory(prefix="recit-window-smoke-") as directory:
            path = Path(directory) / "window.mkv"
            engine.start(path)
            tick(1.5)
            print("Window recording stats:", json.dumps(engine.stats()))
            engine.stop()
            if "ffmpeg_vaapi" in engine.encoders and Path("/dev/dri/renderD128").exists():
                assert engine.encoder == "ffmpeg_vaapi", engine.warnings
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
            video = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert (video["codec_name"], video["width"], video["height"]) == ("h264", 320, 240)
            assert float(probe["format"]["duration"]) > 1
            frame = subprocess.check_output([
                "ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
            assert len(frame) == 320 * 240 * 3
            for x, check in ((60, red), (240, green)):
                offset = (120 * 320 + x) * 3
                check(QColor(*frame[offset:offset + 3]))
        assert not engine.errors, engine.errors
    finally:
        engine.close()
        for widget in widgets:
            widget.close()
        app.processEvents()
    print("Window capture passed: exact ID, overlapping dummy excluded, zoom/reset, live resize, letterboxing, encoded pixels; no camera/audio devices opened.")


def backend_smoke():
    """Run without Qt so Qt cannot hide OBS 27's libGL lifetime bug."""
    for platform in ("glx", "egl"):
        script = (
            "from engine import Engine; "
            f"e = Engine(0, 320, 240, platform={platform!r}); "
            "assert 'xshm_input' in e.source_types; "
            + ("assert 'xcomposite_input' in e.source_types; " if platform == "glx" else "")
            + "e.close(); assert Engine._instance is None"
        )
        subprocess.run([sys.executable, "-X", "faulthandler", "-c", script],
                       cwd=Path(__file__).resolve().parent, check=True, timeout=15)
    print("Qt-free GLX initialization and explicit EGL fallback passed.")


def capture_smoke(camera=None):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QWidget

    class Preview(QWidget):
        def paintEngine(self):
            return None

        def paintEvent(self, event):
            pass

    app = QApplication([])
    widget = Preview()
    for attribute in (Qt.WidgetAttribute.WA_NativeWindow,
                      Qt.WidgetAttribute.WA_PaintOnScreen,
                      Qt.WidgetAttribute.WA_NoSystemBackground):
        widget.setAttribute(attribute)
    widget.resize(640, 360)
    widget.show()
    app.processEvents()
    bubble = Preview()
    for attribute in (Qt.WidgetAttribute.WA_NativeWindow,
                      Qt.WidgetAttribute.WA_PaintOnScreen,
                      Qt.WidgetAttribute.WA_NoSystemBackground):
        bubble.setAttribute(attribute)
    bubble.resize(240, 240)

    def tick(duration):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)

    engine = Engine(int(widget.winId()), 3840, 2160)
    try:
        engine.resize_preview(640, 360)
        engine.configure(camera=camera, microphone="default", desktop_audio=True)
        tick(.3)
        with tempfile.TemporaryDirectory(prefix="glint-smoke-") as directory:
            path = Path(directory) / "capture.mkv"
            engine.start(path)
            tick(1)
            engine.pause(True)
            tick(.2)
            engine.pause(False)
            tick(1)
            print("Live stats:", json.dumps(engine.stats()))
            start = time.monotonic()
            engine.stop()
            assert time.monotonic() - start < 10, "Stop exceeded ten seconds"
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
            video = next(s for s in probe["streams"] if s["codec_type"] == "video")
            assert (video["codec_name"], video["width"], video["height"], video["r_frame_rate"]) == ("h264", 3840, 2160, "30/1")
            assert any(s["codec_name"] == "aac" for s in probe["streams"])
            assert float(probe["format"]["duration"]) > 1
            print("Probe passed:", video["codec_name"], video["width"], video["height"], probe["format"]["duration"])
            # Exercise second recording ownership and stop while paused.
            engine.start(Path(directory) / "paused.mkv")
            tick(.3)
            engine.pause(True)
            engine.stop()
        if camera:
            for shape in ("square", "rounded", "circle"):
                engine.configure(camera=camera, microphone=None, shape=shape)
                tick(.2)
            engine.configure(mode="camera", camera=camera, microphone=None)
            tick(.3)
            bubble.show()
            app.processEvents()
            for shape in ("square", "rounded", "circle"):
                engine.configure(camera=camera, microphone=None, shape=shape, floating_camera=True)
                engine.attach_camera_preview(int(bubble.winId()), 240, 240)
                tick(.3)
                engine.set_screen_zoom(2, 0, 1)
                tick(.1)
                engine.restore_screen_zoom()
                engine.set_camera_preview_enabled(False)
                tick(.1)
                engine.set_camera_preview_enabled(True)
            engine.detach_camera_preview()
            bubble.hide()
        assert not engine.errors, engine.errors
    finally:
        engine.close()
        bubble.close()
        widget.close()
        app.processEvents()
    assert Engine._instance is None
    print("Live smoke passed; temporary recordings deleted.")


if __name__ == "__main__":
    if "--backend-smoke" in sys.argv:
        backend_smoke()
    elif "--window-smoke" in sys.argv:
        window_smoke()
    elif "--preview-smoke" in sys.argv:
        platform = sys.argv[sys.argv.index("--platform") + 1] if "--platform" in sys.argv else "glx"
        preview_smoke(platform)
    elif "--capture" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--capture", action="store_true")
        parser.add_argument("--camera")
        args = parser.parse_args()
        capture_smoke(args.camera)
    else:
        unittest.main()
