# «Cronología» visual (Ursina): el mismo minijuego (frontend/minijuegos/cronologia.py, lógica cronologia_calculos) con
#   - un RELOJ GIGANTE al fondo cuyas agujas giran hacia la hora de la tarjeta con el foco;
#   - las tarjetas CUELGAN de una cuerda (hilo y chincheta a la izquierda) y se balancean al soltarlas;
#   - momento estrella: al comprobar, la cadena se «reproduce» en su orden real y el rumor CRECE con cada reenvío: la
#     burbuja engorda y se le agregan mayúsculas, signos y «¡¡COMPARTE YA!!». Se ve cómo un dato se convierte en bulo.
# No cambia la partida ni el resultado. APAGADO: ALCALDE_CRONOLOGIA_VISUAL=0. GUARDIÁN: un fallo quita lo añadido.
# REDUCIR MOVIMIENTO: sin balanceo; las agujas saltan; la reproducción no engorda la burbuja.

import math

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL
from frontend.minijuegos.cronologia import ANCHO_BOTONES, ANCHO_LISTA, MinijuegoCronologia
from frontend.minijuegos_visual import pistas_visuales_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual
from frontend.minijuegos_visual.trazos import Linea

CRONOLOGIA_VISUAL = True
VARIABLE = "ALCALDE_CRONOLOGIA_VISUAL"

CUERDA = (196, 160, 110)
RADIO_RELOJ = 0.085
DUR_PASO = 0.9


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


