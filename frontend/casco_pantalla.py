# T2 (ALCALDE_CASCO_PANTALLA): shader del casco de tinta de los NPC nuevos con grosor ~constante en pantalla.
# Qué hace y la fórmula: frontend/casco_pantalla_calculos.py.
#
# El casco de un NPC nuevo es un Geom extra en el MISMO GeomNode que el cuerpo (frontend/npc_nuevos_modelo._casco_tinta),
# así que hoy se dibuja con el shader de skinning del cuerpo (skinning_gpu o toon_duro, sin niebla) y sigue la animación
# por los mismos huesos. Aquí ese Geom recibe en su propio estado (prioridad 20 > la 10 del nodo) una variante del
# skinning de frontend/skinning_gpu.py que además empuja el vértice por su normal suavizada (la columna normal del casco
# se rellena con ella al cargar, solo con la bandera). Color: p3d_ColorScale × color de vértice (la tinta), como antes.
#
# GLSL 1.30/1.40 y 1.20 (macOS). Compilación segura, como toon_duro: Panda compila al dibujar; una revisión (invoke)
# mira get_error_flag y, si el driver lo rechazó, UN aviso por stderr y los cascos vuelven al shader del nodo (el casco
# ya viene inflado el grosor T1 en la CPU: queda exactamente como antes).

import sys

from panda3d.core import MaterialAttrib, ShaderAttrib

from frontend import casco_pantalla_calculos as cpc
from frontend import skinning_gpu as sg

PRIORIDAD = 20                   # > la 10 con la que skinning_gpu / toon_duro ponen su shader en el nodo

_HUESO_130 = '''    mat4 hueso = p3d_TransformTable[transform_index.x] * transform_weight.x
               + p3d_TransformTable[transform_index.y] * transform_weight.y
               + p3d_TransformTable[transform_index.z] * transform_weight.z
               + p3d_TransformTable[transform_index.w] * transform_weight.w;'''
_HUESO_120 = _HUESO_130.replace("[transform_index.", "[int(transform_index.").replace(
    "] * transform_weight", ")] * transform_weight")

# casco_pantalla = (px a 720 px de alto, mínimo ×, máximo ×, grosor horneado en unidades del modelo).
# ky = norma de la fila «y» de la proyección (1/tan(fov_v/2), sin depender del eje adelante de Panda); w = profundidad.
_EMPUJE = '''    vec4 posicion = hueso * p3d_Vertex;
    vec3 normal = mat3(hueso) * p3d_Normal;
    vec4 clip = p3d_ModelViewProjectionMatrix * posicion;
    float escala = length(mat3(p3d_ModelMatrix) * normal);
    if (escala > 0.000001) {
        float g = casco_pantalla.w * escala;
        float ky = length(vec3(p3d_ProjectionMatrix[0][1], p3d_ProjectionMatrix[1][1], p3d_ProjectionMatrix[2][1]));
        float objetivo = 2.0 * casco_pantalla.x * abs(clip.w) / (720.0 * max(ky, 0.000001));
        float grosor = clamp(objetivo, casco_pantalla.y * g, casco_pantalla.z * g);
        posicion.xyz += normal * ((grosor - g) / escala);
        clip = p3d_ModelViewProjectionMatrix * posicion;
    }
    gl_Position = clip;
    vertex_color = p3d_Color;'''

VERTEX = f'''#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform mat4 p3d_TransformTable[{sg.MAX_HUESOS}];
uniform vec4 casco_pantalla;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 transform_weight;
in uvec4 transform_index;
in vec4 p3d_Color;
out vec4 vertex_color;

void main() {{
{_HUESO_130}
{_EMPUJE}
}}
'''

VERTEX_120 = f'''#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform mat4 p3d_TransformTable[{sg.MAX_HUESOS}];
uniform vec4 casco_pantalla;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 transform_weight;
attribute vec4 transform_index;
attribute vec4 p3d_Color;
varying vec4 vertex_color;

void main() {{
{_HUESO_120}
{_EMPUJE}
}}
'''

