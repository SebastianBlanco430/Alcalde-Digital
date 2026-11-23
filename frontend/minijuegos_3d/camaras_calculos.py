# Tomas de cámara de los minijuegos 3D (Python puro: NO importa ursina). Las usa frontend/minijuegos_3d/camaras.py.
#
# Una TOMA es un dict {"position": (x, y, z), "target": (x, y, z), "fov": grados HORIZONTALES (Panda: Lens.set_fov)} en
# coordenadas de MUNDO (las del set; el set está en el origen sin rotar, así que mundo = set).
# Un OBJETIVO a encuadrar se describe con: centro (x, y, z), normal (hacia donde mira su cara visible, unitaria), arriba
# (unitario, en el plano de la cara), alto y ancho (m).
#
# Las tres cámaras del rework (fracción = alto del objetivo / alto de la ventana; legibilidad manda: si el texto no llega
# al mínimo, se sube la fracción, nunca se achica el texto):
#   sobre_hombro   monitor ~79 % del alto; cámara junto a la cabeza, por encima del hombro DERECHO (0,35 m a la derecha,
#                  15 cm por encima del centro del monitor, 1,15 m delante de él), FOV 44, mirando el monitor con ~18° de
#                  sesgo. Sale de una búsqueda geométrica (rework-3d/infra-3d/busqueda_sobre_hombro.py) con la cabeza, el
#                  torso y el brazo como oclusores: ninguno tapa la zona de contenido de la vista 2D (y > -0,28 de la UI).
#                  Desde detrás de la espalda (lo primero que se probó) el torso tapaba medio monitor.
#   frente_corcho  corcho ~FRACCION_CORCHO; detrás y un poco al costado del personaje.
#   sobre_mesa     papeles ~FRACCION_MESA; alta, tres cuartos, mirando la mesa desde atrás del personaje.

import math

FOV_JUEGO = 38.0                 # FOV horizontal de las tomas (estrecho: menos deformación de los papeles y del monitor)
FOV_MESA = 55.0                  # la mesa se mira desde arriba: con 38° la cámara tendría que salir por el techo
FRACCION_MONITOR = 0.79          # 60 % pedido; ~79 % con la toma de abajo (legibilidad: texto >= 14 px a 720p)
HOMBRO = {"fondo": 1.15, "lateral": 0.35, "elevacion": 0.15, "mirar_y": 0.04, "fov": 44.0}   # para un monitor de 0,40 m
# Roles con mucho volumen de pelo (brasilena.glb: afro de ~0,28 m de radio): misma búsqueda con esa cabeza -> más de lado.
HOMBRO_POR_ROL = {"influencer": {"fondo": 1.0, "lateral": 0.45, "elevacion": -0.05, "mirar_y": -0.04, "fov": 50.0}}
FRACCION_CORCHO = 0.72
FRACCION_MESA = 0.66
DURACION_TRANSICION = 0.8        # s (pedido: 0,6 a 1)


def _sum(a, b):
    return tuple(a[i] + b[i] for i in range(3))


def _esc(a, k):
    return tuple(a[i] * k for i in range(3))


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(sum(c * c for c in a)) or 1.0
    return _esc(a, 1.0 / n)


def fov_vertical(fov_h, aspecto):
    return math.degrees(2 * math.atan(math.tan(math.radians(fov_h) / 2) / aspecto))


def distancia_para(alto, ancho, fraccion, fov_h, aspecto):
    """Distancia (m) a la que un objetivo de `alto` x `ancho` ocupa `fraccion` del alto de la ventana (o del ancho, si por
    ancho no cabe: nunca se sale de la pantalla)."""
    fov_v = fov_vertical(fov_h, aspecto)
    d_alto = (alto / 2) / (fraccion * math.tan(math.radians(fov_v) / 2))
    d_ancho = (ancho / 2) / (0.96 * math.tan(math.radians(fov_h) / 2))      # margen lateral mínimo del 2 % por lado
    return max(d_alto, d_ancho)


def toma_frente(centro, normal, arriba, alto, ancho, fraccion, aspecto, fov_h=FOV_JUEGO, lateral=0.0, elevacion=0.0,
                mirar_desplazado=(0.0, 0.0)):
    """Toma que encuadra el objetivo de frente con `fraccion` del alto de la ventana. `lateral`/`elevacion` mueven la
    cámara (m) a la derecha/arriba del eje de la cara (en el plano de la cara) manteniendo la distancia; `mirar_desplazado`
    (dx, dy) mueve el punto mirado sobre la cara (m)."""
    normal, arriba = _norm(normal), _norm(arriba)
    derecha = _norm(_cruz(arriba, normal))          # mirando la cara de frente, a la derecha de quien mira
    derecha = _esc(derecha, -1.0)
    d = distancia_para(alto, ancho, fraccion, fov_h, aspecto)
    posicion = _sum(_sum(_sum(centro, _esc(normal, d)), _esc(derecha, lateral)), _esc(arriba, elevacion))
    objetivo = _sum(_sum(centro, _esc(derecha, mirar_desplazado[0])), _esc(arriba, mirar_desplazado[1]))
    return {"position": posicion, "target": objetivo, "fov": fov_h}