class CronologiaVisual(CapaVisual, MinijuegoCronologia):

    _reloj_roto = False

    def construir(self):
        self._listo = False
        super().construir()
        try:
            self._montar()
            self._listo = True
            self._apuntar_agujas(inmediato=True)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("cronologia_visual", error)
            self._quitar()

    def _montar(self):
        x_der = ANCHO_UTIL / 2 - ANCHO_BOTONES / 2
        # En el hueco libre bajo «Comprobar el orden» (la nota del cierre solo aparece al final, y el reloj se esconde).
        self.reloj = Entity(parent=self, position=(x_der, self.y0 - 0.39, 0.05))
        Entity(parent=self.reloj, model="circle", scale=2 * RADIO_RELOJ + 0.01, color=_rgba(estilo.TINTA, 0.5), z=0.002)
        Entity(parent=self.reloj, model="circle", scale=2 * RADIO_RELOJ, color=_rgba((40, 44, 58), 0.9), z=0.001)
        for h in range(12):
            angulo = math.radians(h * 30)
            largo = 0.016 if h % 3 == 0 else 0.009
            r = RADIO_RELOJ - 0.012 - largo / 2
            Entity(parent=self.reloj, model="quad", color=_rgba(estilo.COLOR_TEXTO_TENUE, 0.8), scale=(0.006, largo),
                   rotation_z=h * 30, position=(r * math.sin(angulo), r * math.cos(angulo), 0))
        self.aguja_h = Entity(parent=self.reloj, model="quad", origin=(0, -0.5), scale=(0.008, RADIO_RELOJ * 0.55),
                              color=_rgba(estilo.COLOR_ACENTO, 0.9), z=-0.001)
        self.aguja_m = Entity(parent=self.reloj, model="quad", origin=(0, -0.5), scale=(0.005, RADIO_RELOJ * 0.82),
                              color=_rgba(estilo.COLOR_TEXTO, 0.9), z=-0.002)
        Entity(parent=self.reloj, model="circle", scale=0.02, color=_rgba(estilo.COLOR_ACENTO), z=-0.003)
        self.reloj_txt = Text("", parent=self.reloj, origin=(0, 0.5), position=(0, -RADIO_RELOJ - 0.012, -0.003),
                              scale=escala_fuente(13), color=_rgba(estilo.COLOR_TEXTO_TENUE))
        self._angulos = [0.0, 0.0]
        self._objetivo = (0.0, 0.0)
        # Cuerda vertical a la izquierda y un hilo corto con chincheta por tarjeta.
        x_cuerda = self.filas[0].x - ANCHO_LISTA / 2 - 0.018
        arriba = self.filas[0].y + self.alto_fila / 2 + 0.02
        abajo = self.filas[-1].y - self.alto_fila / 2 - 0.01
        self.cuerda = Linea(CUERDA, 3, parent=self, z=0.05)
        self.cuerda.fijar([(x_cuerda, arriba), (x_cuerda, abajo)])
        for fila in self.filas:
            Entity(parent=fila, model="circle", scale=0.016, color=_rgba((210, 60, 60)),
                   position=(-ANCHO_LISTA / 2 + 0.012, fila.alto / 2 - 0.012, -0.05))
        self._t_balanceo = {}
        self._agarrado_antes = False
        self._t_reproduccion = None
        self.burbuja = None

    def _quitar(self):
        self._reloj_roto = True
        self._listo = False
        for nombre in ("reloj", "cuerda", "burbuja"):
            e = getattr(self, nombre, None)
            if e is not None:
                e.enabled = False
        for fila in self.filas:
            fila.rotation_z = 0
        if getattr(self, "nota", None) is not None:
            self.nota.enabled = True

    # -- Reloj --

    def _pintar_filas(self):
        super()._pintar_filas()
        if getattr(self, "_listo", False) and not self._reloj_roto:
            self._vigilar(self._tras_pintar)

    def _tras_pintar(self):
        # Al soltar una tarjeta se balancea.
        if self._agarrado_antes and not self.agarrado and self.foco < len(self.filas):
            self._t_balanceo[self.foco] = 0.0
        self._agarrado_antes = self.agarrado
        self._apuntar_agujas()

    def _pintar_foco(self):
        super()._pintar_foco()
        if getattr(self, "_listo", False) and not self._reloj_roto:
            self._vigilar(self._apuntar_agujas)

    def _apuntar_agujas(self, inmediato=False):
        if self.foco >= len(self.filas):
            return
        hora = self.partida.item(self.foco).get("hora")
        angulos = calc.angulos_reloj(hora)
        self.reloj_txt.text = hora or "sin hora"
        if angulos is None:
            return
        self._objetivo = angulos
        if inmediato or bv.reducir_movimiento():
            self._angulos = list(angulos)
            self._pintar_agujas()

    def _pintar_agujas(self):
        self.aguja_h.rotation_z = self._angulos[0]
        self.aguja_m.rotation_z = self._angulos[1]

    # -- Momento estrella: el rumor crece con cada reenvío --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        if getattr(self, "_listo", False) and not self._reloj_roto:
            self._vigilar(self._empezar_reproduccion)

    def _empezar_reproduccion(self):
        x_der = ANCHO_UTIL / 2 - ANCHO_BOTONES / 2
        self.nota.enabled = False
        for b in (self.boton_subir, self.boton_bajar, self.boton_comprobar):
            b.enabled = False
        self.reloj.enabled = False
        self.burbuja = Entity(parent=self, position=(x_der, self.y0 - 0.14, -0.1))
        self.burbuja_fondo = ui.rect(self.burbuja, ANCHO_BOTONES + 0.02, 0.26, (250, 250, 245), (0, 0), z=0.002, radio_px=16)
        self.burbuja_quien = Text("", parent=self.burbuja, origin=(-0.5, 0.5), position=(-ANCHO_BOTONES / 2 + 0.01, 0.115, -0.001),
                                  scale=escala_fuente(13), font=tipografia.FUENTE_TITULO, color=_rgba((90, 90, 110)))
        self.burbuja_txt = Text("", parent=self.burbuja, origin=(-0.5, 0.5), position=(-ANCHO_BOTONES / 2 + 0.01, 0.08, -0.001),
                                scale=escala_fuente(15), color=_rgba((25, 25, 35)))
        self._t_reproduccion = 0.0
        self._paso_visto = None

    def _pintar_reproduccion(self, reducir):
        correcto = self.partida.correcto
        paso = calc.paso_reproduccion(self._t_reproduccion, len(correcto), DUR_PASO)
        if paso is None:
            if self._t_reproduccion > DUR_PASO * len(correcto) + 2.5:
                self.burbuja.enabled = False
                self.nota.enabled = True
                self._t_reproduccion = None
            return
        if paso != self._paso_visto:
            self._paso_visto = paso
            item = correcto[paso]
            self.burbuja_quien.text = f"Reenvío {paso + 1} de {len(correcto)} · {calc.recortar(item['quien'], 22)}"
            texto = calc.exagerar(item["texto"], paso)
            self.burbuja_txt.text = "\n".join(ui.lineas_de(texto, 15, ANCHO_BOTONES - 0.03)[:6])
            escala = 1.0 if reducir else calc.escala_burbuja(paso)
            self.burbuja.scale = escala
            # La tarjeta de ese mensaje (en el orden que dejó el jugador) da un pulso.
            for pos in range(len(self.filas)):
                if self.partida.orden[pos] == paso and self._fx is not None:
                    self._fx.pulso(self.filas[pos])

    # -- Bucle visual --

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if not getattr(self, "_listo", False) or self._reloj_roto:
            return
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        if not reducir and self.reloj.enabled:
            self._angulos[0] = calc.acercar_angulo(self._angulos[0], self._objetivo[0], dt)
            self._angulos[1] = calc.acercar_angulo(self._angulos[1], self._objetivo[1], dt)
            self._pintar_agujas()
        for pos in list(self._t_balanceo):
            self._t_balanceo[pos] += dt
            self.filas[pos].rotation_z = calc.balanceo(self._t_balanceo[pos], reducir=reducir)
            if self._t_balanceo[pos] > 2.0:
                self.filas[pos].rotation_z = 0
                del self._t_balanceo[pos]
        if self._t_reproduccion is not None:
            self._t_reproduccion += dt
            self._pintar_reproduccion(reducir)
