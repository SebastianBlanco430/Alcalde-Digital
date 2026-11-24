# Cálculos del interrogatorio como novela visual (frontend/interrogatorio_vn.py). Python puro, sin ursina, con tests en
# tests/test_interrogatorio_vn.py.
#
# - Qué modelo 3D y qué colores lleva cada personaje del caso (backend/datos/interrogatorio_modelos.json + su retrato).
# - Cómo se traduce la `expresion` de cada nodo a postura del cuerpo + gesto de cara + clip, y cómo se mezclan (0,25 s).
# - El texto letra a letra y la boca que se abre con cada vocal.
# - El reparto de las opciones abajo (una o dos columnas) y los acusados del tablero de sospechosos.

import json
import math
from pathlib import Path

RUTA_MODELOS = Path(__file__).resolve().parent.parent / "backend" / "datos" / "interrogatorio_modelos.json"

# Modelos que se pueden pedir: archivo -> rol que entiende npc_calculos.plan_npc.
MODELOS = {
    "periodista.glb": "periodista", "smoking.glb": "candidato", "ciudadano.glb": "ciudadano",
    "npc_hombre_01.glb": "npc_hombre_01", "npc_hombre_02.glb": "npc_hombre_02", "npc_hombre_03.glb": "npc_hombre_03",
    "npc_mujer_01.glb": "npc_mujer_01", "npc_mujer_02.glb": "npc_mujer_02",
}
MODELO_HOMBRE = "npc_hombre_01.glb"
MODELO_MUJER = "npc_mujer_02.glb"

TIEMPO_MEZCLA = 0.25          # s de transición entre gestos
LETRAS_POR_SEGUNDO = 55.0

# -- Expresiones: postura del cuerpo + gesto de cara + clip --
# postura: npc_postura (sociable, neutro, aislado, celular, enojado). Cara: alza y frunce de cejas (0..1), sonrisa (0..1),
# mirada (x, z en -1..1, 0 = a la cámara), esquiva (cuánto se le escapa la mirada), parpadeo (multiplicador de ritmo),
# menton (grados: + arriba). balanceo: amplitud (m) del peso que pasa de un pie a otro. braceo: amplitud (grados) del
# vaivén corto del cuerpo al hablar enojado.
PERFILES = {
    "neutral": {"postura": "neutro", "alza": 0.10, "frunce": 0.00, "sonrisa": 0.30, "mirada": (0.0, 0.0), "esquiva": 0.3,
                "parpadeo": 1.0, "menton": 0.0, "balanceo": 0.0, "braceo": 0.0},
    "serio": {"postura": "neutro", "alza": 0.00, "frunce": 0.45, "sonrisa": 0.12, "mirada": (0.0, 0.0), "esquiva": 0.0,
              "parpadeo": 0.7, "menton": -2.0, "balanceo": 0.0, "braceo": 0.0},
    # nervioso y triste: cuerpo con la postura neutra (la «aislado» de los peatones suma ~80° de cabeza gacha y en el
    # pecho y el primer plano solo se veía el pelo, S4); se leen por cejas, mirada esquiva y parpadeo.
    "nervioso": {"postura": "neutro", "alza": 0.55, "frunce": 0.10, "sonrisa": 0.15, "mirada": (0.6, -0.3), "esquiva": 1.0,
                 "parpadeo": 2.6, "menton": -4.0, "balanceo": 0.025, "braceo": 0.0},
    "enojado": {"postura": "enojado", "alza": 0.00, "frunce": 1.00, "sonrisa": 0.00, "mirada": (0.0, 0.05), "esquiva": 0.1,
                "parpadeo": 0.8, "menton": 2.0, "balanceo": 0.0, "braceo": 3.0},
    "satisfecho": {"postura": "sociable", "alza": 0.35, "frunce": 0.00, "sonrisa": 0.95, "mirada": (0.0, 0.1),
                   "esquiva": 0.2, "parpadeo": 1.0, "menton": 6.0, "balanceo": 0.0, "braceo": 0.0},
    "triste": {"postura": "neutro", "alza": 0.40, "frunce": 0.20, "sonrisa": 0.05, "mirada": (0.0, -0.5), "esquiva": 0.4,
               "parpadeo": 1.2, "menton": -6.0, "balanceo": 0.0, "braceo": 0.0},
    "sorprendido": {"postura": "neutro", "alza": 1.00, "frunce": 0.00, "sonrisa": 0.20, "mirada": (0.0, 0.1),
                    "esquiva": 0.0, "parpadeo": 0.4, "menton": 3.0, "balanceo": 0.0, "braceo": 0.0},
    # Reacciones a las pruebas (no vienen del caso: las pone la vista).
    "burla": {"postura": "sociable", "alza": 0.25, "frunce": 0.15, "sonrisa": 0.75, "mirada": (-0.3, 0.2), "esquiva": 0.2,
              "parpadeo": 1.0, "menton": 7.0, "balanceo": 0.0, "braceo": 0.0},
}
NUMERICOS = ("alza", "frunce", "sonrisa", "esquiva", "parpadeo", "menton", "balanceo", "braceo")


