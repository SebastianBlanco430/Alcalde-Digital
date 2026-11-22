# Lógica PURA (sin ursina) del tutorial breve de la primera vez de cada tipo de misión: qué tutorial toca, si ya se vio, el guion
# (backend/datos/tutoriales_mision.json), su validación y la conversión de los pasos en una línea de tiempo.
#
# BANDERAS (misma regla que las demás «misiones visuales», frontend/banderas_visuales.py):
#   TUTORIAL_MISION = True; ALCALDE_TUTORIAL_MISION=0 lo apaga; ALCALDE_MISIONES_VISUALES=0 (la maestra) también.
#   ALCALDE_TUTORIAL_MISION_FORZAR=1 lo muestra siempre, aunque ya se haya visto (para probar).
#
# LO VISTO se guarda por jugador del PC (no por partida) en ajustes.json, clave extra «tutoriales_vistos». Los extras de los
# ajustes solo admiten ESCALARES, así que no es una lista sino un ENTERO DE BITS: el bit i vale 1 si el tutorial IDS[i] ya se
# vio. Los ajustes antiguos que no la traen leen 0 (nada visto). IDS solo se amplía por el final: reordenarlo cambiaría el
# significado de lo ya guardado.
#
# El tutorial NO tiene consecuencias en la partida: este módulo no toca GameState, billetera, logros ni reloj; solo decide y
# describe. La línea de tiempo reutiliza frontend/cinematica.LineaDeTiempo (Python puro).

import json
import math
import os
from pathlib import Path

TUTORIAL_MISION = True
VARIABLE = "ALCALDE_TUTORIAL_MISION"
VARIABLE_FORZAR = "ALCALDE_TUTORIAL_MISION_FORZAR"
CLAVE_AJUSTE = "tutoriales_vistos"
RUTA_GUION = Path(__file__).resolve().parent.parent / "datos" / "tutoriales_mision.json"

# Un tutorial por tipo de misión (en este orden se guardan los bits).
IDS = (
    "rastrear", "comparar", "cronologia", "chat", "senales", "contrarreloj",      # minijuegos de verificar
    "llegada", "parkour", "parkour_boton2", "investigacion", "rectificar", "dilemas",
    "civitas_estafas", "civitas_foto", "civitas_pantalla",
    "trabajo_atender", "trabajo_secuencia", "trabajo_barra", "trabajo_ritmo", "trabajo_entregas",
)
MINIJUEGOS = ("rastrear", "comparar", "cronologia", "chat", "senales", "contrarreloj")
MOTOR_A_ID = {"atender": "trabajo_atender", "secuencia": "trabajo_secuencia", "barra": "trabajo_barra",
              "ritmo": "trabajo_ritmo", "entregas": "trabajo_entregas"}
EVENTO_CIVITAS_A_ID = {"estafa": "civitas_estafas", "foto": "civitas_foto", "pantalla": "civitas_pantalla"}
TIPO_MISION_A_ID = {"verificar": None, "rectificar": "rectificar", "dilema": "dilemas", "llegada": "llegada",
                    "parkour": "parkour", "investigacion": "investigacion"}

ACCIONES = ("bocadillo", "mover", "tecla", "esperar", "error_demo", "turno_jugador", "camara")
MAX_BOCADILLO = 130
MAX_FRASE = 160
MAX_TITULO = 60
DURACION_MIN, DURACION_MAX = 20.0, 40.0        # s, tutorial completo (con la práctica estimada)
CORTOS = ("parkour_boton2",)                   # novedades de UN bocadillo: sin práctica y de unos segundos
DURACION_CORTO_MIN, DURACION_CORTO_MAX = 2.0, 12.0
SEGUNDOS_TURNO_ESTIMADO = 8.0                  # lo que se estima que tarda el jugador en su turno
SEGUNDOS_POR_CARACTER = 0.045                  # lectura de un bocadillo (se puede avanzar antes con Espacio/Enter/clic)
SEGUNDOS_BOCADILLO_MIN = 2.0
SEGUNDOS_TECLA = 0.45
SEGUNDOS_ERROR_DEMO = 2.6
SEGUNDOS_ESPERAR = 0.8
SEGUNDOS_MOVER = 0.6
SEGUNDOS_CAMARA = 2.5


# ---------------------------------------------------------------- banderas

def activo():
    """¿Está encendida la bandera PROPIA de los tutoriales de misión? (ALCALDE_TUTORIAL_MISION manda sobre la constante.)
    ARQ-004: backend/ no importa frontend; la bandera maestra de las misiones visuales la suma el controlador
    (frontend/registro_tutorial_mision.activo)."""
    valor = os.environ.get(VARIABLE, "").strip().lower()
    if valor in ("0", "false", "no", "off"):
        return False
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    return bool(TUTORIAL_MISION)


def forzar():
    """ALCALDE_TUTORIAL_MISION_FORZAR=1: se muestra siempre (para probar)."""
    return os.environ.get(VARIABLE_FORZAR, "").strip().lower() in ("1", "true", "si", "sí", "on")


# ---------------------------------------------------------------- qué tutorial toca

