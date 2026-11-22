# Textura procedural de relieve de ladrillo para paredes PINTADAS (PIL; no se guarda ningún archivo).
#
# Es una imagen en escala de grises que MULTIPLICA el color plano de la pared (igual que las texturas de
# concreto corregidas de casas_decorativas.py), así que no cambia el color del edificio: su valor medio se
# lleva a `media` (el mismo BRILLO_PARED al que se llevan las paredes de concreto) y solo aporta el dibujo:
# juntas hundidas (oscuras), cada ladrillo con un bisel (borde de arriba claro, de abajo oscuro) y un leve
# cambio de tono entre ladrillos. Hilada a soga: cada fila corrida medio ladrillo.
#
# Se dibuja con la misma cantidad de hiladas por repetición que la textura de ladrillo de los modelos
# (Bricks047, ~10 hiladas), así sobre los UV de las paredes los ladrillos salen del mismo tamaño que el
# ladrillo visto que ya usa la favela. Determinista (random.Random con semilla) y repetible sin costuras.

import os
import random

from PIL import Image, ImageDraw, ImageFilter

from frontend import tinta_calculos

TAMANO = 512                 # px del lado
HILADAS = 10                 # filas de ladrillos por repetición
LADRILLOS_POR_HILADA = 4
JUNTA = 6                    # px de ancho de la junta de mortero
VALOR_LADRILLO = 205         # gris de la cara del ladrillo (antes de normalizar)
VALOR_JUNTA = 92             # gris de la junta: hundida, en sombra
BISEL = 4                    # px del borde con luz (arriba) y sombra (abajo)
LUZ_BISEL = 26               # niveles que suma el borde de arriba
SOMBRA_BISEL = 34            # niveles que resta el borde de abajo
VARIACION = 14               # ± niveles de tono entre ladrillos
SEMILLA = 47

# CACHÉ (M7.2, arranque): la favela pide esta textura con ~12 medias distintas y el dibujo (ladrillos + 262.144
# gauss del grano + desenfoque) era el mismo en todas: solo cambia `normalizar`. Con la caché el dibujo se hace una
# vez por (tamaño, semilla) y se normaliza una copia: la imagen resultante es idéntica byte a byte.
# ALCALDE_CACHE_LADRILLO=0 (o CACHE_LADRILLO = False) lo vuelve a dibujar en cada llamada, como antes.
CACHE_LADRILLO = True
_dibujos = {}


def cache_ladrillo_activa(valor=None):
    valor = (os.environ.get("ALCALDE_CACHE_LADRILLO", "") if valor is None else valor).strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(CACHE_LADRILLO)


def textura_relieve_ladrillo(media, tamano=TAMANO, semilla=SEMILLA):
    if not cache_ladrillo_activa():
        return normalizar(_dibujar_relieve(tamano, semilla), media)
    clave = (tamano, semilla, tinta_calculos.texturas_activa())
    dibujo = _dibujos.get(clave)
    if dibujo is None:
        dibujo = _dibujos[clave] = _dibujar_relieve(tamano, semilla)
    return normalizar(dibujo, media)      # normalizar devuelve una imagen nueva: el dibujo guardado no se toca


