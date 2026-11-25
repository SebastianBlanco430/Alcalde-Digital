# Piezas dibujadas con primitivas para «Contrarreloj» visual (Ursina): sombra plana, tarjeta-titular de papel, cronómetro,
# línea discontinua, iconos (mano, flecha, aspa, palomita) y pulsador-sello. Los cálculos viven en
# contrarreloj_piezas_calculos.py (puro). Propias de esta vista: no dependen de otras piezas.
# Piel BOTW (docs/ESTILO_BOTW.md; ALCALDE_UI_BOTW=0 o Ajustes › Estilo «Clásico» la apagan): paneles, botones y
# títulos con la piel del menú de inicio (componentes.panel_piel / boton_piel_*, tipografia.fuente_piel).

from ursina import Entity, Mesh, Text, Vec3, color

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente, modelo_redondeado, rgb
from frontend.minijuegos import ui
from frontend.minijuegos_visual import contrarreloj_piezas_calculos as pc
from frontend.minijuegos_visual import ladera_calculos as lad

PAPEL = (250, 244, 228)
PAPEL_VIEJO = (236, 224, 190)
PAPEL_SOMBRA = (214, 200, 168)
TINTA = estilo.TINTA
CIAN = estilo.ACENTO_SECUNDARIO
AMARILLO = estilo.COLOR_ACENTO
ROJO = estilo.ESTADO_ERROR
ROJO_TINTA = (176, 40, 48)          # rojo de sello de goma: contraste ≥ 5 sobre el papel
VERDE = estilo.ESTADO_EXITO
AZUL_BOTON = estilo.COLOR_BOTON


def rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def sombra_plana(parent, ancho, alto, posicion, z=0.007, radio_px=8):
    """Sombra plana de tinta desplazada (4, -5) px respecto al panel."""
    dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
    return ui.rect(parent, ancho, alto, rgba(TINTA, estilo.ALFA_SOMBRA / 255.0),
                   (posicion[0] + a_unidades(dx), posicion[1] + a_unidades(dy)), z=z, radio_px=radio_px)


def trazo(parent, cx, cy, angulo, largo, grosor, tono, z=-0.004):
    return Entity(parent=parent, model="quad", color=rgba(tono), scale=(largo, grosor), rotation_z=angulo,
                  position=(cx, cy, z))


def icono_aspa(parent, tam=0.03, tono=ROJO, posicion=(0, 0), z=-0.006):
    raiz = Entity(parent=parent, position=(posicion[0], posicion[1], z))
    for cx, cy, ang, largo in pc.trazos_aspa(tam):
        trazo(raiz, cx, cy, ang, largo, tam * 0.34, tono, 0)
    return raiz


def icono_palomita(parent, tam=0.03, tono=VERDE, posicion=(0, 0), z=-0.006):
    raiz = Entity(parent=parent, position=(posicion[0], posicion[1], z))
    for cx, cy, ang, largo in pc.trazos_palomita(tam):
        trazo(raiz, cx, cy, ang, largo, tam * 0.34, tono, 0)
    return raiz


def icono_flecha(parent, ancho=0.05, tono=TINTA, posicion=(0, 0), z=-0.006):
    raiz = Entity(parent=parent, position=(posicion[0], posicion[1], z))
    for cx, cy, ang, largo in pc.trazos_flecha(ancho):
        trazo(raiz, cx, cy, ang, largo, ancho * 0.16, tono, 0)
    return raiz


def icono_mano(parent, tam=0.06, tono=TINTA, posicion=(0, 0), z=-0.006):
    raiz = Entity(parent=parent, position=(posicion[0], posicion[1], z))
    for cx, cy, ancho, alto, ang in pc.rectangulos_mano(tam):
        Entity(parent=raiz, model="quad", color=rgba(tono), scale=(ancho, alto), rotation_z=ang, position=(cx, cy, 0))
    return raiz


