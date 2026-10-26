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

import os
import sys

from panda3d.core import GeomVertexAnimationSpec, Shader, ShaderAttrib

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

_cache = []
_avisado = []


def activo():
    return SKINNING_GPU and os.environ.get("ALCALDE_SKINNING_CPU", "").strip() not in ("1", "true", "si")


def _avisar(motivo):
    if not _avisado:
        _avisado.append(True)
        print(f"[skinning_gpu] {motivo}; se usa el skinning por CPU.", file=sys.stderr)


def _atributo():
    if not _cache:
        vertex, fragment = (_VERTEX_120, _FRAGMENT_120) if sys.platform == "darwin" else (_VERTEX, _FRAGMENT)
        shader = Shader.make(Shader.SL_GLSL, vertex, fragment)
        if shader is None:
            raise RuntimeError("el shader no compiló")
        _cache.append(ShaderAttrib.make(shader).set_flag(ShaderAttrib.F_hardware_skinning, True))
    return _cache[0]


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
