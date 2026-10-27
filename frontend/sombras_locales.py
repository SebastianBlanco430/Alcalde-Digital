# F6: sombras locales del mapa grande. El mapa de sombras NO cubre los 900 x 650 m (4600 casas): se hornea (buffer one-shot,
# como el de Ciudad3D) solo un volumen de ~170 m alrededor del jugador, con 2048 texels (8,3 cm), y se vuelve a hornear al
# alejarse >30 m del centro o al cambiar los chunks LOD0 de alrededor (con un intervalo mínimo). Entre horneados cuesta 0.
#
# Sin corte duro en el borde: el shader lit_with_shadows de Ursina lee el mapa sin saber de volúmenes, así que se deriva UNA
# copia (shader_de_ciudad) con un desvanecimiento por distancia al centro horneado: sombra completa hasta r0, nula desde r1
# (smoothstep). Fuera de r1 ni siquiera lee el mapa (menos coste y el aspecto de F5: todo iluminado). El shader original de
# Ursina y el del mundo chico no se tocan: la copia solo la usan los Entity de CiudadGrande.
#
# Plan B (documentado, activo solo si Ursina cambia el código del shader y la copia no se puede derivar): shader_de_ciudad()
# devuelve el original, el mapa se queda VACÍO (todo iluminado, como en F5). El otro plan B previsto (sombras solo en LOD0,
# sin fade) no hizo falta: el fade en el shader funciona en macOS (#version 150, la misma que Ursina).
#
# Luz y trampas de la nota 18 intactas: una sola DirectionalLight + AmbientLight, shadow_bias del shader (-0,0008), MASCARA_LUZ
# (el terreno, las calles y la tinta no proyectan), sin tocar combine(include_normals=True) ni la niebla. Los personajes y
# peatones no entran al mapa (como en el mundo chico: llevan el shader por defecto y no reciben ni proyectan sombra).
# ALCALDE_SIN_SOMBRAS_LOCALES=1 deja el mapa vacío (F5).

import os

from panda3d.core import NodePath, PTA_LVecBase4f, Point3
from ursina import application, scene, time as tiempo
from ursina.shaders import lit_with_shadows_shader as _SHADER_URSINA

from frontend import rendimiento
from frontend import sombras_locales_calculos as calc

ENTRADA = "sombra_local"       # uniform vec4 del shader: (centro x, centro z, r0, r1)
SHADOW_BLUR_LOCAL = 0.0094     # el 0,002 del mundo chico es sobre una película de ~800 m (1,6 m); aquí la película mide 170 m

_shader_local = None
_intentado = False
_PTA = PTA_LVecBase4f.empty_array(1)    # (centro x, centro z, r0, r1) compartido: la raíz lo hereda y cambiar su contenido no toca estados

_VIEJO_MUESTRA = "        float shadow = 0.0;\n"
_NUEVO_MUESTRA = (
    "        float d_sombra = length(vertex_world_position.xz - sombra_local.xy);\n"
    "        float k_sombra = (sombra_local.w > 0.0) ? 1.0 - smoothstep(sombra_local.z, sombra_local.w, d_sombra) : 0.0;\n"
    "        vec3 c_sombra = shadow_coord[i].xyz / shadow_coord[i].w;\n"
    "        if (c_sombra.x < 0.0 || c_sombra.x > 1.0 || c_sombra.y < 0.0 || c_sombra.y > 1.0 || c_sombra.z < 0.0 || c_sombra.z > 1.0) k_sombra = 0.0;\n"
    "        int n_muestras = (k_sombra > 0.0) ? shadow_samples : 0;\n"
    "        float shadow = 0.0;\n")
_VIEJO_PROMEDIO = "        shadow /= (shadow_samples_float * shadow_samples_float);\n"
_NUEVO_PROMEDIO = (
    "        shadow = (n_muestras > 0) ? shadow / (shadow_samples_float * shadow_samples_float) : 1.0;\n"
    "        shadow = mix(1.0, shadow, k_sombra);\n")


def derivar_fragmento(fuente):
    """Fuente del fragment shader con el desvanecimiento local, o None si el de Ursina ya no tiene la forma esperada."""
    for viejo in (_VIEJO_MUESTRA, _VIEJO_PROMEDIO, "x < shadow_samples;", "y < shadow_samples;", "uniform int shadow_samples;"):
        if fuente.count(viejo) != 1:
            return None
    f = fuente.replace(_VIEJO_MUESTRA, _NUEVO_MUESTRA).replace(_VIEJO_PROMEDIO, _NUEVO_PROMEDIO)
    f = f.replace("x < shadow_samples;", "x < n_muestras;").replace("y < shadow_samples;", "y < n_muestras;")
    return f.replace("uniform int shadow_samples;", "uniform int shadow_samples;\nuniform vec4 sombra_local;")


def sombras_locales_activas():
    return os.environ.get("ALCALDE_SIN_SOMBRAS_LOCALES", "").strip() != "1"