class TarjetaTitular(ui.Tarjeta):
    """Noticia como tarjeta de papel: círculo amarillo con número, titular (2 líneas) y fila inferior para la barra.
    Imita la interfaz de ui.Tarjeta (estado, fijar_estado, fijar_foco...) porque lo es."""

    sello = None            # la base llama a _pintar() desde su __init__, antes de que exista el sello

    def __init__(self, ancho, alto, titular, numero, **opciones):
        reserva = 0.06
        super().__init__(ancho, alto, "", "", 14, 12, tono=PAPEL, margen_px=3, reserva=reserva, **opciones)
        sombra_plana(self, ancho + 0.006, alto + 0.006, (0, 0), z=0.0045, radio_px=10)
        self.sello = None
        lineas = ui.lineas_de(titular, 14, ancho - 2 * a_unidades(6) - reserva)
        if len(lineas) > 2:
            lineas = lineas[:2]
            lineas[1] = lineas[1].rstrip(" .,;") + "..."
        self.cuerpo.text = "\n".join(lineas)
        self.cuerpo.x += reserva
        self.cuerpo.color = rgb(TINTA)
        self.etiqueta.color = rgb(TINTA)
        self.etiqueta.y = -alto / 2 + 0.028
        self.etiqueta.scale = escala_fuente(17)          # estado final («FRENADA», «MAL: era cierta»...): >= 17 px
        cx, cy = -ancho / 2 + 0.036, alto / 2 - 0.034
        self.disco = Entity(parent=self, model="circle", color=rgba(TINTA), scale=0.054, position=(cx, cy, -0.01))
        self.disco_fondo = Entity(parent=self, model="circle", color=rgba(AMARILLO), scale=0.046, position=(cx, cy, -0.011))
        self.numero = Text(str(numero), parent=self, origin=(0, 0), position=(cx, cy, -0.012), scale=escala_fuente(15),
                           font=tipografia.fuente_piel(titulo=True), color=rgb(TINTA))
        self.icono = None
        self.centro_disco = (cx, cy)

    def _pintar(self):
        """El «>> ELEGIR» de la base se solaparía con la palabra de difusión («Se está difundiendo»): aquí el foco ya se ve en
        el borde amarillo grueso, así que ese rótulo se oculta. El resto de estados (FRENADA, BIEN...) siguen con su texto."""
        super()._pintar()
        if not self.is_empty() and self.etiqueta.text == ">> ELEGIR":
            self.etiqueta.text = ""
        if not self.is_empty() and self.sello is not None and self.estado == "frenada":
            self.etiqueta.text = ""          # el sello ya lo dice; el rótulo de la base quedaría debajo

    def poner_sello(self, texto="FRENADA", giro=-8.0):
        """Sello rojo-tinta rotado sobre la noticia (no sobre el mapa). Devuelve el sello (con .fijar(escala, alfa))."""
        if self.sello is None:
            self.sello = SelloTinta(texto, 0.16, 0.04, 17, parent=self, position=(self.ancho / 2 - 0.105, -self.alto / 2 + 0.032, -0.05))      # dentro de SU nota: no invade la de abajo
            self.sello.rotation_z = giro
            self.sello.fijar(1.0, 0.0)
            self._pintar()
        return self.sello

    def marcar(self, acierto):
        """Palomita verde (acierto) o aspa roja (error) sobre el círculo: el estado no depende solo del color."""
        if self.icono is not None:
            self.icono.enabled = False
            self.icono = None
        self.disco_fondo.color = rgba(VERDE if acierto else ROJO)
        self.numero.enabled = False
        pintar = icono_palomita if acierto else icono_aspa
        self.icono = pintar(self, 0.026, PAPEL, self.centro_disco, z=-0.014)
        if self.sello is not None:
            self.sello.enabled = False       # al final mandan «BIEN» / «MAL» y la palomita o el aspa


class Cronometro(Entity):
    """Cápsula de papel que se vacía; roja en el último 25 %. `position` es su centro."""

    def __init__(self, ancho=0.46, alto=0.04, **opciones):
        super().__init__(**opciones)
        self.ancho, self.alto = ancho, alto
        sombra_plana(self, ancho, alto, (0, 0), z=0.006, radio_px=12)
        ui.rect(self, ancho + 0.008, alto + 0.008, TINTA, z=0.005, radio_px=14)
        ui.rect(self, ancho, alto, PAPEL, z=0.004, radio_px=12)
        self.relleno = Entity(parent=self, model="quad", color=rgba(CIAN), origin=(-0.5, 0), z=0.002,
                              position=(-ancho / 2 + 0.006, 0), scale=(ancho - 0.012, alto * 0.62))
        self.etiqueta = Text("TIEMPO", parent=self, origin=(0, 0), position=(0, 0, -0.002), scale=escala_fuente(13),
                             font=tipografia.fuente_piel(titulo=True), color=rgb(TINTA))

    def fijar(self, restante):
        self.relleno.scale_x = max(0.0001, (self.ancho - 0.012) * restante)
        roja = pc.es_rojo(restante)
        self.relleno.color = rgba(ROJO if roja else CIAN)
        self.etiqueta.text = "POCO TIEMPO" if roja else "TIEMPO"


