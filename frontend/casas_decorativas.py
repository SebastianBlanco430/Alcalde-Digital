# Casas decorativas (no interactivas) dibujadas en lote, a partir de las CasaDecorativa del
# backend (backend/logica/mundo_ciudad.py).
#
# Rendimiento: cada modelo .glb tiene una pieza por material (7 a 12), así que 150 casas sueltas
# serían ~1500 llamadas de dibujo, y también ~1500 en la pasada de sombras. Aquí se copian todas
# bajo una raíz y se funden con flatten_strong(): Panda junta las piezas que comparten estado
# (textura y material) en una sola geometría y hornea en los vértices la posición, el giro, la
# escala y el tinte de cada copia. A diferencia de Entity.combine() (que pierde las texturas),
# conserva el estado de cada pieza: el lote queda en una llamada por material distinto.
#
# Lo fundido ya no se puede mover ni quitar por separado: solo sirve para lo estático.
#
# Pisos: una casa con `pisos` > 1 es el mismo modelo repetido hacia arriba (cada piso, el alto del
# modelo escalado) con el tinte siguiente, como las casas que crecen por encima en una favela.

from panda3d.core import ColorAttrib, MaterialAttrib, NodePath
from ursina import Entity, load_model
from ursina.shaders import lit_with_shadows_shader

from backend.datos.modelos_edificios import modelo_de
from frontend.azar_fijo import azar_de
from frontend.componentes import rgb

TINTE_LADRILLO = (200, 124, 92)     # 2.º piso "a la vista": ladrillo sin revocar en parte de las casas


# Entity con todas las `casas` fundidas, colgada de `padre`. `tintes`: lista de (r, g, b) que
# se elige con casa.variante. `alturas`: la y de la planta baja de cada casa, o sea el `alto` de
# su apoyo (None = todas en 0).
def construir_casas(padre, casas, tintes, alturas=None):
    lote = Entity(parent=padre, shader=lit_with_shadows_shader)
    raiz = NodePath("casas_decorativas")
    fuentes = {}
    for casa, y in zip(casas, alturas or [0.0] * len(casas)):
        if casa.modelo not in fuentes:
            fuentes[casa.modelo] = _fuente(casa.modelo)
        alto_piso = modelo_de(casa.modelo).alto * casa.escala
        for piso in range(getattr(casa, "pisos", 1)):
            copia = fuentes[casa.modelo].copy_to(raiz)
            # Mismo criterio que Entity (Ursina usa y arriba): hpr = (-rotation_y, -rotation_x, rotation_z).
            copia.set_pos(casa.cx, y + piso * alto_piso, casa.cz)
            copia.set_hpr(-casa.rumbo, 0, 0)
            copia.set_scale(casa.escala)
            copia.set_color_scale(rgb(_tinte_del_piso(casa, piso, tintes)))
    raiz.clear_model_nodes()     # el ModelRoot de cada .glb impide fundir las copias entre sí
    raiz.flatten_strong()
    raiz.reparent_to(lote)
    return lote


# Tinte de un piso: el de la paleta (siguiente en cada piso) o, en el 2.º piso de la mitad de las
# casas (decidido por su posición, siempre las mismas), ladrillo a la vista.
def _tinte_del_piso(casa, piso, tintes):
    if piso == 1 and azar_de(casa.cx + 3.1, casa.cz) < 0.5:
        return TINTE_LADRILLO
    return tintes[(casa.variante + piso) % len(tintes)]


# El modelo cargado una vez, con el color base de sus materiales pasado a color plano.
def _fuente(nombre):
    fuente = load_model(modelo_de(nombre).archivo).copy_to(NodePath(nombre))
    color_base_como_color(fuente)
    return fuente


# lit_with_shadows_shader multiplica textura * color del vértice y no lee el material, así que el
# color base de los materiales glTF (las caras sin textura de los modelos) se perdería y se
# verían blancas. Se copia a un color plano por geom (en las caras con textura el factor es 1).
def color_base_como_color(nodo):
    for camino in nodo.find_all_matches("**/+GeomNode"):
        geom_node = camino.node()
        for i in range(geom_node.get_num_geoms()):
            estado = geom_node.get_geom_state(i)
            atributo = estado.get_attrib(MaterialAttrib)
            material = atributo.get_material() if atributo else None
            if material is not None and material.has_base_color():
                geom_node.set_geom_state(i, estado.set_attrib(ColorAttrib.make_flat(material.get_base_color())))


