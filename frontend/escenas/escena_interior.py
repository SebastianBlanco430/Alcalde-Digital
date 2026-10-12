# Interior 3D de un edificio (Ursina): UNA oficina reutilizable con un tema por lugar
# (frontend/temas_interior.py: colores de pared, piso y acento, 2-3 props y el letrero).
#
# Dos cinemáticas (el guion y las duraciones viven en frontend/guion_cinematicas.py):
#   modo 'sentarse':   el personaje entra por la puerta, camina al escritorio, se SIENTA, pone
#                      las manos en el teclado y la cámara se acerca al MONITOR hasta llenar la
#                      pantalla; el monitor "enciende" (Civitas - iniciando sesión de <Rol>),
#                      destello y se llama `al_terminar` (ConexionFlujo abre el juego).
#   modo 'levantarse': sentado, se levanta (POSE_SENTADO -> POSE_PARADO) y se llama `al_terminar`.
#
# La habitación está centrada en el origen; el mundo exterior está desactivado mientras tanto, así
# que no se mezclan. La cámara es propia (no orbital): se guarda y restaura el estado previo
# (las escenas 2D esperan la cámara de siempre). El destello vive en camera.ui como entidad
# aparte para poder desvanecerse DESPUÉS de que esta escena se desactive (cuando entra el juego).

import math

from ursina import Entity, Text, camera, color, destroy, scene, time
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader

from backend.logica.roles import ROLES
from frontend import camara_calculos as cc
from frontend import guion_cinematicas as guion
from frontend import poses
from frontend.cinematica import ease_in_out, lerp, lerp_angulo, lerp_vec3
from frontend.componentes import rgb
from frontend.director_cinematica import DirectorCinematica
from frontend.escenas.escena_base import Escena
from frontend.personaje import Personaje
from frontend.piezas import encender_luz, pieza, silenciar
from frontend.temas_interior import tema_de

COLOR_MADERA = (150, 104, 66)
COLOR_MADERA_OSCURA = (96, 66, 44)
COLOR_METAL = (62, 64, 74)
COLOR_PANTALLA_APAGADA = (12, 14, 20)
COLOR_PANTALLA_ENCENDIDA = (22, 44, 96)
COLOR_DESTELLO = (200, 245, 255)
GOLPES_TECLEO = 2                    # "golpes" de teclear durante el tramo
DURACION_DESVANECER = 0.25

# Anclas en las paredes: (x, z, rotation_y). El +z LOCAL del ancla apunta hacia el interior de
# la habitación, +x local va a lo largo de la pared y +y es la altura.
ANCLAS = {
    "oeste": (-guion.SALA_ANCHO / 2, 0.4, 90),
    "norte": (-1.2, guion.SALA_FONDO / 2, 180),
    "este": (guion.SALA_ANCHO / 2, -0.4, -90),
    "letrero": (guion.POSICION_PANTALLA[0], guion.SALA_FONDO / 2, 180),
}


