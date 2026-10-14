# Cámara en tercera persona orbitable (Ursina). Los cálculos viven en
# frontend/camara_calculos.py (puros, con tests); aquí solo se lee el ratón, se hace el
# raycast y se coloca `camera`.
#
# - Ratón (mientras `mouse.locked`): yaw libre, pitch 5°-60°. Rueda: zoom 3.5-12 m.
# - Colisión: raycast del pivote hacia la cámara; si un edificio tapa al personaje la
#   cámara se acerca (rápido) y al despejarse se aleja (lento, sin "saltar").
# - Terreno: `altura_en(x, z)` (callable opcional) da la altura del suelo: el pivote sigue la
#   altura bajo el jugador y la cámara nunca baja de ALTURA_MIN_SUELO sobre el terreno.
# - `yaw` es público: lo leen el controlador (W = hacia donde mira) y el minimapa.
# - `bloquear(True)`: el ratón no gira la cámara (teléfono/pausa abiertos).
# - `tomar_control()` / `soltar_control()`: una cinemática mueve `camera` a mano; mientras
#   tanto esta cámara no la toca.
#
# Es hija de EscenaMundo: Ursina no le entrega update()/input() con la escena desactivada.
# Entre entradas a la escena, guarda y restaura el estado de `camera` (las escenas 2D
# esperan la cámara de siempre).

import math

from ursina import Entity, Vec3, camera, mouse, raycast, scene, time

from frontend import camara_calculos as cc

SENSIBILIDAD = 130.0          # grados por unidad de mouse.velocity
PITCH_MIN, PITCH_MAX = 5.0, 60.0
DISTANCIA_MIN, DISTANCIA_MAX = 3.5, 12.0
DISTANCIA_INICIAL = 7.0
PITCH_INICIAL = 22.0
MARGEN_COLISION = 0.4
ALTURA_MIN_SUELO = 0.4        # m mínimos entre la cámara y el terreno
DISTANCIA_MIN_COLISION = 1.2  # la cámara nunca se mete más cerca del pivote que esto
FOV = 65
PLANO_CERCANO = 0.1
PLANO_LEJANO = 500
RAPIDEZ_SEGUIR = 10.0         # el pivote alcanza al jugador (caminando casi no se nota)
RAPIDEZ_VIAJE = 3.0           # cuando está lejos (cambio de turno) se desliza más despacio
VELOCIDAD_VIAJE = 32.0        # m/s máximos del pivote al viajar (sin tirón inicial al cambiar de turno)


