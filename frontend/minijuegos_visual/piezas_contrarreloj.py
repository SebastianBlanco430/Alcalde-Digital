# Piezas dibujadas con primitivas para «Contrarreloj» visual (Ursina): sombra plana, tarjeta-titular de papel, cronómetro,
# línea discontinua, iconos (mano, flecha, aspa, palomita) y pulsador-sello. Los cálculos viven en
# contrarreloj_piezas_calculos.py (puro). Propias de esta vista: no dependen de otras piezas.

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente, rgb
from frontend.minijuegos import ui
from frontend.minijuegos_visual import contrarreloj_piezas_calculos as pc

PAPEL = (250, 244, 228)
PAPEL_VIEJO = (236, 224, 190)
PAPEL_SOMBRA = (214, 200, 168)
TINTA = estilo.TINTA
CIAN = estilo.ACENTO_SECUNDARIO
AMARILLO = estilo.COLOR_ACENTO
ROJO = estilo.ESTADO_ERROR
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

    def __init__(self, ancho, alto, titular, numero, **opciones):
        reserva = 0.06
        super().__init__(ancho, alto, "", "", 14, 12, tono=PAPEL, margen_px=6, reserva=reserva, **opciones)
        lineas = ui.lineas_de(titular, 14, ancho - 2 * a_unidades(6) - reserva)
        if len(lineas) > 2:
            lineas = lineas[:2]
            lineas[1] = lineas[1].rstrip(" .,;") + "..."
        self.cuerpo.text = "\n".join(lineas)
        self.cuerpo.x += reserva
        self.cuerpo.color = rgb(TINTA)
        self.etiqueta.color = rgb(TINTA)
        self.etiqueta.y = -alto / 2 + 0.017
        self.etiqueta.scale = escala_fuente(13)
        cx, cy = -ancho / 2 + 0.036, alto / 2 - 0.034
        self.disco = Entity(parent=self, model="circle", color=rgba(TINTA), scale=0.054, position=(cx, cy, -0.01))
        self.disco_fondo = Entity(parent=self, model="circle", color=rgba(AMARILLO), scale=0.046, position=(cx, cy, -0.011))
        self.numero = Text(str(numero), parent=self, origin=(0, 0), position=(cx, cy, -0.012), scale=escala_fuente(15),
                           font=tipografia.FUENTE_TITULO, color=rgb(TINTA))
        self.icono = None
        self.centro_disco = (cx, cy)

    def _pintar(self):
        """El «>> ELEGIR» de la base se solaparía con la palabra de difusión («Se está difundiendo»): aquí el foco ya se ve en
        el borde amarillo grueso, así que ese rótulo se oculta. El resto de estados (FRENADA, BIEN...) siguen con su texto."""
        super()._pintar()
        if not self.is_empty() and self.etiqueta.text == ">> ELEGIR":
            self.etiqueta.text = ""

    def marcar(self, acierto):
        """Palomita verde (acierto) o aspa roja (error) sobre el círculo: el estado no depende solo del color."""
        if self.icono is not None:
            self.icono.enabled = False
            self.icono = None
        self.disco_fondo.color = rgba(VERDE if acierto else ROJO)
        self.numero.enabled = False
        pintar = icono_palomita if acierto else icono_aspa
        self.icono = pintar(self, 0.026, PAPEL, self.centro_disco, z=-0.014)


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
                             font=tipografia.FUENTE_TITULO, color=rgb(TINTA))

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


def pulsador_sello(etiqueta, al_clic, ancho, alto, px, posicion, parent, tipo="frenar"):
    """Botón grande tipo sello: FRENA = amarillo con mano; DEJA PASAR = azul-botón con flecha. Mismo contrato que ui.Boton."""
    primario = tipo == "frenar"
    boton = ui.Boton(etiqueta, al_clic, ancho, alto, px, primario=primario, parent=parent, position=posicion)
    boton.texto.x = 0.03
    x_icono = -ancho / 2 + 0.06
    if primario:
        icono_mano(boton, 0.075, TINTA, (x_icono, 0.0), z=-0.02)
    else:
        icono_flecha(boton, 0.075, estilo.PAPEL, (x_icono, 0.0), z=-0.02)
    sombra_plana(boton, ancho, alto, (0, 0), z=0.006, radio_px=8)
    return boton