FRAGMENT = '''#version 140
uniform vec4 p3d_ColorScale;
in vec4 vertex_color;
out vec4 fragColor;

void main() {
    fragColor = p3d_ColorScale * vertex_color;
}
'''

FRAGMENT_120 = '''#version 120
uniform vec4 p3d_ColorScale;
varying vec4 vertex_color;

void main() {
    gl_FragColor = p3d_ColorScale * vertex_color;
}
'''

_shader = []                     # [Shader] o [None] si no se pudo crear
_aplicados = []                  # (GeomNode, índice, estado de antes) hasta confirmar la compilación
_estado = {"roto": False, "listo": False, "revision": False}
_avisado = []


def _avisar(motivo):
    if not _avisado:
        _avisado.append(True)
        print(f"[casco_pantalla] casco de grosor constante desactivado ({motivo}); se usa el casco de siempre.",
              file=sys.stderr)


def disponible():
    return cpc.activa() and sg.activo() and not _estado["roto"]


def _crear():
    if not _shader:
        try:
            textos = (VERTEX_120, FRAGMENT_120) if sys.platform == "darwin" else (VERTEX, FRAGMENT)
            shader = sg._hacer(*textos)
            sg._encolar_compilacion(shader)
            _shader.append(shader)
        except Exception as error:      # noqa: BLE001 — adorno: sin él, el casco de siempre
            _avisar(f"{type(error).__name__}: {error}")
            _shader.append(None)
    return _shader[0]


def _es_casco(estado):
    atributo = estado.get_attrib(MaterialAttrib)
    material = None if atributo is None else atributo.get_material()
    return material is not None and material.get_name() == "Contorno"


# Pone el shader en los cascos (Geom con material «Contorno») de las piezas animadas de `actor`. `grosor_modelo`: lo que
# el casco ya viene inflado en la CPU (unidades del modelo). Devuelve cuántos cascos lo llevan (0 = como siempre).
def aplicar_actor(actor, grosor_modelo):
    if actor is None or not disponible():
        return 0
    shader = _crear()
    if shader is None:
        return 0
    try:
        atributo = ShaderAttrib.make(shader).set_flag(ShaderAttrib.F_hardware_skinning, True)
        atributo = atributo.set_shader_input("casco_pantalla", cpc.parametros(grosor_modelo))
        aplicados = 0
        for camino in actor.find_all_matches("**/+GeomNode"):
            nodo = camino.node()
            if not sg._tiene_animacion(nodo):
                continue
            for i in range(nodo.get_num_geoms()):
                estado = nodo.get_geom_state(i)
                if _es_casco(estado):
                    nodo.set_geom_state(i, estado.set_attrib(atributo, PRIORIDAD))
                    if not _estado["listo"]:
                        _aplicados.append((nodo, i, estado))
                    aplicados += 1
        if aplicados:
            _programar_revision()
        return aplicados
    except Exception as error:      # noqa: BLE001
        _avisar(f"{type(error).__name__}: {error}")
        return 0


def _programar_revision():
    if _estado["listo"] or _estado["roto"] or _estado["revision"]:
        return
    try:
        from ursina import invoke
        _estado["revision"] = True
        invoke(revisar, delay=1.0)
    except Exception:          # noqa: BLE001 — sin Ursina (pruebas): nada que revisar
        _estado["revision"] = False


# ¿Compiló? Si no: aviso y los cascos vuelven a su estado de antes. Si aún no se dibujó, se mira más tarde.
def revisar():
    _estado["revision"] = False
    shader = _shader[0] if _shader else None
    if shader is None:
        return False
    if shader.get_error_flag():
        _estado["roto"] = True
        _avisar("el GLSL no compiló en este driver")
        revertir()
        return False
    gsg = sg._gsg()
    if gsg is not None and shader.is_prepared(gsg.get_prepared_objects()):
        _estado["listo"] = True
        _aplicados.clear()
        return True
    _programar_revision()
    return True


def revertir():
    for nodo, i, estado in _aplicados:
        try:
            if i < nodo.get_num_geoms():
                nodo.set_geom_state(i, estado)
        except Exception:          # noqa: BLE001
            continue
    _aplicados.clear()

