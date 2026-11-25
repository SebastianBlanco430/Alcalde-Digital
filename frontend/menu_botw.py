# Menú de inicio «estilo BOTW» (sesión G, 24-nov): la VISTA. La lógica pura y las medidas del diseño están en
# frontend/menu_botw_calculos.py (con tests); la monta frontend/escenas/escena_inicio.py detrás de ALCALDE_MENU_BOTW.
#
# Es una PIEL sobre la escena de inicio de siempre: los botones de hoy (Continuar, Empezar/Partida nueva, En línea,
# Ajustes, Salir) siguen existiendo como los controles LÓGICOS (sus callbacks, el guardado, la confirmación de «Salir» y
# de «Partida nueva» no cambian) pero se ocultan; esta vista dibuja encima el fondo del póster con zoom lento, los
# velos, el logo, las opciones en cursiva con la flecha y el pie, y refleja el foco de la escena. El cuadro de
# confirmación de la escena (panel de tinta) queda por encima, centrado, con su velo.
#
# Controles: ratón (pasar por encima selecciona, clic acepta), teclado (↑/↓ con repetición, Enter/Espacio, Esc) y mando
# (cruceta y palo con zona muerta y repetición; A acepta, B = Esc). Mientras el menú está a la vista el palo no mueve el
# cursor del sistema (mando.pausar_cursor): navega por las opciones.
#
# Todo en camera.ui con texturas sin shader: no le llegan ni la niebla ni el pase final.
# GUARDIÁN: si algo falla al construir o en un frame, la escena vuelve sola al menú de siempre y avisa UNA vez por stderr.

from ursina import Entity, Text, Texture, color, held_keys, time, window

from frontend import banderas_visuales as bv
from frontend import menu_botw_calculos as calc
from frontend.fondo_menu import FocoTeclado, _bajo_el_raton

FUENTE_OPCION = "AtkinsonHyperlegible-Italic.ttf"
FUENTE_OPCION_SEL = "AtkinsonHyperlegible-BoldItalic.ttf"
FUENTE_PIE = "AtkinsonHyperlegible-Regular.ttf"
CLAVE_AVISO = "menu_botw"

# Profundidades (camera.ui: z menor = delante). El cuadro de confirmación de la escena está en z -0.3.
Z_FONDO, Z_VELO, Z_VELO_INF, Z_LOGO, Z_OPCIONES, Z_PIE, Z_FUNDIDO = 0.95, 0.9, 0.89, 0.6, 0.5, 0.5, -0.9


def _c(rgb, alfa=1.0):
    return color.rgba(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, alfa)


def _escala_texto(px):
    """Escala de Text para una letra de `px` píxeles a 720p."""
    return calc.u(px) / Text.size


def _textura_pil(imagen, filtrado="bilinear"):
    tex = Texture(imagen)
    tex.filtering = filtrado
    return tex


def _textura_degradado(paradas, horizontal, n=256):
    """Textura RGBA de 1 px de grosor con el color del velo y el alfa interpolado entre `paradas` [(pos 0-1, alfa)]."""
    from PIL import Image
    tam = (n, 1) if horizontal else (1, n)
    img = Image.new("RGBA", tam)
    px = img.load()
    for i in range(n):
        f = i / (n - 1)
        a = paradas[-1][1]
        for (f0, a0), (f1, a1) in zip(paradas, paradas[1:]):
            if f0 <= f <= f1:
                a = a0 + (a1 - a0) * ((f - f0) / (f1 - f0) if f1 > f0 else 0)
                break
        valor = (*calc.VELO, int(round(a * 255)))
        if horizontal:
            px[i, 0] = valor
        else:
            px[0, n - 1 - i] = valor          # PIL: fila 0 = arriba; f = 0 abajo
    return _textura_pil(img)


