# Escenografía del final animado (Ursina): lo que se VE en el mundo. Contrato con el director en contrato.md.
#
#   Escenografia(escena, raiz3d, conexion)
#   preparar(final, roles, planos)  con la pantalla en negro: fuerza etapa y hora (ciudad.py), esconde lo del juego y
#                                   crea TODO el decorado (decorado.py) y los actores (actores.py) de esos planos, ocultos
#   entrar(plano)                   corte: enciende lo de ese plano en su pose inicial y apaga lo de los demás (enabled)
#   avanzar(plano, t, dt)           cada frame: actores (puesta.estado_actor + poses_final.objetivo) y piezas animadas
#   limpiar()                       destruye lo creado y devuelve la ciudad como estaba. Idempotente, nunca lanza
#
# Todo lo creado cuelga de `raiz3d` (del director). La cámara y el HUD son del director: aquí no se tocan.

import math
import sys

from ursina import Entity

from frontend.componentes import destruir_arbol
from frontend.final_animado import actores as act
from frontend.final_animado import decorado as deco
from frontend.final_animado import lugares, poses_final as pf, puesta as P
from frontend.final_animado.ciudad import EstadoCiudad


def _aviso(texto):
    print(f"[final_animado] {texto}", file=sys.stderr)


def _id(plano):
    return plano if isinstance(plano, str) else getattr(plano, "id", str(plano))


def _segundos(plano):
    try:
        return float(getattr(plano, "segundos"))
    except Exception:
        return 8.0


def _girar_hacia(actual, objetivo, k):
    d = (objetivo - actual + 180.0) % 360.0 - 180.0
    return actual + d * k


class _ActorEnPlano:
    """Un actor del pool en un plano concreto: su línea de puesta, sus props de ese plano y su estado de frame."""

    def __init__(self, linea, cuerpo, gestos, props, ancla, mundo):
        self.linea = linea
        self.cuerpo = cuerpo
        self.gestos = gestos
        self.props = props
        self.ancla = ancla
        self.mundo = mundo
        self.rumbo = None
        self.pos = None

    def colocar(self, t, segundos, dt, de_golpe=False):
        estado = P.estado_actor(self.linea, t)
        x, _, z = lugares.a_mundo(self.ancla, estado.derecha, 0.0, estado.frente)
        base = self.ancla.y if self.linea.sobre_ancla else float(self.mundo.altura(x, z))
        accion = estado.accion
        objetivo = pf.objetivo(accion, segundos, self.linea.fase, estado.k)
        y = base + estado.alto + objetivo.dy
        velocidad = 0.0
        if self.pos is not None and dt > 1e-4 and not de_golpe:
            velocidad = math.hypot(x - self.pos[0], z - self.pos[1]) / dt
        self.pos = (x, z)
        c = self.cuerpo
        c.position = (x, y, z)
        rumbo = (self.ancla.rumbo + estado.rumbo) % 360.0
        if self.rumbo is None or de_golpe:
            self.rumbo = rumbo
        else:
            self.rumbo = _girar_hacia(self.rumbo, rumbo, min(1.0, dt * 7.0))
        try:
            c.fijar_rumbo(self.rumbo)
        except Exception:
            pass
        animar = getattr(c, "animar_caminar", None)
        if callable(animar):
            if estado.moviendo:
                animar(max(0.6, min(velocidad, 2.2)), dt)
            else:
                animar(0.0, dt)
                if objetivo.clip != "Idle" and callable(getattr(c, "_poner_clip", None)):
                    c._poner_clip(objetivo.clip, 1.0)
        if self.gestos is not None:
            self.gestos.aplicar({} if estado.moviendo else objetivo.pesos, dt, de_golpe)
        for prop in self.props:
            prop.animar(objetivo.mezcla_b, segundos)


class _PlanoVivo:

    def __init__(self, pid, raiz, piezas, actores, props):
        self.id = pid
        self.raiz = raiz
        self.piezas = piezas
        self.actores = actores
        self.props = props              # entidades raíz de los props de este plano (se encienden con él)
        self.segundos = 0.0


