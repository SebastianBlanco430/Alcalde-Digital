# Ambiente de la ciudad en los NPC (puntos 3, 4 y «cantidad de NPC» del 5 del plan final). frontend/extensiones.py llama
# a registrar(); no se edita main.py ni escena_mundo.py. Un controlador cuelga de la EscenaMundo (solo corre con el mundo
# a la vista) y en cada frame:
#
#   1. ALIMENTA frontend/ambiente_vivo.py (el Ambiente suavizado que leen los demás módulos). Esto se hace SIEMPRE,
#      aunque las tres banderas de abajo estén apagadas.
#   2. CONDUCTA (NPC_CONDUCTA / ALCALDE_NPC_CONDUCTA=0): cada NPC toma el estado de ambiente_ciudad.estado_npc(su semilla)
#      y lo muestra en la postura (npc_postura.aplicar) y en cómo camina (backend/logica/conducta_estados.py): multitud
#      del mapa grande (nivel A: postura + movimiento; nivel B: solo movimiento), peatones del mundo chico (postura,
#      ritmo y paradas «mirando el celular») y NPC clave con los que se habla (solo postura; mientras atienden al jugador
#      no se ponen de espaldas al mundo: ver _postura_de_reactivo).
#   3. DENSIDAD (NPC_DENSIDAD / ALCALDE_NPC_DENSIDAD=0): gente en la calle = densidad_poblacion(amb) x factor horario de
#      la hora de la PARTIDA (ambiente_vivo.hora()). Multitud: gancho Multitud.densidad (el Asignador aplaza altas y bajas
#      a la vista a menos de RADIO_APARICION m). Mundo chico: `enabled` por peatón, con la misma regla.
#   4. GLOBOS (NPC_GLOBOS / ALCALDE_NPC_GLOBOS=0): frontend/globos_npc.py + backend/logica/globos.py.
#
# EN LÍNEA: la conducta deja de tocar el MOVIMIENTO (ConductaConEstado.modular = False: la multitud camina exactamente
# como antes; los peatones del mundo chico conservan su velocidad). Quedan la postura, los globos y la densidad, que son
# solo locales y visuales (nada viaja por la red ni cambia el modelo de la partida).
#
# Rendimiento: el estado de los agentes se recalcula cada PERIODO_ESTADOS frames (180 comparaciones) y solo si el Ambiente
# cambió; la postura se revisa cada PERIODO_POSTURA frames para los actores dibujados (hasta 10); los candidatos a globo
# son los actores de nivel A (hasta 10). Ver tests/humo_ambiente_npc.py para las cifras.

import math
import os
import random
import sys

from backend.logica import ambiente_ciudad as ac
from backend.logica import conducta_estados as ce
from backend.logica import globos as gl
from backend.logica import multitud_calculos as mc
from frontend import ambiente_vivo

NPC_CONDUCTA = True
NPC_DENSIDAD = True
NPC_GLOBOS = True

PERIODO_ESTADOS = 30             # frames entre dos recálculos de los estados (si el ambiente cambió)
PERIODO_POSTURA = 4              # frames entre dos repasos de la postura de los actores dibujados
PERIODO_REACTIVOS = 30           # frames entre dos repasos de los NPC clave
RADIO_GLOBO = 16.0               # m de la cámara: más lejos nadie «habla» (no se leería)
COS_GLOBO = 0.78                 # a menos de ~39 grados del eje de la cámara
COS_VISTA = 0.6                  # a la vista para aparecer / desaparecer (como frontend/multitud.py)
PESO_CHARLA = 3.0                # quien está charlando habla más
SEMILLA_GLOBOS = 2026


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def conducta_activa():
    return _bandera("ALCALDE_NPC_CONDUCTA", NPC_CONDUCTA)


def densidad_activa():
    return _bandera("ALCALDE_NPC_DENSIDAD", NPC_DENSIDAD)


def globos_activos():
    return _bandera("ALCALDE_NPC_GLOBOS", NPC_GLOBOS)


