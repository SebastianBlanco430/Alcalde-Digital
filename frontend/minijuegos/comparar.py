# Vista del minijuego «Comparar dos versiones» (Ursina). Lógica: comparar_calculos.PartidaComparar.
# Izquierda: el original. Derecha: la copia que circula; se marcan las líneas alteradas. Botones: Confirmar / No veo diferencias.

from frontend import estilo
from frontend.componentes import a_unidades
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.comparar_calculos import PartidaComparar


class MinijuegoComparar(Minijuego):

    TITULO = "Comparar dos versiones"
    AYUDA = "Arriba/Abajo: cambiar de línea   Enter o Espacio: marcar o desmarcar   C: confirmar   N: no veo diferencias   Clic: marcar"

    def construir(self):
        self.partida = PartidaComparar(self.caso)
        p = self.partida
        ancho_col = (ANCHO_UTIL - 0.06) / 2
        x_izq, x_der = -ANCHO_UTIL / 2 + ancho_col / 2, ANCHO_UTIL / 2 - ancho_col / 2
        y = Y_CONTENIDO_ARRIBA
        ui.texto(self, "ORIGINAL: " + self.caso["original"], 15, ancho_col, estilo.COLOR_TEXTO_TENUE,
                 (x_izq - ancho_col / 2, y), negrita=True)
        ui.texto(self, "COPIA QUE CIRCULA: " + self.caso["copia"], 15, ancho_col, estilo.COLOR_ACENTO,
                 (x_der - ancho_col / 2, y), negrita=True)
        y -= a_unidades(34)
        reserva, margen = 0.2, 7
        disponible = y + 0.205                   # hasta justo encima de los botones
        for px in (17, 16, 15, 14):               # la letra baja un punto si las filas no caben sin pisar los botones
            altos = [max(ui.Tarjeta.alto_necesario(f"{l['etiqueta']}: {l['original']}", ancho_col, px, margen_px=margen),
                         ui.Tarjeta.alto_necesario(f"{l['etiqueta']}: {l['copia']}", ancho_col, px, margen_px=margen, reserva=reserva))
                     for l in p.lineas]
            if sum(altos) + 0.011 * (len(altos) - 1) <= disponible:
                break
        self.izq, self.tarjetas = [], []
        for i, l in enumerate(p.lineas):
            cy = y - altos[i] / 2
            self.izq.append(ui.Tarjeta(ancho_col, altos[i], f"{l['etiqueta']}: {l['original']}", "", px, parent=self,
                                       position=(x_izq, cy), tono=estilo.COLOR_PANEL, margen_px=margen))
            t = ui.Tarjeta(ancho_col, altos[i], f"{l['etiqueta']}: {l['copia']}", "", px, parent=self, position=(x_der, cy),
                           al_clic=lambda i=i: self.alternar(i), al_cursor=lambda i=i: self.poner_foco(i),
                           margen_px=margen, reserva=reserva)
            self.tarjetas.append(t)
            y -= altos[i] + 0.011
        y_botones = -0.245
        self.boton_confirmar = ui.Boton("Confirmar marcas", self.confirmar, 0.44, 0.055, 17, primario=True, parent=self,
                                        position=(x_der - 0.24, y_botones))
        self.boton_igual = ui.Boton("No veo diferencias", self.sin_diferencias, 0.44, 0.055, 17, parent=self,
                                    position=(x_der + 0.22, y_botones))
        self.focables = self.tarjetas + [self.boton_confirmar, self.boton_igual]
    def alternar(self, i):
        if self.terminado:
            return
        quedo = self.partida.marcar(i)
        if quedo:
            self.tarjetas[i].fijar_estado("marcada", "SOSPECHOSA")
        else:
            self.tarjetas[i].fijar_estado("normal")

    def confirmar(self):
        if self.terminado:
            return
        self.partida.confirmar()
        self.terminar(self.partida.resultado())

    def sin_diferencias(self):
        if self.terminado:
            return
        self.partida.declarar_sin_diferencias()
        self.terminar(self.partida.resultado())

    def tecla_propia(self, k):
        if k == "c":
            self.confirmar()
            return True
        if k == "n":
            self.sin_diferencias()
            return True
        return False

    def activar_foco(self):
        f = self.focables[self.foco]
        if f in self.tarjetas:
            self.alternar(self.tarjetas.index(f))
        else:
            super().activar_foco()

    def mover_foco(self, delta):
        super().mover_foco(delta)

    def al_terminar_propio(self, resultado):
        reales = self.partida.alteradas()
        for i, t in enumerate(self.tarjetas):
            t.habilitada = False
            marcada = i in self.partida.marcadas
            if i in reales:
                t.fijar_estado("encontrada" if marcada else "perdida")
            elif marcada:
                t.fijar_estado("falsa_alarma")
            else:
                t.fijar_estado("normal")
        for b in (self.boton_confirmar, self.boton_igual):
            b.fijar_habilitado(False)
        self.focables = []