def shader_de_ciudad():
    """El shader con luz de CiudadGrande: copia con desvanecimiento (creada una vez) o, en plan B, el original de Ursina."""
    global _shader_local, _intentado
    if _intentado:
        return _shader_local or _SHADER_URSINA
    _intentado = True
    if not sombras_locales_activas():
        return _SHADER_URSINA
    fragmento = derivar_fragmento(_SHADER_URSINA.fragment)
    if fragmento is None:
        return _SHADER_URSINA
    from ursina.shader import Shader
    import frontend.piezas  # noqa: F401 — fija shadow_bias y shadow_color en el shader de Ursina ANTES de copiar sus entradas
    _PTA[0] = (0.0, 0.0, 0.0, 0.0)                          # r1 = 0: sin sombra hasta el primer horneado
    scene.get_top().set_shader_input(ENTRADA, _PTA)         # el shader exige la entrada aunque nadie hornee (CiudadGrande sin sombras)
    entradas = dict(_SHADER_URSINA.default_input)          # ya con shadow_bias y shadow_color de piezas.py (se importó antes)
    entradas["shadow_blur"] = SHADOW_BLUR_LOCAL
    if rendimiento.camara_en_la_raiz_activa():
        entradas.pop(rendimiento.ENTRADA_CAMARA, None)
    copia = Shader(name="lit_con_sombras_locales", language=Shader.GLSL, vertex=_SHADER_URSINA.vertex, fragment=fragmento,
                   default_input=entradas)
    if not rendimiento.camara_en_la_raiz_activa():
        copia.continuous_input = dict(_SHADER_URSINA.continuous_input)
    _shader_local = copia
    return copia


def es_shader_de_luz(shader):
    return shader is _SHADER_URSINA or (_shader_local is not None and shader is _shader_local)


class SombrasLocales:
    """Hornea el mapa de sombras alrededor del jugador y mantiene el desvanecimiento. Lo crea CiudadGrande si hay sombras."""

    def __init__(self, ciudad):
        self.ciudad = ciudad
        self.luz = ciudad.luz
        self.activas = _shader_local is not None
        self._pta = _PTA
        self.centro = None                                     # (x, z) del último horneado
        self._firma = None
        self._t_ultimo = -1e9
        self._frames = 0
        self._reloj = 0.0                                      # s de juego (suma de time.dt): pausa = no pasa nada
        self._viejo = None                                     # centro del desvanecimiento del horneado anterior
        self._t_cambio = -1e9
        self._firma_actual = frozenset()
        self.horneados = 0
        self.ultimo_ms = 0.0
        if self.activas:
            self.luz.update_bounds(ciudad.fondo)               # lente válida desde el principio; se reajusta en cada horneado
            self.luz._light.set_scene(ciudad)                  # el pase de sombras recorre la ciudad (casas y props de los chunks)
            rendimiento.agregar_raiz(ciudad)                   # ese pase no hereda la cámara de render
            ciudad.set_shader_input(ENTRADA, self._pta)        # ni el desvanecimiento (la raíz del pase es la ciudad)

    def _firma_ahora(self, foco):
        g = self.ciudad.gestor
        claves = [c for c, v in g.niveles.items() if 0 in v]
        x, z = self.centro or foco                              # los chunks que importan son los del volumen YA horneado
        return calc.firma_de_chunks(claves, g.limites, x, z)

    def actualizar(self, foco):
        """Se llama cada frame con (x, z) del jugador. Hornea solo cuando toca; devuelve True si pidió un horneado."""
        if not self.activas:
            return False
        self._frames += 1
        if self._frames % calc.CADA_N_FRAMES == 0 or self._firma is None:
            self._firma_actual = self._firma_ahora(foco)
        self._reloj += tiempo.dt
        ahora = self._reloj
        self._deslizar_fade(ahora)
        if not calc.debe_rehornear(self.centro, foco, self._firma, self._firma_actual, self._t_ultimo, ahora):
            return False
        return self.hornear(foco)

    def _deslizar_fade(self, ahora):
        if self._viejo is None or self.centro is None:
            return
        k = calc.avance_transicion(ahora, self._t_cambio)
        cx, cz = calc.centro_de_fade(self._viejo, self.centro, k)
        r0, r1 = calc.rango_fade()
        self._pta[0] = (cx, cz, r0, r1)
        if k >= 1.0:
            self._viejo = None

    def hornear(self, foco):
        buffer = self.luz._light.get_shadow_buffer(application.base.win.gsg)
        if buffer is None:                                     # Panda lo crea al primer render con la luz encendida
            return False
        y = float(self.ciudad._suelo(foco[0], foco[1]))
        p = self.luz.getRelativePoint(scene, Point3(foco[0], y, foco[1]))
        ox, oy, cerca, lejos, lado = calc.lente_local((p.x, p.y, p.z))
        lente = self.luz._light.get_lens()
        lente.set_film_size(lado, lado)
        lente.set_film_offset(ox, oy)
        lente.set_near_far(cerca, lejos)
        r0, r1 = calc.rango_fade()
        ahora = self._reloj
        # el desvanecimiento parte de donde estaba (si ya se estaba deslizando, de donde iba) y se desliza al centro nuevo
        self._viejo = (self._pta[0][0], self._pta[0][1]) if self.centro is not None else None
        self._t_cambio = ahora
        buffer.set_one_shot(True)
        self.centro = (foco[0], foco[1])
        self._firma = self._firma_actual = self._firma_ahora(foco)     # los chunks de alrededor del NUEVO centro
        self._t_ultimo = ahora
        self.horneados += 1
        return True

    def apagar(self):
        """Sin sombras (luz apagada): el desvanecimiento a 0 deja todo iluminado."""
        self._pta[0] = (0.0, 0.0, 0.0, 0.0)
        self.centro = None
        self._viejo = None
        self._firma = None