def _textura_flecha(escala=4):
    """La flecha del diseño (SVG 26 × 18: punta a la izquierda y cola a la derecha), amarilla con borde de tinta."""
    from PIL import Image, ImageDraw
    w, h = calc.FLECHA_ANCHO_PX * escala, calc.FLECHA_ALTO_PX * escala
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = escala
    tinta, amarillo = (*calc.TINTA, 255), (*calc.AMARILLO, 255)
    # cola (trazo amarillo de 3 con borde de tinta) y punta (relleno amarillo y trazo de tinta de 2,5 CENTRADO en el
    # borde, como en SVG: PIL dibuja el `outline` del polígono hacia dentro y se comería el relleno)
    punta = [(2 * s, 9 * s), (18 * s, 2 * s), (15 * s, 9 * s), (18 * s, 16 * s)]
    d.polygon(punta, fill=amarillo)
    d.line(punta + [punta[0]], fill=tinta, width=int(2.5 * s), joint="curve")
    # la cola va encima de la punta, como en el SVG (trazo amarillo de 3 con extremo redondo)
    d.line([(16 * s, 9 * s), (25 * s, 9 * s)], fill=amarillo, width=int(3 * s))
    d.ellipse((23.5 * s, 7.5 * s, 26.5 * s, 10.5 * s), fill=amarillo)
    return _textura_pil(img, "mipmap")


def _textura_flechas_ayuda(escala=4):
    """«↑ ↓» del pie dibujadas (Atkinson Hyperlegible no trae flechas): blancas con sombra de tinta de 1 px."""
    from PIL import Image, ImageDraw
    s = escala
    w, h = ANCHO_FLECHAS_AYUDA_PX * s, calc.ALTO_LINEA_PIE_PX * s
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def flecha(x, arriba, tono, dx=0.0, dy=0.0):
        x0, y0, y1 = (x + dx) * s, (3 + dy) * s, (13 + dy) * s
        punta, base = (y0, y0 + 4.5 * s) if arriba else (y1, y1 - 4.5 * s)
        d.line([(x0, y0 + (1 if arriba else 0) * s), (x0, y1 - (0 if arriba else 1) * s)], fill=tono, width=int(1.6 * s))
        d.polygon([(x0, punta), (x0 - 3.6 * s, base), (x0 + 3.6 * s, base)], fill=tono)

    for dx, dy, tono in ((1, 1, (*calc.TINTA, 255)), (0, 0, (*calc.TEXTO_PIE, 255))):
        flecha(4.5, True, tono, dx, dy)
        flecha(15.5, False, tono, dx, dy)
    return _textura_pil(img, "mipmap")


ANCHO_FLECHAS_AYUDA_PX = 21


class _TextoConSombra(Entity):
    """Text con sombra plana de tinta (desplazada `sombra_px` abajo a la derecha). Alineado por `origen`."""

    def __init__(self, texto, px, fuente, tono, origen=(0.5, 0), sombra_px=calc.SOMBRA_TEXTO_PX, **opciones):
        super().__init__(**opciones)
        escala = _escala_texto(px)
        d = calc.u(sombra_px)
        self.sombra = Text(texto, parent=self, font=fuente, origin=origen, scale=escala, color=_c(calc.TINTA),
                           position=(d, -d, 0.001))
        self.frente = Text(texto, parent=self, font=fuente, origin=origen, scale=escala, color=_c(tono))
        self._tono = tono
        self._alfa = 1.0
        self._texto = texto
        self._ancho = None

    @property
    def texto(self):
        return self._texto

    @texto.setter
    def texto(self, valor):
        if valor != self._texto:
            self._texto = valor
            self.sombra.text = valor
            self.frente.text = valor
            self._ancho = None

    def alfa(self, valor):
        """Opacidad (entrada escalonada). Los Text de Ursina no heredan la escala de color del padre (setColorScaleOff)
        y su shader no la usa: se cambia su color, y solo cuando cambia (tras la entrada queda en 1 y no se toca)."""
        valor = round(float(valor), 3)
        if valor != self._alfa:
            self._alfa = valor
            self.frente.color = _c(self._tono, valor)
            self.sombra.color = _c(calc.TINTA, valor)

    def ancho(self):
        """Ancho del texto en unidades de su padre (en caché hasta que cambie el texto)."""
        if self._ancho is None:
            self._ancho = float(self.frente.width) * float(self.frente.scale_x)
        return self._ancho


