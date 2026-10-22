# Personaje 3D articulado (Ursina): muñeco de primitivas con pivotes en pelvis, torso,
# cabeza, hombros, codos, caderas y rodillas, del color del rol, animado por código con
# las poses de frontend/poses.py (caminar, correr, reposo, sentado, teclear).
#
# Medidas (1 unidad = 1 m, de pie ≈ 1.83 m): cadera a 0.95 m del piso; muslo 0.45, pantorrilla
# 0.43; torso 0.5; cabeza 0.28.
#
# Signos: las poses usan "positivo = hacia adelante" (ver poses.py). En Ursina rotation_x
# positivo inclina hacia ATRÁS un segmento que cuelga (brazos, piernas) y hacia ADELANTE
# uno que sube (torso, cabeza), así que a los miembros se les invierte el signo al aplicar.
#
# Control: el controlador/director llaman a colocar(), mirar_hacia() (giro suave) o
# fijar_rumbo() (instantáneo) y fijan `velocidad` (m/s reales) para que update() anime
# caminar/correr/reposo. Durante una cinemática se pone `automatico = False` y el director
# aplica poses a mano con aplicar_pose().

from panda3d.core import CullFaceAttrib
from ursina import Entity, color, destroy, time

from frontend import contorno_calculos as cc
from frontend import estilo, geometria_mundo, poses
from frontend import rostro_animacion_calculos as ra
from frontend import rostro_calculos as rc
from frontend.componentes import rgb
from frontend import sombra_calculos as sc
from frontend.rostro_modelo import colocar_rostro_procedural
from frontend.sombra_contacto import SombraContacto, crear_aro
from frontend.piezas import COLOR_MARCADOR, COLOR_PIEL, etiqueta, silenciar
from frontend.piezas import malla_unida as _malla_unida_base

CONTORNO_ACTIVO = True            # contorno de tinta (casco invertido) en cada pieza del muñeco

VELOCIDAD_CARRERA = 8.5          # m/s con intensidad 1 (ver poses.pose_caminar)
RESPIRACION = 1.6                # rad/s de la fase en reposo
COLOR_PANTALON = color.rgb32(52, 58, 82)
COLOR_PELO = color.rgb32(48, 36, 30)
COLOR_ZAPATO = color.rgb32(30, 30, 36)


# Contorno de tinta de cada pieza: copia inflada, de color tinta y dibujada solo por sus caras traseras (sin
# shader), colgada del mismo pivote para que siga la animación. `_construir` llama a esta función con el mismo
# nombre y firma que piezas.malla_unida, así no hizo falta tocarlo.
def malla_unida(padre, piezas, **opciones):
    soporte = _malla_unida_base(padre, piezas, **opciones)
    if CONTORNO_ACTIVO:
        try:
            casco_piezas = []
            for datos in piezas:
                casco = cc.especificacion_contorno(datos)
                casco["color"] = color.rgb32(*cc.TINTA)
                casco_piezas.append(casco)
            casco = _malla_unida_base(padre, casco_piezas, **opciones)
            casco.shader = None
            casco.clearShader()             # malla_unida ya le puso el shader con luz: el casco va plano
            casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
            casco.setLightOff(1)
            casco.setTextureOff(1)
        except Exception as error:          # el contorno es adorno: nunca debe impedir crear al personaje
            print(f"[assets] contorno de tinta no disponible ({error})")
    return soporte


# Realce de la ropa: más saturación y contraste (estilo cómic) sobre un color de Ursina.
def _realzado(c):
    r, g, b = cc.realzar_color((round(c.r * 255), round(c.g * 255), round(c.b * 255)))
    return color.rgb32(r, g, b)


# Articulaciones de miembros (se les invierte el signo) y de columna (signo directo).
_MIEMBROS = ("brazo_i", "brazo_d", "codo_i", "codo_d", "muslo_i", "muslo_d", "rodilla_i", "rodilla_d")
_COLUMNA = ("torso", "cabeza")


