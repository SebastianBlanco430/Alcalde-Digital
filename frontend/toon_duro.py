# T5 (ALCALDE_TOON_DURO): shaders del toon DURO y cómo se ponen. Qué, a quién y por qué: frontend/toon_duro_calculos.py.
#
# Dos variantes, cada una en GLSL 1.30/1.40 y en 1.20 (macOS da un contexto OpenGL 2.1):
#   - SKINNING (NPC nuevos, Actor .glb): el skinning de frontend/skinning_gpu.py + deshornear las bandas fijas del color
#     de vértice + corte duro luz / sombra violeta. Sustituye a skinning_gpu.aplicar en esos Actor.
#   - PROCEDURAL (muñeco de frontend/personaje.py): sin huesos; sustituye al lit_with_shadows en las piezas del cuerpo
#     (el casco de tinta sigue sin shader). Pierde la sombra proyectada y la niebla sobre el cuerpo (como los .glb).
# Uniforms toon_duro_*: se ponen en cada nodo al aplicar (fijos: el sol no se mueve; nada por frame).
#
# Compilación segura: Panda compila al dibujar, así que tras aplicar se programa una revisión (invoke). Si el driver
# rechazó el GLSL: UN aviso por stderr y cada nodo vuelve a su shader de antes (skinning_gpu / lit_with_shadows). Si la
# creación del shader lanza: aviso y no se aplica (quien llama usa el camino de siempre).

import sys

from panda3d.core import ShaderAttrib

from frontend import skinning_gpu as sg
from frontend import toon_duro_calculos as tdc

_UNIFORMS_VERTEX_DURO = '''uniform vec3 toon_duro_horneado;
uniform vec2 toon_duro_cortes;
uniform vec3 toon_duro_brillos;
uniform vec3 toon_duro_tinta;'''

_UNIFORMS_FRAGMENT = '''uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 toon_duro_direccion;
uniform vec2 toon_duro_banda;
uniform vec3 toon_duro_luz;
uniform vec3 toon_duro_sombra;'''

# Cuerpo común del vertex con bandas horneadas: deshace el brillo (nn.banda_luz) salvo en el casco de tinta.
_DESHORNEAR = '''    float largo_n = length(p3d_Normal);
    float coseno = largo_n > 0.000001 ? dot(p3d_Normal, toon_duro_horneado) / largo_n : toon_duro_cortes.y;
    float brillo = coseno >= toon_duro_cortes.x ? toon_duro_brillos.x
                 : (coseno >= toon_duro_cortes.y ? toon_duro_brillos.y : toon_duro_brillos.z);
    vec3 dif = abs(p3d_Color.rgb - toon_duro_tinta);
    es_tinta = step(max(dif.x, max(dif.y, dif.z)), 0.01);
    vertex_color = vec4(mix(p3d_Color.rgb / brillo, p3d_Color.rgb, es_tinta), p3d_Color.a);'''

# Cuerpo común del fragment: corte casi en escalón y sombra con matiz; la tinta no se toca.
_SOMBREAR = '''    float largo = length(normal_mundo);
    vec3 n = largo > 0.00001 ? normal_mundo / largo : vec3(0.0, 1.0, 0.0);
    float luz = smoothstep(toon_duro_banda.x - toon_duro_banda.y, toon_duro_banda.x + toon_duro_banda.y,
                           dot(n, toon_duro_direccion));
    color.rgb *= mix(mix(toon_duro_sombra, toon_duro_luz, luz), vec3(1.0), es_tinta);'''

_HUESO_130 = '''    mat4 hueso = p3d_TransformTable[transform_index.x] * transform_weight.x
               + p3d_TransformTable[transform_index.y] * transform_weight.y
               + p3d_TransformTable[transform_index.z] * transform_weight.z
               + p3d_TransformTable[transform_index.w] * transform_weight.w;'''
_HUESO_120 = _HUESO_130.replace("[transform_index.", "[int(transform_index.").replace("] * transform_weight", ")] * transform_weight")

VERTEX_SKIN = f'''#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_TransformTable[{sg.MAX_HUESOS}];
uniform vec2 texture_scale;
uniform vec2 texture_offset;
{_UNIFORMS_VERTEX_DURO}
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 transform_weight;
in uvec4 transform_index;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
out vec2 uvs;
out vec4 vertex_color;
out vec3 normal_mundo;
out float es_tinta;

void main() {{
{_HUESO_130}
    gl_Position = p3d_ModelViewProjectionMatrix * (hueso * p3d_Vertex);
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
{_DESHORNEAR}
    normal_mundo = mat3(p3d_ModelMatrix) * (mat3(hueso) * p3d_Normal);
}}
'''