class _Opcion(Entity):
    """Una opción del menú: texto normal (cursiva blanca) y seleccionado (cursiva negrita amarilla), zona de ratón y,
    solo «Continuar», el detalle de la partida guardada."""

    def __init__(self, boton, con_detalle=False, **opciones):
        super().__init__(**opciones)
        self.boton = boton
        texto = str(getattr(boton, "text", "") or "")
        self.normal = _TextoConSombra(texto, calc.OPCION_PX, FUENTE_OPCION, calc.BLANCO, parent=self)
        self.sel = _TextoConSombra(texto, calc.OPCION_PX, FUENTE_OPCION_SEL, calc.AMARILLO, parent=self,
                                   enabled=False)
        self.detalle = None
        if con_detalle:
            self.detalle = _TextoConSombra("", calc.DETALLE_PX, FUENTE_PIE, calc.TEXTO_DETALLE, parent=self,
                                           sombra_px=1, enabled=False)
        # Zona del ratón: un quad transparente con collider (el texto no lo tiene).
        self.zona = Entity(parent=self, model="quad", color=color.clear, collider="box", z=0.01)
        self.seleccionada = False

    def bajo_el_raton(self):
        return bool(self.enabled and getattr(self.zona, "hovered", False))

    def refrescar_texto(self):
        texto = str(getattr(self.boton, "text", "") or "")
        self.normal.texto = texto
        self.sel.texto = texto

    def alfa(self, valor):
        for t in (self.normal, self.sel, self.detalle):
            if t is not None:
                t.alfa(valor)

    def marcar(self, seleccionada):
        if seleccionada != self.seleccionada:
            self.seleccionada = seleccionada
            self.normal.enabled = not seleccionada
            self.sel.enabled = seleccionada


class FocoBotw(FocoTeclado):
    """FocoTeclado con ↑/↓ con repetición (teclado, cruceta y palo) que salta las opciones ocultas: una pulsación nueva
    da la vuelta (de la última a la primera); sostener se para en el extremo. ←/→/Tab siguen moviendo (el cuadro de
    confirmación «No / Sí» es horizontal). Enter/Espacio activan, como siempre."""

    VERTICAL = {"up arrow": -1, "down arrow": 1}

    def __init__(self, obtener, **opciones):
        super().__init__(obtener, **opciones)
        self.repetidor = calc.Repetidor()

    def reiniciar(self):
        # «Continuar» (si hay guardado) o «Partida nueva» van primero en el orden del diseño (calc.ORDEN): índice 0.
        self.indice = 0
        self.visible = False
        self.repetidor.soltar()
        self._aplicar()

    def _pasos(self, pasos):
        if not pasos:
            return
        completa = list(self._obtener())
        lista = self.controles()
        actual = self.enfocado()
        if actual is None or actual not in completa:
            return
        visibles = [c.esta_habilitado() for c in completa]
        nuevo = completa[calc.navegar(completa.index(actual), pasos, visibles)]
        self.indice = lista.index(nuevo)
        self.visible = True
        self._aplicar()

    def _hover(self):
        """Como FocoTeclado.update, pero el ratón solo se lleva el foco si SE MOVIÓ: si la lista cambia de forma (el
        detalle de «Continuar» aparece o se va) bajo un ratón quieto, el foco que se eligió con el teclado no salta."""
        from ursina import mouse
        lista = self.controles()
        pos = (round(float(mouse.x), 5), round(float(mouse.y), 5))
        movido = pos != getattr(self, "_pos_raton", pos)
        self._pos_raton = pos
        encima = next((c for c in lista if _bajo_el_raton(c)), None)
        if encima is not self._hover_previo:
            self._hover_previo = encima
            if encima is not None and movido:
                self.indice = lista.index(encima)
                self.visible = False
        self._aplicar()

    def input(self, key):
        d = self.VERTICAL.get(key)
        if d is not None:
            self._pasos(self.repetidor.pulsar(d))
        else:
            super().input(key)

    def update(self):
        self._hover()
        try:
            from frontend import mando_calculos as mc
            _, palo_y = mc.palo(held_keys, mc.PALO_IZQUIERDO)
        except Exception:                    # noqa: BLE001  sin mando: solo teclado
            palo_y = 0.0
        d = calc.direccion(arriba=bool(held_keys["up arrow"] or held_keys["gamepad dpad up"]),
                           abajo=bool(held_keys["down arrow"] or held_keys["gamepad dpad down"]), palo_y=palo_y)
        self._pasos(self.repetidor.avanzar(d, time.dt))


