# Skinning por GPU para los personajes con modelo .glb (Actor de Panda3D).
#
# Rendimiento (medido con PStats en Windows, RTX 2050): sin esto Panda deforma en la CPU los vértices
# de cada personaje visible en cada frame («Animation > Skinning» ~16 ms/frame con el jugador y los 12
# peatones), que era el mayor costo del frame. Aquí el vértice se deforma en el shader con la tabla
# de huesos (p3d_TransformTable) que Panda le pasa: la CPU solo calcula los huesos.
#
# El shader es una copia EXACTA del unlit_shader de Ursina (el que ya usaban los Actor) más la suma
# ponderada de huesos en el vertex shader; el fragment shader es el mismo, así que el color no cambia.
# Solo se aplica a los GeomNode con animación de vértices: lo demás (rostro, mochila) sigue igual.
#
# Bandera: SKINNING_GPU = False (o ALCALDE_SKINNING_CPU=1) vuelve al skinning de siempre por CPU. Si el
# shader no compila o algo falla, se avisa una vez y el personaje queda como estaba.
#
# Punto 5 del pulido (ALCALDE_TOON_PERSONAJES, frontend/toon_calculos.py): con la bandera encendida se usa la variante
# TOON (_VERTEX_TOON/_FRAGMENT_TOON, más abajo): 2 bandas luz/sombra + borde de luz. Apagada (=0) se usa el shader de
# arriba, con el texto idéntico al de antes. Si el toon no compila, se avisa una vez y se usa el de arriba (no la CPU).
# Los uniforms del toon los pone frontend/registro_toon_personajes.py según la hora del cielo.

import os
import sys

from panda3d.core import GeomVertexAnimationSpec, Shader, ShaderAttrib

from frontend import toon_calculos as toon

SKINNING_GPU = True
MAX_HUESOS = 128               # tamaño de p3d_TransformTable (los rigs de assets/modelos/personajes usan menos)

_VERTEX = f'''#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_TransformTable[{MAX_HUESOS}];
in vec4 p3d_Vertex;
in vec4 transform_weight;
in uvec4 transform_index;
in vec2 p3d_MultiTexCoord0;
out vec2 uvs;
uniform vec2 texture_scale;
uniform vec2 texture_offset;

in vec4 p3d_Color;
out vec4 vertex_color;

void main() {{
    mat4 hueso = p3d_TransformTable[transform_index.x] * transform_weight.x
               + p3d_TransformTable[transform_index.y] * transform_weight.y
               + p3d_TransformTable[transform_index.z] * transform_weight.z
               + p3d_TransformTable[transform_index.w] * transform_weight.w;
    gl_Position = p3d_ModelViewProjectionMatrix * (hueso * p3d_Vertex);
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
}}
'''

# Idéntico al fragment de ursina.shaders.unlit_shader.
_FRAGMENT = '''#version 140

uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
in vec2 uvs;
out vec4 fragColor;

in vec4 vertex_color;

void main() {
    vec4 color = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
    fragColor = color;
}
'''

# macOS entrega un contexto OpenGL 2.1 (GLSL 1.20): los shaders de arriba (1.30/1.40) no compilan allí y los
# personajes salían blancos (el vértice se pintaba con el shader por defecto). Misma lógica en GLSL 1.20:
# los índices de hueso llegan como vec4 (Panda los convierte) y no hay `in`/`out`/`texture()`.
_VERTEX_120 = f'''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_TransformTable[{MAX_HUESOS}];
attribute vec4 p3d_Vertex;
attribute vec4 transform_weight;
attribute vec4 transform_index;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
varying vec2 uvs;
varying vec4 vertex_color;

void main() {{
    mat4 hueso = p3d_TransformTable[int(transform_index.x)] * transform_weight.x
               + p3d_TransformTable[int(transform_index.y)] * transform_weight.y
               + p3d_TransformTable[int(transform_index.z)] * transform_weight.z
               + p3d_TransformTable[int(transform_index.w)] * transform_weight.w;
    gl_Position = p3d_ModelViewProjectionMatrix * (hueso * p3d_Vertex);
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
}}
'''

