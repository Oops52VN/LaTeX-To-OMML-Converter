import sys
import os

# Guarantee current script directory ('app') and workspace root are in sys.path
_current_app_dir = os.path.dirname(os.path.abspath(__file__))
if _current_app_dir not in sys.path:
    sys.path.insert(0, _current_app_dir)
_workspace_root = os.path.dirname(_current_app_dir)
_local_core_python = os.path.join(_workspace_root, "core", "python")
if os.path.isdir(_local_core_python) and _local_core_python not in sys.path:
    sys.path.insert(1, _local_core_python)
if _workspace_root not in sys.path:
    sys.path.insert(2, _workspace_root)

import io
import time
import zipfile
import re
import shutil
import uuid
import hashlib
import tempfile
import traceback
import json
import ctypes
import threading
from ctypes.wintypes import DWORD
from collections import OrderedDict

import pythoncom
import win32com.client

# WebEngine/Qt5 Core DLL resolution fix for Windows
try:
    for path in sys.path:
        if 'site-packages' in path:
            qt5_bin = os.path.join(path, 'PyQt5', 'Qt5', 'bin')
            if os.path.exists(qt5_bin):
                os.environ['PATH'] = qt5_bin + os.pathsep + os.environ.get('PATH', '')
                if hasattr(os, 'add_dll_directory'):
                    os.add_dll_directory(qt5_bin)
                os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
                os.environ["QTWEBENGINEPROCESS_PATH"] = os.path.join(qt5_bin, "QtWebEngineProcess.exe")
                break
except Exception:
    pass

# Hardware GPU Acceleration & Offline Chromium / Edge WebView2 Flags (Must be set before any Qt/Chromium imports)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-gpu-rasterization "
    "--enable-zero-copy "
    "--enable-accelerated-2d-canvas "
    "--ignore-gpu-blocklist "
    "--disable-gpu-vsync=0 "
    "--disable-background-networking "
    "--dns-prefetch-disable "
    "--disable-sync"
)
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
    "--enable-gpu-rasterization "
    "--enable-zero-copy "
    "--enable-accelerated-2d-canvas "
    "--ignore-gpu-blocklist "
    "--disable-background-networking "
    "--dns-prefetch-disable "
    "--disable-sync"
)

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QFileDialog, QMessageBox, QStackedWidget, QStackedLayout, QLabel, QGraphicsOpacityEffect)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QSettings, QObject, pyqtSlot, QProcess, QPropertyAnimation, QVariantAnimation, QEasingCurve, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QSurfaceFormat, QPainter, QPen, QColor, QPalette, QDesktopServices, QBrush, QLinearGradient
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile, QWebEnginePage
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebChannel import QWebChannel

from lxml import etree
from latex2mathml.converter import convert as latex_to_mathml

try:
    import quast_core
    HAS_RUST_CORE = getattr(quast_core, "HAS_RUST_CORE", False)
except Exception:
    HAS_RUST_CORE = False

import latex_omml_engine
import image_omml_engine
from edge_pdf_viewer import EdgePdfPreviewHost, is_webview2_available


WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {'w': WORD_NAMESPACE, 'm': "http://schemas.openxmlformats.org/officeDocument/2006/math"}


class SilentWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass


class OfflineInterceptor(QWebEngineUrlRequestInterceptor):
    ALLOWED_SCHEMES = ("file", "qrc", "data", "blob", "about")

    def interceptRequest(self, info):
        if info.requestUrl().scheme().lower() not in self.ALLOWED_SCHEMES:
            info.block(True)


def resource_path(relative_path):
    """Resolve a path inside the project's `resources/` directory."""
    try:
        base_path = os.path.join(sys._MEIPASS, "resources")
    except Exception:
        src_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(os.path.dirname(src_dir), "resources")
    path = os.path.join(base_path, relative_path)
    return path if os.path.exists(path) else os.path.join(os.path.abspath("resources"), relative_path)


def locate_xslt():
    import winreg
    paths = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Winword.exe") as key:
            path, _ = winreg.QueryValueEx(key, "Path")
            paths.append(path)
    except Exception:
        pass
        
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Office\16.0\Word\InstallRoot") as key:
            path, _ = winreg.QueryValueEx(key, "Path")
            paths.append(path)
    except Exception:
        pass
        
    for p in paths:
        if p:
            xsl = os.path.join(p, 'MML2OMML.XSL')
            if os.path.exists(xsl):
                return xsl
                
    office_paths = [
        r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL",
        r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL",
        r"C:\Program Files\Microsoft Office\Office16\MML2OMML.XSL",
        r"C:\Program Files (x86)\Microsoft Office\Office16\MML2OMML.XSL",
        r"C:\Program Files\Microsoft Office\Office15\MML2OMML.XSL",
        r"C:\Program Files (x86)\Microsoft Office\Office15\MML2OMML.XSL",
        r"C:\Program Files\Microsoft Office\Office14\MML2OMML.XSL",
        r"C:\Program Files (x86)\Microsoft Office\Office14\MML2OMML.XSL",
    ]
    system_xslt = next((path for path in office_paths if os.path.exists(path)), None)
    if system_xslt:
        return system_xslt

    local_path = resource_path("xsl/MML2OMML.XSL")
    if os.path.exists(local_path): 
        return local_path
        
    return None


_FUNC_PATTERN_RE = re.compile(
    r'\\(sin|cos|tan|cot|sec|csc|log|ln|lim|arcsin|arccos|arctan|sinh|cosh|tanh|coth)((?:[_^](?:[^{}\s]+|\{[^}]+\}))*)\s+([a-zA-Z0-9\\])'
)
_CODE_BLOCK_TRIPLE_RE = re.compile(r'```.*?```', flags=re.DOTALL)
_CODE_BLOCK_SINGLE_RE = re.compile(r'`.*?`', flags=re.DOTALL)
_MATH_SPLIT_RE = re.compile(
    r'((?<!\\)\$\$.*?(?<!\\)\$\$|(?<!\\)(?<!\d)\$(?!\s)(?:\\.|[^$])*?(?<!\s)(?<!\\)\$(?!\d))',
    re.DOTALL
)

OPEN_FENCES = {'(', '[', '{', '&#x00028;', '&#x0005B;', '&#x0007B;', '\u0028', '\u005b', '\u007b'}
CLOSE_MAP = {
    ')': '(', ']': '[', '}': '{',
    '&#x00029;': '&#x00028;', '&#x0005D;': '&#x0005B;', '&#x0007D;': '&#x0007B;',
    '\u0029': '\u0028', '\u005d': '\u005b', '\u007d': '\u007b'
}

def normalize_open(ch):
    if ch in ['(', '&#x00028;', '\u0028']: return '('
    if ch in ['[', '&#x0005B;', '\u005b']: return '['
    if ch in ['{', '&#x0007B;', '\u007b']: return '{'
    return ch

def normalize_close(ch):
    if ch in [')', '&#x00029;', '\u0029']: return '('
    if ch in [']', '&#x0005D;', '\u005d']: return '['
    if ch in ['}', '&#x0007D;', '\u007d']: return '{'
    return ch

def get_fence_close(node):
    tag = node.tag.split('}')[-1]
    if tag == 'mo':
        t = (node.text or '').strip()
        if t in CLOSE_MAP:
            return normalize_close(t)
    elif tag in ['msup', 'msub', 'msubsup']:
        if len(node) > 0:
            base = node[0]
            if base.tag.split('}')[-1] == 'mo':
                t = (base.text or '').strip()
                if t in CLOSE_MAP:
                    return normalize_close(t)
    return None

class FormulaOmmlCache:
    """Thread-safe formula compilation cache: in-memory dict with persistent JSON storage."""
    def __init__(self, cache_file=None):
        if cache_file is None:
            cache_dir = os.path.join(tempfile.gettempdir(), "quast_preview_cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "omml_formula_cache.json")
        self.cache_file = cache_file
        self._lock = threading.Lock()
        self._cache = {}
        self._dirty = False
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 2:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}

    def get(self, key: str):
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: str):
        with self._lock:
            self._cache[key] = value
            self._dirty = True

    def save(self):
        with self._lock:
            if not self._dirty:
                return
            try:
                temp_path = self.cache_file + f".tmp.{os.getpid()}"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f)
                os.replace(temp_path, self.cache_file)
                self._dirty = False
            except Exception:
                pass

_GLOBAL_FORMULA_CACHE = FormulaOmmlCache()

def fix_mathml_tree(tree):
    """
    Standardize MathML AST tree structure in strict compliance with ISO 80000-2 mathematical display standards:
    1. Scan bottom-up (post-order traversal: child elements before parent) to optimize runtime.
    2. Group bracket pairs into dedicated <mrow> blocks.
    3. If the closing bracket carries a script (msup/msub/msubsup as in (-1)^k), elevate the entire
       bracketed expression to become the base of the script to activate Microsoft Word's standard 2D stretchy delimiters.
    4. Wrap multi-element content between two brackets in an inner <mrow> so that MML2OMML.XSL
       consistently outputs Microsoft Word's standard 2D stretchy structure (<m:d> with m:sepChr="").
    """
    ns = 'http://www.w3.org/1998/Math/MathML'
    elements = [el for el in tree.iter() if el.tag.endswith('mrow') or el.tag.endswith('math')]
    elements.reverse()

    for parent in elements:
        while True:
            children = list(parent)
            n = len(children)
            if n <= 1:
                break
            open_idx = None
            open_char = None
            found_fence = False
            for i, ch in enumerate(children):
                tag = ch.tag.split('}')[-1]
                if tag == 'mo':
                    t = (ch.text or '').strip()
                    if t in OPEN_FENCES and open_idx is None:
                        open_idx = i
                        open_char = normalize_open(t)
                        continue

                close_char = get_fence_close(ch)
                if close_char is not None and open_idx is not None:
                    if close_char == open_char:
                        close_idx = i
                        ch_tag = ch.tag.split('}')[-1]
                        is_script = ch_tag in ['msup', 'msub', 'msubsup']

                        if open_idx == 0 and close_idx == n - 1 and not is_script:
                            middle = children[1:-1]
                            if len(middle) > 1:
                                inner_mrow = etree.Element(f'{{{ns}}}mrow')
                                for m in middle:
                                    parent.remove(m)
                                    inner_mrow.append(m)
                                parent.insert(1, inner_mrow)
                            open_idx = None
                            open_char = None
                            break

                        sub_children = children[open_idx:close_idx + 1]
                        for node in sub_children:
                            parent.remove(node)

                        open_node = sub_children[0]
                        close_node = sub_children[-1]
                        middle = sub_children[1:-1]

                        fenced_mrow = etree.Element(f'{{{ns}}}mrow')
                        fenced_mrow.append(open_node)

                        if len(middle) > 1:
                            inner_mrow = etree.Element(f'{{{ns}}}mrow')
                            for m in middle:
                                inner_mrow.append(m)
                            fenced_mrow.append(inner_mrow)
                        elif len(middle) == 1:
                            fenced_mrow.append(middle[0])

                        if is_script:
                            base_mo = close_node[0]
                            close_node.remove(base_mo)
                            fenced_mrow.append(base_mo)
                            close_node.insert(0, fenced_mrow)
                            parent.insert(open_idx, close_node)
                        else:
                            fenced_mrow.append(close_node)
                            parent.insert(open_idx, fenced_mrow)

                        found_fence = True
                        break
            if not found_fence:
                break

    for mrow in tree.iter():
        if mrow.tag.endswith('mrow'):
            children = list(mrow)
            if len(children) > 3:
                first = children[0]
                last = children[-1]
                if first.tag.split('}')[-1] == 'mo' and last.tag.split('}')[-1] == 'mo':
                    f_text = (first.text or '').strip()
                    l_text = (last.text or '').strip()
                    if f_text in OPEN_FENCES and l_text in CLOSE_MAP and normalize_open(f_text) == normalize_close(l_text):
                        inner_nodes = children[1:-1]
                        inner_mrow = etree.Element(f'{{{ns}}}mrow')
                        for in_node in inner_nodes:
                            mrow.remove(in_node)
                            inner_mrow.append(in_node)
                        mrow.insert(1, inner_mrow)

    return tree