class MenuBotw(Entity):
    """La piel BOTW de la escena de inicio. `montar()` oculta el menú de siempre y toma el foco; `desmontar()` lo
    devuelve todo como estaba (lo usa el guardián si algo falla)."""

    def __init__(self, escena, **opciones):
        super().__init__(parent=escena, **opciones)
        try:
            self._construir(escena)
        except Exception:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self)               # nada a medias en pantalla: el menú de siempre sin restos
            raise

    def _construir(self, escena):
        self.escena = escena
        self.t = 0.0                 # reloj del zoom y la flotación
        self.t_entrada = None        # reloj de la entrada (None = ya terminó o no toca)
        self.reducido = bv.reducir_movimiento()
        self._aspecto = None
        self._sel_dibujada = None
        self._roto = False
        self._primera_vez = True

        self.fondo = Entity(parent=self, model="quad", texture=_textura_pil_ruta(calc.FONDO), z=Z_FONDO, shader=None)
        self.velo_der = Entity(parent=self, model="quad", z=Z_VELO, shader=None,
                               texture=_textura_degradado([(0.0, 0.0)] + [(1 - f, a) for f, a in
                                                                           reversed(calc.VELO_DERECHA)], True))
        self.velo_inf = Entity(parent=self, model="quad", z=Z_VELO_INF, shader=None,
                               texture=_textura_degradado([(0.0, calc.VELO_INFERIOR_ALFA), (1.0, 0.0)], False))
        tex_logo = _textura_pil_ruta(calc.LOGO)
        self._tam_logo = (int(tex_logo.width), int(tex_logo.height))
        self.logo = Entity(parent=self, model="quad", texture=tex_logo, z=Z_LOGO, shader=None)

        self.flecha = Entity(parent=self, model="quad", texture=_textura_flecha(), z=Z_OPCIONES - 0.01, shader=None,
                             scale=(calc.u(calc.FLECHA_ANCHO_PX), calc.u(calc.FLECHA_ALTO_PX)))
        self.opciones = []
        for boton in self._botones_posibles():
            self.opciones.append(_Opcion(boton, con_detalle=boton is escena.boton_continuar, parent=self,
                                         z=Z_OPCIONES))

        # «↑ ↓» van dibujadas (la fuente no las trae) y el resto de la ayuda en texto a su derecha.
        self.ayuda_flechas = Entity(parent=self, model="quad", texture=_textura_flechas_ayuda(), z=Z_PIE, shader=None,
                                    scale=(calc.u(ANCHO_FLECHAS_AYUDA_PX), calc.u(calc.ALTO_LINEA_PIE_PX)))
        self.ayuda = _TextoConSombra(calc.AYUDA.replace("↑ ↓", "").strip(), calc.PIE_AYUDA_PX, FUENTE_PIE,
                                     calc.TEXTO_PIE, origen=(-0.5, 0), sombra_px=1, parent=self, z=Z_PIE)
        self.version = [_TextoConSombra(linea, calc.PIE_VERSION_PX, FUENTE_PIE, calc.TEXTO_PIE, sombra_px=1,
                                        parent=self, z=Z_PIE) for linea in calc.VERSION]
        self.negro = Entity(parent=self, model="quad", color=color.black, z=Z_FUNDIDO, shader=None, enabled=False)
        self._detalle_clave, self._detalle = None, ""
        for e in (self.velo_der, self.velo_inf, self.logo, self.flecha, self.negro, self.ayuda_flechas,
                  *self.opciones):
            _transparente(e)
        self.colocar()

    # -- Montaje sobre la escena --

    def _botones_posibles(self):
        e = self.escena
        # «Modo feria» (hilo conductor, docs/MODO_FERIA.md) va tras «Partida nueva»; sin él (bandera), como siempre.
        return [b for b in (e.boton_continuar, e.boton_comenzar, getattr(e, "boton_feria", None), e.boton_online,
                            e.boton_ajustes, e.boton_salir) if b is not None]

    def montar(self):
        e = self.escena
        self._clasico = {"base": e._botones_base, "foco": e.foco}
        # Lo de siempre se oculta colgándolo de un contenedor apagado (los botones siguen «habilitados» y con sus
        # callbacks: son los controles lógicos; ocultos, su collider ya no recibe el ratón).
        self.oculto = Entity(parent=e, enabled=False)
        self._ocultos = [x for x in (e.fondo, e.wordmark, getattr(e, "placa_subtitulo", None), e.texto_continuar,
                                     *self._botones_posibles()) if x is not None]
        for x in self._ocultos:
            x.parent = self.oculto
        # Orden del diseño: Continuar, Partida nueva, (Modo feria), En línea, Ajustes, Salir.
        e._botones_base = tuple(b for b in (e.boton_comenzar, getattr(e, "boton_feria", None), e.boton_online,
                                            e.boton_ajustes, e.boton_salir) if b is not None)
        # El ratón «está encima» de un botón lógico cuando está sobre su opción dibujada.
        for op in self.opciones:
            op.boton.bajo_el_raton = op.bajo_el_raton
        e.foco.enabled = False                 # el foco de siempre deja de escuchar (si no, ↑/↓ moverían dos veces)
        e.foco = FocoBotw(lambda: e.botones, parent=e)
        e._refrescar_continuar()
        e.foco.reiniciar()

    def desmontar(self):
        """Vuelve al menú de siempre (guardián): reaparece lo oculto, orden y foco de siempre, y esta vista se apaga."""
        e = self.escena
        clasico = getattr(self, "_clasico", None)
        try:
            e._cerrar_confirmacion()           # una pregunta abierta no puede quedar sobre los botones de detrás
            for x in getattr(self, "_ocultos", ()):
                x.parent = e
            for op in self.opciones:
                op.boton.__dict__.pop("bajo_el_raton", None)
            if clasico is not None:
                e._botones_base = clasico["base"]
                if e.foco is not clasico["foco"]:
                    e.foco.enabled = False
                    e.foco = clasico["foco"]
                    e.foco.enabled = True
            e._refrescar_continuar()
            e.foco.reiniciar()
        finally:
            self._pausar_palo(False)
            self.enabled = False

    # -- Colocación (cambia con la proporción de la ventana) --

    def colocar(self):
        a = float(window.aspect_ratio)
        self._aspecto = a
        self.velo_der.scale = (a, 1)
        self.velo_inf.scale = (a, calc.u(calc.VELO_INFERIOR_PX))
        self.velo_inf.y = -0.5 + calc.u(calc.VELO_INFERIOR_PX) / 2
        self.negro.scale = (a + 0.2, 1.2)
        x, y, w, h = calc.rect_logo(a, *self._tam_logo)
        self._logo_base = (x, y, w, h)
        (xa, ya), (xv, y1, y2) = calc.pie(a)
        self.ayuda_flechas.position = (xa + calc.u(ANCHO_FLECHAS_AYUDA_PX) / 2, ya, Z_PIE)
        self.ayuda.position = (xa + calc.u(ANCHO_FLECHAS_AYUDA_PX + 5), ya, Z_PIE)
        self.version[0].position = (xv, y1, Z_PIE)
        self.version[1].position = (xv, y2, Z_PIE)
        self._sel_dibujada = None
        self._colocar_fondo()
        self._colocar_logo()
        self._colocar_opciones()

    def _colocar_fondo(self):
        x, y, w, h = calc.transformacion_fondo(self.t, self._aspecto, self.reducido)
        self.fondo.position = (x, y, Z_FONDO)
        self.fondo.scale = (w, h)

    def _t_entrada(self):
        return 1e9 if self.t_entrada is None else self.t_entrada

    def _colocar_logo(self):
        x, y, w, h = self._logo_base
        te = self._t_entrada()
        s = calc.escala_logo(te, self.reducido)
        # el rebote crece desde la esquina del logo (arriba a la derecha), no desde su centro
        derecha, arriba = x + w / 2, y + h / 2
        self.logo.scale = (w * s, h * s)
        self.logo.position = (derecha - w * s / 2, arriba - h * s / 2 + calc.flotacion(self.t, self.reducido), Z_LOGO)
        _alfa_modelo(self.logo, calc.alfa_logo(te, self.reducido))

    def _menu_actual(self):
        e = self.escena
        return list(e._botones_menu if e._botones_menu is not None else e.botones)

    def _colocar_opciones(self):
        e = self.escena
        menu = self._menu_actual()
        enfocado = e.foco.enfocado() if e._botones_menu is None else self._sel_previa()
        visibles = [op for op in self.opciones if op.boton in menu]
        for op in self.opciones:
            ver = op in visibles
            if op.enabled != ver:
                op.enabled = ver
            if ver:
                op.refrescar_texto()
        sel = next((i for i, op in enumerate(visibles) if op.boton is enfocado), None)
        self._sel_boton = enfocado
        con_detalle = None
        if sel is not None and visibles[sel].detalle is not None:
            detalle = self._texto_detalle()
            visibles[sel].detalle.texto = detalle
            con_detalle = sel if detalle else None
        x_der, ys, ys_det = calc.colocar_opciones(self._aspecto, len(visibles), con_detalle)
        te = self._t_entrada()
        for i, op in enumerate(visibles):
            elegida = i == sel
            op.marcar(elegida)
            alfa, dx = calc.entrada_opcion(te, i, self.reducido)
            op.position = (dx, 0, Z_OPCIONES)
            op.alfa(alfa)
            x_txt = calc.x_opcion(x_der, elegida)
            for t in (op.normal, op.sel):
                t.position = (x_txt, ys[i], 0)
            ancho = op.sel.ancho()
            izquierda = x_txt - ancho
            zona_izq = calc.x_flecha(izquierda) - calc.u(calc.FLECHA_ANCHO_PX) / 2
            op.zona.scale = (x_der - zona_izq, calc.u(calc.ALTO_LINEA_OPCION_PX + calc.MENU_SEPARACION_PX))
            op.zona.position = ((x_der + zona_izq) / 2, ys[i], 0.01)
            if op.detalle is not None:
                ver_detalle = elegida and ys_det[i] is not None
                if op.detalle.enabled != ver_detalle:
                    op.detalle.enabled = ver_detalle
                if ver_detalle:
                    op.detalle.position = (x_der, ys_det[i], 0)
            if elegida:
                if not self.flecha.enabled:
                    self.flecha.enabled = True
                self.flecha.position = (calc.x_flecha(izquierda) + dx, ys[i], Z_OPCIONES - 0.01)
                _alfa_modelo(self.flecha, alfa)
        if sel is None and self.flecha.enabled:
            self.flecha.enabled = False

    def _texto_detalle(self):
        """«Partida guardada: …» entero (el texto de la escena va recortado al ancho de la pareja de botones de
        siempre). Se vuelve a pedir el resumen solo cuando la escena cambia el suyo."""
        e = self.escena
        clave = str(getattr(e.texto_continuar, "text", "") or "")
        if clave != self._detalle_clave:
            self._detalle_clave = clave
            texto = ""
            if clave and getattr(e, "_resumen_guardado", None) is not None:
                try:
                    texto = e._resumen_guardado() or ""
                except Exception:            # noqa: BLE001  sin resumen legible: el texto de la escena
                    texto = ""
            self._detalle = (calc.PREFIJO_DETALLE + texto) if texto else clave
        return self._detalle

    def _sel_previa(self):
        return getattr(self, "_sel_boton", None)

    # -- Ciclo --

    def _pausar_palo(self, pausado):
        try:
            from frontend import mando
            mando.pausar_cursor(pausado)
        except Exception:                    # noqa: BLE001  sin mando no hay nada que pausar
            pass

    def al_entrar(self):
        if self._roto:
            return
        self.reducido = bv.reducir_movimiento()
        if self._primera_vez:                 # la entrada solo al abrir el juego
            self._primera_vez = False
            self.t_entrada = 0.0
            self.negro.enabled = True
            _alfa_modelo(self.negro, 1.0)
        self._pausar_palo(True)
        self.colocar()

    def al_salir(self):
        self._pausar_palo(False)

    def _fallar(self, error):
        self._roto = True
        bv.avisar_una_vez(CLAVE_AVISO, error)
        try:
            self.desmontar()
        except Exception as otro:            # noqa: BLE001
            bv.avisar_una_vez(CLAVE_AVISO + ".desmontar", otro)

    def update(self):
        if self._roto or not self.escena.enabled:
            return
        try:
            self._cuadro()
        except Exception as error:           # noqa: BLE001  guardián: vuelve el menú de siempre
            self._fallar(error)

    def _cuadro(self):
        dt = calc.paso_reloj(time.dt)
        if float(window.aspect_ratio) != self._aspecto:
            self.colocar()
        if not self.reducido:
            self.t += dt
        if self.t_entrada is not None:
            self.t_entrada += dt
            _alfa_modelo(self.negro, calc.fundido(self.t_entrada))
            if calc.fundido(self.t_entrada) <= 0:
                self.negro.enabled = False
            if calc.entrada_terminada(self.t_entrada, len(self._menu_actual()), self.reducido):
                self.t_entrada = None
                self.negro.enabled = False
        self._colocar_fondo()
        self._colocar_logo()
        self._colocar_opciones()

    def input(self, key):
        if self._roto or not self.escena.enabled or key != "left mouse down":
            return
        if self.escena.confirmacion.abierta:
            return
        for op in self.opciones:
            if op.enabled and op.bajo_el_raton():
                foco = self.escena.foco
                if op.boton in foco.controles():
                    foco.indice = foco.controles().index(op.boton)
                op.boton.manejar_clic()
                return


