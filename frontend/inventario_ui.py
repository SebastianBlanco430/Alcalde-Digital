# Panel del inventario (Ursina, camera.ui): modal y centrado. Izquierda, una silueta con un hueco por ranura
# (manos, cintura, bolsillos, espalda y mochila); derecha, la lista de objetos con tamaño y peso; abajo, el
# detalle, el mensaje de la última acción (rojo si es un rechazo) y el pie «Peso · R$ · I cierra».
# Toda la lógica vive en frontend/inventario_calculos.py (ControlInventario); aquí solo se dibuja, y solo
# cuando cambia la firma del contenido. Estilo: estilo.py y componentes.panel_tinta.

from ursina import Entity, Text, color

from frontend import diseno_adaptable, estilo, inventario_calculos as calc, tipografia
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, modelo_redondeado, panel_tinta, rgb

ANCHO, ALTO = 1.14, 0.84
ANCHO_SIL, ALTO_SIL = 0.54, 0.52
CELDA = (0.125, 0.05)
ALTO_PIE = 0.17            # del borde inferior a la línea que separa el detalle
PX = 13                    # tamaño mínimo de texto en el panel
MAX_FILAS = 13
ALTO_FILA = 0.034
GRIS_FANTASMA = (52, 55, 74)


def _texto(padre, cadena, px, tono, pos, origen=(-0.5, 0), negrita=False, z=-0.01):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena.replace("<", "(").replace(">", ")"), parent=padre, origin=origen, position=(pos[0], pos[1], z),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


def _caja(padre, ancho, alto, tono, pos, radio=6, z=0.0):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio), color=rgb(tono) if isinstance(tono, tuple)
                  else tono, scale=(ancho, alto), position=(pos[0], pos[1], z))


