# «Contrarreloj» visual (Ursina): el mismo minijuego (frontend/minijuegos/contrarreloj.py, lógica contrarreloj_calculos) con un
# MAPA DEL BARRIO en la columna derecha. Cada noticia es un foco que crece sobre su zona a medida que se difunde (la barra
# de difusión convertida en geografía); un número une cada fila de la lista con su foco.
#   - Frenar: un sello «FRENADA» congela el círculo donde estaba.
#   - Dejar pasar: el círculo se expande con un brillo verde. Sin juzgar: se expande en rojo.
#   - La música tensa se acelera al final y suena un tic-tac en los últimos segundos.
#   - Al terminar: el mapa marca qué zonas quedaron «contagiadas» por bulos que no se frenaron.
#
# No cambia la partida ni el resultado: hereda de MinijuegoContrarreloj, llama a super() y solo dibuja (la capa común,
# frontend/minijuegos_visual/capa.py, se pone delante en el MRO). Durante el juego NO dice si acertaste (eso sería
# información nueva): lo enseña la revisión final, como siempre.
#
# APAGADO: ALCALDE_CONTRARRELOJ_VISUAL=0 (o CONTRARRELOJ_VISUAL = False): se usa la vista de siempre con la capa común.
# GUARDIÁN: un fallo del mapa avisa una vez por stderr, lo esconde y devuelve los botones a su sitio.

from ursina import Entity, Text, color

from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente
from frontend.minijuegos import ui
from frontend.minijuegos.base import ANCHO_UTIL
from frontend.minijuegos.contrarreloj import ANCHO_LATERAL, MinijuegoContrarreloj
from frontend.minijuegos.contrarreloj_calculos import FRENADA, LIBERADA, PENDIENTE, PROPAGADA
from frontend.minijuegos_visual import mapa_barrio_calculos as calc
from frontend.minijuegos_visual.capa import CapaVisual

CONTRARRELOJ_VISUAL = True
VARIABLE = "ALCALDE_CONTRARRELOJ_VISUAL"

MAPA_ANCHO, MAPA_ALTO = ANCHO_LATERAL, 0.21
MAPA_Y = 0.085
Y_FRENAR, Y_PASAR = -0.135, -0.24
RADIO_VISIBLE_MAX = 0.072      # tope del círculo en pantalla (que no tape el mapa entero)
PX_LEYENDA = 12
MUSICA = "musica_tensa"
VOLUMEN_MUSICA = 0.28

TONO_PENDIENTE = (240, 160, 60)
TONO_VIRAL = (235, 87, 87)
TONO_FRENADA = (110, 160, 230)
TONO_LIBERADA = (88, 214, 141)
TONO_CALLE = (70, 76, 92)
TONO_MANZANA = (52, 57, 70)


def _rgba(tono, alfa):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _audio():
    try:
        from frontend import audio
        return audio.obtener()
    except Exception:                    # noqa: BLE001
        return None


