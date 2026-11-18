import os
import sys
import tempfile
import uuid
import shutil
import ctypes
from ctypes import wintypes
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl, Qt, QTimer

# Standard Windows & COM definitions
HRESULT = ctypes.c_long
HWND = wintypes.HWND

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8)
    ]

# COM IUnknown method prototypes
QI_FUNC = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
ADDREF_FUNC = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
RELEASE_FUNC = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)

def _dummy_qi(this, riid, ppv):
    if not ppv:
        return -2147467261  # E_POINTER
    ppv[0] = this
    return 0  # S_OK

def _dummy_addref(this):
    return 1

def _dummy_release(this):
    return 1

c_qi = QI_FUNC(_dummy_qi)
c_addref = ADDREF_FUNC(_dummy_addref)
c_release = RELEASE_FUNC(_dummy_release)

# 1. Environment Completed Handler
ENV_INVOKE_FUNC = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, HRESULT, ctypes.c_void_p)
class EnvCompletedHandlerVtbl(ctypes.Structure):
    _fields_ = [('QI', QI_FUNC), ('AddRef', ADDREF_FUNC), ('Release', RELEASE_FUNC), ('Invoke', ENV_INVOKE_FUNC)]
class EnvCompletedHandler(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(EnvCompletedHandlerVtbl))]

# 2. Controller Completed Handler
CTRL_INVOKE_FUNC = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, HRESULT, ctypes.c_void_p)
class CtrlCompletedHandlerVtbl(ctypes.Structure):
    _fields_ = [('QI', QI_FUNC), ('AddRef', ADDREF_FUNC), ('Release', RELEASE_FUNC), ('Invoke', CTRL_INVOKE_FUNC)]
class CtrlCompletedHandler(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(CtrlCompletedHandlerVtbl))]

# 3. Navigation Completed Handler
NAV_INVOKE_FUNC = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
class NavCompletedHandlerVtbl(ctypes.Structure):
    _fields_ = [('QI', QI_FUNC), ('AddRef', ADDREF_FUNC), ('Release', RELEASE_FUNC), ('Invoke', NAV_INVOKE_FUNC)]
class NavCompletedHandler(ctypes.Structure):
    _fields_ = [('lpVtbl', ctypes.POINTER(NavCompletedHandlerVtbl))]

# VTable function prototypes:
# ICoreWebView2Environment:
# [1] AddRef
AddRef_FuncType = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
# [2] Release
Release_FuncType = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
# [3] CreateCoreWebView2Controller(this, HWND parentWindow, ICoreWebView2CreateCoreWebView2ControllerCompletedHandler* handler)
CreateCtrl_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, HWND, ctypes.c_void_p)

# ICoreWebView2Controller:
# [3] get_IsVisible
GetIsVisible_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL))
# [4] put_IsVisible(this, BOOL isVisible)
PutIsVisible_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, wintypes.BOOL)
# [6] put_Bounds(this, RECT bounds)
PutBounds_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, RECT)
# [23] NotifyParentWindowPositionChanged
NotifyPos_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p)
# [24] Close(this)
CloseCtrl_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p)
# [25] get_CoreWebView2(this, ICoreWebView2** coreWebView2)
GetCore_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))

# ICoreWebView2:
# [3] get_Settings(this, ICoreWebView2Settings** settings)
GetSettings_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
# [4] get_Source
GetSource_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR))
# [5] Navigate(this, LPCWSTR uri)
Navigate_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_wchar_p)
# [15] add_NavigationCompleted
AddNavCompleted_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64))

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8)
    ]

# IID_ICoreWebView2Settings7: {488dc902-35ef-42d2-bc7d-94b65c4bc49c}
IID_ICoreWebView2Settings7 = GUID(
    0x488dc902, 0x35ef, 0x42d2,
    (ctypes.c_ubyte * 8)(0xbc, 0x7d, 0x94, 0xb6, 0x5c, 0x4b, 0xc4, 0x9c)
)
QI_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
PutHiddenPdf_FuncType = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_uint32)


_loader_dll = None

def get_webview2_loader():
    global _loader_dll
    if _loader_dll is not None:
        return _loader_dll
    
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources", "bin", "WebView2Loader.dll"),
        os.path.abspath(os.path.join("resources", "bin", "WebView2Loader.dll"))
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.insert(0, os.path.join(sys._MEIPASS, "resources", "bin", "WebView2Loader.dll"))
        
    for p in candidates:
        if os.path.exists(p):
            try:
                _loader_dll = ctypes.windll.LoadLibrary(p)
                return _loader_dll
            except Exception:
                pass
                
    try:
        _loader_dll = ctypes.windll.LoadLibrary("WebView2Loader.dll")
        return _loader_dll
    except Exception:
        return None