_FRAGMENT_120 = '''#version 120

uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
varying vec2 uvs;
varying vec4 vertex_color;

void main() {
    gl_FragColor = texture2D(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
}
'''

# --- Punto 5 del pulido: TOON de 2 bandas + borde de luz (frontend/toon_calculos.py; ALCALDE_TOON_PERSONAJES=0 lo quita) ---
# Mismo skinning y mismo color base que arriba; además la NORMAL se deforma con la parte 3x3 de la matriz de huesos y se
# lleva al MUNDO (p3d_ModelMatrix; con Ursina ese mundo es y-arriba, ver toon_calculos). La cámara en el mundo sale de p3d_ViewMatrixInverse (columna 3 = imagen del
# origen de la vista), así que nada depende de la cámara en la CPU. Los uniforms toon_* son globales: se ponen UNA vez en
# `render` (fijar_parametros) y todos los personajes los heredan; nada por personaje.
#   luz/sombra: color × mix(toon_sombra, toon_luz, smoothstep estrecho sobre N·L - centro)
#   borde:      + toon_rim.rgb × pow(1 - N·V, toon_rim.w), apagado en lo casi negro (el casco de tinta no se ilumina)
_VERTEX_TOON = f'''#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewMatrixInverse;
uniform mat4 p3d_TransformTable[{MAX_HUESOS}];
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 transform_weight;
in uvec4 transform_index;
in vec2 p3d_MultiTexCoord0;
out vec2 uvs;
uniform vec2 texture_scale;
uniform vec2 texture_offset;

in vec4 p3d_Color;
out vec4 vertex_color;
out vec3 normal_mundo;
out vec3 hacia_camara;

void main() {{
    mat4 hueso = p3d_TransformTable[transform_index.x] * transform_weight.x
               + p3d_TransformTable[transform_index.y] * transform_weight.y
               + p3d_TransformTable[transform_index.z] * transform_weight.z
               + p3d_TransformTable[transform_index.w] * transform_weight.w;
    vec4 posicion = hueso * p3d_Vertex;
    gl_Position = p3d_ModelViewProjectionMatrix * posicion;
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
    normal_mundo = mat3(p3d_ModelMatrix) * (mat3(hueso) * p3d_Normal);
    hacia_camara = p3d_ViewMatrixInverse[3].xyz - (p3d_ModelMatrix * posicion).xyz;
}}
'''

_FRAGMENT_TOON = '''#version 140

uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 toon_direccion;
uniform vec2 toon_banda;
uniform vec3 toon_luz;
uniform vec3 toon_sombra;
uniform vec4 toon_rim;
in vec2 uvs;
out vec4 fragColor;

in vec4 vertex_color;
in vec3 normal_mundo;
in vec3 hacia_camara;

void main() {
    vec4 color = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
    float largo = length(normal_mundo);
    vec3 n = largo > 0.00001 ? normal_mundo / largo : vec3(0.0, 1.0, 0.0);
    float luz = smoothstep(toon_banda.x - toon_banda.y, toon_banda.x + toon_banda.y, dot(n, toon_direccion));
    float tinta = smoothstep(0.05, 0.20, max(color.r, max(color.g, color.b)));
    float borde = pow(1.0 - clamp(dot(n, normalize(hacia_camara)), 0.0, 1.0), toon_rim.w);
    color.rgb = color.rgb * mix(toon_sombra, toon_luz, luz) + toon_rim.rgb * (borde * tinta);
    fragColor = color;
}
'''