def _transparente(entidad):
    # Prioridad 1: que ningún atributo de los hijos deje el fundido sin mezcla.
    from panda3d.core import TransparencyAttrib
    entidad.setTransparency(TransparencyAttrib.M_alpha, 1)


def _alfa_modelo(entidad, alfa):
    """Opacidad de una entidad con modelo. Ursina pone `setColorScaleOff()` en el modelo al fijar `color` (no hereda la
    escala de color del padre), así que un setAlphaScale en la entidad no le llega: se aplica al modelo mismo (conserva
    el RGB de su color). Los Text tampoco heredan: ver _TextoConSombra.alfa."""
    if entidad.model is not None:
        entidad.model.setAlphaScale(alfa)


def _textura_pil_ruta(ruta):
    """Textura desde disco con mipmaps y filtrado lineal (sin parpadeo de texels al hacer zoom ni al reducirla)."""
    tex = Texture(ruta)
    tex.filtering = "mipmap"
    try:
        from panda3d.core import SamplerState
        tex._texture.setMagfilter(SamplerState.FT_linear)
        tex._texture.setAnisotropicDegree(4)
    except Exception:                        # noqa: BLE001
        pass
    return tex


def crear(escena):
    """Construye y monta la piel BOTW sobre `escena`. Devuelve la vista, o None si falta un recurso o algo falla (y
    entonces la escena queda con el menú de siempre; se avisa una vez por stderr)."""
    faltan = calc.recursos_faltantes()
    if faltan:
        bv.avisar_una_vez(CLAVE_AVISO, FileNotFoundError(", ".join(faltan)))
        return None
    vista = None
    try:
        vista = MenuBotw(escena)
        vista.montar()
        return vista
    except Exception as error:               # noqa: BLE001
        bv.avisar_una_vez(CLAVE_AVISO, error)
        if vista is not None:
            try:
                vista.desmontar()
            except Exception:                # noqa: BLE001
                pass
            try:
                from frontend.componentes import destruir_arbol
                destruir_arbol(vista)
            except Exception:                # noqa: BLE001
                pass
        return None
