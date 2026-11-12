# Postura emocional y puntos de anclaje de los NPC con modelo .glb (parte Panda3D; los datos están en
# frontend/npc_postura_calculos.py). Es el GANCHO para la conducta: otro módulo decide el estado de cada NPC y llama
# a `npc.aplicar_postura(estado)` (o a `aplicar(npc, estado)`, que vale también para el muñeco procedural).
#
# Cómo funciona: al cargar un modelo se hornean, además de los clips de siempre (frontend/animacion_humana.py),
# variantes de Idle y de la marcha lenta con cada postura ("Idle_aislado", "HumMarcha2_celular"...), sobre el mismo
# esqueleto. El AnimadorHumano no cambia: sigue pidiendo "Idle" y "HumMarchaN"; entre él y el Actor se pone un
# intermediario (ActorConPostura) que reparte el peso de cada clip entre la variante de la postura que se va y la
# de la que entra, con las dos al mismo fotograma y a la misma cadencia. Con la postura neutra el intermediario
# deja pasar todo tal cual. Los clips sin variante (salto, escalón, gestos, Saludar, Hablar) suenan como siempre.
#
# Anclajes: `ancla_cabeza(npc)` (sobre la cabeza, para globos de texto) y `ancla_muneca(npc, lado)` (en la muñeca,
# para una manilla: la cinta de Bonfim va en la izquierda). Nada de aquí lanza: si el modelo no trae las variantes
# (el muñeco procedural, un modelo sin animación humana) `aplicar` devuelve False y el NPC queda como estaba.

import sys

import gltf
from direct.actor.Actor import Actor
from panda3d.core import AnimBundleNode, NodePath
from ursina import Entity

from frontend import animacion_humana as ah
from frontend import animacion_humana_calculos as ac
from frontend import modelo_calculos as mc
from frontend import npc_postura_calculos as pc
from frontend import personaje_modelo as pm

FOTOGRAMAS_REPOSO = 48           # fotogramas del ciclo de respiración (1,6 s a 30 fps)
# Clips que tienen variante por postura: el reposo y la marcha hasta 3 m/s (los NPC caminan a 1-1,6 m/s). Más deprisa
# suena la marcha de siempre: hornear las seis velocidades alargaba la carga de cada modelo y nadie lo vería.
MARCHAS_CON_POSTURA = ah.NOMBRES_MARCHA[:3]
CLIPS_CON_POSTURA = (ah.IDLE,) + MARCHAS_CON_POSTURA
MARGEN_ANCLA_CABEZA = 0.24       # m por encima de la coronilla
# Los NPC que usan uno de los 4 .glb de siempre (ciudadano, brasileña, periodista, smoking) también cambian de postura:
# para ellos se carga una base APARTE con las variantes (la de los personajes jugables no se toca). False = esos NPC
# usan la base de siempre y no tienen posturas (aplicar devuelve False).
POSTURAS_EN_MODELOS_DE_SIEMPRE = True

_bases = {}                      # rol -> Actor base con variantes de postura (None si no se pudo: no se reintenta)

_avisados = set()


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[assets] postura NPC: {motivo}.", file=sys.stderr)


def _poses_reposo(m):
    return [pc.pose_reposo(k / FOTOGRAMAS_REPOSO, m) for k in range(FOTOGRAMAS_REPOSO)]


# Añade al nodo del modelo (recién cargado, antes de crear el Actor) las variantes de Idle y de la marcha de cada
# postura. Devuelve cuántos clips añadió. Nunca lanza: ante un fallo avisa y el modelo queda sin posturas.
def hornear_posturas(modelo_np, clave):
    try:
        personaje = modelo_np.find("**/+Character")
        if personaje.isEmpty():
            return 0
        esq = ah.Esqueleto(personaje)
        m = esq.medidas()
        reposo = _poses_reposo(m)
        marchas = [[ac.pose_marcha(k / ah.FOTOGRAMAS, v, m) for k in range(ah.FOTOGRAMAS)]
                   for v in ac.VELS[:len(MARCHAS_CON_POSTURA)]]
        hechos = 0
        for estado in pc.ESTADOS_CON_CLIPS:
            clips = [(pc.nombre_clip(ah.IDLE, estado), [pc.aplicar_a_pose(p, estado) for p in reposo])]
            for nombre, poses in zip(MARCHAS_CON_POSTURA, marchas):
                clips.append((pc.nombre_clip(nombre, estado), [pc.aplicar_a_pose(p, estado) for p in poses]))
            for nombre, poses in clips:
                personaje.attachNewNode(AnimBundleNode("rig", ah._construir_clip(esq, nombre, poses)))
                hechos += 1
        return hechos
    except Exception as error:
        _avisar(f"{clave}: no se pudieron hornear las posturas ({error})")
        return 0


