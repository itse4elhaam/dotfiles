"""Direct libobs 27 backend for RecIt on Linux/X11.

Create after QApplication and a visible native preview widget. Call public methods
from one controlling thread, never from an OBS callback. Keep the widget alive
until close() finishes. preview_wid=0 disables preview, useful for smoke tests.
configure() is idle-only and activates capture immediately for the live preview.
GLX supports both desktop and window capture. platform="egl" retains the
desktop-only backend for systems without working GLX.
start() writes MKV; the caller owns any later remux. stop() waits up to ten seconds
for OBS, raising rather than freeing resources still owned by a stuck output.

ABI checked against obsproject/obs-studio tag 27.2.3: libobs/obs.h,
libobs/graphics/graphics.h and libobs/media-io/video-io.h. Only OBS 27 is accepted.
"""
from __future__ import annotations

import ctypes as C
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time


class EngineError(RuntimeError):
    """A recoverable setup, capture, or recording failure."""


def screen_transform(canvasw, canvash, sourcew, sourceh, factor, cx, cy):
    """Return top-left x/y and uniform scale, centered on source coordinates.

    Fit the source at 1x. On each axis, keep letterboxing centered until the
    scaled source fills that axis, then clamp panning to its edges.
    """
    values = (canvasw, canvash, sourcew, sourceh, factor, cx, cy)
    if not all(math.isfinite(value) for value in values):
        raise EngineError("Screen dimensions and zoom coordinates must be finite.")
    if min(canvasw, canvash, sourcew, sourceh) <= 0:
        raise EngineError("Screen and canvas dimensions must be positive.")
    factor = max(1.0, min(3.0, factor))
    cx, cy = max(0.0, min(1.0, cx)), max(0.0, min(1.0, cy))
    scale = min(canvasw / sourcew, canvash / sourceh) * factor

    def offset(canvas, extent, center):
        if extent <= canvas:
            return (canvas - extent) / 2
        return max(canvas - extent, min(0.0, canvas / 2 - center * extent))

    return (offset(canvasw, sourcew * scale, cx),
            offset(canvash, sourceh * scale, cy), scale)


P = C.c_void_p
U = C.c_uint32
I = C.c_int
B = C.c_bool
S = C.c_char_p


class _VideoInfo(C.Structure):
    _fields_ = [("graphics_module", S), ("fps_num", U), ("fps_den", U),
                ("base_width", U), ("base_height", U), ("output_width", U),
                ("output_height", U), ("output_format", I), ("adapter", U),
                ("gpu_conversion", B), ("colorspace", I), ("range", I),
                ("scale_type", I)]


class _AudioInfo(C.Structure):
    _fields_ = [("samples_per_sec", U), ("speakers", I)]


class _Window(C.Structure):
    # OBS uses uint32_t, NOT Xlib's unsigned-long Window.
    _fields_ = [("id", U), ("display", P)]


class _DisplayInfo(C.Structure):
    _fields_ = [("window", _Window), ("cx", U), ("cy", U),
                ("num_backbuffers", U), ("format", I), ("zsformat", I),
                ("adapter", U)]


class _Vec2(C.Structure):
    _fields_ = [("x", C.c_float), ("y", C.c_float)]


_Draw = C.CFUNCTYPE(None, P, U, U)
_Signal = C.CFUNCTYPE(None, P, P)


