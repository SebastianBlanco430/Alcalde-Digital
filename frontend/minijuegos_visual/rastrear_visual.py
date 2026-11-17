# «Rastrear la fuente» visual (Ursina): el mismo minijuego (frontend/minijuegos/rastrear.py, lógica rastrear_calculos) como
# un TABLERO DE CORCHO de detective:
#   - cada mensaje es una nota clavada con una chincheta roja (un poco torcida);
#   - el rastro es una fila de notas abajo unidas por un HILO ROJO: «Tú» a la derecha y cada fuente más antigua a la
#     izquierda (hacia atrás en el tiempo). Al acertar, el hilo llega flojo a la nota nueva y se tensa;
#   - un error es un hilo que se enreda: un rodeo visible y un nudo rojo en el contador de rodeos;
#   - momento estrella: al llegar al origen se ilumina el perfil de quien lo publicó primero, con su inicial, la hora y un
#     sello «FUENTE».
# No cambia la partida ni el resultado (hereda y llama a super(); la capa común va delante en el MRO).
# APAGADO: ALCALDE_RASTREAR_VISUAL=0. GUARDIÁN: un fallo esconde el tablero y vuelve a la vista de siempre.

import random

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL
from frontend.minijuegos.rastrear import MinijuegoRastrear
from frontend.minijuegos.rastrear_calculos import MAX_ERRORES
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual
from frontend.minijuegos_visual.trazos import Linea

RASTREAR_VISUAL = True
VARIABLE = "ALCALDE_RASTREAR_VISUAL"

