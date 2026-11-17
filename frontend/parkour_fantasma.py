# Corredor FANTASMA del parkour (Ursina): tu mejor carrera de cada nivel se reproduce como una silueta translúcida con
# el mismo modelo del jugador (una COPIA nueva hecha con crear_personaje; personaje_modelo.py no se toca). Si no hay
# skin .glb, una silueta de caja.
#
# Graba posición y rumbo cada N frames (frontend/parkour_extra_calculos.Grabador). Al llegar a la meta, si el tiempo
# mejora el guardado, se escribe un archivo NUEVO y opcional por nivel: <carpeta de ajustes>/parkour_fantasmas/<id>.json
# (sin archivo, no hay fantasma; la partida guardada no cambia). El fantasma sigue el tiempo de la simulación.

import sys

from panda3d.core import TransparencyAttrib
from ursina import Entity, color

from frontend import parkour_extra_calculos as calc

ALFA = 0.35
TINTE = (0.55, 0.85, 1.0)


class Fantasma:

    def __init__(self, nivel, mundo, padre):
        self.nivel = nivel
        self.grabador = calc.Grabador()
        self.mejor = calc.cargar_fantasma(nivel.id)
        self.cuerpo = None
        self._skin = False
        self._padre = padre
        self._clave = getattr(mundo, "clave_skin", None)
        if self.mejor is not None:
            self._crear_cuerpo()

    def _crear_cuerpo(self):
        if self.cuerpo is not None:
            return
        try:
            if self._clave is not None:
                from backend.logica.roles import ROLES
                from frontend.personaje_modelo import crear_personaje
                nombre, rol = self._clave
                cuerpo = crear_personaje("", rol, ROLES[rol].color, parent=self._padre)
                for parte in ("aro", "etiqueta", "sombra"):
                    if getattr(cuerpo, parte, None) is not None:
                        getattr(cuerpo, parte).enabled = False
                cuerpo.automatico = False
                self._skin = hasattr(cuerpo, "animar_caminar")
            else:
                raise ValueError("sin skin")
        except Exception as error:      # noqa: BLE001  sin modelo: silueta de caja
            if self._clave is not None:
                print(f"[parkour] fantasma sin modelo ({error}); se usa una silueta.", file=sys.stderr)
            cuerpo = Entity(parent=self._padre, model="cube", scale=(0.55, 1.8, 0.4), origin_y=-0.5)
            self._skin = False
        cuerpo.setTransparency(TransparencyAttrib.M_alpha)
        cuerpo.setColorScale(TINTE[0], TINTE[1], TINTE[2], ALFA)
        cuerpo.setDepthWrite(False)
        cuerpo.setBin("transparent", 30)
        cuerpo.enabled = False
        self.cuerpo = cuerpo

    # -- Cada frame --

    def grabar(self, sim, rumbo):
        if not sim.terminado:
            self.grabador.anotar(sim.t, sim.x, sim.y, sim.z, rumbo)

    def sincronizar(self, sim, dt):
        if self.cuerpo is None or self.mejor is None:
            return
        estado = calc.interpolar(self.mejor["muestras"], sim.t)
        if estado is None:
            self.cuerpo.enabled = False
            return
        x, y, z, rumbo = estado
        self.cuerpo.enabled = True
        self.cuerpo.position = (x, y, z)
        if self._skin:
            self.cuerpo.fijar_rumbo(rumbo)
            self.cuerpo.animar_caminar(calc.velocidad_en(self.mejor["muestras"], sim.t), dt)
        else:
            self.cuerpo.rotation_y = rumbo

    # -- Fin de carrera / reinicio --

    def al_terminar(self, resultado):
        """Guarda la carrera si mejora la mejor. Devuelve True si es un récord nuevo."""
        tiempo = resultado.get("tiempo_s") if resultado.get("completado") else None
        if not calc.es_mejor(tiempo, self.mejor) or not self.grabador.muestras:
            return False
        muestras = list(self.grabador.muestras)
        calc.guardar_fantasma(self.nivel.id, tiempo, muestras)
        self.mejor = {"tiempo_s": tiempo, "muestras": muestras}
        self._crear_cuerpo()
        return True

    def reiniciar(self):
        self.grabador.reiniciar()

    def esconder(self):
        if self.cuerpo is not None:
            self.cuerpo.enabled = False
