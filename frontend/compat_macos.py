# Compatibilidad de Ursina con macOS.
# macOS entrega por defecto un contexto OpenGL 2.1 (GLSL 1.20), pero los shaders
# de Ursina están escritos en GLSL 1.30/1.40 y ahí no compilan (ventana negra).
# Se reescriben a 1.20 con la clase Shader de Ursina para que se vea igual que
# en Windows.

import gc
import re
import sys

from ursina import Entity, window
from ursina.shader import Shader

_RE_SALIDA_FRAGMENTO = re.compile(r"^\s*out\s+vec4\s+(\w+)\s*;\s*$", re.M)


def _a_glsl_120(vertex, fragment):
    # Devuelve (vertex, fragment) en GLSL 1.20; si ya están en 1.20 no cambia nada.
    if "#version 120" in vertex:
        return vertex, fragment
    vertex = re.sub(r"#version\s+1[34]0", "#version 120", vertex)
    vertex = re.sub(r"^(\s*)in\s+", r"\1attribute ", vertex, flags=re.M)
    vertex = re.sub(r"^(\s*)out\s+", r"\1varying ", vertex, flags=re.M)

    fragment = re.sub(r"#version\s+1[34]0", "#version 120", fragment)
    salida = _RE_SALIDA_FRAGMENTO.search(fragment)
    if salida:
        fragment = _RE_SALIDA_FRAGMENTO.sub("", fragment)
        fragment = re.sub(rf"\b{salida.group(1)}\b(?=\s*[.=])", "gl_FragColor", fragment)
    fragment = re.sub(r"^(\s*)in\s+", r"\1varying ", fragment, flags=re.M)
    fragment = re.sub(r"\btexture\(", "texture2D(", fragment)
    return vertex, fragment


def _adaptar(shader):
    if isinstance(shader.vertex, str) and isinstance(shader.fragment, str):
        shader.vertex, shader.fragment = _a_glsl_120(shader.vertex, shader.fragment)


def aplicar():
    # Debe llamarse antes de crear Ursina(); después hay que llamar a reaplicar().
    if sys.platform != "darwin":
        return
    compilar_original = Shader.compile

    def compilar(self, *args, **kwargs):
        _adaptar(self)
        return compilar_original(self, *args, **kwargs)

    Shader.compile = compilar
    for shader in [o for o in gc.get_objects() if isinstance(o, Shader)]:
        _adaptar(shader)
        shader.compiled = False


def reaplicar():
    # Las entidades raíz de Ursina (scene, camera.ui) se crean al importar con el
    # shader viejo ya compilado; al reasignarlo se recompila en GLSL 1.20.
    if sys.platform != "darwin":
        return
    for entidad in [o for o in gc.get_objects() if isinstance(o, Entity)]:
        if isinstance(entidad.shader, Shader):
            entidad.shader = entidad.shader
    # En macOS Panda3D no emite 'aspectRatioChanged' al abrir la ventana, así que
    # la cámara de la UI se queda con su tamaño inicial (1x1) y todo se ve enorme.
    window.update_aspect_ratio()
