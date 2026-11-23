# Papel, texto legible sobre papel y resaltado de selección para los minijuegos 3D (Ursina). Unidades: METROS en el espacio
# local de un ANCLA del set (sets.Ancla.entidad: +x derecha, +y arriba, cara visible hacia -z). Todo lo de aquí cuelga de
# un padre así y queda DELANTE de la superficie (z negativo).
#
# Capas (z local, m; ver contrato «Reglas de render»): superficie 0 · borde de resaltado -0.003 · papel -0.004 (cada papel
# apilado -0.002 más) · texto -0.0015 delante de su papel. Sin z-fighting con near 0.03 m: a 1-2 m de la cámara la
# resolución de profundidad es de micras.
#
#   hoja = papel(ancla.entidad, 0.30, 0.20, posicion=(x, y), giro=3)             # quad con luz y sombra cel
#   t = texto_en_papel(hoja, "Rumor...", alto_linea=0.016, ancho=0.27)            # tipografía de los minijuegos
#   marco = resaltar(hoja, True)  /  resaltar(hoja, False)                         # borde amarillo como el foco de hoy
#
# Texto: misma fuente que los minijuegos (frontend/tipografia: Atkinson Hyperlegible), mismo ajuste de líneas que
# frontend/minijuegos/ui.lineas_de (proporcional), sin escribir profundidad (la tinta de pantalla no lo erosiona, R3a de
# frontend/piezas.texto_sin_tinta) y en el bin transparente (se dibuja después del papel).

from ursina import Entity, Text, color
from ursina.shaders import lit_with_shadows_shader

from frontend import estilo, tipografia
from frontend.componentes import a_unidades, destruir_arbol, escala_fuente, rgb
from frontend.minijuegos import ui as ui_2d
from frontend.piezas import texto_sin_tinta

PAPEL = (250, 246, 232)
TINTA = (34, 30, 40)
PX_REFERENCIA = 18                # px de referencia para envolver (no cambia el tamaño real: lo da alto_linea)
Z_PAPEL = -0.004
Z_BORDE = -0.003
Z_TEXTO = -0.0015
GROSOR_RESALTADO = 0.008          # m del borde amarillo alrededor del papel
# Alto de línea (m) MÍNIMO para que el texto mida >= 14 px a 1280x720 (y por tanto >= 18 px a 1920x1080) con la toma de la
# familia, medido con el arnés (rework-3d/arnes, altura_texto_px) en el peor papel (el más lejano). Corcho: sala de
# investigación (corcho de 1,2 m de alto); en la oficina (corcho de 1,05 m) basta un 12 % menos. Mesa: cuarto_mesa.
ALTO_LINEA_MINIMO = {"corcho": 0.027, "mesa": 0.017}


def papel(padre, ancho, alto, posicion=(0.0, 0.0), giro=0.0, tono=PAPEL, capa=0, iluminado=True, **opciones):
    """Hoja de `ancho` x `alto` m centrada en `posicion` (x, y locales del padre), girada `giro` grados en su plano.
    `capa` la apila delante de otras (cada capa 2 mm). Devuelve la Entity (quad); sus hijos usan ESCALA 1 = metros
    gracias a un pivote sin escalar: usa `hoja.contenido` como padre del texto."""
    pivote = Entity(parent=padre, position=(posicion[0], posicion[1], Z_PAPEL - 0.002 * capa), rotation_z=giro, **opciones)
    hoja = Entity(parent=pivote, model="quad", color=rgb(tono), scale=(ancho, alto),
                  shader=lit_with_shadows_shader if iluminado else None)
    pivote.hoja = hoja
    pivote.ancho, pivote.alto = ancho, alto
    pivote.contenido = pivote             # el texto va en el pivote (sin escala): coordenadas en metros
    pivote.resaltado = None
    return pivote


def texto_en_papel(hoja, cadena, alto_linea=0.016, ancho=None, tono=TINTA, posicion=None, negrita=False, centrado=False):
    """Texto envuelto a `ancho` m con líneas de `alto_linea` m. `posicion` (x, y) es la esquina superior izquierda en el
    papel (por defecto, el margen de arriba a la izquierda). Devuelve el Text (con .n_lineas y .alto en m)."""
    ancho = ancho if ancho is not None else hoja.ancho * 0.88
    k = alto_linea / a_unidades(PX_REFERENCIA)               # metros por unidad de UI
    lineas = ui_2d.lineas_de(str(cadena), PX_REFERENCIA, ancho / k, negrita)
    if posicion is None:
        posicion = (-hoja.ancho / 2 + (hoja.ancho - ancho) / 2, hoja.alto / 2 - (hoja.alto * 0.06))
    t = Text("\n".join(lineas), parent=hoja.contenido, origin=(0, 0.5) if centrado else (-0.5, 0.5),
             position=(0 if centrado else posicion[0], posicion[1], Z_TEXTO), scale=escala_fuente(PX_REFERENCIA) * k,
             color=rgb(tono), font=tipografia.FUENTE_TITULO if negrita else tipografia.FUENTE_TEXTO)
    t.line_height = ui_2d.LINEA
    t.n_lineas = len(lineas)
    t.alto = len(lineas) * alto_linea * ui_2d.LINEA
    texto_sin_tinta(t)
    t.setBin("transparent", 20)
    return t


def resaltar(hoja, activo, tono=None, grosor=GROSOR_RESALTADO):
    """Borde amarillo (el COLOR_FOCO de los minijuegos de hoy) detrás de `hoja` (un papel()). Idempotente."""
    if not activo:
        if getattr(hoja, "resaltado", None) is not None:
            destruir_arbol(hoja.resaltado)
            hoja.resaltado = None
        return None
    if getattr(hoja, "resaltado", None) is not None:
        return hoja.resaltado
    hoja.resaltado = Entity(parent=hoja, model="quad", color=rgb(tono or ui_2d.COLOR_FOCO),
                            scale=(hoja.ancho + 2 * grosor, hoja.alto + 2 * grosor), z=Z_BORDE - Z_PAPEL + 0.001, shader=None)
    return hoja.resaltado


def chincheta(padre, posicion, tono=None):
    """Chincheta (esfera + aguja) en (x, y) local del padre."""
    c = Entity(parent=padre, model="sphere", color=rgb(tono or estilo.ESTADO_ERROR), scale=0.018,
               position=(posicion[0], posicion[1], Z_PAPEL - 0.012), shader=lit_with_shadows_shader)
    return c


def color_tinta():
    return color.rgb32(*TINTA)
