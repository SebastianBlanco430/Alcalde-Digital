# Cámara en tercera persona orbitable (Ursina). Los cálculos viven en
# frontend/camara_calculos.py (puros, con tests); aquí solo se lee el ratón, se hace el
# raycast y se coloca `camera`.
#
# - Ratón (mientras `mouse.locked`): yaw libre, pitch 5°-60°. Rueda: zoom 3.5-12 m.
# - Colisión: raycast del pivote hacia la cámara; si un edificio tapa al personaje la
#   cámara se acerca (rápido) y al despejarse se aleja (lento, sin "saltar"). Contra la ladera
#   no hay raycast: se muestrea la altura del suelo a lo largo del tramo (camara_calculos).
# - `suelo(x, z)`: altura del terreno (MundoCiudad.altura); el pivote va sobre ella.
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
from frontend.geometria_mundo import apoyo_de_caja

SENSIBILIDAD = 130.0          # grados por unidad de mouse.velocity
PITCH_MIN, PITCH_MAX = 5.0, 60.0
DISTANCIA_MIN, DISTANCIA_MAX = 3.5, 12.0
DISTANCIA_INICIAL = 7.0
PITCH_INICIAL = 22.0
MARGEN_COLISION = 0.4
DISTANCIA_MIN_COLISION = 1.2  # la cámara nunca se mete más cerca del pivote que esto
# COLISIÓN ANALÍTICA (aditivo): además del raycast, la cámara no entra en las casas y edificios del
# mundo (cajas 2D con altura, camara_calculos). Las ~263 casas decorativas sí tienen collider, pero
# el raycast no basta: DISTANCIA_MIN_COLISION (1.2 m) dejaba la cámara DENTRO del muro cuando el jugador
# estaba a menos de ~1.6 m de él. False = comportamiento de antes.
CAMARA_ANALITICA = True
MINIMO_ANALITICO = 0.3        # m: lo más cerca del pivote que la colisión analítica deja la cámara
FOV = 65
PLANO_CERCANO = 0.1
PLANO_LEJANO = 500
RAPIDEZ_SEGUIR = 10.0         # el pivote alcanza al jugador (caminando casi no se nota)
RAPIDEZ_VIAJE = 3.0           # cuando está lejos (cambio de turno) se desliza más despacio
FOV_EXTRA_CORRER = 4.0        # grados de FOV que se suman al correr (sube en ~250 ms, baja en ~400 ms)
VELOCIDAD_VIAJE = 32.0        # m/s máximos del pivote al viajar (sin tirón inicial al cambiar de turno)


