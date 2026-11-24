"""Genera el logo del menú de inicio estilo BOTW: assets/ui/menu/logo.png (RGBA, una sola textura).

Diseño aprobado (lienzo «Alcalde Digital — Menú de inicio», medidas a 720p; el PNG sale a 4× = 2× de 1440p):
  - «ALCALDE» en Luckiest Guy 92 px, amarillo #FFD93D, contorno de tinta #1E1B2E y sombra plana desplazada 6 px;
  - debajo, rombo amarillo con borde de tinta + pastilla «DIGITAL» (cian #2EC4D6, borde de tinta 4 px, radio 12,
    sombra 5 px, letras blancas de 42 px con contorno de tinta y espaciado amplio);
  - debajo, «Verifica antes de compartir. Tu barrio decide.» en Atkinson Hyperlegible negrita 17 px, blanco con sombra.
Todo alineado a la derecha. El PNG lleva un margen transparente de MARGEN_LOGO_PX (720p) por cada lado para las sombras:
frontend/menu_botw_calculos.py lo descuenta al colocar el logo (margen derecho 64 px y superior 40 px).

Uso (desde la raíz del repo):  venv\\Scripts\\python.exe tools\\generar_logo_menu.py [--salida ruta.png]
Solo necesita Pillow. Las fuentes salen de assets/fuentes/."""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from frontend.menu_botw_calculos import ESCALA_LOGO_PNG, MARGEN_LOGO_PX  # noqa: E402

FUENTES = RAIZ / "assets" / "fuentes"
SALIDA = RAIZ / "assets" / "ui" / "menu" / "logo.png"

AMARILLO = (255, 217, 61, 255)
CIAN = (46, 196, 214, 255)
TINTA = (30, 27, 46, 255)
BLANCO = (255, 255, 255, 255)

S = ESCALA_LOGO_PNG          # píxeles del PNG por píxel de 720p


def px(v):
    return int(round(v * S))


def ancho_espaciado(fuente, texto, espaciado):
    return sum(fuente.getlength(c) for c in texto) + espaciado * (len(texto) - 1)


def texto_espaciado(dibujo, x, y, texto, fuente, espaciado, relleno, trazo=0, color_trazo=None):
    """Dibuja letra a letra (Pillow no tiene letter-spacing). (x, y) = esquina superior izquierda del cuadro «ascender»."""
    for c in texto:
        dibujo.text((x, y), c, font=fuente, fill=relleno, stroke_width=trazo, stroke_fill=color_trazo)
        x += fuente.getlength(c) + espaciado


def alto_tinta(fuente, texto):
    """(arriba, abajo) de la tinta del texto respecto a la y de dibujo (sin trazo)."""
    caja = fuente.getbbox(texto)
    return caja[1], caja[3]