def perfil_de(expresion):
    """Perfil de la expresión (lo desconocido = neutral). Siempre una copia."""
    perfil = PERFILES.get(str(expresion or "").strip().lower(), PERFILES["neutral"])
    return dict(perfil)


def mezclar_perfiles(a, b, k):
    """Perfil intermedio de a a b (k en 0..1). La postura cambia a la de b a mitad (npc_postura ya la funde)."""
    k = max(0.0, min(1.0, k))
    salida = {clave: a[clave] + (b[clave] - a[clave]) * k for clave in NUMERICOS}
    salida["mirada"] = tuple(a["mirada"][i] + (b["mirada"][i] - a["mirada"][i]) * k for i in range(2))
    salida["postura"] = b["postura"] if k >= 0.5 else a["postura"]
    return salida


def avance_mezcla(k, dt, tiempo=TIEMPO_MEZCLA, reducir=False):
    """Avanza la mezcla entre gestos (de 0 a 1 en `tiempo` s). Con reducir: el cambio es inmediato pero sin sacudidas."""
    if reducir:
        return 1.0
    return min(1.0, k + max(0.0, dt) / max(1e-3, tiempo))


def suave(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def balanceo(t, amplitud, frecuencia=0.7):
    """Desplazamiento lateral (m) del peso que pasa de un pie a otro."""
    return amplitud * math.sin(2 * math.pi * frecuencia * t)


def braceo(t, amplitud, hablando, frecuencia=2.4):
    """Giro corto (grados) del torso al hablar enojado: solo mientras habla."""
    return amplitud * math.sin(2 * math.pi * frecuencia * t) if hablando else 0.0


def mirada(t, perfil, semilla=0):
    """Mirada (x, z): la base del perfil más una deriva que crece con `esquiva` (ojos que se escapan)."""
    bx, bz = perfil["mirada"]
    e = perfil["esquiva"]
    dx = math.sin(t * 1.7 + semilla) * 0.35 + math.sin(t * 0.6 + semilla * 2.1) * 0.25
    dz = math.sin(t * 1.1 + semilla * 0.7) * 0.18
    return max(-1.0, min(1.0, bx + dx * e)), max(-1.0, min(1.0, bz + dz * e))


def parpadeo(t, ritmo=1.0, semilla=0):
    """Cierre de párpados 0..1: parpadeos breves; `ritmo` > 1 parpadea más a menudo (nervioso)."""
    periodo = 3.2 / max(0.2, ritmo)
    fase = (t + (semilla % 13) * 0.37) % periodo
    if fase < 0.12:
        return math.sin(math.pi * fase / 0.12)
    return 0.0


# -- Texto letra a letra y boca --

def letras_visibles(t, total, cps=LETRAS_POR_SEGUNDO, reducir=False):
    """Cuántas letras se ven a los `t` s (todas con reducir)."""
    if reducir or cps <= 0:
        return total
    return max(0, min(total, int(t * cps)))


VOCALES = set("aeiouáéíóúAEIOUÁÉÍÓÚ")


def apertura_letra(caracter):
    """Apertura de boca (0..1) para la última letra escrita: vocales abren, consonantes poco, pausas cierran."""
    if not caracter or caracter.isspace() or caracter in ".,;:!?¡¿«»—-()\"'…":
        return 0.0
    if caracter in "aáAÁ":
        return 0.85
    if caracter in VOCALES:
        return 0.6
    if caracter in "mbpMBP":
        return 0.05
    return 0.25


def apertura_texto(texto, n):
    """Apertura de la boca con `n` letras escritas de `texto` (0 si ya terminó)."""
    if n <= 0 or n >= len(texto):
        return 0.0
    return apertura_letra(texto[n - 1])


# -- Modelo y colores de cada personaje --

def cargar_mapeo(ruta=RUTA_MODELOS):
    try:
        with open(ruta, encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError):
        return {}


def es_mujer(retrato):
    return str((retrato or {}).get("pelo_estilo", "")).lower() == "largo"


def modelo_para(caso_id, personaje_id, retrato, mapeo):
    """(archivo, rol) del .glb del personaje. Nunca falla: sin mapeo, un modelo por defecto según el retrato."""
    entrada = (((mapeo or {}).get("casos") or {}).get(caso_id) or {}).get(personaje_id) or {}
    archivo = entrada.get("modelo")
    if archivo not in MODELOS:
        defecto = ((mapeo or {}).get("por_defecto") or {}).get("mujer" if es_mujer(retrato) else "hombre") or {}
        archivo = defecto.get("modelo")
    if archivo not in MODELOS:
        archivo = MODELO_MUJER if es_mujer(retrato) else MODELO_HOMBRE
    return archivo, MODELOS[archivo]


def _rgb255(valor, defecto):
    try:
        r, g, b = (int(max(0, min(255, c))) for c in valor)
        return r, g, b
    except (TypeError, ValueError):
        return defecto


def aspecto_de(retrato):
    """Aspecto para npc_calculos.plan_npc: piel y pelo en 0..255."""
    retrato = retrato or {}
    return {"piel": _rgb255(retrato.get("piel"), (214, 170, 130)), "pelo": _rgb255(retrato.get("pelo"), (40, 30, 30)),
            "pantalon": (40, 40, 50)}


def colores_ropa(retrato, archivo):
    """(camiseta, pantalon) en 0..1 a partir del color de ropa del retrato. El traje (smoking) va entero del mismo color."""
    r, g, b = _rgb255((retrato or {}).get("ropa"), (80, 80, 110))
    camiseta = (r / 255, g / 255, b / 255)
    if archivo == "smoking.glb":
        return camiseta, camiseta
    pantalon = tuple(max(0.0, c * 0.45) for c in camiseta)
    return camiseta, pantalon


PEINADOS = {"corto": "corto", "largo": "largo", "calvo": "calvo"}


def rasgos_de(retrato):
    """Rasgos de cara (rostro_calculos.descriptor_peaton) a partir del retrato: peinado y accesorio."""
    retrato = retrato or {}
    accesorio = str(retrato.get("accesorio", "ninguno")).lower()
    return {
        "peinado": PEINADOS.get(str(retrato.get("pelo_estilo", "corto")).lower(), "corto"),
        "iris": (0.20, 0.13, 0.07),
        "cejas": (0.026, 0.0068, 0.006),
        "inclinacion": 6.0,
        "gorra": None,
        "gafas": accesorio == "gafas",
        # «barba» se dibuja como bigote: las barbas por código del rostro manchan las mejillas en primer plano.
        "bigote": accesorio == "barba",
        "barba": None,
        "arrugas": False,
    }


def semilla_de(personaje_id):
    """Semilla estable (para el desfase de la animación y la cara) a partir del id del personaje."""
    return sum((i + 1) * ord(c) for i, c in enumerate(str(personaje_id))) % 997 + 3


# -- Encuadre del NPC delante de la cámara --

def escala_pantalla(distancia, fov_horizontal, aspecto):
    """Metros por unidad de camera.ui a `distancia` de la cámara (fov horizontal en grados, como Ursina)."""
    return 2.0 * distancia * math.tan(math.radians(fov_horizontal) / 2.0) / max(0.1, aspecto)


def encuadre(x_ui, y_coronilla_ui, distancia, fov_horizontal, aspecto, altura_coronilla):
    """(x, y) local a la cámara de los PIES del NPC para que su coronilla quede en (x_ui, y_coronilla_ui) de pantalla."""
    k = escala_pantalla(distancia, fov_horizontal, aspecto)
    return x_ui * k, y_coronilla_ui * k - altura_coronilla


# -- Opciones abajo: una columna o dos --

def disposicion_opciones(n, alto_panel, ancho_panel, alto_max=0.056, margen=0.012):
    """[(x, y, ancho, alto)] (relativos al centro del panel) de cada opción, en orden de teclado (1..n).
    Hasta 4 opciones: una columna. Más: dos columnas (la primera se llena antes)."""
    if n <= 0:
        return []
    columnas = 1 if n <= 4 else 2
    filas = math.ceil(n / columnas)
    alto = min(alto_max, (alto_panel - 2 * margen) / filas)
    ancho = (ancho_panel - 2 * margen - (columnas - 1) * margen) / columnas
    arriba = alto_panel / 2 - margen - alto / 2
    salida = []
    for i in range(n):
        columna, fila = divmod(i, filas)
        x = -ancho_panel / 2 + margen + ancho / 2 + columna * (ancho + margen)
        salida.append((x, arriba - fila * alto, ancho, alto))
    return salida


# -- Tablero de sospechosos --

def acusados_de(datos_caso):
    """{id de opción de acusación: id del personaje acusado} de todos los nodos de acusación del caso."""
    salida = {}
    for nodo in ((datos_caso or {}).get("nodos") or {}).values():
        if nodo.get("tipo") != "acusacion":
            continue
        for acusado in nodo.get("acusados") or ():
            if acusado.get("id") and acusado.get("personaje"):
                salida[acusado["id"]] = acusado["personaje"]
    return salida


def es_acusacion(claves_filas, acusados):
    """¿Las filas de opciones son las de una acusación? (al menos una clave es de un acusado)."""
    return any(clave in acusados for clave in claves_filas if clave)


def posiciones_tablero(n, ancho=1.6):
    """x de cada miniatura del tablero (centradas)."""
    if n <= 0:
        return []
    paso = ancho / max(1, n)
    return [-ancho / 2 + paso * (i + 0.5) for i in range(n)]


# -- Reacciones a las pruebas --

DUR_CONTRADICCION = 2.2
DUR_REACCION = 1.6


def reaccion_a_prueba(correcta, expresion_actual):
    """Expresión que adopta el NPC tras una prueba: nervioso o enojado si le pillan, burla o indiferencia si no."""
    if correcta:
        return "enojado" if expresion_actual == "enojado" else "nervioso"
    return "burla"


def zoom_contradiccion(t, dur=DUR_CONTRADICCION, reducir=False):
    """0..1: cuánto se acerca la cámara al NPC (sube rápido, se mantiene y vuelve)."""
    if reducir or t < 0 or t >= dur:
        return 0.0
    if t < 0.25:
        return suave(t / 0.25)
    if t > dur - 0.5:
        return suave((dur - t) / 0.5)
    return 1.0


def alerta(t, dur=DUR_CONTRADICCION, reducir=False):
    """Opacidad del fondo de alerta (rojo) durante la contradicción."""
    if t < 0 or t >= dur:
        return 0.0
    base = 0.45 * (1 - t / dur)
    if reducir:
        return base * 0.6
    return base * (0.75 + 0.25 * math.cos(t * 12))
