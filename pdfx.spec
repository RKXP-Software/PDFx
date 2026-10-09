# -*- mode: python ; coding: utf-8 -*-
# Empacotamento do PDFx com PyInstaller (modo pasta: inicia mais rápido que o modo arquivo único).

a = Analysis(
    ["pdfx/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[("pdfx/resources/pdfx.ico", "pdfx/resources"), ("pdfx/resources/pdfx.png", "pdfx/resources")],
    hiddenimports=[],
    excludes=[
        "tkinter", "unittest", "pydoc", "PIL",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
        "PySide6.QtMultimedia", "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtPdf", "PySide6.Qt3DCore",
    ],
    noarchive=False,
)
# Plugins e DLLs do Qt que o PDFx não usa (QML/Quick, teclado virtual, OpenGL por software, PDF do Qt).
UNUSED = ("qt6qml", "qt6quick", "qt6virtualkeyboard", "qt6pdf", "qt6network", "qt6opengl", "opengl32sw",
          "qtvirtualkeyboardplugin", "qpdf.dll", "qtuiotouchplugin")
a.binaries = [b for b in a.binaries if not any(u in b[0].lower().replace("\\", "/").split("/")[-1] for u in UNUSED)]
a.datas = [d for d in a.datas if "translations" not in d[0].lower() or "qtbase_pt" in d[0].lower()]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PDFx",
    icon="pdfx/resources/pdfx.ico",
    console=False,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="PDFx", upx=False)
