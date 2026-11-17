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
from frontend.minijuegos.contrarreloj import MinijuegoContrarreloj
from frontend.minijuegos.contrarreloj_calculos import FRENADA, LIBERADA, PENDIENTE, PROPAGADA
from frontend.minijuegos_visual import contrarreloj_piezas_calculos as pc
from frontend.minijuegos_visual import mapa_barrio_calculos as calc
from frontend.minijuegos_visual import piezas_contrarreloj as pz
from frontend.minijuegos_visual.capa import CapaVisual

CONTRARRELOJ_VISUAL = True
VARIABLE = "ALCALDE_CONTRARRELOJ_VISUAL"

# Mesa del barrio: ~60 % del ancho, a la izquierda. Cinta de noticias a la derecha.
MAPA_ANCHO, MAPA_ALTO = 1.10, 0.74
X_MAPA, MAPA_Y = -0.29, -0.005
ANCHO_TARJETA = 0.46
Y_FRENAR, Y_PASAR = -0.315, -0.41
ANCHO_BOTON, ALTO_BOTON = 0.40, 0.08
RADIO_VISIBLE_MAX = 0.17       # tope del círculo en pantalla (que no tape el mapa entero)
PX_LEYENDA = 14
ALFA_CONTAGIO = 0.40            # relleno rojo de las zonas contagiadas al final
MUSICA = "musica_tensa"
VOLUMEN_MUSICA = 0.28

