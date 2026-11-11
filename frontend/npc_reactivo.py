# NPC clave con el que se HABLA (Ursina): un cuerpo con modelo .glb (frontend/npc_modelo.py) en el ancla que dice
# backend/datos/npc_clave.json, que cumple el Protocol Interaccion de frontend/economia_mundo.py (prioridad, aviso,
# usar, actualizar). Con E cerca abre la caja de diálogo (frontend/dialogo_ui.py) con lo que decide
# backend/logica/dialogos.py según el GameState. Sin GameState (en línea o ALCALDE_GAMESTATE=0) no avisa ni hace nada.
#
# El cuerpo no camina, pero REACCIONA: cuando el jugador se acerca a menos de RADIO_MIRAR m gira con suavidad para
# mirarlo y lo sigue con el cuerpo; cuando se aleja, vuelve a su rumbo de siempre. Rendimiento: sin update propio por
# frame; la economía llama a actualizar(dt) (un giro son dos restas y un atan2) y cada LOD_S se revisa la distancia a la
# cámara para apagarlo si está lejos.

import math

from backend.logica import dialogos
from backend.logica.multitud_conducta import girar_suave

RADIO_MIRAR = 7.0                # m: más cerca, el NPC se vuelve hacia el jugador
RADIO_DEJAR_DE_MIRAR = 9.0       # m: más lejos, vuelve a su rumbo (histéresis: sin vaivén en el borde)
GIRO_RAPIDEZ, GIRO_MAXIMO = 4.0, 160.0      # 1/s y grados/s del giro (más calmado que el de los peatones)


# Rumbo (grados) al que debe tender el NPC: hacia el jugador si está cerca (con histéresis según `mirando`), o su rumbo
# base. Devuelve (rumbo objetivo, mirando). Puro, para las pruebas.
def rumbo_deseado(x, z, base, jugador, mirando):
    if jugador is None:
        return base, False
    dx, dz = jugador[0] - x, jugador[1] - z
    d = math.hypot(dx, dz)
    limite = RADIO_DEJAR_DE_MIRAR if mirando else RADIO_MIRAR
    if d > limite or d < 0.05:
        return base, False
    return math.degrees(math.atan2(dx, dz)), True

RADIO_USO = 2.2
PRIORIDAD = 9                    # entre el vendedor (10) y el computador (8)
LOD_S = 0.5
DISTANCIA_VISIBLE = 90.0         # m desde la cámara; más lejos el NPC se apaga (no se anima ni se dibuja)
SEMILLA_NPC = 2026


class NpcReactivo:

    prioridad = PRIORIDAD

    # clave: NpcClave. caja: CajaDialogo. obtener_gs(): GameState o None. catalogo: CatalogoDialogos.
    # fabrica(indice, semilla, aspecto, rasgos, ropa, parent=...) -> personaje; por defecto frontend.npc_modelo.crear_npc.
    def __init__(self, escena, clave, x, z, rumbo, caja, obtener_gs, catalogo, fabrica=None):
        self._escena = escena
        self.clave = clave
        self.x, self.z, self.rumbo = float(x), float(z), float(rumbo)
        self._caja, self._obtener_gs, self._catalogo = caja, obtener_gs, catalogo
        self._t_lod = 0.0
        self._rumbo_actual = self.rumbo
        self.mirando = False             # ¿está vuelto hacia el jugador?
        self.npc = self._crear_cuerpo(fabrica)

    def _crear_cuerpo(self, fabrica):
        try:
            if fabrica is None:
                from frontend.npc_modelo import crear_npc as fabrica
            from frontend.peatones import ROPA
            from frontend.peatones_calculos import aspecto_peaton, rasgos_peaton
            i = self.clave.modelo
            npc = fabrica(i, SEMILLA_NPC, aspecto_peaton(i, SEMILLA_NPC), rasgos_peaton(i, SEMILLA_NPC),
                          ROPA[i % len(ROPA)], parent=self._escena)
            npc.aro.enabled = False
            self._poner_nombre(npc)
            npc.suelo = self._escena._mundo.altura
            npc.colocar(self.x, self.z)
            npc.fijar_rumbo(self.rumbo)
            return npc
        except Exception as error:
            print(f"[consecuencias] {self.clave.id}: no se pudo crear el cuerpo ({error}); queda sin modelo")
            return None

    def _poner_nombre(self, npc):
        try:
            from frontend.componentes import destruir_arbol
            from frontend.piezas import etiqueta, silenciar
            npc.nombre = self.clave.nombre
            y = npc.etiqueta.y
            destruir_arbol(npc.etiqueta)
            npc.etiqueta = silenciar(etiqueta(self.clave.nombre, parent=npc, y=y, scale=8))
        except Exception as error:
            print(f"[consecuencias] {self.clave.id}: no se pudo poner el nombre ({error})")

    # -- Protocol Interaccion --

    def _cerca(self, x, z):
        return math.hypot(x - self.x, z - self.z) <= RADIO_USO

    def aviso(self, jugador, x, z):
        if not self._cerca(x, z) or self._obtener_gs() is None:
            return None
        return f"E: hablar con {self.clave.nombre}"

    def usar(self, jugador, economia=None):
        gs = self._obtener_gs()
        if gs is None or not self._cerca(jugador.x, jugador.z) or economia is None:
            return False
        respuesta = dialogos.elegir(self.clave, gs, self._catalogo)
        self._caja.preparar(respuesta, self.clave.retrato, self.clave.rol,
                            al_final=lambda: dialogos.aplicar_ayuda(gs, respuesta))
        if not economia.abrir_modal(self._caja, None):
            return False
        self._mirar_a(jugador)
        return True

    def _mirar_a(self, jugador):
        if self.npc is None:
            return
        try:
            self._rumbo_actual = math.degrees(math.atan2(jugador.x - self.x, jugador.z - self.z))
            self.mirando = True
            self.npc.fijar_rumbo(self._rumbo_actual)
        except Exception:
            pass

    # Gira con suavidad hacia el jugador activo si está cerca, o de vuelta a su rumbo base.
    def _seguir_con_la_mirada(self, dt):
        try:
            activo = self._escena.flujo.jugador_activo()
            jugador = (activo.x, activo.z)
        except Exception:
            jugador = None
        objetivo, self.mirando = rumbo_deseado(self.x, self.z, self.rumbo, jugador, self.mirando)
        if abs((objetivo - self._rumbo_actual + 180.0) % 360.0 - 180.0) < 0.3:
            return
        self._rumbo_actual = girar_suave(self._rumbo_actual, objetivo, dt, GIRO_RAPIDEZ, GIRO_MAXIMO)
        self.npc.fijar_rumbo(self._rumbo_actual)

    def actualizar(self, dt):
        if self.npc is None:
            return
        if self.npc.enabled:
            self._seguir_con_la_mirada(dt)
        self._t_lod -= dt
        if self._t_lod > 0:
            return
        self._t_lod = LOD_S
        try:
            from ursina import camera
            lejos = (camera.world_position - self.npc.world_position).length() > DISTANCIA_VISIBLE
        except Exception:
            return
        if bool(self.npc.enabled) == lejos:
            self.npc.enabled = not lejos
        ignorar = getattr(getattr(self._escena, "camara", None), "ignorar", None)
        if isinstance(ignorar, list) and self.npc not in ignorar:
            ignorar.append(self.npc)                # la cámara no se acerca al NPC

    def destruir(self):
        if self.npc is not None:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self.npc)
            self.npc = None
