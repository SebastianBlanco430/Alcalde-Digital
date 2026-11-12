# Vista del minijuego «Contrarreloj» (Ursina). Lógica: contrarreloj_calculos.PartidaContrarreloj.
# Las noticias llegan al chat una a una y se propagan solas (barra sin cifras). Con la flecha IZQUIERDA o F se FRENA la
# noticia elegida; con la DERECHA o D se DEJA PASAR. Una noticia que se difunde sin que la juzgues no suma.

from frontend import estilo
from frontend.componentes import a_unidades
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL, Minijuego, Y_CONTENIDO_ARRIBA
from frontend.minijuegos.contrarreloj_calculos import FRENADA, LIBERADA, PENDIENTE, PROPAGADA, PartidaContrarreloj

ANCHO_LISTA = 1.2
ANCHO_TEXTO = 0.72
ANCHO_LATERAL = 0.38


def _palabras_difusion(f):
    if f < 0.34:
        return "Recién llegó"
    if f < 0.72:
        return "Se está difundiendo"
    return "¡Casi viral!"


class MinijuegoContrarreloj(Minijuego):

    TITULO = "Contrarreloj: frena lo falso antes de que se propague"
    AYUDA = "Arriba/Abajo: elegir noticia   Izquierda o F: FRENAR   Derecha o D: DEJAR PASAR   Clic: elegir   Cuanto más llena la barra, más se difundió"

    def construir(self):
        mision = self.mision
        self.partida = PartidaContrarreloj(self.caso, getattr(mision, "rumor", "") or "Rumor del barrio",
                                           bool(getattr(mision, "es_verdadera", True)), self.azar)
        p = self.partida
        n = len(p.cartas)
        y = Y_CONTENIDO_ARRIBA
        y -= 0.0
        self.alto_fila = min(0.108, (y + 0.265) / n - 0.01)
        self.paso = self.alto_fila + 0.01
        self.filas, self.barras, self.rotulos = [], [], []
        for i, c in enumerate(p.cartas):
            cy = y - self.alto_fila / 2 - i * self.paso
            x_fila = -ANCHO_UTIL / 2 + ANCHO_LISTA / 2
            fila = ui.Tarjeta(ANCHO_LISTA, self.alto_fila, c["texto"], "", 15, 13, parent=self,
                              position=(x_fila, cy), al_clic=lambda i=i: self.poner_foco(i), al_cursor=None)
            fila.golpe.z = -0.001
            fila.cuerpo.text = "\n".join(ui.lineas_de(c["texto"], 15, ANCHO_TEXTO))
            barra = ui.Barra(0.36, 0.016, tono=estilo.ESTADO_AVISO, parent=self, position=(x_fila + ANCHO_LISTA / 2 - 0.23, cy + 0.004))
            barra.z = -0.04
            rot = ui.texto(self, "", 13, 0.4, estilo.COLOR_TEXTO_TENUE, (x_fila + ANCHO_LISTA / 2 - 0.41, cy - 0.012))
            fila.enabled = barra.enabled = rot.enabled = False
            self.filas.append(fila)
            self.barras.append(barra)
            self.rotulos.append(rot)
        x_lat = ANCHO_UTIL / 2 - ANCHO_LATERAL / 2
        self.tiempo_txt = ui.texto(self, "Tiempo del chat", 15, ANCHO_LATERAL, estilo.COLOR_TEXTO_TENUE,
                                   (x_lat - ANCHO_LATERAL / 2, Y_CONTENIDO_ARRIBA), negrita=True)
        self.barra_tiempo = ui.Barra(ANCHO_LATERAL, 0.022, tono=estilo.COLOR_BOTON_RESALTADO, parent=self,
                                     position=(x_lat, Y_CONTENIDO_ARRIBA - a_unidades(44)))
        self.boton_frenar = ui.Boton("FRENAR (F)", self.frenar, ANCHO_LATERAL, 0.1, 22, primario=True, parent=self,
                                     position=(x_lat, 0.12))
        self.boton_pasar = ui.Boton("DEJAR PASAR (D)", self.dejar, ANCHO_LATERAL, 0.1, 20, parent=self,
                                    position=(x_lat, -0.02))
        self.nota = ui.texto(self, "Frena lo que creas falso. Deja pasar lo que creas cierto. Lo que se difunda sin que decidas, no suma.",
                             15, ANCHO_LATERAL, estilo.COLOR_TEXTO_TENUE, (x_lat - ANCHO_LATERAL / 2, -0.095))
        self.focables = []
        self.foco = 0
        self._sincronizar()

    # -- Entrada --

    def tecla(self, k):
        if self.terminado:
            return False
        if k in ("left arrow", "f"):
            self.frenar()
            return True
        if k in ("right arrow", "d"):
            self.dejar()
            return True
        if k in ("up arrow", "w"):
            self._mover(-1)
            return True
        if k in ("down arrow", "s", "tab"):
            self._mover(+1)
            return True
        if k in ("enter", "space", "return"):
            self.frenar()
            return True
        return False

    def _pendientes_visibles(self):
        p = self.partida
        return [i for i, c in enumerate(p.cartas) if p.visible(i) and c["estado"] == PENDIENTE]

    def _mover(self, delta):
        cand = self._pendientes_visibles()
        if not cand:
            return
        if self.foco not in cand:
            self.foco = cand[0]
        else:
            self.foco = cand[(cand.index(self.foco) + delta) % len(cand)]
        self._sincronizar()

    def poner_foco(self, i):
        if i in self._pendientes_visibles():
            self.foco = i
            self._sincronizar()

    def frenar(self):
        if not self.terminado and self.partida.frenar(self.foco):
            self._tras_decidir()

    def dejar(self):
        if not self.terminado and self.partida.dejar_pasar(self.foco):
            self._tras_decidir()

    def _tras_decidir(self):
        cand = self._pendientes_visibles()
        if cand:
            self.foco = min(cand, key=lambda i: abs(i - self.foco) if i >= self.foco else 99 + i)
        self._sincronizar()
        if self.partida.terminada:
            self.terminar(self.partida.resultado())

    def avanzar_propio(self, dt):
        antes = {i for i, c in enumerate(self.partida.cartas) if self.partida.visible(i)}
        self.partida.avanzar(dt)
        ahora = {i for i, c in enumerate(self.partida.cartas) if self.partida.visible(i)}
        if ahora != antes and self.foco not in self._pendientes_visibles():
            cand = self._pendientes_visibles()
            if cand:
                self.foco = cand[0]
        self._sincronizar()
        if self.partida.terminada:
            self.terminar(self.partida.resultado())

    def _sincronizar(self):
        p = self.partida
        self.barra_tiempo.fijar(1.0 - min(1.0, p.t / max(0.1, p.duracion)))
        for i, c in enumerate(p.cartas):
            visible = p.visible(i)
            self.filas[i].enabled = self.barras[i].enabled = self.rotulos[i].enabled = visible
            if not visible:
                continue
            f = p.propagacion(i)
            estado = c["estado"]
            if estado == PENDIENTE:
                self.filas[i].fijar_estado("normal")
                self.filas[i].fijar_foco(i == self.foco and not self.terminado)
                self.barras[i].fijar(f, estilo.ESTADO_ERROR if f > 0.72 else estilo.ESTADO_AVISO)
                self.rotulos[i].text = _palabras_difusion(f)
            else:
                self.filas[i].fijar_foco(False)
                self.filas[i].fijar_estado({FRENADA: "frenada", LIBERADA: "liberada", PROPAGADA: "propagada"}[estado])
                self.barras[i].fijar(0.0 if estado == FRENADA else (1.0 if estado == PROPAGADA else f))
                self.rotulos[i].text = {FRENADA: "Frenada", LIBERADA: "Dejada pasar", PROPAGADA: "Se difundió sin que la juzgaras"}[estado]

    def al_terminar_propio(self, resultado):
        p = self.partida
        for i, c in enumerate(p.cartas):
            self.filas[i].enabled = self.barras[i].enabled = self.rotulos[i].enabled = True
            self.filas[i].fijar_foco(False)
            ok = p.acierta(i)
            self.filas[i].fijar_estado("correcta" if ok else "incorrecta",
                                       ("BIEN" if ok else "MAL") + (": era cierta" if c["veraz"] else ": era falsa"))
            self.rotulos[i].text = ""
        self.boton_frenar.fijar_habilitado(False)
        self.boton_pasar.fijar_habilitado(False)
