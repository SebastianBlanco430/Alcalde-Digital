# Texturas procedurales del suelo de la favela (PIL; no se guarda ningún archivo: se dibujan al
# arrancar). Son imágenes en tonos casi blancos que MULTIPLICAN el color por vértice de la malla, así
# el color de la arena sale de suelo_calculos.py y la textura solo aporta el detalle fino que un vértice
# cada metro no puede dar: grano, piedritas, grietas, rodadas de ruedas y huellas.
#
# Son deterministas (random.Random con semilla fija) y se pueden repetir sin costuras: cada dibujo se
# pinta con "envoltura" (lo que sale por un borde entra por el opuesto) y el desenfoque se hace sobre
# un mosaico de 3x3. Se prueban en tests/frontend_3d/test_suelo_calculos.py (tamaño, determinismo,
# rango de valores) sin abrir ventana.

import math
import random

from PIL import Image, ImageDraw, ImageFilter

TAMANO_GRANO = 256                       # px del lado de la textura del grano (repite cada METROS_GRANO m)
METROS_GRANO = 8.0
ANCHO_CAMINO, ALTO_CAMINO = 256, 512     # px de la textura del camino (ancho de la cinta x 8 m de largo)
SEMILLA_TEXTURAS = 91
BASE_CLARA = 238                         # valor medio (0-255) de las dos texturas: casi blanco
SEMIANCHO_RODADA = 0.42                  # m: ancho de cada rodada de rueda en el camino
SEPARACION_RODADAS = 1.45                # m del eje de la calle al centro de cada rodada
ANCHO_CAMINO_METROS = 11.0               # m que cubre el ancho de la textura del camino (2 x SEMIANCHO_CINTA)
LARGO_CAMINO_METROS = 8.0                # m que cubre el largo (igual a suelo_calculos.LARGO_TEXTURA_CAMINO)


# Dibuja `dibujo(draw, dx, dy)` con envoltura: nueve veces, desplazado un tamaño a cada lado, para
# que lo que sale por un borde entre por el opuesto y la textura repita sin costuras.
def _con_envoltura(imagen, dibujo):
    ancho, alto = imagen.size
    d = ImageDraw.Draw(imagen)
    for dx in (-ancho, 0, ancho):
        for dy in (-alto, 0, alto):
            dibujo(d, dx, dy)


# Desenfoca sin costuras: se repite la imagen en un mosaico de 3x3, se desenfoca y se recorta el centro.
def _desenfocar(imagen, radio):
    ancho, alto = imagen.size
    mosaico = Image.new(imagen.mode, (ancho * 3, alto * 3))
    for i in range(3):
        for j in range(3):
            mosaico.paste(imagen, (i * ancho, j * alto))
    mosaico = mosaico.filter(ImageFilter.GaussianBlur(radio))
    return mosaico.crop((ancho, alto, 2 * ancho, 2 * alto))


# Ruido de grano fino en tonos de gris alrededor de BASE_CLARA (en escala de grises "L").
def _base_con_grano(ancho, alto, azar, amplitud=14):
    imagen = Image.new("L", (ancho, alto), BASE_CLARA)
    imagen.putdata([BASE_CLARA + int((azar.random() - 0.5) * 2 * amplitud) for _ in range(ancho * alto)])
    return imagen


# Textura del grano de toda la ladera (arena y tierra): grano, piedritas claras y oscuras y grietas
# finas. RGB 256x256 que repite cada METROS_GRANO m.
def textura_grano(semilla=SEMILLA_TEXTURAS):
    azar = random.Random(semilla)
    n = TAMANO_GRANO
    imagen = _base_con_grano(n, n, azar, amplitud=16)
    piedras = [(azar.uniform(0, n), azar.uniform(0, n), azar.uniform(1.0, 3.2), azar.random()) for _ in range(190)]
    grietas = []
    for _ in range(12):
        x, y, angulo = azar.uniform(0, n), azar.uniform(0, n), azar.uniform(0, 6.28)
        puntos = [(x, y)]
        for _ in range(azar.randint(3, 6)):
            angulo += azar.uniform(-0.8, 0.8)
            x, y = x + 9 * math.cos(angulo), y + 9 * math.sin(angulo)
            puntos.append((x, y))
        grietas.append(puntos)

    def dibujo(d, dx, dy):
        for x, y, r, tono in piedras:
            valor = int(BASE_CLARA * (0.62 + 0.3 * tono)) if tono < 0.55 else min(255, BASE_CLARA + 14)
            d.ellipse([x + dx - r, y + dy - r * 0.8, x + dx + r, y + dy + r * 0.8], fill=valor)
            if tono < 0.55:      # sombra corta a un lado: la piedra se despega del suelo
                d.ellipse([x + dx - r + 0.8, y + dy - r * 0.8 + 1.2, x + dx + r + 0.8, y + dy + r * 0.8 + 1.2],
                          fill=int(BASE_CLARA * 0.78))
                d.ellipse([x + dx - r, y + dy - r * 0.8, x + dx + r, y + dy + r * 0.8], fill=valor)
        for puntos in grietas:
            d.line([(px + dx, py + dy) for px, py in puntos], fill=int(BASE_CLARA * 0.72), width=1)

    _con_envoltura(imagen, dibujo)
    return _a_rgb(_desenfocar(imagen, 0.7))


