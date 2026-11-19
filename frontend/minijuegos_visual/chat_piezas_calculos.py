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


# ---------------------------------------------------------------------------------------------------------------------
# Rediseño de papel/tinta (E3): color por personaje desde estilo.COLORES_ROL_PROPUESTOS, retratos de cómic, reloj con número
# grande y reparto vertical del teléfono y de las respuestas. Todo puro (sin ursina). Lo añadido NO cambia lo de arriba.
# ---------------------------------------------------------------------------------------------------------------------

from frontend import estilo as _estilo

# Rol del chat -> rol de estilo.COLORES_ROL_PROPUESTOS (decisión del dueño: ciudadano azul, periodista verde, influencer rosa).
ALIAS_ROL_ESTILO = {
    "organizadora": "influencer", "influencer": "influencer",
    "amigo": "periodista", "amiga": "periodista", "periodista": "periodista",
    "vecino": "ciudadano", "vecina": "ciudadano", "ciudadano": "ciudadano",
    "candidato": "candidato",
}
ESCALA_TELEFONO = 1.15          # el teléfono mide un 15 % más que antes
ALTO_TELEFONO_BASE = 0.56       # alto que tenía el teléfono (Y_CONTENIDO_ARRIBA - (-0.26))
ANCHO_TELEFONO_BASE = 0.56
# Colores del arco del reloj sobre papel: claros, para que el número de tinta se lea (contraste >= 4,5 con la tinta).
COLORES_RELOJ_PAPEL = {"alto": (96, 214, 240), "medio": (240, 200, 80), "bajo": (244, 120, 108)}
PIELES = ((240, 200, 160), (222, 172, 128), (190, 138, 100), (246, 214, 180))
PELOS = ((60, 44, 40), (120, 80, 50), (30, 28, 30), (170, 120, 60))
ESTILOS_PELO_RETRATO = ("corto", "largo", "largo")
ACCESORIOS_RETRATO = ("ninguno", "gafas", "barba", "ninguno")


def rol_de(de):
    """Rol (en minúsculas) del texto «Nombre (rol)»; '' si no trae."""
    texto = str(de or "")
    if "(" not in texto:
        return ""
    return texto.split("(", 1)[1].split(")")[0].strip().lower()


def color_personaje(de, indice=0):
    """Color del personaje tomado de estilo.COLORES_ROL_PROPUESTOS (vía alias del rol); si no hay rol, un tono de respaldo."""
    rol = rol_de(de)
    for clave, alias in ALIAS_ROL_ESTILO.items():
        if clave in rol and alias in _estilo.COLORES_ROL_PROPUESTOS:
            return tuple(_estilo.COLORES_ROL_PROPUESTOS[alias])
    return TONOS_RESPALDO[int(indice) % len(TONOS_RESPALDO)]


def mezclar(a, b, fraccion):
    """Mezcla lineal de dos colores RGB (fraccion = peso de b, 0..1)."""
    f = max(0.0, min(1.0, fraccion))
    return tuple(int(round(a[k] + (b[k] - a[k]) * f)) for k in range(3))


def tono_globo(de, indice=0, papel=None):
    """Relleno del globo de un personaje: su color muy diluido en papel (el texto de tinta siempre se lee)."""
    return mezclar(papel or _estilo.PAPEL, color_personaje(de, indice), 0.30)


def _semilla(texto):
    return sum((i + 1) * ord(c) for i, c in enumerate(str(texto or "")))


def retrato_de(de, indice=0):
    """Dict `retrato` (formato de dialogo_retratos) estable para un personaje: ropa del color de su rol, resto por nombre."""
    s = _semilla(de)
    return {"piel": list(PIELES[s % len(PIELES)]), "pelo": list(PELOS[(s // 3) % len(PELOS)]),
            "pelo_estilo": ESTILOS_PELO_RETRATO[(s // 5) % len(ESTILOS_PELO_RETRATO)],
            "ropa": list(color_personaje(de, indice)), "accesorio": ACCESORIOS_RETRATO[(s // 7) % len(ACCESORIOS_RETRATO)]}


def segundos_restantes(restante):
    """Número entero de segundos que se muestra en el reloj (hacia arriba: «1» hasta que se acaba; nunca negativo)."""
    return max(0, int(math.ceil(max(0.0, float(restante)) - 1e-9)))


def color_reloj_papel(restante):
    return COLORES_RELOJ_PAPEL[tercio_presion(restante)]


def medidas_telefono(alto_area, y_centro, ancho_base=ANCHO_TELEFONO_BASE, alto_base=ALTO_TELEFONO_BASE,
                     escala=ESCALA_TELEFONO):
    """(ancho, alto, y_arriba, y_centro) del teléfono ampliado `escala`, centrado en vertical en la franja útil; si no cabe,
    se limita al alto de la franja."""
    ancho, alto = ancho_base * escala, alto_base * escala
    if alto > alto_area:
        ancho, alto = ancho * alto_area / alto, alto_area
    return ancho, alto, y_centro + alto / 2, y_centro


def reparto_respuestas(altos, y_centro, y_tope, separacion=SEPARACION_RESPUESTAS):
    """Y del centro de cada respuesta (de arriba abajo): el bloque queda centrado en `y_centro`, pero su borde superior nunca
    pasa de `y_tope` (deja sitio al reloj). Devuelve (lista_de_y, y_arriba_del_bloque)."""
    if not altos:
        return [], y_centro
    total = sum(altos) + separacion * (len(altos) - 1)
    arriba = min(y_centro + total / 2, y_tope)
    ys, y = [], arriba
    for a in altos:
        ys.append(y - a / 2)
        y -= a + separacion
    return ys, arriba