# ==================================================================================================
# Favela viva y de cómic (barrio denso): pintura vivida por piso, texturas aclaradas y contorno de tinta.
#
# Las texturas de los modelos de Blender son concreto sucio y oscuro (valor medio ~0,4): multiplicadas por un
# tinte se ven apagadas. Aquí cada textura de pared se aclara y se aplana (menos mugre, más pintura), el
# ladrillo y el zinc se avivan y cada geom recibe su color plano: paredes del tinte del piso, puertas de un
# color que contrasta, techo de zinc, teja u óxido. El contorno de tinta es el truco del casco invertido
# (ver docs/DISENO.md §7): una copia algo más grande de cada casa, sin textura, color tinta, que solo
# dibuja las caras traseras y por eso asoma como línea oscura alrededor de la silueta.
# ==================================================================================================

from panda3d.core import CullFaceAttrib, Texture, TextureAttrib
from PIL import Image, ImageStat

TINTA = (18, 20, 32)                 # RGB del contorno (el mismo de docs/DISENO.md §7)
TINTA_CASCO = (0, 0, 0)             # lo que se pinta en el casco: el shader sin luz lo aclara (gamma) y sale ~TINTA
GROSOR_CONTORNO = 0.12               # m que el casco asoma por cada lado (grosor de la línea de tinta)
SUBE_CONTORNO_PISO = 0.05            # m sobre la base de un piso de arriba a los que llega el fondo del casco (el piso de abajo no se toca)
BAJA_CONTORNO_SUELO = 0.25           # m bajo la base de la planta baja a los que llega el fondo del casco (queda bajo tierra)
# Pinturas vivas de las fachadas (albedo RGB 0-255): turquesa, rosa, amarillo, naranja, lima, cobalto,
# rojo ladrillo, lila, crema, verde agua, coral, celeste.
PINTURAS = (
    (70, 214, 200), (248, 120, 168), (255, 220, 84), (255, 148, 58), (166, 224, 84), (82, 140, 244),
    (226, 90, 72), (190, 140, 238), (240, 206, 140), (120, 214, 158), (255, 128, 108), (140, 208, 255),
)
PUERTAS = ((44, 112, 226), (236, 64, 64), (252, 204, 44), (34, 166, 112), (252, 124, 32), (146, 66, 204))
# Techos: (color, peso): zinc plateado, teja anaranjada, chapa oxidada, zinc azulado.
TECHOS = (((150, 164, 184), 0.42), ((214, 112, 78), 0.28), ((184, 112, 74), 0.15), ((80, 128, 196), 0.15))
PROBABILIDAD_LADRILLO_BAJO = 0.20    # fracción de plantas bajas con la pared de ladrillo sin revocar
PROBABILIDAD_LADRILLO_ALTO = 0.42    # ídem en los pisos de arriba
COLOR_LOSA = (132, 134, 150)         # losas, antepechos y marcos sin textura: concreto gris azulado
TINTE_LADRILLO_VIVO = (255, 156, 124)   # tinte del ladrillo visto: rojo terracota
BRILLO_PARED = 176                   # valor (0-255) al que se lleva la media de las texturas de pared
CONTRASTE_PARED = 0.7                # fracción de la mugre original que se conserva en las paredes
POTENCIA_TECHO = 0.55                # <1 aclara el zinc
POTENCIA_LADRILLO = 0.62             # <1 aclara el ladrillo
POTENCIA_LATERAL = 0.80              # <1 aclara puertas y ventanas (no se aplanan)


# Clase de un geom según el nombre de su textura (None = sin textura).
def clase_de_textura(nombre):
    if not nombre:
        return "otro"
    n = nombre.lower()
    if "door" in n or "garage" in n:
        return "puerta"
    if "roof" in n:
        return "techo"
    if "brick" in n or "clinker" in n:
        return "ladrillo"
    if "concrete" in n or "plaster" in n:
        return "pared"
    return "ventana"