# Textura del camino de las calles de arena: rodadas de ruedas a los lados del eje, una joroba suave
# en el centro, huellas de pasos, piedras y grietas. El ancho (u) cubre toda la cinta (ANCHO_CAMINO_METROS
# m) y el largo (v) repite cada LARGO_CAMINO_METROS m. Los bordes quedan casi blancos (sin dibujo) para
# fundirse con el suelo de alrededor.
def textura_camino(semilla=SEMILLA_TEXTURAS + 1):
    azar = random.Random(semilla)
    ancho, alto = ANCHO_CAMINO, ALTO_CAMINO
    imagen = _base_con_grano(ancho, alto, azar, amplitud=12)
    px_por_m_x = ancho / ANCHO_CAMINO_METROS
    px_por_m_y = alto / LARGO_CAMINO_METROS
    centro_x = ancho / 2
    rodadas = [centro_x + lado * SEPARACION_RODADAS * px_por_m_x for lado in (-1, 1)]
    medio_rodada = SEMIANCHO_RODADA * px_por_m_x
    huellas = []
    for _ in range(26):             # pares de huellas a lo largo de caminos de a pie cerca de las rodadas
        x = centro_x + azar.choice((-1, 1)) * azar.uniform(0.2, 3.6) * px_por_m_x
        y = azar.uniform(0, alto)
        huellas.append((x, y, azar.uniform(-0.25, 0.25)))
    piedras = [(azar.uniform(0.18 * ancho, 0.82 * ancho), azar.uniform(0, alto), azar.uniform(1.4, 4.2), azar.random())
               for _ in range(150)]
    grietas = []
    for _ in range(9):
        x, y = azar.uniform(0.25 * ancho, 0.75 * ancho), azar.uniform(0, alto)
        puntos = [(x, y)]
        for _ in range(azar.randint(3, 6)):
            x, y = x + azar.uniform(-12, 12), y + azar.uniform(6, 20)
            puntos.append((x, y))
        grietas.append(puntos)

    def dibujo(d, dx, dy):
        for cx in rodadas:                       # rodadas: dos bandas oscuras que serpentean un poco
            for y in range(0, alto, 6):
                onda = 5 * math.sin(2 * math.pi * (y / alto) * 2 + cx)
                d.rectangle([cx - medio_rodada + onda + dx, y + dy, cx + medio_rodada + onda + dx, y + 6 + dy],
                            fill=int(BASE_CLARA * 0.80))
        d.rectangle([centro_x - 0.5 * px_por_m_x + dx, dy, centro_x + 0.5 * px_por_m_x + dx, alto + dy],
                    fill=min(255, BASE_CLARA + 8))            # joroba central un poco más clara
        for x, y, giro in huellas:               # huellas: dos óvalos oscuros por paso
            for lado in (-1, 1):
                hx, hy = x + dx + lado * 3.0 + giro * 4, y + dy + (6 if lado > 0 else 0)
                d.ellipse([hx - 2.4, hy - 4.6, hx + 2.4, hy + 4.6], fill=int(BASE_CLARA * 0.74))
        for x, y, r, tono in piedras:
            valor = int(BASE_CLARA * (0.6 + 0.25 * tono)) if tono < 0.6 else min(255, BASE_CLARA + 14)
            d.ellipse([x + dx - r, y + dy - r * 0.8, x + dx + r, y + dy + r * 0.8], fill=valor)
        for puntos in grietas:
            d.line([(px + dx, py + dy) for px, py in puntos], fill=int(BASE_CLARA * 0.7), width=1)

    _con_envoltura(imagen, dibujo)
    imagen = _desenfocar(imagen, 1.1)
    # Los bordes se funden a blanco: nada de rodadas en los últimos 8 % a cada lado.
    mascara = Image.new("L", imagen.size, 0)
    d = ImageDraw.Draw(mascara)
    margen = int(ancho * 0.08)
    d.rectangle([margen, 0, ancho - margen, alto], fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(margen / 2))
    imagen = Image.composite(imagen, Image.new("L", imagen.size, BASE_CLARA), mascara)
    return _a_rgb(imagen)


# La imagen en escala de grises como RGB, con un leve tinte cálido (los valores multiplican el color).
def _a_rgb(imagen):
    gris = imagen.convert("L")
    rojo = gris.point(lambda v: min(255, int(v * 1.02)))
    azul = gris.point(lambda v: int(v * 0.96))
    return Image.merge("RGB", (rojo, gris, azul))
