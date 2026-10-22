"""Microphone filtering checks with mocked OBS and optional native silent frames.

Never starts OBS, opens audio devices, or captures the desktop.
"""
import ctypes as C
import math
from pathlib import Path
import unittest
from unittest.mock import Mock, call

from engine import Engine, EngineError


class MicrophoneFilterTests(unittest.TestCase):
    def setUp(self):
        self.engine = e = Engine.__new__(Engine)
        e._obs = self.obs = Mock()
        e.warnings = []
        e.source_types = {"noise_suppress_filter_v2", "noise_suppress_filter", "limiter_filter"}
        self.methods = {101: [(b"speex", False), (b"rnnoise", False)],
                        201: [(b"speex", False), (b"rnnoise", False)]}
        self.obs.obs_get_source_properties.side_effect = lambda kind: 101 if kind.endswith(b"_v2") else 201
        self.obs.obs_properties_get.side_effect = lambda props, key: props if key == b"method" else None
        self.obs.obs_property_list_item_count.side_effect = lambda prop: len(self.methods[prop])
        self.obs.obs_property_list_item_string.side_effect = lambda prop, index: self.methods[prop][index][0]
        self.obs.obs_property_list_item_disabled.side_effect = lambda prop, index: self.methods[prop][index][1]

    def test_prefers_versioned_rnnoise_and_frees_properties(self):
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter_v2", "rnnoise"))
        self.obs.obs_properties_destroy.assert_called_once_with(101)
        self.obs.obs_get_source_defaults.assert_not_called()

    def test_generic_filter_id_does_not_prove_rnnoise(self):
        self.methods = {101: [(b"speex", False)], 201: [(b"speex", False)]}
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter_v2", "speex"))
        self.assertEqual(self.obs.obs_properties_destroy.call_args_list, [call(101), call(201)])

    def test_rnnoise_on_older_filter_beats_speex_on_newer_filter(self):
        self.methods[101] = [(b"speex", False)]
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter", "rnnoise"))

    def test_disabled_backends_are_not_selected(self):
        self.methods = {101: [(b"rnnoise", True), (b"speex", False)],
                        201: [(b"rnnoise", True), (b"speex", True)]}
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter_v2", "speex"))

    def test_unknown_or_empty_method_lists_do_not_guess(self):
        self.methods = {101: [(b"nvafx", False)], 201: []}
        self.assertIsNone(self.engine._microphone_noise_backend())

    def test_single_backend_build_uses_default_and_releases_settings(self):
        self.engine.source_types = {"noise_suppress_filter_v2"}
        self.obs.obs_properties_get.side_effect = lambda props, key: None
        self.obs.obs_get_source_defaults.return_value = 301
        self.obs.obs_data_get_string.return_value = b"rnnoise"
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter_v2", "rnnoise"))
        self.obs.obs_data_release.assert_called_once_with(301)
        self.obs.obs_properties_destroy.assert_called_once_with(101)

    def test_single_speex_backend_requires_its_compiled_property(self):
        self.engine.source_types = {"noise_suppress_filter_v2"}
        self.obs.obs_get_source_defaults.return_value = 301
        self.obs.obs_data_get_string.return_value = b"speex"
        self.obs.obs_properties_get.side_effect = lambda props, key: 401 if key == b"suppress_level" else None
        self.assertEqual(self.engine._microphone_noise_backend(), ("noise_suppress_filter_v2", "speex"))
        self.obs.obs_properties_get.side_effect = lambda props, key: None
        self.assertIsNone(self.engine._microphone_noise_backend())

    def test_unavailable_properties_or_defaults_are_safe(self):
        self.obs.obs_get_source_properties.side_effect = None
        self.obs.obs_get_source_properties.return_value = None
        self.assertIsNone(self.engine._microphone_noise_backend())
        self.obs.obs_properties_destroy.assert_not_called()
        self.obs.obs_get_source_properties.return_value = 101
        self.obs.obs_properties_get.side_effect = lambda props, key: None
        self.obs.obs_get_source_defaults.return_value = None
        self.assertIsNone(self.engine._microphone_noise_backend())
        self.assertEqual(self.obs.obs_properties_destroy.call_count, 2)

    def test_no_registered_noise_filter_does_not_probe_obs(self):
        self.engine.source_types = {"limiter_filter"}
        self.assertIsNone(self.engine._microphone_noise_backend())
        self.obs.obs_get_source_properties.assert_not_called()

    def test_filter_settings_order_and_reference_ownership(self):
        e = self.engine
        settings = []
        e._data = Mock(side_effect=lambda value: settings.append(value) or len(settings))
        self.obs.obs_source_create.side_effect = [501, 502]
        e._microphone_filters(99)
        self.assertEqual(settings, [{"method": "rnnoise"}, {"threshold": -3.0, "release_time": 60}])
        self.assertEqual([c.args[0] for c in self.obs.obs_source_create.call_args_list],
                         [b"noise_suppress_filter_v2", b"limiter_filter"])
        self.assertEqual(self.obs.obs_source_filter_add.call_args_list, [call(99, 501), call(99, 502)])
        self.assertEqual(self.obs.obs_source_release.call_args_list, [call(501), call(502)])
        self.assertEqual(e.warnings, [])

    def test_speex_fallback_is_gentle_and_explicit(self):
        self.methods = {101: [(b"speex", False)], 201: []}
        self.engine._filter = Mock()
        self.engine._microphone_filters(99)
        self.assertEqual(self.engine._filter.call_args_list[0].args[3],
                         {"method": "speex", "suppress_level": -15})
        self.assertIn("RNNoise is unavailable", " ".join(self.engine.warnings))

    def test_missing_suppression_keeps_limiter_and_reports_noise_unchanged(self):
        self.engine.source_types = {"limiter_filter"}
        self.engine._filter = Mock()
        self.engine._microphone_filters(99)
        self.assertEqual([c.args[1] for c in self.engine._filter.call_args_list], ["limiter_filter"])
        self.assertIn("noise is unchanged", " ".join(self.engine.warnings))

    def test_failed_noise_filter_still_attempts_limiter(self):
        self.engine._filter = Mock(side_effect=[EngineError("allocation failed"), None])
        self.engine._microphone_filters(99)
        self.assertEqual(self.engine._filter.call_count, 2)
        self.assertEqual(self.engine._filter.call_args.args[1], "limiter_filter")
        self.assertIn("continuing without it", " ".join(self.engine.warnings))

    def test_missing_optional_filters_leave_audio_connected(self):
        self.engine.source_types = set()
        self.engine._microphone_filters(99)
        self.obs.obs_source_filter_add.assert_not_called()
        self.assertTrue(any("peak limiter is unavailable" in warning for warning in self.engine.warnings))

    def test_bypass_does_not_probe_or_attach_any_processing(self):
        self.engine._filter = Mock()
        self.engine._microphone_filters(99, False)
        self.obs.obs_get_source_properties.assert_not_called()
        self.engine._filter.assert_not_called()
        self.assertEqual(self.engine.warnings, [])