def _aviso(texto):
    print(f"[ambiente_npc] {texto}", file=sys.stderr)


def semilla_peaton(k):
    """Semilla estable del peatón `k` del mundo chico (para su estado y su umbral de densidad)."""
    return ("peaton", k)


def postura_de_reactivo(estado, mirando):
    """Postura de un NPC clave: la de su estado, salvo que esté atendiendo al jugador (vuelto hacia él): entonces no se
    queda cabizbajo ni mirando el celular (se vería que ignora al jugador mientras le habla)."""
    if mirando and estado in (ce.CELULAR, ce.AISLADO):
        return ce.NEUTRO
    return estado


def en_cono(x, z, cx, cz, fx, fz, coseno):
    """¿Está (x, z) dentro del cono de visión horizontal de la cámara en (cx, cz) que mira hacia (fx, fz)?"""
    dx, dz = x - cx, z - cz
    d = math.hypot(dx, dz)
    return d < 1e-6 or (dx * fx + dz * fz) / d > coseno


class _Densidad:
    """Gancho de Multitud.densidad: activos por umbral fijo del agente contra el factor (ambiente x hora)."""

    def __init__(self):
        self.factor = 1.0
        self._clave, self._lista = None, None

    def __call__(self, agentes, activos=None):
        clave = (round(self.factor, 3), len(agentes))
        if clave != self._clave:
            self._clave = clave
            self._lista = ce.activos_por_factor([a.umbral for a in agentes], clave[0])
        if activos is None:
            return self._lista
        return [a and b for a, b in zip(activos, self._lista)]


