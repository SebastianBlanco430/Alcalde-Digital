# «Comparar dos versiones» en 3D (familia mesa): cuarto con la luz del techo APAGADA, dos papeles impresos sobre la mesa
# de madera (izquierda el ORIGINAL, derecha la COPIA que circula) y el protagonista de pie en la esquina con el CELULAR y
# la linterna encendida. Solo se lee lo que cae dentro del haz (mesa_piezas.ShaderLinterna sobre papel, texto y madera).
#
# El minijuego ES la vista 2D de hoy (MinijuegoComparar / CompararVisual), viva y sin dibujar: el texto de las filas sale
# de su partida (`partida.lineas`), el clic en una fila de la copia es el clic en su tarjeta (raton.vincular), las teclas
# llegan como siempre y los botones de abajo llaman a los de la vista. El 3D solo refleja (foco, marcadas, cierre) y anima.
#
# El haz: sigue al puntero sobre la mesa (rayo del ratón -> plano de la mesa); con el mando, el palo DERECHO
# (raton.CursorMando); con el teclado, va solo a la fila con el foco y alterna copia / original (mesa_calculos.Haz).
# Bandera: ALCALDE_3D_COMPARAR (y la general ALCALDE_MINIJUEGOS_3D). Cualquier fallo -> la escena cae al 2D de hoy.

from ursina import Entity, scene

from frontend import estilo, sello_marca_agua
from frontend.componentes import destruir_arbol, rgb
from frontend.minijuegos import ui as ui_2d
from frontend.minijuegos_3d import mesa_calculos as mc
from frontend.minijuegos_3d import mesa_piezas as mp
from frontend.minijuegos_3d import papel_3d, raton, sonidos
from frontend.minijuegos_3d.base import Minijuego3D

PAPEL_VIEJO = (236, 224, 190)
ALTO_CABECERA_LETRA = 0.026
AMARILLO = (255, 214, 60)
ROJO = estilo.ESTADO_ERROR
VERDE = estilo.ESTADO_EXITO
TECLAS_FOCO = ("up arrow", "down arrow", "left arrow", "right arrow", "tab", "shift+tab", "enter", "space", "return")
ALTO_ETIQUETA = 0.030                 # etiquetas de las marcas y del cierre (>= 14 px a 720p)
FRAMES_REVISION_SHADER = 20
LADO = "i"                    # el celular en la mano IZQUIERDA (la de fuera): el brazo no se mete delante de los papeles


