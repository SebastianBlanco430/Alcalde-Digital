# Piloto con la MISMA skin que el jugador elegido (modelo .glb) sentado en una bicicleta o una moto.
#
# Por qué: vehiculo_modelo.crear_piloto() devuelve un muñeco procedural; al montar, el periodista, el candidato, la
# brasileña o el ciudadano (PersonajeModelo, sin `pivotes`) se cambiaban por ese maniquí. Aquí el piloto es OTRA
# copia del mismo .glb (PilotoGlb, un PersonajeModelo con el mismo nombre, así que lleva el mismo rostro) y el
# avatar original solo se oculta: no se toca el modelo cargado ni su caché `_bases`.
# Cómo se sienta: el .glb no tiene clip de sentado. Se controlan TODOS los huesos con Actor.controlJoint y se les
# da la pose calculada por frontend/piloto_glb_calculos.py (cinemática inversa: caderas sobre el asiento, pies en
# pedales/estribos, manos en el manubrio, torso inclinado) con el Hornero de animacion_humana.py. En la bici la
# pose depende de la fase del pedal: se cachea por fase cuantizada (48 pasos) para no repetir la matemática.
# API: la misma que usa VehiculoModelo con el Personaje procedural, más `sentar_en(piezas, fase)`.
#
# REVERTIR: SKIN_EN_VEHICULO = False (el piloto vuelve a ser el maniquí procedural de siempre). Si algo falla al
# crear o sentar al modelo, crear_piloto_skin() cae al maniquí y avisa UNA vez por stderr, sin crash.

import math
import sys

from frontend import animacion_humana as ah
from frontend.componentes import destruir_arbol
from frontend import modelo_calculos as mc
from frontend import personaje_modelo as pm
from frontend import piloto_glb_calculos as pc
from frontend import vehiculo_calculos as vc
from frontend.personaje_modelo import PersonajeModelo
from frontend.vehiculo_modelo import crear_piloto

SKIN_EN_VEHICULO = True          # True = el piloto lleva la skin elegida; False = maniquí procedural (comportamiento anterior)

PASOS_FASE = 48                  # poses cacheadas por vuelta de pedal (bici)

_avisados = set()
_contextos = {}                  # rol -> _Contexto (esqueleto, hornero y medidas; salen del Actor base ya cargado)
_poses = {}                      # (rol, tipo, puntos, paso de fase) -> {hueso: matriz local}


def _avisar(motivo):
    if motivo not in _avisados:
        _avisados.add(motivo)
        print(f"[assets] piloto con skin: {motivo}. Se usa el maniquí procedural.", file=sys.stderr)


class _Contexto:
    def __init__(self, rol):
        base = pm._bases[rol]                       # ya cargado por _cargar_actor al crear el PersonajeModelo
        self.esq = ah.Esqueleto(base.find("**/+Character"))
        self.hornero = ah.Hornero(self.esq)
        self.medidas = self.esq.medidas()
        miembro = self.esq.tipo["miembro"]
        pos = self.esq.pos_rep
        self.huesos_brazo = {"i": miembro["brazo"] % "L", "d": miembro["brazo"] % "R"}
        brazo = (pos(miembro["antebrazo"] % "L") - pos(miembro["brazo"] % "L")).length()
        antebrazo = (pos(miembro["mano"] % "L") - pos(miembro["antebrazo"] % "L")).length()
        self.largos = (brazo, antebrazo)


def _contexto(rol):
    ctx = _contextos.get(rol)
    if ctx is None:
        ctx = _contextos[rol] = _Contexto(rol)
    return ctx