def convert_latex_to_omml(latex_string, transform, is_block=False):
    cache_key = f"{'B' if is_block else 'I'}:{latex_string}"
    cached_omml = _GLOBAL_FORMULA_CACHE.get(cache_key)
    if cached_omml is not None:
        try:
            return etree.fromstring(cached_omml.encode('utf-8'))
        except Exception:
            pass

    # High-Performance Direct AST Compiler Fast-Path (< 0.1ms)
    fast_omml = latex_omml_engine.compile_formula_fast_omml(latex_string, is_block=is_block)
    if fast_omml is not None:
        _GLOBAL_FORMULA_CACHE.set(cache_key, fast_omml)
        try:
            return etree.fromstring(fast_omml.encode('utf-8'))
        except Exception:
            pass

    latex_processed = _FUNC_PATTERN_RE.sub(r'\\\1\2\\, \3', latex_string)
    
    mathml = latex_to_mathml(latex_processed, display="block") if is_block else latex_to_mathml(latex_processed)
    mathml = mathml.replace("&#x02212;", "-") \
                   .replace('<mspace width="0.167em" />', '<mtext>&#x2009;</mtext>') \
                   .replace('<mspace width="0.222em" />', '<mtext>&#x2004;</mtext>') \
                   .replace('<mspace width="0.278em" />', '<mtext>&#x2004;</mtext>') \
                   .replace('<mspace width="1em" />', '<mtext>&#x2003;</mtext>') \
                   .replace('<mspace width="2em" />', '<mtext>&#x2003;&#x2003;</mtext>')
    
    mathml_tree = etree.fromstring(mathml.encode('utf-8'))
    mathml_tree.attrib['xmlns'] = "http://www.w3.org/1998/Math/MathML"
    mathml_tree = fix_mathml_tree(mathml_tree)
    omml_node = transform(mathml_tree).getroot()
    omml_str = etree.tostring(omml_node, encoding='utf-8', pretty_print=False).decode('utf-8')
    _GLOBAL_FORMULA_CACHE.set(cache_key, omml_str)
    return omml_node


def convert_latex_snippet_to_omml(latex_code, transform, pretty_print=False):
    try:
        latex_code = latex_code.strip()
        if not latex_code:
            return {"success": False, "error": "LaTeX input is empty"}

        is_block = True
        if latex_code.startswith('$$') and latex_code.endswith('$$'):
            latex_code = latex_code[2:-2].strip()
        elif latex_code.startswith('$') and latex_code.endswith('$'):
            latex_code = latex_code[1:-1].strip()
            is_block = False
        elif (latex_code.startswith(r'\[') and latex_code.endswith(r'\]')) or (latex_code.startswith('\\[') and latex_code.endswith('\\]')):
            latex_code = latex_code[2:-2].strip()
        elif (latex_code.startswith(r'\(') and latex_code.endswith(r'\)')) or (latex_code.startswith('\\(') and latex_code.endswith('\\)')):
            latex_code = latex_code[2:-2].strip()
            is_block = False

        cache_key = f"{'B' if is_block else 'I'}:{latex_code}"
        cached_omml = _GLOBAL_FORMULA_CACHE.get(cache_key)
        if cached_omml is not None:
            return {
                "success": True,
                "latex": latex_code,
                "mathml": "",
                "omml": cached_omml,
                "error": None
            }

        # High-Performance Direct AST Compiler Fast-Path (< 0.1ms)
        fast_omml = latex_omml_engine.compile_formula_fast_omml(latex_code, is_block=is_block)
        if fast_omml is not None:
            _GLOBAL_FORMULA_CACHE.set(cache_key, fast_omml)
            return {
                "success": True,
                "latex": latex_code,
                "mathml": "",
                "omml": fast_omml,
                "error": None
            }

        latex_processed = _FUNC_PATTERN_RE.sub(r'\\\1\2\\, \3', latex_code)

        mathml_str = latex_to_mathml(latex_processed, display="block" if is_block else "inline")
        mathml_clean = mathml_str.replace("&#x02212;", "-")

        mathml_tree = etree.fromstring(mathml_clean.encode('utf-8'))
        mathml_tree.attrib['xmlns'] = "http://www.w3.org/1998/Math/MathML"
        mathml_tree = fix_mathml_tree(mathml_tree)
        omml_node = transform(mathml_tree).getroot()
        
        omml_str = etree.tostring(omml_node, encoding='utf-8', pretty_print=pretty_print).decode('utf-8')
        _GLOBAL_FORMULA_CACHE.set(cache_key, omml_str)
        
        return {
            "success": True,
            "latex": latex_code,
            "mathml": mathml_clean,
            "omml": omml_str,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}



def add_text_to_paragraph(paragraph, text):
    for i, line_text in enumerate(text.split('\n')):
        if i > 0:
            br_run = etree.Element(f"{{{WORD_NAMESPACE}}}r")
            etree.SubElement(br_run, f"{{{WORD_NAMESPACE}}}br")
            paragraph.append(br_run)
        if line_text:
            for j, t_text in enumerate(line_text.split('\t')):
                if j > 0:
                    t_run = etree.Element(f"{{{WORD_NAMESPACE}}}r")
                    etree.SubElement(t_run, f"{{{WORD_NAMESPACE}}}tab")
                    paragraph.append(t_run)
                if t_text:
                    text_run = etree.Element(f"{{{WORD_NAMESPACE}}}r")
                    text_node = etree.SubElement(text_run, f"{{{WORD_NAMESPACE}}}t")
                    text_node.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                    text_node.text = t_text
                    paragraph.append(text_run)


def process_paragraph_xml(paragraph, transform):
    nodes = paragraph.xpath('.//w:t | .//w:br | .//w:tab', namespaces=NSMAP)
    if not nodes: 
        return False

    texts = []
    for node in nodes:
        if node.tag.endswith('}t') and node.text: 
            texts.append(node.text)
        elif node.tag.endswith('}br'): 
            texts.append('\n')
        elif node.tag.endswith('}tab'): 
            texts.append('\t')
            
    full_text = "".join(texts)

    if HAS_RUST_CORE:
        segments = quast_core.scan_formulas(full_text)
        if not any(s.is_math for s in segments):
            return False

        pPr = paragraph.find(f"{{{WORD_NAMESPACE}}}pPr")
        for child in list(paragraph):
            if child != pPr:
                paragraph.remove(child)

        has_surrounding_text = any(not s.is_math and s.text.strip() for s in segments)

        for seg in segments:
            if not seg.is_math:
                add_text_to_paragraph(paragraph, seg.text)
            else:
                effective_block = seg.is_block and not has_surrounding_text
                try:
                    paragraph.append(convert_latex_to_omml(seg.text, transform, is_block=effective_block))
                except Exception:
                    fallback_text = f"$${seg.text}$$" if seg.is_block else f"${seg.text}$"
                    add_text_to_paragraph(paragraph, fallback_text)
        return True
        
    code_blocks, cb_counter = {}, [0]
    
    def repl_code(m):
        token = f"__QUAST_CB_{cb_counter[0]}__"
        code_blocks[token] = m.group(0)
        cb_counter[0] += 1
        return token

    full_text = _CODE_BLOCK_TRIPLE_RE.sub(repl_code, full_text)
    full_text = _CODE_BLOCK_SINGLE_RE.sub(repl_code, full_text)

    parts = _MATH_SPLIT_RE.split(full_text)
    
    if len(parts) == 1: 
        return False
        
    pPr = paragraph.find(f"{{{WORD_NAMESPACE}}}pPr")
    for child in list(paragraph):
        if child != pPr:
            paragraph.remove(child)
            
    for i, part in enumerate(parts):
        if not part: 
            continue
        
        for uid, orig_text in code_blocks.items():
            if uid in part:
                part = part.replace(uid, orig_text)
                    
        if i % 2 != 0:
            is_block = part.startswith('$$')
            latex_expr = part[2:-2] if is_block else part[1:-1]
            try:
                paragraph.append(convert_latex_to_omml(latex_expr, transform, is_block=is_block))
            except Exception:
                add_text_to_paragraph(paragraph, part)
        else:
            add_text_to_paragraph(paragraph, part)
            
    return True


# =====================================================================
# BACKGROUND THREAD WORKERS
# =====================================================================
WORD_COM_LOCK = threading.Lock()


class ImageOcrWorker(QThread):
    result_signal = pyqtSignal(str)

    def __init__(self, image_data_b64, xslt_transform=None):
        super().__init__()
        self.image_data_b64 = image_data_b64
        self.xslt_transform = xslt_transform
        # Set LowPriority to guarantee smooth 60 FPS in UI
        self.setPriority(QThread.LowPriority)

    def run(self):
        try:
            # Yield slightly to ensure the GUI event loop remains 100% fluid
            time.sleep(0.01)
            res = image_omml_engine.recognize_formula_image_to_omml(
                self.image_data_b64,
                xslt_transform=self.xslt_transform
            )
            self.image_data_b64 = None
            self.result_signal.emit(json.dumps(res))
        except Exception as e:
            self.image_data_b64 = None
            self.result_signal.emit(json.dumps({"success": False, "error": str(e)}))
        finally:
            import gc
            gc.collect()



class SpinnerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._rotate)
        self.timer.start(16)

    def _rotate(self):
        self.angle = (self.angle + 7) % 360
        self.update()

    def stop(self):
        self.timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(4.0, 4.0, 38.0, 38.0)
        pen_bg = QPen(QColor(45, 48, 55), 3.0)
        painter.setPen(pen_bg)
        painter.drawEllipse(rect)
        pen_fg = QPen(QColor(59, 130, 246), 3.0)
        painter.setPen(pen_fg)
        painter.drawArc(rect, int(-self.angle * 16), int(100 * 16))


class QtLoadingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #141518;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Container for content (spinner + text) so that text disappears completely before background fades out
        self.content_widget = QWidget(self)
        self.content_widget.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(self.content_widget)
        c_layout.setAlignment(Qt.AlignCenter)
        c_layout.setSpacing(16)

        self.spinner = SpinnerWidget(self.content_widget)
        c_layout.addWidget(self.spinner, 0, Qt.AlignCenter)

        self.title_label = QLabel("LATEX TO OMML CONVERTER", self.content_widget)
        self.title_label.setStyleSheet(
            "color: #ffffff; font-size: 17px; font-weight: 700; letter-spacing: 3.5px; background: transparent;"
        )
        self.title_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.title_label, 0, Qt.AlignCenter)

        self.sub_label = QLabel("INITIALIZING...", self.content_widget)
        self.sub_label.setStyleSheet(
            "color: #9ca3af; font-size: 12px; font-family: monospace; letter-spacing: 2px; font-weight: 500; background: transparent;"
        )
        self.sub_label.setAlignment(Qt.AlignCenter)
        c_layout.addWidget(self.sub_label, 0, Qt.AlignCenter)

        main_layout.addWidget(self.content_widget, 0, Qt.AlignCenter)
        
        self.content_opacity = QGraphicsOpacityEffect(self.content_widget)
        self.content_widget.setGraphicsEffect(self.content_opacity)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def update_progress(self, percent, message=""):
        if message:
            self.sub_label.setText(message.upper())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#141518"))


class PreviewCacheManager:
    """Thread-safe persistent on-disk and in-memory PDF preview cache manager (full + 3-page partial)."""
    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = os.path.join(tempfile.gettempdir(), "quast_preview_cache")
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)
        self._memory_cache = {}   # (norm_docx_path, key) -> full_pdf_path
        self._partial_cache = {}  # (norm_docx_path, key) -> _p3.pdf_path
        self._lock = threading.Lock()

    def _get_key(self, docx_path):
        norm_path = os.path.normcase(os.path.abspath(docx_path))
        try:
            stat = os.stat(norm_path)
            mtime = stat.st_mtime_ns
            size = stat.st_size
        except Exception:
            mtime = 0
            size = 0
        raw = f"{norm_path}|{mtime}|{size}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()[:16]

    def get_cached_preview(self, docx_path):
        """Return (pdf_path, is_partial) if full or 3-page partial PDF is cached, else (None, False)."""
        if not docx_path or not os.path.exists(docx_path):
            return None, False
        norm_path = os.path.normcase(os.path.abspath(docx_path))
        key = self._get_key(docx_path)
        mem_key = (norm_path, key)
        safe_stem = re.sub(r'[^\w\-. ]', '_', os.path.splitext(os.path.basename(docx_path))[0])

        with self._lock:
            # 1. Check full PDF cache (memory -> disk)
            if mem_key in self._memory_cache:
                pdf_path = self._memory_cache[mem_key]
                if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 100:
                    return pdf_path, False
                self._memory_cache.pop(mem_key, None)

            disk_full = os.path.join(self.cache_dir, f"{safe_stem}_{key}.pdf")
            if os.path.exists(disk_full) and os.path.getsize(disk_full) > 100:
                self._memory_cache[mem_key] = disk_full
                return disk_full, False

            # 2. Check partial (_p3) PDF cache (memory -> disk)
            if mem_key in self._partial_cache:
                p3_path = self._partial_cache[mem_key]
                if os.path.exists(p3_path) and os.path.getsize(p3_path) > 100:
                    return p3_path, True
                self._partial_cache.pop(mem_key, None)

            disk_p3 = os.path.join(self.cache_dir, f"{safe_stem}_{key}_p3.pdf")
            if os.path.exists(disk_p3) and os.path.getsize(disk_p3) > 100:
                self._partial_cache[mem_key] = disk_p3
                return disk_p3, True

        return None, False

    def get_cached_pdf(self, docx_path):
        """Return cached full PDF path if available, else None."""
        pdf_path, is_partial = self.get_cached_preview(docx_path)
        if pdf_path and not is_partial:
            return pdf_path
        return None

    def get_target_cache_path(self, docx_path):
        key = self._get_key(docx_path)
        safe_stem = re.sub(r'[^\w\-. ]', '_', os.path.splitext(os.path.basename(docx_path))[0])
        return os.path.join(self.cache_dir, f"{safe_stem}_{key}.pdf")

    def get_target_partial_cache_path(self, docx_path):
        key = self._get_key(docx_path)
        safe_stem = re.sub(r'[^\w\-. ]', '_', os.path.splitext(os.path.basename(docx_path))[0])
        return os.path.join(self.cache_dir, f"{safe_stem}_{key}_p3.pdf")

    def register_cache(self, docx_path, pdf_path):
        if not docx_path or not pdf_path or not os.path.exists(pdf_path):
            return
        norm_path = os.path.normcase(os.path.abspath(docx_path))
        key = self._get_key(docx_path)
        mem_key = (norm_path, key)
        target_path = self.get_target_cache_path(docx_path)
        with self._lock:
            if os.path.abspath(pdf_path) != os.path.abspath(target_path):
                try:
                    shutil.copy2(pdf_path, target_path)
                    pdf_path = target_path
                except Exception:
                    pass
            self._memory_cache[mem_key] = pdf_path

    def register_partial_cache(self, docx_path, pdf_path):
        if not docx_path or not pdf_path or not os.path.exists(pdf_path):
            return
        norm_path = os.path.normcase(os.path.abspath(docx_path))
        key = self._get_key(docx_path)
        mem_key = (norm_path, key)
        target_path = self.get_target_partial_cache_path(docx_path)
        with self._lock:
            if os.path.abspath(pdf_path) != os.path.abspath(target_path):
                try:
                    shutil.copy2(pdf_path, target_path)
                    pdf_path = target_path
                except Exception:
                    pass
            self._partial_cache[mem_key] = pdf_path

    def clear(self):
        with self._lock:
            self._memory_cache.clear()
            self._partial_cache.clear()
            try:
                for f in os.listdir(self.cache_dir):
                    fp = os.path.join(self.cache_dir, f)
                    if os.path.isfile(fp):
                        try:
                            os.remove(fp)
                        except Exception:
                            pass
            except Exception:
                pass


