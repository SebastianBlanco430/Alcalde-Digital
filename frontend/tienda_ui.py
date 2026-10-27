# Panel de la tienda (Ursina, camera.ui): modal y centrado, con el mismo estilo que el inventario (PanelInventario).
# Arriba el nombre del comercio y del dependiente; en medio la lista de lo que vende (nombre, descripción y precio, con la
# fila elegida resaltada); abajo el saldo, el mensaje de la última compra (rojo si se rechazó) y las teclas. Toda la
# lógica vive en frontend/tienda_calculos.py (ControlTienda); aquí solo se dibuja, y solo cuando cambia la firma.
# Pantallas 16:9 y 4:3: el ancho se mide en unidades de camera.ui y los textos largos se ajustan (diseno_adaptable).

from ursina import Entity, Text

from frontend import diseno_adaptable, estilo, tienda_calculos as calc, tipografia
from frontend.componentes import destruir_arbol, escala_fuente, modelo_redondeado, panel_tinta, rgb

ANCHO, ALTO = 0.84, 0.70
ALTO_FILA = 0.062
MAX_FILAS = 7


def _texto(padre, cadena, px, tono, pos, origen=(-0.5, 0), negrita=False, z=-0.01):
    opciones = {"font": tipografia.FUENTE_TITULO} if negrita else {}
    return Text(cadena.replace("<", "(").replace(">", ")"), parent=padre, origin=origen, position=(pos[0], pos[1], z),
                scale=escala_fuente(px), color=rgb(tono), **opciones)


def _caja(padre, ancho, alto, tono, pos, radio=6, z=0.0):
    return Entity(parent=padre, model=modelo_redondeado(ancho, alto, radio), color=rgb(tono) if isinstance(tono, tuple)
                  else tono, scale=(ancho, alto), position=(pos[0], pos[1], z))


class PanelTienda(Entity):

    def __init__(self, control=None, titulo_fn=None, **opciones):
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        self.control = control
        self._titulo_fn = titulo_fn or (lambda: ("", ""))
        self._firma = None
        self.marco = panel_tinta(self, ANCHO, ALTO, z=-0.02)
        self.dinamico = Entity(parent=self, z=-0.03)
        self.z = -0.05

    # -- Contrato de modal (frontend/economia_mundo.py) --

    def abrir(self, control=None):
        if control is not None:
            self.control = control
        self.enabled = True
        self._firma = None
        self.redibujar()

    def cerrar(self):
        self.enabled = False

    def tecla(self, key):
        return None if self.control is None else self.control.tecla(key)

    def actualizar(self):
        if self.enabled and self.control is not None:
            self.redibujar()

    # Redibuja solo si cambió algo visible.
    def redibujar(self):
        firma = (self.control.firma(), self._titulo_fn())
        if firma == self._firma:
            return False
        self._firma = firma
        for hijo in list(self.dinamico.children):
            destruir_arbol(hijo)
        self._dibujar()
        return True

    # -- Dibujo --

    def _dibujar(self):
        d, c = self.dinamico, self.control
        izq, arriba = -ANCHO / 2, ALTO / 2
        titulo, dependiente = self._titulo_fn()
        t = _texto(d, titulo or "TIENDA", 24, estilo.COLOR_ACENTO, (izq + 0.03, arriba - 0.04), negrita=True)
        diseno_adaptable.ajustar_texto(t, ANCHO - 0.28, escala_min=0.55)
        if dependiente:
            _texto(d, f"Atiende {dependiente}", 14, estilo.COLOR_TEXTO_TENUE, (izq + 0.03, arriba - 0.082))
        _texto(d, "Esc cierra", 14, estilo.COLOR_TEXTO_TENUE, (ANCHO / 2 - 0.03, arriba - 0.042), origen=(0.5, 0))
        _caja(d, ANCHO - 0.06, 0.003, estilo.COLOR_BARRA_FONDO, (0, arriba - 0.105))
        self._lista(d, izq + 0.03, arriba - 0.12)
        self._pie(d)

    def _lista(self, d, x0, y0):
        c = self.control
        ancho = ANCHO - 0.06
        primera = max(0, min(c.seleccion - MAX_FILAS + 1, len(c.filas) - MAX_FILAS))
        y = y0
        for i in range(primera, min(len(c.filas), primera + MAX_FILAS)):
            fila = c.filas[i]
            centro_y = y - ALTO_FILA / 2
            if i == c.seleccion:
                _caja(d, ancho + 0.01, ALTO_FILA - 0.004, estilo.COLOR_ACENTO, (x0 + ancho / 2, centro_y), 5, -0.001)
                _caja(d, ancho + 0.004, ALTO_FILA - 0.011, estilo.COLOR_PANEL, (x0 + ancho / 2, centro_y), 4, -0.002)
            n = _texto(d, fila.nombre, 16, estilo.COLOR_TEXTO, (x0 + 0.012, centro_y + 0.014), negrita=True)
            diseno_adaptable.ajustar_texto(n, ancho - 0.24, escala_min=0.6)
            descripcion = _texto(d, fila.descripcion, 11, estilo.COLOR_TEXTO_TENUE, (x0 + 0.012, centro_y - 0.014))
            diseno_adaptable.ajustar_texto(descripcion, ancho - 0.20, escala_min=0.55)
            _texto(d, fila.texto_precio, 18, estilo.COLOR_ACENTO if i == c.seleccion else estilo.COLOR_TEXTO,
                   (x0 + ancho - 0.012, centro_y), origen=(0.5, 0), negrita=True)
            y -= ALTO_FILA
        if not c.filas:
            _texto(d, "Aquí no hay nada a la venta.", 15, estilo.COLOR_TEXTO_TENUE, (x0, y - 0.03))
        if len(c.filas) > MAX_FILAS:
            _texto(d, f"{c.seleccion + 1} / {len(c.filas)}", 12, estilo.COLOR_TEXTO_TENUE,
                   (x0 + ancho, ALTO / 2 - 0.082), origen=(0.5, 0))

    def _pie(self, d):
        c = self.control
        abajo = -ALTO / 2
        izq = -ANCHO / 2 + 0.03
        ancho = ANCHO - 0.06
        _caja(d, ancho, 0.003, estilo.COLOR_BARRA_FONDO, (0, abajo + 0.128))
        _texto(d, calc.texto_saldo(c.saldo()), 18, estilo.COLOR_TEXTO, (izq, abajo + 0.104), negrita=True)
        if c.mensaje:
            tono = (240, 110, 110) if c.error else estilo.ESTADO_EXITO
            m = _texto(d, c.mensaje, 14, tono, (izq, abajo + 0.066), negrita=True)
            diseno_adaptable.ajustar_texto(m, ancho, escala_min=0.6)
        a = _texto(d, "Flechas elegir · Enter comprar · Esc cierra", 12, estilo.COLOR_TEXTO_TENUE, (izq, abajo + 0.026))
        diseno_adaptable.ajustar_texto(a, ancho, escala_min=0.6)
