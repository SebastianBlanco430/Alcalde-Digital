# Personaje con modelo .glb animado (Actor de Panda3D) para los roles de MODELOS_POR_ROL
# (periodista y candidato); el resto de roles sigue con el muñeco procedural de personaje.py.
# Tiene la MISMA API pública que Personaje (colocar, mirar_hacia, fijar_rumbo, girar,
# fijar_velocidad, resaltar, aplicar_pose, animar_caminar, update; atributos nombre, rumbo,
# velocidad, automatico, suelo, cuerpo, aro, etiqueta, pivotes), así que escenas, controlador y
# director de cinemáticas no notan la diferencia.
#
# Clips del .glb: Idle, Caminar, Correr, Saludar, Hablar (frontend/modelo_calculos.py decide cuál
# toca). Las poses articuladas de poses.py no se pueden aplicar a un esqueleto: aplicar_pose()
# las traduce a un clip (idempotente: solo cambia de clip si el deseado es otro) y los clips se
# mezclan 0.2 s. `pivotes` queda vacío.
# LIMITACIÓN: no hay clip de sentado ni de teclear. En el interior (pelvis_y < 0.8) el modelo
# queda DE PIE con el clip Hablar, desplazado OFFSET_SENTADO detrás de la silla para no atravesarla.
#
# Falla en silencio: crear_personaje() devuelve el Personaje procedural si el modelo no existe o
# no carga, y avisa una sola vez por rol por stderr. Sin colliders. El Actor usa el shader por
# defecto (no recibe la niebla del mundo, ver MODELOS_3D.md).

import sys
import zlib
from pathlib import Path

import gltf
from direct.actor.Actor import Actor
from panda3d.core import NodePath
from ursina import Entity, time

from frontend import estilo, geometria_mundo, modelo_calculos as mc
from frontend.componentes import rgb
from frontend.personaje import Personaje
from frontend.piezas import COLOR_MARCADOR, etiqueta, silenciar
from frontend import rostro_calculos as rc
from frontend import animacion_humana as ah
from frontend import skinning_gpu
from frontend.rostro_modelo import colocar_rostro_animado
from frontend import sombra_calculos as sc
from frontend.sombra_contacto import SombraContacto, crear_aro

CARPETA_MODELOS = Path(__file__).resolve().parent.parent / "assets" / "modelos" / "personajes"
TIEMPO_MEZCLA = 0.2              # s para pasar de un clip a otro
OFFSET_SENTADO = (0.0, 0.0, -0.7)   # (x, y, z) del cuerpo sin sentarse: detrás de la silla (ASIENTO)

ANIMACION_HUMANA = True          # clips horneados con cinemática humana (frontend/animacion_humana.py); False = clips del .glb

_bases = {}                      # rol -> Actor ya cargado (se copia por jugador)
_avisados = set()


def _avisar(rol, motivo):
    if rol not in _avisados:
        _avisados.add(rol)
        print(f"[assets] {rol}: {motivo}. Se usa el modelo procedural.", file=sys.stderr)


def _cargar_actor(rol):
    base = _bases.get(rol)
    if base is None:
        ruta = CARPETA_MODELOS / mc.MODELOS_POR_ROL[rol]
        # Actor(ruta) carga el glb con la altura en Z (tumbado); gltf.load_model la deja en Y.
        modelo = gltf.load_model(str(ruta), gltf_settings=gltf.GltfSettings())
        if ANIMACION_HUMANA:      # añade al nodo los clips de marcha/escalón/salto antes de crear el Actor
            ah.hornear_clips(NodePath(modelo), rol)
        base = Actor(NodePath(modelo))
        faltan = [c for c in (mc.IDLE, mc.CAMINAR, mc.CORRER, mc.HABLAR) if c not in base.getAnimNames()]
        if faltan:
            raise ValueError(f"faltan clips {faltan}")
        base.hide()
        _bases[rol] = base
    return Actor(base)


