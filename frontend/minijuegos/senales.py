# Vista del minijuego «Señales de edición» (Ursina). Lógica: senales_calculos.PartidaSenales.
# Una captura falsa (zonas apiladas como en un teléfono); se marcan hasta tres zonas que delatan edición o engaño. La lupa de la
# derecha dice qué es la zona sobre la que estás (cursor o teclado) sin delatar si está bien.

from frontend import estilo
from frontend.componentes import a_unidades
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.senales_calculos import PartidaSenales

ANCHO_TEL = 1.0
ANCHO_LUPA = 0.56


class MinijuegoSenales(Minijuego):

    TITULO = "Señales de edición en una captura"
    AYUDA = "Arriba/Abajo: cambiar de zona   Enter o Espacio: marcar o desmarcar   C: confirmar   N: no veo nada raro   Clic: marcar"

    def construir(self):
        self.partida = PartidaSenales(self.caso)
        p = self.partida
        self.x_tel = -ANCHO_UTIL / 2 + ANCHO_TEL / 2
        self.x_lupa = ANCHO_UTIL / 2 - ANCHO_LUPA / 2
        y = Y_CONTENIDO_ARRIBA
        ui.texto(self, "CAPTURA QUE CIRCULA: " + self.caso["titulo"], 15, ANCHO_TEL, estilo.COLOR_ACENTO,
                 (self.x_tel - ANCHO_TEL / 2, y), negrita=True)
        y -= a_unidades(32)
        n = len(p.zonas)
        altos = [ui.Tarjeta.alto_necesario(z["texto"], ANCHO_TEL, 17, margen_px=7, reserva=0.2) for z in p.zonas]
        total = sum(altos) + 0.01 * (n - 1)
        marco = ui.rect(self, ANCHO_TEL + 0.07, total + 0.05, estilo.COLOR_PANEL, (self.x_tel, y - total / 2), z=0.1, radio_px=14)
        self.tarjetas = []
        for i, z in enumerate(p.zonas):
            self.tarjetas.append(ui.Tarjeta(ANCHO_TEL, altos[i], z["texto"], "", 17, 13, parent=self,
                                            position=(self.x_tel, y - altos[i] / 2),
                                            al_clic=lambda i=i: self.alternar(i), al_cursor=lambda i=i: self.poner_foco(i),
                                            margen_px=7, reserva=0.2))
            y -= altos[i] + 0.01
        self.lupa_titulo = ui.texto(self, "LUPA", 15, ANCHO_LUPA, estilo.COLOR_TEXTO_TENUE, (self.x_lupa - ANCHO_LUPA / 2, Y_CONTENIDO_ARRIBA), negrita=True)
        self.lupa = ui.texto(self, "", 17, ANCHO_LUPA, estilo.COLOR_TEXTO, (self.x_lupa - ANCHO_LUPA / 2, Y_CONTENIDO_ARRIBA - a_unidades(30)))
        self.marcas_txt = ui.texto(self, "", 16, ANCHO_LUPA, estilo.ESTADO_INFO, (self.x_lupa - ANCHO_LUPA / 2, Y_CONTENIDO_ARRIBA - a_unidades(110)))
        self.revision = ui.texto(self, "", 15, ANCHO_LUPA, estilo.COLOR_TEXTO, (self.x_lupa - ANCHO_LUPA / 2, Y_CONTENIDO_ARRIBA - a_unidades(70)))
        self.boton_confirmar = ui.Boton("Confirmar marcas", self.confirmar, ANCHO_LUPA, 0.06, 17, primario=True, parent=self,
                                        position=(self.x_lupa, -0.165))
        self.boton_nada = ui.Boton("No veo nada raro", self.sin_senales, ANCHO_LUPA, 0.06, 17, parent=self,
                                   position=(self.x_lupa, -0.235))
        self.focables = self.tarjetas + [self.boton_confirmar, self.boton_nada]
        self._pintar_lupa()

    def _pintar_lupa(self):
        if self.terminado:
            return
        if self.foco < len(self.tarjetas):
            z = self.partida.zonas[self.foco]
            self.lupa.text = "\n".join(ui.lineas_de("Mirando: " + z["lupa"] + ".", 17, ANCHO_LUPA))
        else:
            self.lupa.text = "Confirma tus marcas, o di que la captura no tiene nada raro."
        self.marcas_txt.text = f"Zonas sospechosas marcadas: {len(self.partida.marcadas)} de {self.partida.max_marcas}"

    def _pintar_foco(self):
        super()._pintar_foco()
        if self.partida is not None:
            self._pintar_lupa()

    def alternar(self, i):
        if self.terminado:
            return
        antes = i in self.partida.marcadas
        self.partida.marcar(i)
        ahora = i in self.partida.marcadas
        if ahora:
            self.tarjetas[i].fijar_estado("marcada", "SOSPECHOSA")
        else:
            self.tarjetas[i].fijar_estado("normal")
            if not antes:
                self.lupa.text = "Ya usaste todas tus marcas: desmarca una antes de elegir otra."
        self.marcas_txt.text = f"Zonas sospechosas marcadas: {len(self.partida.marcadas)} de {self.partida.max_marcas}"

    def activar_foco(self):
        if self.foco < len(self.tarjetas):
            self.alternar(self.foco)
        else:
            super().activar_foco()

    def confirmar(self):
        if self.terminado:
            return
        self.partida.confirmar()
        self.terminar(self.partida.resultado())

    def sin_senales(self):
        if self.terminado:
            return
        self.partida.declarar_sin_senales()
        self.terminar(self.partida.resultado())

    def tecla_propia(self, k):
        if k == "c":
            self.confirmar()
            return True
        if k == "n":
            self.sin_senales()
            return True
        return False

    def al_terminar_propio(self, resultado):
        reales = self.partida.fallas()
        for i, t in enumerate(self.tarjetas):
            t.habilitada = False
            marcada = i in self.partida.marcadas
            if i in reales:
                t.fijar_estado("encontrada" if marcada else "perdida")
            elif marcada:
                t.fijar_estado("falsa_alarma")
            else:
                t.fijar_estado("normal")
        for b in (self.boton_confirmar, self.boton_nada):
            b.fijar_habilitado(False)
        self.focables = []
        self.lupa_titulo.text = "LO QUE DELATABA LA CAPTURA"
        explicaciones = [self.partida.zonas[i]["explica"] for i in sorted(reales)] or ["No había nada raro: la captura era auténtica."]
        self.lupa.text = ""
        self.revision.y = self.lupa.y
        self.revision.text = "\n\n".join("- " + "\n".join(ui.lineas_de(e, 15, ANCHO_LUPA - a_unidades(14))) for e in explicaciones)
        self.marcas_txt.text = ""
