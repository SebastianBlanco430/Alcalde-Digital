# Planificación pura (sin ursina ni panda3d) del streaming por chunks del mapa grande: qué chunks hay que construir, a qué
# nivel de detalle, en qué orden, y cuáles soltar. La usa frontend/ciudad_chunks.py cada pocos frames; se prueba sin ventana.
#
# Niveles: 0 = LOD0 (casas completas, calles, escaleras, props), 1 = LOD1 (cajas y terreno a 4 m), None = nada (solo el fondo).
# Histéresis: un chunk que ya tiene un nivel lo conserva hasta pasar `histeresis` m del radio con que se construyó; así un jugador
# que camina por el borde de un radio no construye y descarta el mismo chunk en bucle.

import math

PRIORIDAD_LOD1_EXTRA = 80.0        # m que se suman a la distancia de un LOD1 al ordenar la cola (el LOD0 cercano va antes)


def distancia_a_caja(x, z, caja):
    """Distancia (m) de un punto a un rectángulo (xmin, xmax, zmin, zmax); 0 si está dentro."""
    xmin, xmax, zmin, zmax = caja
    return math.hypot(x - min(max(x, xmin), xmax), z - min(max(z, zmin), zmax))


def distancia_minima(focos, caja):
    return min(distancia_a_caja(x, z, caja) for x, z in focos)


def nivel_deseado(d, actual, radio0, radio1, histeresis, adelanto):
    """Nivel (0, 1 o None) que le toca a un chunk a distancia `d` del foco, sabiendo el nivel `actual` que ya tiene."""
    carga0 = radio0 + adelanto                    # a esta distancia se EMPIEZA a construir el LOD0
    if d <= carga0 or (actual == 0 and d <= carga0 + histeresis):
        return 0
    if d <= radio1 or (actual in (0, 1) and d <= radio1 + histeresis):
        return 1
    return None


def planificar(limites, focos, actual, radio0, radio1, histeresis=25.0, adelanto=30.0):
    """limites: {clave: caja}; focos: [(x, z)] (el jugador y, si se mueve, el punto adelantado); actual: {clave: nivel}.
    Devuelve (construir, soltar, degradar):
      construir: [(prioridad, clave, nivel)] ordenada (menor primero), sin lo que ya está;
      soltar:    [clave] cuyo nivel actual ya no hace falta (se quita todo);
      degradar:  [clave] con LOD0 que ahora solo necesita LOD1 (se construye el LOD1 y luego se suelta el LOD0)."""
    construir, soltar, degradar = [], [], []
    for clave, caja in limites.items():
        d = distancia_minima(focos, caja)
        a = actual.get(clave)
        if a is None and d > radio1 + histeresis:
            continue
        n = nivel_deseado(d, a, radio0, radio1, histeresis, adelanto)
        if n == a:
            continue
        if n is None:
            soltar.append(clave)
        elif n == 0:
            construir.append((d, clave, 0))
        elif a is None:
            construir.append((d + PRIORIDAD_LOD1_EXTRA, clave, 1))
        else:                                     # a == 0 y n == 1
            construir.append((d + PRIORIDAD_LOD1_EXTRA, clave, 1))
            degradar.append(clave)
    construir.sort()
    return construir, soltar, degradar


def foco_adelantado(x, z, vx, vz, segundos, tope=60.0):
    """Punto al que llegará el jugador en `segundos` si sigue a la velocidad (vx, vz), con un tope de `tope` m."""
    dx, dz = vx * segundos, vz * segundos
    largo = math.hypot(dx, dz)
    if largo > tope:
        dx, dz = dx * tope / largo, dz * tope / largo
    return (x + dx, z + dz)


def anillo_de_arranque(limites, foco, radio):
    """Claves de los chunks a menos de `radio` m del foco, de más cerca a más lejos."""
    cercanos = [(distancia_a_caja(foco[0], foco[1], caja), clave) for clave, caja in limites.items()]
    return [clave for d, clave in sorted(cercanos) if d <= radio]
