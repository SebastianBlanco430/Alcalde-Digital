# Decorado 3D del mundo digital (Ursina): rejilla en el suelo, torres y avatar de alambre (wireframe), núcleo
# rotatorio y una estación holográfica por personaje del caso (pedestal de alambre + retrato). Paleta de
# frontend/materiales.py (tema «digital»). Todo es geometría ESTÁTICA: cada grupo de líneas es UN solo nodo con
# `lineas_sueltas` (rejilla menor, rejilla mayor, torres, estaciones...: unas pocas llamadas de dibujo), sin luces ni
# sombras (sin shader: color plano). La escena solo anima pulsos de color y el giro del núcleo.

import math

from panda3d.core import TransparencyAttrib
from ursina import Entity, color

from frontend import materiales as mat
from frontend import mundo_digital_calculos as calc
from frontend.piezas import lineas_sueltas, silenciar

EXTENSION_REJILLA = 70.0
PASO_REJILLA = 2.0
EJE_CADA = 5
RADIO_ESTACIONES = 7.0
ARCO_ESTACIONES = 100.0
SEMILLA_TORRES = 20261108
ANCHO_RETRATO = 1.5


# Un solo nodo de líneas de color plano colgado de `padre`.
def nodo_lineas(padre, vertices, rgb, grosor=2.0, nombre="lineas"):
    nodo = lineas_sueltas(vertices)
    nodo.set_name(nombre)
    nodo.reparent_to(padre)
    nodo.set_shader_off()
    nodo.set_light_off()
    nodo.set_fog_off()
    nodo.set_color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, 1)
    nodo.set_render_mode_thickness(grosor)
    return nodo


def _desplazar(vertices, dx, dy, dz):
    return [(x + dx, y + dy, z + dz) for x, y, z in vertices]


class DecoradoDigital(Entity):

    # personajes: {id: dict del JSON con "retrato"}. textura(retrato, expresion) -> Texture (inyectable para tests).
    def __init__(self, personajes, textura, **opciones):
        super().__init__(**opciones)
        self.estaciones = {}              # id de personaje -> (x, z)
        self.retratos = {}                # id de personaje -> Entity del retrato holográfico
        self._pulsos = []                 # (NodePath, color_a, color_b, fase)
        self._construir_suelo()
        self._construir_torres()
        self.avatar = self._construir_avatar()
        self.nucleo = self._construir_nucleo()
        self._construir_estaciones(personajes, textura)
        silenciar(self)

    def _construir_suelo(self):
        menores, mayores = calc.lineas_rejilla(EXTENSION_REJILLA, PASO_REJILLA, EJE_CADA)
        nodo_lineas(self, menores, mat.DIGITAL_REJILLA, 1.0, "rejilla_menor")
        nodo_lineas(self, mayores, mat.DIGITAL_REJILLA_EJE, 2.0, "rejilla_mayor")

    def _construir_torres(self):
        cian, magenta = [], []
        for i, (cx, cz, ancho, fondo, alto) in enumerate(
                calc.torres_digitales(26, SEMILLA_TORRES, 16.0, 46.0)):
            destino = magenta if i % 6 == 0 else cian
            destino += calc.aristas_caja(cx, alto / 2, cz, ancho, alto, fondo)
            if alto > 9:                                       # un piso intermedio da aspecto de edificio
                destino += calc.aristas_caja(cx, alto * 0.55, cz, ancho * 1.02, 0.05, fondo * 1.02)
        nodo_lineas(self, cian, mat.WIREFRAME_TENUE, 1.5, "torres")
        nodo_lineas(self, magenta, mat.NEON_MAGENTA, 1.5, "torres_magenta")

    def _construir_avatar(self):
        raiz = Entity(parent=self, name="avatar_digital")
        vertices = []
        for caja in calc.CAJAS_AVATAR:
            vertices += calc.aristas_caja(*caja)
        nodo_lineas(raiz, vertices, mat.AVATAR_CONTORNO, 2.5, "avatar_alambre")
        # núcleo luminoso en el pecho (esfera sin sombreado)
        nucleo = Entity(parent=raiz, model="sphere", color=_color(mat.AVATAR_NUCLEO), scale=0.16, position=(0, 1.2, -0.12),
                        shader=None)
        raiz.nucleo = nucleo
        return raiz

    def _construir_nucleo(self):
        centro = Entity(parent=self, position=(0, 1.4, RADIO_ESTACIONES), name="nucleo_digital")
        nodo_lineas(centro, calc.aristas_caja(0, 0, 0, 1.0, 1.0, 1.0), mat.NEON_AMARILLO, 2.5, "nucleo_cubo")
        nodo_lineas(centro, calc.aristas_caja(0, 0, 0, 0.55, 0.55, 0.55), mat.NEON_CIAN, 2.0, "nucleo_interior")
        centro.rotation = (0, 20, 0)
        return centro

    def _construir_estaciones(self, personajes, textura):
        ids = list(personajes)
        for pid, (x, z) in zip(ids, calc.posiciones_estaciones(len(ids), RADIO_ESTACIONES, ARCO_ESTACIONES)):
            self.estaciones[pid] = (x, z)
            raiz = Entity(parent=self, position=(x, 0, z), name=f"estacion_{pid}")
            # pedestal (caja baja) + marco del holograma (rectángulo de aristas) mirando al avatar
            vertices = calc.aristas_caja(0, 0.1, 0, 1.2, 0.2, 1.2)
            vertices += calc.aristas_caja(0, ANCHO_RETRATO / 2 + 0.95, 0.0, ANCHO_RETRATO + 0.1, ANCHO_RETRATO + 0.1, 0.02)
            nodo_lineas(raiz, vertices, mat.NEON_CIAN, 2.0, "estacion_marco")
            retrato = Entity(parent=raiz, model="quad", texture=textura(personajes[pid]["retrato"], "neutral"),
                             position=(0, ANCHO_RETRATO / 2 + 0.95, 0.03), scale=(ANCHO_RETRATO, ANCHO_RETRATO),
                             color=color.rgba(1, 1, 1, 0.92), double_sided=True)
            retrato.setTransparency(TransparencyAttrib.M_alpha)
            # mira hacia el avatar (el origen): el quad mira a -z por defecto, así que el yaw apunta al origen
            raiz.rotation_y = math.degrees(math.atan2(-x, -z)) + 180
            self.retratos[pid] = retrato

    def fijar_expresion(self, pid, retrato_json, expresion, textura):
        quad = self.retratos.get(pid)
        if quad is not None:
            quad.texture = textura(retrato_json, expresion)

    # Resalta la estación de `pid` (None = ninguna): el que habla se ve a plena opacidad, el resto atenuado.
    def resaltar(self, pid):
        for otro, quad in self.retratos.items():
            quad.color = color.rgba(1, 1, 1, 0.95 if otro == pid else 0.35)

    # Un paso de animación (sin asignar entidades nuevas): giro del núcleo y respiración del avatar.
    def avanzar(self, t):
        self.nucleo.rotation_y = (t * 40.0) % 360.0
        self.nucleo.y = 1.4 + 0.08 * math.sin(t * 1.6)
        self.avatar.nucleo.scale = 0.16 + 0.025 * math.sin(t * 3.0)


def _color(rgb):
    return color.rgb32(*rgb)
