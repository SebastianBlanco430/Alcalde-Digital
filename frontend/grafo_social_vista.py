# Vista del grafo social "Civitas" (Python puro: NO importa ursina, se prueba con pytest
# sin ventana). Decide DÓNDE se dibuja cada ciudadano en el panel y QUÉ estado tiene
# cada nodo/arista en un instante `t` de la animación de una propagación.
# frontend/panel_propagacion.py solo ejecuta este modelo en Ursina.
#
# La animación depende únicamente de `t` (suma de los dt), así que es determinista:
#   t = 0            -> solo el origen está encendido
#   t >= k * PASO    -> ya se alcanzó el salto k (propagacion["niveles"][k - 1])

import math

PASO_SEGUNDOS = 0.45          # duración de cada salto de la propagación

ORIGEN = "origen"
ALCANZADO = "alcanzado"
PENDIENTE = "pendiente"
FRENADO = "frenado"

# Posiciones fijas (x, y) en [-1, 1] (y arriba) de los 17 ciudadanos del grafo de ejemplo: la red de Ana a la
# izquierda (el ciclo Ana-Fábio-Ivan-Hugo-Elena como un lazo y las cadenas cortas hacia Júlia-Kauã y Carlos-Luana),
# la comunidad del Morro a la derecha (unida a la red de Ana por el puente Luana-Nayara, en la misma fila: un trazo
# horizontal corto que no cruza nada) y Diana (aislada) sola abajo a la derecha. Buscadas en una rejilla para que
# ninguna arista se cruce, los nombres (bajo el nodo, o hacia afuera en los bordes: ver
# resultado_grafo_calculos.lado_etiqueta) no pisen otros nodos ni nombres en el panel de resultado y los nodos no se
# toquen en el panel pequeño de alcance (lo comprueban las pruebas, con escala_nodos aplicada).
POSICIONES_EJEMPLO = {
    "Ana": (-0.4, 0.62),
    "Beto": (-0.2, 0.3),
    "Carlos": (-0.4, -0.35),
    "Diana": (0.8, -0.95),
    "Elena": (-0.6, 0.3),
    "Fábio": (-0.8, 0.62),
    "Gina": (-0.6, 0.95),
    "Hugo": (-0.8, -0.95),
    "Ivan": (-0.8, -0.35),
    "Júlia": (0.0, 0.95),
    "Kauã": (0.2, 0.62),
    "Luana": (0.0, -0.35),
    "Marcos": (0.6, 0.3),
    "Nayara": (0.4, -0.35),
    "Otávio": (0.8, -0.35),
    "Paula": (0.8, 0.62),
    "Quitéria": (0.6, 0.95),
}

# Escala de los nodos según cuántos ciudadanos hay: hasta NODOS_REFERENCIA (los 10 del grafo de antes), el tamaño de
# siempre; con más, se encogen con la raíz de la proporción (el área total de nodos se mantiene) para que quepan.
NODOS_REFERENCIA = 10


def escala_nodos(cantidad):
    return min(1.0, math.sqrt(NODOS_REFERENCIA / cantidad)) if cantidad > 0 else 1.0


# {ciudadano: (x, y)} de todos los ciudadanos del grafo. Los conocidos usan la tabla
# fija; los demás (otro grafo) se reparten en un círculo en orden de aparición, así el
# resultado siempre es determinista.
def posiciones(grafo_social):
    nombres = grafo_social.ciudadanos()
    resultado = {}
    desconocidos = [n for n in nombres if n not in POSICIONES_EJEMPLO]
    for nombre in nombres:
        if nombre in POSICIONES_EJEMPLO:
            resultado[nombre] = POSICIONES_EJEMPLO[nombre]
    for indice, nombre in enumerate(desconocidos):
        angulo = 2 * math.pi * indice / len(desconocidos)
        resultado[nombre] = (round(math.cos(angulo), 4), round(math.sin(angulo), 4))
    return resultado


# Aristas únicas (a, b) del grafo, sin repetir (a, b) y (b, a), en orden estable.
def aristas(grafo_social):
    vistas = set()
    resultado = []
    for a in grafo_social.ciudadanos():
        for b in grafo_social.vecinos(a):
            clave = frozenset((a, b))
            if clave not in vistas:
                vistas.add(clave)
                resultado.append((a, b))
    return resultado


# Salto alcanzado de cada ciudadano: el origen es 0 y los demás k según su nivel.
# Los que no reciben la publicación no aparecen.
def saltos_por_ciudadano(propagacion):
    saltos = {propagacion["origen"]: 0}
    for indice, nivel in enumerate(propagacion["niveles"], start=1):
        for nombre in nivel:
            saltos[nombre] = indice
    return saltos


# Segundos que dura la animación completa (0 si la publicación se frenó).
def duracion_total(propagacion):
    return len(propagacion["niveles"]) * PASO_SEGUNDOS


