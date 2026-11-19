# Cálculos puros (sin ursina) de las marcas de «Ordenar la cadena de difusión»: los 3 pasos de la instrucción (cintas), la
# marca discreta de cada viñeta (palomita / aspa + texto corto) y el único sello «EN ORDEN». Tests: tests/test_cronologia_marcas.py.

PASOS = ("Se lee de izquierda a derecha y de arriba abajo.",
         "La viñeta 1 es lo que se dijo primero.",
         "Fíjate en la hora de cada cartela.")
TEXTO_EN_ORDEN = "EN ORDEN"


def cintas(ancho_total, n=3, hueco=0.02):
    """Reparte `ancho_total` en `n` cintas iguales separadas por `hueco`: lista de (x_centro_relativo_al_borde_izq, ancho)."""
    n = max(1, int(n))
    ancho = max(0.0, (ancho_total - (n - 1) * hueco) / n)
    return [(i * (ancho + hueco) + ancho / 2, ancho) for i in range(n)]


def etiqueta_marca(estado, etiqueta=None):
    """Texto corto de la marca de una viñeta tras comprobar. Correcta: «EN SU PUESTO»; incorrecta: «ERA LA 3.ª» (o el
    texto dado). Otro estado: ''."""
    if estado == "correcta":
        return "EN SU PUESTO"
    if estado == "incorrecta":
        texto = etiqueta or "FUERA DE SITIO"
        return texto.replace("ERA EL", "ERA LA").replace(".º", ".ª")
    return ""


def todo_en_orden(en_su_puesto):
    """True si hay viñetas y todas están en su puesto (el sello «EN ORDEN» solo sale entonces)."""
    lista = list(en_su_puesto)
    return bool(lista) and all(bool(x) for x in lista)


def palomita(lado):
    """Dos trazos (x1, y1, x2, y2) de una palomita dentro de un cuadrado de `lado`, centrada en (0, 0)."""
    return [(-0.32 * lado, 0.0, -0.1 * lado, -0.26 * lado), (-0.1 * lado, -0.26 * lado, 0.34 * lado, 0.28 * lado)]


def aspa(lado):
    """Dos trazos (x1, y1, x2, y2) de un aspa dentro de un cuadrado de `lado`, centrada en (0, 0)."""
    m = 0.3 * lado
    return [(-m, -m, m, m), (-m, m, m, -m)]


def trazo(x1, y1, x2, y2):
    """Un segmento como rectángulo girado: (x_centro, y_centro, largo, angulo_grados)."""
    import math
    dx, dy = x2 - x1, y2 - y1
    return ((x1 + x2) / 2, (y1 + y2) / 2, math.hypot(dx, dy), math.degrees(math.atan2(dy, dx)))


def ancho_marca(ancho_texto, alto, margen=0.012):
    """Ancho de la marca: espacio del icono (cuadrado de `alto`) + texto + márgenes."""
    return alto + ancho_texto + 3 * margen
