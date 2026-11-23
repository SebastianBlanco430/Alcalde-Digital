# Cálculos puros de la familia CORCHO del rework 3D (Rastrear la fuente y Ordenar la cadena). Python puro: NO importa
# ursina ni panda3d (regla R2 de tests/test_arquitectura_mvc.py); los usan rastrear_3d.py y cronologia_3d.py.
#
# Unidades: METROS en el plano local del ancla «corcho» (sets.Ancla: +x derecha, +y arriba, cara visible hacia -z).
# Todo se diseña para el corcho de la sala de investigación (2,0 x 1,2 m) y ESCALA con su alto (`escala(alto)`): en la
# oficina (1,7 x 1,05) todo mide un 12,5 % menos y la cámara se acerca en la misma proporción, así el texto mide los
# mismos píxeles en los dos sets. El ancho útil normalizado (ANCHO_NORMAL) cabe en los dos corchos.
#
#   s = escala(alto)
#   encuadre(ancho, alto)            -> rectángulo que la cámara encuadra (corcho + hueco del personaje + franja de ayuda)
#   reposo(ancho, alto)              -> (x local, distancia) del personaje en reposo: a la izquierda, FUERA del corcho
#   disposicion_rastrear(ancho, alto) / disposicion_cronologia(ancho, alto, n)
#   cinta(puntos, grosor)            -> malla (vértices, triángulos) de un hilo/cordel plano que pasa por `puntos`
#   foto_rastreo(partida) / eventos_rastreo(antes, ahora, partida)   -> qué pasó entre dos frames (para la cola de gestos)
#   ColaGestos                       -> gestos pendientes; si se acumulan, el 3D se pone al día (no bloquea la lógica)

import math

from frontend.minijuegos_visual import pistas_visuales_calculos as pvc

ALTO_REF = 1.2                   # m: alto del corcho de la sala de investigación
ANCHO_NORMAL = 1.94              # m (normalizados): ancho útil que cabe en los dos corchos (oficina: 1,7 / 0,875 = 1,943)
FRACCION_ENCUADRE = 0.97         # el rectángulo encuadrado llena el 97 % de la ventana (por alto o por ancho)
HUECO_PERSONAJE = 0.62           # m normalizados a la izquierda del corcho donde se ve al personaje en reposo
MARGEN_DERECHO = 0.10
MARGEN_ARRIBA = 0.09
MARGEN_ABAJO = 0.16              # la franja de ayuda de la capa de pantalla tapa esto (no el corcho)
REPOSO_LATERAL = 0.30            # m REALES (el cuerpo no escala con el corcho) más allá del borde izquierdo del corcho
MEDIO_CUERPO = 0.32              # m: medio ancho de hombros/brazos del protagonista más ancho (traje del candidato)
REPOSO_DISTANCIA = 0.72          # m del corcho a los pies en reposo
ACERCARSE_DISTANCIA = 0.50       # m del corcho a los pies durante un gesto (el brazo llega con holgura)

# Alturas de línea (m normalizados). papel_3d.ALTO_LINEA_MINIMO["corcho"] = 0,027 con la toma de infra (corcho al 72 %);
# esta toma deja el corcho al ~78 %. Medido en ventana (altura_texto_px, caja ajustada de los glifos): 0,028 da 14,4-16 px a
# 1280x720 con minúsculas, pero un rótulo SOLO en mayúsculas («INTENTOS: 2 de 2») o sin ascendentes («ayer 19:30») mide
# menos: por eso esos van a 0,032-0,034. Nada baja de 0,028.
LINEA_RUMOR = 0.034
LINEA_TITULO = 0.032
LINEA_CUERPO = 0.032
LINEA_CABECERA = 0.030
LINEA_CADENA = 0.032
LINEA_INTENTOS = 0.034
LINEA_MINIMA = 0.028
# Cronología (tarjetas de ~0,30 m): medido con 0,028 -> quién 11,4-16,5 px, hora 12,3-12,8 px, globo 15,2-15,9 px.
LINEA_VINETA_QUIEN = 0.036
LINEA_VINETA_HORA = 0.034        # la hora es la pista: SIEMPRE entera en una línea (si no cabe, baja hasta LINEA_MINIMA)
LINEA_VINETA_GLOBO = 0.030
LINEA_VINETA_MARCA = 0.034
LINEA_BOTON = 0.036