class ContrarrelojVisual(CapaVisual, MinijuegoContrarreloj):

    _mapa_roto = False

    def construir(self):
        super().construir()
        self._congelada = {}
        self._t_vis = 0.0
        self._musica = False
        self._t_sellos = {}
        self._radio = {}
        try:
            self._construir_mapa()
        except Exception as error:      # noqa: BLE001  guardián: la vista de siempre
            bv.avisar_una_vez("contrarreloj_visual", error)
            self._quitar_mapa()

    # -- Construcción --

    def _a_mapa(self, x, y):
        return self.x_mapa + x * MAPA_ANCHO, MAPA_Y + y * MAPA_ALTO

    def _construir_mapa(self):
        self.x_mapa = ANCHO_UTIL / 2 - ANCHO_LATERAL / 2
        self.mapa = Entity(parent=self)
        ui.rect(self.mapa, MAPA_ANCHO + 0.008, MAPA_ALTO + 0.008, estilo.TINTA, (self.x_mapa, MAPA_Y), z=0.006, radio_px=8)
        ui.rect(self.mapa, MAPA_ANCHO, MAPA_ALTO, (38, 42, 54), (self.x_mapa, MAPA_Y), z=0.005, radio_px=7)
        # Manzanas y calles (decorado fijo).
        for x, y, w, h in ((-0.30, 0.10, 0.22, 0.30), (0.12, 0.12, 0.30, 0.26), (-0.18, -0.24, 0.40, 0.20),
                           (0.30, -0.10, 0.22, 0.34), (-0.40, -0.06, 0.12, 0.18)):
            cx, cy = self._a_mapa(x, y)
            ui.rect(self.mapa, w * MAPA_ANCHO, h * MAPA_ALTO, TONO_MANZANA, (cx, cy), z=0.004, radio_px=3)
        for y in (-0.12, 0.16):
            cx, cy = self._a_mapa(0, y)
            Entity(parent=self.mapa, model="quad", color=_rgba(TONO_CALLE, 1), scale=(MAPA_ANCHO * 0.96, 0.006),
                   position=(cx, cy, 0.0035))
        for x in (-0.10, 0.20):
            cx, cy = self._a_mapa(x, 0)
            Entity(parent=self.mapa, model="quad", color=_rgba(TONO_CALLE, 1), scale=(0.006, MAPA_ALTO * 0.94),
                   position=(cx, cy, 0.0035))
        # Zonas: punto + nombre (al final se tiñen las contagiadas).
        self.zonas = []
        for nombre, zx, zy in calc.ZONAS:
            cx, cy = self._a_mapa(zx, zy)
            punto = Entity(parent=self.mapa, model="circle", scale=0.012, color=_rgba(estilo.COLOR_TEXTO_TENUE, 0.8),
                           position=(cx, cy, 0.002))
            rotulo = Text(nombre, parent=self.mapa, origin=(0, -0.9), position=(cx, cy + 0.006, 0.001),
                          scale=escala_fuente(10), color=_rgba(estilo.COLOR_TEXTO_TENUE, 0.9))
            self.zonas.append((punto, rotulo))
        self.leyenda = ui.texto(self.mapa, "Mapa del barrio: cada círculo es una noticia que se difunde", PX_LEYENDA,
                                MAPA_ANCHO, estilo.COLOR_TEXTO_TENUE, (self.x_mapa - MAPA_ANCHO / 2, MAPA_Y - MAPA_ALTO / 2 - 0.008))
        # Un foco por noticia: halo de foco (detrás), círculo y número. Más el número en la fila de la lista.
        self.focos, self.halos, self.numeros, self.marcas, self.sellos = [], [], [], [], []
        for i, fila in enumerate(self.filas):
            cx, cy = self._a_mapa(*calc.posicion_foco(i))
            halo = Entity(parent=self.mapa, model="circle", color=_rgba(estilo.COLOR_ACENTO, 0), position=(cx, cy, 0.0015))
            foco = Entity(parent=self.mapa, model="circle", color=_rgba(TONO_PENDIENTE, 0.45), position=(cx, cy, 0.001))
            numero = Text(str(i + 1), parent=self.mapa, origin=(0, 0), position=(cx, cy, -0.002), scale=escala_fuente(13),
                          font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_TEXTO, 1))
            sello = Text("FRENADA", parent=self.mapa, origin=(0, 0), position=(cx, cy - 0.022, -0.003), rotation_z=-12,
                         scale=escala_fuente(12), font=tipografia.FUENTE_TITULO, color=_rgba(TONO_FRENADA, 1), enabled=False)
            marca = Entity(parent=self, position=(fila.x - fila.ancho / 2 - 0.022, fila.y, -0.01))
            Entity(parent=marca, model="circle", scale=0.03, color=_rgba(estilo.TINTA, 1), z=0.001)
            Entity(parent=marca, model="circle", scale=0.025, color=_rgba(TONO_PENDIENTE, 1))
            Text(str(i + 1), parent=marca, origin=(0, 0), z=-0.001, scale=escala_fuente(12), font=tipografia.FUENTE_TITULO,
                 color=_rgba(estilo.TINTA, 1))
            for e in (halo, foco, numero, marca):
                e.enabled = False
            self.focos.append(foco)
            self.halos.append(halo)
            self.numeros.append(numero)
            self.marcas.append(marca)
            self.sellos.append(sello)
            self._radio[i] = calc.RADIO_MIN
        # La columna se reordena: el mapa ocupa el sitio de la nota (las teclas siguen en el pie y en «Antes de empezar»).
        self._posiciones_originales = (self.boton_frenar.y, self.boton_pasar.y, self.nota.enabled)
        self.boton_frenar.y, self.boton_pasar.y = Y_FRENAR, Y_PASAR
        self.nota.enabled = False

    def _quitar_mapa(self):
        self._mapa_roto = True
        mapa = getattr(self, "mapa", None)
        if mapa is not None:
            mapa.enabled = False
        for marca in getattr(self, "marcas", []):
            marca.enabled = False
        if getattr(self, "_posiciones_originales", None):
            self.boton_frenar.y, self.boton_pasar.y, self.nota.enabled = self._posiciones_originales
        self._parar_musica()

    # -- Decisiones: sello al frenar --

    def frenar(self):
        i = self.foco
        estaba = self.partida.cartas[i]["estado"] if 0 <= i < len(self.partida.cartas) else None
        f = self.partida.propagacion(i) if estaba == PENDIENTE else None
        super().frenar()
        if estaba == PENDIENTE and self.partida.cartas[i]["estado"] == FRENADA and not self._mapa_roto:
            self._congelada[i] = f
            self._t_sellos[i] = 0.0
            if self._fx is not None:
                self._vigilar(self._fx.pulso, self.filas[i])

    def dejar(self):
        i = self.foco
        super().dejar()
        if 0 <= i < len(self.filas) and self._fx is not None and self.partida.cartas[i]["estado"] == LIBERADA:
            self._vigilar(self._fx.pulso, self.filas[i])

    # -- Bucle visual --

    def al_montar_visual(self):
        super().al_montar_visual()
        if not self._mapa_roto:
            sonido = _audio()
            if sonido is not None:
                try:
                    sonido.bucle(MUSICA, volumen=VOLUMEN_MUSICA, pitch=1.0, fundido=0.8)
                    self._musica = True
                except Exception:        # noqa: BLE001
                    self._musica = False

    def avanzar_visual_propio(self, dt):
        super().avanzar_visual_propio(dt)
        if self._mapa_roto:
            return
        try:
            self._pintar_mapa(dt)
            self._sonido_del_tiempo(dt)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("contrarreloj_visual", error)
            self._quitar_mapa()

    def _pintar_mapa(self, dt):
        p = self.partida
        reducir = self._fx.reducir if self._fx is not None else bv.reducir_movimiento()
        self._t_vis += dt
        for i, c in enumerate(p.cartas):
            visible = p.visible(i) or self.terminado
            for e in (self.focos[i], self.numeros[i], self.marcas[i]):
                e.enabled = visible
            if not visible:
                self.halos[i].enabled = False
                continue
            estado = c["estado"]
            objetivo = calc.radio_objetivo(estado, p.propagacion(i), self._congelada.get(i))
            actual = self._radio[i]
            self._radio[i] = objetivo if reducir else fx_calc.acercar(actual, objetivo, dt, 0.18)
            radio = self._radio_visible(i, self._radio[i])
            self.focos[i].scale = 2 * radio
            if estado == PENDIENTE:
                f = p.propagacion(i)
                tono = TONO_VIRAL if f > 0.72 else TONO_PENDIENTE
                alfa = 0.35 + 0.25 * f
            elif estado == FRENADA:
                tono, alfa = TONO_FRENADA, 0.55
            elif estado == LIBERADA:
                tono = TONO_LIBERADA
                alfa = 0.30 if reducir else 0.22 + 0.16 * calc.brillo(self._t_vis, 1.1)
            else:
                tono, alfa = TONO_VIRAL, 0.3
            self.focos[i].color = _rgba(tono, alfa)
            self.marcas[i].children[1].color = _rgba(tono, 1)
            enfocado = estado == PENDIENTE and i == self.foco and not self.terminado
            self.halos[i].enabled = enfocado
            if enfocado:
                self.halos[i].scale = 2 * radio + 0.018
                self.halos[i].color = _rgba(estilo.COLOR_ACENTO, 0.8 if reducir else 0.45 + 0.4 * calc.brillo(self._t_vis))
            if i in self._t_sellos:
                self._t_sellos[i] += dt
                escala, alfa_sello, _ = fx_calc.caida_sello(self._t_sellos[i], reducir=reducir)
                self.sellos[i].enabled = True
                self.sellos[i].scale = escala_fuente(12) * escala
                self.sellos[i].color = _rgba(TONO_FRENADA, alfa_sello)
                if self._t_sellos[i] > fx_calc.DUR_SELLO:
                    del self._t_sellos[i]

    def _radio_visible(self, i, radio):
        """Radio en unidades de pantalla, recortado para no salirse del mapa."""
        x, y = calc.posicion_foco(i)
        en_pantalla = radio * MAPA_ALTO
        margen_x = (0.5 - abs(x)) * MAPA_ANCHO
        margen_y = (0.5 - abs(y)) * MAPA_ALTO
        return max(0.008, min(en_pantalla, margen_x, margen_y, RADIO_VISIBLE_MAX))

    def _sonido_del_tiempo(self, dt):
        if self.terminado:
            return
        p = self.partida
        restante_ahora = p.duracion - p.t
        restante_antes = restante_ahora + dt
        sonido = _audio()
        if sonido is None:
            return
        if self._musica:
            sonido.ajustar_bucle(MUSICA, pitch=calc.pitch_musica(p.t, p.duracion))
        if calc.tictac(restante_antes, restante_ahora):
            sonido.efecto("clic_ui", volumen=0.9, pitch=0.55)

    # -- Fin: zonas contagiadas --

    def al_terminar_propio(self, resultado):
        super().al_terminar_propio(resultado)
        self._parar_musica()
        if self._mapa_roto:
            return
        try:
            self._mostrar_contagio()
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("contrarreloj_visual", error)
            self._quitar_mapa()

    def _mostrar_contagio(self):
        p = self.partida
        focos = []
        for i, c in enumerate(p.cartas):
            x, y = calc.posicion_foco(i)
            radio = calc.radio_objetivo(c["estado"], p.propagacion(i), self._congelada.get(i))
            focos.append((x, y, radio, calc.contagia(c["veraz"], c["estado"])))
        contagiadas = calc.zonas_contagiadas(focos)
        for z, (punto, rotulo) in enumerate(self.zonas):
            if z in contagiadas:
                punto.scale = 0.02
                punto.color = _rgba(TONO_VIRAL, 1)
                rotulo.text = calc.ZONAS[z][0] + " !"
                rotulo.color = _rgba(TONO_VIRAL, 1)
            else:
                punto.color = _rgba(TONO_LIBERADA, 0.9)
        self.leyenda.text = "\n".join(ui.lineas_de(calc.texto_contagio(len(contagiadas)), PX_LEYENDA + 2, MAPA_ANCHO))
        self.leyenda.scale = escala_fuente(PX_LEYENDA + 2)
        # Los botones ya no sirven (la vista de siempre los deshabilita): se esconden para dejar ver el mapa y el banner.
        self.boton_frenar.enabled = self.boton_pasar.enabled = False
        self.leyenda.color = _rgba(TONO_VIRAL if contagiadas else TONO_LIBERADA, 1)

    # -- Música: se para al terminar o si la pantalla se destruye a mitad --

    def _parar_musica(self):
        if self._musica:
            self._musica = False
            sonido = _audio()
            if sonido is not None:
                try:
                    sonido.parar_bucle(MUSICA, fundido=0.6)
                except Exception:        # noqa: BLE001
                    pass

    def on_destroy(self):
        self._parar_musica()