class PanelInventario(Entity):

    def __init__(self, control, nombre_fn=None, **opciones):
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self.control = control
        self._nombre_fn = nombre_fn or (lambda: "")
        self._firma = None
        self.marco = panel_tinta(self, ANCHO, ALTO, z=-0.02)
        self.dinamico = Entity(parent=self, z=-0.03)
        self.z = -0.05

    def establecer_control(self, control):
        self.control = control
        self._firma = None

    def abrir(self):
        self.enabled = True
        self._firma = None
        self.redibujar()

    def cerrar(self):
        self.enabled = False

    def actualizar(self):
        if self.enabled:
            self.redibujar()

    # Redibuja solo si cambió algo visible.
    def redibujar(self):
        firma = (self.control.firma(), self._nombre_fn())
        if firma == self._firma:
            return False
        self._firma = firma
        for hijo in list(self.dinamico.children):
            destruir_arbol(hijo)
        self._dibujar()
        return True

    # -- Dibujo --

    def _dibujar(self):
        d, c, inv = self.dinamico, self.control, self.control.inv
        izq, arriba = -ANCHO / 2, ALTO / 2
        _texto(d, "MOCHILA", 24, estilo.COLOR_ACENTO, (izq + 0.03, arriba - 0.04), negrita=True)
        _texto(d, self._nombre_fn(), 16, estilo.COLOR_TEXTO_TENUE, (izq + 0.03 + 0.2, arriba - 0.043))
        _texto(d, "I cierra", 14, estilo.COLOR_TEXTO_TENUE, (ANCHO / 2 - 0.03, arriba - 0.042), origen=(0.5, 0))
        _caja(d, ANCHO - 0.06, 0.003, estilo.COLOR_BARRA_FONDO, (0, arriba - 0.075))
        self._silueta(d, izq + 0.03, arriba - 0.095)
        self._lista(d, izq + 0.03 + ANCHO_SIL + 0.04, arriba - 0.095)
        self._pie(d)

    def _silueta(self, d, x0, y0):
        c, inv = self.control, self.control.inv
        base_y = y0 - ALTO_SIL + 0.025
        def pos(cx, cy):
            return (x0 + cx * ANCHO_SIL, base_y + cy * ALTO_SIL)
        def pieza(cx, cy, w, h, tono, radio=8, z=-0.001):
            x, y = pos(cx, cy)
            _caja(d, w * ANCHO_SIL, h * ALTO_SIL, tono, (x, y), radio, z)
        PIEL, CAMISA, JEAN, CINTURON = (176, 138, 112), (74, 82, 112), (46, 72, 122), (128, 88, 52)
        px, py = pos(0.5, 0.925)
        Entity(parent=d, model="circle", color=rgb(PIEL), scale=(0.07, 0.07), position=(px, py, -0.001))
        pieza(0.5, 0.87, 0.07, 0.04, PIEL, 3)                                    # cuello
        pieza(0.5, 0.72, 0.44, 0.31, CAMISA, 10)                                   # torso
        pieza(0.10, 0.64, 0.17, 0.40, CAMISA, 8)                                   # brazo derecho
        pieza(0.90, 0.64, 0.17, 0.40, CAMISA, 8)                                   # brazo izquierdo
        for cx in (0.10, 0.90):                                                    # manos
            x, y = pos(cx, 0.43)
            Entity(parent=d, model="circle", color=rgb(PIEL), scale=(0.05, 0.05), position=(x, y, -0.001))
        pieza(0.5, 0.40, 0.46, 0.46, JEAN, 6)                                      # pantalón (cadera y muslos)
        pieza(0.33, 0.17, 0.20, 0.17, JEAN, 6)                                     # pierna derecha
        pieza(0.67, 0.17, 0.20, 0.17, JEAN, 6)                                     # pierna izquierda
        pieza(0.5, 0.27, 0.015, 0.20, (30, 48, 86), 2, -0.0015)                     # costura entre las piernas
        pieza(0.5, 0.62, 0.46, 0.045, CINTURON, 3, -0.0015)                        # cinturón
        pieza(0.5, 0.62, 0.05, 0.05, estilo.COLOR_ACENTO, 3, -0.0016)              # hebilla
        for h in calc.huecos(inv):
            self._hueco(d, h, pos(h.celda.x, h.celda.y))

    def _hueco(self, d, h, centro):
        c = self.control
        celda = h.celda
        seleccionado = celda.clave == c.seleccion
        origen = c.origen == celda.clave
        tenue = (128, 132, 158)
        if not celda.activa or celda.bloqueada:
            relleno, borde = GRIS_FANTASMA, (44, 46, 62)
        elif h.item_id is None:
            relleno, borde = estilo.COLOR_FONDO, estilo.COLOR_BARRA_FONDO
        else:
            relleno, borde = estilo.COLOR_SUPERFICIE_ALTA, estilo.COLOR_TEXTO_TENUE
        if seleccionado:
            borde = estilo.COLOR_ACENTO
        elif origen:
            borde = estilo.ACENTO_SECUNDARIO
        g = 0.004 if (seleccionado or origen) else 0.002
        _caja(d, CELDA[0] + 2 * g, CELDA[1] + 2 * g, borde, centro, 6, -0.002)
        _caja(d, CELDA[0], CELDA[1], relleno, centro, 5, -0.003)
        if h.item_id is not None:
            t = _texto(d, h.texto, PX, estilo.COLOR_TEXTO, (centro[0], centro[1]), origen=(0, 0))
            t.line_height = 1.0
            if h.cantidad > 1:
                bx, by = centro[0] + CELDA[0] / 2 - 0.002, centro[1] + CELDA[1] / 2 + 0.002
                _caja(d, 0.034, 0.024, estilo.COLOR_ACENTO, (bx, by), 5, -0.004)
                _texto(d, f"×{h.cantidad}", PX, estilo.COLOR_ACENTO_TEXTO, (bx, by), origen=(0, 0), negrita=True, z=-0.005)
        elif celda.bloqueada:
            _texto(d, "Ocupada", PX, tenue, centro, origen=(0, 0))
        elif not celda.activa:
            if celda.indice == 0:
                _texto(d, "Sin mochila", PX, tenue, centro, origen=(0, 0))
        elif celda.ubicacion == "mochila":
            _texto(d, str(celda.indice + 1), PX, tenue, centro, origen=(0, 0))
        else:
            _texto(d, calc.ETIQUETA_HUECO.get(celda.ubicacion, ""), PX, tenue, centro, origen=(0, 0))

    def _lista(self, d, x0, y0):
        c, inv = self.control, self.control.inv
        ancho = ANCHO / 2 - 0.03 - x0
        _texto(d, "OBJETOS", PX, estilo.COLOR_TEXTO_TENUE, (x0, y0 - 0.012), negrita=True)
        _texto(d, "Tamaño", PX, estilo.COLOR_TEXTO_TENUE, (x0 + ancho - 0.105, y0 - 0.012), origen=(0.5, 0))
        _texto(d, "Peso", PX, estilo.COLOR_TEXTO_TENUE, (x0 + ancho, y0 - 0.012), origen=(0.5, 0))
        y = y0 - 0.04
        filas = calc.filas_lista(inv)
        for fila in filas[:MAX_FILAS]:
            sel = fila.clave == c.seleccion
            if sel:
                _caja(d, ancho + 0.01, ALTO_FILA - 0.003, estilo.COLOR_ACENTO if not c.modo_mover else
                      estilo.ACENTO_SECUNDARIO, (x0 + ancho / 2, y - ALTO_FILA / 2), 5, -0.001)
                _caja(d, ancho + 0.004, ALTO_FILA - 0.009, estilo.COLOR_PANEL, (x0 + ancho / 2, y - ALTO_FILA / 2), 4, -0.002)
            nombre = f"{fila.nombre} ×{fila.cantidad}" if fila.cantidad > 1 else fila.nombre
            t = _texto(d, nombre, 14, estilo.COLOR_TEXTO, (x0 + 0.006, y - ALTO_FILA / 2))
            diseno_adaptable.ajustar_texto(t, ancho - 0.34, escala_min=0.93, max_lineas=1)
            _texto(d, fila.donde, PX, estilo.COLOR_TEXTO_TENUE, (x0 + ancho - 0.205, y - ALTO_FILA / 2), origen=(0.5, 0))
            _texto(d, fila.tamano, PX, estilo.COLOR_TEXTO_TENUE, (x0 + ancho - 0.105, y - ALTO_FILA / 2), origen=(0.5, 0))
            _texto(d, fila.peso, PX, estilo.COLOR_TEXTO, (x0 + ancho - 0.005, y - ALTO_FILA / 2), origen=(0.5, 0))
            y -= ALTO_FILA
        if len(filas) > MAX_FILAS:
            _texto(d, f"+{len(filas) - MAX_FILAS} más", PX, estilo.COLOR_TEXTO_TENUE, (x0, y - 0.015))
        if not filas:
            _texto(d, "No llevas nada.", 15, estilo.COLOR_TEXTO_TENUE, (x0, y - 0.02))

    def _pie(self, d):
        c, inv = self.control, self.control.inv
        abajo = -ALTO / 2
        izq = -ANCHO / 2 + 0.03
        ancho = ANCHO - 0.06
        _caja(d, ancho, 0.003, estilo.COLOR_BARRA_FONDO, (0, abajo + ALTO_PIE))
        titulo, detalle = calc.detalle_de(inv, c.seleccion)
        _texto(d, titulo, 16, estilo.COLOR_TEXTO, (izq, abajo + ALTO_PIE - 0.022), negrita=True)
        t = _texto(d, detalle, PX, estilo.COLOR_TEXTO_TENUE, (izq, abajo + ALTO_PIE - 0.05))
        diseno_adaptable.ajustar_texto(t, ancho, escala_min=0.93)
        # El mensaje solo aparece si aporta algo distinto de la descripción (los rechazos, siempre).
        if c.mensaje and (c.error or c.mensaje.strip() != detalle.strip()):
            tono = (240, 110, 110) if c.error else estilo.ESTADO_EXITO
            m = _texto(d, c.mensaje, 14, tono, (izq, abajo + ALTO_PIE - 0.080), negrita=True)
            diseno_adaptable.ajustar_texto(m, ancho, escala_min=0.93)
        proporcion = min(1.0, inv.peso_total() / max(inv.peso_max(), 1e-6))
        tono = estilo.COLOR_BARRA_ALTO if proporcion < 0.7 else estilo.COLOR_BARRA_MEDIO if proporcion < 0.95 \
            else estilo.COLOR_BARRA_BAJO
        ancho_barra, y_barra = 0.30, abajo + 0.058
        _caja(d, ancho_barra, 0.012, estilo.COLOR_BARRA_FONDO, (izq + ancho_barra / 2, y_barra), 3)
        if proporcion > 0:
            w = max(ancho_barra * proporcion, 0.012)
            _caja(d, w, 0.012, tono, (izq + w / 2, y_barra), 3, -0.001)
        _texto(d, calc.texto_pie(inv), 14, estilo.COLOR_TEXTO, (izq + ancho_barra + 0.02, y_barra))
        ayuda = ("Flechas elegir · Enter mover aquí · X cancela" if c.modo_mover else
                 "Flechas elegir · Enter usar · Q soltar · X mover · Esc cierra")
        a = _texto(d, ayuda, PX, estilo.COLOR_TEXTO_TENUE, (izq, abajo + 0.022))
        diseno_adaptable.ajustar_texto(a, ancho, escala_min=0.93)
