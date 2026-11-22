# Guion de las cinemáticas de entrar a un edificio y salir (Python puro: NO importa ursina).
# Reúne en UN solo lugar todas las duraciones, las tomas de cámara y las medidas del interior;
# el DirectorCinematica y las escenas solo las leen. Los scripts de prueba usan `escalar(plan, 0)`
# (duración 0 = todo instantáneo).
#
# Entrada (exterior):  encuadre -> acercarse -> abrir_puerta -> entrar          ~2.4 s
#   fundido: salida 0.4 + NEGRO 0.6 (con el nombre del lugar) + entrada 0.4     1.4 s
# Entrada (interior):  caminar -> sentarse -> teclear -> acercar -> destello    ~3.65 s
# Salida:              interior levantarse (1.0) | fundido | exterior aparecer ->
#                      salir -> cerrar_puerta -> camara
#
# Acercamiento al monitor: para que un monitor de alto h llene la vista con fov vertical f,
# la cámara va a  distancia = (h/2) / tan(f/2)   (0.40 m con fov 40°  ->  ~0.55 m).

import math

from frontend.camara_calculos import rotacion_mirando

# -- Duraciones (segundos) ------------------------------------------------------------------
ENTRADA_ENCUADRE = 0.5
ENTRADA_ACERCARSE_MIN = 0.3
ENTRADA_ACERCARSE_MAX = 0.8
VELOCIDAD_ACERCARSE = 4.0          # m/s con los que se calcula cuánto dura acercarse
ENTRADA_ABRIR = 0.4
ENTRADA_ENTRAR = 0.7

NEGRO_SALIDA = 0.4
NEGRO_SOSTENER = 0.6
NEGRO_ENTRADA = 0.4

INT_CAMINAR = 1.0
INT_SENTARSE = 0.8
INT_TECLEAR = 0.5
INT_ACERCAR = 1.2
INT_DESTELLO = 0.15
INT_LEVANTARSE = 1.0

SAL_APARECER = 0.2
SAL_SALIR = 0.6
SAL_CERRAR = 0.4
SAL_CAMARA = 0.6


# Cuánto dura "acercarse": lo que tarda en caminar `distancia` m, entre un mínimo (si ya está
# en el punto solo gira) y un máximo.
def duracion_acercarse(distancia):
    return min(ENTRADA_ACERCARSE_MAX, max(ENTRADA_ACERCARSE_MIN, distancia / VELOCIDAD_ACERCARSE))


# Cada plan es [(nombre_del_tramo, duracion)].
def plan_entrada(distancia):
    return [("encuadre", ENTRADA_ENCUADRE), ("acercarse", duracion_acercarse(distancia)),
            ("abrir_puerta", ENTRADA_ABRIR), ("entrar", ENTRADA_ENTRAR)]


def plan_interior_sentarse():
    return [("caminar", INT_CAMINAR), ("sentarse", INT_SENTARSE), ("teclear", INT_TECLEAR),
            ("acercar", INT_ACERCAR), ("destello", INT_DESTELLO)]


def plan_interior_levantarse():
    return [("levantarse", INT_LEVANTARSE)]


def plan_salida():
    return [("aparecer", SAL_APARECER), ("salir", SAL_SALIR), ("cerrar_puerta", SAL_CERRAR),
            ("camara", SAL_CAMARA)]


# Multiplica todas las duraciones por `factor` (0 = instantáneo; los scripts de prueba).
def escalar(plan, factor):
    return [(nombre, duracion * factor) for nombre, duracion in plan]


def distancia_a_monitor(alto, fov_grados):
    return (alto / 2) / math.tan(math.radians(fov_grados) / 2)


# -- Exterior: toma 3/4 de la fachada --------------------------------------------------------

_NORMAL_FUERA = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "o": (-1, 0)}
ALTURA_OBJETIVO_PUERTA = 1.3


