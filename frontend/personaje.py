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
#
# Dos implementaciones detrás de la misma API: procedural (primitivas articuladas, la de siempre)
# y modelo importado (.glb del catálogo, frontend/catalogo_assets.py). En la importada las poses
# se traducen a clips por nombre (parado, caminar, correr, sentado, teclear); si falta un clip
# queda la pose estática, sin error. Si el modelo no existe o no carga, se usa la procedural.
#
# Altura: `altura_en(x, z)` (callable opcional, p. ej. MundoCiudad.altura_en) da la y del suelo;
# sin ella el personaje se queda en su y (interior: 0).

from ursina import Entity, color, time
from ursina.shaders import lit_with_shadows_shader

from frontend import catalogo_assets, estilo, geometria_mundo, poses
from frontend.componentes import rgb
from frontend.piezas import COLOR_MARCADOR, COLOR_PIEL, etiqueta, malla_unida, silenciar

VELOCIDAD_CARRERA = 8.5          # m/s con intensidad 1 (ver poses.pose_caminar)
RESPIRACION = 1.6                # rad/s de la fase en reposo
COLOR_PANTALON = color.rgb32(52, 58, 82)
COLOR_PELO = color.rgb32(48, 36, 30)
COLOR_ZAPATO = color.rgb32(30, 30, 36)

# Articulaciones de miembros (se les invierte el signo) y de columna (signo directo).
_MIEMBROS = ("brazo_i", "brazo_d", "codo_i", "codo_d", "muslo_i", "muslo_d", "rodilla_i", "rodilla_d")
_COLUMNA = ("torso", "cabeza")

# Umbrales para deducir qué clip pide una pose de poses.py (el modelo importado no usa ángulos).
_PELVIS_SENTADO = 0.7            # pelvis más baja que esto = sentado (parado 0.95, sentado 0.5)
_CODO_CAMINANDO = 12.0           # codo = 8 + 25·intensidad en pose_caminar
_CODO_CORRIENDO = 28.0
_VELOCIDAD_CORRER_CLIP = 6.5     # m/s: por encima se reproduce el clip "correr"