def _crear_controlador(escena):
    from ursina import Entity, camera, time
    from frontend import npc_postura

    class ControladorAmbienteNPC(Entity):

        def __init__(self, **opciones):
            super().__init__(**opciones)
            self._frame = 0
            self._amb_estados = None
            self._t = 0.0
            self.conducta = conducta_activa()
            self.con_densidad = densidad_activa()
            self.densidad = _Densidad()
            self.factor = 1.0
            self.globos = None
            self._estados_multitud = None        # EstadosNPC si la multitud no tiene ConductaConEstado
            self._instalar_multitud()
            self._instalar_peatones()
            if globos_activos():
                self._instalar_globos()

        # -- Instalación (una vez) --

        def _instalar_multitud(self):
            m = getattr(escena, "multitud", None)
            if m is None:
                return
            if self.con_densidad:
                m.densidad = self.densidad
            if not self.conducta:
                return
            from backend.logica import multitud_conducta as cd
            if type(m.conducta) is cd.Conducta:                     # la variante con estados sustituye a la base
                nueva = ce.ConductaConEstado(m.agentes)
                for i in m.conducta.activos:
                    nueva.entrar(i, m._t)
                m.conducta = nueva
            if not isinstance(m.conducta, ce.ConductaConEstado):
                self._estados_multitud = ce.EstadosNPC([a.semilla for a in m.agentes])

        def _instalar_peatones(self):
            p = getattr(escena, "peatones", None)
            self._peatones = p if p is not None and p.personajes else None
            if self._peatones is None:
                return
            n = len(p.personajes)
            semillas = [semilla_peaton(k) for k in range(n)]
            self._estados_peatones = ce.EstadosNPC(semillas)
            self._umbral_peatones = ce.umbrales_repartidos(semillas)
            self._velocidad_base = [c.velocidad for c in p.caminantes]
            self._ritmo_peatones = [1.0] * n
            self._semilla_parada = [1000 + k for k in range(n)]

        def _instalar_globos(self):
            try:
                from frontend.globos_npc import GlobosNPC
                catalogo, _ = gl.cargar_frases()
                azar = random.Random(SEMILLA_GLOBOS)
                plan = gl.PlanificadorGlobos(gl.SelectorFrases(catalogo, azar), azar)
                self.globos = GlobosNPC(self, plan)
                m = getattr(escena, "multitud", None)               # las anclas de cabeza se crean ya (no al hablar)
                cuerpos = list(m._actores) if m is not None else []
                if self._peatones is not None:
                    cuerpos += list(self._peatones.personajes)
                for cuerpo in cuerpos:
                    npc_postura.ancla_cabeza(cuerpo)
            except Exception as error:
                _aviso(f"globos no instalados ({type(error).__name__}: {error})")
                self.globos = None

        # -- Frame --

        def update(self):
            self.avanzar(min(time.dt, 0.1))

        def avanzar(self, dt):
            amb = ambiente_vivo.alimentar(dt, escena)
            if escena.flujo is None or escena._sesion is None:
                return
            self._frame += 1
            self._t += dt
            linea = ambiente_vivo.en_linea()
            hora = ambiente_vivo.hora()
            self.factor = ce.factor_poblacion(amb, hora) if self.con_densidad else 1.0
            self.densidad.factor = self.factor
            if self._frame % PERIODO_ESTADOS == 1 and amb != self._amb_estados:
                self._amb_estados = amb
                self._fijar_estados(amb)
            yaw = math.radians(camera.world_rotation_y)
            vista = (camera.world_x, camera.world_z, math.sin(yaw), math.cos(yaw))
            candidatos = []
            self._multitud(linea, vista, candidatos)
            if self._peatones is not None:
                self._mundo_chico(dt, linea, vista, candidatos)
            if self.conducta and self._frame % PERIODO_REACTIVOS == 2:
                self._reactivos(amb)
            if self.globos is not None:
                if escena.en_pausa or escena._cinematica:
                    candidatos = []
                self.globos.actualizar(dt, candidatos, amb.nivel, hora, ambiente_vivo.dia())

        def _fijar_estados(self, amb):
            if not self.conducta:
                return
            m = getattr(escena, "multitud", None)
            if m is not None:
                if isinstance(m.conducta, ce.ConductaConEstado):
                    m.conducta.fijar_ambiente(amb)
                elif self._estados_multitud is not None:
                    self._estados_multitud.fijar_ambiente(amb)
            if self._peatones is not None:
                self._estados_peatones.fijar_ambiente(amb)

        def _estado_agente(self, m):
            c = m.conducta
            if isinstance(c, ce.ConductaConEstado):
                return c.estado
            return None if self._estados_multitud is None else self._estados_multitud.estado

        # Multitud del mapa grande: postura de los actores de nivel A y candidatos a globo.
        def _multitud(self, linea, vista, candidatos):
            m = getattr(escena, "multitud", None)
            if m is None:
                return
            c = m.conducta
            con_estado = isinstance(c, ce.ConductaConEstado)
            if con_estado:
                c.modular = self.conducta and not linea
            estados = self._estado_agente(m) if self.conducta else None
            revisar = self._frame % PERIODO_POSTURA == 0
            if not revisar and self.globos is None:
                return
            cx, cz, fx, fz = vista
            recurso, actores, pos = m.asignador.recurso, m._actores, m._pos
            for i in m._en_a:
                actor = actores[recurso[i]]
                estado = estados[i] if estados is not None else ce.NEUTRO
                if revisar and estados is not None and npc_postura.estado_de(actor) != estado:
                    npc_postura.aplicar(actor, estado)
                if self.globos is not None:
                    e = pos[i]
                    if e is None:
                        continue
                    d = math.hypot(e[0] - cx, e[1] - cz)
                    if d < RADIO_GLOBO and en_cono(e[0], e[1], cx, cz, fx, fz, COS_GLOBO):
                        peso = PESO_CHARLA if con_estado and c.charla_hasta[i] > m._t else 1.0
                        candidatos.append((("m", i), estado, d, peso, actor))

        # Peatones del mundo chico: estado -> postura, ritmo, paradas del celular, y `enabled` por densidad.
        def _mundo_chico(self, dt, linea, vista, candidatos):
            p = self._peatones
            cx, cz, fx, fz = vista
            estados = self._estados_peatones.estado
            revisar = self._frame % PERIODO_POSTURA == 0
            for k, (caminante, personaje) in enumerate(zip(p.caminantes, p.personajes)):
                estado = estados[k] if self.conducta else ce.NEUTRO
                x, z = caminante.x, caminante.z
                d = math.hypot(x - cx, z - cz)
                a_la_vista = en_cono(x, z, cx, cz, fx, fz, COS_VISTA)
                if self.con_densidad:
                    quiere = self._umbral_peatones[k] < self.factor
                    if bool(personaje.enabled) != quiere and not (d < mc.RADIO_APARICION and a_la_vista):
                        personaje.enabled = quiere            # aparece o se va solo fuera de la vista (o muy lejos)
                if not personaje.enabled:
                    continue
                if self.conducta:
                    if not linea:
                        ritmo = self._ritmo_peatones[k] = ce.acercar(self._ritmo_peatones[k], ce.ritmo_de(estado), dt)
                        caminante.velocidad = self._velocidad_base[k] * ritmo
                        if estado == ce.CELULAR and caminante.en_movimiento and hasattr(caminante, "_espera"):
                            parada = ce.parada_celular(self._semilla_parada[k], self._t)
                            if parada is not None and parada[0] <= self._t < parada[1]:
                                caminante._espera = max(caminante._espera, parada[1] - self._t)
                    if revisar and npc_postura.estado_de(personaje) != estado:
                        npc_postura.aplicar(personaje, estado)
                if self.globos is not None and d < RADIO_GLOBO and en_cono(x, z, cx, cz, fx, fz, COS_GLOBO):
                    candidatos.append((("p", k), estado, d, 1.0, personaje))

        # NPC clave (frontend/npc_reactivo.py): postura según el ambiente, sin tocar su diálogo ni su giro.
        def _reactivos(self, amb):
            economia = getattr(escena, "economia", None)
            if economia is None:
                return
            for interaccion in getattr(economia, "interacciones", ()):
                cuerpo = getattr(interaccion, "npc", None)
                clave = getattr(interaccion, "clave", None)
                if cuerpo is None or clave is None or not hasattr(interaccion, "mirando"):
                    continue
                estado = postura_de_reactivo(ac.estado_npc(str(clave.id), amb), interaccion.mirando)
                if npc_postura.estado_de(cuerpo) != estado:
                    npc_postura.aplicar(cuerpo, estado)

        def estadisticas(self):
            m = getattr(escena, "multitud", None)
            cuenta = {}
            if m is not None and self.conducta:
                estados = self._estado_agente(m)
                if estados is not None:
                    for i in list(m._en_a) + list(m._en_b):
                        cuenta[estados[i]] = cuenta.get(estados[i], 0) + 1
            return {"factor": round(self.factor, 3), "estados_dibujados": cuenta,
                    "globos_mostrados": 0 if self.globos is None else self.globos.mostrados,
                    "charlas": getattr(getattr(m, "conducta", None), "charlas", 0) if m is not None else 0}

    return ControladorAmbienteNPC(parent=escena)


def registrar(gestor, conexion, escena_mundo):
    try:
        conexion.ambiente_npc = _crear_controlador(escena_mundo)
        return conexion.ambiente_npc
    except Exception as error:
        _aviso(f"no instalado ({type(error).__name__}: {error}); la ciudad sigue como antes")
        return _solo_alimentar(escena_mundo)


# Respaldo: si el controlador completo no se pudo crear, al menos se alimenta ambiente_vivo (los demás módulos lo leen).
def _solo_alimentar(escena):
    try:
        from ursina import Entity, time

        class AlimentadorAmbiente(Entity):
            def update(self):
                ambiente_vivo.alimentar(min(time.dt, 0.1), escena)

        return AlimentadorAmbiente(parent=escena)
    except Exception as error:
        _aviso(f"ambiente_vivo sin alimentar ({type(error).__name__}: {error})")
        return None