def id_tutorial(contexto):
    """Id del tutorial de este contexto, o None si ese tipo de misión no tiene.
    `contexto` es un dict con UNA de estas claves: «minijuego» (id del minijuego), «tipo» (tipo de misión), «evento_civitas»
    (tipo de evento de la bandeja) o «motor» (motor del trabajo). «parkour_boton2» lo pide el parkour con «segundo_boton»."""
    if not isinstance(contexto, dict):
        return None
    if contexto.get("minijuego") in MINIJUEGOS:
        return contexto["minijuego"]
    if contexto.get("evento_civitas") in EVENTO_CIVITAS_A_ID:
        return EVENTO_CIVITAS_A_ID[contexto["evento_civitas"]]
    if contexto.get("motor") in MOTOR_A_ID:
        return MOTOR_A_ID[contexto["motor"]]
    if contexto.get("tipo") == "parkour" and contexto.get("segundo_boton"):
        return "parkour_boton2"
    return TIPO_MISION_A_ID.get(contexto.get("tipo"))


def necesita_tutorial(id_, vistos, forzar_=False):
    """¿Hay que enseñarlo? Sí si el id existe y (se fuerza o aún no se vio). `vistos` es un conjunto de ids."""
    if id_ not in IDS:
        return False
    return bool(forzar_) or id_ not in set(vistos or ())


# ---------------------------------------------------------------- lo visto (entero de bits)

def vistos_desde_mascara(mascara):
    """Conjunto de ids vistos que representa el entero `mascara`. Valores raros (None, texto, negativos) leen «nada»."""
    if isinstance(mascara, bool) or not isinstance(mascara, int) or mascara < 0:
        return frozenset()
    return frozenset(id_ for i, id_ in enumerate(IDS) if mascara >> i & 1)


def mascara_de(vistos):
    mascara = 0
    for id_ in vistos or ():
        if id_ in IDS:
            mascara |= 1 << IDS.index(id_)
    return mascara


def marcar_visto(mascara, id_):
    """Máscara con `id_` añadido (sin cambios si el id no existe)."""
    return mascara_de(vistos_desde_mascara(mascara) | ({id_} if id_ in IDS else set()))


TODOS = (1 << len(IDS)) - 1          # todos los bits (lo usan las pruebas)


# ---------------------------------------------------------------- guion

