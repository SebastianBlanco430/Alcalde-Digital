# Pantallas «Sesión iniciada» y «Sesión cerrada» del monitor de Civitas (interior de los edificios).
#
# Cada pantalla es UNA textura dibujada con Pillow (sin entidades nuevas: 0 costo por frame) con el estilo
# «cómic cívico» de docs/DISENO.md: fondo de tinta con semitono, banderines de fiesta de barrio arriba (los de
# las calles de la favela), tarjeta con borde de tinta y sombra plana, amarillo para lo importante y cian para
# la información, y la fuente Atkinson Hyperlegible. Reutiliza el logo de Civitas (red_social_iconos) y los
# retratos de rol (iconos). Los textos y las cajas viven en pantalla_monitor_calculos.py (puro).
#
#   imagen_inicio(rol, nombre_rol, color_rol, jugador, lugar)   -> PIL.Image RGBA
#   imagen_cierre(rol, nombre_rol, color_rol, lugar, resultado) -> PIL.Image RGBA
#   textura_inicio(...) / textura_cierre(...)                   -> Texture de Ursina (caché pequeña)
#
# La barra de carga NO va en la textura: es un quad hijo de la pantalla (escena_interior) que se estira con el
# tramo de tecleo; aquí solo se dibuja su carril. Bandera PANTALLAS_CIVITAS: False = el fondo azul liso con
# texto blanco de antes.

from collections import OrderedDict

from PIL import Image, ImageDraw, ImageFont

from backend.datos.nombres_visibles import glosar_texto, nombre_visible
from frontend import estilo, iconos, red_social_iconos, tipografia
from frontend import pantalla_monitor_calculos as pmc

PANTALLAS_CIVITAS = True
TEXTURAS_EN_CACHE = 4        # texturas guardadas (1280 x 720 RGBA = 3,7 MB cada una)

COLOR_RELLENO_BARRA = estilo.ACENTO_PRIMARIO
_ROSA = (240, 98, 120)
_VERDE = estilo.ESTADO_EXITO
_BANDERINES = (estilo.ACENTO_PRIMARIO, estilo.ACENTO_SECUNDARIO, _ROSA, _VERDE, estilo.PAPEL)
_TONO_CAMBIO = {"bueno": estilo.ESTADO_EXITO, "malo": estilo.ESTADO_ERROR, "igual": estilo.COLOR_TEXTO_TENUE}
_SOMBRA_PX = 12              # desplazamiento de la sombra plana de la tarjeta
_BORDE_PX = 6                # borde de tinta de la tarjeta (a 1280 px)


def _fuente(px, negrita=False):
    nombre = tipografia.FUENTE_TITULO if negrita else tipografia.FUENTE_TEXTO
    return ImageFont.truetype(str(tipografia.ruta_fuente(nombre)), px)


def _rgba(rgb, alfa=255):
    return (*rgb, alfa)