def escala(alto):
    """Factor de escala del corcho (1 en la sala, 0,875 en la oficina)."""
    return max(0.3, float(alto)) / ALTO_REF


def encuadre(ancho, alto):
    """Rectángulo (en el plano del corcho, m) que encuadra la cámara: el corcho con su marco, el hueco del personaje a la
    izquierda y la franja de la ayuda abajo. Devuelve {"centro": (dx, dy), "ancho", "alto"} (dx, dy respecto al centro
    del corcho)."""
    s = escala(alto)
    izq = -ancho / 2 - HUECO_PERSONAJE * s
    der = ancho / 2 + MARGEN_DERECHO * s
    arr = alto / 2 + MARGEN_ARRIBA * s
    aba = -alto / 2 - MARGEN_ABAJO * s
    return {"centro": ((izq + der) / 2, (arr + aba) / 2), "ancho": der - izq, "alto": arr - aba}


def distancia_camara(ancho_v, alto_v, fov_h, aspecto, fraccion=FRACCION_ENCUADRE):
    """Distancia a la que el rectángulo ancho_v x alto_v ocupa `fraccion` de la ventana (el lado que antes llene)."""
    t_h = math.tan(math.radians(fov_h) / 2)
    t_v = t_h / aspecto
    return max((alto_v / 2) / (fraccion * t_v), (ancho_v / 2) / (fraccion * t_h))


def fraccion_corcho(alto, distancia, fov_h, aspecto):
    """Fracción del alto de la ventana que ocupa el corcho visto de frente a `distancia`."""
    t_v = math.tan(math.radians(fov_h) / 2) / aspecto
    return alto / (2 * distancia * t_v)


def reposo(ancho, alto):
    """(x local, distancia) del personaje en reposo: a la izquierda del corcho, fuera de su marco (no tapa nada)."""
    return (-ancho / 2 - REPOSO_LATERAL, REPOSO_DISTANCIA)


def proyectar_x(x_obj, dist_obj, x_cam, dist_cam):
    """x (en el plano del corcho) donde se ve un punto que está a `dist_obj` m delante del corcho en x_obj, desde una
    cámara a `dist_cam` m en x_cam (sirve para comprobar que el personaje en reposo no tapa el corcho)."""
    return x_cam + (x_obj - x_cam) * dist_cam / max(1e-6, dist_cam - dist_obj)


# -- Rastrear --

def disposicion_rastrear(ancho, alto):
    """Dónde va cada cosa en el corcho de Rastrear (m locales del corcho, ya escalados). Rectángulos como
    (cx, cy, ancho, alto); 'notas_x' son los centros de las 3 candidatas y 'notas_arriba' su borde superior común."""
    s = escala(alto)
    u = lambda v: v * s           # noqa: E731
    ancho_n = min(ANCHO_NORMAL, ancho / s)
    mitad = ancho_n / 2
    nota_w = (ancho_n - 2 * 0.05) / 3
    return {
        "s": s,
        "rumor": (u(-0.27), u(0.505), u(1.34), u(0.12)),
        "hueco_sello": (u(0.535), u(0.505)),                   # entre la tira del rumor y la polaroid
        "rumor_etiqueta_w": u(0.21),
        "polaroid": (u(0.80), u(0.385), u(0.27), u(0.33)),
        "foto": (0.0, u(0.035), u(0.225), u(0.20)),            # relativo al centro de la polaroid
        "pin_tu": (u(0.80), u(0.535)),
        "cadena_y": u(0.33),
        "cadena_nota": (u(0.36), u(0.19)),
        "cadena_paso": u(0.43),
        "cadena_x_min": u(-mitad + 0.20),
        "pregunta": (u(-0.17), u(0.13), u(1.54), u(0.15)),
        "intentos": (u(0.80), u(0.135)),
        "notas_x": tuple(u(-mitad + nota_w / 2 + i * (nota_w + 0.05)) for i in range(3)),
        "notas_arriba": u(0.01),
        "nota_w": u(nota_w),
        "origen": (0.0, u(-0.17), u(1.40), u(0.32)),
        "giros": (-1.2, 0.6, -0.4),
    }