class PilotoGlb(PersonajeModelo):

    def __init__(self, nombre, rol, **opciones):
        super().__init__(nombre, rol, **opciones)
        try:
            self._preparar_pose(rol)
        except Exception:
            destruir_arbol(self)                        # no dejar una Entity (y su Actor) a medias en la escena
            raise

    def _preparar_pose(self, rol):
        self._humano = None                        # sin animador de marcha: los huesos los mueve la pose sentada
        self._nodos = {}
        self._clave_pose = None
        self._ctx = _contexto(rol)
        self.actor.stop()
        for hueso in self._ctx.esq.orden:
            self._nodos[hueso] = self.actor.controlJoint(None, "modelRoot", hueso)
        self._escala = max(0.3, abs(float(self.actor.getScale()[1])))
        self._ejes = self._medir_ejes()
        self._centrar_actor()

    # El piloto no se eleva sobre el suelo: el vehículo lo lleva (montar_piloto llama a _elevar).
    def _elevar(self):
        pass

    def _mezclar(self, dt):
        pass

    # Ejes del cuerpo del modelo (adelante, izquierda, arriba) expresados en el marco de `cuerpo`: sirven para pasar
    # puntos del vehículo (x derecha, y arriba, z adelante) al marco del cuerpo del modelo, sea cual sea la
    # orientación con que se cargó el .glb.
    def _medir_ejes(self):
        m = self.actor.getMat(self.cuerpo)
        ejes = []
        for e in self._ctx.esq.base:
            v = m.xformVec(ah._vec(e))
            ejes.append((v[0] / self._escala, v[1] / self._escala, v[2] / self._escala))
        return ejes

    # Pone el origen del marco del cuerpo (suelo bajo la pelvis) en el origen del piloto.
    def _centrar_actor(self):
        p = self.actor.getMat(self.cuerpo).xformPoint(self._ctx.esq.origen)
        self.actor.setPos(self.actor.getPos() - p)

    # Punto del vehículo (x, y, z; z relativo al origen del piloto) -> marco del cuerpo, en unidades del modelo.
    def _conv(self, v):
        k = 1.0 / self._escala
        return tuple(sum(e[i] * v[i] for i in range(3)) * k for e in self._ejes)

    # Sienta al modelo en el vehículo para esa fase de pedal. Devuelve la z del piloto (la del asiento).
    def sentar_en(self, piezas, fase):
        puntos = piezas.puntos
        es_bici = piezas.tipo == vc.BICICLETA
        sillin_z = puntos["sillin"][2]
        paso = int(round((fase % (2 * math.pi)) / (2 * math.pi) * PASOS_FASE)) % PASOS_FASE if es_bici else 0
        apoyo = ("pedalier", "eje_pedal_x") if es_bici else ("estribo_d", "estribo_i")
        clave = (self.rol, piezas.tipo, tuple(puntos[k] for k in ("sillin", "agarre_d", "agarre_i") + apoyo), paso)
        if clave != self._clave_pose:
            self._clave_pose = clave
            locales = _poses.get(clave)
            if locales is None:
                locales = _poses[clave] = self._calcular(puntos, es_bici, paso, sillin_z)
            for hueso, matriz in locales.items():
                self._nodos[hueso].setMat(matriz)
        return sillin_z

    def _calcular(self, puntos, es_bici, paso, sillin_z):
        ctx = self._ctx
        fase = paso * 2 * math.pi / PASOS_FASE

        def conv(p):
            return self._conv((p[0], p[1], p[2] - sillin_z))

        pose = pc.pose_sentada(ctx.medidas, puntos, es_bici, fase, conv, self._escala)
        hombros = self._hombros(ctx.hornero.locales(pose))
        pose = pc.pose_sentada(ctx.medidas, puntos, es_bici, fase, conv, self._escala, hombros, ctx.largos)
        return ctx.hornero.locales(pose)

    # Posición de los hombros (huesos del brazo) en el marco del cuerpo, a partir de las matrices locales.
    def _hombros(self, locales):
        esq = self._ctx.esq
        mundo = {}

        def calcular(h):
            if h not in mundo:
                padre = esq.padre[h]
                mundo[h] = locales[h] if padre is None else locales[h] * calcular(padre)
            return mundo[h]

        return {c: esq.a_cuerpo(calcular(h).getRow3(3)) for c, h in self._ctx.huesos_brazo.items()}


# Fábrica: PilotoGlb con la skin del jugador si tiene modelo .glb; si no (rol sin modelo, avatar procedural, bandera
# apagada o cualquier fallo) el maniquí procedural de siempre. `avatar`: el avatar real del jugador (si lo hay).
def crear_piloto_skin(nombre, color_rol, rasgos="ciudadano", avatar=None, rol=None):
    if SKIN_EN_VEHICULO:
        if isinstance(avatar, PersonajeModelo):
            rol, nombre = getattr(avatar, "rol", None), avatar.nombre         # mismo rol y mismo nombre = mismo rostro
        elif avatar is not None:
            rol = None                                                         # avatar procedural: maniquí
        if rol in mc.MODELOS_POR_ROL:
            try:
                return PilotoGlb(nombre, rol)
            except Exception as error:
                _avisar(f"{rol}: no se pudo crear el piloto con el modelo ({error})")
    return crear_piloto(nombre, color_rol, rasgos)
