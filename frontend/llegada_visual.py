# LLEGADA a una misión de verificar (Ursina, mundo 3D). Sin tocar las reglas ni el flujo de las misiones:
#   - cuando llega la misión, el teléfono VIBRA en pantalla y la cámara hace un VISTAZO de 1,5 s al destino (guion nuevo
#     en frontend/llegada_visual_calculos.VISTAZO, reproducido con el DirectorCinematica de la escena; se salta con la
#     tecla de saltar cinemáticas). Una sola vez por misión: salir y volver al radio no lo repite;
#   - una COLUMNA DE LUZ marca la puerta del destino mientras la misión está en camino;
#   - cerca del destino, los vecinos COMENTAN el rumor con globos (uno cuenta la pista que se ve en el lugar) y adoptan la
#     postura «enojado» o «celular» según el tema del rumor (minijuegos_asignacion.tema_de). La pista se ve en el mundo;
#   - al pulsar E, el teléfono se ACERCA a la cámara justo antes del fundido al minijuego.
#
# Entra desde frontend/registro_misiones_visuales.py (un vigía colgado del HUD del mundo). Las posturas pasan por el
# enganche `_postura_forzada` de registro_ambiente_npc.py (el mismo que usa rectificar_visual.py).
# APAGADO: ALCALDE_LLEGADA_VISUAL=0. REDUCIR MOVIMIENTO: sin vistazo ni vibración; la columna no late.
# GUARDIÁN: un fallo avisa una vez por stderr, devuelve la cámara y deja el mundo como siempre.

import math

from panda3d.core import TransparencyAttrib
from ursina import Entity, Text, camera, color, time

from backend.datos import minijuegos_asignacion as asignacion
from frontend import banderas_visuales as bv
from frontend import estilo
from frontend import llegada_visual_calculos as calc
from frontend.componentes import escala_fuente, rgb

LLEGADA_VISUAL = True
VARIABLE = "ALCALDE_LLEGADA_VISUAL"
REPASO_VECINOS_S = 2.0


def activo():
    return bv.activa(LLEGADA_VISUAL, VARIABLE)


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    return VigiaLlegada(escena_mundo, parent=escena_mundo.hud)