class Escenografia:

    def __init__(self, escena, raiz3d, conexion=None):
        self.escena = escena
        self.raiz3d = raiz3d
        self.conexion = conexion
        self.final = None
        self.ciudad = None
        self.cuerpos = {}               # id del pool -> cuerpo
        self.bases = {}                 # id del pool -> soporte de props
        self.planos = {}                # id de plano -> _PlanoVivo
        self.actual = None
        self.creadas = []               # raíces creadas aquí (para limpiar)
        self._limpio = True

    # -- preparar ---------------------------------------------------------------------------------------------------

    def preparar(self, final, roles, planos):
        self._limpio = False
        self.final = final
        escena = self.escena
        mundo = escena._mundo
        anclas = lugares.anclas(mundo)
        self.ciudad = EstadoCiudad(escena, self.conexion)
        self.ciudad.preparar(final)
        luz = deco.LUZ_POR_FINAL.get(final, 1.0)
        ids = [_id(p) for p in planos]
        segundos = {_id(p): _segundos(p) for p in planos}
        # poses que necesita cada actor del pool en estos planos
        poses = {}
        for pid in ids:
            pz = P.PUESTAS.get(pid)
            if pz is None:
                continue
            for linea in pz.actores:
                acciones = {linea.accion} | {paso.accion for paso in linea.pasos}
                poses.setdefault(linea.id, set()).update(p for a in acciones for p in pf.poses_de(a))
        raiz_actores = Entity(parent=self.raiz3d, name="final_actores")
        self.creadas.append(raiz_actores)
        gestos = {}
        for id_pool in P.actores_del_pool(ids):
            cuerpo = act.crear_cuerpo(id_pool, raiz_actores, mundo)
            self.cuerpos[id_pool] = cuerpo
            base = act.soporte(cuerpo)
            self.bases[id_pool] = base
            act.vestir_fijo(id_pool, cuerpo, base)
            gestos[id_pool] = act.Gestos(cuerpo, sorted(poses.get(id_pool, ())))
        for pid in ids:
            pz = P.PUESTAS.get(pid)
            if pz is None:
                _aviso(f"plano sin puesta: {pid}")
                continue
            ancla = anclas[pz.ancla]
            raiz = Entity(parent=self.raiz3d, name=f"final_{pid}")
            self.creadas.append(raiz)
            piezas = []
            for pieza in pz.piezas:
                try:
                    piezas.append(deco.construir(pieza, pid, raiz, anclas, ancla, mundo, final))
                except Exception as error:
                    _aviso(f"{pid}: pieza {pieza.tipo} sin construir ({type(error).__name__}: {error})")
            en_plano, props = [], []
            for linea in pz.actores:
                cuerpo = self.cuerpos[linea.id]
                mis_props = []
                if linea.prop:
                    try:
                        prop = act.crear_prop(linea.prop, cuerpo, self.bases[linea.id], luz, linea.texto)
                        prop.raiz.enabled = False
                        mis_props.append(prop)
                        props.append(prop.raiz)
                    except Exception as error:
                        _aviso(f"{pid}: prop {linea.prop} sin crear ({type(error).__name__}: {error})")
                en_plano.append(_ActorEnPlano(linea, cuerpo, gestos.get(linea.id), mis_props, ancla, mundo))
            raiz.enabled = False
            vivo = _PlanoVivo(pid, raiz, piezas, en_plano, props)
            vivo.duracion = segundos.get(pid, 8.0)
            self.planos[pid] = vivo

    # -- entrar / avanzar -------------------------------------------------------------------------------------------

    def _apagar(self, vivo):
        vivo.raiz.enabled = False
        for prop in vivo.props:
            prop.enabled = False
        for a in vivo.actores:
            a.cuerpo.enabled = False

    def entrar(self, plano):
        pid = _id(plano)
        vivo = self.planos.get(pid)
        anterior = self.planos.get(self.actual) if self.actual is not None else None
        if anterior is not None and anterior is not vivo:
            self._apagar(anterior)
        self.actual = pid
        if vivo is None:
            return
        vivo.segundos = 0.0
        vivo.raiz.enabled = True
        for prop in vivo.props:
            prop.enabled = True
        for a in vivo.actores:
            a.cuerpo.enabled = True
            a.rumbo = a.pos = None
            a.colocar(0.0, 0.0, 0.0, de_golpe=True)
        for pieza in vivo.piezas:
            pieza.avanzar(0.0, 0.0)

    def avanzar(self, plano, t, dt):
        pid = _id(plano)
        if pid != self.actual:
            self.entrar(plano)
        vivo = self.planos.get(pid)
        if self.ciudad is not None:
            self.ciudad.mantener()
        if vivo is None:
            return
        dt = max(0.0, min(float(dt), 0.1))
        t = max(0.0, min(1.0, float(t)))
        vivo.segundos = t * getattr(vivo, "duracion", 8.0)
        for a in vivo.actores:
            a.colocar(t, vivo.segundos, dt)
        for pieza in vivo.piezas:
            pieza.avanzar(t, vivo.segundos)

    # -- limpiar ----------------------------------------------------------------------------------------------------

    def limpiar(self):
        if self._limpio:
            return
        self._limpio = True
        for paso in (self._destruir, self._soltar_ciudad):
            try:
                paso()
            except Exception as error:
                _aviso(f"limpiar: {type(error).__name__}: {error}")

    def _destruir(self):
        for cuerpo in list(self.cuerpos.values()):
            try:
                destruir_arbol(cuerpo)
            except Exception as error:
                _aviso(f"limpiar actor: {type(error).__name__}: {error}")
        for raiz in self.creadas:
            try:
                if raiz is not None:
                    destruir_arbol(raiz)
            except Exception as error:
                _aviso(f"limpiar raíz: {type(error).__name__}: {error}")
        self.cuerpos, self.bases, self.planos, self.creadas = {}, {}, {}, []
        self.actual = None

    def _soltar_ciudad(self):
        if self.ciudad is not None:
            self.ciudad.soltar()
        self.ciudad = None
