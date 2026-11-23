# Matemática de las poses procedurales de los minijuegos 3D (Python puro: NO importa ursina). La usa poses_3d.py.
# Vectores = tuplas (x, y, z) en el espacio que diga el llamador (en poses_3d: MUNDO).

import math

DOS_HUESOS_ESTIRADO = 0.995       # fracción del largo total al que se acerca el brazo (nunca 100 %: evita el chasquido)


def resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def suma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def escala(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def largo(a):
    return math.sqrt(punto(a, a))


def unitario(a, defecto=(0.0, 1.0, 0.0)):
    n = largo(a)
    return escala(a, 1.0 / n) if n > 1e-9 else defecto


def lerp(a, b, k):
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def ik_dos_huesos(hombro, objetivo, l1, l2, polo):
    """IK analítica de dos huesos (hombro-codo-mano). Devuelve (codo, mano). La mano llega a `objetivo` si está al alcance
    (si no, se estira hacia él); el codo se dobla hacia el punto `polo`."""
    eje = resta(objetivo, hombro)
    d = largo(eje)
    alcance = (l1 + l2) * DOS_HUESOS_ESTIRADO
    minimo = abs(l1 - l2) + 1e-4
    d_ok = min(max(d, minimo), alcance)
    u = unitario(eje, (0.0, -1.0, 0.0))
    mano = suma(hombro, escala(u, d_ok))
    # ley de cosenos: distancia a lo largo del eje hasta el pie de la altura del codo
    a = (l1 * l1 - l2 * l2 + d_ok * d_ok) / (2 * d_ok)
    h = math.sqrt(max(0.0, l1 * l1 - a * a))
    hacia_polo = resta(polo, hombro)
    perp = resta(hacia_polo, escala(u, punto(hacia_polo, u)))
    perp = unitario(perp, unitario(cruz(u, (1.0, 0.0, 0.0)), (0.0, 0.0, 1.0)))
    codo = suma(suma(hombro, escala(u, a)), escala(perp, h))
    return codo, mano


def no_atravesar(p, punto_plano, normal, margen=0.02):
    """Si `p` queda a menos de `margen` m DEL LADO VISIBLE de un plano (o detrás), lo empuja hasta `margen` delante.
    `normal` apunta hacia el lado permitido (arriba de la mesa, hacia la habitación desde el corcho)."""
    n = unitario(normal)
    d = punto(resta(p, punto_plano), n)
    if d >= margen:
        return p
    return suma(p, escala(n, margen - d))


def suave(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3 - 2 * k)


def arco(a, b, k, altura):
    """Punto de un arco de `a` a `b` (k en [0, 1]) que sube `altura` m en el medio (llevar un papel, colgar una viñeta)."""
    p = lerp(a, b, k)
    return (p[0], p[1] + altura * 4 * k * (1 - k), p[2])


def curva_golpe(t, duracion):
    """0 -> 1 -> 0 en `duracion` s (gesto corto: clic, chincheta). t fuera de [0, duracion] da 0."""
    if t <= 0 or t >= duracion:
        return 0.0
    return math.sin(math.pi * t / duracion)


def tecleo(t, frecuencia=7.0):
    """Desplazamiento vertical (m) de la mano tecleando: golpes cortos y desfasados."""
    return 0.012 * max(0.0, math.sin(2 * math.pi * frecuencia * t))


def seguir(actual, objetivo, dt, rapidez):
    """Paso exponencial hacia `objetivo` (rapidez en 1/s; independiente de los fps)."""
    if actual is None:
        return objetivo
    k = 1.0 - math.exp(-rapidez * max(0.0, dt))
    return lerp(actual, objetivo, k)


def finito(v):
    """¿Todos los componentes de `v` (vector o lista de números) son finitos? Nada no finito llega a Panda."""
    try:
        return all(math.isfinite(float(c)) for c in v)
    except (TypeError, ValueError):
        return False


def angulo_entre(a, b):
    """Ángulo (grados, 0..180) entre dos vectores de CUALQUIER largo, robusto (atan2 de |a x b| y a·b). None si alguno es
    nulo o no finito. (Panda LVector3.angleDeg exige vectores normalizados: con vectores sin normalizar da otro ángulo.)"""
    if not (finito(a) and finito(b)) or largo(a) < 1e-9 or largo(b) < 1e-9:
        return None
    return math.degrees(math.atan2(largo(cruz(a, b)), punto(a, b)))


CAIDA_REPOSO = 0.80               # fracción del alcance que baja la muñeca bajo el hombro con el brazo en reposo
AFUERA_REPOSO = 0.05              # m hacia fuera del cuerpo (la mano no se mete delante del muslo)
ATRAS_REPOSO = 0.03               # m hacia atrás del plano de los hombros (los dedos no asoman por delante)


def mano_colgando(hombro, adelante, derecha, signo, alcance, caida=CAIDA_REPOSO, afuera=AFUERA_REPOSO,
                  atras=ATRAS_REPOSO):
    """Muñeca (mundo) de un brazo en reposo, colgando junto al costado: `caida` x `alcance` m bajo el hombro, `afuera` m
    hacia su lado (`signo` +1 = derecha, -1 = izquierda) y `atras` m detrás del plano de los hombros. Es la pose de «mano
    quieta, fuera de la mesa»: con el personaje pegado al borde de la mesa, la mano que cuelga de la animación (Idle)
    adelanta los dedos ~17 cm y cae sobre lo que hay en el borde. None si algo no es finito."""
    if not (finito(hombro) and finito(adelante) and finito(derecha) and finito((signo, alcance, caida, afuera, atras))):
        return None
    p = suma(hombro, (0.0, -abs(alcance) * caida, 0.0))
    p = suma(p, escala(unitario((derecha[0], 0.0, derecha[2])), afuera * (1.0 if signo >= 0 else -1.0)))
    return suma(p, escala(unitario((adelante[0], 0.0, adelante[2])), -atras))


INCLINACION_MAXIMA = 40.0         # grados que se inclina el torso como mucho para llegar a algo
VELOCIDAD_INCLINAR = 70.0          # grados/s al inclinarse
VELOCIDAD_ENDEREZAR = 45.0         # grados/s al enderezarse


def paso_inclinacion(actual, falta, dt, maximo=INCLINACION_MAXIMA):
    """Siguiente inclinación del torso (grados) según lo que le `falta` (m, >0 = no llega) a la mano más exigida. Banda
    muerta entre -6 cm y +1 cm (no oscila). Nunca devuelve algo no finito."""
    if not (math.isfinite(actual) and math.isfinite(falta) and math.isfinite(dt)) or dt <= 0:
        return actual if math.isfinite(actual) else 0.0
    maximo = max(0.0, maximo) if math.isfinite(maximo) else INCLINACION_MAXIMA
    if actual > maximo:                  # bajaron el tope: vuelve suave hasta él, sin salto
        return max(maximo, actual - VELOCIDAD_ENDEREZAR * dt)
    if falta > 0.01:
        actual += VELOCIDAD_INCLINAR * dt
    elif falta < -0.06:
        actual -= VELOCIDAD_ENDEREZAR * dt
    return min(max(actual, 0.0), maximo)


def rotacion_entre(a, b):
    """Cuaternión (w, x, y, z) que lleva la dirección `a` a la dirección `b` (el arco más corto)."""
    a, b = unitario(a), unitario(b)
    c = punto(a, b)
    if c < -0.999999:
        eje = cruz((1.0, 0.0, 0.0), a)
        if largo(eje) < 1e-6:
            eje = cruz((0.0, 1.0, 0.0), a)
        eje = unitario(eje)
        return (0.0, eje[0], eje[1], eje[2])
    eje = cruz(a, b)
    w = 1.0 + c
    q = (w, eje[0], eje[1], eje[2])
    n = math.sqrt(sum(v * v for v in q))
    return tuple(v / n for v in q)


def escalar_rotacion(q, peso):
    """La rotación `q` aplicada solo en fracción `peso` (slerp desde la identidad)."""
    w, x, y, z = q
    w = min(1.0, max(-1.0, w))
    angulo = 2 * math.acos(w)
    s = math.sqrt(max(0.0, 1 - w * w))
    if s < 1e-8 or peso >= 1.0:
        return q if peso >= 1.0 else (1.0, 0.0, 0.0, 0.0)
    eje = (x / s, y / s, z / s)
    medio = angulo * max(0.0, peso) / 2
    return (math.cos(medio), eje[0] * math.sin(medio), eje[1] * math.sin(medio), eje[2] * math.sin(medio))


def rotar(q, v):
    """Aplica el cuaternión (w, x, y, z) al vector v."""
    w, x, y, z = q
    u = (x, y, z)
    t = escala(cruz(u, v), 2.0)
    return suma(suma(v, escala(t, w)), cruz(u, t))