# Copia de la textura `tex` con los valores corregidos por `lut(canal) -> lista de 256 valores` por canal
# RGB (las texturas sin alfa o con él: el alfa no se toca). Mantiene el envoltorio y el filtrado.
def _textura_corregida(tex, tablas):
    ancho, alto = tex.get_x_size(), tex.get_y_size()
    datos = bytes(tex.get_ram_image_as("RGB"))
    imagen = Image.frombytes("RGB", (ancho, alto), datos)
    r, g, b = imagen.split()
    imagen = Image.merge("RGB", (r.point(tablas[0]), g.point(tablas[1]), b.point(tablas[2])))
    nueva = Texture(tex.get_name() + "_viva")
    nueva.setup_2d_texture(ancho, alto, Texture.T_unsigned_byte, Texture.F_rgb)
    nueva.set_ram_image_as(imagen.tobytes(), "RGB")
    nueva.set_wrap_u(tex.get_wrap_u())
    nueva.set_wrap_v(tex.get_wrap_v())
    nueva.set_minfilter(Texture.FT_linear_mipmap_linear)
    nueva.set_magfilter(Texture.FT_linear)
    nueva.set_anisotropic_degree(4)
    return nueva


# Tabla (256 valores) que lleva la media de la textura a `brillo` y reduce su contraste a `contraste`.
def _tabla_pared(tex):
    imagen = Image.frombytes("RGB", (tex.get_x_size(), tex.get_y_size()), bytes(tex.get_ram_image_as("RGB")))
    medias = ImageStat.Stat(imagen).mean
    return [[int(min(255, max(0, BRILLO_PARED + (v - medias[c]) * CONTRASTE_PARED))) for v in range(256)] for c in range(3)]


def _tabla_potencia(potencia):
    tabla = [int(255 * (v / 255) ** potencia) for v in range(256)]
    return [tabla, tabla, tabla]


class _Texturas:
    """Texturas de los modelos ya corregidas (una vez por textura): aclaradas y con la mugre atenuada."""

    def __init__(self):
        self._cache = {}

    def de(self, tex, clase):
        clave = (tex.get_name(), clase)
        if clave not in self._cache:
            if clase == "pared":
                tablas = _tabla_pared(tex)
            elif clase == "techo":
                tablas = _tabla_potencia(POTENCIA_TECHO)
            elif clase == "ladrillo":
                tablas = _tabla_potencia(POTENCIA_LADRILLO)
            else:
                tablas = _tabla_potencia(POTENCIA_LATERAL)
            self._cache[clave] = _textura_corregida(tex, tablas)
        return self._cache[clave]

    # La textura de ladrillo avivada, para las paredes sin revocar.
    def ladrillo_vivo(self):
        return self.de(_textura_ladrillo_de_referencia(), "ladrillo")


# Estilo de pintura de un piso: (índice de pintura, ¿ladrillo visto?, índice de techo). Depende solo de la
# posición de la casa y del piso: siempre sale igual.
def estilo_del_piso(casa, piso):
    u = azar_de(casa.cx * 0.73 + piso * 5.1, casa.cz * 1.31 + casa.variante)
    pintura = int(u * len(PINTURAS)) % len(PINTURAS)
    p_ladrillo = PROBABILIDAD_LADRILLO_BAJO if piso == 0 else PROBABILIDAD_LADRILLO_ALTO
    ladrillo = azar_de(casa.cx + 3.1 + piso, casa.cz) < p_ladrillo
    v = azar_de(casa.cz * 0.9 + 7.7, casa.cx * 1.1 + piso)
    acumulado, techo = 0.0, 0
    for i, (_, peso) in enumerate(TECHOS):
        acumulado += peso
        if v < acumulado:
            techo = i
            break
    return pintura, ladrillo, techo


# Pinta una copia de un modelo (`fuente`, ya independiente del caché de Ursina): texturas corregidas y color
# plano por geom según su clase. `pared`, `puerta` y `techo` son colores de Ursina; `ladrillo` deja la pared
# de ladrillo visto en vez de pintada.
def pintar_modelo(fuente, pared, puerta, techo, ladrillo, texturas):
    color_base_como_color(fuente)
    tonos = {"pared": pared, "puerta": puerta, "techo": techo}
    blanco = rgb((255, 255, 255))
    for camino in fuente.find_all_matches("**/+GeomNode"):
        nodo = camino.node()
        for i in range(nodo.get_num_geoms()):
            estado = nodo.get_geom_state(i)
            atributo = estado.get_attrib(TextureAttrib)
            tex = atributo.get_texture() if atributo else None
            if tex is None:                              # sin textura: losas y antepechos de concreto
                nodo.set_geom_state(i, estado.set_attrib(ColorAttrib.make_flat(rgb(COLOR_LOSA))))
                continue
            clase = clase_de_textura(tex.get_name())
            if clase == "pared" and ladrillo:            # pared sin revocar: ladrillo visto, rojo terracota
                estado = estado.set_attrib(TextureAttrib.make(texturas.ladrillo_vivo()))
                nodo.set_geom_state(i, estado.set_attrib(ColorAttrib.make_flat(rgb(TINTE_LADRILLO_VIVO))))
                continue
            estado = estado.set_attrib(TextureAttrib.make(texturas.de(tex, clase)))
            nodo.set_geom_state(i, estado.set_attrib(ColorAttrib.make_flat(tonos.get(clase, blanco))))
    return fuente