# Fondo de tinta con puntos de semitono en la esquina inferior derecha (cómic).
def _fondo():
    img = Image.new("RGBA", (pmc.ANCHO_PX, pmc.ALTO_PX), _rgba(estilo.COLOR_FONDO))
    d = ImageDraw.Draw(img)
    paso = 26
    for j, y in enumerate(range(pmc.ALTO_PX // 2, pmc.ALTO_PX + paso, paso)):
        for x in range(pmc.ANCHO_PX // 2 + (paso // 2) * (j % 2), pmc.ANCHO_PX + paso, paso):
            fuerza = min(1.0, (x - pmc.ANCHO_PX / 2) / (pmc.ANCHO_PX / 2) + (y - pmc.ALTO_PX / 2) / pmc.ALTO_PX)
            r = 1 + int(5 * max(0.0, fuerza))
            d.ellipse((x - r, y - r, x + r, y + r), fill=_rgba(estilo.COLOR_PANEL))
    _banderines(d)
    return img


# Guirnalda de banderines triangulares de colores con borde de tinta, colgando de una cuerda en curva.
def _banderines(d):
    cantidad = 22
    ancho = pmc.ANCHO_PX / cantidad
    d.line([(k * ancho, 9 + 18 * (1 - ((k / cantidad) * 2 - 1) ** 2)) for k in range(cantidad + 1)],
           fill=_rgba(estilo.COLOR_TEXTO_TENUE), width=4)
    for k in range(cantidad):
        x0 = k * ancho
        caida = 18 * (1 - ((k + 0.5) / cantidad * 2 - 1) ** 2)       # la cuerda cuelga en el centro
        y = 10 + caida
        tono = _BANDERINES[k % len(_BANDERINES)]
        d.polygon(((x0 + 4, y), (x0 + ancho - 4, y), (x0 + ancho / 2, y + 44)),
                  fill=_rgba(tono), outline=_rgba(estilo.TINTA), width=3)


# Rectángulo redondeado con borde de tinta y sombra plana desplazada (los paneles del juego).
def _tarjeta(d, caja, relleno, radio=22):
    x0, y0, x1, y1 = caja
    d.rounded_rectangle((x0 + _SOMBRA_PX, y0 + _SOMBRA_PX, x1 + _SOMBRA_PX, y1 + _SOMBRA_PX), radio,
                        fill=_rgba(estilo.TINTA))
    d.rounded_rectangle(caja, radio, fill=_rgba(relleno), outline=_rgba(estilo.TINTA), width=_BORDE_PX)


# Texto con contorno de tinta (títulos de cómic).
def _texto(d, xy, cadena, px, color, negrita=False, contorno=0, ancla="la"):
    d.text(xy, cadena, font=_fuente(px, negrita), fill=_rgba(color), anchor=ancla,
           stroke_width=contorno, stroke_fill=_rgba(estilo.TINTA))


# Corta `cadena` con «...» para que quepa en `ancho` px con la fuente dada.
def _ajustar(d, cadena, px, ancho, negrita=False):
    fuente = _fuente(px, negrita)
    if d.textlength(cadena, font=fuente) <= ancho:
        return cadena
    while cadena and d.textlength(cadena + "...", font=fuente) > ancho:
        cadena = cadena[:-1]
    return cadena.rstrip() + "..."


# Mayor tamaño entre `px` y `px_min` con el que `cadena` cabe en `ancho` (si ni así cabe, `px_min`).
def _px_que_cabe(d, cadena, px, px_min, ancho, negrita=False):
    while px > px_min and d.textlength(cadena, font=_fuente(px, negrita)) > ancho:
        px -= 2
    return max(px, px_min)


# Logo de Civitas y su nombre arriba a la izquierda (con `grande`, el de la pantalla de inicio).
def _cabecera(img, d, grande):
    lado = 150 if grande else 96
    img.alpha_composite(red_social_iconos.dibujar_logo(lado), (72, 70))
    px = 92 if grande else 60
    _texto(d, (72 + lado + 28, 70 + lado / 2 - (14 if grande else 6)), pmc.TITULO, px, estilo.PAPEL,
           negrita=True, contorno=5, ancla="lm")
    _texto(d, (72 + lado + 32, 70 + lado / 2 + px * 0.55), pmc.SUBTITULO, 30 if grande else 26,
           estilo.ACENTO_SECUNDARIO, ancla="lm")


# Retrato del rol dentro de un aro del color del rol con borde de tinta.
def _retrato(img, d, rol, color_rol):
    x0, y0, x1, y1 = pmc.CAJA_RETRATO
    d.ellipse((x0 - 8, y0 - 8, x1 + 8, y1 + 8), fill=_rgba(estilo.TINTA))
    d.ellipse((x0 - 2, y0 - 2, x1 + 2, y1 + 2), fill=_rgba(color_rol))
    d.ellipse((x0 + 12, y0 + 12, x1 - 12, y1 - 12), fill=_rgba(estilo.PAPEL), outline=_rgba(estilo.TINTA), width=4)
    lado = x1 - x0 - 40
    retrato = iconos.dibujar_retrato(rol, lado) if rol in iconos.ROLES_RETRATO else iconos.dibujar_icono("mision", lado)
    img.alpha_composite(retrato, (x0 + 20, y0 + 20))


# Chip amarillo con texto de tinta (el lugar).
def _chip(d, x, y, cadena, px=28):
    fuente = _fuente(px, True)
    ancho = d.textlength(cadena, font=fuente)
    d.rounded_rectangle((x, y, x + ancho + 36, y + px + 22), 12, fill=_rgba(estilo.ACENTO_PRIMARIO),
                        outline=_rgba(estilo.TINTA), width=4)
    d.text((x + 18, y + 11), cadena, font=fuente, fill=_rgba(estilo.TINTA))


# Franja inferior con el mensaje corto (comillas de cómic).
def _mensaje(d, cadena):
    x0, y0, x1, y1 = pmc.CAJA_MENSAJE
    cadena = f"« {cadena} »"
    px = _px_que_cabe(d, cadena, 30, 24, x1 - x0 - 40)
    cadena = _ajustar(d, cadena, px, x1 - x0 - 40)
    _texto(d, ((x0 + x1) / 2, (y0 + y1) / 2), cadena, px, estilo.PAPEL, ancla="mm")


def imagen_inicio(rol, nombre_rol, color_rol, jugador, lugar):
    img = _fondo()
    d = ImageDraw.Draw(img)
    _cabecera(img, d, grande=True)
    _tarjeta(d, pmc.CAJA_TARJETA, estilo.COLOR_PANEL)
    _retrato(img, d, rol, color_rol)
    x = pmc.CAJA_BARRA[0]
    ancho = pmc.CAJA_TARJETA[2] - x - 40
    _texto(d, (x, 292), pmc.ETIQUETA_INICIO, 30, estilo.ACENTO_SECUNDARIO, negrita=True)
    _texto(d, (x, 330), _ajustar(d, nombre_rol, 70, ancho, True), 70, estilo.PAPEL, negrita=True, contorno=4)
    # Jugador y lugar comparten la fila: cada uno, como mucho, media tarjeta.
    x_chip = x
    if jugador:
        nombre = _ajustar(d, jugador, 30, ancho * 0.42)
        _texto(d, (x, 416), nombre, 30, estilo.COLOR_TEXTO_TENUE)
        x_chip += d.textlength(nombre, font=_fuente(30)) + 24
    if lugar:
        # el chip usa todo el ancho que queda a la derecha del jugador (antes, como mucho la mitad: «Universidade de Ciudad N…»)
        disponible = max(ancho * 0.5, ancho - (x_chip - x) - 40)
        texto_lugar = nombre_visible(lugar, corto=True)
        px_lugar = _px_que_cabe(d, texto_lugar, 28, 20, disponible, True)
        _chip(d, x_chip, 408 + (28 - px_lugar) // 2, _ajustar(d, texto_lugar, px_lugar, disponible, True), px_lugar)
    _texto(d, (x, 478), pmc.TEXTO_CARGA, 28, estilo.COLOR_TEXTO)
    x0, y0, x1, y1 = pmc.CAJA_BARRA
    d.rounded_rectangle(pmc.CAJA_BARRA, 10, fill=_rgba(estilo.COLOR_BARRA_FONDO), outline=_rgba(estilo.TINTA),
                        width=pmc.BORDE_BARRA_PX)
    _mensaje(d, glosar_texto(pmc.mensaje_inicio(rol, lugar or "")))
    return img


def imagen_cierre(rol, nombre_rol, color_rol, lugar, resultado):
    img = _fondo()
    d = ImageDraw.Draw(img)
    _cabecera(img, d, grande=False)
    _texto(d, (1208, 118), pmc.TITULO_CIERRE, 64, estilo.ACENTO_PRIMARIO, negrita=True, contorno=5, ancla="rm")
    _tarjeta(d, pmc.CAJA_TARJETA, estilo.COLOR_PANEL)
    _retrato(img, d, rol, color_rol)
    x = pmc.CAJA_BARRA[0]
    ancho = pmc.CAJA_TARJETA[2] - x - 40
    despedida = glosar_texto(pmc.despedida(nombre_rol))
    px = _px_que_cabe(d, despedida, 52, 26, ancho, True)
    _texto(d, (x, 288 + (52 - px) // 2), _ajustar(d, despedida, px, ancho, True), px, estilo.PAPEL,
           negrita=True, contorno=4)
    resumen = pmc.resumen_cierre(resultado, estilo.ETIQUETAS_INDICADORES)
    if resumen is None:
        _texto(d, (x, 370), _ajustar(d, pmc.MENSAJE_SIN_RESULTADO, 30, ancho), 30, estilo.COLOR_TEXTO)
    else:
        _texto(d, (x, 360), resumen["decisiones"], 32, estilo.ACENTO_SECUNDARIO, negrita=True)
        for k, (etiqueta, cambio, tono) in enumerate(resumen["indicadores"]):
            y = 408 + k * 44
            _texto(d, (x, y), f"{etiqueta}:", 30, estilo.COLOR_TEXTO)
            _texto(d, (x + 270, y), cambio, 30, _TONO_CAMBIO[tono], negrita=True)
        if resumen["alcance"]:
            _texto(d, (x, 548), _ajustar(d, resumen["alcance"], 28, ancho), 28, estilo.COLOR_TEXTO_TENUE)
    _mensaje(d, glosar_texto(pmc.mensaje_cierre(rol, lugar or "")))
    return img


# -- Capa Ursina (importa ursina solo al usarse) --

_CACHE = OrderedDict()


def _textura(clave, hacer_imagen):
    if clave in _CACHE:
        _CACHE.move_to_end(clave)
        return _CACHE[clave]
    from ursina import Texture
    textura = Texture(hacer_imagen())
    textura.filtering = "bilinear"
    textura.filtering = "mipmap"      # el monitor se ve pequeño en las primeras tomas: sin parpadeo de píxeles
    _CACHE[clave] = textura
    while len(_CACHE) > TEXTURAS_EN_CACHE:
        _CACHE.popitem(last=False)
    return textura


def textura_inicio(rol, nombre_rol, color_rol, jugador, lugar):
    return _textura(("inicio", rol, jugador, lugar),
                    lambda: imagen_inicio(rol, nombre_rol, color_rol, jugador, lugar))


def textura_cierre(rol, nombre_rol, color_rol, lugar, resultado):
    resumen = pmc.resumen_cierre(resultado, estilo.ETIQUETAS_INDICADORES)
    clave = ("cierre", rol, lugar, repr(resumen))
    return _textura(clave, lambda: imagen_cierre(rol, nombre_rol, color_rol, lugar, resultado))
