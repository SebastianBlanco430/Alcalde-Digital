# Cinemática de la intro: la parte PURA (no importa ursina). Ver frontend/intro_cinematica.py (lo que dibuja) y el guion de
# la bóveda (00-Proyecto/guion-cinematica-intro.md), copiado literal en backend/datos/intro_cinematica.json.
#
#   - GLOBOS: cada línea del guion se parte en ORACIONES (partir_oraciones) y cada oración es un globo, una a la vez. El
#     globo dura su tiempo de lectura: 1,5 s + 0,06 s por carácter, mínimo 2,5 s (tiempo_lectura).
#   - PLAN: plan_intro() convierte las escenas en una lista de Paso (un tramo por globo, más cámara, pausas y fundidos);
#     plan_director() da el [(nombre, duracion)] que ejecuta frontend/director_cinematica.py. Espacio = siguiente tramo
#     (siguiente globo); Esc = todo. guion_cinematicas.escalar(plan, 0) lo resuelve al instante (tests).
#   - RECORRIDO (escena 6): pasos_foco() da las viñetas «foco» de frontend/cinematica_final.crear_vinetas, una por oración,
#     con su tiempo de lectura en «segundos».
#
# BANDERA. INTRO_CINEMATICA = False (o ALCALDE_INTRO_CINEMATICA=0): no hay cinemática y el tutorial de viñetas sale como
# antes. ALCALDE_INTRO_FASE=<n> elige la fase (1 = plaza, título, periodista y recorrido).

import json
import os
import re
from collections import namedtuple
from pathlib import Path

INTRO_CINEMATICA = True
RUTA_GUION = Path(__file__).resolve().parent.parent / "backend" / "datos" / "intro_cinematica.json"

LECTURA_BASE = 1.5               # s
LECTURA_POR_CARACTER = 0.06      # s por carácter
LECTURA_MINIMA = 2.5             # s

HABLANTES = ("Ciudadano", "Influencer", "Periodista", "")      # "" = narración (escena 2)
TOMAS_REEL = ("cara", "muneca_i", "muneca_d", "lejos")

# Duraciones de los tramos sin globo (s).
PLAZA_BAJADA = 3.0               # la cámara baja hacia la fuente antes del primer globo
FUNDIDO_A_NEGRO = 0.8            # de la plaza al negro del título
TITULO_ENTRADA = 1.2             # el título aparece solo, antes de sus globos
TITULO_SALIDA = 0.6              # el título se apaga (sigue el negro)
SALIDA_A_JUEGO = 0.8             # del negro del periodista al juego (empieza el recorrido)

FASE_MINIMA = 1
FASE_INTRO = FASE_MINIMA
ESCENAS_POR_FASE = {1: ("plaza", "titulo", "periodista")}
ESCENAS_GUION = ("plaza", "titulo", "telefono", "reel", "periodista")

Globo = namedtuple("Globo", "escena hablante texto segundos toma")
Paso = namedtuple("Paso", "nombre duracion escena tipo globo")       # tipo: globo | pausa | camara | fundido | titulo


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def intro_activa():
    """¿Hay cinemática de intro? ALCALDE_INTRO_CINEMATICA=1/0 manda sobre la constante."""
    return _bandera("ALCALDE_INTRO_CINEMATICA", INTRO_CINEMATICA)


def fase_intro():
    """Fase de la cinemática (ALCALDE_INTRO_FASE); una fase sin escenas definidas cae a la mínima."""
    try:
        fase = int(os.environ.get("ALCALDE_INTRO_FASE", "").strip() or FASE_INTRO)
    except ValueError:
        fase = FASE_INTRO
    return fase if fase in ESCENAS_POR_FASE else FASE_MINIMA


# -- Oraciones y tiempo de lectura ---------------------------------------------------------------------------------------

def tiempo_lectura(texto):
    """Segundos que se queda un globo: 1,5 + 0,06 por carácter, nunca menos de 2,5."""
    return round(max(LECTURA_MINIMA, LECTURA_BASE + LECTURA_POR_CARACTER * len(str(texto).strip())), 3)


# Fin de oración: . ! ? … (con comillas o paréntesis de cierre) seguido de espacio y de algo que abre otra oración.
_FIN = re.compile(r"([.!?…]+[\"»”’)]*)\s+(?=[¡¿«\"“(]?[A-ZÁÉÍÓÚÑÜ0-9])")
_ABREVIATURAS = {"p", "ej", "etc", "sr", "sra", "srta", "dr", "dra", "n", "núm", "pág", "aprox", "av"}


def partir_oraciones(texto):
    """Lista de oraciones de `texto` (espacios normalizados). No corta en abreviaturas («p. ej.»), en números («3.5»)
    ni en signos de apertura («¡», «¿»): solo donde termina una oración y empieza otra."""
    texto = " ".join(str(texto or "").split())
    if not texto:
        return []
    piezas, inicio = [], 0
    for m in _FIN.finditer(texto):
        fin = m.end(1)
        palabra = re.search(r"(\w+)\.$", texto[inicio:fin])
        if palabra and palabra.group(1).lower() in _ABREVIATURAS:
            continue
        piezas.append(texto[inicio:fin].strip())
        inicio = m.end()
    resto = texto[inicio:].strip()
    if resto:
        piezas.append(resto)
    return piezas


# -- Guion ---------------------------------------------------------------------------------------------------------------