def _bind(lib, name, restype, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = restype, list(args)
    return fn


def _load_obs():
    try:
        lib = C.CDLL("libobs.so.0", mode=C.RTLD_GLOBAL)
    except OSError as exc:
        raise EngineError(f"Cannot load libobs.so.0. Install OBS Studio: {exc}") from exc
    signatures = {
        "obs_get_version": (U,), "obs_get_version_string": (S,),
        "obs_startup": (B, S, S, P), "obs_shutdown": (None,),
        "obs_set_nix_platform": (None, I), "obs_set_nix_platform_display": (None, P),
        "obs_add_data_path": (None, S),
        "obs_reset_video": (I, C.POINTER(_VideoInfo)),
        "obs_reset_audio": (B, C.POINTER(_AudioInfo)),
        "obs_open_module": (I, C.POINTER(P), S, S),
        "obs_init_module": (B, P), "obs_post_load_modules": (None,),
        "obs_enum_encoder_types": (B, C.c_size_t, C.POINTER(S)),
        "obs_enum_source_types": (B, C.c_size_t, C.POINTER(S)),
        "obs_data_create_from_json": (P, S), "obs_data_release": (None, P),
        "obs_source_create": (P, S, S, P, P), "obs_source_release": (None, P),
        "obs_source_get_width": (U, P), "obs_source_get_height": (U, P),
        "obs_source_inc_showing": (None, P), "obs_source_dec_showing": (None, P),
        "obs_source_video_render": (None, P),
        "obs_source_filter_add": (None, P, P),
        "obs_scene_create": (P, S), "obs_scene_release": (None, P),
        "obs_wait_for_destroy_queue": (B,),
        "obs_scene_get_source": (P, P), "obs_scene_add": (P, P, P),
        "obs_sceneitem_set_pos": (None, P, C.POINTER(_Vec2)),
        "obs_sceneitem_set_scale": (None, P, C.POINTER(_Vec2)),
        "obs_sceneitem_set_alignment": (None, P, U),
        "obs_sceneitem_defer_update_begin": (None, P),
        "obs_sceneitem_defer_update_end": (None, P),
        "obs_set_output_source": (None, U, P),
        "obs_display_create": (P, C.POINTER(_DisplayInfo), U),
        "obs_display_destroy": (None, P), "obs_display_resize": (None, P, U, U),
        "obs_display_set_enabled": (None, P, B),
        "obs_display_add_draw_callback": (None, P, _Draw, P),
        "obs_display_remove_draw_callback": (None, P, _Draw, P),
        "obs_render_main_texture": (None,),
        "gs_viewport_push": (None,), "gs_viewport_pop": (None,),
        "gs_projection_push": (None,), "gs_projection_pop": (None,),
        "gs_set_viewport": (None, I, I, I, I),
        "gs_ortho": (None, *([C.c_float] * 6)),
        "obs_get_video": (P,), "obs_get_audio": (P,),
        "obs_video_encoder_create": (P, S, S, P, P),
        "obs_audio_encoder_create": (P, S, S, P, C.c_size_t, P),
        "obs_encoder_set_video": (None, P, P), "obs_encoder_set_audio": (None, P, P),
        "obs_encoder_release": (None, P),
        "obs_output_create": (P, S, S, P, P), "obs_output_release": (None, P),
        "obs_output_set_video_encoder": (None, P, P),
        "obs_output_set_audio_encoder": (None, P, P, C.c_size_t),
        "obs_output_start": (B, P), "obs_output_stop": (None, P),
        "obs_output_force_stop": (None, P), "obs_output_active": (B, P),
        "obs_output_pause": (B, P, B), "obs_output_paused": (B, P),
        "obs_output_get_last_error": (S, P), "obs_output_get_signal_handler": (P, P),
        "obs_output_get_total_bytes": (C.c_uint64, P),
        "obs_output_get_total_frames": (I, P), "obs_output_get_frames_dropped": (I, P),
        "obs_get_total_frames": (U,), "obs_get_lagged_frames": (U,),
        "obs_get_active_fps": (C.c_double,),
        "obs_get_average_frame_time_ns": (C.c_uint64,),
        "signal_handler_connect": (None, P, S, _Signal, P),
        "signal_handler_disconnect": (None, P, S, _Signal, P),
        "calldata_get_data": (B, P, S, P, C.c_size_t),
    }
    for name, sig in signatures.items():
        _bind(lib, name, *sig)
    version = lib.obs_get_version()
    if version >> 24 != 27:
        raise EngineError(f"RecIt requires the OBS 27 ABI; found {lib.obs_get_version_string().decode()}.")
    return lib


class Engine:
    """One engine per process. errors contains asynchronous failures; warnings
    contains nonfatal diagnostics. recording and paused are read-only properties.
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self, preview_wid: int, width: int, height: int, fps: int = 30,
                 *, platform: str = "glx"):
        if platform not in ("glx", "egl"):
            raise EngineError("The graphics platform must be 'glx' or 'egl'.")
        if width < 16 or height < 16 or width % 2 or height % 2 or not 1 <= fps <= 120:
            raise EngineError("Canvas dimensions must be even and at least 16; FPS must be 1–120.")
        if not os.environ.get("DISPLAY"):
            raise EngineError("RecIt requires an X11 session with DISPLAY set.")
        with Engine._instance_lock:
            if Engine._instance is not None:
                raise EngineError("Only one RecIt engine may own libobs in a process.")
            Engine._instance = self
        self.width, self.height, self.fps = width, height, fps
        self.platform = platform
        self._gl = None
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.encoder = ""
        self._obs = None
        self._started_obs = False
        self._closed = False
        self._xdisplay = None
        self._display = None
        self._camera_display = None
        self._camera_source = None  # Owned by _sources, never released separately.
        self._camera_item = None  # Overlay only; borrowed from _scene.
        self._camera_display_size = None
        self._camera_mirror = False
        self._camera_preview_enabled = False
        self._screen_item = None  # Borrowed from _scene.
        self._screen_source = None  # Owned by _sources.
        self._window_id = None
        self._screen_dimensions = None
        self._scene = None
        self._sources = []
        self._output = None
        self._video_encoder = None
        self._audio_encoder = None
        self._stop_event = threading.Event()
        self._started_at = None
        self._paused_at = None
        self._paused_seconds = 0.0
        self._ended_at = None
        self._last_stats = {}
        self._configured = False
        self._mask_dir = tempfile.TemporaryDirectory(prefix="glint-masks-")
        self._draw_callback = _Draw(self._draw)
        self._camera_draw_callback = _Draw(self._draw_camera)
        self._stop_callback = _Signal(self._on_stop)
        try:
            self._obs = _load_obs()
            self._xlib = C.CDLL("libX11.so.6")
            _bind(self._xlib, "XInitThreads", I)()
            _bind(self._xlib, "XOpenDisplay", P, S)
            _bind(self._xlib, "XCloseDisplay", I, P)
            self._xdisplay = self._xlib.XOpenDisplay(None)
            if not self._xdisplay:
                raise EngineError(f"Cannot open X11 display {os.environ['DISPLAY']}.")
            o = self._obs
            if platform == "glx":
                # OBS 27's gladLoadGLX dlcloses libGL after resolving its entry
                # points. Keep a separate reference so those pointers stay valid
                # even when Qt has not already loaded libGL for a native widget.
                # See deps/glad/src/glad_glx.c in obs-studio tag 27.2.3.
                try:
                    self._gl = C.CDLL("libGL.so.1", mode=C.RTLD_GLOBAL)
                except OSError as exc:
                    raise EngineError("Cannot load GLX; use platform='egl' for desktop capture.") from exc
            o.obs_set_nix_platform(0 if platform == "glx" else 1)
            o.obs_set_nix_platform_display(self._xdisplay)
            if not o.obs_startup(b"en-US", None, None):
                raise EngineError("libobs startup failed. See terminal output for details.")
            self._started_obs = True
            o.obs_add_data_path(b"/usr/share/obs/libobs")
            vi = _VideoInfo(b"libobs-opengl.so.0", fps, 1, width, height,
                            width, height, 2, 0, True, 2, 1, 2)
            result = o.obs_reset_video(C.byref(vi))
            if result != 0:
                raise EngineError(f"OBS {platform.upper()} video initialization failed ({result}) "
                                  f"at {width}×{height}/{fps}. "
                                  "Use platform='egl' for desktop capture if GLX is unavailable.")
            if not o.obs_reset_audio(C.byref(_AudioInfo(48000, 2))):
                raise EngineError("OBS could not initialize 48 kHz stereo audio.")
            self._load_modules()
            self.encoders = self._enum(o.obs_enum_encoder_types)
            self.source_types = self._enum(o.obs_enum_source_types)
            if preview_wid:
                # Qt must use a native X11 widget; do not pass a Wayland surface.
                info = _DisplayInfo(_Window(int(preview_wid), self._xdisplay),
                                    width, height, 2, 3, 0, 0)
                self._display = o.obs_display_create(C.byref(info), 0xFF181818)
                if not self._display:
                    raise EngineError("OBS cannot attach its OpenGL preview to this X11 window.")
                o.obs_display_add_draw_callback(self._display, self._draw_callback, None)
        except Exception:
            self.close()
            raise

    def _load_modules(self):
        # Avoid frontend/decklink/VLC plugins and their unrelated dependencies.
        for name in ("linux-capture", "linux-v4l2", "linux-pulseaudio", "obs-filters",
                     "image-source", "obs-ffmpeg", "obs-outputs", "obs-x264"):
            module = P()
            result = self._obs.obs_open_module(C.byref(module),
                f"/usr/lib/x86_64-linux-gnu/obs-plugins/{name}.so".encode(),
                f"/usr/share/obs/obs-plugins/{name}".encode())
            if result != 0 or not self._obs.obs_init_module(module):
                self.warnings.append(f"OBS plugin {name} could not load (code {result}).")
        self._obs.obs_post_load_modules()

    @staticmethod
    def _enum(fn):
        result, i, value = set(), 0, S()
        while fn(i, C.byref(value)):
            result.add(value.value.decode())
            i += 1
        return result

    def _check_open(self):
        if self._closed:
            raise EngineError("This engine has been closed.")

    def _data(self, settings):
        result = self._obs.obs_data_create_from_json(json.dumps(settings).encode())
        if not result:
            raise EngineError("OBS could not allocate settings.")
        return result

    def _source(self, kind, name, settings):
        if kind not in self.source_types:
            raise EngineError(f"Required OBS source '{kind}' is unavailable. Check OBS plugin installation.")
        data = self._data(settings)
        try:
            source = self._obs.obs_source_create(kind.encode(), name.encode(), data, None)
        finally:
            self._obs.obs_data_release(data)
        if not source:
            raise EngineError(f"OBS could not create {name} ({kind}).")
        return source

    def _filter(self, source, kind, name, settings):
        filt = self._source(kind, name, settings)
        try:
            self._obs.obs_source_filter_add(source, filt)
        finally:
            self._obs.obs_source_release(filt)

    def _dimensions(self, source, label, timeout=3.0):
        deadline = time.monotonic() + timeout
        while True:
            w = self._obs.obs_source_get_width(source)
            h = self._obs.obs_source_get_height(source)
            if w and h:
                return w, h
            if time.monotonic() >= deadline:
                raise EngineError(f"{label} supplied no video. Check device access, screen index, or whether another app owns the camera.")
            time.sleep(0.025)

    def _place(self, item, x, y, scale, mirror=False, display_width=0):
        o = self._obs
        o.obs_sceneitem_set_alignment(item, 1 | 4)  # OBS_ALIGN_LEFT | TOP
        o.obs_sceneitem_set_scale(item, C.byref(_Vec2(-scale if mirror else scale, scale)))
        o.obs_sceneitem_set_pos(item, C.byref(_Vec2(x + display_width if mirror else x, y)))

    def _mask(self, shape, mask_path, width, height):
        from PySide6.QtCore import Qt, QRectF
        from PySide6.QtGui import QColor, QImage, QPainter
        if shape == "custom":
            path = Path(mask_path).expanduser() if mask_path else None
            if not path or not path.is_file() or QImage(str(path)).isNull():
                raise EngineError("Custom shape requires a readable image mask.")
            return str(path.resolve())
        path = Path(self._mask_dir.name) / f"{shape}-{width}-{height}.png"
        if not path.exists():
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("white"))
            rect = QRectF(0, 0, width, height)
            if shape == "circle":
                painter.drawEllipse(rect)
            else:
                radius = min(width, height) * 0.16
                painter.drawRoundedRect(rect, radius, radius)
            painter.end()
            if not image.save(str(path)):
                raise EngineError("Could not save the camera mask image.")
        return str(path)

    def configure(self, mode="screen", camera="/dev/video0", microphone="default",
                  desktop_audio=False, shape="circle", mask_path=None, size=.22,
                  position="bottom-right", screen=0, mirror=True, floating_camera=False,
                  window_id: int | None = None):
        """Replace the scene and detach any camera display. Reattach afterward.

        In screen mode floating_camera omits the camera scene item: XShm captures
        its native desktop window once, including any desktop zoom/cropping.
        With window_id, XComposite captures only that window, so the camera is
        always composited. Its mask is mirrored with the image; a custom Qt
        preview silhouette must match that orientation. The caller owns window
        lifetime checks and should stop capture when the selected window closes.
        """
        self._check_open()
        if self._output:
            raise EngineError("Stop the recording before changing the scene.")
        if mode not in ("screen", "camera") or shape not in ("circle", "square", "rounded", "custom"):
            raise EngineError("Unknown recording mode or camera shape.")
        if position not in ("top-left", "top-right", "bottom-left", "bottom-right", "center"):
            raise EngineError("Unknown camera position.")
        if not 0.05 <= size <= 1 or not isinstance(screen, int) or screen < 0:
            raise EngineError("Camera size must be 0.05–1.0 and screen must be a nonnegative index.")
        if mode == "camera" and not camera:
            raise EngineError("Camera mode requires a camera device.")
        if window_id is not None and (type(window_id) is not int or not 0 < window_id <= 0xFFFFFFFF):
            raise EngineError("Window capture requires a nonzero 32-bit X11 window ID.")
        if mode == "screen" and window_id is not None and "xcomposite_input" not in self.source_types:
            raise EngineError("Native window capture is unavailable: OBS 27 requires its GLX backend "
                              "for XComposite. Create Engine with platform='glx'. "
                              "Entire-screen capture remains available.")
        if camera and not os.access(camera, os.R_OK | os.W_OK):
            raise EngineError(f"Camera {camera} is missing or inaccessible.")
        # Release old camera before reopening it: V4L2 streaming is exclusive.
        self._clear_scene()
        o = self._obs
        try:
            self._scene = o.obs_scene_create(b"RecIt scene")
            if not self._scene:
                raise EngineError("OBS could not create the composition scene.")
            o.obs_set_output_source(0, o.obs_scene_get_source(self._scene))
            if mode == "screen":
                if window_id is not None:
                    # OBS 27 xcompcap-main.cpp getWindowFromString accepts a
                    # decimal ID alone, avoiding its title/class fallback.
                    source = self._source("xcomposite_input", "RecIt window", {
                        "capture_window": str(window_id), "show_cursor": True,
                        "include_border": False})
                    self._window_id = window_id
                else:
                    source = self._source("xshm_input", "RecIt screen", {"screen": screen, "show_cursor": True})
                self._sources.append(source)
                self._screen_source = source
                item = o.obs_scene_add(self._scene, source)
                if not item:
                    raise EngineError("OBS could not add the screen to the scene.")
                sw, sh = self._dimensions(source, "Screen capture")
                self._screen_item = item
                self._screen_dimensions = (sw, sh)
                self.restore_screen_zoom()
            if camera:
                source = self._source("v4l2_input", "RecIt camera", {"device_id": camera, "buffering": False})
                self._sources.append(source)
                self._camera_source = source
                self._camera_mirror = bool(mirror)
                item = None
                compose_camera = mode != "screen" or not floating_camera or window_id is not None
                if compose_camera:
                    item = o.obs_scene_add(self._scene, source)
                    if not item:
                        raise EngineError("OBS could not add the camera to the scene.")
                cw, ch = self._dimensions(source, f"Camera {camera}")
                # In camera-only mode fill the canvas. Masks apply to overlays.
                ratio = self.width / self.height if mode == "camera" else 1.0
                crop_w, crop_h = min(cw, round(ch*ratio)), min(ch, round(cw/ratio))
                self._filter(source, "crop_filter", "RecIt camera crop", {
                    "relative": False, "left": (cw-crop_w)//2, "top": (ch-crop_h)//2,
                    "cx": crop_w, "cy": crop_h})
                if mode == "camera":
                    dw, dh, x, y = self.width, self.height, 0, 0
                else:
                    dw = dh = round(min(self.width, self.height) * size)
                    margin = round(min(self.width, self.height) * .025)
                    x = margin if "left" in position else self.width-dw-margin
                    y = margin if "top" in position else self.height-dh-margin
                    if position == "center":
                        x, y = (self.width-dw)/2, (self.height-dh)/2
                    # Desktop floating capture lets Qt own the silhouette.
                    # Window capture excludes that bubble and needs an OBS mask.
                    if shape != "square" and compose_camera:
                        path = self._mask(shape, mask_path, crop_w, crop_h)
                        self._filter(source, "mask_filter_v2", "RecIt image mask", {
                            "image_path": path, "type": "mask_alpha_filter.effect",
                            "opacity": 1.0, "color": 0xFFFFFF, "stretch": True})
                if item:
                    self._place(item, x, y, dw/crop_w, mirror, dw)
                    if mode == "screen":
                        self._camera_item = item
                        self._camera_display_size = (dw, dh)
            if microphone:
                source = self._source("pulse_input_capture", "RecIt microphone", {"device_id": microphone})
                self._sources.append(source)
                o.obs_set_output_source(1, source)
            if desktop_audio:
                source = self._source("pulse_output_capture", "RecIt desktop audio", {"device_id": "default"})
                self._sources.append(source)
                o.obs_set_output_source(2, source)
            self._configured = True
        except Exception as exc:
            self._clear_scene()
            self.errors.append(str(exc))
            raise

    def _clear_scene(self):
        self.detach_camera_preview()
        self._camera_source = None
        self._camera_item = None
        self._camera_display_size = None
        self._camera_mirror = False
        self._screen_item = None
        self._screen_source = None
        self._window_id = None
        self._screen_dimensions = None
        if not self._started_obs:
            return
        self._configured = False
        for channel in range(3):
            self._obs.obs_set_output_source(channel, None)
        if self._scene:
            self._obs.obs_scene_release(self._scene)
            self._scene = None
        for source in self._sources:
            self._obs.obs_source_release(source)
        self._sources.clear()
        # Source destruction is deferred in libobs. Drain it before reopening
        # V4L2, otherwise the previous source can still own its streaming buffers.
        self._obs.obs_wait_for_destroy_queue()

    def _draw(self, _param, cx, cy):
        if not cx or not cy:
            return
        o = self._obs
        scale = min(cx/self.width, cy/self.height)
        w, h = max(1, round(self.width*scale)), max(1, round(self.height*scale))
        o.gs_viewport_push()
        o.gs_projection_push()
        try:
            o.gs_set_viewport((cx-w)//2, (cy-h)//2, w, h)
            o.gs_ortho(0, self.width, 0, self.height, -100, 100)
            o.obs_render_main_texture()
        finally:
            o.gs_projection_pop()
            o.gs_viewport_pop()

    def resize_preview(self, w, h):
        self._check_open()
        if self._display and w > 0 and h > 0:
            self._obs.obs_display_resize(self._display, int(w), int(h))

    def attach_camera_preview(self, wid: int, width: int, height: int):
        """Draw the existing filtered camera in a visible native X11 widget.

        Keep this widget alive until detach or close. OBS owns an opaque swap
        chain; the caller must shape the top-level window for rounded edges.
        This replaces any previous camera display and starts it enabled.
        """
        self._check_open()
        if not self._camera_source:
            raise EngineError("Configure a camera before attaching its preview.")
        if (not isinstance(wid, int) or not 0 < wid <= 0xFFFFFFFF or
                not isinstance(width, int) or not 0 < width <= 0x7FFFFFFF or
                not isinstance(height, int) or not 0 < height <= 0x7FFFFFFF):
            raise EngineError("Camera preview requires a native X11 window ID and positive integer dimensions.")
        self.detach_camera_preview()
        o = self._obs
        info = _DisplayInfo(_Window(wid, self._xdisplay), width, height, 2, 3, 0, 0)
        self._camera_display = o.obs_display_create(C.byref(info), 0xFF000000)
        if not self._camera_display:
            raise EngineError("OBS cannot attach the camera preview. Use a visible native X11 widget and keep it alive until detach.")
        o.obs_display_set_enabled(self._camera_display, False)
        o.obs_display_add_draw_callback(self._camera_display, self._camera_draw_callback, None)
        self.set_camera_preview_enabled(True)

    def detach_camera_preview(self):
        """Synchronize with the render callback before releasing its source."""
        if not self._camera_display:
            return
        o = self._obs
        o.obs_display_set_enabled(self._camera_display, False)
        # remove_draw_callback waits for an in-flight draw under OBS's mutex.
        # Keep the callback and camera source alive until that completes.
        o.obs_display_remove_draw_callback(self._camera_display, self._camera_draw_callback, None)
        o.obs_display_destroy(self._camera_display)
        self._camera_display = None
        if self._camera_preview_enabled:
            o.obs_source_dec_showing(self._camera_source)
        self._camera_preview_enabled = False

    def set_camera_preview_enabled(self, enabled: bool):
        """Suspend the hidden display and balance its source showing count."""
        self._check_open()
        enabled = bool(enabled)
        if not self._camera_display or enabled == self._camera_preview_enabled:
            return
        o = self._obs
        if enabled:
            o.obs_source_inc_showing(self._camera_source)
            self._camera_preview_enabled = True
            o.obs_display_set_enabled(self._camera_display, True)
        else:
            o.obs_display_set_enabled(self._camera_display, False)
            self._camera_preview_enabled = False
            o.obs_source_dec_showing(self._camera_source)

    def _draw_camera(self, _param, cx, cy):
        source = self._camera_source
        if not source or not self._camera_preview_enabled or not cx or not cy:
            return
        o = self._obs
        sw, sh = o.obs_source_get_width(source), o.obs_source_get_height(source)
        if not sw or not sh:
            return
        scale = min(cx / sw, cy / sh)
        w, h = max(1, round(sw * scale)), max(1, round(sh * scale))
        o.gs_viewport_push()
        o.gs_projection_push()
        try:
            o.gs_set_viewport((cx - w) // 2, (cy - h) // 2, w, h)
            o.gs_ortho(sw if self._camera_mirror else 0,
                       0 if self._camera_mirror else sw, 0, sh, -100, 100)
            o.obs_source_video_render(source)
        finally:
            o.gs_projection_pop()
            o.gs_viewport_pop()

    def set_camera_position(self, x: float, y: float):
        """Move a composited overlay within its available canvas travel area.

        Coordinates are clamped to 0–1: (0, 0) is top-left and (1, 1) is
        bottom-right with the whole overlay visible. No-op for camera-only
        mode or a desktop floating camera that has no composited scene item.
        """
        self._check_open()
        if not all(math.isfinite(value) for value in (x, y)):
            raise EngineError("Camera coordinates must be finite.")
        if not self._camera_item:
            return
        dw, dh = self._camera_display_size
        source_width = self._obs.obs_source_get_width(self._camera_source)
        if not source_width:
            return
        o = self._obs
        o.obs_sceneitem_defer_update_begin(self._camera_item)
        try:
            self._place(self._camera_item,
                max(0.0, min(1.0, x)) * (self.width - dw),
                max(0.0, min(1.0, y)) * (self.height - dh),
                dw / source_width, self._camera_mirror, dw)
        finally:
            o.obs_sceneitem_defer_update_end(self._camera_item)

    def window_dimensions(self) -> tuple[int, int] | None:
        """Current OBS window content size, or None for desktop/camera capture.

        Zero dimensions can occur during resize or loss; this is not an X11
        window-liveness check. Read on the controlling thread, like zoom updates.
        """
        self._check_open()
        if self._window_id is None or not self._screen_source:
            return None
        return (self._obs.obs_source_get_width(self._screen_source),
                self._obs.obs_source_get_height(self._screen_source))

    def set_screen_zoom(self, factor: float, center_x: float, center_y: float):
        """Set 1–3x desktop/window zoom around normalized source coordinates.

        Safe in screen preview or recording; a no-op in camera-only mode.
        Only scene-item transforms change. Smoothing belongs to the caller.
        """
        self._check_open()
        if not self._screen_item:
            return
        dimensions = self.window_dimensions()
        if dimensions and all(dimensions):
            self._screen_dimensions = dimensions
        x, y, scale = screen_transform(self.width, self.height,
            *self._screen_dimensions, factor, center_x, center_y)
        o = self._obs
        o.obs_sceneitem_defer_update_begin(self._screen_item)
        try:
            self._place(self._screen_item, x, y, scale)
        finally:
            o.obs_sceneitem_defer_update_end(self._screen_item)

    def restore_screen_zoom(self):
        """Restore aspect-fit capture framing. stop() leaves framing unchanged."""
        self.set_screen_zoom(1.0, .5, .5)

    def _create_recording(self, path, encoder_id):
        o = self._obs
        bitrate = max(6000, round(self.width*self.height*self.fps / 10000))
        settings = {"bitrate": bitrate, "keyint_sec": 2, "rate_control": "CBR"}
        if encoder_id == "ffmpeg_vaapi":
            settings.update(vaapi_device="/dev/dri/renderD128", vaapi_codec=27,
                            profile=100, level=52, bf=0)
        else:
            settings.update(preset="veryfast", profile="high")
        data = self._data(settings)
        try:
            self._video_encoder = o.obs_video_encoder_create(encoder_id.encode(), b"RecIt H264", data, None)
        finally:
            o.obs_data_release(data)
        if not self._video_encoder:
            raise EngineError(f"Could not create {encoder_id} video encoder.")
        o.obs_encoder_set_video(self._video_encoder, o.obs_get_video())
        if "ffmpeg_aac" not in self.encoders:
            raise EngineError("The OBS FFmpeg AAC encoder is unavailable.")
        data = self._data({"bitrate": 160})
        try:
            self._audio_encoder = o.obs_audio_encoder_create(b"ffmpeg_aac", b"RecIt AAC", data, 0, None)
        finally:
            o.obs_data_release(data)
        if not self._audio_encoder:
            raise EngineError("Could not create the AAC audio encoder.")
        o.obs_encoder_set_audio(self._audio_encoder, o.obs_get_audio())
        data = self._data({"path": str(path)})
        try:
            self._output = o.obs_output_create(b"ffmpeg_muxer", b"RecIt recording", data, None)
        finally:
            o.obs_data_release(data)
        if not self._output:
            raise EngineError("The OBS FFmpeg recording output is unavailable.")
        o.obs_output_set_video_encoder(self._output, self._video_encoder)
        o.obs_output_set_audio_encoder(self._output, self._audio_encoder, 0)
        self._stop_event.clear()
        signal = o.obs_output_get_signal_handler(self._output)
        o.signal_handler_connect(signal, b"stop", self._stop_callback, None)
        if not o.obs_output_start(self._output):
            detail = o.obs_output_get_last_error(self._output)
            raise EngineError(f"{encoder_id} could not start recording: " +
                              (detail.decode(errors="replace") if detail else "check encoder/device permissions and the OBS terminal log."))
        self.encoder = encoder_id

    def start(self, path: Path) -> None:
        self._check_open()
        if self._output:
            raise EngineError("A recording already exists; stop it before starting another.")
        if not self._configured:
            raise EngineError("Configure a scene before recording.")
        path = Path(path).expanduser().absolute()
        if path.suffix.lower() != ".mkv":
            raise EngineError("Record to an .mkv path; remux to MP4 after stop().")
        if path.exists():
            raise EngineError(f"Refusing to overwrite {path}.")
        if not path.parent.is_dir() or not os.access(path.parent, os.W_OK):
            raise EngineError(f"Recording directory is missing or not writable: {path.parent}")
        candidates = []
        if "ffmpeg_vaapi" in self.encoders and os.access("/dev/dri/renderD128", os.R_OK | os.W_OK):
            candidates.append("ffmpeg_vaapi")
        if "obs_x264" in self.encoders:
            candidates.append("obs_x264")
        if not candidates:
            raise EngineError("No usable H.264 encoder. Install obs-ffmpeg/obs-x264 and grant access to /dev/dri/renderD128.")
        failures = []
        for candidate in candidates:
            try:
                self._create_recording(path, candidate)
                break
            except EngineError as exc:
                failures.append(str(exc))
                self._release_recording()
        else:
            message = "\n".join(failures)
            self.errors.append(message)
            raise EngineError(message)
        if candidate != "ffmpeg_vaapi":
            self.warnings.append("Hardware recording is unavailable; using CPU x264. " + " ".join(failures))
        self._started_at = time.monotonic()
        self._ended_at = None
        self._paused_at = None
        self._paused_seconds = 0.0
        self._last_stats = {}
        self._frame_baseline = self._obs.obs_get_total_frames()
        self._lag_baseline = self._obs.obs_get_lagged_frames()

    def _on_stop(self, _param, data):
        code = C.c_longlong()
        self._obs.calldata_get_data(data, b"code", C.byref(code), C.sizeof(code))
        self._ended_at = time.monotonic()
        if code.value:
            detail = self._obs.obs_output_get_last_error(self._output) if self._output else None
            self.errors.append(f"Recording stopped with OBS error {code.value}: " +
                (detail.decode(errors="replace") if detail else "check disk space and encoder output."))
        self._stop_event.set()

    @property
    def recording(self):
        return bool(self._output and self._obs.obs_output_active(self._output))

    @property
    def paused(self):
        return bool(self._output and self._obs.obs_output_paused(self._output))

    def pause(self, paused: bool):
        self._check_open()
        if not self.recording:
            raise EngineError("There is no active recording to pause.")
        if self.paused == bool(paused):
            return
        if not self._obs.obs_output_pause(self._output, bool(paused)):
            raise EngineError("OBS could not change the recording pause state.")
        now = time.monotonic()
        if paused:
            self._paused_at = now
        elif self._paused_at is not None:
            self._paused_seconds += now-self._paused_at
            self._paused_at = None

    def stats(self) -> dict:
        result = dict(self._last_stats)
        now = self._ended_at or time.monotonic()
        elapsed = 0.0 if self._started_at is None else max(0.0,
            now-self._started_at-self._paused_seconds-
            (max(0.0, now-self._paused_at) if self._paused_at is not None else 0.0))
        result.update(elapsed=elapsed, recording=self.recording, paused=self.paused,
                      encoder=self.encoder, errors=list(self.errors), warnings=list(self.warnings))
        if self._started_obs and not self._closed:
            o = self._obs
            result.update(fps=o.obs_get_active_fps(), render_ms=o.obs_get_average_frame_time_ns()/1e6,
                rendered_frames=max(0, o.obs_get_total_frames()-getattr(self, "_frame_baseline", 0)),
                lagged_frames=max(0, o.obs_get_lagged_frames()-getattr(self, "_lag_baseline", 0)))
        if self._output:
            result.update(frames=self._obs.obs_output_get_total_frames(self._output),
                dropped=self._obs.obs_output_get_frames_dropped(self._output),
                bytes=self._obs.obs_output_get_total_bytes(self._output))
        for key in ("frames", "dropped", "bytes"):
            result.setdefault(key, 0)
        return result

    def stop(self) -> None:
        if not self._output:
            return
        o = self._obs
        deadline = time.monotonic() + 10.0
        if self.paused:
            # OBS 27 can stall its interleaver if pause and the implicit resume
            # in obs_output_stop land on the same video timestamp. Allow both
            # transitions to cross a frame boundary before asking the muxer
            # to drain. This also closes our elapsed-time pause interval.
            since_pause = time.monotonic() - (self._paused_at or 0)
            time.sleep(max(0, 2 / self.fps - since_pause))
            self.pause(False)
            time.sleep(2 / self.fps)
        if not self._stop_event.is_set():
            o.obs_output_stop(self._output)
            if not self._stop_event.wait(max(0, deadline-time.monotonic()-2)):
                o.obs_output_force_stop(self._output)
                if not self._stop_event.wait(max(0, deadline-time.monotonic())):
                    message = "OBS did not finish stopping within 10 seconds; output retained to avoid unsafe teardown. Retry stop()."
                    self.errors.append(message)
                    raise EngineError(message)
        self._ended_at = self._ended_at or time.monotonic()
        self._last_stats = self.stats()
        self._release_recording()

    def _release_recording(self):
        o = self._obs
        if self._output:
            signal = o.obs_output_get_signal_handler(self._output)
            o.signal_handler_disconnect(signal, b"stop", self._stop_callback, None)
            o.obs_output_release(self._output)
            self._output = None
        for attr in ("_video_encoder", "_audio_encoder"):
            encoder = getattr(self, attr)
            if encoder:
                o.obs_encoder_release(encoder)
                setattr(self, attr, None)

    def close(self):
        if self._closed:
            return
        self.stop()
        if self._display:
            self._obs.obs_display_remove_draw_callback(self._display, self._draw_callback, None)
            self._obs.obs_display_destroy(self._display)
            self._display = None
        self._clear_scene()
        if self._started_obs:
            self._obs.obs_shutdown()
            self._started_obs = False
        if self._xdisplay:
            self._xlib.XCloseDisplay(self._xdisplay)
            self._xdisplay = None
        self._mask_dir.cleanup()
        self._closed = True
        with Engine._instance_lock:
            if Engine._instance is self:
                Engine._instance = None
