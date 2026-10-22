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

import random

from PIL import Image, ImageDraw, ImageFilter

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


def textura_relieve_ladrillo(media, tamano=TAMANO, semilla=SEMILLA):
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
    return normalizar(imagen, media)


# Desplaza los valores para que la media sea `media` (0-255), sin cambiar el contraste.
def normalizar(imagen, media):
    datos = list(imagen.getdata())
    actual = sum(datos) / len(datos)
    ajuste = media - actual
    return imagen.point(lambda v: int(min(255, max(0, round(v + ajuste)))))


def media_de(imagen):
    datos = list(imagen.convert("L").getdata())
    return sum(datos) / len(datos)
