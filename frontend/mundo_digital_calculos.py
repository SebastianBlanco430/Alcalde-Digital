# Cálculos puros del mundo digital (sin ursina, testeables): geometría de la rejilla y las torres wireframe,
# estaciones de los personajes y toma de la cámara de diálogo, efecto glitch, plan de la animación de sentarse ante
# el computador, formato del temporizador y teclas de las opciones. La vista (escena, computador, interfaz) solo aplica
# estos datos.

import math
import random
from dataclasses import dataclass

# -- Plan de la animación en el mundo (computador): tramos (nombre, segundos) --

DURACION_CAMINAR = 0.6
DURACION_SENTARSE = 0.7
DURACION_ACERCAR = 0.9
DURACION_GLITCH = 0.55
DURACION_GLITCH_SALIDA = 0.45


def plan_sentarse():
    return [("caminar", DURACION_CAMINAR), ("sentarse", DURACION_SENTARSE), ("acercar", DURACION_ACERCAR),
            ("glitch", DURACION_GLITCH)]


# (x, z) del mundo de un punto local (lx a la derecha, lz hacia delante) de un objeto en (x, z) con `rumbo` (grados;
# la dirección de avance es (sin rumbo, cos rumbo), como en vendedor_calle).
def local_a_mundo(x, z, rumbo, lx, lz):
    r = math.radians(rumbo)
    return (x + lx * math.cos(r) + lz * math.sin(r), z - lx * math.sin(r) + lz * math.cos(r))


# -- Temporizador de la pregunta (se ve con texto, no solo con color) --

def formatear_tiempo(segundos):
    s = max(0, int(math.ceil(segundos)))
    return f"{s // 60}:{s % 60:02d}"


UMBRAL_URGENTE_S = 10.0
FRACCION_URGENTE = 0.25
FRACCION_AVISO = 0.5


# "normal" | "aviso" | "urgente" según lo que queda.
def nivel_temporizador(restante, total):
    if total <= 0:
        return "normal"
    if restante <= min(UMBRAL_URGENTE_S, total * FRACCION_URGENTE):
        return "urgente"
    if restante <= total * FRACCION_AVISO:
        return "aviso"
    return "normal"


def texto_temporizador(restante, total):
    nivel = nivel_temporizador(restante, total)
    sufijo = {"normal": "", "aviso": " (se acaba)", "urgente": " - ¡POCO TIEMPO!"}[nivel]
    return f"Tiempo: {formatear_tiempo(restante)}{sufijo}"


def fraccion_temporizador(restante, total):
    return 0.0 if total <= 0 else max(0.0, min(1.0, restante / total))


# -- Opciones y texto --

_TECLAS_NUMERO = {str(n): n for n in range(1, 10)} | {f"numpad {n}": n for n in range(1, 10)}


# Índice 0-based de la opción que elige la tecla (1-9 o teclado numérico), o None.
def indice_de_tecla(tecla):
    n = _TECLAS_NUMERO.get(tecla)
    return None if n is None else n - 1


def etiqueta_opcion(indice, texto):
    return f"{indice + 1}. {texto}"


# Una fila de la zona de opciones de la interfaz. tipo: opcion | prueba | modo_pruebas | cancelar | continuar | salir.
@dataclass(frozen=True)
class Fila:
    texto: str
    habilitada: bool
    tipo: str
    clave: str | None = None
    motivo: str = ""


TEXTO_CONTINUAR = "Continuar"
TEXTO_PRESENTAR = "Presentar una prueba..."
TEXTO_CANCELAR = "Cancelar"
TEXTO_SALIR = "Cerrar sesión y volver a la ciudad"


# Filas que muestra la interfaz para el nodo `vista` (VistaNodo de backend/logica/casos.py). `modo`: "opciones" (lo
# normal) o "pruebas" (el jugador escogiendo qué evidencia presentar). `evidencias`: [(id, nombre)] que tiene el jugador.
def filas_de_nodo(vista, modo, evidencias):
    if vista.tipo == "final":
        return [Fila(TEXTO_SALIR, True, "salir")]
    if vista.tipo == "dialogo":
        return [Fila(TEXTO_CONTINUAR, True, "continuar")]
    if modo == "pruebas":
        return [Fila(nombre, True, "prueba", eid) for eid, nombre in evidencias] + [Fila(TEXTO_CANCELAR, True, "cancelar")]
    filas = [Fila(o.texto, o.disponible, "opcion", o.id, o.motivo) for o in vista.opciones]
    if vista.admite_presentar:
        filas.append(Fila(TEXTO_PRESENTAR, bool(evidencias), "modo_pruebas",
                          motivo="" if evidencias else "No tienes pruebas todavía."))
    return filas


_RESULTADOS = {"exito": "ÉXITO", "parcial": "PARCIAL", "fracaso": "FRACASO"}


def texto_resultado(resultado):
    return f"Resultado: {_RESULTADOS.get(resultado, str(resultado).upper())}"


def texto_errores(errores, maximo):
    if not maximo:
        return ""
    return f"Pruebas mal usadas: {errores} de {maximo}"


# -- Geometría wireframe: listas de vértices de a pares (segmentos sueltos, para lineas_sueltas) --