class Personaje(Entity):

    VELOCIDAD_GIRO = 12

    # clave_asset: entrada del catálogo ("rol:ciudadano", "peaton"); None = siempre procedural.
    # altura_en: callable (x, z) -> y del suelo, o None.
    def __init__(self, nombre, color_rol, clave_asset=None, altura_en=None, **opciones):
        super().__init__(**opciones)
        self.nombre = nombre
        self.altura_en = altura_en
        self._actor = None            # Actor/NodePath del modelo importado (None = procedural)
        self._clips = {}              # pose -> nombre de clip realmente disponible
        self._clip_actual = None
        self.rumbo = 0.0              # rotation_y del cuerpo (grados)
        self.rumbo_objetivo = 0.0
        self.velocidad = 0.0          # m/s reales; la fija el controlador
        self.automatico = True        # False: el director controla pose y giro
        self._fase = 0.0
        self._intensidad = 0.0
        self._activo = False

        self.aro = Entity(parent=self, model="circle", rotation_x=90, y=0.03, scale=1.7,
                          color=COLOR_MARCADOR, enabled=False)
        self.cuerpo = Entity(parent=self)          # gira hacia donde camina; la etiqueta no
        self.pivotes = {}
        if not self._construir_importado(clave_asset):
            self._construir(rgb(color_rol))
        self.etiqueta = etiqueta(nombre, parent=self, y=2.25, scale=8)
        for parte in (self.aro, self.cuerpo, self.etiqueta):
            silenciar(parte)               # solo el Personaje (la raíz) necesita update()
        self.aplicar_pose(poses.POSE_PARADO)

    # -- Construcción --

    # Monta el modelo del catálogo bajo `cuerpo`. False (y queda lo procedural) si la clave no
    # tiene modelo o no carga.
    def _construir_importado(self, clave):
        if clave is None:
            return False
        asset = catalogo_assets.asset_de(clave)
        prototipo = catalogo_assets.cargar_prototipo(clave, asset)
        if prototipo is None:
            return False
        nodo = None
        try:
            # Con Actor se pueden reproducir los clips del archivo; si no se puede, modelo estático.
            from direct.actor.Actor import Actor
            from panda3d.core import Filename
            ruta = Filename.from_os_specific(str(catalogo_assets.ruta_asset(asset.modelo)))
            nodo = Actor(ruta)
            nodo.reparentTo(self.cuerpo)
            self._actor = nodo
            disponibles = set(nodo.getAnimNames())
        except Exception:
            if nodo is not None:
                nodo.removeNode()
            nodo = prototipo.copy_to(self.cuerpo)
            self._actor = None
            disponibles = set()
        if not catalogo_assets.aplicar_asset(nodo, clave, asset):
            nodo.removeNode()
            self._actor = None
            return False
        for pose in catalogo_assets.POSES:
            clip = asset.animaciones.get(pose)
            if clip in disponibles:
                self._clips[pose] = clip
        self.cuerpo.shader = lit_with_shadows_shader      # el mismo sombreado que pieza()
        self._reproducir("parado")
        return True

    # Reproduce el clip de `pose` en bucle (una sola vez por cambio); sin clip, deja la pose estática.
    def _reproducir(self, pose):
        if self._actor is None or pose == self._clip_actual:
            return
        self._clip_actual = pose
        clip = self._clips.get(pose)
        try:
            if clip is not None:
                self._actor.loop(clip)
            else:
                self._actor.stop()
        except Exception:
            self._actor = None            # clip roto: se queda estático para siempre, sin crash

    # Qué pose del modelo importado representa un dict de poses.py.
    @staticmethod
    def _nombre_de_pose(pose):
        if pose["pelvis_y"] <= _PELVIS_SENTADO:
            return "teclear" if (pose["brazo_i"] > 15 or pose["brazo_d"] > 15) else "sentado"
        codo = pose["codo_i"]
        if codo > _CODO_CORRIENDO:
            return "correr"
        return "caminar" if codo > _CODO_CAMINANDO else "parado"

    def _pivote(self, nombre, padre, **posicion):
        pivote = Entity(parent=padre, **posicion)
        self.pivotes[nombre] = pivote
        return pivote

    def _construir(self, tono):
        manga = color.rgb32(int(tono.r * 255 * 0.85), int(tono.g * 255 * 0.85), int(tono.b * 255 * 0.85))
        self.pelvis = self._pivote("pelvis", self.cuerpo, y=poses.ALTURA_PELVIS_PARADO)
        malla_unida(self.pelvis, [dict(model="cube", color=COLOR_PANTALON, scale=(0.36, 0.2, 0.2))])

        torso = self._pivote("torso", self.pelvis, y=0.1)
        malla_unida(torso, [dict(model="cube", color=tono, position=(0, 0.25, 0), scale=(0.42, 0.5, 0.24))])
        cabeza = self._pivote("cabeza", torso, y=0.5)
        malla_unida(cabeza, [
            dict(model="sphere", color=COLOR_PIEL, position=(0, 0.15, 0), scale=0.27),
            dict(model="cube", color=COLOR_PELO, position=(0, 0.25, -0.02), scale=(0.25, 0.1, 0.25)),
            dict(model="cube", color=color.rgb32(30, 30, 40), position=(0, 0.17, 0.12),
                 scale=(0.2, 0.05, 0.05)),                   # visor: marca hacia dónde mira
        ])

        for lado, signo in (("i", -1), ("d", 1)):
            hombro = self._pivote(f"brazo_{lado}", torso, position=(signo * 0.27, 0.46, 0))
            malla_unida(hombro, [dict(model="cube", color=manga, position=(0, -0.15, 0), scale=(0.12, 0.3, 0.12))])
            codo = self._pivote(f"codo_{lado}", hombro, y=-0.3)
            malla_unida(codo, [
                dict(model="cube", color=COLOR_PIEL, position=(0, -0.13, 0), scale=(0.1, 0.26, 0.1)),
                dict(model="sphere", color=COLOR_PIEL, position=(0, -0.28, 0), scale=0.11),
            ])

            cadera = self._pivote(f"muslo_{lado}", self.pelvis, position=(signo * 0.1, -0.05, 0))
            malla_unida(cadera, [dict(model="cube", color=COLOR_PANTALON, position=(0, -0.225, 0),
                                      scale=(0.17, 0.45, 0.17))])
            rodilla = self._pivote(f"rodilla_{lado}", cadera, y=-0.45)
            malla_unida(rodilla, [
                dict(model="cube", color=COLOR_PANTALON, position=(0, -0.2, 0), scale=(0.14, 0.4, 0.14)),
                dict(model="cube", color=COLOR_ZAPATO, position=(0, -0.41, 0.05), scale=(0.14, 0.08, 0.28)),
            ])

    # -- Pose --

    # Aplica una pose de frontend/poses.py (ángulos "positivo = hacia adelante" + altura de pelvis).
    def aplicar_pose(self, pose):
        if self._importado():
            self._reproducir(self._nombre_de_pose(pose))
            return
        self.pelvis.y = pose["pelvis_y"]
        for nombre in _COLUMNA:
            self.pivotes[nombre].rotation_x = pose[nombre]
        for nombre in _MIEMBROS:
            self.pivotes[nombre].rotation_x = -pose[nombre]

    # Un paso de la animación automática: caminar/correr según `velocidad` o respirar en reposo.
    def animar_caminar(self, velocidad, dt):
        if self._importado():
            if velocidad <= 0.05:
                self._reproducir("parado")
            else:
                self._reproducir("correr" if velocidad > _VELOCIDAD_CORRER_CLIP else "caminar")
            return
        objetivo = min(1.0, velocidad / VELOCIDAD_CARRERA)
        self._intensidad = geometria_mundo.suavizar(self._intensidad, objetivo, 10, dt)
        if velocidad > 0.05:
            self._fase = poses.fase_siguiente(self._fase, velocidad, dt)
        else:
            self._fase = (self._fase + RESPIRACION * dt) % poses.DOS_PI
        self.aplicar_pose(poses.pose_caminar(self._fase, self._intensidad))

    # -- Posición y rumbo --

    def colocar(self, x, z):
        y = self.altura_en(x, z) if self.altura_en is not None else self.y
        self.position = (x, y, z)

    # ¿Se dibuja con un modelo importado? (las poses se traducen a clips)
    def _importado(self):
        return self._actor is not None or "pelvis" not in self.pivotes

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

    # -- Resaltado del jugador activo --

    def resaltar(self, activo):
        self._activo = activo
        self.aro.enabled = activo
        self.etiqueta.color = COLOR_MARCADOR if activo else rgb(estilo.COLOR_TEXTO)
        self.etiqueta.y = 2.45 if activo else 2.25

    def esta_resaltado(self):
        return self._activo

    # Solo corre con la escena activa (Ursina salta update() con un ancestro desactivado).
    def update(self):
        if not self.automatico:
            return
        self.girar(time.dt)
        self.animar_caminar(self.velocidad, time.dt)