def cargar_guion(ruta=None, elementos=None):
    """El JSON del guion, validado. `elementos`: los elementos del HUD que admite el recorrido (None = no se revisan).
    ValueError si falta algo, hay un hablante desconocido o una línea vacía."""
    with open(ruta or RUTA_GUION, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    escenas = {e.get("id"): e for e in datos.get("escenas", [])}
    for clave in ESCENAS_GUION:
        if clave not in escenas:
            raise ValueError(f"intro_cinematica.json: falta la escena «{clave}».")
        for linea in escenas[clave].get("lineas", []):
            if linea.get("hablante") not in HABLANTES:
                raise ValueError(f"Hablante desconocido en «{clave}»: {linea.get('hablante')!r}")
            if not partir_oraciones(linea.get("texto")):
                raise ValueError(f"Línea vacía en la escena «{clave}».")
            if clave == "reel" and linea.get("toma") not in TOMAS_REEL:
                raise ValueError(f"Toma desconocida en el reel: {linea.get('toma')!r}")
            pausa = linea.get("pausa_despues", 0.0)
            if not isinstance(pausa, (int, float)) or pausa < 0:
                raise ValueError(f"pausa_despues inválida en «{clave}»: {pausa!r}")
    if not str(escenas["titulo"].get("titulo", "")).strip():
        raise ValueError("La escena «titulo» no trae título.")
    recorrido = datos.get("recorrido") or {}
    pasos = recorrido.get("pasos") or []
    if not pasos:
        raise ValueError("intro_cinematica.json: el recorrido no trae pasos.")
    for paso in pasos:
        if elementos is not None and paso.get("elemento") not in elementos:
            raise ValueError(f"Paso del recorrido con un elemento desconocido: {paso.get('elemento')!r}")
        if not paso.get("texto") or not str(paso.get("titulo", "")).strip():
            raise ValueError(f"Paso del recorrido sin título o sin texto: {paso!r}")
    datos["_escenas"] = escenas
    return datos


def lineas_de(guion, escena):
    return list(guion["_escenas"][escena].get("lineas", []))


def globos_de(guion, escena):
    """[(Globo, pausa_despues)] de una escena: una entrada por oración; la pausa va tras la última oración de su línea."""
    salida = []
    for linea in lineas_de(guion, escena):
        oraciones = partir_oraciones(linea["texto"])
        for k, oracion in enumerate(oraciones):
            pausa = float(linea.get("pausa_despues", 0.0)) if k == len(oraciones) - 1 else 0.0
            salida.append((Globo(escena, linea["hablante"], oracion, tiempo_lectura(oracion), linea.get("toma")), pausa))
    return salida


# -- Plan ----------------------------------------------------------------------------------------------------------------

def _pasos_globos(guion, escena):
    pasos = []
    for k, (globo, pausa) in enumerate(globos_de(guion, escena), start=1):
        pasos.append(Paso(f"{escena}_{k}", globo.segundos, escena, "globo", globo))
        if pausa > 0:
            pasos.append(Paso(f"{escena}_pausa_{k}", pausa, escena, "pausa", None))
    return pasos


def plan_intro(guion, fase=FASE_MINIMA):
    """Lista de Paso de la cinemática (escenas 1-5; la 6 es el recorrido, aparte). Nombres únicos."""
    escenas = ESCENAS_POR_FASE.get(fase, ESCENAS_POR_FASE[FASE_MINIMA])
    pasos = []
    for escena in escenas:
        if escena == "plaza":
            pasos.append(Paso("plaza_bajada", PLAZA_BAJADA, "plaza", "camara", None))
            pasos += _pasos_globos(guion, "plaza")
            pasos.append(Paso("plaza_fundido", FUNDIDO_A_NEGRO, "plaza", "fundido", None))
        elif escena == "titulo":
            pasos.append(Paso("titulo_entrada", TITULO_ENTRADA, "titulo", "titulo", None))
            pasos += _pasos_globos(guion, "titulo")
            pasos.append(Paso("titulo_salida", TITULO_SALIDA, "titulo", "titulo", None))
        elif escena == "periodista":
            pasos += _pasos_globos(guion, "periodista")
            pasos.append(Paso("periodista_salida", SALIDA_A_JUEGO, "periodista", "fundido", None))
    return pasos


def plan_director(pasos):
    """[(nombre, duracion)] para DirectorCinematica.reproducir."""
    return [(p.nombre, p.duracion) for p in pasos]


def duracion_total(pasos):
    return round(sum(p.duracion for p in pasos), 3)


def progreso_escena(pasos, nombre, t):
    """Avance 0..1 de la ESCENA del paso `nombre` cuando ese paso va por `t` (0..1). Sirve para que la cámara siga
    una sola curva a lo largo de todos los globos de la escena."""
    actual = next((p for p in pasos if p.nombre == nombre), None)
    if actual is None:
        return 0.0
    de_la_escena = [p for p in pasos if p.escena == actual.escena]
    total = sum(p.duracion for p in de_la_escena)
    if total <= 0:
        return 1.0
    hecho = 0.0
    for p in de_la_escena:
        if p.nombre == nombre:
            hecho += p.duracion * max(0.0, min(1.0, t))
            break
        hecho += p.duracion
    return max(0.0, min(1.0, hecho / total))


# -- Recorrido del HUD (escena 6) ----------------------------------------------------------------------------------------

def pasos_foco(guion):
    """Viñetas «foco» (cinematica_final.crear_vinetas): una por oración, con título «Periodista · <elemento>» y su
    tiempo de lectura en «segundos»."""
    recorrido = guion["recorrido"]
    hablante = recorrido.get("hablante", "Periodista")
    vinetas = []
    for paso in recorrido["pasos"]:
        textos = paso["texto"] if isinstance(paso["texto"], list) else [paso["texto"]]
        for texto in textos:
            for oracion in partir_oraciones(texto):
                vinetas.append({"tipo": "foco", "elemento": paso["elemento"], "titulo": f"{hablante} · {paso['titulo']}",
                                "texto": oracion, "segundos": tiempo_lectura(oracion)})
    return vinetas