TONO_PENDIENTE = (240, 160, 60)
TONO_VIRAL = (214, 62, 62)
TONO_FRENADA = (60, 110, 200)
TONO_LIBERADA = (80, 190, 110)
TONO_TEXTO_SUAVE = (70, 66, 58)
# Manzanas de la mesa: (x0, x1, y0, y1) en coordenadas normalizadas; entre ellas quedan las calles.
MANZANAS = tuple((x0, x1, y0, y1) for (x0, x1) in ((-0.48, -0.19), (-0.15, 0.16), (0.20, 0.48))
                 for (y0, y1) in ((0.14, 0.48), (-0.10, 0.10), (-0.48, -0.14)))


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

    def _manzana_de(self, zx, zy):
        """Rectángulo (oculto) que cubre la manzana donde está la zona; se enciende en rojo si queda contagiada."""
        for x0, x1, y0, y1 in MANZANAS:
            if x0 <= zx <= x1 and y0 <= zy <= y1:
                cx, cy = self._a_mapa((x0 + x1) / 2, (y0 + y1) / 2)
                return ui.rect(self.mapa, (x1 - x0) * MAPA_ANCHO, (y1 - y0) * MAPA_ALTO, _rgba(TONO_VIRAL, ALFA_CONTAGIO),
                               (cx, cy), z=0.004, radio_px=4)
        return None

    def _casa(self, x, y):
        """Casita dibujada con primitivas: pared de papel con borde de tinta y tejado en rombo."""
        ui.rect(self.mapa, 0.036, 0.028, estilo.TINTA, (x, y), z=0.0032, radio_px=2)
        ui.rect(self.mapa, 0.031, 0.023, pz.PAPEL_SOMBRA, (x, y), z=0.0031, radio_px=2)
        Entity(parent=self.mapa, model="quad", color=_rgba(estilo.TINTA, 1), scale=0.026, rotation_z=45,
               position=(x, y + 0.02, 0.0033))

    def _construir_mapa(self):
        self.x_mapa = X_MAPA
        self.mapa = Entity(parent=self)
        pz.sombra_plana(self.mapa, MAPA_ANCHO, MAPA_ALTO, (X_MAPA, MAPA_Y), z=0.0075, radio_px=10)
        ui.rect(self.mapa, MAPA_ANCHO + 0.008, MAPA_ALTO + 0.008, estilo.TINTA, (X_MAPA, MAPA_Y), z=0.0065, radio_px=10)
        ui.rect(self.mapa, MAPA_ANCHO, MAPA_ALTO, pz.PAPEL_VIEJO, (X_MAPA, MAPA_Y), z=0.005, radio_px=9)
        # Manzanas de papel; lo que queda entre ellas son las calles.
        for x0, x1, y0, y1 in MANZANAS:
            cx, cy = self._a_mapa((x0 + x1) / 2, (y0 + y1) / 2)
            ui.rect(self.mapa, (x1 - x0) * MAPA_ANCHO, (y1 - y0) * MAPA_ALTO, pz.PAPEL, (cx, cy), z=0.0045, radio_px=4)
        # Zonas: casas + punto + nombre (al final se marcan las contagiadas).
        self.zonas, self.iconos_zona, self.teñidos = [], [], []
        for nombre, zx, zy in calc.ZONAS:
            cx, cy = self._a_mapa(zx, zy)
            # Relleno rojo de la manzana de la zona: apagado hasta el final (solo si queda contagiada).
            teñido = self._manzana_de(zx, zy)
            if teñido is not None:
                teñido.enabled = False
            self.teñidos.append(teñido)
            for dx in (-0.05, 0.0, 0.05):
                self._casa(cx + dx, cy - 0.034 - (0.012 if dx == 0 else 0.0))
            punto = Entity(parent=self.mapa, model="circle", scale=0.012, color=_rgba(estilo.TINTA, 0.9),
                           position=(cx, cy + 0.012, 0.002))
            rotulo = Text(nombre, parent=self.mapa, origin=(0, -0.9), position=(cx, cy + 0.016, 0.001),
                          scale=escala_fuente(13), font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            self.zonas.append((punto, rotulo))
        self.leyenda = ui.texto(self.mapa, "Cada mancha es una noticia que se difunde por el barrio", PX_LEYENDA,
                                MAPA_ANCHO, estilo.COLOR_TEXTO_TENUE, (X_MAPA - MAPA_ANCHO / 2, MAPA_Y - MAPA_ALTO / 2 - 0.008))
        # Un foco por noticia: aro (detrás), mancha y número.
        self.focos, self.halos, self.numeros, self.sellos = [], [], [], []
        for i, fila in enumerate(self.filas):
            cx, cy = self._a_mapa(*calc.posicion_foco(i))
            halo = Entity(parent=self.mapa, model="circle", color=_rgba(estilo.COLOR_ACENTO, 0), position=(cx, cy, 0.0015))
            foco = Entity(parent=self.mapa, model="circle", color=_rgba(TONO_PENDIENTE, 0.45), position=(cx, cy, 0.001))
            numero = Text(str(i + 1), parent=self.mapa, origin=(0, 0), position=(cx, cy, -0.002), scale=escala_fuente(15),
                          font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA, 1))
            sello = Text("FRENADA", parent=self.mapa, origin=(0, 0), position=(cx, cy - 0.03, -0.003), rotation_z=-12,
                         scale=escala_fuente(14), font=tipografia.FUENTE_TITULO, color=_rgba(TONO_FRENADA, 1), enabled=False)
            for e in (halo, foco, numero):
                e.enabled = False
            self.focos.append(foco)
            self.halos.append(halo)
            self.numeros.append(numero)
            self.sellos.append(sello)
            self._radio[i] = calc.RADIO_MIN
        self.enlace = pz.LineaDiscontinua(parent=self, z=-0.02)
        self._cinta_y_botones()

    def _cinta_y_botones(self):
        """Cinta de teletipo a la derecha (tarjetas de papel con barra), línea roja, cronómetro y botones apilados.
        Se construye entera antes de sustituir lo de la vista base, así un fallo a medias no deja nada roto."""
        n = len(self.partida.cartas)
        alto, ys = pc.huecos_cinta(n)
        x = pc.X_CINTA
        filas, barras, rotulos = [], [], []
        for i, c in enumerate(self.partida.cartas):
            fila = pz.TarjetaTitular(ANCHO_TARJETA, alto, c["texto"], i + 1, parent=self, position=(x, ys[i]),
                                     al_clic=lambda i=i: self.poner_foco(i), al_cursor=None)
            fila.golpe.z = -0.001
            y_fila = ys[i] - alto / 2 + 0.017
            barra = ui.Barra(0.15, 0.014, tono=estilo.ESTADO_AVISO, parent=self,
                             position=(x - ANCHO_TARJETA / 2 + 0.09, y_fila))
            barra.z = -0.04
            rot = ui.texto(self, "", 13, 0.2, TONO_TEXTO_SUAVE, (x - ANCHO_TARJETA / 2 + 0.175, y_fila + 0.009))
            fila.enabled = barra.enabled = rot.enabled = False
            filas.append(fila)
            barras.append(barra)
            rotulos.append(rot)
        cronometro = pz.Cronometro(0.52, 0.04, parent=self, position=(x, 0.345))
        linea = Entity(parent=self, model="quad", color=_rgba(pz.ROJO, 1), scale=(0.52, 0.006), position=(x, pc.Y_LINEA_ROJA, 0.0))
        rotulo_linea = Text("LLEGÓ AL BARRIO", parent=self, origin=(0, 0.5), position=(x, pc.Y_LINEA_ROJA - 0.007, 0.0),
                            scale=escala_fuente(13), font=tipografia.FUENTE_TITULO, color=_rgba((255, 150, 150), 1))
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
        self.cronometro, self.linea_roja, self.rotulo_linea = cronometro, linea, rotulo_linea
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
        enlazado = False
        for i, c in enumerate(p.cartas):
            visible = p.visible(i) or self.terminado
            for e in (self.focos[i], self.numeros[i]):
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
                alfa = 0.40 + 0.25 * f
            elif estado == FRENADA:
                tono, alfa = TONO_FRENADA, 0.55
            elif estado == LIBERADA:
                tono = TONO_LIBERADA
                alfa = 0.40 if reducir else 0.30 + 0.16 * calc.brillo(self._t_vis, 1.1)
            else:
                tono, alfa = TONO_VIRAL, 0.4
            self.focos[i].color = _rgba(tono, alfa)
            enfocado = estado == PENDIENTE and i == self.foco and not self.terminado
            congelada = estado == FRENADA
            self.halos[i].enabled = enfocado or congelada
            if enfocado:
                # El círculo pulsa (quieto con «reducir movimiento»).
                self.halos[i].scale = 2 * radio + 0.018
                self.halos[i].color = _rgba(estilo.COLOR_ACENTO, 0.9 if reducir else 0.5 + 0.4 * calc.brillo(self._t_vis))
                if not enlazado:
                    enlazado = True
                    self.enlace.fijar(self._borde_tarjeta(i), self._a_mapa(*calc.posicion_foco(i)))
            elif congelada:
                self.halos[i].scale = 2 * radio + 0.01          # aro de tinta: el círculo queda congelado
                self.halos[i].color = _rgba(estilo.TINTA, 1.0)
            if i in self._t_sellos:
                self._t_sellos[i] += dt
                escala, alfa_sello, _ = fx_calc.caida_sello(self._t_sellos[i], reducir=reducir)
                self.sellos[i].enabled = True
                self.sellos[i].scale = escala_fuente(14) * escala
                self.sellos[i].color = _rgba(TONO_FRENADA, alfa_sello)
                if self._t_sellos[i] > fx_calc.DUR_SELLO:
                    del self._t_sellos[i]
        if not enlazado:
            self.enlace.esconder()

    def _borde_tarjeta(self, i):
        """Punto del borde izquierdo de la tarjeta i, de donde sale el enlace hacia su zona del mapa."""
        fila = self.filas[i]
        return fila.x - fila.ancho / 2 - 0.004, fila.y

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
            acierto = p.acierta(i)
            try:
                self.filas[i].marcar(acierto)
            except Exception:            # noqa: BLE001
                pass
        contagiadas = calc.zonas_contagiadas(focos)
        for z, (punto, rotulo) in enumerate(self.zonas):
            cx, cy = self._a_mapa(calc.ZONAS[z][1], calc.ZONAS[z][2])
            if z in contagiadas:
                punto.scale = 0.02
                punto.color = _rgba(TONO_VIRAL, 1)
                if self.teñidos[z] is not None:
                    self.teñidos[z].enabled = True          # manzana teñida de rojo (40 %), no solo el punto
                pz.icono_aspa(self.mapa, 0.03, pz.ROJO, (cx + 0.085, cy + 0.035), z=-0.004)
            else:
                punto.color = _rgba(TONO_LIBERADA, 1)
                pz.icono_palomita(self.mapa, 0.03, pz.VERDE, (cx + 0.085, cy + 0.035), z=-0.004)
        self._leyenda_final(len(contagiadas))
        # Los botones ya no sirven (la vista de siempre los deshabilita): se esconden, igual que el cronómetro y el enlace.
        self.boton_frenar.enabled = self.boton_pasar.enabled = False
        self.cronometro.enabled = False
        self.enlace.esconder()
        for h in self.halos:
            h.enabled = False
        if self._fx is not None:
            self._vigilar(self._sello_final, bool(contagiadas))

    def _leyenda_final(self, n_contagiadas):
        """El banner de resultado de la vista base tapa el borde inferior del mapa, donde está la leyenda: el resumen pasa a
        una pastilla oscura sobre la calle central del mapa (siempre visible y con contraste, claro u oscuro el papel)."""
        texto = calc.texto_contagio(n_contagiadas)
        ancho = 0.70
        lineas = ui.lineas_de(texto, PX_LEYENDA + 1, ancho - 0.04)
        alto = ui.alto_de(len(lineas), PX_LEYENDA + 1) + 0.024
        y = MAPA_Y - 0.07
        self.leyenda_fondo = ui.rect(self.mapa, ancho, alto, (22, 24, 38), (X_MAPA, y), z=-0.006, radio_px=8)
        self.leyenda.origin = (0, 0.5)
        self.leyenda.position = (X_MAPA, y + alto / 2 - 0.012, -0.02)
        self.leyenda.text = "\n".join(lineas)
        self.leyenda.scale = escala_fuente(PX_LEYENDA + 1)
        self.leyenda.color = _rgba((255, 150, 150) if n_contagiadas else (150, 230, 170), 1)

    def _sello_final(self, contagiado):
        """Sello grande sobre el mapa: BARRIO A SALVO o BARRIO CONTAGIADO (sustituye al sello común de la capa)."""
        texto = "BARRIO CONTAGIADO" if contagiado else "BARRIO A SALVO"
        self._fx.sello(texto, posicion=(X_MAPA, MAPA_Y + 0.04), tono=pz.ROJO if contagiado else pz.VERDE, retardo=0.5)
        ancho = 0.62
        self._fx._sello_borde.scale = (ancho + 0.02, 0.092)
        self._fx._sello_fondo.scale = (ancho, 0.074)

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
