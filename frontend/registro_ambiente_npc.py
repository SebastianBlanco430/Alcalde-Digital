# Ambiente de la ciudad en los NPC (puntos 3, 4 y «cantidad de NPC» del 5 del plan final). frontend/extensiones.py llama
# a registrar(); no se edita main.py ni escena_mundo.py. Un controlador cuelga de la EscenaMundo (solo corre con el mundo
# a la vista) y en cada frame:
#
#   1. ALIMENTA frontend/ambiente_vivo.py (el Ambiente suavizado que leen los demás módulos). Esto se hace SIEMPRE,
#      aunque las tres banderas de abajo estén apagadas.
#   2. CONDUCTA (NPC_CONDUCTA / ALCALDE_NPC_CONDUCTA=0): cada NPC toma el estado de ambiente_ciudad.estado_npc(su semilla)
#      y lo muestra en la postura (npc_postura.aplicar) y en cómo camina (backend/logica/conducta_estados.py): peatones
#      (postura, ritmo y paradas «mirando el celular») y NPC clave con los que se habla (solo postura; mientras atienden
#      al jugador no se ponen de espaldas al mundo: ver _postura_de_reactivo).
#   3. DENSIDAD (NPC_DENSIDAD / ALCALDE_NPC_DENSIDAD=0): gente en la calle = densidad_poblacion(amb) x factor horario de
#      la hora de la PARTIDA (ambiente_vivo.hora()). `enabled` por peatón (altas y bajas fuera de la vista, a menos de
#      RADIO_APARICION m no).
#   4. GLOBOS (NPC_GLOBOS / ALCALDE_NPC_GLOBOS=0): frontend/globos_npc.py + backend/logica/globos.py.
#
# EN LÍNEA: la conducta deja de tocar el MOVIMIENTO (los peatones conservan su velocidad). Quedan la postura, los globos y la densidad, que son
# solo locales y visuales (nada viaja por la red ni cambia el modelo de la partida).
#
# Rendimiento: el estado de los agentes se recalcula cada PERIODO_ESTADOS frames y solo si el Ambiente cambió; la postura
# se revisa cada PERIODO_POSTURA frames para los peatones dibujados. Ver tests/humo_ambiente_npc.py para las cifras.

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
COS_VISTA = 0.6                  # a la vista para aparecer / desaparecer
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
            self._instalar_peatones()
            if globos_activos():
                self._instalar_globos()

        # -- Instalación (una vez) --

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
                cuerpos = []                                        # las anclas de cabeza se crean ya (no al hablar)
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
            if self._peatones is not None:
                self._estados_peatones.fijar_ambiente(amb)

        # Peatones del mundo chico: estado -> postura, ritmo, paradas del celular, y `enabled` por densidad.
        def _mundo_chico(self, dt, linea, vista, candidatos):
            p = self._peatones
            cx, cz, fx, fz = vista
            estados = self._estados_peatones.estado
            revisar = self._frame % PERIODO_POSTURA == 0
            for k, (caminante, personaje) in enumerate(zip(p.caminantes, p.personajes)):
                estado = estados[k] if self.conducta else ce.NEUTRO
                estado = getattr(personaje, "_postura_forzada", None) or estado     # misiones visuales (rectificar_visual.py)
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
                estado = getattr(cuerpo, "_postura_forzada", None) or estado     # misiones visuales (rectificar_visual.py)
                if npc_postura.estado_de(cuerpo) != estado:
                    npc_postura.aplicar(cuerpo, estado)

        def estadisticas(self):
            return {"factor": round(self.factor, 3), "estados_dibujados": {},
                    "globos_mostrados": 0 if self.globos is None else self.globos.mostrados,
                    "charlas": 0}

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