# Añade los clips que el modelo no trae (los .glb nuevos vienen sin animaciones): Idle (respiración), Hablar,
# Saludar, Caminar y Correr, con los nombres de siempre. Hay que llamarla ANTES de ah.hornear_clips. Lanza si el
# esqueleto no se reconoce (quien carga el modelo decide el respaldo).
def hornear_clips_basicos(modelo_np):
    personaje = modelo_np.find("**/+Character")
    if personaje.isEmpty():
        raise ValueError("el modelo no tiene esqueleto")
    esq = ah.Esqueleto(personaje)
    m = esq.medidas()
    existentes = {nodo.node().getBundle().getName() for nodo in personaje.findAllMatches("**/+AnimBundleNode")}
    ciclo = lambda pose, n: [pose(k / n, m) for k in range(n)]
    clips = ((mc.IDLE, lambda: _poses_reposo(m)),
             (mc.HABLAR, lambda: ciclo(pc.pose_hablar, FOTOGRAMAS_REPOSO)),
             (mc.SALUDAR, lambda: ciclo(pc.pose_saludar, ah.FOTOGRAMAS)),
             (mc.CAMINAR, lambda: [ac.pose_marcha(k / ah.FOTOGRAMAS, ac.VELS[1], m) for k in range(ah.FOTOGRAMAS)]),
             (mc.CORRER, lambda: [ac.pose_marcha(k / ah.FOTOGRAMAS, ac.VELS[4], m) for k in range(ah.FOTOGRAMAS)]))
    hechos = []
    for nombre, poses in clips:
        if nombre not in existentes:
            personaje.attachNewNode(AnimBundleNode("rig", ah._construir_clip(esq, nombre, poses())))
            hechos.append(nombre)
    return hechos


# Copia del Actor de uno de los 4 modelos de siempre CON variantes de postura, para un NPC. Devuelve None si la
# bandera está apagada, no hay animación humana o algo falla (quien llama usa entonces personaje_modelo._cargar_actor).
def cargar_actor_de_siempre(rol):
    if not (POSTURAS_EN_MODELOS_DE_SIEMPRE and pm.ANIMACION_HUMANA) or rol not in mc.MODELOS_POR_ROL:
        return None
    if rol not in _bases:
        _bases[rol] = None
        try:
            ruta = pm.CARPETA_MODELOS / mc.MODELOS_POR_ROL[rol]
            modelo = NodePath(gltf.load_model(str(ruta), gltf_settings=gltf.GltfSettings()))
            if ah.hornear_clips(modelo, rol) and hornear_posturas(modelo, rol):
                base = Actor(modelo)
                faltan = [c for c in (mc.IDLE, mc.CAMINAR, mc.CORRER, mc.HABLAR) if c not in base.getAnimNames()]
                if faltan:
                    raise ValueError(f"faltan clips {faltan}")
                base.hide()
                _bases[rol] = base
        except Exception as error:
            _avisar(f"{rol}: no se pudo cargar la base con posturas ({error})")
    base = _bases[rol]
    return None if base is None else Actor(base)


class ActorConPostura:
    # Intermediario entre el AnimadorHumano y el Actor: todo lo que no es de clips pasa directo al Actor.
    def __init__(self, actor):
        self._actor = actor
        self._nombres = set(actor.getAnimNames())
        self.estado = pc.NEUTRO       # postura que entra (o la actual, si no hay cambio en curso)
        self._desde = pc.NEUTRO       # postura que se va
        self._k = 1.0                 # avance del cambio (1 = terminado)
        self._pesos = {}              # clip lógico -> peso pedido por el animador
        self._sonando = {}            # clip lógico -> variantes que suenan (nombres reales)

    def __getattr__(self, nombre):
        return getattr(self._actor, nombre)

    def _real(self, clip, estado):
        nombre = pc.nombre_clip(clip, estado)
        return nombre if nombre in self._nombres else clip

    # [(nombre real, peso)] del clip lógico con el cambio de postura en curso.
    def _partes(self, clip, peso):
        saliente, entrante = self._real(clip, self._desde), self._real(clip, self.estado)
        if saliente == entrante or self._k >= 1.0:
            return [(entrante, peso)]
        sale, entra = pc.repartir(peso, self._k)
        return [(saliente, sale), (entrante, entra)]

    # Arranca una variante al mismo fotograma y a la misma cadencia que el clip lógico (que ya suena).
    def _arrancar_variante(self, clip, real):
        origen, destino = self._actor.getAnimControl(clip), self._actor.getAnimControl(real)
        if destino is None:
            return
        cuadros = max(1, destino.getNumFrames())
        if origen is not None:
            destino.setPlayRate(origen.getPlayRate())
            destino.pose(int(origen.getFrame()) % cuadros)
        destino.loop(False)
        self._sonando.setdefault(clip, set()).add(real)

    def _repartir(self, clip):
        partes = dict(self._partes(clip, self._pesos.get(clip, 0.0)))
        for real, peso in partes.items():
            if real != clip and peso > 0.0 and real not in self._sonando.get(clip, ()):
                self._arrancar_variante(clip, real)
            self._actor.setControlEffect(real, peso)
        if clip not in partes:
            self._actor.setControlEffect(clip, 0.0)       # el clip de siempre sigue sonando, pero sin peso
        for real in list(self._sonando.get(clip, ())):
            if real not in partes:                        # variante de una postura que ya se fue
                self._actor.setControlEffect(real, 0.0)
                self._actor.stop(real)
                self._sonando[clip].discard(real)

    # -- Lo que el AnimadorHumano le pide al Actor --

    def setControlEffect(self, clip, peso, *resto, **opciones):
        if clip not in CLIPS_CON_POSTURA:
            return self._actor.setControlEffect(clip, peso, *resto, **opciones)
        self._pesos[clip] = peso
        self._repartir(clip)

    def stop(self, clip=None, *resto, **opciones):
        for real in self._sonando.pop(clip, ()):
            self._actor.setControlEffect(real, 0.0)
            self._actor.stop(real)
        self._pesos.pop(clip, None)
        return self._actor.stop(clip, *resto, **opciones)

    def setPlayRate(self, tasa, clip, *resto, **opciones):
        for real in self._sonando.get(clip, ()):
            self._actor.setPlayRate(tasa, real)
        return self._actor.setPlayRate(tasa, clip, *resto, **opciones)

    # -- Cambio de postura --

    def fijar(self, estado):
        estado = pc.estado_valido(estado)
        if estado == self.estado:
            return
        if self._k >= 0.5:            # el cambio anterior iba más que a medias: se parte de esa postura
            self._desde = self.estado
        self.estado = estado
        self._k = 0.0
        self._repartir_todo()

    def avanzar(self, dt):
        if self._k >= 1.0:
            return
        self._k = min(1.0, self._k + max(0.0, dt) / pc.TIEMPO_CAMBIO)
        if self._k >= 1.0:
            self._desde = self.estado
        self._repartir_todo()

    def _repartir_todo(self):
        for clip in list(self._pesos):
            self._repartir(clip)