def generar(salida=SALIDA):
    luckiest = FUENTES / "LuckiestGuy-Regular.ttf"
    atkinson = FUENTES / "AtkinsonHyperlegible-Bold.ttf"
    f_alcalde = ImageFont.truetype(str(luckiest), px(92))
    f_digital = ImageFont.truetype(str(luckiest), px(42))
    f_lema = ImageFont.truetype(str(atkinson), px(17))

    trazo_alcalde = px(3)        # CSS: -webkit-text-stroke 4 px con paint-order stroke → ~2 px visibles; 3 px aguanta el sol
    sombra_alcalde = px(6)
    esp_alcalde = px(2)
    trazo_digital = px(1.5)
    esp_digital = px(6)
    borde_pastilla = px(4)
    sombra_pastilla = px(5)
    pad_x, pad_y = px(22), px(4)
    lema = "Verifica antes de compartir. Tu barrio decide."

    # --- medidas de cada bloque (ancho de tinta incluido el trazo) ---
    w_alc = ancho_espaciado(f_alcalde, "ALCALDE", esp_alcalde) + 2 * trazo_alcalde
    a0, a1 = alto_tinta(f_alcalde, "ALCALDE")
    h_alc = (a1 - a0) + 2 * trazo_alcalde

    w_dig_txt = ancho_espaciado(f_digital, "DIGITAL", esp_digital)
    d0, d1 = alto_tinta(f_digital, "DIGITAL")
    h_dig_txt = d1 - d0
    w_pastilla = w_dig_txt + 2 * pad_x + 2 * borde_pastilla
    h_pastilla = h_dig_txt + 2 * pad_y + 2 * borde_pastilla + px(10)     # line-height 1.05: algo de aire arriba y abajo
    lado_rombo = px(22)
    gap_rombo = px(10)
    w_fila = lado_rombo + gap_rombo + w_pastilla
    l0, l1 = alto_tinta(f_lema, lema)
    w_lema = f_lema.getlength(lema) + px(2)
    h_lema = l1 - l0

    gap1, gap2 = px(10), px(12)
    margen = px(MARGEN_LOGO_PX)
    ancho_contenido = int(max(w_alc + sombra_alcalde, w_fila + sombra_pastilla, w_lema + px(4) + px(2)))
    alto_contenido = int(h_alc + sombra_alcalde + gap1 + h_pastilla + sombra_pastilla + gap2 + h_lema + px(2))
    W, H = ancho_contenido + 2 * margen, alto_contenido + 2 * margen
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    derecha = margen + ancho_contenido           # borde derecho del contenido (sin las sombras, que van hacia +x)

    # --- ALCALDE: sombra plana y luego texto con contorno ---
    y = margen
    x = derecha - sombra_alcalde - w_alc + trazo_alcalde
    ty = y + trazo_alcalde - a0
    texto_espaciado(d, x + sombra_alcalde, ty + sombra_alcalde, "ALCALDE", f_alcalde, esp_alcalde, TINTA,
                    trazo_alcalde, TINTA)
    texto_espaciado(d, x, ty, "ALCALDE", f_alcalde, esp_alcalde, AMARILLO, trazo_alcalde, TINTA)
    y += h_alc + sombra_alcalde + gap1

    # --- fila: rombo + pastilla DIGITAL ---
    px0 = derecha - sombra_pastilla - w_pastilla
    d.rounded_rectangle((px0 + sombra_pastilla, y + sombra_pastilla, px0 + sombra_pastilla + w_pastilla,
                         y + sombra_pastilla + h_pastilla), radius=px(12), fill=TINTA)
    d.rounded_rectangle((px0, y, px0 + w_pastilla, y + h_pastilla), radius=px(12), fill=CIAN, outline=TINTA,
                        width=borde_pastilla)
    tx = px0 + borde_pastilla + pad_x
    ty = y + (h_pastilla - h_dig_txt) / 2 - d0
    texto_espaciado(d, tx, ty, "DIGITAL", f_digital, esp_digital, BLANCO, trazo_digital, TINTA)
    # rombo: cuadrado de 14 px girado 45° (diagonal ≈ 20 px) con borde de tinta de 3 px
    cx = px0 - gap_rombo - lado_rombo / 2
    cy = y + h_pastilla / 2
    r = px(12)
    rombo = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    d.polygon(rombo, fill=AMARILLO, outline=TINTA, width=px(3))
    y += h_pastilla + sombra_pastilla + gap2

    # --- lema con sombra de tinta 2 px ---
    lx = derecha - px(4) - px(2) - f_lema.getlength(lema)
    ly = y - l0
    d.text((lx + px(2), ly + px(2)), lema, font=f_lema, fill=TINTA)
    d.text((lx, ly), lema, font=f_lema, fill=BLANCO)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    img.save(salida, optimize=True)
    return salida, img.size


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--salida", default=str(SALIDA))
    ruta, tam = generar(a.parse_args().salida)
    print(f"{ruta}  {tam[0]}x{tam[1]} px  (a 720p: {tam[0] / S:.0f}x{tam[1] / S:.0f})")