# Fuente tinteada de un modelo para las casas del barrio (según el estilo de un piso).
def _fuente_viva(nombre, pintura, ladrillo, techo, texturas):
    fuente = load_model(modelo_de(nombre).archivo).copy_to(NodePath(f"{nombre}_{pintura}_{int(ladrillo)}_{techo}"))
    return pintar_modelo(fuente, rgb(PINTURAS[pintura]), rgb(PUERTAS[(pintura * 3 + 1) % len(PUERTAS)]),
                         rgb(TECHOS[techo][0]), ladrillo, texturas)


_TEXTURAS_COMPARTIDAS = []


# Copia independiente y pintada del modelo `nombre` para un edificio jugable (`pared`, `puerta`, `techo`: RGB
# 0-255): no toca el modelo que cachea Ursina, así las casas del barrio no se contagian.
def modelo_pintado(nombre, pared, puerta, techo):
    if not _TEXTURAS_COMPARTIDAS:
        _TEXTURAS_COMPARTIDAS.append(_Texturas())
    fuente = load_model(modelo_de(nombre).archivo).copy_to(NodePath(f"{nombre}_pintado"))
    return pintar_modelo(fuente, rgb(pared), rgb(puerta), rgb(techo), False, _TEXTURAS_COMPARTIDAS[0])


# Pone y escala `casco` (copia de _casco) sobre una casa: engrosado GROSOR_CONTORNO a cada lado en planta, con el fondo
# a `inferior` m de la base del piso y el tope `GROSOR_CONTORNO` sobre su techo. La escala vertical sale de esos dos
# límites (el modelo mide `alto` + `hondo` de plinto) y el origen se sube lo que baja el plinto: así el casco de un piso de
# arriba no se mete en el techo del de abajo (donde parpadearía contra él).
def _colocar_casco(casco, m, casa, estiramiento, base, alto_piso, inferior):
    t = GROSOR_CONTORNO
    sy = (alto_piso + t - inferior) / (m.alto + m.hondo)
    casco.set_pos(base[0], base[1] + inferior + m.hondo * sy, base[2])
    casco.set_hpr(-casa.rumbo, 0, 0)
    casco.set_scale(casa.escala + 2 * t / m.frente, sy, casa.escala * estiramiento + 2 * t / m.fondo)


# Casco de tinta de `nombre` listo para colgar, ya colocado: base del modelo en `posicion` (x, y, z), girado `rumbo`
# (rotation_y en grados, convención de Ursina) y escalado `escala` (y `estiramiento` en profundidad).
def casco_de_modelo(nombre, escala, posicion, rumbo, estiramiento=1.0):
    m = modelo_de(nombre)
    casco = _casco(nombre)
    t = GROSOR_CONTORNO
    sy = (m.alto * escala + t + BAJA_CONTORNO_SUELO) / (m.alto + m.hondo)
    casco.set_pos(posicion[0], posicion[1] - BAJA_CONTORNO_SUELO + m.hondo * sy, posicion[2])
    casco.set_hpr(-rumbo, 0, 0)
    casco.set_scale(escala + 2 * t / m.frente, sy, escala * estiramiento + 2 * t / m.fondo)
    return casco


_REFERENCIA_LADRILLO = []