class LineaDiscontinua(Entity):
    """Enlace cian discontinuo entre dos puntos (pool de trazos que se recolocan)."""

    def __init__(self, tono=CIAN, grosor=0.006, n=40, **opciones):
        super().__init__(**opciones)
        self.trazos = [Entity(parent=self, model="quad", color=rgba(tono), scale=(0.01, grosor), enabled=False)
                       for _ in range(n)]
        self._clave = None

    def fijar(self, p0, p1):
        clave = (round(p0[0], 3), round(p0[1], 3), round(p1[0], 3), round(p1[1], 3))
        if clave == self._clave:
            return
        self._clave = clave
        seg = pc.segmentos_discontinuos(p0, p1, maximo=len(self.trazos))
        for i, t in enumerate(self.trazos):
            if i < len(seg):
                cx, cy, ang, largo = seg[i]
                t.enabled = True
                t.position = (cx, cy, 0.0)
                t.rotation_z = ang
                t.scale_x = largo
            else:
                t.enabled = False

    def esconder(self):
        self._clave = None
        for t in self.trazos:
            t.enabled = False


class SelloTinta(Entity):
    """Sello de goma: texto en rojo-tinta dentro de un marco de 2 px, con papel semitransparente debajo."""

    def __init__(self, texto, ancho, alto, px, tono=ROJO_TINTA, **opciones):
        super().__init__(**opciones)
        self.tono = tono
        borde = 0.004
        self.marco = ui.rect(self, ancho, alto, rgba(tono, 0), z=0.0, radio_px=6)
        self.hueco = ui.rect(self, ancho - 2 * borde, alto - 2 * borde, rgba(PAPEL, 0), z=-0.001, radio_px=4)
        self.texto = Text(texto, parent=self, origin=(0, 0), position=(0, 0, -0.002), scale=escala_fuente(px),
                          font=tipografia.fuente_piel(titulo=True), color=rgba(tono, 0))

    ALFA_MAX = 0.6          # MIN-014: el sello deja leer la noticia frenada que tiene debajo
    ALFA_HUECO = 0.25       # antes 0,92: el papel casi opaco del hueco tapaba el texto

    def fijar(self, escala, alfa):
        self.scale = escala
        alfa = min(float(alfa), 1.0) * self.ALFA_MAX
        self.marco.color = rgba(self.tono, alfa)
        self.hueco.color = rgba(PAPEL, self.ALFA_HUECO * alfa)
        self.texto.color = rgba(self.tono, alfa)


class BarraTinta(ui.Barra):
    """Barra de difusión de papel: pista clara con borde de tinta, relleno de color y dos marcas de tercio.
    Mismo contrato que ui.Barra (fijar, enabled, z)."""

    def __init__(self, ancho, alto=0.018, tono=None, **opciones):
        super().__init__(ancho, alto, tono=tono, **opciones)
        self.fondo.color = rgb(PAPEL_SOMBRA)
        self.fondo.z = 0.003
        self.borde = ui.rect(self, ancho + 0.006, alto + 0.006, TINTA, z=0.004, radio_px=5)
        for k in (1, 2):
            Entity(parent=self, model="quad", color=rgba(TINTA, 0.55), scale=(0.0018, alto * 0.9),
                   position=(-ancho / 2 + ancho * k / 3, 0, 0.001))


class _BotonTinta(ui.Boton):
    """Botón con borde de tinta de 3 px sobre papel o amarillo (no el azul de menú). Mismo contrato que ui.Boton."""

    _FONDO = PAPEL
    _TEXTO = TINTA
    _SOBRE = (255, 247, 214)

    def _entra(self):
        if not self.is_empty() and self.habilitado:
            self.fondo.color = rgb(self._SOBRE)

    def fijar_foco(self, valor):
        self._foco = bool(valor)
        if self.is_empty():
            return
        if not self.habilitado:
            self.fondo.color = rgb((200, 192, 172))
            self.texto.color = rgb((96, 90, 76))
        else:
            self.fondo.color = rgb(self._FONDO)
            self.texto.color = rgb(self._TEXTO)
        extra = a_unidades(5 if self._foco else 3)
        if getattr(self, "_foco_pintado", None) != self._foco:
            self._foco_pintado = self._foco
            self.borde.model = modelo_redondeado(self.ancho + 2 * extra, self.alto + 2 * extra, 10)
            self.borde.scale = (self.ancho + 2 * extra, self.alto + 2 * extra)
        self.borde.color = rgb(ui.COLOR_FOCO if self._foco else TINTA)
        self.texto.text = self._etiqueta