class MicrophoneRoutingTests(unittest.TestCase):
    def setUp(self):
        self.engine = e = Engine.__new__(Engine)
        e._obs = Mock()
        e._closed, e._output = False, None
        e._sources, e.errors, e.warnings = [], [], []
        e.width, e.height = 1920, 1080
        e._clear_scene = Mock()
        e._dimensions = Mock(return_value=(1920, 1080))
        e.restore_screen_zoom = Mock()
        e._source = Mock(side_effect=lambda kind, name, settings: {
            "xshm_input": 10, "pulse_input_capture": 20, "pulse_output_capture": 30}[kind])
        e._microphone_filters = Mock()

    def test_only_selected_microphone_gets_filters(self):
        self.engine.configure(camera=None, microphone="fake-mic", desktop_audio=True)
        self.engine._microphone_filters.assert_called_once_with(20, True)
        self.assertEqual(self.engine._source.call_args_list[-2:], [
            call("pulse_input_capture", "RecIt microphone", {"device_id": "fake-mic"}),
            call("pulse_output_capture", "RecIt desktop audio", {"device_id": "default"})])
        self.engine._obs.obs_set_output_source.assert_has_calls([call(1, 20), call(2, 30)])

    def test_microphone_off_does_not_process_desktop_audio(self):
        self.engine.configure(camera=None, microphone=None, desktop_audio=True)
        self.engine._microphone_filters.assert_not_called()
        self.assertEqual([c.args[0] for c in self.engine._source.call_args_list],
                         ["xshm_input", "pulse_output_capture"])

    def test_processing_off_preserves_microphone_routing(self):
        self.engine.configure(camera=None, microphone="fake-mic", microphone_processing=False)
        self.engine._microphone_filters.assert_called_once_with(20, False)
        self.engine._obs.obs_set_output_source.assert_any_call(1, 20)

    def test_reconfigure_clears_old_audio_warnings_and_preserves_other_diagnostics(self):
        for microphone in (None, "fake-mic"):
            with self.subTest(microphone=microphone):
                self.engine.warnings = ["Microphone processing: old fallback", "OBS plugin warning"]
                self.engine.configure(camera=None, microphone=microphone, microphone_processing=False)
                self.assertEqual(self.engine.warnings, ["OBS plugin warning"])

    def test_invalid_processing_option_keeps_existing_scene(self):
        with self.assertRaisesRegex(EngineError, "enabled or disabled"):
            self.engine.configure(camera=None, microphone_processing="false")
        self.engine._clear_scene.assert_not_called()
        self.engine._source.assert_not_called()


class InstalledRNNoiseTests(unittest.TestCase):
    def test_bundled_backend_processes_synthetic_silence_without_obs_startup(self):
        plugin_path = Path("/usr/lib/x86_64-linux-gnu/obs-plugins/obs-filters.so")
        if not plugin_path.is_file():
            self.skipTest("Installed OBS filter plugin is unavailable; mocked fallback checks still run.")
        try:
            plugin = C.CDLL(str(plugin_path))
            create, process, destroy = plugin.rnnoise_create, plugin.rnnoise_process_frame, plugin.rnnoise_destroy
        except (OSError, AttributeError) as exc:
            self.skipTest(f"Bundled RNNoise symbols unavailable: {exc}")
        create.restype, create.argtypes = C.c_void_p, [C.c_void_p]
        process.restype, process.argtypes = C.c_float, [C.c_void_p, C.POINTER(C.c_float), C.POINTER(C.c_float)]
        destroy.restype, destroy.argtypes = None, [C.c_void_p]
        state = create(None)
        self.assertTrue(state, "RNNoise could not allocate a denoiser.")
        try:
            silence, output = (C.c_float * 480)(), (C.c_float * 480)()
            for _ in range(20):
                probability = process(state, output, silence)
                self.assertTrue(math.isfinite(probability))
                self.assertTrue(all(math.isfinite(sample) and abs(sample) < 1e-6 for sample in output))
        finally:
            destroy(state)


if __name__ == "__main__":
    unittest.main()