class VigiaLlegada(Entity):

    def __init__(self, escena, **opciones):
        super().__init__(**opciones)
        self.escena = escena
        self.roto = False
        self._vistos = set()
        self._t = 0.0
        self._t_vibra = None
        self._estado_previo = None
        self._t_telefono = None
        self._vecinos = []           # personajes con postura forzada y globo
        self._comentarios = []       # [(personaje, frase)]: lo que la CapaGlobos pinta en sus globos
        self._t_repaso = 0.0
        self.columna = None
        self._destino_columna = None
        self._capa = None
        # Del HUD del mundo: si la escena cambia, se apaga con él y nunca tapa el minijuego.
        self.pantalla = Entity(parent=escena.hud, z=-0.5, enabled=False)
        self.pantalla_marco = Entity(parent=self.pantalla, model="quad", color=_rgba((24, 26, 34)))
        self.pantalla_brillo = Entity(parent=self.pantalla, model="quad", color=_rgba(estilo.COLOR_FONDO), z=-0.01)

    # Retoques 23-nov (globos): los globos de los vecinos los pinta la CapaGlobos de frontend/globos_npc.py, la misma
    # que los del pool de NPC (en pantalla, uno por NPC, sin pisarse ni pisar el HUD, sin cables encima, sin teñir).
    def _pedir_globos(self):
        if self._capa is None:
            if not self._comentarios:
                return
            from frontend.globos_npc import capa_de
            self._capa = capa_de(self.escena)
        from frontend.globos_npc import PRIORIDAD_LLEGADA
        self._capa.fijar("llegada", [(npc, frase, 1.0, PRIORIDAD_LLEGADA) for npc, frase in self._comentarios])

    # -- Frame --

    def update(self):
        if self.roto:
            return
        try:
            self._frame(min(time.dt, 0.1))
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("llegada_visual", error)
            self._apagar()

    def _frame(self, dt):
        self._t += dt
        escena = self.escena
        flujo = getattr(escena, "flujo", None)
        if flujo is None or getattr(escena, "online", None) is not None:
            self._ocultar_todo()
            return
        mision = flujo.mision_actual()
        estado = flujo.estado_mision()
        reducir = bv.reducir_movimiento()
        # Anuncio de misión nueva (cuando el mundo está libre: sin pausa, paneles ni otra cinemática).
        if calc.debe_anunciar(mision, self._vistos) and escena.enabled and not escena.controles_bloqueados():
            self._vistos.add(mision.id)
            self._t_vibra = 0.0 if not reducir else None
            if not reducir:
                self._vistazo(mision)
            else:
                self._tutorial(mision)
        self._vibrar(dt, reducir)
        self._pintar_columna(mision, estado, reducir)
        self._pintar_vecinos(mision, estado, dt)
        self._pedir_globos()
        # Al pulsar E (EN_RADIO -> EN_MINIJUEGO) el teléfono se acerca a la cámara durante el fundido.
        if self._estado_previo == "en_radio" and estado == "en_minijuego":
            self._t_telefono = 0.0
        self._estado_previo = estado
        self._pintar_telefono(dt, reducir)

    # -- Vibración del teléfono en pantalla --

    def _vibrar(self, dt, reducir):
        telefono = getattr(self.escena.hud, "telefono_ui", None)
        if telefono is None or self._t_vibra is None:
            return
        if not hasattr(self, "_x_telefono"):
            self._x_telefono = telefono.x
        self._t_vibra += dt
        telefono.x = self._x_telefono + calc.temblor_telefono(self._t_vibra, reducir=reducir)
        if self._t_vibra >= calc.DUR_VIBRACION:
            telefono.x = self._x_telefono
            self._t_vibra = None

    # Tutorial de la primera vez (frontend/tutorial_mision_ruta.py, ALCALDE_TUTORIAL_MISION=0 lo apaga). Nunca rompe el vigía.
    def _tutorial(self, mision):
        try:
            from frontend import tutorial_mision_ruta
            tutorial_mision_ruta.llegada_despues_del_vistazo(self.escena, mision)
        except Exception:                # noqa: BLE001
            pass

    # -- Vistazo de cámara al destino --

    def _toma_destino(self, mision):
        mundo = self.escena._mundo
        try:
            from frontend import guion_cinematicas as guion
            return guion.toma_fachada(mundo.edificio_de(mision.destino))
        except (ValueError, KeyError, AttributeError):
            from frontend import camara_calculos as cc
            px, pz = mundo.punto_interaccion(mision.destino)
            y = mundo.altura(px, pz) if hasattr(mundo, "altura") else 0.0
            posicion = (px + 6.0, y + 4.0, pz - 7.0)
            pitch, yaw = cc.rotacion_mirando(posicion, (px, y + 1.2, pz))
            return {"position": posicion, "pitch": pitch, "yaw": yaw}

    def _vistazo(self, mision):
        escena = self.escena
        if escena.director.activa:
            return
        from frontend.cinematica import ease_in_out, lerp, lerp_angulo, lerp_vec3
        toma = self._toma_destino(mision)
        inicio = (tuple(camera.position), camera.rotation_x, camera.rotation_y)
        escena._cinematica = True
        escena.camara.tomar_control()

        def ir(t):
            k = ease_in_out(t)
            camera.position = lerp_vec3(inicio[0], toma["position"], k)
            camera.rotation = (lerp(inicio[1], toma["pitch"], k), lerp_angulo(inicio[2], toma["yaw"], k), 0)

        def mirar(t):
            camera.position = toma["position"]

        def volver(t):
            k = ease_in_out(t)
            camera.position = lerp_vec3(toma["position"], inicio[0], k)
            camera.rotation = (lerp(toma["pitch"], inicio[1], k), lerp_angulo(toma["yaw"], inicio[2], k), 0)

        def terminar():
            escena.camara.soltar_control()
            escena._cinematica = False
            try:
                escena._sincronizar_raton()
            except Exception:            # noqa: BLE001
                pass
            self._tutorial(mision)       # la primera vez: tutorial de cómo llega una misión (tras el vistazo)

        escena.director.reproducir(calc.plan_vistazo(), {"ir": ir, "mirar": mirar, "volver": volver}, al_terminar=terminar)

    # -- Columna de luz en la puerta --

    def _pintar_columna(self, mision, estado, reducir):
        if mision is None or getattr(mision, "tipo", "") != "verificar" or not calc.columna_visible(estado):
            if self.columna is not None:
                self.columna.enabled = False
            return
        if self.columna is None:
            from ursina import Cylinder
            self.columna = Entity(parent=self.escena, model=Cylinder(resolution=14, height=1.0, radius=0.5),
                                  color=_rgba((120, 240, 255), 0.4))
            self.columna.setTransparency(TransparencyAttrib.M_alpha)
            self.columna.setDepthWrite(False)
            self.columna.setLightOff()
            self.columna.setTwoSided(True)
        if self._destino_columna != mision.destino:
            self._destino_columna = mision.destino
            mundo = self.escena._mundo
            px, pz = mundo.punto_interaccion(mision.destino)
            y = mundo.altura(px, pz) if hasattr(mundo, "altura") else 0.0
            self.columna.position = (px, y, pz)
            self.columna.scale = (1.1, calc.ALTURA_COLUMNA, 1.1)
        self.columna.enabled = True
        self.columna.color = _rgba((120, 240, 255), calc.alfa_columna(self._t, reducir))

    # -- Vecinos que comentan el rumor --

    def _pintar_vecinos(self, mision, estado, dt):
        cerca = False
        if mision is not None and getattr(mision, "tipo", "") == "verificar" and calc.columna_visible(estado):
            mundo = self.escena._mundo
            dx, dz = mundo.punto_interaccion(mision.destino)
            try:
                jugador = self.escena.flujo.jugador_activo()
                cerca = math.hypot(jugador.x - dx, jugador.z - dz) <= calc.DISTANCIA_JUGADOR
            except Exception:            # noqa: BLE001
                cerca = False
        if not cerca:
            self._soltar_vecinos()
            return
        self._t_repaso -= dt
        if self._t_repaso > 0 and self._vecinos:
            return
        self._t_repaso = REPASO_VECINOS_S
        from frontend.rectificar_visual import _personajes_del_mundo
        candidatos = list(_personajes_del_mundo(self.escena))
        posiciones = [(p.world_x, p.world_z) if p.enabled else None for p in candidatos]
        elegidos = [candidatos[i] for i in calc.mas_cercanos(posiciones, (dx, dz))]
        tema = asignacion.tema_de(mision)
        postura = calc.postura_por_tema(tema)
        frases = calc.comentarios(getattr(mision, "rumor", ""), getattr(mision, "pista", ""), tema)
        self._soltar_vecinos(esconder=False)
        from frontend import npc_postura
        for k, npc in enumerate(elegidos[:calc.MAX_COMENTARIOS]):
            npc._postura_forzada = postura
            self._vecinos.append(npc)
            if k < len(frases):
                npc_postura.ancla_cabeza(npc)            # (se crea una sola vez por NPC)
                self._comentarios.append((npc, frases[k]))

    def _soltar_vecinos(self, esconder=True):
        for npc in self._vecinos:
            try:
                npc._postura_forzada = None
            except Exception:            # noqa: BLE001
                pass
        self._vecinos = []
        self._comentarios = []
        if esconder and self._capa is not None:
            self._capa.fijar("llegada", ())    # sin globos de vecinos (la capa apaga los suyos con fundido)

    # -- El teléfono que se acerca al pulsar E --

    def _pintar_telefono(self, dt, reducir):
        if self._t_telefono is None:
            self.pantalla.enabled = False
            return
        self._t_telefono += dt
        k = calc.acercar_telefono(self._t_telefono, reducir)
        telefono = getattr(self.escena.hud, "telefono_ui", None)
        origen = (0.78, -0.38)
        if telefono is not None:
            try:
                p = telefono.get_position(relative_to=camera.ui)
                origen = (p[0], p[1])
            except Exception:            # noqa: BLE001
                pass
        ancho = 0.08 + (16 / 9 + 0.1 - 0.08) * k
        alto = 0.13 + (1.1 - 0.13) * k
        self.pantalla.position = (origen[0] * (1 - k), origen[1] * (1 - k), -0.5)
        self.pantalla_marco.scale = (ancho, alto)
        self.pantalla_brillo.scale = (ancho * 0.92, alto * 0.9)
        self.pantalla.enabled = True
        if self._t_telefono > calc.DUR_TELEFONO + 0.9:
            self._t_telefono = None
            self.pantalla.enabled = False

    # -- Limpieza / guardián --

    def _ocultar_todo(self):
        if self.columna is not None:
            self.columna.enabled = False
        self._soltar_vecinos()
        self.pantalla.enabled = False

    def _apagar(self):
        self.roto = True
        try:
            self._ocultar_todo()
            telefono = getattr(self.escena.hud, "telefono_ui", None)
            if telefono is not None and hasattr(self, "_x_telefono"):
                telefono.x = self._x_telefono
            if self.escena._cinematica and self.escena.director.activa:
                self.escena.director.cancelar()
                self.escena.camara.soltar_control()
                self.escena._cinematica = False
        except Exception:                # noqa: BLE001
            pass

    def on_disable(self):
        # El HUD se apaga al salir del mundo: los vecinos recuperan su postura y el teléfono no se queda a medias.
        try:
            self._soltar_vecinos()
            if self._t_telefono is not None and not self.escena.enabled:
                self._t_telefono = None
                self.pantalla.enabled = False
        except Exception:                # noqa: BLE001
            pass


def _partir(texto, ancho):
    palabras, lineas, actual = str(texto).split(), [], ""
    for palabra in palabras:
        if actual and len(actual) + 1 + len(palabra) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = f"{actual} {palabra}".strip()
    if actual:
        lineas.append(actual)
    return "\n".join(lineas[:4])
