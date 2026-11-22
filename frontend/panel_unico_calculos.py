# Un solo estilo de panel para el HUD del mundo (M3.3, docs/DISENO.md §4). Python puro (sin ursina ni panda3d).
#
# Todos los bloques del HUD se pintan con componentes.panel_tinta (cara + borde de tinta + sombra plana) y, según su
# CATEGORÍA, con el mismo radio, el mismo borde y el mismo relleno interior:
#   chip     una línea de texto (misión, chip del lugar, reloj, dinero, dilema, hábito, botón del teléfono, toast,
#            avisos «E» y genérico): radio 6 px, borde 2 px (HUD denso), relleno 8 px
#   tarjeta  bloques de varias filas (franja de confianza/desinformación, marco del minimapa, pulseras): radio 10 px,
#            borde 2 px, relleno 12 px
# Los px son los de componentes.a_unidades (alto de referencia 600 px), los mismos que ya usa panel_tinta.
#
# Bandera reversible: PANEL_UNICO / ALCALDE_PANEL_UNICO=0 deja cada bloque con su fondo de antes.

import os
from dataclasses import dataclass

from frontend import estilo

PANEL_UNICO = True
ALTO_REFERENCIA_PX = 600                       # = componentes.ALTO_REFERENCIA_PX
ESCALA_PX = (4, 8, 12, 16, 24, 32)              # escala de espaciados de DISENO.md §4
RADIOS_DISENO = (estilo.RADIO_CHIP_PX, estilo.RADIO_TARJETA_PX, estilo.RADIO_PANEL_PX)
BORDES_DISENO = (estilo.GROSOR_BORDE_DENSO_PX, estilo.GROSOR_BORDE_PX)


@dataclass(frozen=True)
class EstiloPanel:
    radio_px: int
    borde_px: int
    relleno_px: int
    tono: tuple = estilo.COLOR_FONDO

    @property
    def relleno(self):
        """Relleno interior en unidades de camera.ui."""
        return self.relleno_px / ALTO_REFERENCIA_PX


CHIP, TARJETA = "chip", "tarjeta"
CATEGORIAS = {
    CHIP: EstiloPanel(estilo.RADIO_CHIP_PX, estilo.GROSOR_BORDE_DENSO_PX, 8),
    TARJETA: EstiloPanel(estilo.RADIO_TARJETA_PX, estilo.GROSOR_BORDE_DENSO_PX, 12),
}

BLOQUES = {
    "mision": CHIP, "lugar": CHIP, "reloj": CHIP, "dinero": CHIP, "dilema": CHIP, "habito": CHIP,
    "telefono": CHIP, "toast": CHIP, "aviso_e": CHIP, "aviso": CHIP,
    "franja": TARJETA, "minimapa": TARJETA, "pulseras": TARJETA,
}


def activo():
    """¿Estilo único? ALCALDE_PANEL_UNICO=1/0 manda sobre la constante PANEL_UNICO."""
    valor = os.environ.get("ALCALDE_PANEL_UNICO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PANEL_UNICO)


def estilo_de(bloque):
    """EstiloPanel del bloque del HUD (KeyError si el bloque no está en el mapa: así no se cuela uno sin estilo)."""
    return CATEGORIAS[BLOQUES[bloque]]


def relleno(bloque):
    return estilo_de(bloque).relleno


def alto_una_linea(px, bloque="mision", interlineado=1.2):
    """Alto (unidades) de un chip de una línea de `px` con el relleno de su categoría arriba y abajo."""
    return px / ALTO_REFERENCIA_PX * interlineado + 2 * relleno(bloque)


def extension_px(bloque):
    """Cuánto sobresalen borde y sombra plana de la cara del panel, por lado (px de referencia 600):
    el borde rodea la cara y la sombra se desplaza estilo.DESPLAZAMIENTO_SOMBRA_PX (+x, -y)."""
    borde = estilo_de(bloque).borde_px
    dx, dy = estilo.DESPLAZAMIENTO_SOMBRA_PX
    return {"izquierda": borde, "arriba": borde, "derecha": borde + max(0, dx), "abajo": borde + max(0, -dy)}