VERTEX_SKIN_120 = f'''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_TransformTable[{sg.MAX_HUESOS}];
uniform vec2 texture_scale;
uniform vec2 texture_offset;
{_UNIFORMS_VERTEX_DURO}
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 transform_weight;
attribute vec4 transform_index;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 normal_mundo;
varying float es_tinta;

void main() {{
{_HUESO_120}
    gl_Position = p3d_ModelViewProjectionMatrix * (hueso * p3d_Vertex);
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
{_DESHORNEAR}
    normal_mundo = mat3(p3d_ModelMatrix) * (mat3(hueso) * p3d_Normal);
}}
'''

# Procedural: sin huesos ni bandas horneadas (el casco de tinta va en otro nodo, sin shader). Las mallas de
# piezas.malla_unida (Entity.combine de Ursina) NO traen normales (medido: solo vertex, color y texcoord; por eso el
# lit_with_shadows tampoco las sombreaba por caras): la normal de la cara sale en el fragment de las derivadas de la
# posición en el mundo (cubos: exacta; esferas: facetada, como los NPC low-poly) y se gira hacia la cámara.
VERTEX_PROC = '''#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
out vec2 uvs;
out vec4 vertex_color;
out vec3 pos_mundo;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
    pos_mundo = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
'''

VERTEX_PROC_120 = '''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
attribute vec4 p3d_Color;
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 pos_mundo;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uvs = (p3d_MultiTexCoord0 * texture_scale) + texture_offset;
    vertex_color = p3d_Color;
    pos_mundo = (p3d_ModelMatrix * p3d_Vertex).xyz;
}
'''

_NORMAL_DE_CARA = '''    vec3 normal_mundo = cross(dFdx(pos_mundo), dFdy(pos_mundo));
    if (dot(normal_mundo, p3d_ViewMatrixInverse[3].xyz - pos_mundo) < 0.0) {
        normal_mundo = -normal_mundo;
    }
    float es_tinta = 0.0;'''

FRAGMENT_PROC = f'''#version 140
{_UNIFORMS_FRAGMENT}
uniform mat4 p3d_ViewMatrixInverse;
in vec2 uvs;
in vec4 vertex_color;
in vec3 pos_mundo;
out vec4 fragColor;

void main() {{
    vec4 color = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
{_NORMAL_DE_CARA}
{_SOMBREAR}
    fragColor = color;
}}
'''

FRAGMENT_PROC_120 = f'''#version 120
{_UNIFORMS_FRAGMENT}
uniform mat4 p3d_ViewMatrixInverse;
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 pos_mundo;

void main() {{
    vec4 color = texture2D(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
{_NORMAL_DE_CARA}
{_SOMBREAR}
    gl_FragColor = color;
}}
'''

FRAGMENT = f'''#version 140
{_UNIFORMS_FRAGMENT}
in vec2 uvs;
in vec4 vertex_color;
in vec3 normal_mundo;
in float es_tinta;
out vec4 fragColor;

void main() {{
    vec4 color = texture(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
{_SOMBREAR}
    fragColor = color;
}}
'''

FRAGMENT_120 = f'''#version 120
{_UNIFORMS_FRAGMENT}
varying vec2 uvs;
varying vec4 vertex_color;
varying vec3 normal_mundo;
varying float es_tinta;

void main() {{
    vec4 color = texture2D(p3d_Texture0, uvs) * p3d_ColorScale * vertex_color;
{_SOMBREAR}
    gl_FragColor = color;
}}
'''

_shaders = {}                    # "skin" / "proc" -> Shader (o None si no se pudo crear)
_aplicados = []                  # (tipo, NodePath o Entity) con el toon duro: para revertir si no compila
_estado = {"roto": False, "listo": False, "revision": False}
_avisado = []


def _avisar(motivo):
    if not _avisado:
        _avisado.append(True)
        print(f"[toon_duro] toon duro desactivado ({motivo}); se usa el shader de siempre.", file=sys.stderr)


def _textos(tipo, darwin=None):
    darwin = sys.platform == "darwin" if darwin is None else darwin
    if tipo == "skin":
        return (VERTEX_SKIN_120, FRAGMENT_120) if darwin else (VERTEX_SKIN, FRAGMENT)
    return (VERTEX_PROC_120, FRAGMENT_PROC_120) if darwin else (VERTEX_PROC, FRAGMENT_PROC)