def toma_sobre_hombro(monitor, aspecto, fraccion=FRACCION_MONITOR, rol=None):
    """`monitor`: {"centro", "normal", "arriba", "alto", "ancho"}. Cámara junto a la cabeza, sobre el hombro derecho (ver
    arriba). Las distancias de HOMBRO escalan con el alto del monitor; `fraccion` distinta de FRACCION_MONITOR acerca o
    aleja la cámara en proporción (más fracción = más cerca). `rol` elige la variante de HOMBRO_POR_ROL si la hay."""
    h = HOMBRO_POR_ROL.get(rol, HOMBRO)
    normal, arriba = _norm(monitor["normal"]), _norm(monitor["arriba"])
    derecha = _esc(_norm(_cruz(arriba, normal)), -1.0)
    k = monitor["alto"] / 0.40
    fondo = h["fondo"] * k * FRACCION_MONITOR / max(0.2, fraccion)
    centro = monitor["centro"]
    posicion = _sum(_sum(_sum(centro, _esc(normal, fondo)), _esc(derecha, h["lateral"] * k)), _esc(arriba, h["elevacion"] * k))
    return {"position": posicion, "target": _sum(centro, _esc(arriba, h["mirar_y"] * k)), "fov": h["fov"]}


def toma_frente_corcho(corcho, aspecto, fraccion=FRACCION_CORCHO):
    return toma_frente(corcho["centro"], corcho["normal"], corcho["arriba"], corcho["alto"], corcho["ancho"],
                       fraccion, aspecto, lateral=0.38, elevacion=0.08, mirar_desplazado=(0.03, -0.02))


def toma_sobre_mesa(mesa, aspecto, fraccion=FRACCION_MESA, inclinacion=62.0, techo=None):
    """Como _toma_sobre_mesa, bajando la inclinación de 2 en 2 grados (hasta 40) si la cámara quedaría a menos de 15 cm del
    `techo` (y del techo del set; None = sin techo)."""
    toma = _toma_sobre_mesa(mesa, aspecto, fraccion, inclinacion)
    while techo is not None and toma["position"][1] > techo - 0.15 and inclinacion > 40:
        inclinacion -= 2
        toma = _toma_sobre_mesa(mesa, aspecto, fraccion, inclinacion)
    return toma


def _toma_sobre_mesa(mesa, aspecto, fraccion, inclinacion):
    """`mesa`: {"centro", "normal" (arriba de la mesa), "frente" (de la mesa hacia el personaje), "alto" (fondo de la zona
    de papeles, m), "ancho"}. Cámara alta, a `inclinacion` grados sobre la horizontal, desde atrás del personaje y un poco
    al costado (tres cuartos)."""
    centro = mesa["centro"]
    arriba_mesa, frente = _norm(mesa["normal"]), _norm(mesa["frente"])
    a = math.radians(inclinacion)
    eje = _norm(_sum(_esc(frente, math.cos(a)), _esc(arriba_mesa, math.sin(a))))      # de la mesa hacia la cámara
    # el «alto» aparente de la zona de papeles se acorta con la inclinación: se encuadra el alto proyectado
    alto_visto = mesa["alto"] * math.sin(a) + 0.05
    lateral = _norm(_cruz(arriba_mesa, frente))
    d = distancia_para(alto_visto, mesa["ancho"], fraccion, FOV_MESA, aspecto)
    posicion = _sum(_sum(centro, _esc(eje, d)), _esc(lateral, -0.30))      # a la derecha (el personaje está a la izquierda)
    return {"position": posicion, "target": _sum(centro, _esc(frente, 0.04)), "fov": FOV_MESA}


def suave(k):
    """Ease in-out cúbico en [0, 1]."""
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def interpolar(a, b, k):
    """Toma intermedia (posición, objetivo y fov lineales con k ya suavizado)."""
    return {"position": tuple(a["position"][i] + (b["position"][i] - a["position"][i]) * k for i in range(3)),
            "target": tuple(a["target"][i] + (b["target"][i] - a["target"][i]) * k for i in range(3)),
            "fov": a["fov"] + (b["fov"] - a["fov"]) * k}


def rotacion_mirando(posicion, objetivo):
    """(pitch, yaw) en grados de Ursina para mirar de `posicion` a `objetivo` (igual que frontend/camara_calculos)."""
    dx, dy, dz = (objetivo[i] - posicion[i] for i in range(3))
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    return pitch, yaw


def altura_px(altura_mundo, distancia, fov_h, aspecto, alto_ventana_px):
    """Píxeles que mide algo de `altura_mundo` m visto de frente a `distancia` m (para medir legibilidad)."""
    fov_v = fov_vertical(fov_h, aspecto)
    return altura_mundo / (2 * distancia * math.tan(math.radians(fov_v) / 2)) * alto_ventana_px