class CamaraTerceraPersona(Entity):

    # raiz_colisiones: Entity cuyos hijos con collider bloquean la cámara (los edificios).
    def __init__(self, raiz_colisiones=None, **opciones):
        super().__init__(**opciones)
        self.raiz_colisiones = raiz_colisiones
        self.yaw = 0.0
        self.pitch = PITCH_INICIAL
        self.distancia = DISTANCIA_INICIAL       # la que pide el jugador (rueda)
        self.distancia_real = DISTANCIA_INICIAL  # la que queda tras la colisión y el suavizado
        self.objetivo = None                     # callable -> (x, z) del jugador al que sigue
        self.altura_en = None                    # callable (x, z) -> y del suelo (None = plano)
        self.ignorar = []                        # entidades que el raycast atraviesa (personajes)
        self.bloqueada = False
        self.controlada = False
        self._pivote = None                      # (x, z) suavizado
        self._guardada = None

    # -- Estado --

    def bloquear(self, valor):
        self.bloqueada = bool(valor)

    def tomar_control(self):
        self.controlada = True

    # Devuelve la cámara a la órbita. Parte de la distancia pedida para que no "salte".
    def soltar_control(self):
        self.controlada = False
        self.distancia_real = self.distancia

    def pivote(self):
        return self._pivote

    # Pone el pivote sobre el objetivo y la cámara en su sitio, sin deslizar.
    def colocar_ya(self):
        if self.objetivo is not None:
            self._pivote = tuple(self.objetivo())
            self.distancia_real = self.distancia
            self.actualizar(0)

    # -- Frame --

    def update(self):
        if self.controlada:
            return
        if mouse.locked and not self.bloqueada:
            self.yaw, self.pitch = cc.aplicar_raton(
                self.yaw, self.pitch, mouse.velocity[0], mouse.velocity[1], SENSIBILIDAD,
                PITCH_MIN, PITCH_MAX)
        self.actualizar(time.dt)

    def input(self, key):
        if self.controlada or self.bloqueada:
            return
        if key == "scroll up":
            self.distancia = cc.aplicar_zoom(self.distancia, 1, DISTANCIA_MIN, DISTANCIA_MAX)
        elif key == "scroll down":
            self.distancia = cc.aplicar_zoom(self.distancia, -1, DISTANCIA_MIN, DISTANCIA_MAX)

    # Sigue al objetivo, resuelve la colisión y coloca la cámara de Ursina.
    def actualizar(self, dt):
        if self.objetivo is None:
            return
        meta = self.objetivo()
        if self._pivote is None:
            self._pivote = tuple(meta)
        px, pz = self._pivote
        rapidez = cc.rapidez_de_seguimiento(math.hypot(meta[0] - px, meta[1] - pz), RAPIDEZ_SEGUIR, RAPIDEZ_VIAJE)
        self._pivote = cc.avanzar_pivote((px, pz), meta, dt, rapidez, vmax=VELOCIDAD_VIAJE)

        suelo = self.altura_en(*self._pivote) if self.altura_en is not None else 0.0
        pivote = cc.pivote_del_jugador(*self._pivote, suelo=suelo)
        impacto = self._distancia_hasta_obstaculo(pivote)
        objetivo = cc.distancia_con_colision(
            self.distancia, impacto, MARGEN_COLISION, DISTANCIA_MIN_COLISION)
        suave = cc.suavizar_distancia(self.distancia_real, objetivo, dt)
        # Hacia adentro nunca por detrás de la pared: el suavizado solo afloja el alejarse.
        self.distancia_real = min(suave, objetivo)
        posicion = cc.posicion_orbital(pivote, self.yaw, self.pitch, self.distancia_real)
        if self.altura_en is not None:
            minimo = self.altura_en(posicion[0], posicion[2]) + ALTURA_MIN_SUELO
            if posicion[1] < minimo:
                posicion = (posicion[0], minimo, posicion[2])
        camera.position = posicion
        camera.rotation = (self.pitch, self.yaw, 0)

    # Distancia del pivote al primer obstáculo en dirección a la cámara deseada (None si
    # no hay). El raycast no toca personajes (`ignorar`) ni nada sin collider.
    def _distancia_hasta_obstaculo(self, pivote):
        if self.raiz_colisiones is None:
            return None
        deseada = Vec3(*cc.posicion_orbital(pivote, self.yaw, self.pitch, self.distancia))
        origen = Vec3(*pivote)
        direccion = (deseada - origen).normalized()
        golpe = raycast(origen, direccion, distance=self.distancia,
                        traverse_target=self.raiz_colisiones, ignore=list(self.ignorar))
        return golpe.distance if golpe.hit else None

    # -- Cámara de Ursina: guardar / poner / restaurar --

    # Guarda UNA vez el estado previo (el de las escenas 2D) y pone la cámara perspectiva.
    def preparar_camara(self):
        if self._guardada is None:
            self._guardada = {
                "parent": camera.parent, "orthographic": camera.orthographic,
                "fov": camera.fov, "position": camera.position, "rotation": camera.rotation,
                "near": camera.clip_plane_near, "far": camera.clip_plane_far,
            }
        camera.parent = scene
        camera.orthographic = False
        camera.fov = FOV
        camera.clip_plane_near = PLANO_CERCANO
        camera.clip_plane_far = PLANO_LEJANO

    # Orden: padre, tipo de lente, fov (depende del tipo), planos, pose.
    def restaurar_camara(self):
        guardada = self._guardada
        if guardada is None:
            return
        camera.parent = guardada["parent"]
        camera.orthographic = guardada["orthographic"]
        camera.fov = guardada["fov"]
        camera.clip_plane_near = guardada["near"]
        camera.clip_plane_far = guardada["far"]
        camera.position = guardada["position"]
        camera.rotation = guardada["rotation"]
        self._guardada = None