class PersistentWordPdfEngine(QThread):
    finished_signal = pyqtSignal(int, bool, str, str, str)  # req_id, success, docx_path, full_pdf_path, error_msg

    def __init__(self, window=None, cache_manager=None):
        super().__init__()
        self.window = window
        self.cache_manager = cache_manager or PreviewCacheManager()
        self.word = None
        self._active_stage1_queue = []  # priority 1: active user-selected Stage 1 (_p3.pdf)
        self._bg_stage1_queue = []      # priority 2: inactive list items Stage 1 (_p3.pdf)
        self._bg_stage2_queue = []      # priority 3: full-document PDF exports
        self.active_req_id = 0
        self.active_docx = None
        self.req_counter = 0
        self._last_request_time = 0.0
        self.stopping = False
        self._cond = threading.Condition()

    def request_preview(self, docx_path, is_active=True, stage2_only=False):
        if not docx_path or not os.path.exists(docx_path):
            return 0
        with self._cond:
            self.req_counter += 1
            req_id = self.req_counter
            orig_docx = os.path.abspath(docx_path)
            norm_docx = os.path.normcase(orig_docx)
            target_pdf = self.cache_manager.get_target_cache_path(orig_docx)
            target_early = self.cache_manager.get_target_partial_cache_path(orig_docx)
            self._last_request_time = time.monotonic()

            if is_active:
                self.active_req_id = req_id
                self.active_docx = norm_docx
                cached_pdf, is_partial = self.cache_manager.get_cached_preview(orig_docx)
                if cached_pdf and not is_partial:
                    self._active_stage1_queue.clear()
                    self._cond.notify_all()
                    return req_id

                if stage2_only or (cached_pdf and is_partial):
                    self._active_stage1_queue.clear()
                    self._bg_stage1_queue = [item for item in self._bg_stage1_queue if item[1] != norm_docx]
                    self._bg_stage2_queue = [item for item in self._bg_stage2_queue if item[1] != norm_docx]
                    self._bg_stage2_queue.insert(0, (req_id, norm_docx, orig_docx, target_pdf))
                else:
                    self._bg_stage1_queue = [item for item in self._bg_stage1_queue if item[1] != norm_docx]
                    self._active_stage1_queue = [(req_id, norm_docx, orig_docx, target_early, target_pdf)]
            else:
                cached_pdf, is_partial = self.cache_manager.get_cached_preview(orig_docx)
                if cached_pdf and not is_partial:
                    return req_id
                if cached_pdf and is_partial:
                    if not any(item[1] == norm_docx for item in self._bg_stage2_queue):
                        self._bg_stage2_queue.append((req_id, norm_docx, orig_docx, target_pdf))
                else:
                    already_s1 = any(item[1] == norm_docx for item in self._active_stage1_queue) or any(
                        item[1] == norm_docx for item in self._bg_stage1_queue
                    )
                    if not already_s1:
                        self._bg_stage1_queue.append((req_id, norm_docx, orig_docx, target_early, target_pdf))

            self._cond.notify_all()
            return req_id

    def clear_active_request(self):
        """Invalidate current active preview UI target without discarding background Stage 2 caching."""
        with self._cond:
            self.active_req_id = -1
            self.active_docx = None
            self._active_stage1_queue.clear()
            self._cond.notify_all()

    def run(self):
        pythoncom.CoInitialize()
        try:
            self._init_word()
            while not self.stopping:
                stage1_req = None
                stage1_is_active = False
                bg_req = None
                with self._cond:
                    while (
                        not self.stopping
                        and not self._active_stage1_queue
                        and not self._bg_stage1_queue
                        and not self._bg_stage2_queue
                    ):
                        self._cond.wait(0.08)
                    if self.stopping:
                        break
                    if self._active_stage1_queue:
                        stage1_req = self._active_stage1_queue.pop(0)
                        stage1_is_active = True
                    elif self._bg_stage1_queue:
                        stage1_req = self._bg_stage1_queue.pop(0)
                        stage1_is_active = False
                    elif self._bg_stage2_queue:
                        # Allow brief cooldown so rapid multi-file Stage 1 previews run before heavy Stage 2 export
                        since_last = time.monotonic() - self._last_request_time
                        if since_last < 1.0:
                            self._cond.wait(min(0.25, 1.0 - since_last))
                            continue
                        # Prefer currently active document first in Stage 2 queue
                        pick_idx = 0
                        if self.active_docx:
                            for idx, item in enumerate(self._bg_stage2_queue):
                                if item[1] == self.active_docx:
                                    pick_idx = idx
                                    break
                        bg_req = self._bg_stage2_queue.pop(pick_idx)

                if stage1_req:
                    req_id, norm_docx, orig_docx, target_early, target_pdf = stage1_req
                    cached_pdf, is_partial = self.cache_manager.get_cached_preview(orig_docx)
                    if cached_pdf:
                        with self._cond:
                            still_active = stage1_is_active and (req_id == self.active_req_id and norm_docx == self.active_docx)
                            if is_partial and not any(item[1] == norm_docx for item in self._bg_stage2_queue):
                                if stage1_is_active:
                                    self._bg_stage2_queue.insert(0, (req_id, norm_docx, orig_docx, target_pdf))
                                else:
                                    self._bg_stage2_queue.append((req_id, norm_docx, orig_docx, target_pdf))
                        if still_active:
                            self.finished_signal.emit(req_id, True, orig_docx, cached_pdf, "")
                        continue

                    self._run_stage1(req_id, norm_docx, orig_docx, target_early, target_pdf, stage1_is_active)
                elif bg_req:
                    req_id, norm_docx, orig_docx, target_pdf = bg_req
                    full_cached = self.cache_manager.get_cached_pdf(orig_docx)
                    if full_cached:
                        with self._cond:
                            still_current = (norm_docx == self.active_docx)
                        if still_current:
                            self.finished_signal.emit(req_id, True, orig_docx, full_cached, "")
                        continue

                    self._run_stage2(req_id, norm_docx, orig_docx, target_pdf)
        finally:
            self._quit_word()
            pythoncom.CoUninitialize()

    def _init_word(self):
        try:
            pids_before = set()
            try:
                pids_before = {p.pid for p in psutil.process_iter() if 'winword' in p.name().lower()}
            except Exception:
                pass
            self.word = win32com.client.DispatchEx("Word.Application")
            try:
                pids_after = {p.pid for p in psutil.process_iter() if 'winword' in p.name().lower()}
                new_pids = pids_after - pids_before
                if new_pids:
                    self.word_pid = list(new_pids)[0]
            except Exception:
                pass
            self.word.Visible = False
            self.word.DisplayAlerts = 0  # wdAlertsNone
            try:
                self.word.ScreenUpdating = False
                self.word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
                self.word.Options.CheckSpellingAsYouType = False
                self.word.Options.CheckGrammarAsYouType = False
                self.word.Options.Pagination = False
                self.word.ShowAnimation = False
            except Exception:
                pass
        except Exception:
            self.word = None

    def _quit_word(self):
        pid = getattr(self, 'word_pid', None)
        if self.word:
            try:
                self.word.Quit(SaveChanges=0)
            except Exception:
                pass
            self.word = None
        if pid:
            try:
                if psutil.pid_exists(pid):
                    p = psutil.Process(pid)
                    try:
                        p.wait(timeout=0.8)
                    except psutil.TimeoutExpired:
                        p.kill()
            except Exception:
                pass
            self.word_pid = None

    def cancel_pending_requests(self):
        """Immediately discard all queued preview tasks and invalidate active requests."""
        with self._cond:
            self.active_req_id = -1
            self.active_docx = None
            self._active_stage1_queue.clear()
            self._bg_stage1_queue.clear()
            self._bg_stage2_queue.clear()
            self._cond.notify_all()

    def _create_early_slice_docx(self, src_docx, dst_docx, max_rows=35, max_paras=45):
        """Ultra-fast in-memory extraction of the first ~3-4 pages of a document to eliminate layout lag."""
        try:
            with zipfile.ZipFile(src_docx, 'r') as zin, zipfile.ZipFile(dst_docx, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == 'word/document.xml':
                        xml_bytes = zin.read(item.filename)
                        tree = etree.fromstring(xml_bytes)
                        body = tree.find(f'{{{WORD_NAMESPACE}}}body')
                        if body is not None:
                            sectPr = body.find(f'{{{WORD_NAMESPACE}}}sectPr')
                            tables = body.findall(f'{{{WORD_NAMESPACE}}}tbl')
                            has_truncated = False
                            for tbl in tables:
                                rows = tbl.findall(f'{{{WORD_NAMESPACE}}}tr')
                                if len(rows) > max_rows:
                                    for r in rows[max_rows:]:
                                        tbl.remove(r)
                                    has_truncated = True
                            paras = body.findall(f'{{{WORD_NAMESPACE}}}p')
                            if len(paras) > max_paras:
                                for p in paras[max_paras:]:
                                    body.remove(p)
                                has_truncated = True
                            if sectPr is not None and sectPr not in list(body):
                                body.append(sectPr)
                            if not has_truncated:
                                return False
                        zout.writestr(item.filename, etree.tostring(tree, encoding='utf-8', xml_declaration=True))
                    else:
                        zout.writestr(item, zin.read(item.filename))
            return True
        except Exception:
            return False

    def _run_stage1(self, req_id, norm_docx, docx_path, target_early, target_pdf, is_active=True):
        if self.word is None:
            self._init_word()
        if self.word is None:
            with self._cond:
                still_active = is_active and (req_id == self.active_req_id and norm_docx == self.active_docx)
            if still_active:
                self.finished_signal.emit(req_id, False, docx_path, "", "Microsoft Word COM is unavailable.")
            return

        if is_active:
            with self._cond:
                if self.active_req_id != req_id or self.active_docx != norm_docx:
                    return

        early_slice_docx = None
        slice_doc = None
        try:
            early_slice_docx = os.path.abspath(
                os.path.join(tempfile.gettempdir(), f"quast_slice_{uuid.uuid4().hex[:8]}.docx")
            )
            if self._create_early_slice_docx(docx_path, early_slice_docx):
                slice_doc = self.word.Documents.Open(
                    FileName=early_slice_docx,
                    ReadOnly=True,
                    Visible=False,
                    NoEncodingDialog=True
                )
                slice_doc.ExportAsFixedFormat(
                    OutputFileName=target_early,
                    ExportFormat=17,  # wdExportFormatPDF
                    OpenAfterExport=False,
                    OptimizeFor=1,    # wdExportOptimizeForOnScreen
                    Range=0,          # Entire slice is ~3 pages
                    Item=0,
                    IncludeDocProps=False,
                    KeepIRM=False,
                    CreateBookmarks=0,
                    DocStructureTags=False,
                    BitmapMissingFonts=False,
                    UseISO19005_1=False
                )
                slice_doc.Close(SaveChanges=0)
                slice_doc = None
                if os.path.exists(target_early) and os.path.getsize(target_early) > 0:
                    self.cache_manager.register_partial_cache(docx_path, target_early)
                    with self._cond:
                        still_active = is_active and (req_id == self.active_req_id and norm_docx == self.active_docx)
                        # Queue Stage 2 full export to complete and cache in background
                        self._bg_stage2_queue = [item for item in self._bg_stage2_queue if item[1] != norm_docx]
                        if is_active:
                            self._bg_stage2_queue.insert(0, (req_id, norm_docx, docx_path, target_pdf))
                        else:
                            self._bg_stage2_queue.append((req_id, norm_docx, docx_path, target_pdf))
                    if still_active:
                        self.finished_signal.emit(req_id, True, docx_path, target_early, "")
                    return
            else:
                # Document is already small (<= 45 paragraphs): export full PDF directly in one pass
                self._run_stage2(req_id, norm_docx, docx_path, target_pdf)
                return
        except Exception:
            if slice_doc is not None:
                try:
                    slice_doc.Close(SaveChanges=0)
                except Exception:
                    pass
            try:
                self._quit_word()
            except Exception:
                pass
            # Fallback to full document export
            self._run_stage2(req_id, norm_docx, docx_path, target_pdf)
            return
        finally:
            if slice_doc is not None:
                try:
                    slice_doc.Close(SaveChanges=0)
                except Exception:
                    pass
            if early_slice_docx and os.path.exists(early_slice_docx):
                try:
                    os.remove(early_slice_docx)
                except Exception:
                    pass

        # If Stage 1 produced empty file, fall back to Stage 2
        self._run_stage2(req_id, norm_docx, docx_path, target_pdf)

    def _run_stage2(self, req_id, norm_docx, docx_path, target_pdf):
        if self.word is None:
            self._init_word()
        if self.word is None:
            with self._cond:
                still_current = (norm_docx == self.active_docx)
            if still_current:
                self.finished_signal.emit(req_id, False, docx_path, "", "Microsoft Word COM is unavailable.")
            return

        temp_src_docx = None
        doc = None
        try:
            temp_src_docx = os.path.abspath(
                os.path.join(tempfile.gettempdir(), f"quast_preview_src_{uuid.uuid4().hex[:8]}.docx")
            )
            try:
                shutil.copyfile(docx_path, temp_src_docx)
            except Exception:
                shutil.copy2(docx_path, temp_src_docx)

            doc = self.word.Documents.Open(
                FileName=temp_src_docx,
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                PasswordDocument="",
                PasswordTemplate="",
                Revert=False,
                WritePasswordDocument="",
                WritePasswordTemplate="",
                Format=0,
                Visible=False,
                OpenAndRepair=False,
                NoEncodingDialog=True
            )

            # Suppress background proofing layout overhead
            try:
                doc.SpellingChecked = True
                doc.GrammarChecked = True
            except Exception:
                pass

            # Direct full-document PDF export with Screen Optimization
            doc.ExportAsFixedFormat(
                OutputFileName=target_pdf,
                ExportFormat=17,  # wdExportFormatPDF
                OpenAfterExport=False,
                OptimizeFor=1,    # wdExportOptimizeForOnScreen
                Range=0,          # wdExportAllDocument
                Item=0,
                IncludeDocProps=False,
                KeepIRM=False,
                CreateBookmarks=0,
                DocStructureTags=False,
                BitmapMissingFonts=False,
                UseISO19005_1=False
            )

            if os.path.exists(target_pdf) and os.path.getsize(target_pdf) > 0:
                self.cache_manager.register_cache(docx_path, target_pdf)
                with self._cond:
                    still_current = (norm_docx == self.active_docx)
                if still_current:
                    self.finished_signal.emit(req_id, True, docx_path, target_pdf, "")
            else:
                with self._cond:
                    still_current = (norm_docx == self.active_docx)
                if still_current:
                    self.finished_signal.emit(req_id, False, docx_path, "", "PDF export produced empty output.")

        except Exception as e:
            try:
                self._quit_word()
            except Exception:
                pass
            with self._cond:
                still_current = (norm_docx == self.active_docx)
            if still_current:
                self.finished_signal.emit(req_id, False, docx_path, "", str(e))
        finally:
            if doc is not None:
                try:
                    doc.Close(SaveChanges=0)
                except Exception:
                    pass
            if temp_src_docx and os.path.exists(temp_src_docx):
                try:
                    os.remove(temp_src_docx)
                except Exception:
                    pass

    def stop(self, timeout_ms=3000):
        with self._cond:
            self.stopping = True
            self.active_req_id = -1
            self.active_docx = None
            self._active_stage1_queue.clear()
            self._bg_stage1_queue.clear()
            self._bg_stage2_queue.clear()
            self._cond.notify_all()
        self.wait(timeout_ms)
        if self.isRunning():
            self.terminate()
            self.wait(500)
        pid = getattr(self, 'word_pid', None)
        if pid:
            try:
                if psutil.pid_exists(pid):
                    psutil.Process(pid).kill()
            except Exception:
                pass
            self.word_pid = None


class DocxToPdfPreviewWorker(QThread):
    finished_signal = pyqtSignal(bool, str, str, str)

    def __init__(self, window, docx_path, pdf_path):
        super().__init__()
        self.window = window
        self.docx_path = os.path.abspath(docx_path)
        self.pdf_path = os.path.abspath(pdf_path)

    def run(self):
        if hasattr(self.window, 'word_engine') and self.window.word_engine.isRunning():
            self.window.word_engine.request_preview(self.docx_path, is_active=True)


class ConversionWorker(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, list)

    def __init__(self, input_files, output_dir, xslt_path):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.xslt_path = xslt_path

    def run(self):
        try:
            parser = etree.XMLParser(recover=True)
            xslt_doc = etree.parse(self.xslt_path, parser)
            transform = etree.XSLT(xslt_doc)

            if HAS_RUST_CORE:
                def compile_fn(latex_str):
                    res = convert_latex_snippet_to_omml(latex_str, transform, pretty_print=False)
                    return res["omml"] if res.get("success") else None

                results = quast_core.batch_convert_docx_hybrid(
                    self.input_files,
                    self.output_dir,
                    formula_compiler_fn=compile_fn,
                    progress_callback=self.progress_signal.emit
                )
                _GLOBAL_FORMULA_CACHE.save()
                output_paths = [r.output_path for r in results if r.success]
                if not output_paths and results and not results[0].success:
                    raise RuntimeError(results[0].error_msg)
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, output_paths)
                return
            
            total_files = len(self.input_files)
            output_paths = []
            
            for file_idx, input_path in enumerate(self.input_files):
                filename = os.path.basename(input_path)
                out_name = f"OMML_{filename}" if not filename.startswith("OMML_") else f"Converted_{filename}"
                original_output_path = os.path.join(self.output_dir, out_name)
                output_path = original_output_path
                
                with io.BytesIO() as output_stream:
                    with zipfile.ZipFile(input_path, 'r') as zin, zipfile.ZipFile(output_stream, 'w') as zout:
                        xml_content = zin.read('word/document.xml')
                        tree = etree.fromstring(xml_content)
                        
                        paragraphs = tree.xpath('.//w:p[contains(., "$")]', namespaces=NSMAP)
                        total_paragraphs = len(paragraphs)
                        
                        for index, paragraph in enumerate(paragraphs):
                            process_paragraph_xml(paragraph, transform)
                            if total_paragraphs > 0 and index % max(1, total_paragraphs // 10) == 0:
                                base_prog = (file_idx / total_files) * 100
                                file_prog = ((index + 1) / total_paragraphs) * (100 / total_files)
                                self.progress_signal.emit(int(base_prog + file_prog))
                        
                        for item in zin.infolist():
                            if item.filename == 'word/document.xml':
                                zout.writestr(item, etree.tostring(tree, encoding='UTF-8', xml_declaration=True))
                            else: 
                                zout.writestr(item, zin.read(item.filename))
                                
                        del tree
                        del xml_content
                    
                    counter = 1
                    while True:
                        try:
                            with open(output_path, 'wb') as f: 
                                f.write(output_stream.getvalue())
                            output_paths.append(output_path)
                            break
                        except PermissionError:
                            base, ext = os.path.splitext(original_output_path)
                            output_path = f"{base}_{counter}{ext}"
                            counter += 1
            
            self.progress_signal.emit(100)
            self.finished_signal.emit(True, output_paths)
            
        except Exception as e:
            self.finished_signal.emit(False, [str(e)])


# =====================================================================
# GUI CONTROLLER & FRONTEND UI BINDINGS
# =====================================================================
class Backend(QObject):
    def __init__(self, window):
        super().__init__()
        self.window = window

    @pyqtSlot(str, float, float, float, float)
    def update_word_rect(self, widget_id, x, y, w, h):
        if widget_id == 'pdf-preview' and hasattr(self.window, 'edge_pdf_viewer'):
            self.window.edge_pdf_viewer.update_geometry_dip(x, y, w, h)

    @pyqtSlot(str, bool)
    def set_word_visible(self, widget_id, visible):
        if widget_id == 'pdf-preview' and hasattr(self.window, 'edge_pdf_viewer'):
            self.window.edge_pdf_viewer.set_viewer_visible(visible)

    @pyqtSlot(result=bool)
    def is_edge_pdf_active(self):
        return bool(hasattr(self.window, 'edge_pdf_viewer') and self.window.edge_pdf_viewer.is_available)

    # ------ EAGER ALL-LOADING STARTUP PRELOAD API ------
    @pyqtSlot(int, str)
    def report_preload_progress(self, percent, message):
        if hasattr(self.window, 'on_preload_progress'):
            self.window.on_preload_progress(percent, message)

    @pyqtSlot()
    def signal_frontend_ready(self):
        if hasattr(self.window, 'on_frontend_preload_complete'):
            self.window.on_frontend_preload_complete()
            
    # ------ IMAGE OCR & PREPROCESSING BACKEND API ------
    @pyqtSlot(str, result=str)
    def preprocess_image_base64(self, b64_str):
        try:
            res = image_omml_engine.preprocess_for_math_ocr(b64_str)
            return json.dumps({
                "success": True,
                "width": res["width"],
                "height": res["height"],
                "crop_box": res["crop_box"],
                "png_base64": res["enhanced_png_b64"],
                "time_ms": res["time_ms"]
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str)
    def start_image_ocr(self, b64_str):
        """Asynchronously executes Math OCR without freezing UI."""
        worker = ImageOcrWorker(b64_str, getattr(self.window, 'xslt_transform', None))
        def on_done(res_json):
            js_call = f"if(typeof window.onImageOcrFinished === 'function') window.onImageOcrFinished({json.dumps(res_json)});"
            self.window.run_js(js_call)
            if worker in getattr(self.window, 'active_workers', []):
                self.window.active_workers.remove(worker)
        worker.result_signal.connect(on_done)
        if hasattr(self.window, 'active_workers'):
            self.window.active_workers.append(worker)
        worker.start()

    @pyqtSlot(str, result=str)
    def recognize_image_ocr_json(self, b64_str):
        """Synchronous Math OCR recognition with direct OMML generation."""
        try:
            res = image_omml_engine.recognize_formula_image_to_omml(
                b64_str,
                xslt_transform=getattr(self.window, 'xslt_transform', None)
            )
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ------ CLIPBOARD API (SUPPORTS NATIVE WORD EQUATION PASTE) ------
    @pyqtSlot(str, str, result=bool)
    def copy_omml_to_clipboard(self, omml_str, mathml_str=""):
        """
        Sets Windows Clipboard with:
        1. 'HTML Format' containing an invisible Zero-Width Space (\u200b) before the MathML equation.
           This ensures Microsoft Word pastes the formula in INLINE mode (Left-aligned), preventing Word
           from automatically jumping the formula to the center of the page when pasted onto an empty line.
        2. 'MathML Presentation' format for secondary MathML consumers.
        3. 'CF_UNICODETEXT' for text/code editors to receive the raw OMML XML.
        """
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                if mathml_str:
                    # 1. HTML Format with Zero-Width Space (&#8203;) before MathML
                    header_template = (
                        "Version:0.9\r\n"
                        "StartHTML:{:08d}\r\n"
                        "EndHTML:{:08d}\r\n"
                        "StartFragment:{:08d}\r\n"
                        "EndFragment:{:08d}\r\n"
                    )
                    html_start = (
                        '<!DOCTYPE html>\r\n'
                        '<html>\r\n'
                        '<head><meta charset="utf-8"></head>\r\n'
                        '<body>\r\n'
                        '<!--StartFragment-->'
                    )
                    html_end = '<!--EndFragment-->\r\n</body>\r\n</html>'
                    fragment = f'&#8203;{mathml_str}'

                    dummy_header = header_template.format(0, 0, 0, 0)
                    start_html = len(dummy_header.encode('utf-8'))
                    start_frag = start_html + len(html_start.encode('utf-8'))
                    end_frag = start_frag + len(fragment.encode('utf-8'))
                    end_html = end_frag + len(html_end.encode('utf-8'))

                    final_header = header_template.format(start_html, end_html, start_frag, end_frag)
                    html_payload = (final_header + html_start + fragment + html_end).encode('utf-8')

                    fmt_html = win32clipboard.RegisterClipboardFormat("HTML Format")
                    win32clipboard.SetClipboardData(fmt_html, html_payload)

                    # 2. MathML Presentation format
                    fmt_mml = win32clipboard.RegisterClipboardFormat("MathML Presentation")
                    win32clipboard.SetClipboardData(fmt_mml, mathml_str.encode("utf-8"))

                # 3. Plain text OMML XML
                win32clipboard.SetClipboardText(omml_str, win32clipboard.CF_UNICODETEXT)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            try:
                from PyQt5.QtWidgets import QApplication
                QApplication.clipboard().setText(omml_str)
                return True
            except Exception:
                return False

    # ------ DEDICATED LATEX STUDIO BACKEND API (NEW DIRECT COMPILER) ------
    @pyqtSlot(str, result=str)
    def compile_latex_studio_json(self, latex_str):
        """
        Direct AST compiler for the LaTeX tab.
        Completely decoupled from MML2OMML.XSL and latex2mathml.
        """
        res = latex_omml_engine.compile_raw_latex_for_studio(latex_str)
        return json.dumps(res)

    @pyqtSlot(str, result=str)
    def export_latex_studio_docx(self, latex_str):
        """
        Exports the compiled raw LaTeX directly to a Microsoft Word .docx file.
        """
        try:
            out_dir = self.window.output_dir or self.window.last_output_dir or tempfile.gettempdir()
            if not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)

            file_name = f"LaTeX_OMML_{int(time.time())}.docx"
            file_path = os.path.join(out_dir, file_name)

            docx_bytes = latex_omml_engine.build_studio_docx_bytes(latex_str)
            with open(file_path, 'wb') as f:
                f.write(docx_bytes)

            return json.dumps({"success": True, "file_path": file_path, "filename": file_name})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ------ DEDICATED IMAGE STUDIO BACKEND API ------
    @pyqtSlot(str, result=str)
    def convert_image_latex_to_omml_json(self, latex_str):
        res = latex_omml_engine.compile_raw_latex_for_studio(latex_str)
        if res.get("success", False):
            return json.dumps(res)
        if not self.window.xslt_transform:
            self.window.detect_xslt()
        if self.window.xslt_transform:
            return json.dumps(convert_latex_snippet_to_omml(latex_str, self.window.xslt_transform))
        return json.dumps(res)

    @pyqtSlot(str, result=str)
    def save_image_latex_to_docx(self, latex_str):
        return self.export_latex_studio_docx(latex_str)

    @pyqtSlot(str, result=str)
    def save_latex_to_docx(self, latex_str):
        return self.export_latex_studio_docx(latex_str)

    @pyqtSlot(result=str)
    def get_readme_markdown(self):
        """Read the live README.md file directly from disk and return its verbatim text."""
        try:
            readme_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "README.md")
            if not os.path.exists(readme_path):
                readme_path = os.path.abspath("README.md")
            if os.path.exists(readme_path):
                with open(readme_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"[get_readme_markdown] Error reading README.md: {e}")
        return ""

    @pyqtSlot(str, result=bool)
    def copy_text_to_clipboard(self, text):
        """Copy arbitrary plain text directly to the Windows OS clipboard."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"[copy_text_to_clipboard] Error: {e}")
            return False
    # ---------------------------------------------------
        
    @pyqtSlot(result=str)
    def get_theme(self):
        return getattr(self.window, 'current_theme', 'dark')

    @pyqtSlot(str)
    def set_theme(self, theme):
        self.window.on_theme_changed(theme)

    @pyqtSlot()
    def select_files(self):
        self.window.select_files()

    @pyqtSlot()
    def start_conversion(self):
        self.window.start_conversion()

    @pyqtSlot(str)
    def open_url(self, url_str):
        if url_str:
            QDesktopServices.openUrl(QUrl(url_str))

    @pyqtSlot()
    def open_folder(self):
        self.window.open_folder()

    @pyqtSlot()
    def reload(self):
        self.window._batch_gen = getattr(self.window, '_batch_gen', 0) + 1
        self.window.current_preview_file = None
        self.window.current_preview_req_id = -1
        if hasattr(self.window, 'word_engine') and self.window.word_engine:
            self.window.word_engine.cancel_pending_requests()
        self.window.cache_manager.clear()
        self.window.input_files.clear()
        self.window.output_paths.clear()
        self.window.run_js("if(typeof setFileNotice === 'function') setFileNotice('idle');")
        
        for temp_file in self.window.preview_temp_files:
            if os.path.exists(temp_file):
                try: 
                    os.remove(temp_file)
                except Exception: 
                    pass
        self.window.preview_temp_files.clear()
        
        try:
            profile = QWebEngineProfile.defaultProfile()
            profile.clearHttpCache()
            profile.clearAllVisitedLinks()
        except Exception: 
            pass
        
        QProcess.startDetached(sys.executable, sys.argv)
        QApplication.quit()

    @pyqtSlot(int, bool)
    def preview_file(self, index, is_output):
        if is_output and index < len(self.window.output_paths):
            self.window.preview_file(self.window.output_paths[index])
        elif not is_output and index < len(self.window.input_files):
            self.window.preview_file(self.window.input_files[index])

    @pyqtSlot(int)
    def remove_file(self, index):
        if index < len(self.window.input_files):
            self.window._batch_gen = getattr(self.window, '_batch_gen', 0) + 1
            removed_file = self.window.input_files[index]
            del self.window.input_files[index]
            self.window.update_js_lists()
            
            if len(self.window.input_files) == 0:
                self.window.current_preview_file = None
                self.window.current_preview_req_id = -1
                if hasattr(self.window, 'word_engine') and self.window.word_engine:
                    self.window.word_engine.cancel_pending_requests()
                self.window.output_paths.clear()
                self.window.run_js("if(typeof hidePdfPreview === 'function') hidePdfPreview();")
                self.window.run_js("if(typeof setFileNotice === 'function') setFileNotice('idle');")
            elif getattr(self.window, 'current_preview_file', None) == removed_file:
                self.window.preview_file(self.window.input_files[0])


class WebMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.launch_time = time.time()
        self.loading_dismissed = False
        self.setWindowTitle(" ")
        # 16x16 100% transparent icon to guarantee Windows caption bar never renders any icon
        transparent_pixmap = QPixmap(16, 16)
        transparent_pixmap.fill(Qt.transparent)
        self.setWindowIcon(QIcon(transparent_pixmap))
        self.setFixedSize(1100, 700)
        self.setWindowFlags(
            (self.windowFlags() | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
            & ~Qt.WindowMaximizeButtonHint
        )
        self.setAcceptDrops(True) 
        self.setStyleSheet("background-color: #141518;")

        try:
            hwnd = int(self.winId())
            # Lock window size at Win32 OS level and hide title bar icon completely
            try:
                self._remove_titlebar_icon(hwnd)
            except Exception:
                pass
            # Enable Win32 immersive dark mode so Windows never creates/paints the window with a white background
            val = ctypes.c_int(1)
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
            except Exception:
                pass
            bg_color = DWORD(0x00181514)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(bg_color), ctypes.sizeof(bg_color))
            text_color = DWORD(0x00ECE8E6)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
        except Exception:
            pass
        
        self.settings = QSettings("QUAST", "LatexToOMML")
        self.last_input_dir = self.settings.value("last_input_dir", "")
        self.last_output_dir = self.settings.value("last_output_dir", "")
        self.current_theme = self.settings.value("app_theme", "dark")
        self._title_bar_is_light = False
        self._current_title_bar_bg = (20, 21, 24)
        self._current_title_bar_fg = (230, 232, 236)
        
        self.input_files = []
        self.output_paths = []
        self.cache_manager = PreviewCacheManager()
        self.preview_cache = self.cache_manager._memory_cache
        self.preview_temp_files = []
        self.current_preview_file = None
        self.current_preview_req_id = 0
        self._batch_gen = 0
        self.is_processing = False
        self.active_workers = []
        
        self.xslt_transform = None
        self.detect_xslt()
        self.setup_ui()

    def on_theme_changed(self, theme):
        self.current_theme = theme
        self.settings.setValue("app_theme", theme)
        if getattr(self, 'loading_dismissed', False):
            self.update_window_theme(theme, animated=True)

    def apply_title_bar_colors(self, bg_rgb, fg_rgb, is_dark_mode):
        self._current_title_bar_bg = bg_rgb
        self._current_title_bar_fg = fg_rgb
        self._title_bar_is_dark = is_dark_mode
        try:
            hwnd = int(self.winId())
            r, g, b = bg_rgb
            tr, tg, tb = fg_rgb
            bg_val = DWORD((b << 16) | (g << 8) | r)
            fg_val = DWORD((tb << 16) | (tg << 8) | tr)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(bg_val), ctypes.sizeof(bg_val))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(fg_val), ctypes.sizeof(fg_val))
            
            dark_val = ctypes.c_int(1 if is_dark_mode else 0)
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
            except Exception:
                pass
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(dark_val), ctypes.sizeof(dark_val))
            except Exception:
                pass
        except Exception:
            pass

    def animate_title_bar_theme(self, from_theme, to_theme, duration=500, easing=QEasingCurve.OutCubic):
        if from_theme == to_theme:
            return
            
        dark_bg = (20, 21, 24)       # #141518 (Loading Screen & Dark Theme)
        dark_fg = (230, 232, 236)    # #e6e8ec
        light_bg = (235, 237, 242)   # #ebedf2 (Main Window Light Theme)
        light_fg = (24, 28, 36)      # #181c24
        
        start_bg = dark_bg if from_theme == "dark" else light_bg
        start_fg = dark_fg if from_theme == "dark" else light_fg
        end_bg = light_bg if to_theme == "light" else dark_bg
        end_fg = light_fg if to_theme == "light" else dark_fg
        
        if hasattr(self, '_title_bar_anim') and self._title_bar_anim.state() == QVariantAnimation.Running:
            self._title_bar_anim.stop()
            
        self._title_bar_anim = QVariantAnimation(self)
        self._title_bar_anim.setDuration(duration)
        self._title_bar_anim.setStartValue(0.0)
        self._title_bar_anim.setEndValue(1.0)
        self._title_bar_anim.setEasingCurve(easing)
        
        def on_step(val):
            t = float(val)
            curr_bg = (
                int(start_bg[0] + (end_bg[0] - start_bg[0]) * t),
                int(start_bg[1] + (end_bg[1] - start_bg[1]) * t),
                int(start_bg[2] + (end_bg[2] - start_bg[2]) * t),
            )
            curr_fg = (
                int(start_fg[0] + (end_fg[0] - start_fg[0]) * t),
                int(start_fg[1] + (end_fg[1] - start_fg[1]) * t),
                int(start_fg[2] + (end_fg[2] - start_fg[2]) * t),
            )
            is_dark_state = (to_theme == "dark") if t >= 0.5 else (from_theme == "dark")
            self.apply_title_bar_colors(curr_bg, curr_fg, is_dark_state)
            
        def on_complete():
            is_dark = (to_theme == "dark")
            self.apply_title_bar_colors(end_bg, end_fg, is_dark)
            bg_hex = "#ebedf2" if to_theme == "light" else "#141518"
            self.setStyleSheet(f"background-color: {bg_hex};")
            if hasattr(self, 'central_widget'):
                self.central_widget.setStyleSheet(f"background-color: {bg_hex};")
                
        self._title_bar_anim.valueChanged.connect(on_step)
        self._title_bar_anim.finished.connect(on_complete)
        self._title_bar_anim.start()

    def update_window_theme(self, theme, animated=True):
        current_is_light = getattr(self, '_title_bar_is_light', False)
        target_is_light = (theme == "light")
        if animated and (current_is_light != target_is_light):
            from_th = "light" if current_is_light else "dark"
            self.animate_title_bar_theme(from_th, theme, duration=350)
            self._title_bar_is_light = target_is_light
        else:
            self._title_bar_is_light = target_is_light
            if theme == "light":
                self.apply_title_bar_colors((235, 237, 242), (24, 28, 36), False)
                self.setStyleSheet("background-color: #ebedf2;")
                if hasattr(self, 'central_widget'):
                    self.central_widget.setStyleSheet("background-color: #ebedf2;")
            else:
                self.apply_title_bar_colors((20, 21, 24), (230, 232, 236), True)
                self.setStyleSheet("background-color: #141518;")
                if hasattr(self, 'central_widget'):
                    self.central_widget.setStyleSheet("background-color: #141518;")
        
    def setup_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background-color: #141518;")
        self.setCentralWidget(self.central_widget)
        
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.web_view = QWebEngineView(self.central_widget)
        self.web_profile = QWebEngineProfile(self.web_view)
        self.interceptor = OfflineInterceptor()
        self.web_profile.setRequestInterceptor(self.interceptor)
        try:
            QWebEngineProfile.defaultProfile().setRequestInterceptor(self.interceptor)
        except Exception:
            pass

        self.web_page = SilentWebEnginePage(self.web_profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.page().setBackgroundColor(QColor(20, 21, 24))
        self.web_view.setAcceptDrops(False) 
        
        try:
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
            settings.setAttribute(QWebEngineSettings.PdfViewerEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
            settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        except Exception:
            pass

        # Register WebChannel BEFORE loading URL so transport is available immediately
        self.channel = QWebChannel()
        self.backend = Backend(self)
        self.channel.registerObject("backend", self.backend)
        self.web_view.page().setWebChannel(self.channel)

        # Connect loadFinished BEFORE loading URL to guarantee signal is never missed
        self.web_view.loadFinished.connect(self.on_load_finished)

        # Instant native loading overlay appearing immediately at application launch
        self.loading_overlay = QtLoadingOverlay(self.central_widget)
        self.loading_overlay.setGeometry(self.central_widget.rect())
        self.loading_overlay.raise_()
        self.on_preload_progress(20, "INITIALIZING GPU ACCELERATION...")

        ui_path = os.path.abspath(resource_path("UI/UI.html"))
        self.web_view.setUrl(QUrl.fromLocalFile(ui_path))
        main_layout.addWidget(self.web_view)
        # Robust Fallback Timeout: Guarantee dismiss after 9000ms so user is never blocked
        self.fallback_dismiss_timer = QTimer.singleShot(9000, self.on_preload_timeout_fallback)

        # Microsoft Edge WebView2 PDF Preview Host (Adobe Acrobat Engine)
        self.edge_pdf_viewer = EdgePdfPreviewHost(self.central_widget)
        self.edge_pdf_viewer.pdf_loaded_signal.connect(self.on_edge_pdf_loaded)
        self.edge_pdf_viewer.error_signal.connect(self.on_edge_pdf_error)
        
        # Pre-warmed Persistent Word COM Engine with integrated cache
        self.word_engine = PersistentWordPdfEngine(self, self.cache_manager)
        self.word_engine.finished_signal.connect(self.on_preview_ready)
        # Defer the Word COM pre-warm so the window appears first (Word's slow startup keeps Windows' busy cursor on)
        QTimer.singleShot(3000, self.word_engine.start)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith('.docx') for url in urls):
                event.acceptProposedAction()
                return
        event.ignore() 

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith('.docx') for url in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = [url.toLocalFile() for url in urls if url.toLocalFile().lower().endswith('.docx')]
        if paths:
            event.acceptProposedAction()
            self.run_js("if(typeof fadeOutDefaultView === 'function') fadeOutDefaultView();")
            self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(true, 'Processing...', 'Scanning document');")
            QTimer.singleShot(100, lambda: self.add_input_files(paths))
        else:
            event.ignore()

    def on_load_finished(self, ok):
        if ok:
            overlay_js = """
            window.quastShowLoader = function(show, title, subtext) {
                if (typeof showInlineLoader === 'function') {
                    showInlineLoader(show, title, false);
                }
            };
            """
            self.run_js(overlay_js)
            self.run_js(f"if(typeof applyTheme === 'function') applyTheme('{self.current_theme}');")
            self.update_js_lists()

            # Advance progress and trigger eager all-loading pre-rendering across all tabs
            if hasattr(self, 'loading_overlay') and not getattr(self, 'loading_dismissed', False):
                self.on_preload_progress(45, "LOADING VIEWS & ASSETS...")
            self.run_js("if(typeof window.quastStartEagerPreload === 'function') window.quastStartEagerPreload();")
        else:
            self.dismiss_loading_screen()

    def on_preload_progress(self, percent, message):
        if hasattr(self, 'loading_overlay') and not getattr(self, 'loading_dismissed', False):
            self.loading_overlay.update_progress(percent, message)

    def on_frontend_preload_complete(self):
        if getattr(self, 'loading_dismissed', False):
            return
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.update_progress(100, "ALL MODULES READY")
        # Visual confirmation delay (250ms) before fading out smoothly
        QTimer.singleShot(250, self.dismiss_loading_screen)

    def on_preload_timeout_fallback(self):
        if not getattr(self, 'loading_dismissed', False):
            self.dismiss_loading_screen()

    def dismiss_loading_screen(self):
        if getattr(self, 'loading_dismissed', False):
            return
        self.loading_dismissed = True

        if hasattr(self, 'loading_overlay') and self.loading_overlay.isVisible():
            # Stage 1: Text on loading screen fades out completely first
            self.anim_content = QPropertyAnimation(self.loading_overlay.content_opacity, b"opacity")
            self.anim_content.setDuration(280)
            self.anim_content.setStartValue(1.0)
            self.anim_content.setEndValue(0.0)
            self.anim_content.setEasingCurve(QEasingCurve.OutCubic)

            def on_content_disappeared():
                try:
                    self.loading_overlay.content_widget.hide()
                    self.loading_overlay.spinner.stop()
                except Exception:
                    pass

                def start_bg_fade():
                    # Stage 2: Loading screen background gradually fades out after text has completely disappeared
                    self.bg_opacity_effect = QGraphicsOpacityEffect(self.loading_overlay)
                    self.loading_overlay.setGraphicsEffect(self.bg_opacity_effect)

                    self.anim_bg = QPropertyAnimation(self.bg_opacity_effect, b"opacity")
                    self.anim_bg.setDuration(500)
                    self.anim_bg.setStartValue(1.0)
                    self.anim_bg.setEndValue(0.0)
                    self.anim_bg.setEasingCurve(QEasingCurve.OutCubic)

                    # SYNCHRONIZE TITLE BAR TRANSITION:
                    # If application is in Light Mode, activate fade-out / color transition from dark to light
                    # synchronized 100% in duration (500ms) and easing curve (OutCubic) with loading screen
                    if getattr(self, 'current_theme', 'dark') == "light":
                        self.animate_title_bar_theme("dark", "light", duration=500, easing=QEasingCurve.OutCubic)
                        self._title_bar_is_light = True
                    else:
                        self._title_bar_is_light = False

                    def on_bg_disappeared():
                        try:
                            self.loading_overlay.hide()
                        except Exception:
                            pass

                    self.anim_bg.finished.connect(on_bg_disappeared)
                    self.anim_bg.start()

                # Ensure text disappears completely before background begins fading out
                QTimer.singleShot(100, start_bg_fade)

            self.anim_content.finished.connect(on_content_disappeared)
            self.anim_content.start()
        else:
            pass

    def detect_xslt(self):
        xslt = locate_xslt()
        if xslt:
            parser = etree.XMLParser(recover=True)
            self.xslt_transform = etree.XSLT(etree.parse(xslt, parser))

    def select_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Word Files", self.last_input_dir, "Word Documents (*.docx)")
        if paths:
            if hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available:
                self.edge_pdf_viewer.set_viewer_visible(False)
            self.run_js("if(typeof fadeOutDefaultView === 'function') fadeOutDefaultView();")
            self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(true, 'Processing...', 'Scanning document');")
            self.add_input_files(paths)

    def add_input_files(self, paths):
        if not paths: 
            return
        new_dir = os.path.dirname(paths[0])
        self.settings.setValue("last_input_dir", new_dir)
        self.last_input_dir = new_dir
        
        if self.output_paths:
            self._batch_gen += 1
            self.input_files.clear()
            self.output_paths.clear()
            self.current_preview_file = None
            self.current_preview_req_id = -1
            if hasattr(self, 'word_engine') and self.word_engine:
                self.word_engine.cancel_pending_requests()
            if hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available:
                self.edge_pdf_viewer.set_viewer_visible(False)
        
        existing_names = {os.path.basename(f) for f in self.input_files}
        new_paths = []
        for p in paths:
            norm_p = os.path.normpath(os.path.abspath(p))
            name = os.path.basename(norm_p)
            if name not in existing_names:
                new_paths.append(norm_p)
                existing_names.add(name)
                
        if not new_paths: 
            self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")
            return
        
        self._batch_gen += 1
        gen = self._batch_gen
        self.input_files.extend(new_paths)
        self.update_js_lists()
        
        if new_paths:
            self.run_js("if(typeof fadeOutDefaultView === 'function') fadeOutDefaultView();")
            self.preview_file(new_paths[0])
            if not getattr(self, 'is_processing', False) and len(self.output_paths) == 0:
                self.run_js("if(typeof setFileNotice === 'function') setFileNotice('ready');")
            # Pre-cache remaining input files with short debounce to grant active file 100% priority
            if len(new_paths) > 1:
                rem_in = list(new_paths[1:])
                QTimer.singleShot(600, lambda g=gen, files=rem_in: [
                    self.word_engine.request_preview(p, is_active=False)
                    for p in files
                    if g == self._batch_gen
                    and p in self.input_files
                    and hasattr(self, 'word_engine')
                    and not self.word_engine.stopping
                ])

    def update_js_lists(self):
        in_files = [os.path.basename(f) for f in self.input_files]
        out_files = [os.path.basename(f) for f in self.output_paths]
        
        allow_remove = len(self.output_paths) == 0 and not getattr(self, 'is_processing', False)
        active_in_idx, active_out_idx = -1, -1
        current_file = getattr(self, 'current_preview_file', None)
        
        if current_file:
            norm_curr = os.path.normcase(os.path.normpath(current_file))
            for i, p in enumerate(self.input_files):
                if os.path.normcase(os.path.normpath(p)) == norm_curr:
                    active_in_idx = i
                    break
            for i, p in enumerate(self.output_paths):
                if os.path.normcase(os.path.normpath(p)) == norm_curr:
                    active_out_idx = i
                    break
        
        self.run_js(f"if(typeof setFileList === 'function') setFileList('input-file-list', {json.dumps(in_files)}, {str(allow_remove).lower()}, false, {active_in_idx})")
        self.run_js(f"if(typeof setFileList === 'function') setFileList('output-file-list', {json.dumps(out_files)}, false, false, {active_out_idx})")

    def run_js(self, js_code):
        self.web_view.page().runJavaScript(js_code)

    def start_conversion(self):
        if not self.input_files or not locate_xslt():
            self.run_js("if(typeof resetStartButton === 'function') resetStartButton();")
            return
        
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.last_output_dir)
        if not dir_path: 
            self.run_js("if(typeof resetStartButton === 'function') resetStartButton();")
            return
            
        self.run_js("if(typeof resetStartButton === 'function') resetStartButton();")
        
        self.output_dir = dir_path
        self.settings.setValue("last_output_dir", self.output_dir)
        self.last_output_dir = self.output_dir
        
        # Immediately hide native Edge PDF viewer in Python to avoid HWND overlay/clipping
        if hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available:
            self.edge_pdf_viewer.set_viewer_visible(False)
        
        # Cancel any pending background Word COM preview tasks immediately
        self._batch_gen += 1
        self.current_preview_req_id = -1
        if hasattr(self, 'word_engine') and self.word_engine:
            self.word_engine.cancel_pending_requests()
        
        self.is_processing = True
        self.update_js_lists()
        
        self.run_js("if(typeof setFileNotice === 'function') setFileNotice('processing');")
        self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(true, 'Processing...', 'Applying Math Transformations');")
        
        def start_worker():
            self.worker = ConversionWorker(self.input_files, self.output_dir, locate_xslt())
            self.worker.progress_signal.connect(lambda val: self.run_js(f"if(typeof updateProgress === 'function') updateProgress({val})"))
            self.worker.finished_signal.connect(self.on_conversion_finished)
            self.worker.start()
            
        QTimer.singleShot(10, start_worker)

    def on_conversion_finished(self, success, result):
        self.is_processing = False
        
        if success:
            self._batch_gen += 1
            gen = self._batch_gen
            self.output_paths = result
            self.update_js_lists()
            if self.output_paths:
                # Preview first converted file (automatically hits cache or opens loader)
                self.preview_file(self.output_paths[0])
                # Quietly pre-cache remaining converted files with short debounce
                if len(self.output_paths) > 1:
                    rem_out = list(self.output_paths[1:])
                    QTimer.singleShot(600, lambda g=gen, files=rem_out: [
                        self.word_engine.request_preview(p, is_active=False)
                        for p in files
                        if g == self._batch_gen
                        and p in self.output_paths
                        and hasattr(self, 'word_engine')
                        and not self.word_engine.stopping
                    ])
            else:
                self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")
        else:
            self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")
            self.run_js("if(typeof setFileNotice === 'function') setFileNotice('error');")
            err_msg = str(result[0]).replace("'", "\'").replace("\n", " ")
            self.run_js(f"console.error('Conversion exception: {err_msg}');")
            self.update_js_lists()
            QMessageBox.critical(self, "Error occurred", f"Internal exception:\n{result[0]}")

    def open_folder(self):
        if self.output_dir and os.path.exists(self.output_dir):
            try: 
                os.startfile(self.output_dir)
            except Exception: 
                pass

    def _remove_titlebar_icon(self, hwnd=None):
        try:
            if hwnd is None:
                hwnd = int(self.winId())
            GWL_STYLE = -16
            GWL_EXSTYLE = -20
            WS_MAXIMIZEBOX = 0x00010000
            WS_THICKFRAME = 0x00040000
            WS_EX_DLGMODALFRAME = 0x00000001
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            GCLP_HICON = -14
            GCLP_HICONSM = -34

            # Lock window size (remove maximize button and resize borders)
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~WS_MAXIMIZEBOX
            style &= ~WS_THICKFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            # Set WS_EX_DLGMODALFRAME so Windows suppresses caption icon
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_DLGMODALFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)

            # Clear class icons so Windows never falls back to any class icon
            try:
                SetClassLongPtr = getattr(ctypes.windll.user32, 'SetClassLongPtrW', ctypes.windll.user32.SetClassLongW)
                SetClassLongPtr(hwnd, GCLP_HICONSM, 0)
                SetClassLongPtr(hwnd, GCLP_HICON, 0)
            except Exception:
                pass

            ctypes.windll.user32.SetWindowTextW(hwnd, "")
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self._remove_titlebar_icon()
        except Exception:
            pass
        if hasattr(self, 'loading_overlay') and self.loading_overlay.isVisible():
            self.loading_overlay.setGeometry(self.central_widget.rect())
            self.loading_overlay.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay') and self.loading_overlay.isVisible():
            self.loading_overlay.setGeometry(self.central_widget.rect())
            self.loading_overlay.raise_()
        self.run_js("if(typeof syncEdgePdfViewerRect === 'function') syncEdgePdfViewerRect();")

    def on_edge_pdf_loaded(self, path):
        self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")
        self.run_js("if(typeof syncEdgePdfViewerRect === 'function') syncEdgePdfViewerRect();")

    def on_edge_pdf_error(self, err):
        self.run_js(f"console.error('Edge PDF Viewer error: {err}');")

    def _display_pdf_preview(self, file_path, pdf_path, is_partial, is_output_file):
        is_native_edge = bool(hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available)
        pdf_url = QUrl.fromLocalFile(pdf_path).toString()
        if is_native_edge:
            self.edge_pdf_viewer.load_pdf(pdf_path)
            self.edge_pdf_viewer.set_viewer_visible(True)
        self.run_js(f"if(typeof showPdfPreview === 'function') showPdfPreview({json.dumps(pdf_url)}, {json.dumps(is_native_edge)});")
        self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")

        if is_output_file:
            if is_partial:
                self.run_js("if(typeof setFileNotice === 'function') setFileNotice('rendering_full');")
            else:
                self.run_js("if(typeof setFileNotice === 'function') setFileNotice('done');")
        else:
            self.run_js("if(typeof setFileNotice === 'function') setFileNotice('ready');")

    def preview_file(self, file_path):
        if not file_path or not os.path.exists(file_path):
            return
            
        file_path = os.path.normpath(os.path.abspath(file_path))
        self.current_preview_file = file_path
        self.update_js_lists()

        is_output_file = any(
            os.path.normcase(os.path.abspath(file_path)) == os.path.normcase(os.path.abspath(p))
            for p in getattr(self, 'output_paths', [])
        )
        
        # 1. Instant Cache Check (<5ms) for full PDF or cached 3-page partial PDF
        cached_pdf, is_partial = self.cache_manager.get_cached_preview(file_path)
        if cached_pdf:
            if not is_partial:
                # Invalidate any older in-flight render request so it cannot overwrite this cached file
                self.current_preview_req_id = -1
                if hasattr(self, 'word_engine') and self.word_engine:
                    self.word_engine.clear_active_request()
                self._display_pdf_preview(file_path, cached_pdf, is_partial=False, is_output_file=is_output_file)
                return

            # Partial (_p3.pdf) hit: display immediately with zero re-render and upgrade Stage 2 in background
            self._display_pdf_preview(file_path, cached_pdf, is_partial=True, is_output_file=is_output_file)
            self.current_preview_req_id = self.word_engine.request_preview(file_path, is_active=True, stage2_only=True)
            return
            
        # 2. Cache Miss -> Immediately hide Edge viewer so spinner is 100% visible
        if hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available:
            self.edge_pdf_viewer.set_viewer_visible(False)
        self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(true, 'Rendering preview...', 'Generating document preview');")
        
        if is_output_file:
            self.run_js("if(typeof setFileNotice === 'function') setFileNotice('rendering_full');")
        else:
            self.run_js("if(typeof setFileNotice === 'function') setFileNotice('ready');")
        
        # 3. Request background PDF export directly into cache
        self.current_preview_req_id = self.word_engine.request_preview(file_path, is_active=True)

    def on_preview_ready(self, req_id, success, docx_path, pdf_path, error_msg):
        curr_file = getattr(self, 'current_preview_file', None)
        is_same_file = (
            curr_file is not None
            and docx_path
            and os.path.normcase(os.path.abspath(docx_path)) == os.path.normcase(os.path.abspath(curr_file))
        )
        if not is_same_file:
            return

        if not success:
            if getattr(self, 'current_preview_req_id', None) == req_id:
                self.run_js("if(typeof showPreviewLoader === 'function') showPreviewLoader(false);")
                err_clean = str(error_msg).replace("'", "\'").replace("\n", " ")
                self.run_js(f"console.error('Preview error: {err_clean}');")
                self.run_js("if(typeof setFileNotice === 'function') setFileNotice('done');")
                if hasattr(self, 'edge_pdf_viewer') and self.edge_pdf_viewer.is_available:
                    self.edge_pdf_viewer.set_viewer_visible(False)
            return

        is_partial = pdf_path.endswith("_p3.pdf")
        if getattr(self, 'current_preview_req_id', None) == req_id or not is_partial:
            is_output_file = any(
                os.path.normcase(os.path.abspath(docx_path)) == os.path.normcase(os.path.abspath(p))
                for p in getattr(self, 'output_paths', [])
            )
            self._display_pdf_preview(docx_path, pdf_path, is_partial=is_partial, is_output_file=is_output_file)


    def closeEvent(self, event):
        # 1. Immediately hide window to eliminate any user-perceived freezing or lag
        self.hide()
        event.accept()

        # 2. Fast non-blocking stop of background Word COM engine
        if hasattr(self, 'word_engine'):
            try:
                self.word_engine.stop(timeout_ms=2500)
            except Exception:
                pass
            
        # 3. Fast destruction of Edge PDF viewer
        if hasattr(self, 'edge_pdf_viewer'):
            try:
                self.edge_pdf_viewer.destroy_viewer()
            except Exception:
                pass

        # 4. Request fast interruption on any active workers without blocking UI
        for w in getattr(self, 'active_workers', []):
            try:
                if w.isRunning():
                    w.requestInterruption()
                    w.wait(50)
            except Exception:
                pass

        # 5. Fast clean up of temporary preview files
        for temp_file in getattr(self, 'preview_temp_files', []):
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception: 
                pass
        
        super().closeEvent(event)


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings, True)
    
    # Configure QSurfaceFormat for VSync to synchronize rendering frame rate with monitor native refresh rate (e.g., 60Hz, 120Hz, 144Hz, 240Hz)
    surface_format = QSurfaceFormat.defaultFormat()
    surface_format.setSwapInterval(1)  # Synchronize buffer swap with monitor VSync
    QSurfaceFormat.setDefaultFormat(surface_format)

    # Enable GPU hardware acceleration and match native display refresh rate without FPS capping
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--enable-gpu-rasterization "
        "--enable-zero-copy "
        "--enable-accelerated-2d-canvas "
        "--ignore-gpu-blocklist "
        "--disable-gpu-vsync=0"
    )
    
    # Set Windows AppUserModelID so taskbar and Alt+Tab display the custom app icon
    try:
        myappid = "quast.latex2omml.app.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # Pre-set dark palette and background before any window is shown to eliminate Windows default white background flash
    dark_bg = QColor(20, 21, 24)  # #141518
    palette = app.palette()
    palette.setColor(QPalette.Window, dark_bg)
    palette.setColor(QPalette.Base, dark_bg)
    palette.setColor(QPalette.AlternateBase, dark_bg)
    palette.setColor(QPalette.WindowText, QColor(230, 232, 236))
    app.setPalette(palette)
    app.setStyleSheet("QMainWindow, QWidget { background-color: #141518; }")
    
    def global_exception_handler(exc_type, exc_value, exc_traceback):
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        with open(os.path.join(tempfile.gettempdir(), "quast_crash.log"), "w") as f:
            f.write(error_msg)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        
    sys.excepthook = global_exception_handler

    try:
        window = WebMainWindow()
        window.show()
        sys.exit(app.exec_())
    except Exception:
        sys.exit(1)