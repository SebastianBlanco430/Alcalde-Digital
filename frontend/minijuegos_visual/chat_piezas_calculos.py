# Cálculo puro (sin ursina) de las piezas del «Chat del barrio» visual: colas de globo, arcos del reloj de presión,
# posiciones de las burbujas y color por rol. Lo usan piezas_chat.py y chat_visual.py.

import math

COLOR_CIAN = (70, 220, 255)
COLOR_AVISO = (215, 180, 60)
COLOR_ROJO = (214, 62, 62)
COLOR_GRIS = (150, 152, 165)
COLORES_ROL = {
    "organizadora": (232, 84, 150),
    "amigo": (46, 184, 116),
    "periodista": (46, 184, 116),
    "influencer": (232, 84, 150),
    "vecino": (66, 133, 244),
    "ciudadano": (66, 133, 244),
}
TONOS_RESPALDO = ((66, 133, 244), (232, 160, 70), (170, 130, 220), (46, 184, 116))


def color_de_rol(de, indice=0):
    """Color del avatar según el rol entre paréntesis de «Nombre (rol)»; si no hay, uno de respaldo por índice."""
    texto = str(de or "")
    if "(" in texto:
        rol = texto.split("(", 1)[1].split(")")[0].strip().lower()
        for clave, tono in COLORES_ROL.items():
            if clave in rol:
                return tono
    return TONOS_RESPALDO[int(indice) % len(TONOS_RESPALDO)]


def tercio_presion(restante):
    """'alto' (>66 %), 'medio' (34-66 %) o 'bajo' (<34 %) según la fracción de tiempo que queda (0..1)."""
    r = max(0.0, min(1.0, restante))
    if r > 0.66:
        return "alto"
    if r >= 0.34:
        return "medio"
    return "bajo"


def color_reloj(restante):
    return {"alto": COLOR_CIAN, "medio": COLOR_AVISO, "bajo": COLOR_ROJO}[tercio_presion(restante)]


def arco_reloj(restante, radio, pasos=40):
    """Triángulos (abanico) de un sector que arranca arriba y se vacía en sentido horario. Devuelve (vertices, triangulos).
    Con restante<=0 no hay sector (listas vacías)."""
    r = max(0.0, min(1.0, restante))
    if r <= 0.0:
        return [], []
    n = max(2, int(math.ceil(pasos * r)))
    verts = [(0.0, 0.0)]
    for i in range(n + 1):
        ang = math.pi / 2 - 2 * math.pi * r * (i / n)
        verts.append((radio * math.cos(ang), radio * math.sin(ang)))
    return verts, [(0, i, i + 1) for i in range(1, n + 1)]


def cola_globo(lado, ancho, alto, tam=0.014):
    """Centro (x, y) y giro (grados) del rombito que hace de cola, en coordenadas locales del globo (centro en 0,0).
    lado: 'izq' (entrantes) o 'der' (salientes)."""
    x = -ancho / 2 + 0.001 if lado == "izq" else ancho / 2 - 0.001
    return x, -alto / 2 + tam * 1.1, 45.0


def alto_globo(n_lineas, alto_linea, margen=0.012, minimo=0.05):
    return max(minimo, n_lineas * alto_linea + 2 * margen)


def posiciones_burbujas(altos, y_abajo, y_arriba, hueco=0.018):
    """Coloca de abajo hacia arriba los globos más recientes que caben. Devuelve [(indice, y_centro)] en orden
    cronológico (los que no caben por arriba se omiten; siempre cabe el último)."""
    colocados, y = [], y_abajo
    for i in range(len(altos) - 1, -1, -1):
        a = altos[i]
        if y + a > y_arriba and colocados:
            break
        colocados.append((i, y + a / 2))
        y += a + hueco
    colocados.reverse()
    return colocados


def inclinacion_avatar(presion, indice):
    """Grados de inclinación de un avatar «esperando»: crece con la presión, alterna el signo."""
    p = max(0.0, min(1.0, presion))
    return (1 if indice % 2 == 0 else -1) * 14.0 * p


def muestra_alarma(presion):
    """¿Se muestra el «!» sobre los avatares? Cuando queda menos del 20 % del tiempo."""
    return (1.0 - presion) < 0.20


# Disposición de la vista de juego (coordenadas de camera.ui): reloj arriba a la derecha, respuestas por debajo.
RELOJ_CENTRO = (0.78, 0.36)
RELOJ_DIAMETRO = 0.10
X_RESPUESTAS = 0.45
ANCHO_RESPUESTAS = 0.78
Y_RESPUESTAS_ARRIBA = 0.24
SEPARACION_RESPUESTAS = 0.04
X_AVATARES = 0.60               # primer avatar «esperando»; a la izquierda del reloj, en su misma franja
PASO_AVATARES = 0.045


def puntos_palomita():
    """Tres puntos (x, y) de una palomita centrada en el origen, en el rango -0.5..0.5."""
    return [(-0.5, 0.0), (-0.15, -0.38), (0.5, 0.42)]


def puntos_aspa():
    """Dos trazos ((x1, y1), (x2, y2)) de un aspa centrada en el origen, en el rango -0.45..0.45."""
    return [((-0.45, -0.45), (0.45, 0.45)), ((-0.45, 0.45), (0.45, -0.45))]


def marca_de_valor(valor):
    """'bien' para la respuesta que protege (valor 2), 'mal' para la que cede un dato (0), '' para la intermedia."""
    return "bien" if valor == 2 else ("mal" if valor == 0 else "")


def resumen_final(respuestas):
    """Una línea de resumen con lo que pasó en la conversación (respuestas: [{"valor", "elegida"}])."""
    n = len(respuestas)
    if n == 0:
        return ""
    bien = sum(1 for r in respuestas if r["valor"] == 2)
    visto = sum(1 for r in respuestas if r.get("elegida") is None)
    cedidos = sum(1 for r in respuestas if r["valor"] == 0)
    partes = ["Protegiste los datos en %d de %d respuestas" % (bien, n)]
    if cedidos:
        partes.append("cediste datos %d %s" % (cedidos, "vez" if cedidos == 1 else "veces"))
    if visto:
        partes.append("te quedaste en visto %d %s" % (visto, "vez" if visto == 1 else "veces"))
    return ", ".join(partes) + "."