# Pone el intermediario de posturas a un PersonajeModelo ya creado. Devuelve el intermediario o None si el modelo
# no trae variantes de postura o no usa la animación humana (entonces `aplicar` devolverá False).
def instalar(personaje):
    try:
        humano = getattr(personaje, "_humano", None)
        actor = getattr(personaje, "actor", None)
        if humano is None or actor is None:
            return None
        nombres = set(actor.getAnimNames())
        if not any(pc.nombre_clip(ah.IDLE, estado) in nombres for estado in pc.ESTADOS_CON_CLIPS):
            return None
        intermediario = ActorConPostura(actor)
        humano.actor = intermediario
        return intermediario
    except Exception as error:
        _avisar(f"no se pudo instalar ({error})")
        return None


# Cambia la postura de un NPC ('sociable', 'neutro', 'aislado', 'celular', 'enojado'; lo desconocido = 'neutro').
# Devuelve True si el cuerpo la puede mostrar; False si no (muñeco procedural, modelo sin variantes): no pasa nada.
def aplicar(personaje, estado):
    try:
        intermediario = getattr(personaje, "_postura", None)
        if intermediario is None:
            return False
        intermediario.fijar(estado)
        return True
    except Exception as error:
        _avisar(f"no se pudo aplicar '{estado}' ({error})")
        return False


# Postura actual de un NPC ('neutro' si no tiene posturas).
def estado_de(personaje):
    return getattr(getattr(personaje, "_postura", None), "estado", pc.NEUTRO)


# Altura (m, respecto al NPC) del ancla de la cabeza: la coronilla del modelo escalado más un margen.
def y_ancla_cabeza(personaje):
    try:
        escala = abs(float(personaje.actor.getScale()[1]))
    except Exception:
        escala = mc.ESCALA_MODELO
    return mc.ALTURA_MODELO * escala + MARGEN_ANCLA_CABEZA + (getattr(personaje, "_elevacion", None) or 0.0)


# Entity vacía sobre la cabeza del NPC (hija del NPC: lo sigue, no gira con el cuerpo ni sube y baja con el paso).
# Para colgar globos de texto: `Text(parent=npc.ancla_cabeza(), billboard=True, ...)`. Se crea una sola vez.
def ancla_cabeza(personaje):
    ancla = getattr(personaje, "_ancla_cabeza", None)
    if ancla is None:
        ancla = Entity(parent=personaje, y=y_ancla_cabeza(personaje))
        personaje._ancla_cabeza = ancla
    return ancla


# Nodo en la muñeca ("i" izquierda, "d" derecha) que sigue al hueso de la mano, o None si el modelo no tiene ese
# hueso. Para colgar una manilla (la cinta de Bonfim): el origen está en la muñeca y el eje Y del nodo va hacia los
# dedos; las medidas son las del esqueleto sin escalar. Se crea una sola vez por lado.
def ancla_muneca(personaje, lado="i"):
    anclas = personaje.__dict__.setdefault("_anclas_muneca", {})
    if lado in anclas:
        return anclas[lado]
    nodo = None
    try:
        mano = personaje.mano(lado)
        if mano is not None:
            nodo = mano.attachNewNode(f"ancla_muneca_{lado}")
    except Exception as error:
        _avisar(f"no se pudo anclar la muñeca ({error})")
    anclas[lado] = nodo
    return nodo