# Lo mismo en GLSL 1.20 (macOS): attribute/varying, texture2D, gl_FragColor e índices de hueso como vec4 -> int().
# mat3(mat4) existe desde GLSL 1.20.
_VERTEX_TOON_120 = f'''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewMatrixInverse;
uniform mat4 p3d_TransformTable[{MAX_HUESOS}];
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 transform_weight;
attribute vec4 transform_index;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 normal_mundo;
varying vec3 hacia_camara;

void main() {{
    mat4 hueso = p3d_TransformTable[int(transform_index.x)] * transform_weight.x
               + p3d_TransformTable[int(transform_index.y)] * transform_weight.y
               + p3d_TransformTable[int(transform_index.z)] * transform_weight.z
               + p3d_TransformTable[int(transform_index.w)] * transform_weight.w;
    vec4 posicion = hueso * p3d_Vertex;
    gl_Position = p3d_ModelViewProjectionMatrix * posicion;
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
    normal_mundo = mat3(p3d_ModelMatrix) * (mat3(hueso) * p3d_Normal);
    hacia_camara = p3d_ViewMatrixInverse[3].xyz - (p3d_ModelMatrix * posicion).xyz;
}}
'''

_FRAGMENT_TOON_120 = '''#version 120

uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 toon_direccion;
uniform vec2 toon_banda;
uniform vec3 toon_luz;
uniform vec3 toon_sombra;
uniform vec4 toon_rim;
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 normal_mundo;
varying vec3 hacia_camara;

void main() {
    vec4 color = texture2D(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
    float largo = length(normal_mundo);
    vec3 n = largo > 0.00001 ? normal_mundo / largo : vec3(0.0, 1.0, 0.0);
    float luz = smoothstep(toon_banda.x - toon_banda.y, toon_banda.x + toon_banda.y, dot(n, toon_direccion));
    float tinta = smoothstep(0.05, 0.20, max(color.r, max(color.g, color.b)));
    float borde = pow(1.0 - clamp(dot(n, normalize(hacia_camara)), 0.0, 1.0), toon_rim.w);
    color.rgb = color.rgb * mix(toon_sombra, toon_luz, luz) + toon_rim.rgb * (borde * tinta);
    gl_FragColor = color;
}
'''

_cache = []
_avisado = []
_avisado_toon = []
_parametros_puestos = []


def activo():
    return SKINNING_GPU and os.environ.get("ALCALDE_SKINNING_CPU", "").strip() not in ("1", "true", "si")


# ¿Los personajes animados llevan el shader toon? (solo con el skinning por GPU: sin él no hay shader propio)
def toon_activo():
    return activo() and toon.activa() and (not _cache or _cache[0][1])


def _avisar(motivo):
    if not _avisado:
        _avisado.append(True)
        print(f"[skinning_gpu] {motivo}; se usa el skinning por CPU.", file=sys.stderr)


def _avisar_toon(motivo):
    if not _avisado_toon:
        _avisado_toon.append(True)
        print(f"[skinning_gpu] toon de personajes desactivado ({motivo}); se usa el shader de siempre.", file=sys.stderr)


def _hacer(vertex, fragment):
    shader = Shader.make(Shader.SL_GLSL, vertex, fragment)
    if shader is None:
        raise RuntimeError("el shader no compiló")
    return shader


def _gsg():
    from direct.showbase import ShowBaseGlobal
    win = getattr(getattr(ShowBaseGlobal, "base", None), "win", None)
    return None if win is None else win.get_gsg()


# Shader.make no compila el GLSL: eso lo hace Panda al dibujar. Compilarlo aquí con prepare_now NO es seguro (se llama
# durante la carga, fuera del dibujo y con otro contexto GL activo por el MSAA: medido, access violation). Así que se
# ENCOLA (Panda lo compila al empezar el siguiente frame, en su contexto) y revisar_toon() mira después si falló.
def _encolar_compilacion(shader):
    gsg = _gsg()
    if gsg is not None:
        shader.prepare(gsg.get_prepared_objects())


def _atributo_viejo():
    vertex, fragment = (_VERTEX_120, _FRAGMENT_120) if sys.platform == "darwin" else (_VERTEX, _FRAGMENT)
    return ShaderAttrib.make(_hacer(vertex, fragment)).set_flag(ShaderAttrib.F_hardware_skinning, True)