def _dibujar_relieve(tamano, semilla):
    azar = random.Random(semilla)
    imagen = Image.new("L", (tamano, tamano), VALOR_JUNTA)
    d = ImageDraw.Draw(imagen)
    alto = tamano / HILADAS
    ancho = tamano / LADRILLOS_POR_HILADA
    for fila in range(HILADAS):
        y0 = fila * alto
        desfase = (ancho / 2) * (fila % 2)
        for k in range(-1, LADRILLOS_POR_HILADA + 1):
            x0 = k * ancho + desfase
            tono = VALOR_LADRILLO + azar.randint(-VARIACION, VARIACION)
            caja = (x0 + JUNTA / 2, y0 + JUNTA / 2, x0 + ancho - JUNTA / 2, y0 + alto - JUNTA / 2)
            d.rectangle(caja, fill=tono)
            # bisel: arriba claro, abajo oscuro (la luz viene de arriba); y = 0 es la fila de arriba de la imagen
            d.rectangle((caja[0], caja[1], caja[2], caja[1] + BISEL), fill=min(255, tono + LUZ_BISEL))
            d.rectangle((caja[0], caja[3] - BISEL, caja[2], caja[3]), fill=max(0, tono - SOMBRA_BISEL))
    # grano fino para que no se vea de plástico
    ruido = Image.new("L", (tamano, tamano))
    ruido.putdata([128 + int(azar.gauss(0, 40)) for _ in range(tamano * tamano)])
    imagen = Image.blend(imagen, Image.eval(ruido, lambda v: min(255, max(0, v))), 0.08)
    imagen = imagen.filter(ImageFilter.GaussianBlur(0.8))
    if tinta_calculos.texturas_activa():
        imagen = entintar_ladrillo(imagen, tamano, semilla)
    return imagen


# T6 (ALCALDE_TINTA_TEXTURAS): trazo de tinta bajo y a la derecha de cada ladrillo (el lado en sombra, como una línea de
# cómic), 2-3 grietas y un rayado leve en la franja de abajo. Se dibuja DESPUÉS del desenfoque: línea nítida. Repetible
# sin costuras (las líneas van dentro de cada ladrillo y el rayado repite con un período que divide al tamaño).
TRAZO_LADRILLO = 2           # px
GRIETAS_LADRILLO = 3
FRANJA_RAYADO = 0.16         # fracción de abajo con rayado
PASO_RAYADO = 16             # px (divide a 512)
OSCURO_RAYADO = 30           # niveles que resta cada raya


def entintar_ladrillo(imagen, tamano=TAMANO, semilla=SEMILLA):
    azar = random.Random(semilla * 31 + 7)
    d = ImageDraw.Draw(imagen)
    tinta = tinta_calculos.VALOR_TINTA_TEXTURA
    alto = tamano / HILADAS
    ancho = tamano / LADRILLOS_POR_HILADA
    for fila in range(HILADAS):
        y0 = fila * alto
        desfase = (ancho / 2) * (fila % 2)
        for k in range(-1, LADRILLOS_POR_HILADA + 1):
            x0 = k * ancho + desfase
            x1, y1 = x0 + ancho - JUNTA / 2, y0 + alto - JUNTA / 2
            d.line((x0 + JUNTA / 2, y1, x1, y1), fill=tinta, width=TRAZO_LADRILLO)           # borde de abajo
            d.line((x1, y0 + JUNTA / 2, x1, y1), fill=tinta, width=TRAZO_LADRILLO)           # borde derecho
    for _ in range(GRIETAS_LADRILLO):
        fila = azar.randrange(1, HILADAS - 1)
        x = azar.uniform(0.15, 0.85) * tamano
        y = (fila + 0.25) * alto
        puntos = [(x, y)]
        for _ in range(azar.randint(2, 4)):
            x, y = x + azar.uniform(-7, 7), y + azar.uniform(4, 9)
            puntos.append((x, y))
        d.line(puntos, fill=tinta, width=1)
    y_franja = int(tamano * (1.0 - FRANJA_RAYADO))
    pixeles = imagen.load()
    for y in range(y_franja, tamano):
        for x in range(tamano):
            if (x + y) % PASO_RAYADO == 0:
                pixeles[x, y] = max(0, pixeles[x, y] - OSCURO_RAYADO)
    return imagen


# Desplaza los valores para que la media sea `media` (0-255), sin cambiar el contraste.
def normalizar(imagen, media):
    datos = list(imagen.getdata())
    actual = sum(datos) / len(datos)
    ajuste = media - actual
    return imagen.point(lambda v: int(min(255, max(0, round(v + ajuste)))))


def media_de(imagen):
    datos = list(imagen.convert("L").getdata())
    return sum(datos) / len(datos)
