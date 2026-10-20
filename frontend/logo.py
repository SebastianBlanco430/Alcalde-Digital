# Wordmark «Alcalde Digital» dibujado por código (T7, docs/DISENO.md sección 1 y 6):
#   «ALCALDE» en la fuente de títulos, amarillo, con una copia de tinta desplazada detrás
#   (sombra dura); debajo «DIGITAL» sobre una placa cian con borde de tinta, inclinada;
#   y sobre la «A» un rombo amarillo con borde de tinta (la baliza del juego) a modo de pin.
from panda3d.core import TextNode
from ursina import Entity, Text, destroy

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, escala_fuente, panel_tinta, rgb
from frontend.fondo_menu import malla_rombo

PX_ALCALDE = 76
PX_DIGITAL = 30
SOMBRA_PX = (5, -5)
INCLINACION_PLACA = 2.0       # grados (la placa gira en sentido antihorario visto en pantalla)
PALABRA = "ALCALDE"
SEGUNDA = "DIGITAL"


# Ancho (unidades de camera.ui) de `cadena` en la fuente de títulos a `px` px.
def medir_titulo(cadena, px):
    nodo = TextNode("medida")
    texto = Text("", add_to_scene_entities=False, font=tipografia.FUENTE_TITULO)
    nodo.setFont(texto.font)
    ancho = nodo.calcWidth(cadena) * texto.size * escala_fuente(px)
    destroy(texto)
    return ancho


# Crea el wordmark centrado en su `position`. Devuelve un Entity con los hijos
# .texto_principal (ALCALDE amarillo), .texto_sombra, .placa (DIGITAL) y .baliza (rombo).
def crear_wordmark(padre, **opciones):
    raiz = Entity(parent=padre, **opciones)
    dx, dy = a_unidades(SOMBRA_PX[0]), a_unidades(SOMBRA_PX[1])
    escala = escala_fuente(PX_ALCALDE)

    raiz.texto_sombra = Text(
        PALABRA, parent=raiz, origin=(0, 0), position=(dx, dy, 0.002), scale=escala,
        font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))
    raiz.texto_principal = Text(
        PALABRA, parent=raiz, origin=(0, 0), position=(0, 0, 0), scale=escala,
        font=tipografia.FUENTE_TITULO, color=rgb(estilo.ACENTO_PRIMARIO))

    ancho_palabra = medir_titulo(PALABRA, PX_ALCALDE)
    ancho_a = medir_titulo("A", PX_ALCALDE)

    # Placa «DIGITAL»: cian con borde de tinta, ligeramente inclinada, bajo la palabra.
    ancho_placa = medir_titulo(SEGUNDA, PX_DIGITAL) + a_unidades(36)
    alto_placa = a_unidades(PX_DIGITAL + 16)
    raiz.placa = panel_tinta(raiz, ancho_placa, alto_placa, estilo.ACENTO_SECUNDARIO, 8,
                             position=(0, -a_unidades(PX_ALCALDE * 0.78), -0.001))
    raiz.placa.rotation_z = -INCLINACION_PLACA
    raiz.texto_placa = Text(
        SEGUNDA, parent=raiz.placa, origin=(0, 0), position=(0, 0, -0.001),
        scale=escala_fuente(PX_DIGITAL), font=tipografia.FUENTE_TITULO, color=rgb(estilo.TINTA))

    # Baliza sobre la «A» (primera letra): rombo amarillo con borde de tinta.
    lado = a_unidades(34)
    x_a = -ancho_palabra / 2 + ancho_a / 2
    raiz.baliza = Entity(parent=raiz, position=(x_a, a_unidades(PX_ALCALDE * 0.68), -0.002))
    Entity(parent=raiz.baliza, model=malla_rombo(), scale=(lado * 1.34, lado * 1.7),
           color=rgb(estilo.TINTA), z=0.001)
    Entity(parent=raiz.baliza, model=malla_rombo(), scale=(lado, lado * 1.3),
           color=rgb(estilo.ACENTO_PRIMARIO))
    raiz.ancho = ancho_palabra
    return raiz