def _shader(tipo):
    if tipo not in _shaders:
        try:
            shader = sg._hacer(*_textos(tipo))
            sg._encolar_compilacion(shader)
            _shaders[tipo] = shader
            _estado["listo"] = False          # un shader nuevo: hay que volver a revisar
        except Exception as error:      # noqa: BLE001 — adorno: sin él, el shader de siempre
            _avisar(f"{type(error).__name__}: {error}")
            _shaders[tipo] = None
    return _shaders[tipo]


def disponible():
    return tdc.activa() and not _estado["roto"]


def _poner_uniforms(nodo):
    for nombre, valor in tdc.parametros().items():
        nodo.set_shader_input(nombre, valor)
    nodo.set_shader_input("texture_scale", (1.0, 1.0))
    nodo.set_shader_input("texture_offset", (0.0, 0.0))


# Toon duro en las piezas animadas del Actor de un NPC nuevo (en vez de skinning_gpu.aplicar). Devuelve cuántos
# GeomNode lo llevan; 0 = no se aplicó (bandera apagada, skinning por CPU, shader roto): quien llama sigue como siempre.
def aplicar_actor(actor):
    if actor is None or not disponible() or not sg.activo():
        return 0
    shader = _shader("skin")
    if shader is None:
        return 0
    try:
        atributo = ShaderAttrib.make(shader).set_flag(ShaderAttrib.F_hardware_skinning, True)
        aplicados = 0
        for camino in actor.find_all_matches("**/+GeomNode"):
            if sg._tiene_animacion(camino.node()):
                camino.set_attrib(atributo, 10)
                _poner_uniforms(camino)
                _anotar("skin", camino)
                aplicados += 1
        _programar_revision()
        return aplicados
    except Exception as error:      # noqa: BLE001
        _avisar(f"{type(error).__name__}: {error}")
        return 0


# Toon duro en una pieza del muñeco procedural (Entity de piezas.malla_unida). True si se aplicó.
def aplicar_pieza(entidad):
    if entidad is None or not disponible():
        return False
    shader = _shader("proc")
    if shader is None:
        return False
    try:
        entidad.shader = shader            # Shader de Panda: Ursina hace setShader y lo recuerda en entidad.shader
        _poner_uniforms(entidad)
        _anotar("proc", entidad)
        _programar_revision()
        return True
    except Exception as error:      # noqa: BLE001
        _avisar(f"{type(error).__name__}: {error}")
        return False


# Solo mientras la compilación no está confirmada (después no hará falta revertir y no se retienen nodos).
def _anotar(tipo, nodo):
    if not _estado["listo"]:
        _aplicados.append((tipo, nodo))


def _programar_revision():
    if _estado["listo"] or _estado["roto"] or _estado["revision"]:
        return
    try:
        from ursina import invoke
        _estado["revision"] = True
        invoke(revisar, delay=1.0)
    except Exception:          # noqa: BLE001 — sin Ursina (pruebas): no hay nada que dibujar ni revisar
        _estado["revision"] = False


# ¿Compilaron? Si el driver rechazó alguno: aviso y todos los nodos vuelven a su shader de siempre. Si aún no se
# dibujaron, se mira de nuevo más tarde. Devuelve True si el toon duro sigue en pie.
def revisar():
    _estado["revision"] = False
    shaders = [s for s in _shaders.values() if s is not None]
    if any(s.get_error_flag() for s in shaders):
        _estado["roto"] = True
        _avisar("el GLSL no compiló en este driver")
        revertir()
        return False
    gsg = sg._gsg()
    if gsg is not None and shaders and all(s.is_prepared(gsg.get_prepared_objects()) for s in shaders):
        _estado["listo"] = True
        _aplicados.clear()            # ya no hará falta revertirlos
        return True
    _programar_revision()
    return True


def revertir():
    viejo = None
    for tipo, nodo in _aplicados:
        try:
            if nodo.is_empty():
                continue
            if tipo == "skin":
                viejo = viejo or sg._atributo()
                nodo.set_attrib(viejo, 10)
            else:
                from ursina.shaders import lit_with_shadows_shader
                nodo.shader = lit_with_shadows_shader
        except Exception:          # noqa: BLE001 — un nodo a medio destruir no impide revertir los demás
            continue
    _aplicados.clear()
