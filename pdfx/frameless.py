"""Janela sem a barra de título do Windows, usando a headerbar no lugar (como no GNOME).

Mantém os comportamentos nativos: sombra, redimensionar pelas bordas, Aero Snap,
arrastar pela barra e duplo clique para maximizar. Defina PDFX_NATIVE_FRAME=1 para
voltar à moldura padrão do Windows.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
HTCAPTION = 2
HTLEFT, HTRIGHT, HTTOP, HTTOPLEFT, HTTOPRIGHT = 10, 11, 12, 13, 14
HTBOTTOM, HTBOTTOMLEFT, HTBOTTOMRIGHT = 15, 16, 17
GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU = 0x00080000
SWP_FLAGS = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
SM_CXSIZEFRAME, SM_CYSIZEFRAME, SM_CXPADDEDBORDER = 32, 33, 92
BORDER = 6  # largura (lógica) da área de redimensionamento


def enabled() -> bool:
    return sys.platform == "win32" and os.environ.get("PDFX_NATIVE_FRAME") != "1"


if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = ctypes.c_long
    _user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    _user32.SetWindowLongW.restype = ctypes.c_long
    _user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.IsZoomed.argtypes = [wintypes.HWND]
    try:
        _user32.GetDpiForWindow.argtypes = [wintypes.HWND]
    except AttributeError:
        pass
    try:
        _dwmapi = ctypes.windll.dwmapi
        _dwmapi.DwmExtendFrameIntoClientArea.argtypes = [wintypes.HWND, ctypes.c_void_p]
    except (OSError, AttributeError):
        _dwmapi = None

    class _MARGINS(ctypes.Structure):
        _fields_ = [("left", ctypes.c_int), ("right", ctypes.c_int), ("top", ctypes.c_int), ("bottom", ctypes.c_int)]

    class _NCCALCSIZE_PARAMS(ctypes.Structure):
        _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


def _frame_thickness(hwnd: int) -> tuple[int, int]:
    try:
        dpi = _user32.GetDpiForWindow(hwnd)
        pad = _user32.GetSystemMetricsForDpi(SM_CXPADDEDBORDER, dpi)
        return (_user32.GetSystemMetricsForDpi(SM_CXSIZEFRAME, dpi) + pad,
                _user32.GetSystemMetricsForDpi(SM_CYSIZEFRAME, dpi) + pad)
    except AttributeError:
        pad = _user32.GetSystemMetrics(SM_CXPADDEDBORDER)
        return _user32.GetSystemMetrics(SM_CXSIZEFRAME) + pad, _user32.GetSystemMetrics(SM_CYSIZEFRAME) + pad


class FramelessMixin:
    """Misture em um QMainWindow e chame _setup_frameless(header) no __init__."""

    _frameless = False

    def _setup_frameless(self, header) -> None:
        self._frameless_header = header
        if not enabled():
            return
        self._frameless = True
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self._apply_native_style()

    def _apply_native_style(self) -> None:
        if not self._frameless:
            return
        hwnd = int(self.winId())
        style = _user32.GetWindowLongW(hwnd, GWL_STYLE)
        style |= WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
        _user32.SetWindowLongW(hwnd, GWL_STYLE, style)
        if _dwmapi is not None:
            margins = _MARGINS(1, 1, 1, 1)  # mantém a sombra da janela
            _dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        _user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)

    def nativeEvent(self, event_type, message):
        if not self._frameless:
            return super().nativeEvent(event_type, message)
        try:
            msg = wintypes.MSG.from_address(int(message))
        except (TypeError, ValueError):
            return super().nativeEvent(event_type, message)

        if msg.message == WM_NCCALCSIZE:
            if msg.wParam and _user32.IsZoomed(msg.hWnd) and not self.isFullScreen():
                # Maximizada: o Windows estende a janela além da tela pela espessura da borda.
                params = ctypes.cast(msg.lParam, ctypes.POINTER(_NCCALCSIZE_PARAMS)).contents
                tx, ty = _frame_thickness(msg.hWnd)
                params.rgrc[0].left += tx
                params.rgrc[0].right -= tx
                params.rgrc[0].top += ty
                params.rgrc[0].bottom -= ty
            return True, 0

        if msg.message == WM_NCHITTEST:
            pos = QCursor.pos()
            x, y = pos.x() - self.x(), pos.y() - self.y()
            w, h = self.width(), self.height()
            if not self.isMaximized() and not self.isFullScreen():
                left, right = x < BORDER, x >= w - BORDER
                top, bottom = y < BORDER, y >= h - BORDER
                if top and left:
                    return True, HTTOPLEFT
                if top and right:
                    return True, HTTOPRIGHT
                if bottom and left:
                    return True, HTBOTTOMLEFT
                if bottom and right:
                    return True, HTBOTTOMRIGHT
                if left:
                    return True, HTLEFT
                if right:
                    return True, HTRIGHT
                if top:
                    return True, HTTOP
                if bottom:
                    return True, HTBOTTOM
            header = self._frameless_header
            if header.isVisible() and not self.isFullScreen():
                local = header.mapFrom(self, self.mapFromGlobal(pos))
                if header.rect().contains(local) and header.is_drag_area(header.childAt(local)):
                    return True, HTCAPTION
        return super().nativeEvent(event_type, message)

    def _frameless_state_changed(self) -> None:
        """O Qt redefine o estilo nativo ao sair da tela cheia; reaplica."""
        self._apply_native_style()