# Rejilla en el plano y=0 de [-extension, extension]. Devuelve (menores, mayores): las mayores cada `eje_cada` celdas.
def lineas_rejilla(extension, paso, eje_cada):
    if paso <= 0 or extension <= 0 or eje_cada < 1:
        raise ValueError("extension, paso y eje_cada deben ser positivos.")
    menores, mayores = [], []
    n = int(extension // paso)
    for i in range(-n, n + 1):
        destino = mayores if i % eje_cada == 0 else menores
        c = i * paso
        destino += [(c, 0, -extension), (c, 0, extension), (-extension, 0, c), (extension, 0, c)]
    return menores, mayores


_ARISTAS_CAJA = ((0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7))


# 12 aristas (24 vértices) de una caja centrada en (cx, cy, cz) de tamaño (sx, sy, sz).
def aristas_caja(cx, cy, cz, sx, sy, sz):
    esquinas = [(cx + dx * sx / 2, cy + dy * sy / 2, cz + dz * sz / 2)
                for dy in (-1, 1) for dz in (-1, 1) for dx in (-1, 1)]
    return [esquinas[i] for a, b in _ARISTAS_CAJA for i in (a, b)]


# Torres del fondo: [(cx, cz, ancho, fondo, alto)], deterministas, fuera del radio central libre.
def torres_digitales(cantidad, semilla, radio_min, radio_max, alto_min=3.0, alto_max=16.0):
    azar = random.Random(semilla)
    torres = []
    for i in range(cantidad):
        ang = 2 * math.pi * (i + azar.random() * 0.8) / cantidad
        radio = azar.uniform(radio_min, radio_max)
        torres.append((round(radio * math.sin(ang), 2), round(radio * math.cos(ang), 2),
                       round(azar.uniform(1.2, 3.2), 2), round(azar.uniform(1.2, 3.2), 2),
                       round(azar.uniform(alto_min, alto_max), 2)))
    return torres


# Avatar de alambre: cajas (centro y tamaño) de cabeza, torso, brazos y piernas, con los pies en y = 0.
CAJAS_AVATAR = (
    (0.0, 1.62, 0.0, 0.26, 0.28, 0.26),     # cabeza
    (0.0, 1.15, 0.0, 0.42, 0.62, 0.22),     # torso
    (-0.30, 1.12, 0.0, 0.12, 0.60, 0.12),   # brazo izquierdo
    (0.30, 1.12, 0.0, 0.12, 0.60, 0.12),    # brazo derecho
    (-0.11, 0.41, 0.0, 0.15, 0.82, 0.15),   # pierna izquierda
    (0.11, 0.41, 0.0, 0.15, 0.82, 0.15),    # pierna derecha
)


# -- Estaciones de los personajes y cámara de diálogo --

# Posiciones (x, z) de `n` estaciones en un arco de `arco` grados frente al avatar (que mira a +z), a `radio` m.
def posiciones_estaciones(n, radio, arco=110.0):
    if n <= 0:
        return []
    if n == 1:
        return [(0.0, radio)]
    return [(round(radio * math.sin(math.radians(-arco / 2 + arco * i / (n - 1))), 3),
             round(radio * math.cos(math.radians(-arco / 2 + arco * i / (n - 1))), 3)) for i in range(n)]


ALTURA_OJOS_CAMARA = 1.75
ALTURA_RETRATO = 1.7


# Toma de la cámara de diálogo: {"position", "target"}. `estacion` = (x, z) del que habla (None = el narrador: se mira
# al centro del arco). La cámara se coloca detrás-derecha del avatar y mira a la estación.
def toma_dialogo(estacion, centro_arco=(0.0, 7.0)):
    hacia = centro_arco if estacion is None else estacion
    posicion = (1.3, ALTURA_OJOS_CAMARA, -2.6)
    return {"position": posicion, "target": (hacia[0], ALTURA_RETRATO if estacion else 1.3, hacia[1])}


# Un paso de suavizado exponencial de `actual` hacia `meta`.
def acercar_a(actual, meta, dt, rapidez=4.0):
    k = 1.0 - math.exp(-rapidez * max(0.0, dt))
    return tuple(a + (m - a) * k for a, m in zip(actual, meta))


# -- Glitch (colores GLITCH_A / GLITCH_B de frontend/materiales) --

# Intensidad 0-1 de un glitch que sube y baja con t en [0, 1] (pico en 0,5).
def intensidad_glitch(t):
    t = max(0.0, min(1.0, t))
    return math.sin(math.pi * t) ** 0.8


# Bandas del cuadro `cuadro`: [(y, alto, desplazamiento_x, 0|1, alfa)] (y en [-0.5, 0.5], 0 = color A, 1 = color B).
# Determinista por cuadro; cuanta más intensidad, más y más anchas son.
def bandas_glitch(cuadro, cantidad, intensidad):
    azar = random.Random(cuadro * 7919 + 13)
    activas = int(round(cantidad * max(0.0, min(1.0, intensidad))))
    bandas = []
    for i in range(cantidad):
        y, alto = azar.uniform(-0.5, 0.5), azar.uniform(0.01, 0.015 + 0.09 * intensidad)
        dx = azar.uniform(-0.25, 0.25) * (0.3 + intensidad)
        color, alfa = azar.randint(0, 1), azar.uniform(0.35, 0.85)
        bandas.append((y, alto, dx, color, alfa if i < activas else 0.0))
    return bandas


# Opacidad del velo oscuro que tapa la pantalla en el pico del glitch (para cambiar de escena sin que se vea).
def velo_glitch(intensidad):
    return max(0.0, min(1.0, (intensidad - 0.75) / 0.25))