def cabecera_nota(numero, quien, hora, cabe, sep_numero="   ", sep_hora="  ·  "):
    """Cabecera de una nota candidata («número   quién  ·  hora») que CABE en una línea según `cabe(cadena) -> bool` (el
    llamador mide con su fuente, su tamaño y su ancho). Si no cabe, se recorta SOLO el nombre (con «…», nunca a medio
    «« (·»); la hora y el número van siempre enteros. Si ni con el nombre reducido a «…» cabe, se devuelve así (la hora
    entera manda sobre el ancho)."""
    quien, hora = str(quien or ""), str(hora or "")

    def armar(q):
        return f"{numero}{sep_numero}{q}" + (f"{sep_hora}{hora}" if hora else "")

    cadena = armar(quien)
    if cabe(cadena):
        return cadena
    q = quien
    while len(q.rstrip("…")) > 1:
        q = q.rstrip("…")[:-1].rstrip(" «(·,;:") + "…"
        cadena = armar(q)
        if cabe(cadena):
            return cadena
    return armar("…")


def posiciones_cadena(n, disp):
    """x de los eslabones 1..n de la cadena (TÚ es el 0, a la derecha). Si no caben, se aprietan."""
    xs = pvc.posiciones_rastro(n + 1, disp["polaroid"][0], disp["cadena_paso"], disp["cadena_x_min"])
    return xs[1:]


def hilo(a, b, caida, n=16):
    """Puntos del hilo entre dos chinchetas (cuelga `caida` m en el centro)."""
    return pvc.catenaria(a, b, caida, n)


def caida_hilo(t, s=1.0):
    """Caída del hilo `t` s después de clavar (llega flojo y se tensa). t None = tenso."""
    if t is None:
        return 0.010 * s
    return pvc.caida_hilo(t, dur=0.45, floja=0.07 * s, tensa=0.010 * s)


def foto_rastreo(partida):
    """Estado de la partida que el 3D refleja: (índice del salto, errores, descartadas de cada salto)."""
    return (partida.indice, partida.errores, tuple(tuple(sorted(s["descartadas"])) for s in partida.saltos))


def eventos_rastreo(antes, ahora, partida):
    """Lo que pasó entre dos fotos, en orden: ("bien", salto, opción) por cada salto acertado y ("error", salto, opción)
    por cada opción descartada nueva. Solo lee la partida."""
    if antes is None or antes == ahora:
        return []
    eventos = []
    for k in range(len(ahora[2])):
        nuevas = [i for i in ahora[2][k] if i not in (antes[2][k] if k < len(antes[2]) else ())]
        for i in nuevas:
            eventos.append(("error", k, i))
        if antes[0] <= k < ahora[0]:
            eventos.append(("bien", k, partida.saltos[k]["correcta"]))
    return eventos


# -- Cronología --