# Cámara a 7 m de la puerta hacia afuera, 4 m de lado y 2.4 m sobre el umbral (edificio.y),
# mirando a la puerta. Devuelve {"position", "pitch", "yaw", "target"}.
def toma_fachada(edificio):
    nx, nz = _NORMAL_FUERA[edificio.lado_puerta]
    lx, lz = -nz, nx
    px, pz = edificio.puerta()
    y = getattr(edificio, "y", 0.0)
    posicion = (px + nx * 7 + lx * 4, y + 2.4, pz + nz * 7 + lz * 4)
    objetivo = (px, y + ALTURA_OBJETIVO_PUERTA, pz)
    pitch, yaw = rotacion_mirando(posicion, objetivo)
    return {"position": posicion, "pitch": pitch, "yaw": yaw, "target": objetivo}


# -- Interior (oficina única; ver EscenaInterior) -----------------------------------------------
# Habitación centrada en el origen: x en [-3, 3], z en [-2.5, 2.5]. La puerta está en la pared
# sur (z = -2.5); el escritorio y el monitor contra la pared norte, con la pantalla mirando a -z.

SALA_ANCHO, SALA_FONDO, SALA_ALTO = 6.0, 5.0, 3.0
PUERTA_SALA = (-1.8, -2.3)                 # donde el personaje aparece al entrar
LADO_SILLA = (-0.4, 1.1)                   # punto desde el que se sienta (a un lado de la silla)
ASIENTO = (1.2, 1.1)                       # (x, z) de la pelvis sentado
POSICION_PANTALLA = (1.2, 1.15, 2.15)      # centro de la pantalla del monitor
ALTO_PANTALLA = 0.40
ANCHO_PANTALLA = ALTO_PANTALLA * 16 / 9
FOV_INTERIOR = 65
FOV_PANTALLA = 40

# Punto por el que pasa la cámara al acercarse al monitor (curva sobre el hombro izquierdo, para
# no atravesar la cabeza del personaje sentado en ASIENTO).
VIA_ACERCAR = (0.5, 1.5, 1.2)

TOMAS_INTERIOR = {
    "caminar": {"position": (2.8, 1.7, -1.9), "target": (0.2, 1.0, 0.8), "fov": FOV_INTERIOR},
    "sentarse": {"position": (2.5, 1.6, -0.3), "target": (1.2, 0.9, 1.4), "fov": FOV_INTERIOR},
    "teclear": {"position": (0.5, 1.4, 0.3), "target": POSICION_PANTALLA, "fov": FOV_INTERIOR},
    "acercar_fin": {
        "position": (POSICION_PANTALLA[0], POSICION_PANTALLA[1],
                     POSICION_PANTALLA[2] - distancia_a_monitor(ALTO_PANTALLA, FOV_PANTALLA)),
        "target": POSICION_PANTALLA, "fov": FOV_PANTALLA},
    # MIN-015: antes (2.0, 1.6, 0.2), a 0,9 m de la nuca del personaje sentado (tapaba un tercio del encuadre); ahora
    # desde atrás y a un lado, como la toma «sentarse»: se le ve entero levantarse frente al escritorio.
    "levantarse": {"position": (2.7, 1.8, -0.6), "target": (1.1, 1.15, 1.3), "fov": FOV_INTERIOR},
}

# -- Intro: plaza de la fuente (frontend/intro_cinematica.py) ------------------------------------------------------------
# Todo relativo al CENTRO de la fuente de la Praça da Sé, leído del mundo (centro_fuente), nunca escrito a mano. Los dos
# actores quedan al sur de la fuente (-z), frente a frente y un poco girados hacia la cámara, que baja desde lo alto
# mirando a la fuente y termina en un plano medio de los dos con la fuente detrás.