class Comparar3D(Minijuego3D):

    FAMILIA = "mesa"
    DIBUJAR_VISTA_2D = False
    MOSTRAR_AYUDA = True

    # -- Composición --

    def _colocar_personaje(self):
        x, z, rumbo = mc.PIE_MESA
        self.set.pie = (x, z, rumbo)          # esquina cercana izquierda: no tapa los papeles (ver mesa_calculos)
        super()._colocar_personaje()

    # Entrada animada (sesión B): toma abierta desde la esquina derecha del lado de la puerta (se le ve llegar por la
    # izquierda, sacar la silla y sentarse) que sube hasta la toma cenital de juego. Con la toma de juego retrocedida
    # (la del módulo) la cámara quedaba encima de su cabeza mientras caminaba (capturas m3_cmp2_per).
    TOMA_ESTABLECIMIENTO = {"position": (0.9, 1.9, -1.9), "target": (-0.45, 0.85, 0.0), "fov": 55.0}
    PARTIDA_ENTRADA = (-1.45, -0.55, 90.0)

    def toma_establecimiento(self):
        return dict(self.TOMA_ESTABLECIMIENTO)

    def partida_entrada(self):
        return self.PARTIDA_ENTRADA

    def toma_juego(self):
        t = mc.TOMA_COMPARAR
        objetivo = self.set.anclas["mesa"].mundo(t["objetivo"][0], t["objetivo"][1], 0)
        return mc.toma_mesa(objetivo, t["inclinacion"], t["rumbo"], t["distancia"], t["fov"], techo=self.set.techo)

    # -- Construcción --

    def construir(self):
        mj = self.minijuego
        mesa = self.mesa = self.set.anclas["mesa"]
        self.set.luz_techo(False)
        self.mesa_y = mesa.datos_toma()["centro"][1]
        self.raiz_luz = Entity(parent=mesa.entidad, name="comparar_linterna")
        self.linterna = mp.ShaderLinterna(self.raiz_luz)
        mp.tablero(mesa, self.raiz_luz)
        lineas = mj.partida.lineas
        caso = getattr(mj, "caso", None) or {}
        ancho = mc.ANCHO_HOJA
        ancho_texto = ancho * 0.88
        cab = ("ORIGINAL: " + str(caso.get("original", "")), "COPIA QUE CIRCULA: " + str(caso.get("copia", "")))
        n_cab = max(mp.n_lineas(c, ALTO_CABECERA_LETRA, ancho_texto, True) for c in cab)
        alto_cab = n_cab * ALTO_CABECERA_LETRA * mc.LINEA + 0.02
        rep = mc.filas_comparar(lineas, mp.n_lineas, ancho_texto, mc.ALTO_LINEA, alto_cab)
        self.rep = rep
        alto = rep["alto_hoja"]
        xa, xb = mc.x_hojas(ancho)
        self.hojas = [papel_3d.papel(self.raiz_luz, ancho, alto, posicion=(xa, mc.Y_HOJAS), giro=-0.8, iluminado=False),
                      papel_3d.papel(self.raiz_luz, ancho, alto, posicion=(xb, mc.Y_HOJAS), giro=0.7, tono=PAPEL_VIEJO,
                                     capa=1, iluminado=False)]
        # Marca de agua del sello de la Tradición en la copia que circula si el rumor lo lleva (hilo conductor).
        sello_marca_agua.poner_en_papel(self.hojas[1], getattr(self.ctx, "mision", None))
        y_arriba = alto / 2 - mc.MARGEN_HOJA
        x0 = -ancho_texto / 2
        self.cabeceras = []
        for h, c, tono in zip(self.hojas, cab, (estilo.COLOR_TEXTO_TENUE, ROJO)):
            self.cabeceras.append(mp.ShaderLinterna.impreso(papel_3d.texto_en_papel(
                h, c, alto_linea=ALTO_CABECERA_LETRA, ancho=ancho_texto, posicion=(x0, y_arriba), negrita=True,
                tono=estilo.tono_legible(tono, PAPEL_VIEJO))))
        y_filas = y_arriba - alto_cab
        self.textos, self.filas, self.golpes, self.anchos = [], [], [], []
        for k, (ta, tb) in enumerate(rep["textos"]):
            yc = y_filas + rep["centros"][k]
            ys = yc + rep["altos"][k] / 2 - mc.MARGEN_FILA
            fila = []
            for h, t in zip(self.hojas, (ta, tb)):
                texto = papel_3d.texto_en_papel(h, t, alto_linea=mc.ALTO_LINEA, ancho=ancho_texto, posicion=(x0, ys))
                mp.ShaderLinterna.impreso(texto)            # fuera del haz no se distingue
                self.textos.append(texto)
                self.anchos.append(mp.ancho_mayor(t, mc.ALTO_LINEA, ancho_texto))
                fila.append(Entity(parent=h, position=(0, yc, 0)))          # centro de la fila (para el haz y las marcas)
                if k < len(rep["textos"]) - 1:
                    mp.ShaderLinterna.impreso(Entity(parent=h, model="quad", position=(0, yc - rep["altos"][k] / 2, -0.0008),
                                                     scale=(ancho - 0.06, 0.0015), color=rgb(papel_3d.TINTA)))
            self.filas.append(fila)
            # clic en la fila de la COPIA = clic en su tarjeta de la vista 2D (el hover le da el foco, como en 2D)
            golpe = Entity(parent=self.hojas[1], model="quad", position=(0, yc, -0.003), scale=(ancho, rep["altos"][k]),
                           collider="box", visible=False)
            raton.vincular(golpe, mj.tarjetas[k].golpe)
            self.golpes.append(golpe)
        self.radio = mc.radio_haz(self.anchos)
        # marcas que se ven aunque estén fuera del haz (sin luz)
        self.foco_marca = [mp.plano(h, (0.012, 0.05), AMARILLO, (ancho / 2 - 0.014, 0, -0.0026)) for h in self.hojas]
        self.marcas = {}
        self.cierre = []
        d = mesa.datos_toma()
        self.poses.limitar(d["centro"], d["normal"])
        # haz: empieza en el centro de la copia; límites = la zona de las hojas (y un poco más)
        x_min, x_max = xa - ancho / 2 - 0.05, xb + ancho / 2 + 0.05
        y_min, y_max = mc.Y_HOJAS - alto / 2 - 0.05, mc.Y_HOJAS + alto / 2 + 0.05
        self.haz = mc.Haz((xb, mc.Y_HOJAS), (x_min, x_max, y_min, y_max))
        self.cursor = raton.CursorMando(mesa.entidad, (x_min, x_max, y_min, y_max), (xb, mc.Y_HOJAS))
        self._ultimo_cursor = None
        self.celular = mp.Celular(self.set.raiz)
        self.cono = mp.Cono(self.set.raiz)
        self.celular.enabled = self.cono.enabled = False
        self._frames_shader = 0
        self._marcadas_vistas = set()
        self._botones = None
        self._sin_shader_visto = False

    # -- Capa en pantalla: rumor arriba y los dos botones de la vista 2D abajo --

    def _montar_capa(self):
        if self.capa is None or self._botones is not None:
            return
        mj = self.minijuego
        rumor = getattr(getattr(mj, "mision", None), "rumor", "") or (getattr(mj, "caso", None) or {}).get("intro", "")
        if rumor:
            ancho = 1.62
            texto = f"{mj.TITULO}. Rumor a verificar: «{rumor}»"
            n = len(ui_2d.lineas_de(texto, 17, ancho))
            alto = ui_2d.alto_de(n, 17)
            from ursina import color as _c
            Entity(parent=self.capa, model="quad", color=_c.rgba32(14, 16, 26, 170), scale=(4, alto + 0.03),
                   y=0.5 - (alto + 0.03) / 2, z=0.01)
            self.rumor = ui_2d.texto(self.capa, texto, 17, ancho, estilo.COLOR_TEXTO, (-ancho / 2, 0.5 - 0.015))
        conf = ui_2d.Boton(self._etiqueta(mj.boton_confirmar), lambda: self._pulsar("boton_confirmar"), 0.40, 0.075, 18,
                           primario=True, parent=self.capa, position=(0.2, -0.39, -0.01))
        clase = getattr(ui_2d, "BotonTinta", ui_2d.Boton)
        igual = clase(self._etiqueta(mj.boton_igual), lambda: self._pulsar("boton_igual"), 0.40, 0.075, 18,
                      parent=self.capa, position=(0.64, -0.39, -0.01))
        self._botones = {"boton_confirmar": conf, "boton_igual": igual}

    @staticmethod
    def _etiqueta(boton):
        return getattr(boton, "_etiqueta", "") or getattr(getattr(boton, "texto", None), "text", "")

    def _pulsar(self, nombre):
        """El botón en pantalla = el botón de la vista 2D (mismo _clic: misma comprobación y misma acción)."""
        boton = getattr(self.minijuego, nombre, None)
        if boton is not None:
            boton._clic()

    def _reflejar_botones(self):
        mj = self.minijuego
        indice = {"boton_confirmar": None, "boton_igual": None}
        for nombre in indice:
            b = getattr(mj, nombre, None)
            if b in mj.focables:
                indice[nombre] = mj.focables.index(b)
        for nombre, propio in self._botones.items():
            b = getattr(mj, nombre, None)
            if b is None:
                continue
            foco = indice[nombre] is not None and mj.foco == indice[nombre] and not mj.terminado
            habil = bool(getattr(b, "habilitado", True))
            if propio._foco != foco or propio.habilitado != habil or propio._etiqueta != self._etiqueta(b):
                propio.habilitado = habil
                propio._etiqueta = self._etiqueta(b)
                propio.fijar_foco(foco)

    # -- Cada frame --

    def avanzar_3d(self, dt):
        self._revisar_shader()
        self._montar_capa()
        if self._botones is not None and self.resultado_3d is None:
            self._reflejar_botones()
        mj = self.minijuego
        if self.resultado_3d is None:
            self._mover_haz(dt)
        self._reflejar_marcas()
        # foco (amarillo, se ve en la penumbra) en la fila con el foco, en las dos hojas
        f = mj.foco if (not mj.terminado and mj.focables and mj.foco < len(self.filas)) else None
        for i, m in enumerate(self.foco_marca):
            m.enabled = f is not None
            if f is not None:
                m.y = self.filas[f][i].y

    def _revisar_shader(self):
        self._frames_shader += 1
        if self._frames_shader == FRAMES_REVISION_SHADER and self.linterna.roto():
            raise RuntimeError("el shader de la linterna no compiló: se sigue en 2D")

    def _mover_haz(self, dt):
        c = self.cursor.avanzar(dt)
        libre = c if (self._ultimo_cursor is not None and mc.se_movio(c, self._ultimo_cursor)) else None
        self._ultimo_cursor = c
        hx, hy = self.haz.avanzar(dt, libre)
        if self.haz.modo == "teclado":
            self.cursor.x, self.cursor.y = hx, hy               # el palo sigue desde donde está el haz
            self._ultimo_cursor = (hx, hy)
        centro = self.mesa.mundo(hx, hy, 0)
        self.linterna.poner((centro[0], centro[2]), self.radio)
        self.centro_haz = (hx, hy)
        if not self.listo:
            return
        p = self.set.personaje
        base = tuple(p.world_position)
        # sentado (sesión B, ALCALDE_ANIM_SILLA) el hombro baja lo que bajó la pelvis (cuerpo.y < 0)
        bajada = float(getattr(getattr(p, "cuerpo", None), "y", 0.0) or 0.0) if self.poses.sentado else 0.0
        hombro = mc.hombro_estimado(base, getattr(p, "rumbo", 0.0), LADO, alto=1.40 + min(0.0, bajada))
        objetivo = mc.mano_pecho(hombro, getattr(p, "rumbo", 0.0), centro, self.mesa_y)
        if not mc.finito(objetivo):
            return
        self.poses.mano_a(objetivo, LADO)
        mano = self._mano_real() or objetivo
        # el celular en la palma: unos cm de la muñeca hacia lo que alumbra
        d = [centro[i] - mano[i] for i in range(3)]
        n = max(1e-6, sum(c * c for c in d) ** 0.5)
        mano = tuple(mano[i] + d[i] / n * 0.06 for i in range(3))
        self.celular.enabled = self.cono.enabled = True
        self.celular.colocar(mano, centro)
        self.cono.apuntar(self.celular.punta(), centro, self.radio)

    def _mano_real(self):
        try:
            n = self.set.personaje.mano(LADO)
            if n is None:
                return None
            q = n.getPos(scene)
            q = (q[0], q[1], q[2])
            return q if mc.finito(q) else None
        except Exception:                # noqa: BLE001  sin esqueleto: la mano objetivo
            return None

    def _centro_fila_local(self, k, hoja):
        p = self.filas[k][hoja].world_position
        x, y, _ = self.mesa.local((p[0], p[1], p[2]))
        return (x, y)

    def al_tecla(self, k):
        mj = self.minijuego
        if k in TECLAS_FOCO and not mj.terminado and mj.foco < len(self.filas):
            self.haz.teclado([self._centro_fila_local(mj.foco, 1), self._centro_fila_local(mj.foco, 0)])

    def _reflejar_marcas(self):
        marcadas = set(getattr(self.minijuego.partida, "marcadas", ()))
        if marcadas == self._marcadas_vistas or self.resultado_3d is not None:
            return
        for k in marcadas - self._marcadas_vistas:
            t = self.minijuego.tarjetas[k]
            texto = str(getattr(getattr(t, "etiqueta", None), "text", "") or "")
            self.marcas[k] = self._marca(k, ROJO, texto if texto and not texto.startswith(">>") else "SOSPECHOSA")
            sonidos.sonar("papel")
        for k in self._marcadas_vistas - marcadas:
            m = self.marcas.pop(k, None)
            if m is not None:
                destruir_arbol(m)
        self._marcadas_vistas = marcadas

    def _marca(self, k, tono, texto, aro=None):
        """Marca de la fila k de la copia: barra en el borde derecho y etiqueta al lado (sin luz: se ve en la penumbra)."""
        h = self.hojas[1]
        fila = self.filas[k][1]
        alto = self.rep["altos"][k]
        raiz = Entity(parent=h, position=(0, fila.y, 0))
        mp.plano(raiz, (0.014, alto - 0.012), tono, (-h.ancho / 2, 0, -0.0026))      # medio sobre el papel
        ancho_et = mc.SEPARACION_HOJAS - 0.03
        alto_et = mp.alto_que_cabe(texto, ALTO_ETIQUETA, 0.024, ancho_et, True)    # solo se parte por palabras
        lineas = mp.n_lineas(texto, alto_et, ancho_et, True)
        etiqueta = papel_3d.texto_en_papel(h, texto, alto_linea=alto_et, ancho=ancho_et, tono=tono, negrita=True,
                                           posicion=(-h.ancho / 2 - 0.012 - ancho_et,
                                                     fila.y + lineas * alto_et * mc.LINEA / 2))
        etiqueta.parent = raiz
        etiqueta.y -= fila.y
        mp.sin_luz(etiqueta)
        if aro is not None:
            mp.aro(raiz, h.ancho / 2 - 0.01, alto / 2, tono, posicion=(0, 0, -0.0027), discontinuo=aro == "discontinuo")
        return raiz

    # -- Cierre --

    def al_resultado(self, resultado):
        self.set.luz_techo(True)                 # la revisión se lee con la luz encendida
        self.poses.soltar_mano(LADO)
        self.linterna.luz_plena()
        self.celular.enabled = self.cono.enabled = False
        for b in (self._botones or {}).values():
            b.enabled = False
        for m in list(self.marcas.values()):
            destruir_arbol(m)
        self.marcas = {}
        estilos = {"encontrada": (VERDE, "continuo"), "perdida": (ROJO, "discontinuo"), "falsa_alarma": (ROJO, None)}
        for k, t in enumerate(self.minijuego.tarjetas):
            estado = getattr(t, "estado", "normal")
            if estado in estilos:
                tono, aro = estilos[estado]
                texto = getattr(getattr(t, "etiqueta", None), "text", "") or estado.upper()
                self.cierre.append(self._marca(k, tono, texto, aro))
        for m in self.foco_marca:
            m.enabled = False

    def destruir(self):
        raton.desvincular()


CLASE_3D = Comparar3D