class CamaraTerceraPersona(Entity):

    # raiz_colisiones: Entity cuyos hijos con collider bloquean la cámara (los edificios).
    # obstaculos (opcional): lista de obstáculos de camara_calculos, o el mundo (MundoCiudad), del que
    # se leen casas y edificios (solo lectura). None = solo el raycast de siempre.
    def __init__(self, raiz_colisiones=None, suelo=None, obstaculos=None, **opciones):
        super().__init__(**opciones)
        self.raiz_colisiones = raiz_colisiones
        self.obstaculos = obstaculos_de_camara(obstaculos) if hasattr(obstaculos, "obstaculos") else list(obstaculos or [])
        self.suelo = suelo or (lambda x, z: 0.0)
        self.yaw = 0.0
        self.pitch = PITCH_INICIAL
        self.distancia = DISTANCIA_INICIAL       # la que pide el jugador (rueda)
        self.distancia_real = DISTANCIA_INICIAL  # la que queda tras la colisión y el suavizado
        self.objetivo = None                     # callable -> (x, z) del jugador al que sigue
        self.ignorar = []                        # entidades que el raycast atraviesa (personajes)
        self.bloqueada = False
        self.distancia_extra = 0.0               # VEHÍCULOS (aditivo): m extra de distancia, grados de FOV y m de altura del pivote
        self.fov_extra = 0.0                     # (los fija vehiculo_mundo con la velocidad; 0 = comportamiento de siempre)
        self.altura_extra = 0.0
        self.controlada = False
        self._pivote = None                      # (x, z) suavizado
        self._guardada = None
        self._fov = float(FOV)                   # FOV suavizado (FOV al caminar, +FOV_EXTRA_CORRER al correr)
        self._meta_previa = None                 # (x, z) del objetivo en el frame anterior
        self._reposo = (0.0, 0.0)                # sesgo del recentrado del cursor (ver quitar_reposo)

    # -- Estado --

    def bloquear(self, valor):
        self.bloqueada = bool(valor)

    def tomar_control(self):
        self.controlada = True
        self._reposo = (0.0, 0.0)
        self._meta_previa = None
        camera.fov = FOV                         # las cinemáticas parten del FOV normal, no del ensanchado al correr
        self._fov = float(FOV)

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
            vx, vy = cc.quitar_reposo(mouse.velocity, self._reposo)
            self.yaw, self.pitch = cc.aplicar_raton(
                self.yaw, self.pitch, vx, vy, SENSIBILIDAD, PITCH_MIN, PITCH_MAX)
            if mouse.velocity[0] or mouse.velocity[1]:      # hubo recentrado: el cursor quedó en prev_x/prev_y
                self._reposo = (mouse.prev_x, mouse.prev_y)
        else:
            self._reposo = (0.0, 0.0)
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

        px, pz = self._pivote
        pivote = cc.pivote_del_jugador(px, pz, suelo=self.suelo(px, pz))
        if self.altura_extra:
            pivote = (pivote[0], pivote[1] + self.altura_extra, pivote[2])
        pedida = self.distancia + self.distancia_extra
        impacto = self._distancia_hasta_obstaculo(pivote)
        deseada = cc.posicion_orbital(pivote, self.yaw, self.pitch, pedida)
        impacto_suelo = cc.distancia_libre_de_suelo(pivote, deseada, self.suelo)
        if impacto_suelo is not None:
            impacto = impacto_suelo if impacto is None else min(impacto, impacto_suelo)
        objetivo = cc.distancia_con_colision(
            pedida, impacto, MARGEN_COLISION, DISTANCIA_MIN_COLISION)
        if CAMARA_ANALITICA and self.obstaculos:
            objetivo = min(objetivo, cc.distancia_libre_analitica(
                pivote, deseada, self.obstaculos, MARGEN_COLISION, MINIMO_ANALITICO))
        suave = cc.suavizar_distancia(self.distancia_real, objetivo, dt)
        # Hacia adentro nunca por detrás de la pared: el suavizado solo afloja el alejarse.
        self.distancia_real = min(suave, objetivo)
        camera.position = cc.posicion_orbital(pivote, self.yaw, self.pitch, self.distancia_real)
        camera.rotation = (self.pitch, self.yaw, 0)
        self._actualizar_fov(meta, dt)

    # FOV dinámico: +FOV_EXTRA_CORRER al correr. La señal sale de la velocidad real del objetivo
    # (no hay que tocar el controlador); un salto de posición (cambio de turno) no cuenta como correr.
    def _actualizar_fov(self, meta, dt):
        if dt <= 0:
            self._meta_previa = tuple(meta)
            return
        corre = cc.corriendo_por_velocidad(cc.velocidad_del_objetivo(self._meta_previa, meta, dt))
        self._meta_previa = tuple(meta)
        self._fov = cc.fov_al_correr(self._fov, FOV, corre, dt, FOV_EXTRA_CORRER)
        camera.fov = self._fov + self.fov_extra

    # Distancia del pivote al primer obstáculo en dirección a la cámara deseada (None si
    # no hay). El raycast no toca personajes (`ignorar`) ni nada sin collider.
    def _distancia_hasta_obstaculo(self, pivote):
        if self.raiz_colisiones is None:
            return None
        pedida = self.distancia + self.distancia_extra
        deseada = Vec3(*cc.posicion_orbital(pivote, self.yaw, self.pitch, pedida))
        origen = Vec3(*pivote)
        direccion = (deseada - origen).normalized()
        golpe = raycast(origen, direccion, distance=pedida,
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
        self._fov = float(FOV)
        self._meta_previa = None
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


# Obstáculos de cámara (camara_calculos) de un MundoCiudad, solo lectura: las casas decorativas y los
# edificios, con el mismo tramo vertical que sus colliders (ciudad_3d). Árboles, farolas y bancos no
# cuentan: son finos y la cámara los atraviesa sin taparse la pantalla.
def obstaculos_de_camara(mundo):
    lista = []
    for o in mundo.obstaculos():
        if o.tipo == "casa" and o.es_caja:
            bajo, alto = apoyo_de_caja(mundo.altura, o.cx, o.cz, o.ancho, o.fondo)
            lista.append(cc.obstaculo_caja(o.cx, o.cz, o.ancho, o.fondo, bajo, alto + o.alto_total))
    for e in mundo.edificios():
        lista.append(cc.obstaculo_caja(e.cx, e.cz, e.ancho, e.fondo, e.y, e.y + e.alto))
    return lista