INTRO_LUGAR_FUENTE = "Praça da Sé"
INTRO_DISTANCIA_ACTORES = 3.7      # m del centro de la fuente al punto medio de los actores (el borde de piedra: 2,05)
INTRO_SEPARACION = 1.6             # m entre los dos actores
INTRO_GIRO_A_CAMARA = 25.0         # grados que se abren hacia la cámara (0 = de perfil)
INTRO_FOV = 50
INTRO_ALTA = (0.0, 24.0, -16.0)    # cámara alta, relativa al punto medio de los actores (y: sobre su suelo)
INTRO_CERCA = (0.4, 1.7, -4.3)     # plano medio final
INTRO_EMPUJE = (0.0, -0.05, 0.5)   # acercamiento lento después de llegar
INTRO_ALTURA_OBJETIVO = 1.45       # m: a qué altura de los actores mira el plano medio
INTRO_LLEGADA = 0.45               # fracción de la escena en la que la cámara llega al plano medio
INTRO_ALTURA_MINIMA_CAMARA = 1.2   # m sobre el suelo que pisa la cámara (la ladera puede subir hacia ella)


def centro_fuente(mundo, lugar=INTRO_LUGAR_FUENTE):
    """(x, z) del centro de la fuente: el círculo «fuente» que la ciudad entregó al mundo o, sin él, el centro de la
    plaza. None si el mundo no tiene esa plaza."""
    extra = getattr(mundo, "obstaculos_extra", None)
    if callable(extra):
        try:
            for obstaculo in extra("fuente"):
                if getattr(obstaculo, "es_circulo", False):
                    return (float(obstaculo.cx), float(obstaculo.cz))
        except Exception:
            pass
    try:
        if lugar in mundo.lugares():
            x, z = mundo.coordenada(lugar)
            return (float(x), float(z))
    except Exception:
        pass
    return None


def tomas_plaza(centro, altura):
    """Actores y tomas de cámara de la escena 1. `centro`: (x, z) de la fuente; `altura(x, z)`: el suelo.
    Devuelve {"actores": {hablante: (x, z, rumbo)}, "alta", "cerca", "final": (posicion, objetivo), "fov"}."""
    cx, cz = centro
    mx, mz = cx, cz - INTRO_DISTANCIA_ACTORES
    suelo_m = altura(mx, mz)
    medio = INTRO_SEPARACION / 2
    actores = {"Ciudadano": (mx - medio, mz, 90.0 + INTRO_GIRO_A_CAMARA),
               "Influencer": (mx + medio, mz, -90.0 - INTRO_GIRO_A_CAMARA)}

    def punto(rel):
        x, z = mx + rel[0], mz + rel[2]
        y = max(suelo_m + rel[1], altura(x, z) + INTRO_ALTURA_MINIMA_CAMARA)
        return (x, y, z)

    objetivo_cerca = (mx, suelo_m + INTRO_ALTURA_OBJETIVO, mz)
    objetivo_alto = (cx, altura(cx, cz) + 1.0, cz)
    cerca = punto(INTRO_CERCA)
    final = (tuple(c + e for c, e in zip(cerca, INTRO_EMPUJE)), objetivo_cerca)
    return {"actores": actores, "alta": (punto(INTRO_ALTA), objetivo_alto), "cerca": (cerca, objetivo_cerca),
            "final": final, "fov": INTRO_FOV}


def camara_plaza(tomas, progreso):
    """(posicion, pitch, yaw) de la cámara cuando la escena 1 va por `progreso` (0..1): baja de la toma alta al plano
    medio hasta INTRO_LLEGADA y luego se acerca despacio."""
    from frontend.cinematica import ease_in_out, lerp_vec3
    p = max(0.0, min(1.0, progreso))
    if p <= INTRO_LLEGADA:
        k = ease_in_out(p / INTRO_LLEGADA)
        posicion = lerp_vec3(tomas["alta"][0], tomas["cerca"][0], k)
        objetivo = lerp_vec3(tomas["alta"][1], tomas["cerca"][1], k)
    else:
        k = (p - INTRO_LLEGADA) / (1.0 - INTRO_LLEGADA)
        posicion = lerp_vec3(tomas["cerca"][0], tomas["final"][0], k)
        objetivo = lerp_vec3(tomas["cerca"][1], tomas["final"][1], k)
    pitch, yaw = rotacion_mirando(posicion, objetivo)
    return tuple(posicion), pitch, yaw