def is_webview2_available():
    loader = get_webview2_loader()
    if not loader or not hasattr(loader, "GetAvailableCoreWebView2BrowserVersionString"):
        return False
    try:
        GetVersion = loader.GetAvailableCoreWebView2BrowserVersionString
        GetVersion.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.LPWSTR)]
        GetVersion.restype = HRESULT
        ver_ptr = wintypes.LPWSTR()
        hr = GetVersion(None, ctypes.byref(ver_ptr))
        if hr == 0 and ver_ptr.value:
            ctypes.windll.ole32.CoTaskMemFree(ver_ptr)
            return True
        return False
    except Exception:
        return False


class EdgePdfPreviewHost(QWidget):
    pdf_loaded_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow, True)
        self.hide()

        self.env = None
        self.controller = None
        self.core_webview = None
        self.is_initialized = False
        self.is_initializing = False
        self.is_available = is_webview2_available()

        self.pending_pdf_path = None
        self.current_pdf_path = None
        self._nav_seq = 0
        self.last_rect = (0, 0, 0, 0)
        self._should_be_visible = False
        self._user_data_dir = os.path.abspath(os.path.join(tempfile.gettempdir(), f"quast_wv2_{uuid.uuid4().hex[:8]}"))
        self._com_refs = []  # Keep references alive to avoid GC

        if self.is_available:
            try:
                ctypes.windll.ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
            except Exception:
                pass
            # Start background initialization immediately
            QTimer.singleShot(0, self._start_init_webview)

    def _start_init_webview(self):
        if self.is_initialized or self.is_initializing or not self.is_available:
            return
        self.is_initializing = True

        loader = get_webview2_loader()
        if not loader:
            self.is_available = False
            self.is_initializing = False
            return

        # Enable Chromium/Edge PDF Engine without Adobe promotional bars
        existing_args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
        features_flag = "--enable-features=msEdgePdfOOPViewer,PdfOopif,PdfUseSkiaRenderer --disable-features=PdfAcrobat --no-first-run --disable-background-timer-throttling"
        if features_flag not in existing_args:
            os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"{existing_args} {features_flag}".strip()

        hwnd = int(self.winId())

        # Handler for NavigationCompleted
        def on_nav_completed(this, sender, args):
            if self.current_pdf_path and self._should_be_visible:
                self.pdf_loaded_signal.emit(self.current_pdf_path)
            return 0

        c_nav_invoke = NAV_INVOKE_FUNC(on_nav_completed)
        nav_vtbl = NavCompletedHandlerVtbl(c_qi, c_addref, c_release, c_nav_invoke)
        nav_h = NavCompletedHandler(ctypes.pointer(nav_vtbl))
        self._com_refs.extend([c_nav_invoke, nav_vtbl, nav_h])

        # Handler for CreateCoreWebView2ControllerCompleted
        def on_controller_created(this, hr, created_controller):
            self.is_initializing = False
            if hr != 0 or not created_controller:
                self.error_signal.emit(f"Failed to create WebView2 controller (HRESULT: {hex(hr & 0xFFFFFFFF)})")
                return 0

            self.controller = created_controller
            p_ctrl_vt = ctypes.cast(created_controller, ctypes.POINTER(ctypes.c_void_p))[0]
            ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
            
            # AddRef controller to maintain strong lifetime
            AddRef_FuncType(ctrl_methods[1])(created_controller)

            # Get CoreWebView2
            core_ptr = ctypes.c_void_p()
            hr_core = GetCore_FuncType(ctrl_methods[25])(created_controller, ctypes.byref(core_ptr))
            if hr_core == 0 and core_ptr.value:
                self.core_webview = core_ptr.value
                p_core_vt = ctypes.cast(self.core_webview, ctypes.POINTER(ctypes.c_void_p))[0]
                core_methods = ctypes.cast(p_core_vt, ctypes.POINTER(ctypes.c_void_p))
                
                # AddRef core
                AddRef_FuncType(core_methods[1])(self.core_webview)

                # Configure Settings to hide all PDF toolbar buttons (print, save, zoom, rotate, search, page selector, more, etc.)
                try:
                    settings_ptr = ctypes.c_void_p()
                    hr_set = GetSettings_FuncType(core_methods[3])(self.core_webview, ctypes.byref(settings_ptr))
                    if hr_set == 0 and settings_ptr.value:
                        p_set_vt = ctypes.cast(settings_ptr, ctypes.POINTER(ctypes.c_void_p))[0]
                        set_methods = ctypes.cast(p_set_vt, ctypes.POINTER(ctypes.c_void_p))
                        settings7_ptr = ctypes.c_void_p()
                        hr_qi = QI_FuncType(set_methods[0])(settings_ptr, ctypes.byref(IID_ICoreWebView2Settings7), ctypes.byref(settings7_ptr))
                        if hr_qi == 0 and settings7_ptr.value:
                            p_s7_vt = ctypes.cast(settings7_ptr, ctypes.POINTER(ctypes.c_void_p))[0]
                            s7_methods = ctypes.cast(p_s7_vt, ctypes.POINTER(ctypes.c_void_p))
                            # Slot 34 is put_HiddenPdfToolbarItems; 0xFFFF hides all toolbar action buttons
                            PutHiddenPdf_FuncType(s7_methods[34])(settings7_ptr, 0xFFFF)
                            Release_FuncType(s7_methods[2])(settings7_ptr)
                        Release_FuncType(set_methods[2])(settings_ptr)
                except Exception:
                    pass

                # Register NavigationCompleted
                token = ctypes.c_int64()
                AddNavCompleted_FuncType(core_methods[15])(self.core_webview, ctypes.byref(nav_h), ctypes.byref(token))

            self.is_initialized = True

            # Sync initial geometry if available
            x, y, w, h = self.last_rect
            if w > 0 and h > 0:
                self.update_geometry_dip(x, y, w, h)

            if getattr(self, '_should_be_visible', False) and w > 0 and h > 0:
                self.show()
                self.raise_()
                try:
                    p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                    ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                    PutIsVisible_FuncType(ctrl_methods[4])(self.controller, True)
                except Exception:
                    pass

            # Load queued PDF if any
            if self.pending_pdf_path:
                pdf_to_load = self.pending_pdf_path
                self.pending_pdf_path = None
                self.load_pdf(pdf_to_load)

            return 0

        c_ctrl_invoke = CTRL_INVOKE_FUNC(on_controller_created)
        ctrl_vtbl = CtrlCompletedHandlerVtbl(c_qi, c_addref, c_release, c_ctrl_invoke)
        ctrl_h = CtrlCompletedHandler(ctypes.pointer(ctrl_vtbl))
        self._com_refs.extend([c_ctrl_invoke, ctrl_vtbl, ctrl_h])

        # Handler for CreateCoreWebView2EnvironmentCompleted
        def on_env_created(this, hr, created_env):
            if hr != 0 or not created_env:
                self.is_initializing = False
                self.error_signal.emit(f"Failed to create WebView2 environment (HRESULT: {hex(hr & 0xFFFFFFFF)})")
                return 0

            self.env = created_env
            p_env_vt = ctypes.cast(created_env, ctypes.POINTER(ctypes.c_void_p))[0]
            env_methods = ctypes.cast(p_env_vt, ctypes.POINTER(ctypes.c_void_p))
            
            # AddRef environment
            AddRef_FuncType(env_methods[1])(created_env)

            create_ctrl = CreateCtrl_FuncType(env_methods[3])
            hr_ctrl = create_ctrl(created_env, hwnd, ctypes.byref(ctrl_h))
            if hr_ctrl != 0:
                self.is_initializing = False
                self.error_signal.emit(f"CreateCoreWebView2Controller call failed: {hex(hr_ctrl & 0xFFFFFFFF)}")
            return 0

        c_env_invoke = ENV_INVOKE_FUNC(on_env_created)
        env_vtbl = EnvCompletedHandlerVtbl(c_qi, c_addref, c_release, c_env_invoke)
        env_h = EnvCompletedHandler(ctypes.pointer(env_vtbl))
        self._com_refs.extend([c_env_invoke, env_vtbl, env_h])

        CreateEnv = loader.CreateCoreWebView2EnvironmentWithOptions
        CreateEnv.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p]
        CreateEnv.restype = HRESULT

        # Force full GPU hardware acceleration on Microsoft Edge WebView2 PDF preview
        cur_args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
        gpu_args = "--enable-gpu-rasterization --enable-zero-copy --enable-accelerated-2d-canvas --ignore-gpu-blocklist"
        for arg in gpu_args.split():
            if arg not in cur_args:
                cur_args = f"{cur_args} {arg}".strip()
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = cur_args

        hr_env = CreateEnv(None, self._user_data_dir, None, ctypes.byref(env_h))
        if hr_env != 0:
            self.is_initializing = False
            self.error_signal.emit(f"CreateCoreWebView2EnvironmentWithOptions failed: {hex(hr_env & 0xFFFFFFFF)}")

    def load_pdf(self, pdf_path):
        if not pdf_path:
            return
        abs_path = os.path.abspath(pdf_path)
        if (
            self.is_initialized
            and self.core_webview
            and self.pending_pdf_path is None
            and self.current_pdf_path == abs_path
        ):
            self._nav_seq += 1
            seq = self._nav_seq
            QTimer.singleShot(0, lambda: (
                self.pdf_loaded_signal.emit(abs_path)
                if self._nav_seq == seq and self.current_pdf_path == abs_path and self._should_be_visible
                else None
            ))
            return

        self.current_pdf_path = abs_path
        self._nav_seq += 1
        seq = self._nav_seq

        if not self.is_initialized or not self.core_webview:
            self.pending_pdf_path = abs_path
            if not self.is_initializing:
                self._start_init_webview()
            return

        # Prepare URI pointing to local file with toolbar hidden and Fit to Width parameter
        uri = "file:///" + abs_path.replace("\\", "/") + "#toolbar=0&navpanes=0&scrollbar=0&view=FitH"
        
        try:
            p_core_vt = ctypes.cast(self.core_webview, ctypes.POINTER(ctypes.c_void_p))[0]
            core_methods = ctypes.cast(p_core_vt, ctypes.POINTER(ctypes.c_void_p))
            Navigate_FuncType(core_methods[5])(self.core_webview, uri)
            
            # Fallback timer in case PDF plugin completes silently (ultra-low latency)
            QTimer.singleShot(150, lambda: (
                self.pdf_loaded_signal.emit(abs_path)
                if self._nav_seq == seq and self.current_pdf_path == abs_path and self._should_be_visible
                else None
            ))
        except Exception as e:
            self.error_signal.emit(f"Navigate error: {e}")

    def update_geometry_dip(self, x, y, w, h, dpr=None):
        self.last_rect = (x, y, w, h)
        if w <= 0 or h <= 0:
            self.hide()
            return

        if dpr is None:
            try:
                dpr = self.devicePixelRatioF()
            except Exception:
                dpr = 1.0

        ix = int(round(x))
        iy = int(round(y))
        iw = int(round(w))
        ih = int(round(h))

        # Position Qt host widget
        self.setGeometry(ix, iy, iw, ih)

        # Match native Win32 controller bounds (in physical pixels)
        if self.controller:
            try:
                w_px = int(round(iw * dpr))
                h_px = int(round(ih * dpr))
                p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                
                rect = RECT(0, 0, w_px, h_px)
                PutBounds_FuncType(ctrl_methods[6])(self.controller, rect)
                NotifyPos_FuncType(ctrl_methods[23])(self.controller)
            except Exception:
                pass

        if getattr(self, '_should_be_visible', False):
            self.show()
            self.raise_()
            if self.controller:
                try:
                    p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                    ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                    PutIsVisible_FuncType(ctrl_methods[4])(self.controller, True)
                except Exception:
                    pass

    def set_viewer_visible(self, visible):
        self._should_be_visible = visible
        if visible:
            if self.last_rect[2] > 0 and self.last_rect[3] > 0:
                self.show()
                self.raise_()
                if self.controller:
                    try:
                        p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                        ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                        PutIsVisible_FuncType(ctrl_methods[4])(self.controller, True)
                    except Exception:
                        pass
        else:
            self.hide()
            if self.controller:
                try:
                    p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                    ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                    PutIsVisible_FuncType(ctrl_methods[4])(self.controller, False)
                except Exception:
                    pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.controller:
            try:
                dpr = self.devicePixelRatioF()
                w_px = int(round(self.width() * dpr))
                h_px = int(round(self.height() * dpr))
                p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                
                rect = RECT(0, 0, w_px, h_px)
                PutBounds_FuncType(ctrl_methods[6])(self.controller, rect)
                NotifyPos_FuncType(ctrl_methods[23])(self.controller)
            except Exception:
                pass

    def destroy_viewer(self):
        if self.controller:
            try:
                p_ctrl_vt = ctypes.cast(self.controller, ctypes.POINTER(ctypes.c_void_p))[0]
                ctrl_methods = ctypes.cast(p_ctrl_vt, ctypes.POINTER(ctypes.c_void_p))
                CloseCtrl_FuncType(ctrl_methods[24])(self.controller)
                Release_FuncType(ctrl_methods[2])(self.controller)
            except Exception:
                pass
            self.controller = None

        if self.core_webview:
            try:
                p_core_vt = ctypes.cast(self.core_webview, ctypes.POINTER(ctypes.c_void_p))[0]
                core_methods = ctypes.cast(p_core_vt, ctypes.POINTER(ctypes.c_void_p))
                Release_FuncType(core_methods[2])(self.core_webview)
            except Exception:
                pass
            self.core_webview = None

        if self.env:
            try:
                p_env_vt = ctypes.cast(self.env, ctypes.POINTER(ctypes.c_void_p))[0]
                env_methods = ctypes.cast(p_env_vt, ctypes.POINTER(ctypes.c_void_p))
                Release_FuncType(env_methods[2])(self.env)
            except Exception:
                pass
            self.env = None

        self._com_refs.clear()

        # Clean user data dir if empty or temporary
        if self._user_data_dir and os.path.exists(self._user_data_dir):
            try:
                shutil.rmtree(self._user_data_dir, ignore_errors=True)
            except Exception:
                pass
