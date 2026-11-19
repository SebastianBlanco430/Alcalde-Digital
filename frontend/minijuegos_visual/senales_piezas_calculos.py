# Cálculo puro (sin ursina) de «Señales de edición» visual: ancho y lado de cada burbuja de la captura, reparto vertical,
# ficha de pista compacta, columna derecha centrada y trazos (doble check, cara del avatar, mango y brillo de la lupa).
# Lo usa senales_visual.py. Unidades de camera.ui (alto de pantalla = 1.0, 720 px de referencia).

import math

PX = 1.0 / 720.0                       # una unidad de píxel de referencia
ALTO_FICHA_MIN = 130 * PX              # la ficha de pista no baja de ~130 px
ALTO_LINEA_PISTA = 25 * PX             # una línea de pista de 18 px
ALTO_CABECERA_FICHA = 46 * PX          # etiqueta de la zona (22 px) + aire
MARGEN_FICHA = 16 * PX


def ancho_burbuja(ancho_texto, ancho_area, minimo=0.46, margen=0.04, reserva=0.2):
    """Ancho de una burbuja según su texto (más reserva para el sello), entre `minimo` y `ancho_area`."""
    deseado = float(ancho_texto) + 2 * margen + reserva
    return max(min(minimo, ancho_area), min(ancho_area, deseado))


def x_burbuja(ancho, ancho_area, centro=0.0, lado="izq", sangria=0.0):
    """Centro-x de una burbuja de ancho `ancho` pegada a la izquierda (recibido) o derecha (enviado) del área."""
    medio = ancho_area / 2
    if lado == "der":
        return centro + medio - ancho / 2 - sangria
    return centro - medio + ancho / 2 + sangria


def lado_de(i, texto=""):
    """Lado de la burbuja: todo lo reenviado entra por la izquierda; la última de la lista (la que escribe) a la derecha."""
    return "izq"


def repartir(altos, arriba, abajo, hueco=0.014, tope_extra=0.03):
    """Centros-y de bloques apilados entre `arriba` y `abajo`. Si sobra sitio lo reparte (hasta `tope_extra` por bloque);
    si falta, comprime el hueco (mínimo 0.004). Devuelve (altos_finales, centros_y)."""
    n = len(altos)
    if n == 0:
        return [], []
    libre = (arriba - abajo) - sum(altos)
    hueco_real = hueco
    altos = list(altos)
    if libre < hueco * (n - 1):
        hueco_real = max(0.004, libre / (n - 1)) if n > 1 else 0.0
    else:
        extra = min((libre - hueco * (n - 1)) / n, tope_extra)
        altos = [a + extra for a in altos]
    centros, y = [], arriba
    for a in altos:
        centros.append(y - a / 2)
        y -= a + hueco_real
    return altos, centros


def alto_ficha(n_lineas):
    """Alto de la ficha de pista para `n_lineas` de pista (>= ~130 px)."""
    return max(ALTO_FICHA_MIN, 2 * MARGEN_FICHA + ALTO_CABECERA_FICHA + max(1, n_lineas) * ALTO_LINEA_PISTA)


def columna_derecha(alto_ficha_, alto_contador, alto_boton, centro_y, hueco=0.03, hueco_botones=0.02):
    """Columna de la derecha centrada verticalmente en `centro_y`: ficha, contador, Confirmar, No veo nada raro.
    Devuelve dict con y de la parte superior de la ficha y los centros de contador y botones."""
    total = alto_ficha_ + hueco + alto_contador + hueco + 2 * alto_boton + hueco_botones
    arriba = centro_y + total / 2
    y = arriba - alto_ficha_
    y_cont = y - hueco - alto_contador / 2
    y -= hueco + alto_contador + hueco
    y_conf = y - alto_boton / 2
    y_nada = y_conf - alto_boton - hueco_botones
    return {"arriba": arriba, "ficha_y": arriba - alto_ficha_ / 2, "contador_y": y_cont, "confirmar_y": y_conf,
            "nada_y": y_nada, "abajo": y_nada - alto_boton / 2}


def puntos_doble_check(tam=0.016):
    """Dos palomitas solapadas (listas de puntos x,y) que miden ~`tam` de alto, centradas en (0,0)."""
    def palomita(dx):
        return [(dx - tam * 0.55, 0.0), (dx - tam * 0.2, -tam * 0.4), (dx + tam * 0.5, tam * 0.45)]
    return [palomita(-tam * 0.3), palomita(tam * 0.3)]


def cara_avatar(radio):
    """Ojos y sonrisa de un avatar de cómic: (ojo_izq, ojo_der, radio_ojo, puntos_sonrisa)."""
    ojo = radio * 0.13
    ex, ey = radio * 0.36, radio * 0.18
    sonrisa = [(radio * 0.5 * math.cos(math.radians(a)), -radio * 0.08 + radio * 0.5 * math.sin(math.radians(a)))
               for a in range(210, 331, 15)]
    return (-ex, ey), (ex, ey), ojo, sonrisa


def mango_lupa(radio, grados=-45, largo=None):
    """Extremos (inicio, fin) del mango de la lupa: sale del borde del aro hacia abajo a la derecha."""
    largo = radio * 0.9 if largo is None else largo
    a = math.radians(grados)
    c, s = math.cos(a), math.sin(a)
    return (radio * c, radio * s), ((radio + largo) * c, (radio + largo) * s)


def arco_brillo(radio, desde=110, hasta=160, n=8):
    """Puntos del destello curvo de la lupa (arriba a la izquierda, dentro del aro)."""
    r = radio * 0.72
    return [(r * math.cos(math.radians(desde + (hasta - desde) * k / n)),
             r * math.sin(math.radians(desde + (hasta - desde) * k / n))) for k in range(n + 1)]


def x_contador(izq, k, paso=0.06):
    return izq + k * paso


def texto_marcas(n, maximo):
    """«0 de 3 marcas» (nunca solo color: el contador también dice la cifra de marcas, no de indicadores)."""
    return f"{int(n)} de {int(maximo)} marcas" if maximo != 1 or n != 1 else "1 de 1 marca"