def disposicion_cronologia(ancho, alto, n):
    """Corcho de Ordenar la cadena (de arriba abajo): tira del rumor, tarjeta con las 3 instrucciones, el CORDEL que cruza
    el corcho con `n` viñetas colgadas + la tarjeta FIN, y la fila de botones (Mover antes / Mover después / Comprobar).
    Devuelve m locales ya escalados. Rectángulos como (cx, cy, ancho, alto)."""
    s = escala(alto)
    u = lambda v: v * s           # noqa: E731
    ancho_n = min(ANCHO_NORMAL, ancho / s)
    mitad = ancho_n / 2
    huecos = n + 1                                   # + la tarjeta FIN
    hueco = 0.03
    vin_w = (ancho_n - hueco * (huecos - 1)) / huecos
    xs = tuple(u(-mitad + vin_w / 2 + k * (vin_w + hueco)) for k in range(huecos))
    botones = (0.50, 0.50, 0.62)
    hueco_b = 0.06
    total_b = sum(botones) + hueco_b * (len(botones) - 1)
    bx, x = [], -total_b / 2
    for w in botones:
        bx.append(u(x + w / 2))
        x += w + hueco_b
    return {
        "s": s,
        "rumor": (0.0, u(0.537), u(ancho_n - 0.04), u(0.085)),
        "rumor_etiqueta_w": u(0.19),
        "instrucciones": (0.0, u(0.42), u(ancho_n - 0.04), u(0.125)),
        "cordel_y": u(0.305),
        "cordel_x": (u(-mitad - 0.02), u(mitad + 0.02)),
        "vineta_x": xs[:n],
        "fin_x": xs[n],
        "vineta": (u(vin_w), u(0.53)),
        "vineta_arriba": u(0.29),
        "botones_x": tuple(bx),
        "botones_w": tuple(u(w) for w in botones),
        "botones_y": u(-0.36),
        "boton_alto": u(0.105),
        "giros": (-1.0, 0.8, -0.5, 1.1, -0.7, 0.5, -0.9),
    }


def balanceo(t, amplitud=2.5, frecuencia=1.6, amortiguacion=2.2):
    """Ángulo (grados) de una tarjeta recién colgada que se balancea hasta pararse."""
    return pvc.balanceo(t, amplitud, frecuencia, amortiguacion)


# -- Geometría del hilo / cordel --

def cinta(puntos, grosor, z=0.0):
    """Malla de una cinta plana de `grosor` m que sigue la polilínea `puntos` [(x, y)] en el plano z. Devuelve
    (vértices [(x, y, z)], triángulos [i, j, k, ...]). Uniones en inglete (sin huecos en los quiebres)."""
    n = len(puntos)
    if n < 2:
        return [], []
    medio = grosor / 2
    vertices = []
    for i, (x, y) in enumerate(puntos):
        if i == 0:
            dx, dy = puntos[1][0] - x, puntos[1][1] - y
        elif i == n - 1:
            dx, dy = x - puntos[i - 1][0], y - puntos[i - 1][1]
        else:
            dx, dy = puntos[i + 1][0] - puntos[i - 1][0], puntos[i + 1][1] - puntos[i - 1][1]
        largo = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / largo * medio, dx / largo * medio
        vertices.append((x + nx, y + ny, z))
        vertices.append((x - nx, y - ny, z))
    triangulos = []
    for i in range(n - 1):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3
        triangulos += [a, b, c, b, d, c]
    return vertices, triangulos


# -- Cola de gestos --

class ColaGestos:
    """Gestos del personaje pendientes. La lógica nunca espera al 3D: si llega un gesto con otro en curso, el de curso se
    TERMINA YA (su resultado visual se aplica al instante) y el nuevo empieza. `actual` es el gesto en curso (o None)."""

    def __init__(self):
        self.pendientes = []
        self.actual = None

    def poner(self, gesto):
        self.pendientes.append(gesto)

    def hay_atraso(self):
        return self.actual is not None and bool(self.pendientes)

    def siguiente(self):
        """Saca el siguiente pendiente y lo hace actual (o None si no hay)."""
        self.actual = self.pendientes.pop(0) if self.pendientes else None
        return self.actual

    def terminar_actual(self):
        g, self.actual = self.actual, None
        return g

    def vacia(self):
        return self.actual is None and not self.pendientes