class PersonajeModelo(Entity):

    VELOCIDAD_GIRO = 12

    def __init__(self, nombre, rol, **opciones):
        actor = self._crear_actor(rol)  # antes de crear nada: si falla, no queda una Entity a medias
        super().__init__(**opciones)
        self.nombre = nombre
        self.rumbo = 0.0
        self.rumbo_objetivo = 0.0
        self.velocidad = 0.0
        self.automatico = True
        self.suelo = None
        self._activo = False
        self._elevacion = None        # elevación de los pies ya aplicada (ver _elevar)
        self.pivotes = {}
        self._clip = None             # clip que suena
        self._clip_vel = None         # último clip elegido por velocidad (histéresis)
        self._rate = 1.0
        self._pesos = {}              # clip -> peso de la mezcla
        self._humano = None           # AnimadorHumano (si el modelo trae los clips horneados)
        self._v_anim = 0.0            # velocidad (m/s) que guía el ciclo de marcha
        self._en_aire = False         # estado de salto (lo fija el controlador con fijar_estado_aire)
        self._vel_vertical = 0.0
        self._subiendo = False        # subiendo escalones (fijar_subiendo_escalera)

        self.aro = crear_aro(self, sc.altura_aro(False))   # translúcido, sobre las capas del suelo
        self.cuerpo = Entity(parent=self)
        self.sombra = SombraContacto(self.cuerpo, sc.ELEVACION_PIES_INTERIOR + sc.SESGO_SOMBRA)
        self.actor = actor
        self.actor.reparent_to(self.cuerpo)
        self.actor.show()
        self.actor.setScale(self._escala_modelo(rol))
        self.actor.setH(180)          # en Blender mira a -Z; así mira hacia +z del cuerpo
        self.actor.enableBlend()
        # ojos, cejas, nariz, boca, orejas y pelo colgados del hueso de la cabeza, con sus gestos
        self.rostro = self._poner_rostro(rol, nombre)
        self._t_rostro = 0.0
        self.etiqueta = etiqueta(nombre, parent=self, y=2.25, scale=8)
        for parte in (self.aro, self.cuerpo, self.etiqueta):
            silenciar(parte)
        self._elevar()
        self._poner_clip(mc.IDLE, 1.0)
        self._pesos[mc.IDLE] = 1.0    # arranca ya en Idle, sin pasar 0.2 s en la pose base
        self.actor.setControlEffect(mc.IDLE, 1.0)
        if ANIMACION_HUMANA:
            self._humano = ah.crear_animador(self)
        skinning_gpu.aplicar(self.actor)    # deforma en la GPU (frontend/skinning_gpu.py); si falla, sigue por CPU

    # -- Ganchos que las variantes (frontend/npc_modelo.py) sustituyen; por defecto, el comportamiento de siempre --

    def _crear_actor(self, rol):
        return _cargar_actor(rol)

    def _escala_modelo(self, rol):
        return mc.escala_para_rol(rol)

    def _poner_rostro(self, rol, nombre):
        return colocar_rostro_animado(self.actor, rol, zlib.crc32(nombre.encode()))

    # ¿Se anima la cara este frame? Siempre; los NPC la apagan cuando están lejos (rendimiento).
    def _animar_rostro(self):
        return True

    # Arranca el loop del clip (una variante puede desfasarlo para que no vayan todos sincronizados).
    def _iniciar_loop(self, clip):
        self.actor.loop(clip)

    # -- Clips --

    def _poner_clip(self, clip, rate):
        if self._humano is not None:      # con animación humana el clip es solo LÓGICO; el animador elige los reales
            self._clip = clip
            return
        if clip != self._clip:
            self._pesos.setdefault(clip, 0.0)
            self._iniciar_loop(clip)
            self._clip = clip
            self._rate = None
        if self._rate is None or abs(rate - self._rate) > 0.02:
            self.actor.setPlayRate(rate, clip)
            self._rate = rate

    def _mezclar(self, dt):
        if self._humano is not None:
            self._humano.mezclar(dt)
            return
        paso = dt / TIEMPO_MEZCLA
        for clip, peso in list(self._pesos.items()):
            destino = 1.0 if clip == self._clip else 0.0
            peso = min(destino, peso + paso) if peso < destino else max(destino, peso - paso)
            self._pesos[clip] = peso
            self.actor.setControlEffect(clip, peso)
            if peso == 0.0 and clip != self._clip:
                self.actor.stop(clip)
                del self._pesos[clip]

    # -- Pose --

    # Traduce una pose de poses.py a un clip. Se llama varias veces por frame: es idempotente.
    def aplicar_pose(self, pose):
        clip, rate = mc.clip_para_pose(pose)
        self._v_anim = mc.velocidad_de_pose(pose)
        self._poner_clip(clip, rate)
        sentado = clip == mc.HABLAR
        self.cuerpo.position = OFFSET_SENTADO if sentado else (0, 0, 0)

    # Un paso de la animación automática: el clip sale de la velocidad real.
    def animar_caminar(self, velocidad, dt):
        clip, rate = mc.clip_para_velocidad(velocidad, self._clip_vel)
        self._v_anim = velocidad
        self._clip_vel = clip
        self._poner_clip(clip, rate)
        self.cuerpo.position = (0, 0, 0)

    # -- Posición y rumbo --

    def colocar(self, x, z):
        self.position = (x, self.y if self.suelo is None else self.suelo(x, z), z)
        self._elevar()

    # Sube los pies sobre las capas planas del suelo (ver «Pies enterrados»): se eleva el ACTOR
    # (setY, eje vertical en Ursina), no cuerpo.y, que aplicar_pose/animar_caminar reinician.
    # La sombra y el aro suben con la misma regla; la etiqueta conserva su altura relativa.
    def _elevar(self):
        hay_suelo = self.suelo is not None
        elevacion = sc.elevacion_pies(hay_suelo)
        if elevacion == self._elevacion:
            return
        self._elevacion = elevacion
        self.actor.setY(elevacion)
        self.sombra.y = elevacion + sc.SESGO_SOMBRA
        self.aro.y = sc.altura_aro(hay_suelo)
        self.etiqueta.y = self._y_etiqueta()

    def mirar_hacia(self, rumbo):
        self.rumbo_objetivo = rumbo

    def fijar_rumbo(self, rumbo):
        self.rumbo = self.rumbo_objetivo = rumbo
        self.cuerpo.rotation_y = rumbo

    def girar(self, dt):
        self.rumbo = geometria_mundo.suavizar_angulo(
            self.rumbo, self.rumbo_objetivo, self.VELOCIDAD_GIRO, dt)
        self.cuerpo.rotation_y = self.rumbo

    def fijar_velocidad(self, velocidad):
        self.velocidad = velocidad

    # Ganchos de movimiento (los activa el controlador): salto y subir escalones. Con animación humana cambian
    # la pose; sin ella son inofensivos (se guardan y no hacen nada).
    def fijar_estado_aire(self, en_aire, vel_vertical=0.0):
        self._en_aire = bool(en_aire)
        try:
            self._vel_vertical = float(vel_vertical)
        except (TypeError, ValueError):
            self._vel_vertical = 0.0

    def fijar_subiendo_escalera(self, subiendo):
        self._subiendo = bool(subiendo)

    # -- Resaltado del jugador activo --

    def resaltar(self, activo):
        self._activo = activo
        self.aro.enabled = activo
        self.etiqueta.color = COLOR_MARCADOR if activo else rgb(estilo.COLOR_TEXTO)
        self.etiqueta.y = self._y_etiqueta()

    def _y_etiqueta(self):
        return (2.45 if self._activo else 2.25) + (self._elevacion or 0.0)

    def esta_resaltado(self):
        return self._activo

    def update(self):
        self._mezclar(time.dt)        # la mezcla corre también durante las cinemáticas
        if self.rostro is not None and self._animar_rostro():   # gestos de la cara: parpadeo, mirada, boca y cejas según el clip
            self._t_rostro += time.dt
            self.rostro.actualizar(self._t_rostro, self._clip, self.rumbo, time.dt)
        if not self.automatico:
            return
        self.girar(time.dt)
        self.animar_caminar(self.velocidad, time.dt)

    # destruir_arbol llama a ursina.destroy(), que solo invoca este gancho: hay que soltar el Actor a mano.
    def on_destroy(self):
        actor = getattr(self, "actor", None)
        if actor is not None:
            try:
                actor.stop()
                actor.cleanup()
                actor.removeNode()
            except Exception as error:
                # Un Actor a medio soltar no debe impedir destruir la Entity: se avisa y se sigue.
                print(f"[assets] {self.nombre}: no se pudo soltar el Actor ({error})", file=sys.stderr)
            self.actor = None
        self.rostro = None            # el rostro cuelga del Actor ya soltado


# Fábrica: PersonajeModelo si el rol tiene modelo y carga; si no, el Personaje procedural.
def crear_personaje(nombre, rol, color_rol, **opciones):
    if rol in mc.MODELOS_POR_ROL:
        try:
            return PersonajeModelo(nombre, rol, **opciones)
        except Exception as error:
            _avisar(rol, f"no se pudo cargar {mc.MODELOS_POR_ROL[rol]} ({error})")
    opciones = dict(opciones)
    apariencia = dict(opciones.pop("apariencia", None) or {})
    if rol in rc.ROSTRO_PROCEDURAL_POR_ROL:
        apariencia.setdefault("rasgos", rol)       # cabeza de cómic propia del rol (gorra, gafas de sol...)
    return Personaje(nombre, color_rol, apariencia=apariencia or None, **opciones)
