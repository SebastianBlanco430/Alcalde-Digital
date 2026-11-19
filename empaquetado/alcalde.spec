# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para Alcalde Digital. Variante por entorno: ALCALDE_MODO = onefile | onedir (por defecto onedir -> .app en macOS)
import os, sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

RAIZ = Path(os.environ["ALCALDE_RAIZ"]) if os.environ.get("ALCALDE_RAIZ") else Path(SPECPATH).parent   # el spec vive en <repo>/empaquetado/
sys.path.insert(0, str(RAIZ))   # sin esto collect_submodules("frontend"/"backend") no los encuentra (solo pathex afecta a Analysis)
MODO = os.environ.get("ALCALDE_MODO", "onedir")
NOMBRE = "AlcaldeDigital"

datas, binaries, hiddenimports = [], [], []
for paquete in ("ursina", "panda3d", "direct", "panda3d_gltf", "gltf", "simplepbr", "psutil", "panda3d_simplepbr"):
    try:
        d, b, h = collect_all(paquete)
    except Exception:
        continue
    datas += d; binaries += b; hiddenimports += h
hiddenimports += collect_submodules("frontend") + collect_submodules("backend")

# Recursos propios (los modulos usan Path(__file__).parent[.parent]/..., asi que se conserva la misma estructura)
datas.append((str(RAIZ / "assets"), "assets"))
for ruta in (RAIZ / "backend").rglob("*"):
    if ruta.is_file() and ruta.suffix not in (".py", ".pyc") and "__pycache__" not in ruta.parts and ruta.name != ".gitkeep":
        datas.append((str(ruta), str(Path("backend") / ruta.relative_to(RAIZ / "backend").parent)))

a = Analysis([str(RAIZ / "main.py")], pathex=[str(RAIZ)], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=["pytest", "tkinter", "unittest"], noarchive=False)
# Binarios solo-x86_64/i386 del wheel de Panda3D en macOS (libRocket, Cg): inutiles aqui y rompen el build arm64/universal2
def _fuera(nombre):
    n = nombre.lower()
    return "rocket" in n or "libcg." in n
if sys.platform == "darwin":
    a.binaries = [t for t in a.binaries if not _fuera(t[0])]
    a.datas = [t for t in a.datas if not _fuera(t[0])]
pyz = PYZ(a.pure)
icono = os.environ.get("ALCALDE_ICONO") or None

if MODO == "onefile":
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name=NOMBRE, console=False if sys.platform != "linux" else True, target_arch=os.environ.get("ALCALDE_ARCH") or None,
              upx=False, icon=icono)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=NOMBRE, console=False, target_arch=os.environ.get("ALCALDE_ARCH") or None, upx=False, icon=icono)
    coll = COLLECT(exe, a.binaries, a.datas, name=NOMBRE, upx=False)
    if sys.platform == "darwin":
        app = BUNDLE(coll, name=NOMBRE + ".app", icon=icono, bundle_identifier="app.alcaldedigital.juego",
                     info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0"})