# Último salto ya alcanzado en el instante `t` (0 = solo el origen).
def salto_actual(propagacion, t):
    if t <= 0:
        return 0
    return min(len(propagacion["niveles"]), int(t / PASO_SEGUNDOS + 1e-9))


# ¿Terminó la animación en el instante `t`?
def terminada(propagacion, t):
    return t >= duracion_total(propagacion) - 1e-9


# Cuántos ciudadanos (sin el origen) han recibido la publicación en el instante `t`.
def alcanzados_hasta(propagacion, t):
    return sum(len(n) for n in propagacion["niveles"][:salto_actual(propagacion, t)])


# Estado de cada ciudadano en `t`: ORIGEN / ALCANZADO / PENDIENTE; con "reportar" el
# origen queda FRENADO (la publicación no sale de él) y los demás PENDIENTE.
def estado_nodos(propagacion, nombres, t):
    saltos = saltos_por_ciudadano(propagacion)
    actual = salto_actual(propagacion, t)
    resultado = {}
    for nombre in nombres:
        if nombre == propagacion["origen"]:
            frenado = propagacion["accion"] == "reportar"
            resultado[nombre] = FRENADO if frenado else ORIGEN
        elif nombre in saltos and saltos[nombre] <= actual:
            resultado[nombre] = ALCANZADO
        else:
            resultado[nombre] = PENDIENTE
    return resultado


# Estado de cada arista en `t`: True (activa) cuando sus dos extremos ya están
# alcanzados (origen incluido); con "reportar" ninguna se activa.
def estado_aristas(propagacion, lista_aristas, t):
    if propagacion["accion"] == "reportar":
        return {arista: False for arista in lista_aristas}
    saltos = saltos_por_ciudadano(propagacion)
    actual = salto_actual(propagacion, t)
    return {
        (a, b): (a in saltos and b in saltos and saltos[a] <= actual and saltos[b] <= actual)
        for a, b in lista_aristas
    }


# Texto bajo el grafo en el instante `t`. Compartir: el contador crece con los saltos
# hasta "Alcanzó a N de M ciudadanos"; Reportar: el mensaje de frenado.
def texto_resultado(propagacion, total_ciudadanos, t):
    if propagacion["accion"] == "reportar":
        return "Reporte: la publicación se frenó (alcance 0)"
    return f"Alcanzó a {alcanzados_hasta(propagacion, t)} de {total_ciudadanos} ciudadanos"


# Resumen compacto de `resumen_red_social` (backend): dos líneas, % de la red alcanzada y
# alcance por salto. Sin resumen o sin saltos -> "". No recalcula nada.
MAX_SALTOS_MOSTRADOS = 4


def texto_alcance_red(resumen):
    if not resumen or not resumen.get("alcance_por_salto"):
        return ""
    saltos = resumen["alcance_por_salto"]
    porcentaje = round(resumen["fraccion_alcanzada"] * 100)
    partes = [f"S{s['salto']} +{s['nuevos']}" for s in saltos[:MAX_SALTOS_MOSTRADOS]]
    if len(saltos) > MAX_SALTOS_MOSTRADOS:
        partes.append("…")
    return f"Red alcanzada: {porcentaje}%\n" + "  ".join(partes)


# -- Ciudadanos influyentes y comunidades aisladas ------------------------------

INFLUYENTES_MOSTRADOS = 3     # cuántos ciudadanos se destacan en el panel
MAX_NOMBRES_AISLADOS = 2      # nombres que caben en la línea de aislados ("+N" el resto)


# {ciudadano: grado} de los `n` más influyentes. Un grado 0 no influye: no se destaca.
def influyentes(grafo_social, n=INFLUYENTES_MOSTRADOS):
    return {c: g for c, g in grafo_social.ciudadanos_influyentes(n) if g > 0}


# Ciudadanos (en orden del grafo) que una publicación desde `origen` jamás alcanzaría
# por estar en otra comunidad. Origen desconocido -> vacío (no rompe el panel).
def aislados(grafo_social, origen):
    try:
        fuera = set(grafo_social.inalcanzables_desde(origen))
    except ValueError:
        return []
    return [c for c in grafo_social.ciudadanos() if c in fuera]


# Diámetro del nodo: crece con el grado entre `base` y `base * factor_max` (el de mayor
# grado). Con grado máximo 0 todos miden `base`.
def diametro_nodo(grado, grado_maximo, base, factor_max=1.35):
    if grado_maximo <= 0:
        return base
    return base * (1 + (factor_max - 1) * min(grado, grado_maximo) / grado_maximo)


# Línea bajo el grafo con los ciudadanos que la publicación no alcanza ("" si no hay).
def texto_aislados(nombres):
    if not nombres:
        return ""
    visibles = ", ".join(nombres[:MAX_NOMBRES_AISLADOS])
    resto = len(nombres) - MAX_NOMBRES_AISLADOS
    return f"Sin alcance: {visibles}" + (f" +{resto}" if resto > 0 else "")