# La textura de ladrillo original ("Bricks047...") tomada de casa3, para las paredes sin revocar.
def _textura_ladrillo_de_referencia():
    if not _REFERENCIA_LADRILLO:
        modelo = load_model(modelo_de("casa3").archivo)
        for camino in modelo.find_all_matches("**/+GeomNode"):
            nodo = camino.node()
            for i in range(nodo.get_num_geoms()):
                atributo = nodo.get_geom_state(i).get_attrib(TextureAttrib)
                tex = atributo.get_texture() if atributo else None
                if tex is not None and "bricks" in tex.get_name().lower():
                    _REFERENCIA_LADRILLO.append(tex)
                    return tex
        raise ValueError("No se encontró la textura de ladrillo en casa3.")
    return _REFERENCIA_LADRILLO[0]


# Entity con todas las `casas` fundidas (pisos con su pintura viva) colgada de `padre`; devuelve
# (lote, contorno): `contorno` es la Entity del casco de tinta (None si contorno=False), que el llamador
# debe colgar donde convenga (fuera del mapa de sombras). `alturas`: la y de la planta baja de cada casa.
def construir_casas_favela(padre, casas, alturas=None, contorno=True):
    lote = Entity(parent=padre, shader=lit_with_shadows_shader)
    raiz = NodePath("casas_favela")
    raiz_tinta = NodePath("contorno_casas") if contorno else None
    texturas = _Texturas()
    fuentes, cascos = {}, {}
    for casa, y in zip(casas, alturas or [0.0] * len(casas)):
        m = modelo_de(casa.modelo)
        alto_piso = m.alto * casa.escala
        est = getattr(casa, "estiramiento", 1.0)
        for piso in range(getattr(casa, "pisos", 1)):
            estilo = estilo_del_piso(casa, piso)
            clave = (casa.modelo,) + estilo
            if clave not in fuentes:
                fuentes[clave] = _fuente_viva(casa.modelo, *estilo, texturas)
            copia = fuentes[clave].copy_to(raiz)
            copia.set_pos(casa.cx, y + piso * alto_piso, casa.cz)
            copia.set_hpr(-casa.rumbo, 0, 0)
            copia.set_scale(casa.escala, casa.escala, casa.escala * est)
            if raiz_tinta is not None:
                if casa.modelo not in cascos:
                    cascos[casa.modelo] = _casco(casa.modelo)
                casco = cascos[casa.modelo].copy_to(raiz_tinta)
                inferior = SUBE_CONTORNO_PISO if piso else -BAJA_CONTORNO_SUELO
                _colocar_casco(casco, m, casa, est, (casa.cx, y + piso * alto_piso, casa.cz), alto_piso, inferior)
    raiz.clear_model_nodes()
    raiz.flatten_strong()
    raiz.reparent_to(lote)
    tinta = None
    if raiz_tinta is not None:
        raiz_tinta.clear_model_nodes()
        raiz_tinta.flatten_strong()
        tinta = Entity(parent=padre, shader=None, name="contorno_de_casas")
        raiz_tinta.reparent_to(tinta)
        tinta.set_light_off()
    return lote, tinta


# Clases de geom que NO entran en el casco de tinta (se llenan en _casco): los planos de grosor cero (láminas de
# techo, antepechos de una sola cara) dejarían una copia casi pegada al plano real que parpadea contra él.
CLASES_SIN_CASCO = ("techo",)


# Casco de tinta de un modelo: la misma geometría sin texturas ni materiales, de color tinta, a una cara.
def _casco(nombre):
    casco = load_model(modelo_de(nombre).archivo).copy_to(NodePath(f"casco_{nombre}"))
    if CLASES_SIN_CASCO:
        for camino in casco.find_all_matches("**/+GeomNode"):
            nodo = camino.node()
            for i in reversed(range(nodo.get_num_geoms())):
                atributo = nodo.get_geom_state(i).get_attrib(TextureAttrib)
                tex = atributo.get_texture() if atributo else None
                if clase_de_textura(tex.get_name() if tex else None) in CLASES_SIN_CASCO:
                    nodo.remove_geom(i)
    casco.set_texture_off(1000)
    casco.set_material_off(1000)
    casco.set_color(rgb_plano(TINTA_CASCO), 1000)
    # solo caras traseras: el casco asoma como línea por detrás de la silueta (con prioridad alta para que
    # no lo pisen los estados propios de los geoms del modelo)
    casco.set_attrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise), 1000)
    return casco


# Color de Panda (0-1) de una tupla RGB 0-255.
def rgb_plano(tupla):
    return (tupla[0] / 255, tupla[1] / 255, tupla[2] / 255, 1.0)
