# Vista del minijuego «Rastrear la fuente» (Ursina). Lógica: rastrear_calculos.PartidaRastreo.
# Muestras tres mensajes por salto (quién, cuándo y qué dice); hay que elegir el más antiguo que no sea un reenvío.

from ursina import destroy

from frontend import estilo
from frontend.componentes import a_unidades, destruir_arbol
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.rastrear_calculos import MAX_ERRORES, PartidaRastreo

PISTA = "Regla: el original es el más ANTIGUO y no dice «reenviado». Los reenvíos y las copias son posteriores."


class MinijuegoRastrear(Minijuego):

    TITULO = "Rastrear la fuente"
    AYUDA = "Izquierda/Derecha o Tab: cambiar de mensaje   Enter o Espacio: elegirlo   Teclas 1, 2, 3   Clic: elegir"

    def construir(self):
        self.partida = PartidaRastreo(self.caso, self.azar)
        y = Y_CONTENIDO_ARRIBA
        intro = ui.texto(self, self.caso["intro"], 17, ANCHO_UTIL, estilo.COLOR_TEXTO, (-ANCHO_UTIL / 2, y))
        y -= intro.alto + a_unidades(8)
        self.y_ronda = y
        self.estado_txt = ui.texto(self, PISTA, 15, ANCHO_UTIL, estilo.COLOR_TEXTO_TENUE, (-ANCHO_UTIL / 2, -0.205))
        self.rastro_txt = ui.texto(self, "", 15, ANCHO_UTIL, estilo.ESTADO_INFO, (-ANCHO_UTIL / 2, -0.245))
        self.ronda = None
        self.rastro = ["Tú"]
        self._pintar_ronda()

    def _pintar_ronda(self):
        if self.ronda is not None:
            destruir_arbol(self.ronda)
        self.ronda = ui.Entity(parent=self)
        self.focables = []
        salto = self.partida.salto_actual()
        y = self.y_ronda
        if salto is None:
            self._pintar_origen(y)
            return
        n = self.partida.indice + 1
        ui.texto(self.ronda, f"Paso {n} de {len(self.partida.saltos)}: {salto['pregunta']}", 19, ANCHO_UTIL,
                 estilo.COLOR_TEXTO, (-ANCHO_UTIL / 2, y), negrita=True)
        y -= a_unidades(44)
        ancho = (ANCHO_UTIL - 2 * 0.04) / 3
        alto = max(ui.Tarjeta.alto_necesario(o["texto"], ancho, 17, "x", 14) for o in salto["opciones"]) + 0.03
        alto = max(alto, 0.24)
        for i, o in enumerate(salto["opciones"]):
            x = -ANCHO_UTIL / 2 + ancho / 2 + i * (ancho + 0.04)
            tarjeta = ui.Tarjeta(ancho, alto, o["texto"], f"{o['de']}  ·  {o['hora']}", 17, parent=self.ronda,
                                 position=(x, y - alto / 2), al_clic=lambda i=i: self.elegir(i),
                                 al_cursor=lambda i=i: self.poner_foco(i))
            if i in salto["descartadas"]:
                tarjeta.fijar_estado("descartada")
                tarjeta.habilitada = False
            self.focables.append(tarjeta)
        self.foco = next((i for i, f in enumerate(self.focables) if f.habilitada), 0)
        self._pintar_foco()
        self.rastro_txt.text = "Rastro: " + "  >  ".join(self.rastro) + f"      (rodeos permitidos: {max(0, MAX_ERRORES - 1 - self.partida.errores)})"

    def _pintar_origen(self, y):
        origen = self.partida.origen()
        if origen is None:
            return
        ancho = ANCHO_UTIL
        alto = ui.Tarjeta.alto_necesario(origen["detalle"], ancho, 19, origen["titulo"], 16) + 0.03
        tarjeta = ui.Tarjeta(ancho, alto, origen["detalle"], origen["titulo"], 19, 16, parent=self.ronda,
                             position=(0, y - alto / 2), tono=estilo.COLOR_PANEL)
        tarjeta.fijar_estado("correcta", "LLEGASTE AL ORIGEN")

    def elegir(self, i):
        if self.terminado:
            return
        resultado = self.partida.elegir(i)
        if resultado == "bien":
            salto_previo = self.partida.saltos[self.partida.indice - 1]
            self.rastro.append(salto_previo["opciones"][i]["de"])
            self.estado_txt.text = "Bien: ese mensaje es anterior. Sigue hacia atrás."
        elif resultado == "error":
            self.estado_txt.text = "Ese mensaje es posterior o es un reenvío. Prueba con otro."
        else:
            return
        self._pintar_ronda()
        if self.partida.terminada:
            self.terminar(self.partida.resultado())

    def tecla_propia(self, k):
        if k in ("1", "2", "3") and not self.terminado:
            self.elegir(int(k) - 1)
            return True
        return False

    def al_terminar_propio(self, resultado):
        if self.partida.llegado:
            self.estado_txt.text = "Llegaste al origen: ahora sabes de quién salió."
        else:
            self.estado_txt.text = "Perdiste el rastro: demasiados mensajes equivocados."
        self.rastro_txt.text = "Rastro: " + "  >  ".join(self.rastro)