CORCHO = (150, 106, 66)
CORCHO_OSCURO = (118, 80, 48)
ROJO = (214, 52, 52)
PAPEL = (246, 236, 200)
Y_RASTRO = -0.256
X_TU, PASO_NOTA, X_MIN = 0.68, 0.21, -0.40


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class RastrearVisual(CapaVisual, MinijuegoRastrear):

    _tablero_roto = False

    def construir(self):
        self._listo = False
        super().construir()
        try:
            self._montar_corcho()
            self._listo = True
            self._pintar_ronda()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("rastrear_visual", error)
            self._quitar_tablero()

    def _montar_corcho(self):
        arriba, abajo = self.y_ronda + 0.01, -0.27
        self.tablero = Entity(parent=self)
        ui.rect(self.tablero, ANCHO_UTIL + 0.05, arriba - abajo, CORCHO, (0, (arriba + abajo) / 2), z=0.2, radio_px=10)
        azar = random.Random(11)
        for _ in range(40):
            Entity(parent=self.tablero, model="circle", color=_rgba(CORCHO_OSCURO, 0.8), z=0.19,
                   scale=azar.uniform(0.006, 0.014),
                   position=(azar.uniform(-ANCHO_UTIL / 2, ANCHO_UTIL / 2), azar.uniform(abajo + 0.01, arriba - 0.01)))
        self.rastro_txt.enabled = False                      # el rastro se ve como notas e hilo (abajo)
        self.contador = ui.texto(self.tablero, "", 14, 0.4, PAPEL, (-ANCHO_UTIL / 2, Y_RASTRO + 0.012), negrita=True)
        self.contador.z = -0.03
        self.notas, self.hilos = [], []
        self.enredos = []                                    # (Linea, nudo)
        self.elegidos = [("Tú", None)]
        self._t_hilo = None
        self._t_fuente = None
        self._pendiente = None
        self._pintar_rastro()

    def _quitar_tablero(self):
        self._tablero_roto = True
        self._listo = False
        tablero = getattr(self, "tablero", None)
        if tablero is not None:
            tablero.enabled = False
        self.rastro_txt.enabled = True

    # -- Ronda: notas clavadas --

    def _pintar_ronda(self):
        super()._pintar_ronda()
        if not self._listo or self._tablero_roto:
            return
        try:
            reducir = bv.reducir_movimiento()
            for i, nota in enumerate(self.focables):
                Entity(parent=nota, model="circle", scale=0.024, color=_rgba(ROJO), position=(0, nota.alto / 2 - 0.006, -0.05))
                Entity(parent=nota, model="circle", scale=0.01, color=_rgba((255, 200, 200)),
                       position=(-0.004, nota.alto / 2 - 0.002, -0.051))
                nota.rotation_z = 0 if reducir else (((i * 7 + self.partida.indice * 3) % 5) - 2) * 0.9
            self._pintar_contador()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("rastrear_visual", error)
            self._quitar_tablero()

    def _pintar_contador(self):
        libres = max(0, MAX_ERRORES - 1 - self.partida.errores)
        self.contador.text = f"Rodeos: quedan {libres}" + ("  " + "x" * self.partida.errores if self.partida.errores else "")

    # -- Elegir: hilo que se tensa o que se enreda --

    def elegir(self, i):
        salto = self.partida.salto_actual()
        opcion = salto["opciones"][i] if salto is not None and 0 <= i < len(salto["opciones"]) else None
        n_antes, errores_antes = len(self.rastro), self.partida.errores
        posicion = None
        if 0 <= i < len(self.focables):
            nota = self.focables[i]
            posicion = (nota.x, nota.y)
        self._pendiente = opcion          # el origen se pinta DENTRO de super().elegir: necesita saber quién fue
        super().elegir(i)
        self._pendiente = None
        if not self._listo or self._tablero_roto:
            return
        self._vigilar(self._tras_elegir, i, opcion, n_antes, errores_antes, posicion)

    def _tras_elegir(self, i, opcion, n_antes, errores_antes, posicion):
        if len(self.rastro) > n_antes and opcion is not None:
            self.elegidos.append((opcion["de"], opcion.get("hora")))
            self._t_hilo = 0.0
            if self._fx is not None and posicion is not None:
                from frontend.efectos_ui import VERDE
                self._fx.particulas((posicion[0], posicion[1], 0), VERDE)
                self._fx.acierto(None)
            self._pintar_rastro()
        elif self.partida.errores > errores_antes:
            if self._fx is not None:
                nota = self.focables[i] if 0 <= i < len(self.focables) else None
                self._fx.error(nota)
            self._nuevo_enredo()
        self._pintar_contador()

    def _pintar_rastro(self):
        xs = calc.posiciones_rastro(len(self.elegidos), X_TU, PASO_NOTA, X_MIN)
        while len(self.notas) < len(self.elegidos):
            nota = Entity(parent=self.tablero, z=-0.03)
            ui.rect(nota, 0.17, 0.04, PAPEL, (0, 0), z=0.001, radio_px=4)
            Entity(parent=nota, model="circle", scale=0.016, color=_rgba(ROJO), position=(0, 0.02, -0.002))
            nota.texto = Text("", parent=nota, origin=(0, 0), position=(0, -0.002, -0.002), scale=escala_fuente(12),
                              font=tipografia.FUENTE_TITULO, color=_rgba((40, 30, 20)))
            self.notas.append(nota)
        for k, (nota, (nombre, _)) in enumerate(zip(self.notas, self.elegidos)):
            nota.position = (xs[k], Y_RASTRO, -0.03)
            nota.texto.text = calc.recortar(nombre, 18)
        while len(self.hilos) < len(self.elegidos) - 1:
            self.hilos.append(Linea(ROJO, 3, parent=self.tablero, z=-0.025))
        self._pintar_hilos()

    def _pintar_hilos(self):
        reducir = bv.reducir_movimiento()
        for k, hilo in enumerate(self.hilos):
            a = (self.notas[k].x, Y_RASTRO + 0.02)
            b = (self.notas[k + 1].x, Y_RASTRO + 0.02)
            nuevo = k == len(self.hilos) - 1 and self._t_hilo is not None
            caida = calc.caida_hilo(self._t_hilo, reducir=reducir) if nuevo else 0.008
            puntos = calc.catenaria(a, b, caida)
            if nuevo and not reducir:
                puntos = calc.parcial(puntos, min(1.0, self._t_hilo / 0.2))
            hilo.fijar(puntos)

    def _nuevo_enredo(self):
        ultima = self.notas[len(self.elegidos) - 1]
        a = (ultima.x - 0.085, Y_RASTRO + 0.02)
        k = len(self.enredos)
        b = (a[0] - 0.05 - 0.01 * k, Y_RASTRO + 0.03 + 0.012 * (k % 2))
        linea = Linea(ROJO, 2, parent=self.tablero, z=-0.025)
        linea.fijar(calc.enredo(a, b, vueltas=3, radio=0.012))
        nudo = Entity(parent=self.tablero, model="circle", scale=0.016, color=_rgba((120, 20, 20)), position=(b[0], b[1], -0.03))
        self.enredos.append((linea, nudo))

    # -- Momento estrella: la fuente --

    def _pintar_origen(self, y):
        super()._pintar_origen(y)
        if not self._listo or self._tablero_roto or len(self.elegidos) < 2:
            return
        self._vigilar(self._perfil_fuente, y)

    def _perfil_fuente(self, y):
        if self._pendiente is not None:
            nombre, hora = self._pendiente["de"], self._pendiente.get("hora")
        else:
            nombre, hora = self.elegidos[-1]
        origen = self.ronda.children[-1] if self.ronda.children else None
        alto = getattr(origen, "alto", 0.15)
        # Debajo de la tarjeta del origen, sobre el corcho libre (no tapa su texto).
        cx, cy = 0.35, y - alto - 0.1
        self.fuente = Entity(parent=self.ronda, position=(cx, cy, -0.06))
        self.halo = Entity(parent=self.fuente, model="circle", scale=0.12, color=_rgba(estilo.COLOR_ACENTO, 0.35), z=0.002)
        Entity(parent=self.fuente, model="circle", scale=0.085, color=_rgba(estilo.TINTA), z=0.001)
        Entity(parent=self.fuente, model="circle", scale=0.075, color=_rgba((120, 170, 230)))
        Text(nombre[:1].upper() or "?", parent=self.fuente, origin=(0, 0), z=-0.001, scale=escala_fuente(26),
             font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA))
        Text(calc.recortar(nombre, 24) + (f"\n{hora}" if hora else ""), parent=self.fuente, origin=(0, 0.5),
             position=(0, -0.05, -0.001), scale=escala_fuente(13), color=_rgba(estilo.COLOR_TEXTO))
        self.sello_fuente = Text("FUENTE", parent=self.fuente, origin=(0, 0), position=(-0.13, 0.0, -0.002),
                                 rotation_z=-12, scale=escala_fuente(26), font=tipografia.FUENTE_TITULO, color=_rgba(ROJO, 0))
        self._t_fuente = 0.0

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not self._listo or self._tablero_roto:
            return
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        if self._t_hilo is not None:
            self._t_hilo += dt
            self._pintar_hilos()
            if self._t_hilo > 0.6:
                self._t_hilo = None
                self._pintar_hilos()
        if self._t_fuente is not None and getattr(self, "fuente", None) is not None and not self.fuente.is_empty():
            self._t_fuente += dt
            escala, alfa, _ = fx_calc.caida_sello(self._t_fuente - 0.3, reducir=reducir)
            self.sello_fuente.scale = escala_fuente(26) * escala
            self.sello_fuente.color = _rgba(ROJO, alfa)
            if not reducir:
                self.halo.scale = 0.12 + 0.015 * abs(((self._t_fuente * 1.2) % 2) - 1)