# Si el toon no compiló en este driver (get_error_flag, tras dibujarse al menos un frame): avisa UNA vez, cambia la caché
# al shader de siempre y se lo pone a las piezas que ya tenían el toon (un solo recorrido de `raiz`, una sola vez).
# Devuelve True si el toon sigue activo. Lo llama frontend/registro_toon_personajes.py cada PERIODO_TOON s.
def revisar_toon(raiz=None):
    if not _cache or not _cache[0][1]:
        return False
    toon_attrib = _cache[0][0]
    if not toon_attrib.get_shader().get_error_flag():
        return True
    _avisar_toon("el GLSL no compiló en este driver")
    viejo = _atributo_viejo()
    _cache[0] = (viejo, False)
    if raiz is None:
        from direct.showbase import ShowBaseGlobal
        raiz = ShowBaseGlobal.base.render
    for camino in raiz.find_all_matches("**/+GeomNode"):
        if camino.get_attrib(ShaderAttrib) == toon_attrib:
            camino.set_attrib(viejo, 10)
    return False


# Pone los uniforms toon_* en `render` (los heredan todos los personajes). `parametros` = toon_calculos.parametros_toon().
# False si no hay dónde ponerlos (sin ShowBase: pruebas sin ventana).
def fijar_parametros(parametros, raiz=None):
    if raiz is None:
        from direct.showbase import ShowBaseGlobal
        raiz = getattr(getattr(ShowBaseGlobal, "base", None), "render", None)
        if raiz is None:
            return False
    raiz.set_shader_input("toon_direccion", tuple(parametros["direccion"]))
    raiz.set_shader_input("toon_banda", tuple(parametros["banda"]))
    raiz.set_shader_input("toon_luz", tuple(parametros["luz"]))
    raiz.set_shader_input("toon_sombra", tuple(parametros["sombra"]))
    raiz.set_shader_input("toon_rim", tuple(parametros["rim"]))
    if not _parametros_puestos:
        _parametros_puestos.append(True)
    return True


def _atributo_toon():
    vertex, fragment = ((_VERTEX_TOON_120, _FRAGMENT_TOON_120) if sys.platform == "darwin"
                        else (_VERTEX_TOON, _FRAGMENT_TOON))
    shader = _hacer(vertex, fragment)
    _encolar_compilacion(shader)
    if not _parametros_puestos:          # sin registro todavía (menú, pruebas): la tarde de siempre
        fijar_parametros(toon.parametros_toon(None))
    return ShaderAttrib.make(shader).set_flag(ShaderAttrib.F_hardware_skinning, True)


def _atributo():
    if not _cache:
        atributo, es_toon = None, False
        if toon.activa():
            try:
                atributo, es_toon = _atributo_toon(), True
            except Exception as error:      # noqa: BLE001 — el toon es adorno: cae al shader de siempre, no a la CPU
                _avisar_toon(f"{type(error).__name__}: {error}")
        if atributo is None:
            atributo = _atributo_viejo()
        _cache.append((atributo, es_toon))
    return _cache[0][0]


def _tiene_animacion(geom_node):
    for i in range(geom_node.get_num_geoms()):
        formato = geom_node.get_geom(i).get_vertex_data().get_format()
        if formato.get_animation().get_animation_type() == GeomVertexAnimationSpec.AT_panda:
            return True
    return False


# Activa el skinning por GPU en las piezas animadas de `actor` (NodePath del Actor). Devuelve cuántos
# GeomNode quedaron con el shader (0 = sin cambios). Nunca lanza: ante un error, el Actor queda como estaba.
def aplicar(actor):
    if not activo() or actor is None:
        return 0
    try:
        atributo = _atributo()
        aplicados = 0
        for camino in actor.find_all_matches("**/+GeomNode"):
            if _tiene_animacion(camino.node()):
                camino.set_attrib(atributo, 10)
                # Los mismos valores por defecto que Ursina da al unlit_shader.
                camino.set_shader_input("texture_scale", (1.0, 1.0))
                camino.set_shader_input("texture_offset", (0.0, 0.0))
                aplicados += 1
        return aplicados
    except Exception as error:      # noqa: BLE001 — cualquier fallo deja el skinning por CPU
        _avisar(str(error))
        return 0
