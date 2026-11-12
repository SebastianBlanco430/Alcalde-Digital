# Vista del minijuego «Ordenar la cadena de difusión» (Ursina). Lógica: cronologia_calculos.PartidaOrden.
# Cinco mensajes barajados; se agarra uno (Enter), se sube o baja con las flechas y se suelta (Enter). «Comprobar» cierra.

from frontend import estilo
from frontend.componentes import a_unidades
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.cronologia_calculos import PartidaOrden

ANCHO_LISTA = 1.12


class MinijuegoCronologia(Minijuego):

    TITULO = "Ordenar la cadena de difusión"
    AYUDA = "Arriba/Abajo: cambiar de mensaje   Enter o Espacio: agarrar o soltar (agarrado, las flechas lo mueven)   C: comprobar"

    def construir(self):
        self.partida = PartidaOrden(self.caso, self.azar)
        p = self.partida
        self.agarrado = False
        y = Y_CONTENIDO_ARRIBA
        intro = ui.texto(self, self.caso["intro"] + "  Arriba va lo que se dijo primero; abajo, lo último.", 16,
                         ANCHO_UTIL, estilo.COLOR_TEXTO, (-ANCHO_UTIL / 2, y))
        y -= intro.alto + a_unidades(8)
        n = len(p.orden)
        self.alto_fila = min(0.085, (y + 0.255) / n - 0.012)
        self.paso = self.alto_fila + 0.012
        self.y0 = y
        self.filas = []
        for pos in range(n):
            self.filas.append(ui.Tarjeta(ANCHO_LISTA, self.alto_fila, "", "·", 16, 13, parent=self,
                                         position=(-ANCHO_UTIL / 2 + ANCHO_LISTA / 2 + 0.05, y - self.alto_fila / 2 - pos * self.paso),
                                         al_clic=lambda pos=pos: self.tocar(pos), al_cursor=lambda pos=pos: self.poner_foco(pos)))
        self.numeros = [ui.texto(self, str(pos + 1), 22, None, estilo.COLOR_ACENTO,
                                 (-ANCHO_UTIL / 2 + 0.0, y - pos * self.paso - self.alto_fila / 2 + a_unidades(11)), negrita=True)
                        for pos in range(n)]
        x_der = ANCHO_UTIL / 2 - 0.25
        self.boton_subir = ui.Boton("Subir", lambda: self._mover(-1), 0.4, 0.07, 17, parent=self, position=(x_der, y - 0.06))
        self.boton_bajar = ui.Boton("Bajar", lambda: self._mover(+1), 0.4, 0.07, 17, parent=self, position=(x_der, y - 0.15))
        self.boton_comprobar = ui.Boton("Comprobar el orden", self.comprobar, 0.4, 0.08, 17, primario=True, parent=self,
                                        position=(x_der, y - 0.26))
        self.nota = ui.texto(self, "", 15, 0.4, estilo.COLOR_TEXTO_TENUE, (x_der - 0.17, y - 0.34))
        self.focables = self.filas + [self.boton_comprobar]
        self._pintar_filas()

    def _pintar_filas(self):
        for pos, tarjeta in enumerate(self.filas):
            item = self.partida.item(pos)
            tarjeta.titulo.text = item["quien"] + (f"   ·   {item['hora']}" if item.get("hora") else "   ·   sin hora visible")
            tarjeta.cuerpo.text = "\n".join(ui.lineas_de(item["texto"], 16, ANCHO_LISTA - a_unidades(20)))
            tarjeta.fijar_estado("seleccionada" if (self.agarrado and pos == self.foco) else "normal")

    def tocar(self, pos):
        if self.terminado:
            return
        self.poner_foco(pos)
        self.agarrado = not self.agarrado
        self._pintar_filas()

    def _mover(self, delta):
        if self.terminado or self.foco >= len(self.filas):
            return
        nuevo = self.partida.mover(self.foco, delta)
        self.foco = nuevo
        self._pintar_filas()
        self._pintar_foco()

    def activar_foco(self):
        if self.foco >= len(self.filas):
            self.comprobar()
            return
        self.agarrado = not self.agarrado
        self._pintar_filas()

    def mover_foco(self, delta):
        if self.agarrado and self.foco < len(self.filas):
            self._mover(delta)
            return
        super().mover_foco(delta)
        self._pintar_filas()

    def tecla_propia(self, k):
        if k == "c":
            self.comprobar()
            return True
        return False

    def comprobar(self):
        if self.terminado:
            return
        self.agarrado = False
        self.partida.comprobar()
        self.terminar(self.partida.resultado())

    def al_terminar_propio(self, resultado):
        en_puesto = self.partida.en_su_puesto()
        for pos, tarjeta in enumerate(self.filas):
            tarjeta.habilitada = False
            real = self.partida.orden[pos] + 1
            if en_puesto[pos]:
                tarjeta.fijar_estado("correcta", "EN SU PUESTO")
            else:
                tarjeta.fijar_estado("incorrecta", f"ERA EL {real}.º")
        self.nota.text = "\n".join(ui.lineas_de(self.caso.get("cierre", ""), 15, 0.4))
        for b in (self.boton_subir, self.boton_bajar, self.boton_comprobar):
            b.fijar_habilitado(False)
        self.focables = []