class Personaje(Entity):

    VELOCIDAD_GIRO = 12

    def __init__(self, nombre, color_rol, apariencia=None, **opciones):
        super().__init__(**opciones)
        self.nombre = nombre
        self._apariencia = apariencia or {}   # opcional: tuplas RGB de pantalon, piel y pelo (peatones)
        self.rumbo = 0.0              # rotation_y del cuerpo (grados)
        self.rumbo_objetivo = 0.0
        self.velocidad = 0.0          # m/s reales; la fija el controlador
        self.automatico = True        # False: el director controla pose y giro
        self.suelo = None             # altura del suelo (x, z) -> y; None = se queda en su y
        self._fase = 0.0
        self._intensidad = 0.0
        self._activo = False

        self.aro = crear_aro(self)                 # translúcido y sobre las capas del suelo (y = 0.30)
        self.cuerpo = Entity(parent=self)          # gira hacia donde camina; la etiqueta no
        self._elevacion = None                     # elevación de los pies ya aplicada (ver _elevar)
        self.pivotes = {}
        self._construir(_realzado(rgb(color_rol)))
        self.rostro = None                         # RostroAnimado del muñeco (solo con rasgos de rol)
        self._t_rostro = 0.0
        self._estilizar(nombre)
        self.etiqueta = etiqueta(nombre, parent=self, y=2.25, scale=8)
        for parte in (self.aro, self.cuerpo, self.etiqueta):
            silenciar(parte)               # solo el Personaje (la raíz) necesita update()
        self.sombra = SombraContacto(self.cuerpo, sc.SESGO_SOMBRA)   # disco bajo los pies (cuelga de cuerpo)
        self._elevar()
        self.aplicar_pose(poses.POSE_PARADO)

    # -- Construcción --

    def _pivote(self, nombre, padre, **posicion):
        pivote = Entity(parent=padre, **posicion)
        self.pivotes[nombre] = pivote
        return pivote

    def _construir(self, tono):
        pantalon, piel, pelo = (rgb(self._apariencia[c]) if c in self._apariencia else por_defecto
                                for c, por_defecto in (("pantalon", COLOR_PANTALON), ("piel", COLOR_PIEL),
                                                       ("pelo", COLOR_PELO)))
        manga = color.rgb32(int(tono.r * 255 * 0.85), int(tono.g * 255 * 0.85), int(tono.b * 255 * 0.85))
        self.pelvis = self._pivote("pelvis", self.cuerpo, y=poses.ALTURA_PELVIS_PARADO)
        malla_unida(self.pelvis, [dict(model="cube", color=pantalon, scale=(0.36, 0.2, 0.2))])

        torso = self._pivote("torso", self.pelvis, y=0.1)
        malla_unida(torso, [dict(model="cube", color=tono, position=(0, 0.25, 0), scale=(0.42, 0.5, 0.24))])
        cabeza = self._pivote("cabeza", torso, y=0.5)
        malla_unida(cabeza, [
            dict(model="sphere", color=piel, position=(0, 0.15, 0), scale=0.27),
            dict(model="cube", color=pelo, position=(0, 0.25, -0.02), scale=(0.25, 0.1, 0.25)),
            dict(model="cube", color=color.rgb32(30, 30, 40), position=(0, 0.17, 0.12),
                 scale=(0.2, 0.05, 0.05)),                   # visor: marca hacia dónde mira
        ])

        for lado, signo in (("i", -1), ("d", 1)):
            hombro = self._pivote(f"brazo_{lado}", torso, position=(signo * 0.27, 0.46, 0))
            malla_unida(hombro, [dict(model="cube", color=manga, position=(0, -0.15, 0), scale=(0.12, 0.3, 0.12))])
            codo = self._pivote(f"codo_{lado}", hombro, y=-0.3)
            malla_unida(codo, [
                dict(model="cube", color=piel, position=(0, -0.13, 0), scale=(0.1, 0.26, 0.1)),
                dict(model="sphere", color=piel, position=(0, -0.28, 0), scale=0.11),
            ])

            cadera = self._pivote(f"muslo_{lado}", self.pelvis, position=(signo * 0.1, -0.05, 0))
            malla_unida(cadera, [dict(model="cube", color=pantalon, position=(0, -0.225, 0),
                                      scale=(0.17, 0.45, 0.17))])
            rodilla = self._pivote(f"rodilla_{lado}", cadera, y=-0.45)
            malla_unida(rodilla, [
                dict(model="cube", color=pantalon, position=(0, -0.2, 0), scale=(0.14, 0.4, 0.14)),
                dict(model="cube", color=COLOR_ZAPATO, position=(0, -0.41, 0.05), scale=(0.14, 0.08, 0.28)),
            ])

    # Cabeza de cómic: cambia la cabeza de primitivas (esfera + visor) por la del estilo Borderlands (cráneo con
    # contorno, ojos, cejas, nariz, boca, pelo y accesorios) cuando `apariencia` trae "rasgos" (el nombre de un rol
    # o los rasgos de un peatón). Sin rasgos conserva la cabeza de siempre. NUNCA lanza.
    def _estilizar(self, nombre):
        rasgos = self._apariencia.get("rasgos")
        if rasgos is None:
            return
        try:
            if isinstance(rasgos, str):
                piezas = rc.ROSTRO_PROCEDURAL_POR_ROL[rasgos]
                animado = True
            else:
                piel = self._apariencia.get("piel_rgb", (235, 200, 170))
                pelo = self._apariencia.get("pelo_rgb", (48, 36, 30))
                piezas = rc.piezas_peaton(rasgos, piel, pelo)
                animado = False
            cabeza = self.pivotes["cabeza"]
            viejos = list(cabeza.children)
            semilla = sum(ord(c) * (i + 1) for i, c in enumerate(nombre))
            raiz, self.rostro = colocar_rostro_procedural(cabeza, piezas, animado, str(rasgos)[:12], semilla)
            if raiz is not None:
                for hijo in viejos:
                    destroy(hijo)
                self._detalles(rasgos)
        except Exception as error:
            self.rostro = None
            print(f"[assets] {nombre}: no se pudo estilizar la cabeza ({error})")

    # Detalles de ropa que dan carácter al muñeco (cinturón con hebilla, puños, suelas; raya o emblema en el pecho
    # según el rol). Cada uno cuelga de su pivote, con su contorno: siguen la animación.
    def _detalles(self, rasgos):
        puno = color.rgb32(235, 232, 220)
        oscuro = color.rgb32(38, 32, 34)
        # sin casco propio: el contorno de la pieza grande que los lleva ya los rodea (y son menos dibujos)
        _malla_unida_base(self.pivotes["pelvis"], [
            dict(model="cube", color=oscuro, position=(0, 0.072, 0), scale=(0.375, 0.05, 0.215)),
            dict(model="cube", color=color.rgb32(250, 205, 70), position=(0, 0.072, 0.108), scale=(0.07, 0.042, 0.02)),
        ])
        if rasgos == "ciudadano":     # raya blanca en el pecho
            _malla_unida_base(self.pivotes["torso"], [
                dict(model="cube", color=puno, position=(0, 0.32, 0), scale=(0.43, 0.055, 0.25))])
        elif rasgos == "influencer":  # emblema de corazón en el pecho: dos lóbulos y una punta
            rosa = color.rgb32(255, 245, 250)
            _malla_unida_base(self.pivotes["torso"], [
                dict(model="sphere", color=rosa, position=(-0.032, 0.33, 0.121), scale=0.06),
                dict(model="sphere", color=rosa, position=(0.032, 0.33, 0.121), scale=0.06),
                dict(model="cube", color=rosa, position=(0, 0.305, 0.121), scale=(0.05, 0.05, 0.012)),
            ])

    # Clip equivalente a la velocidad (para los gestos de la cara): Idle, Caminar o Correr.
    def _clip_rostro(self):
        if self.velocidad < 0.1:
            return ra.IDLE
        return ra.CORRER if self.velocidad > 6.5 else ra.CAMINAR

    # -- Pose --

    # Aplica una pose de frontend/poses.py (ángulos "positivo = hacia adelante" + altura de pelvis).
    def aplicar_pose(self, pose):
        self.pelvis.y = pose["pelvis_y"]
        for nombre in _COLUMNA:
            self.pivotes[nombre].rotation_x = pose[nombre]
        for nombre in _MIEMBROS:
            self.pivotes[nombre].rotation_x = -pose[nombre]

    # Un paso de la animación automática: caminar/correr según `velocidad` o respirar en reposo.
    def animar_caminar(self, velocidad, dt):
        objetivo = min(1.0, velocidad / VELOCIDAD_CARRERA)
        self._intensidad = geometria_mundo.suavizar(self._intensidad, objetivo, 10, dt)
        if velocidad > 0.05:
            self._fase = poses.fase_siguiente(self._fase, velocidad, dt)
        else:
            self._fase = (self._fase + RESPIRACION * dt) % poses.DOS_PI
        self.aplicar_pose(poses.pose_caminar(self._fase, self._intensidad))

    # -- Posición y rumbo --

    def colocar(self, x, z):
        self.position = (x, self.y if self.suelo is None else self.suelo(x, z), z)
        self._elevar()

    # Sube los pies sobre las capas planas del suelo (ver «Pies enterrados»): en el mundo ELEVACION_PIES
    # y en el interior 0 (el piso está en y = 0). cuerpo.y es libre: aplicar_pose mueve `pelvis`, no `cuerpo`.
    # El aro conserva su altura sobre los pies y la etiqueta su altura relativa (la sombra cuelga de cuerpo).
    def _elevar(self):
        hay_suelo = self.suelo is not None
        elevacion = sc.ELEVACION_PIES if hay_suelo else 0.0
        if elevacion == self._elevacion:
            return
        self._elevacion = elevacion
        self.cuerpo.y = elevacion
        self.aro.y = sc.altura_aro(hay_suelo)
        self.etiqueta.y = self._y_etiqueta()

    def _y_etiqueta(self):
        return (2.45 if self._activo else 2.25) + self._elevacion

    # Rumbo al que debe girar el cuerpo (giro suave en update()).
    def mirar_hacia(self, rumbo):
        self.rumbo_objetivo = rumbo

    # Rumbo instantáneo (cinemáticas).
    def fijar_rumbo(self, rumbo):
        self.rumbo = self.rumbo_objetivo = rumbo
        self.cuerpo.rotation_y = rumbo

    def girar(self, dt):
        self.rumbo = geometria_mundo.suavizar_angulo(
            self.rumbo, self.rumbo_objetivo, self.VELOCIDAD_GIRO, dt)
        self.cuerpo.rotation_y = self.rumbo

    def fijar_velocidad(self, velocidad):
        self.velocidad = velocidad

    # Ganchos de salto y escaleras: el muñeco procedural no los usa (no-op).
    def fijar_estado_aire(self, en_aire, vel_vertical=0.0):
        pass

    def fijar_subiendo_escalera(self, subiendo):
        pass

    # -- Resaltado del jugador activo --

    def resaltar(self, activo):
        self._activo = activo
        self.aro.enabled = activo
        self.etiqueta.color = COLOR_MARCADOR if activo else rgb(estilo.COLOR_TEXTO)
        self.etiqueta.y = self._y_etiqueta()

    def esta_resaltado(self):
        return self._activo

    # Solo corre con la escena activa (Ursina salta update() con un ancestro desactivado).
    def update(self):
        if self.rostro is not None:   # parpadeo, mirada, boca y cejas (también durante las cinemáticas)
            self._t_rostro += time.dt
            self.rostro.actualizar(self._t_rostro, self._clip_rostro(), self.rumbo, time.dt)
        if not self.automatico:
            return
        self.girar(time.dt)
        self.animar_caminar(self.velocidad, time.dt)