# Destello blanco-cian que cubre la pantalla al "entrar" al monitor. Vive en camera.ui, fuera de
# la escena, y se desvanece solo (update) aunque la escena ya esté desactivada.
class Destello(Entity):

    def __init__(self, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(model="quad", color=color.rgba(0, 0, 0, 0), scale=(4, 4), z=-90,
                         enabled=False, **opciones)
        self.alfa = 0.0
        self._desvaneciendo = False

    def poner(self, alfa):
        self._desvaneciendo = False
        self.alfa = min(1.0, max(0.0, alfa))
        self.enabled = self.alfa > 0
        self.color = color.rgba32(*COLOR_DESTELLO, int(255 * self.alfa))

    def desvanecer(self):
        self._desvaneciendo = self.alfa > 0

    def avanzar(self, dt):
        if not self._desvaneciendo:
            return
        self.poner(self.alfa - dt / DURACION_DESVANECER)
        self._desvaneciendo = self.alfa > 0

    def update(self):
        self.avanzar(time.dt)


class EscenaInterior(Escena):

    # escala_tiempo: multiplica las duraciones de las cinemáticas (0 = instantáneas, para los scripts).
    def __init__(self, escala_tiempo=1.0, **opciones):
        opciones.setdefault("parent", scene)
        super().__init__(**opciones)
        self.escala_tiempo = escala_tiempo
        self.lugar = None
        self.modo = None
        self.jugador = None
        self.personaje = None
        self._al_terminar = None
        self._camara_guardada = None
        self._tematico = []               # entidades del tema actual (se rehacen por lugar)

        self._construir_sala()
        self.pantalla_texto = Text("", parent=self, origin=(0, 0), scale=1.0,
                                   color=color.rgb32(210, 230, 255))
        self.pantalla_texto.position = (guion.POSICION_PANTALLA[0], guion.POSICION_PANTALLA[1],
                                        guion.POSICION_PANTALLA[2] - 0.03)
        # Con sombras: sin mapa de sombra el shader lit_with_shadows da todo por "en sombra" (oscuro).
        self.luz = DirectionalLight(parent=self, shadows=True, shadow_map_resolution=(1024, 1024))
        self.luz.look_at((-0.6, -1.4, 0.8))
        self.ambiente = AmbientLight(parent=self, color=color.rgba32(120, 120, 130, 255))
        self.director = DirectorCinematica(parent=self)
        self.destello = Destello()
        silenciar(self.pantalla_texto)
        self.luz.update_bounds(self)        # el volumen de sombra abarca la habitación
        self._luces(False)                 # se enciende al entrar (ver al_entrar)

    # -- Habitación (geometría fija) --

    def _construir_sala(self):
        w, d, h = guion.SALA_ANCHO, guion.SALA_FONDO, guion.SALA_ALTO
        # Paredes, piso y techo son entidades SUELTAS (7): el tema les cambia el color.
        self._piso = pieza(parent=self, model="cube", position=(0, -0.05, 0), scale=(w, 0.1, d))
        self._paredes = [
            pieza(parent=self, model="cube", position=(0, h / 2, d / 2 + 0.05), scale=(w + 0.2, h, 0.1)),      # norte
            pieza(parent=self, model="cube", position=(0, h / 2, -d / 2 - 0.05), scale=(w + 0.2, h, 0.1)),     # sur
            pieza(parent=self, model="cube", position=(w / 2 + 0.05, h / 2, 0), scale=(0.1, h, d)),            # este
            pieza(parent=self, model="cube", position=(-w / 2 - 0.05, h / 2, 0), scale=(0.1, h, d)),           # oeste
        ]
        # Sin techo: la cámara nunca lo ve y una habitación cerrada deja la luz direccional en sombra.
        for e in (self._piso, *self._paredes):
            silenciar(e)
        # Lo demás (puerta, escritorio, monitor, silla, ventana, rodapié) es fijo y se combina.
        grupo = Entity(parent=self, shader=lit_with_shadows_shader)
        for (x, z, sx, sz) in ((0, d / 2 - 0.03, w, 0.06), (0, -d / 2 + 0.03, w, 0.06),
                               (w / 2 - 0.03, 0, 0.06, d), (-w / 2 + 0.03, 0, 0.06, d)):
            pieza(parent=grupo, model="cube", color=rgb((236, 236, 240)), position=(x, 0.08, z), scale=(sx, 0.16, sz))
        self._puerta_visible(grupo)
        self._escritorio(grupo)
        self._ventana(grupo)
        grupo.combine()
        silenciar(grupo)
        self._grupo_fijo = grupo
        self._pantalla()

    # Puerta de entrada en la pared sur (x = PUERTA_SALA[0]), pegada a la cara interior.
    def _puerta_visible(self, grupo):
        x = guion.PUERTA_SALA[0]
        z = -guion.SALA_FONDO / 2
        pieza(parent=grupo, model="cube", color=rgb((30, 30, 38)), position=(x, 1.15, z + 0.015), scale=(1.14, 2.34, 0.03))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_MADERA_OSCURA), position=(x, 1.1, z + 0.04), scale=(1.0, 2.2, 0.03))
        pieza(parent=grupo, model="sphere", color=rgb((220, 200, 120)), position=(x + 0.36, 1.05, z + 0.08), scale=0.08)

    def _escritorio(self, grupo):
        mx, my, mz = guion.POSICION_PANTALLA
        madera = rgb(COLOR_MADERA)
        pieza(parent=grupo, model="cube", color=madera, position=(mx, 0.73, 2.0), scale=(1.8, 0.05, 0.8))   # tablero
        for dx in (-0.85, 0.85):
            pieza(parent=grupo, model="cube", color=rgb(COLOR_MADERA_OSCURA), position=(mx + dx, 0.36, 2.0),
                  scale=(0.06, 0.72, 0.76))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_MADERA_OSCURA), position=(mx, 0.45, 2.38), scale=(1.7, 0.6, 0.03))
        # monitor: cuerpo, pie y base (la pantalla es aparte: cambia de color)
        pieza(parent=grupo, model="cube", color=rgb(COLOR_METAL), position=(mx, my, mz + 0.03),
              scale=(guion.ANCHO_PANTALLA + 0.06, guion.ALTO_PANTALLA + 0.06, 0.06))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_METAL), position=(mx, 0.84, mz + 0.06), scale=(0.06, 0.2, 0.05))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_METAL), position=(mx, 0.76, mz + 0.04), scale=(0.3, 0.02, 0.2))
        # teclado y ratón
        pieza(parent=grupo, model="cube", color=rgb((40, 42, 52)), position=(mx, 0.77, 1.78), scale=(0.46, 0.02, 0.15))
        pieza(parent=grupo, model="cube", color=rgb((40, 42, 52)), position=(mx + 0.4, 0.77, 1.8), scale=(0.07, 0.025, 0.11))
        # lámpara de escritorio
        pieza(parent=grupo, model="cube", color=rgb((200, 200, 205)), position=(mx - 0.75, 0.9, 2.2), scale=(0.03, 0.3, 0.03))
        pieza(parent=grupo, model="sphere", color=rgb((255, 238, 170)), position=(mx - 0.75, 1.08, 2.15), scale=0.14)
        # silla
        silla = rgb((52, 56, 74))
        pieza(parent=grupo, model="cube", color=silla, position=(guion.ASIENTO[0], 0.45, guion.ASIENTO[1]), scale=(0.48, 0.07, 0.48))
        pieza(parent=grupo, model="cube", color=silla, position=(guion.ASIENTO[0], 0.78, guion.ASIENTO[1] - 0.22), scale=(0.46, 0.55, 0.06))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_METAL), position=(guion.ASIENTO[0], 0.22, guion.ASIENTO[1]), scale=(0.06, 0.4, 0.06))
        pieza(parent=grupo, model="cube", color=rgb(COLOR_METAL), position=(guion.ASIENTO[0], 0.03, guion.ASIENTO[1]), scale=(0.5, 0.05, 0.5))

    def _ventana(self, grupo):
        x = guion.SALA_ANCHO / 2
        pieza(parent=grupo, model="cube", color=rgb((230, 230, 236)), position=(x - 0.04, 1.6, -0.6), scale=(0.07, 1.34, 1.54))
        pieza(parent=grupo, model="cube", color=rgb((150, 205, 235)), position=(x - 0.08, 1.6, -0.6), scale=(0.05, 1.2, 1.4))
        pieza(parent=grupo, model="cube", color=rgb((230, 230, 236)), position=(x - 0.1, 1.6, -0.6), scale=(0.05, 1.2, 0.05))

    # La pantalla del monitor: un quad que mira a -z (hacia quien se sienta) y su texto.
    def _pantalla(self):
        mx, my, mz = guion.POSICION_PANTALLA
        self.pantalla = pieza(parent=self, model="quad", color=rgb(COLOR_PANTALLA_APAGADA),
                              position=(mx, my, mz - 0.012), scale=(guion.ANCHO_PANTALLA, guion.ALTO_PANTALLA),
                              shader=None)
        silenciar(self.pantalla)

    def _encender_pantalla(self, rol):
        self.pantalla.color = rgb(COLOR_PANTALLA_ENCENDIDA)
        self.pantalla_texto.text = f"Civitas\n\nIniciando sesión de\n{rol}"
        self.pantalla_texto.scale = 1.7

    def _apagar_pantalla(self, texto=""):
        self.pantalla.color = rgb(COLOR_PANTALLA_APAGADA)
        self.pantalla_texto.text = texto
        self.pantalla_texto.scale = 1.7

    # -- Tema --

    def aplicar_tema(self, lugar):
        tema = tema_de(lugar)
        self.lugar = lugar
        for e in self._tematico:
            destroy(e)
        self._tematico = []
        for pared in self._paredes:
            pared.color = rgb(tema.pared)
        self._piso.color = rgb(tema.piso)
        # franja de acento a media pared (norte, oeste y este)
        w, d = guion.SALA_ANCHO, guion.SALA_FONDO
        franjas = Entity(parent=self, shader=lit_with_shadows_shader)
        for (x, z, sx, sz) in ((0, d / 2 - 0.02, w, 0.02), (w / 2 - 0.02, 0, 0.02, d), (-w / 2 + 0.02, 0, 0.02, d)):
            pieza(parent=franjas, model="cube", color=rgb(tema.acento), position=(x, 1.0, z), scale=(sx, 0.08, sz))
        franjas.combine()
        silenciar(franjas)
        self._tematico.append(franjas)
        self._tematico.append(self._letrero(tema))
        for indice, prop in enumerate(tema.props):
            self._tematico.append(self._construir_prop(prop, tema, ("oeste", "norte", "este")[indice]))

    # Cartel con el nombre del lugar en la pared norte, sobre el escritorio.
    def _letrero(self, tema):
        ancla = self._ancla("letrero")
        ancho = min(max(len(tema.letrero) * 0.2, 1.6), 3.4)
        pieza(parent=ancla, model="cube", color=rgb((30, 32, 46)), position=(0, 2.3, 0.04), scale=(ancho, 0.34, 0.05))
        Text(tema.letrero, parent=ancla, origin=(0, 0), position=(0, 2.3, 0.0), scale=4.2,
             color=color.rgb32(240, 240, 245), rotation_y=180)
        silenciar(ancla)
        return ancla

    # Un ancla en una pared: +z local hacia el interior, +x local a lo largo de la pared.
    def _ancla(self, nombre):
        x, z, rotacion = ANCLAS[nombre]
        return Entity(parent=self, position=(x, 0, z), rotation_y=rotacion)

    def _construir_prop(self, prop, tema, ancla_nombre):
        ancla = self._ancla(ancla_nombre)
        acento = rgb(tema.acento)
        c = lambda t: rgb(t)           # noqa: E731
        p = lambda **o: pieza(parent=ancla, **o)   # noqa: E731
        if prop == "bandera":
            p(model="cube", color=c((200, 200, 205)), position=(0, 1.2, 0.3), scale=(0.05, 2.4, 0.05))
            p(model="cube", color=acento, position=(0.45, 2.0, 0.3), scale=(0.85, 0.5, 0.03))
            p(model="cube", color=c((240, 240, 245)), position=(0.45, 1.6, 0.3), scale=(0.85, 0.25, 0.03))
        elif prop == "libreria":
            p(model="cube", color=c(COLOR_MADERA_OSCURA), position=(0, 1.0, 0.18), scale=(1.6, 2.0, 0.34))
            for fila in range(4):
                for k in range(7):
                    tono = ((190, 70, 70), (70, 110, 190), (230, 190, 80), (90, 160, 100))[(fila + k) % 4]
                    p(model="cube", color=c(tono), position=(-0.66 + k * 0.22, 0.28 + fila * 0.46, 0.38),
                      scale=(0.14, 0.34, 0.08))
        elif prop == "cafetera":
            p(model="cube", color=c(COLOR_MADERA_OSCURA), position=(0, 0.45, 0.35), scale=(1.4, 0.9, 0.6))
            p(model="cube", color=c((70, 72, 84)), position=(-0.3, 1.1, 0.4), scale=(0.34, 0.4, 0.3))
            p(model="cube", color=acento, position=(-0.3, 1.24, 0.24), scale=(0.2, 0.08, 0.02))
            p(model="cube", color=c((240, 240, 245)), position=(0.3, 0.95, 0.4), scale=(0.1, 0.1, 0.1))
        elif prop == "mostrador":
            p(model="cube", color=acento, position=(0, 0.5, 0.4), scale=(1.5, 1.0, 0.5))
            p(model="cube", color=c(COLOR_MADERA), position=(0, 1.02, 0.4), scale=(1.6, 0.06, 0.6))
        elif prop == "pizarra":
            p(model="cube", color=c((236, 238, 240)), position=(0, 1.5, 0.04), scale=(1.8, 1.0, 0.05))
            p(model="cube", color=acento, position=(0, 2.04, 0.03), scale=(1.86, 0.06, 0.06))
            for k in range(3):
                p(model="cube", color=acento, position=(-0.4 + k * 0.1, 1.5 - k * 0.2, 0.08), scale=(0.9 - k * 0.2, 0.04, 0.02))
        elif prop == "camilla":
            p(model="cube", color=c((236, 240, 244)), position=(0, 0.55, 0.6), scale=(1.9, 0.18, 0.8))
            p(model="cube", color=c(COLOR_METAL), position=(0, 0.28, 0.6), scale=(1.8, 0.04, 0.7))
            p(model="cube", color=acento, position=(0, 1.9, 0.04), scale=(0.5, 0.14, 0.04))
            p(model="cube", color=acento, position=(0, 1.9, 0.04), scale=(0.14, 0.5, 0.04))
        elif prop == "mapa_rutas":
            p(model="cube", color=c((246, 244, 232)), position=(0, 1.5, 0.04), scale=(1.5, 1.0, 0.04))
            for k, tono in enumerate(((66, 133, 244), (234, 67, 53), (52, 168, 83))):
                p(model="cube", color=c(tono), position=(-0.4 + k * 0.4, 1.5, 0.07), scale=(0.06, 0.8, 0.02))
            p(model="cube", color=acento, position=(0, 1.5, 0.07), scale=(1.3, 0.06, 0.02))
        elif prop == "afiches":
            for k, tono in enumerate(((234, 120, 90), (90, 150, 220), (240, 200, 90))):
                p(model="cube", color=c(tono), position=(-0.6 + k * 0.6, 1.5 + (k % 2) * 0.12, 0.03), scale=(0.44, 0.62, 0.03))
        elif prop == "planta_grande":
            p(model="cube", color=c((160, 100, 70)), position=(0, 0.25, 0.4), scale=(0.4, 0.5, 0.4))
            p(model="sphere", color=c((60, 140, 70)), position=(0, 0.95, 0.4), scale=(0.9, 0.9, 0.9))
            p(model="sphere", color=c((80, 160, 84)), position=(0.18, 1.3, 0.4), scale=0.55)
        elif prop == "reloj":
            p(model="circle", color=c((245, 245, 248)), position=(0, 2.0, 0.03), scale=0.5, rotation_y=180)
            p(model="cube", color=c((30, 30, 40)), position=(0, 2.04, 0.04), scale=(0.02, 0.18, 0.01))
            p(model="cube", color=c((30, 30, 40)), position=(0.05, 2.0, 0.04), scale=(0.13, 0.02, 0.01))
        silenciar(ancla)
        return ancla

    # -- Ciclo de vida --

    # jugador: Jugador (nombre, rol). lugar: nombre del lugar. modo: 'sentarse' | 'levantarse'.
    # al_terminar: se llama sin argumentos al acabar la cinemática (ConexionFlujo sigue la cadena).
    def al_entrar(self, jugador=None, lugar=None, modo="sentarse", al_terminar=None, **datos):
        self._luces(True)
        self._guardar_camara()
        self.jugador, self.modo, self._al_terminar = jugador, modo, al_terminar
        self.aplicar_tema(lugar)
        self._crear_personaje(jugador)
        self.destello.poner(0)
        rol = ROLES[jugador.rol].nombre
        if modo == "sentarse":
            self._apagar_pantalla()
            plan = guion.plan_interior_sentarse()
            animaciones = self._animaciones_sentarse(rol)
        elif modo == "levantarse":
            self._encender_pantalla(rol)
            self.pantalla_texto.text = "Sesión cerrada"
            plan = guion.plan_interior_levantarse()
            animaciones = self._animaciones_levantarse()
        else:
            raise ValueError(f"Modo de interior desconocido: {modo!r}")
        self.director.reproducir(plan, animaciones, al_terminar=self._terminar, escala=self.escala_tiempo)

    def al_salir(self):
        self.director.cancelar()
        self._restaurar_camara()
        self._luces(False)

    def _luces(self, encendidas):
        encender_luz(self.luz, encendidas)
        encender_luz(self.ambiente, encendidas)

    def saltar_cinematica(self):
        return self.director.saltar()

    def _terminar(self):
        callback, self._al_terminar = self._al_terminar, None
        if self.modo == "sentarse":
            self.destello.poner(1)            # cubre la pantalla; el juego aparece y el destello se desvanece
            if callback is not None:
                try:
                    callback()
                finally:
                    self.destello.desvanecer()
            else:
                self.destello.desvanecer()
        elif callback is not None:
            callback()

    def _crear_personaje(self, jugador):
        if self.personaje is not None:
            destroy(self.personaje)
        self.personaje = Personaje(jugador.nombre, ROLES[jugador.rol].color, parent=self)
        self.personaje.automatico = False
        self.personaje.etiqueta.enabled = False
        self.personaje.aro.enabled = False

    # -- Cámara --

    def _guardar_camara(self):
        if self._camara_guardada is None:
            self._camara_guardada = {
                "parent": camera.parent, "orthographic": camera.orthographic, "fov": camera.fov,
                "position": camera.position, "rotation": camera.rotation,
                "near": camera.clip_plane_near, "far": camera.clip_plane_far,
            }
        camera.parent = scene
        camera.orthographic = False
        camera.fov = guion.FOV_INTERIOR
        camera.clip_plane_near = 0.05
        camera.clip_plane_far = 100

    def _restaurar_camara(self):
        g = self._camara_guardada
        if g is None:
            return
        camera.parent = g["parent"]
        camera.orthographic = g["orthographic"]
        camera.fov = g["fov"]
        camera.clip_plane_near = g["near"]
        camera.clip_plane_far = g["far"]
        camera.position = g["position"]
        camera.rotation = g["rotation"]
        self._camara_guardada = None

    # Pone la cámara entre dos tomas (cada una {position, target, fov}) con avance k en [0, 1].
    def _camara_entre(self, a, b, k):
        posicion = lerp_vec3(a["position"], b["position"], k)
        objetivo = lerp_vec3(a["target"], b["target"], k)
        camera.position = posicion
        pitch, yaw = cc.rotacion_mirando(posicion, objetivo)
        camera.rotation = (pitch, yaw, 0)
        camera.fov = lerp(a["fov"], b["fov"], k)

    # -- Animaciones --

    def _animaciones_sentarse(self, rol):
        p = self.personaje
        tomas = guion.TOMAS_INTERIOR
        puerta, lado, (ax, az) = guion.PUERTA_SALA, guion.LADO_SILLA, guion.ASIENTO

        def caminar(t):
            k = ease_in_out(t)
            p.colocar(lerp(puerta[0], lado[0], k), lerp(puerta[1], lado[1], k))
            # camina hacia la silla: primero al norte y al final gira hacia el este
            rumbo = lerp_angulo(0, 90, ease_in_out(max(0.0, (t - 0.6) / 0.4)))
            p.fijar_rumbo(rumbo)
            p.aplicar_pose(poses.pose_caminar(poses.fase_siguiente(0, 3.0, t * guion.INT_CAMINAR), 0.45))
            self._camara_entre(tomas["caminar"], tomas["caminar"], 0)

        def sentarse(t):
            k = ease_in_out(t)
            p.colocar(lerp(lado[0], ax, k), lerp(lado[1], az, k))
            p.fijar_rumbo(lerp_angulo(90, 0, k))
            p.aplicar_pose(poses.interpolar_pose(poses.POSE_PARADO, poses.POSE_SENTADO, k))
            self._camara_entre(tomas["caminar"], tomas["sentarse"], k)

        def teclear(t):
            if t == 0.0:
                self._encender_pantalla(rol)
            p.colocar(ax, az)
            p.fijar_rumbo(0)
            entrada = ease_in_out(min(1.0, t * 3))            # las manos suben al teclado en el primer tercio
            base = poses.interpolar_pose(poses.POSE_SENTADO, poses.pose_teclear(0), entrada)
            fase = t * GOLPES_TECLEO * 2 * math.pi
            tecleo = poses.pose_teclear(fase)
            p.aplicar_pose(poses.interpolar_pose(base, tecleo, entrada))
            self._camara_entre(tomas["sentarse"], tomas["teclear"], ease_in_out(t))

        def acercar(t):
            p.aplicar_pose(poses.pose_teclear(t * 2 * math.pi))
            k = ease_in_out(t)
            a, via, b = tomas["teclear"]["position"], guion.VIA_ACERCAR, tomas["acercar_fin"]["position"]
            posicion = tuple((1 - k) ** 2 * a[i] + 2 * (1 - k) * k * via[i] + k ** 2 * b[i] for i in range(3))
            objetivo = lerp_vec3(tomas["teclear"]["target"], tomas["acercar_fin"]["target"], k)
            camera.position = posicion
            camera.rotation = (*cc.rotacion_mirando(posicion, objetivo), 0)
            camera.fov = lerp(tomas["teclear"]["fov"], tomas["acercar_fin"]["fov"], k)

        def destello(t):
            self.destello.poner(t)

        return {"caminar": caminar, "sentarse": sentarse, "teclear": teclear, "acercar": acercar,
                "destello": destello}

    def _animaciones_levantarse(self):
        p = self.personaje
        tomas = guion.TOMAS_INTERIOR
        (ax, az), lado = guion.ASIENTO, guion.LADO_SILLA

        def levantarse(t):
            k = ease_in_out(t)
            p.colocar(lerp(ax, lado[0] + 0.6, k), lerp(az, lado[1], k))
            p.fijar_rumbo(lerp_angulo(0, 90, k))
            p.aplicar_pose(poses.interpolar_pose(poses.POSE_SENTADO, poses.POSE_PARADO, k))
            self._camara_entre(tomas["levantarse"], tomas["levantarse"], 0)

        return {"levantarse": levantarse}
