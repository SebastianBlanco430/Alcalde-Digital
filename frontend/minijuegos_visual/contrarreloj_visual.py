# «Contrarreloj» visual (Ursina): el mismo minijuego (frontend/minijuegos/contrarreloj.py, lógica contrarreloj_calculos) con un
# MAPA DEL BARRIO en la columna izquierda: una LADERA dibujada como cómic (casas escalonadas de colores por lugar, terrazas,
# cresta con sol). Cada noticia es una mancha con borde de tinta que crece detrás de las casas de su zona a medida que se
# difunde; una chapa con su número la une con su noticia. El paisaje estático es UNA sola malla (un dibujo).
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
from frontend.minijuegos.contrarreloj import MinijuegoContrarreloj
from frontend.minijuegos.contrarreloj_calculos import FRENADA, LIBERADA, PENDIENTE, PROPAGADA
from frontend.minijuegos_visual import contrarreloj_piezas_calculos as pc
from frontend.minijuegos_visual import ladera_calculos as lad
from frontend.minijuegos_visual import mapa_barrio_calculos as calc
from frontend.minijuegos_visual import papel_calculos as papel
from frontend.minijuegos_visual import piezas_contrarreloj as pz
from frontend.minijuegos_visual.capa import CapaVisual

CONTRARRELOJ_VISUAL = True
VARIABLE = "ALCALDE_CONTRARRELOJ_VISUAL"

# Mesa del barrio: ~60 % del ancho, a la izquierda. Cinta de noticias a la derecha. El mapa va de y 0,30 (bajo la cabecera) a -0,23 para que el
# banner de resultado de la escena (abajo) no tape la fila de abajo; la leyenda va justo debajo.
MAPA_ANCHO, MAPA_ALTO = 1.10, 0.53
X_MAPA, MAPA_Y = -0.29, 0.035
ANCHO_TARJETA = 0.46
Y_FRENAR, Y_PASAR = -0.335, -0.425
ANCHO_BOTON, ALTO_BOTON = 0.40, 0.08
PX_LEYENDA = 17
PX_ZONA = 14
ALFA_MANCHA = 0.55
ALFA_CONTAGIO = 0.42
GROSOR_BORDE = 0.0055           # borde de tinta de la mancha (≈ 3 px)
MUSICA = "musica_tensa"
VOLUMEN_MUSICA = 0.28

