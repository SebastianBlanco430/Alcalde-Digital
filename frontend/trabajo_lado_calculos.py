# Separación de los carteles «TRABAJO» (puro, con tests; pulido visual M1.2, diagnóstico D8).
# Dos tiendas vecinas (panadería y supermercado del Mercado, bar y lan house de la Praça) corrían su puesto de trabajo
# 2,8 m al MISMO lado (el +1 primero): los dos carteles quedaban a pocos metros y en el mismo cuadro se leían como un
# cartel duplicado. Ahora, entre los lados transitables, se queda el preferido si ya está a SEPARACION_MINIMA de los
# carteles puestos; si no, el que más lejos queda de ellos (hacia fuera del grupo).
# Bandera: TRABAJO_SEPARADO = False o ALCALDE_TRABAJO_SEPARADO=0 vuelve a «el primer lado transitable».

import math
import os

TRABAJO_SEPARADO = True
SEPARACION_MINIMA = 10.0       # m entre carteles: a menos, los dos tableros (2,5 m) entran juntos en el encuadre


def separado_activo(entorno=None):
    entorno = os.environ if entorno is None else entorno
    bruto = str(entorno.get("ALCALDE_TRABAJO_SEPARADO", "")).strip().lower()
    if bruto in ("0", "false", "no", "off"):
        return False
    if bruto in ("1", "true", "si", "sí", "on"):
        return True
    return TRABAJO_SEPARADO


# Distancia del punto `c` al cartel más cercano de `ocupados` (infinito si no hay ninguno).
def holgura(c, ocupados):
    return min((math.hypot(c[0] - o[0], c[1] - o[1]) for o in ocupados), default=math.inf)


# candidatos: [(x, z)] en orden de preferencia; ocupados: carteles ya colocados; transitable(x, z) -> bool o None.
# Devuelve el (x, z) elegido, o None si ningún candidato es transitable.
def elegir_sitio(candidatos, ocupados=(), transitable=None, separacion=SEPARACION_MINIMA):
    libres = [c for c in candidatos if transitable is None or transitable(c[0], c[1])]
    if not libres:
        return None
    if holgura(libres[0], ocupados) >= separacion:
        return libres[0]
    return max(libres, key=lambda c: holgura(c, ocupados))      # en empate, el primero (max es estable)


# Menor distancia entre dos carteles de la lista (infinito con menos de dos).
def separacion_minima_entre(puntos):
    puntos = list(puntos)
    return min((holgura(p, puntos[:i]) for i, p in enumerate(puntos) if i), default=math.inf)