class _BotonFrena(_BotonTinta):
    _FONDO = AMARILLO
    _SOBRE = (255, 232, 110)


class _BotonPasa(_BotonTinta):
    pass


def pulsador_sello(etiqueta, al_clic, ancho, alto, px, posicion, parent, tipo="frenar"):
    """Pulsador grande con borde de tinta: FRENA = amarillo con mano; DEJA PASAR = papel con flecha. Mismo contrato que ui.Boton."""
    primario = tipo == "frenar"
    clase = _BotonFrena if primario else _BotonPasa
    boton = clase(etiqueta, al_clic, ancho, alto, px, primario=primario, parent=parent, position=posicion)
    boton.texto.x = 0.03
    x_icono = -ancho / 2 + 0.06
    if primario:
        icono_mano(boton, 0.075, TINTA, (x_icono, 0.0), z=-0.02)
    else:
        icono_flecha(boton, 0.075, TINTA, (x_icono, 0.0), z=-0.02)
    sombra_plana(boton, ancho, alto, (0, 0), z=0.006, radio_px=8)
    return boton


# -- Mapa de ladera: una sola malla estática, manchas y chapas --

def malla_de(vertices, triangulos, colores=None):
    return Mesh(vertices=[Vec3(*v) for v in vertices], triangles=[tuple(t) for t in triangulos],
                colors=[color.rgba32(*c) for c in colores] if colores else None)


def escenario_ladera(parent, ancho, alto, anchos_etiqueta, posicion=(0.0, 0.0)):
    """Todo el paisaje estático (cielo, terrazas, escaleras, casas, chapas de nombre) como UNA entidad con una malla."""
    vertices, triangulos, colores = lad.malla(lad.escenario(ancho, alto, anchos_etiqueta))
    ent = Entity(parent=parent, model=malla_de(vertices, triangulos, colores), position=(posicion[0], posicion[1], 0.0),
                 double_sided=True)
    return ent


class Mancha(Entity):
    """Mancha de contagio: relleno translúcido (escala = radio) con la forma irregular de la zona."""

    def __init__(self, fase, **opciones):
        vertices, triangulos = lad.malla_relleno(fase)
        super().__init__(model=malla_de(vertices, triangulos), double_sided=True, **opciones)


class AnilloMancha(Entity):
    """Contorno de tinta de la mancha, de grosor constante; la malla solo se rehace si el radio cambia un paso."""

    def __init__(self, fase, **opciones):
        super().__init__(double_sided=True, **opciones)
        self.fase = fase
        self._clave = None

    def fijar(self, radio, grosor):
        clave = (lad.cuantizar_radio(radio), round(grosor, 4))
        if clave == self._clave:
            return
        self._clave = clave
        vertices, triangulos = lad.malla_anillo(clave[0], grosor, self.fase)
        self.model = malla_de(vertices, triangulos)


class Chapa(Entity):
    """Chapa redonda de tinta con el número de la noticia (círculo amarillo, cifra en tinta)."""

    def __init__(self, numero, tam=0.036, **opciones):
        super().__init__(**opciones)
        Entity(parent=self, model="circle", color=rgba(TINTA), scale=tam, z=0.0)
        Entity(parent=self, model="circle", color=rgba(AMARILLO), scale=tam * 0.84, z=-0.0005)
        Text(str(numero), parent=self, origin=(0, 0), position=(0, 0, -0.001), scale=escala_fuente(15),
             font=tipografia.fuente_piel(titulo=True), color=rgb(TINTA))