TONO_PENDIENTE = (240, 160, 60)
TONO_VIRAL = (214, 62, 62)
TONO_FRENADA = (60, 110, 200)
TONO_LIBERADA = (80, 190, 110)
TONO_TEXTO_SUAVE = (70, 66, 58)


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
        self.marcas = []
        try:
            self._construir_mapa()
        except Exception as error:      # noqa: BLE001  guardián: la vista de siempre
            bv.avisar_una_vez("contrarreloj_visual", error)
            self._quitar_mapa()

    # -- Construcción --

    def _a_mapa(self, x, y):
        return X_MAPA + x * MAPA_ANCHO, MAPA_Y + y * MAPA_ALTO

    def _centro_zona(self, indice):
        """Centro de la zona en pantalla (donde se dibujan sus casas)."""
        dx, dy = lad.posicion_zona(indice, MAPA_ANCHO, MAPA_ALTO)
        return X_MAPA + dx, MAPA_Y + dy

    def _construir_mapa(self):
        self.x_mapa = X_MAPA
        self.mapa = Entity(parent=self)
        pz.sombra_plana(self.mapa, MAPA_ANCHO, MAPA_ALTO, (X_MAPA, MAPA_Y), z=0.011, radio_px=10)
        ui.rect(self.mapa, MAPA_ANCHO + 0.008, MAPA_ALTO + 0.008, estilo.TINTA, (X_MAPA, MAPA_Y), z=0.010, radio_px=10)
        ui.rect(self.mapa, MAPA_ANCHO, MAPA_ALTO, pz.PAPEL_VIEJO, (X_MAPA, MAPA_Y), z=0.009, radio_px=9)
        # Paisaje estático (cielo, terrazas, escaleras, casas y chapas de nombre) en una sola malla.
        n_zonas = len(calc.ZONAS)
        self._ancho_nombre = [ui.medir(nombre, PX_ZONA, True) + 0.04 for nombre, _, _ in calc.ZONAS]
        self.escenario = pz.escenario_ladera(self.mapa, MAPA_ANCHO, MAPA_ALTO, self._ancho_nombre, (X_MAPA, MAPA_Y))
        # Nombres de zona (texto sobre sus chapas de papel) y manchas de contagio finales (apagadas hasta el final).
        self.rotulos_zona, self.teñidos = [], []
        for z, (nombre, _, _) in enumerate(calc.ZONAS):
            cx, cy = self._centro_zona(z)
            ex, ey = lad.etiqueta_de_zona(z, cx, cy)
            self.rotulos_zona.append(Text(nombre, parent=self.mapa, origin=(0, 0), position=(ex, ey, 0.0015),
                                          scale=escala_fuente(PX_ZONA), font=tipografia.FUENTE_TITULO,
                                          color=_rgba(estilo.TINTA, 1)))
            mancha = pz.Mancha(1.7 * z, parent=self.mapa, position=(cx, cy, lad.Z_MANCHA + 0.0001),
                               scale=0.12, color=_rgba(TONO_VIRAL, ALFA_CONTAGIO), enabled=False)
            self.teñidos.append(mancha)
        self.leyenda_raiz, self.leyenda = pz.tira_leyenda(
            self.mapa, "Cada mancha es una noticia que se difunde por el barrio", PX_LEYENDA,
            (X_MAPA - MAPA_ANCHO / 2, MAPA_Y - MAPA_ALTO / 2), MAPA_ANCHO - 0.04)
        # Un foco por noticia: mancha (relleno), borde de tinta, aro de foco (amarillo) y chapa con el número.
        self.focos, self.bordes, self.halos, self.numeros = [], [], [], []
        for i, fila in enumerate(self.filas):
            cx, cy = self._a_mapa(*calc.posicion_foco(i))
            fase = 1.3 * i
            foco = pz.Mancha(fase, parent=self.mapa, position=(cx, cy, lad.Z_MANCHA), color=_rgba(TONO_PENDIENTE, ALFA_MANCHA))
            borde = pz.AnilloMancha(fase, parent=self.mapa, position=(cx, cy, lad.Z_ARO), color=_rgba(estilo.TINTA, 1))
            halo = pz.AnilloMancha(fase, parent=self.mapa, position=(cx, cy, lad.Z_ARO + 0.0003),
                                   color=_rgba(estilo.COLOR_ACENTO, 1))
            zi = i % n_zonas
            zx, zy = self._centro_zona(zi)
            ex, ey = lad.etiqueta_de_zona(zi, zx, zy)
            vuelta = i // n_zonas
            chapa = pz.Chapa(i + 1, parent=self.mapa, position=(ex - self._ancho_nombre[zi] / 2 - 0.02 + 0.06 * vuelta * MAPA_ANCHO,
                                                                  ey - 0.05 * vuelta * MAPA_ALTO, 0.0015))
            for e in (foco, borde, halo, chapa):
                e.enabled = False
            self.focos.append(foco)
            self.bordes.append(borde)
            self.halos.append(halo)
            self.numeros.append(chapa)
            self._radio[i] = calc.RADIO_MIN
        self.sellos = [None] * len(self.filas)
        self.enlace = pz.LineaDiscontinua(parent=self, tono=estilo.TINTA, grosor=0.005, z=-0.02)
        self._cinta_y_botones()

    def _cinta_y_botones(self):
        """Cinta de papeles a la derecha (barra de difusión con borde de tinta), línea de peligro, cronómetro y botones
        apilados. Se construye entera antes de sustituir lo de la vista base, así un fallo a medias no deja nada roto."""
        n = len(self.partida.cartas)
        alto, ys = pc.huecos_cinta(n)
        x = pc.X_CINTA
        reducir = bv.reducir_movimiento()
        filas, barras, rotulos = [], [], []
        for i, c in enumerate(self.partida.cartas):
            fila = pz.TarjetaTitular(ANCHO_TARJETA, alto, c["texto"], i + 1, parent=self, position=(x, ys[i]),
                                     al_clic=lambda i=i: self.poner_foco(i), al_cursor=None)
            fila.golpe.z = -0.001
            fila.rotation_z = 0.0 if reducir else papel.giro_por_id("cr%d" % i, 0.6)
            y_fila = ys[i] - alto / 2 + 0.017
            x_barra = x - ANCHO_TARJETA / 2 + 0.068 + 0.085
            barra = pz.BarraTinta(0.13, 0.017, tono=estilo.ESTADO_AVISO, parent=self, position=(x_barra - 0.02, y_fila))
            barra.z = -0.04
            rot = ui.texto(self, "", 17, 0.27, TONO_TEXTO_SUAVE, (x_barra + 0.065, y_fila + 0.013))
            fila.enabled = barra.enabled = rot.enabled = False
            filas.append(fila)
            barras.append(barra)
            rotulos.append(rot)
        # El cronómetro va en la fila de debajo del mapa, a la derecha de la leyenda (arriba no cabe: la cabecera ocupa hasta 0,31).
        y_pie = self.leyenda_raiz.y
        cronometro = pz.Cronometro(0.30, 0.04, parent=self, position=(X_MAPA + MAPA_ANCHO / 2 - 0.15, y_pie))
        peligro = pz.LineaPeligro(0.52, 0.022, "LLEGÓ AL BARRIO", parent=self, position=(x, pc.Y_LINEA_ROJA))
        frenar = pz.pulsador_sello("FRENA (F)", self.frenar, ANCHO_BOTON, ALTO_BOTON, 20, (x, Y_FRENAR), self, "frenar")
        pasar = pz.pulsador_sello("DEJA PASAR (D)", self.dejar, ANCHO_BOTON, ALTO_BOTON, 19, (x, Y_PASAR), self, "pasar")
        # Todo listo: se sustituye lo de la vista base (mismos nombres, mismo contrato).
        for viejo in list(self.filas) + list(self.barras) + list(self.rotulos) + [self.boton_frenar, self.boton_pasar]:
            viejo.enabled = False
            viejo.visible = False
            try:
                from ursina import destroy
                destroy(viejo)
            except Exception:           # noqa: BLE001
                pass
        self.filas, self.barras, self.rotulos = filas, barras, rotulos
        self.boton_frenar, self.boton_pasar = frenar, pasar
        for e in (self.tiempo_txt, self.barra_tiempo, self.nota, self.pie):
            e.enabled = False          # el pie largo de teclas sobra aquí: los botones ya dicen F y D
        self.cronometro, self.linea_roja = cronometro, peligro
        self._sincronizar()

    def _sincronizar(self):
        super()._sincronizar()
        if getattr(self, "cronometro", None) is None or self._mapa_roto:
            return
        p = self.partida
        self.cronometro.fijar(pc.fraccion_restante(p.t, p.duracion))
        for i, c in enumerate(p.cartas):
            if c["estado"] != PENDIENTE and not self.terminado:
                self.rotulos[i].text = ""

    def _quitar_mapa(self):
        self._mapa_roto = True
        mapa = getattr(self, "mapa", None)
        if mapa is not None:
            mapa.enabled = False
        enlace = getattr(self, "enlace", None)
        if enlace is not None:
            enlace.enabled = False
        self._parar_musica()

    # -- Decisiones: sello al frenar --

    def frenar(self):
        i = self.foco
        estaba = self.partida.cartas[i]["estado"] if 0 <= i < len(self.partida.cartas) else None
        f = self.partida.propagacion(i) if estaba == PENDIENTE else None
        super().frenar()
        if estaba == PENDIENTE and self.partida.cartas[i]["estado"] == FRENADA and not self._mapa_roto:
            self._congelada[i] = f
            if self.terminado:
                return          # era la última: el cierre ya puso «BIEN» / «MAL» en cada papel, no hay sello que estampar
            self._t_sellos[i] = 0.0
            self.sellos[i] = self.filas[i].poner_sello("FRENADA", 0.0 if self._reducir() else -8.0)
            if self._fx is not None:
                self._vigilar(self._fx.pulso, self.filas[i])

    def dejar(self):
        i = self.foco
        super().dejar()
        if 0 <= i < len(self.filas) and self._fx is not None and self.partida.cartas[i]["estado"] == LIBERADA:
            self._vigilar(self._fx.pulso, self.filas[i])

    def posicion_sello(self):
        # El rumor de esta vista llega casi hasta el borde derecho: el sello del veredicto va más a la derecha y arriba.
        x, y = super().posicion_sello()
        return (x + 0.04, y + 0.015)

    def escala_sello(self):
        return min(super().escala_sello(), 0.5)

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

    def _reducir(self):
        return self._fx.reducir if self._fx is not None else bv.reducir_movimiento()

    def _pintar_mapa(self, dt):
        p = self.partida
        reducir = self._reducir()
        self._t_vis += dt
        enlazado = False
        for i, c in enumerate(p.cartas):
            visible = p.visible(i) or self.terminado
            for e in (self.focos[i], self.bordes[i], self.numeros[i]):
                e.enabled = visible
            if not visible:
                self.halos[i].enabled = False
                continue
            estado = c["estado"]
            objetivo = calc.radio_objetivo(estado, p.propagacion(i), self._congelada.get(i))
            actual = self._radio[i]
            self._radio[i] = objetivo if reducir else fx_calc.acercar(actual, objetivo, dt, 0.18)
            radio = self._radio_visible(i, self._radio[i])
            self.focos[i].scale = lad.cuantizar_radio(radio)
            congelada = estado == FRENADA
            self.bordes[i].fijar(radio, GROSOR_BORDE * (1.7 if congelada else 1.0))
            if estado == PENDIENTE:
                f = p.propagacion(i)
                tono = TONO_VIRAL if f > 0.72 else TONO_PENDIENTE
            elif estado == FRENADA:
                tono = TONO_FRENADA
            elif estado == LIBERADA:
                tono = TONO_LIBERADA
            else:
                tono = TONO_VIRAL
            alfa = ALFA_MANCHA
            if estado == LIBERADA and not reducir:
                alfa = ALFA_MANCHA - 0.08 + 0.12 * calc.brillo(self._t_vis, 1.1)
            self.focos[i].color = _rgba(tono, alfa)
            enfocado = estado == PENDIENTE and i == self.foco and not self.terminado
            self.halos[i].enabled = enfocado
            if enfocado:
                # Aro amarillo exterior que pulsa (quieto con «reducir movimiento»), sobre el borde de tinta.
                self.halos[i].fijar(radio + 0.012, 0.006)
                self.halos[i].color = _rgba(estilo.COLOR_ACENTO, 1.0 if reducir else 0.6 + 0.4 * calc.brillo(self._t_vis))
                if not enlazado:
                    enlazado = True
                    self.enlace.fijar(self._borde_tarjeta(i), self._a_mapa(*calc.posicion_foco(i)))
            sello = self.sellos[i]
            if sello is not None and i in self._t_sellos:
                self._t_sellos[i] += dt
                escala, alfa_sello, _ = fx_calc.caida_sello(self._t_sellos[i], reducir=reducir)
                sello.fijar(escala, alfa_sello)
                if self._t_sellos[i] > fx_calc.DUR_SELLO:
                    del self._t_sellos[i]
        if not enlazado:
            self.enlace.esconder()

    def _borde_tarjeta(self, i):
        """Punto del borde izquierdo de la tarjeta i, de donde sale el enlace hacia su zona del mapa."""
        fila = self.filas[i]
        return fila.x - fila.ancho / 2 - 0.004, fila.y

    def _radio_visible(self, i, radio):
        """Radio en unidades de pantalla (un 40 % menor que el lógico), recortado para no salirse del mapa."""
        x, y = calc.posicion_foco(i)
        return lad.radio_visible(radio, x, y, MAPA_ANCHO, MAPA_ALTO)

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
            acierto = p.acierta(i)
            try:
                self.filas[i].marcar(acierto)
            except Exception:            # noqa: BLE001
                pass
        contagiadas = calc.zonas_contagiadas(focos)
        for z, rotulo in enumerate(self.rotulos_zona):
            cx, cy = self._centro_zona(z)
            ex, ey = lad.etiqueta_de_zona(z, cx, cy)
            x_marca = ex + self._ancho_nombre[z] / 2 + 0.022
            if z in contagiadas:
                self.teñidos[z].enabled = True          # mancha roja detrás de las casas, además del aspa
                pz.icono_aspa(self.mapa, 0.03, pz.ROJO_TINTA, (x_marca, ey), z=-0.004)
            else:
                pz.icono_palomita(self.mapa, 0.03, pz.VERDE, (x_marca, ey), z=-0.004)
        # Los botones, el cronómetro, el enlace, la línea de peligro y la leyenda ya no sirven: se esconden.
        self.boton_frenar.enabled = self.boton_pasar.enabled = False
        self.cronometro.enabled = False
        self.linea_roja.enabled = False
        self.leyenda_raiz.enabled = False
        self.enlace.esconder()
        for h in self.halos:
            h.enabled = False
        from ursina import destroy
        for i, sello in enumerate(self.sellos):
            if sello is not None:                 # al final mandan «BIEN» / «MAL» y la palomita o el aspa de cada papel
                sello.enabled = False
                destroy(sello)
                self.sellos[i] = None
                self.filas[i].sello = None
        self._cierre(len(contagiadas))

    def _cierre(self, n_contagiadas):
        """Veredicto del barrio y mensaje DENTRO de la cinta de noticias (debajo de las tarjetas), no sobre el mapa. Deja libre
        el pie de la pantalla para el banner de resultado de la escena."""
        texto = calc.texto_contagio(n_contagiadas)
        alto_aprox = ui.alto_de(2, PX_LEYENDA) + ui.alto_de(1, 19) + 0.016
        y_ultima = min(f.y - f.alto / 2 for f in self.filas)
        y = y_ultima - 0.006 - alto_aprox / 2
        self.cierre, _ = pz.tarjeta_cierre(self, 0.52, n_contagiadas == 0, texto, PX_LEYENDA, (pc.X_CINTA, y))

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
