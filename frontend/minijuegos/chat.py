# Vista del minijuego «Chat del barrio» (Ursina). Lógica: chat_calculos.PartidaChat.
# A la izquierda el chat (mensajes y reacciones); a la derecha tres respuestas posibles y la presión del grupo, que sube con el
# tiempo y se dice en PALABRAS (nunca con números). Si se agota, te quedas en visto.

from frontend import estilo
from frontend.componentes import a_unidades, destruir_arbol
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.chat_calculos import PartidaChat

ANCHO_CHAT = 0.84
ANCHO_OPC = 0.74
MAX_LINEAS_CHAT = 10


def _palabras_presion(p):
    if p < 0.4:
        return "El grupo espera tu respuesta"
    if p < 0.75:
        return "El grupo se impacienta"
    return "¡Te están esperando ya!"


class MinijuegoChat(Minijuego):

    TITULO = "Chat del barrio: responde sin regalar datos de nadie"
    AYUDA = "Arriba/Abajo: cambiar de respuesta   Enter o Espacio: responder   Teclas 1, 2, 3   Clic: responder"

    def construir(self):
        self.partida = PartidaChat(self.caso, self.azar)
        y = Y_CONTENIDO_ARRIBA
        self.x_chat = -ANCHO_UTIL / 2 + ANCHO_CHAT / 2
        self.x_opc = ANCHO_UTIL / 2 - ANCHO_OPC / 2
        alto_chat = Y_CONTENIDO_ARRIBA - (-0.26)
        self.panel = ui.Tarjeta(ANCHO_CHAT, alto_chat, "", self.caso["titulo"], 16, 14,
                                parent=self, position=(self.x_chat, y - alto_chat / 2), tono=estilo.COLOR_PANEL)
        self.panel.cuerpo.text = ""
        self.panel.golpe.collider = None
        self.alto_chat = alto_chat
        self.y_panel = y
        self.log = [("", self.caso["intro"], "contexto")]
        self.texto_chat = ui.texto(self, "", 16, ANCHO_CHAT - a_unidades(24), estilo.COLOR_TEXTO,
                                   (self.x_chat - ANCHO_CHAT / 2 + a_unidades(12), y - a_unidades(36)))
        self.rotulo = ui.texto(self, "", 17, ANCHO_OPC, estilo.COLOR_ACENTO, (self.x_opc - ANCHO_OPC / 2, y), negrita=True)
        self.barra = ui.Barra(ANCHO_OPC, 0.022, tono=estilo.ESTADO_AVISO, parent=self,
                              position=(self.x_opc, y - a_unidades(44)))
        self.opciones = []
        self._pintar_turno()

    def _entrada(self, quien, cuerpo, tipo):
        if tipo == "contexto":
            return cuerpo
        if tipo == "tu":
            return f"Tú: {cuerpo}"
        if tipo == "reaccion":
            return f"   {cuerpo}"
        return f"{quien}: {cuerpo}"

    def _pintar_chat(self):
        """Pinta los mensajes más recientes que CABEN completos (no se corta ninguno por arriba)."""
        ancho = ANCHO_CHAT - a_unidades(24)
        tope = int((self.alto_chat - a_unidades(60)) / (a_unidades(16) * ui.LINEA))
        bloques, usadas = [], 0
        for quien, cuerpo, tipo in reversed(self.log):
            lineas = ui.lineas_de(self._entrada(quien, cuerpo, tipo), 16, ancho) + [""]
            if usadas + len(lineas) - 1 > tope and bloques:
                break
            bloques.insert(0, lineas)
            usadas += len(lineas)
        self.texto_chat.text = "\n".join(l for b in bloques for l in b).rstrip("\n")

    def _pintar_turno(self):
        for o in self.opciones:
            destruir_arbol(o)
        self.opciones = []
        self.focables = []
        turno = self.partida.turno_actual()
        if turno is None:
            self.rotulo.text = "La conversación terminó."
            self.barra.fijar(0.0)
            self._pintar_chat()
            return
        if not self.log or self.log[-1][2] not in ("msg",) or self.log[-1][1] != turno["texto"]:
            self.log.append((turno["de"], turno["texto"], "msg"))
        self._pintar_chat()
        y = self.y_panel - a_unidades(68)
        for i, o in enumerate(turno["opciones"]):
            alto = ui.Tarjeta.alto_necesario(o["texto"], ANCHO_OPC, 17, "Respuesta %d" % (i + 1), 13)
            t = ui.Tarjeta(ANCHO_OPC, alto, o["texto"], "Respuesta %d" % (i + 1), 17, 13, parent=self,
                           position=(self.x_opc, y - alto / 2), al_clic=lambda i=i: self.responder(i),
                           al_cursor=lambda i=i: self.poner_foco(i))
            self.opciones.append(t)
            self.focables.append(t)
            y -= alto + 0.02
        self.foco = 0
        self._pintar_foco()

    def responder(self, i):
        if self.terminado:
            return
        turno = self.partida.turno_actual()
        if turno is None or not 0 <= i < len(turno["opciones"]):
            return
        elegida = turno["opciones"][i]["texto"]
        reaccion = self.partida.responder(i)
        self.log.append(("", elegida, "tu"))
        if reaccion:
            self.log.append(("", reaccion, "reaccion"))
        self._despues_de_turno()

    def _despues_de_turno(self):
        self._pintar_turno()
        if self.partida.terminada:
            self.terminar(self.partida.resultado())

    def tecla_propia(self, k):
        if k in ("1", "2", "3"):
            self.responder(int(k) - 1)
            return True
        return False

    def avanzar_propio(self, dt):
        turno = self.partida.turno_actual()
        if turno is None:
            return
        reaccion = self.partida.avanzar(dt)
        if reaccion is not None:
            self.log.append(("", reaccion, "reaccion"))
            self._despues_de_turno()
            return
        p = self.partida.presion()
        self.barra.fijar(p, estilo.ESTADO_ERROR if p > 0.75 else estilo.ESTADO_AVISO)
        self.rotulo.text = "Presión: " + _palabras_presion(p)

    def al_terminar_propio(self, resultado):
        for o in self.opciones:
            o.habilitada = False
        self.rotulo.text = resultado.detalle
        self.barra.fijar(0.0)