class LineaPeligro(Entity):
    """Cinta de peligro amarilla y negra (una malla) con la etiqueta «LLEGÓ AL BARRIO» en una pestaña de papel debajo."""

    def __init__(self, ancho, alto, etiqueta, **opciones):
        super().__init__(**opciones)
        polis = lad.franjas_peligro(ancho, alto)
        vertices, triangulos, colores = [], [], []
        for k, (puntos, rgba_) in enumerate(polis):       # fondo amarillo detrás (z .0012) y franjas delante (z .0006)
            base = len(vertices)
            for x, y in puntos:
                vertices.append((x, y, 0.0012 if k == 0 else 0.0006))
                colores.append(rgba_)
            triangulos += [(base, base + j, base + j + 1) for j in range(1, len(puntos) - 1)]
        sombra_plana(self, ancho, alto, (0, 0), z=0.003, radio_px=2)
        ui.rect(self, ancho + 0.007, alto + 0.007, TINTA, z=0.002, radio_px=2)
        Entity(parent=self, model=malla_de(vertices, triangulos, colores), double_sided=True)
        ancho_tab = ui.medir(etiqueta, 14, True) + 0.05
        y_tab = -alto / 2 - 0.021
        ui.rect(self, ancho_tab + 0.006, 0.034, TINTA, (0, y_tab), z=0.002, radio_px=6)
        ui.rect(self, ancho_tab, 0.028, PAPEL, (0, y_tab), z=0.001, radio_px=5)
        Text(etiqueta, parent=self, origin=(0, 0), position=(0, y_tab, -0.002), scale=escala_fuente(14),
             font=tipografia.fuente_piel(titulo=True), color=rgb(TINTA))


def tira_leyenda(parent, texto, px, posicion, ancho_max):
    """Pie del mapa: texto de tinta (≥ 17 px) sobre una tira de papel con borde y sombra. `posicion` = esquina inferior izquierda
    del mapa. Devuelve (raiz, Text)."""
    ancho = min(ancho_max, ui.medir(texto, px) + 0.05)
    alto = ui.alto_de(1, px) + 0.022
    raiz = Entity(parent=parent, position=(posicion[0] + 0.02 + ancho / 2, posicion[1] - 0.018 - alto / 2, 0.0))
    sombra_plana(raiz, ancho, alto, (0, 0), z=0.0035, radio_px=6)
    ui.rect(raiz, ancho + 0.006, alto + 0.006, TINTA, z=0.003, radio_px=7)
    ui.rect(raiz, ancho, alto, PAPEL, z=0.002, radio_px=6)
    t = Text(texto, parent=raiz, origin=(0, 0), position=(0, 0, -0.002), scale=escala_fuente(px), font=tipografia.FUENTE_TEXTO,
             color=rgb(TINTA))
    return raiz, t


def tarjeta_cierre(parent, ancho, a_salvo, mensaje, px, posicion):
    """Cierre de la ronda: papel con borde de tinta, banda de color, icono (palomita o aspa), veredicto en negrita y el
    mensaje debajo. `posicion` = centro de la tarjeta. Devuelve (raiz, alto)."""
    titulo = "BARRIO A SALVO" if a_salvo else "BARRIO CONTAGIADO"
    reserva = 0.065
    lineas = ui.lineas_de(mensaje, px, ancho - reserva - 0.012)
    alto = ui.alto_de(len(lineas), px) + ui.alto_de(1, 19) + 0.016
    raiz = Entity(parent=parent, position=(posicion[0], posicion[1], 0.0))
    tono = VERDE if a_salvo else ROJO_TINTA
    sombra_plana(raiz, ancho, alto, (0, 0), z=0.0035, radio_px=7)
    ui.rect(raiz, ancho + 0.006, alto + 0.006, TINTA, z=0.003, radio_px=9)
    ui.rect(raiz, ancho, alto, PAPEL, z=0.002, radio_px=7)
    ui.rect(raiz, 0.014, alto - 0.012, tono, (-ancho / 2 + 0.014, 0), z=0.001, radio_px=3)
    (icono_palomita if a_salvo else icono_aspa)(raiz, 0.034, tono, (-ancho / 2 + 0.05, alto / 2 - 0.036), z=-0.002)
    ui.texto(raiz, titulo, 19, ancho - reserva, TINTA, (-ancho / 2 + reserva, alto / 2 - 0.014), negrita=True)
    ui.texto(raiz, "\n".join(lineas), px, ancho - reserva - 0.01, TINTA,
             (-ancho / 2 + reserva, alto / 2 - 0.014 - ui.alto_de(1, 19) - 0.004))
    return raiz, alto