def cargar(ruta=None):
    """Lee y VALIDA el guion. ValueError si algo no cumple las reglas."""
    with open(ruta or RUTA_GUION, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    validar(datos)
    return datos


def validar(datos):
    if not isinstance(datos, dict) or not datos:
        raise ValueError("tutoriales_mision.json: se esperaba un objeto con un guion por tipo.")
    for id_, guion in datos.items():
        if id_ not in IDS:
            raise ValueError(f"Tutorial desconocido: {id_!r}.")
        _validar_guion(id_, guion)


def _validar_guion(id_, guion):
    donde = f"tutorial {id_!r}"
    if not isinstance(guion, dict):
        raise ValueError(f"{donde}: el guion debe ser un objeto.")
    for clave in ("rotulo",):
        if clave in guion and (not isinstance(guion[clave], str) or not guion[clave].strip() or len(guion[clave]) > MAX_TITULO):
            raise ValueError(f"{donde}: «{clave}» debe ser un texto de hasta {MAX_TITULO} caracteres.")
    if "oscuro" in guion and not isinstance(guion["oscuro"], bool):
        raise ValueError(f"{donde}: «oscuro» debe ser true o false.")
    titulo, frase = str(guion.get("titulo", "")).strip(), str(guion.get("frase", "")).strip()
    if not titulo or len(titulo) > MAX_TITULO:
        raise ValueError(f"{donde}: «titulo» vacío o de más de {MAX_TITULO} caracteres.")
    if not frase or len(frase) > MAX_FRASE:
        raise ValueError(f"{donde}: «frase» vacía o de más de {MAX_FRASE} caracteres.")
    if not isinstance(guion.get("caso_demo"), dict):
        raise ValueError(f"{donde}: falta «caso_demo».")
    archivo = guion["caso_demo"].get("archivo")
    if archivo is not None:                       # el caso de demo vive DENTRO de backend/datos (sin «..» ni rutas absolutas)
        base = RUTA_GUION.parent.resolve()
        if not isinstance(archivo, str) or not (base / archivo).resolve().is_relative_to(base):
            raise ValueError(f"{donde}: «archivo» del caso de demo debe quedar dentro de backend/datos.")
    n_focos = guion.get("n_focos")
    if isinstance(n_focos, bool) or not isinstance(n_focos, int) or n_focos < 1:
        raise ValueError(f"{donde}: «n_focos» debe ser un entero >= 1 (cuántos elementos se pueden señalar).")
    pasos = guion.get("pasos")
    if not isinstance(pasos, list) or not pasos:
        raise ValueError(f"{donde}: sin pasos.")
    turnos = 0
    for i, paso in enumerate(pasos):
        _validar_paso(f"{donde}, paso {i + 1}", paso, n_focos)
        turnos += paso["accion"] == "turno_jugador"
    if turnos > 1:
        raise ValueError(f"{donde}: «Ahora tú» es UN solo paso (hay {turnos} turno_jugador).")
    duracion = duracion_estimada(pasos)
    minimo, maximo = (DURACION_CORTO_MIN, DURACION_CORTO_MAX) if id_ in CORTOS else (DURACION_MIN, DURACION_MAX)
    if not minimo <= duracion <= maximo:
        raise ValueError(f"{donde}: dura ~{duracion:.0f} s; debe estar entre {minimo:.0f} y {maximo:.0f}.")


def _validar_paso(donde, paso, n_focos):
    if not isinstance(paso, dict) or paso.get("accion") not in ACCIONES:
        raise ValueError(f"{donde}: acción desconocida ({paso.get('accion') if isinstance(paso, dict) else paso!r}).")
    accion = paso["accion"]
    if "foco" in paso:
        foco = paso["foco"]
        if isinstance(foco, bool) or not isinstance(foco, int) or not 0 <= foco < n_focos:
            raise ValueError(f"{donde}: foco {foco!r} fuera de rango (0..{n_focos - 1}).")
    elif accion in ("mover", "error_demo", "turno_jugador"):
        raise ValueError(f"{donde}: «{accion}» necesita «foco».")
    if accion in ("bocadillo", "error_demo", "turno_jugador"):
        texto = str(paso.get("texto", "")).strip()
        if not texto or len(texto) > MAX_BOCADILLO:
            raise ValueError(f"{donde}: «texto» vacío o de más de {MAX_BOCADILLO} caracteres.")
    if "etapa" in paso and (isinstance(paso["etapa"], bool) or paso["etapa"] not in (1, 2, 3)):
        raise ValueError(f"{donde}: «etapa» debe ser 1, 2 o 3.")
    if "texto2" in paso and (not isinstance(paso["texto2"], str) or not paso["texto2"].strip()
                             or len(paso["texto2"]) > MAX_BOCADILLO):
        raise ValueError(f"{donde}: «texto2» vacío o de más de {MAX_BOCADILLO} caracteres.")
    if accion == "turno_jugador":
        falla = str(paso.get("si_falla", "")).strip()
        if not falla or len(falla) > MAX_BOCADILLO:
            raise ValueError(f"{donde}: «si_falla» vacío o de más de {MAX_BOCADILLO} caracteres.")
    if "hasta" in paso and paso["hasta"] not in ("fuera", "dentro", "nota"):
        raise ValueError(f"{donde}: «hasta» debe ser fuera, dentro o nota.")
    if accion == "camara" and paso.get("a") not in ("inicio", "meta"):
        raise ValueError(f"{donde}: «camara» necesita «a»: «inicio» o «meta».")
    if accion == "tecla" and not str(paso.get("k", "")).strip():
        raise ValueError(f"{donde}: «tecla» sin «k».")
    for clave in ("s", "avanza"):
        if clave in paso and (isinstance(paso[clave], bool) or not isinstance(paso[clave], (int, float))
                              or not math.isfinite(paso[clave]) or paso[clave] < 0):
            raise ValueError(f"{donde}: «{clave}» debe ser un número >= 0.")


# ---------------------------------------------------------------- tiempos

def duracion_paso(paso):
    """Segundos que dura un paso en la línea de tiempo. El turno del jugador no tiene límite (math.inf)."""
    accion = paso["accion"]
    if accion == "turno_jugador":
        return math.inf
    if "s" in paso:
        return float(paso["s"])
    if accion == "bocadillo":
        return max(SEGUNDOS_BOCADILLO_MIN, len(paso["texto"]) * SEGUNDOS_POR_CARACTER)
    return {"mover": SEGUNDOS_MOVER, "tecla": SEGUNDOS_TECLA, "esperar": SEGUNDOS_ESPERAR,
            "error_demo": SEGUNDOS_ERROR_DEMO, "camara": SEGUNDOS_CAMARA}[accion]


def duracion_estimada(pasos):
    """Duración total estimada (s), contando el turno del jugador como SEGUNDOS_TURNO_ESTIMADO."""
    return sum(SEGUNDOS_TURNO_ESTIMADO if p["accion"] == "turno_jugador" else duracion_paso(p) for p in pasos)


def etapa_de(pasos, indice):
    """Etapa (1 «Mira», 2 «Ahora tú», 3 «De verdad») del paso `indice`: el turno del jugador es la 2."""
    turno = next((i for i, p in enumerate(pasos) if p["accion"] == "turno_jugador"), None)
    if turno is None or indice < turno:
        return 1
    return 2 if indice == turno else 3


ROTULOS_ETAPA = {1: "Mira", 2: "Ahora tú", 3: "De verdad"}


def rotulo_progreso(etapa, total=3):
    return f"Tutorial {etapa} de {total}: {ROTULOS_ETAPA[etapa]}"


# ---------------------------------------------------------------- línea de tiempo

# ARQ-004: construir_linea (la LineaDeTiempo de frontend/cinematica con un tramo por paso) vive ahora en quien la usa,
# frontend/tutorial_mision_vista.construir_linea: backend/ no importa frontend.
