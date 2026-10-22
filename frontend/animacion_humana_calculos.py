# Matemática PURA (sin ursina ni panda3d) del caminar/correr humano de los personajes con modelo .glb.
# Genera poses de cuerpo completo para una fase del ciclo y una velocidad real:
#   - piernas por IK de dos huesos (muslo + pierna) con el pie PLANTADO en el suelo durante el apoyo
#     (balanceo de talón -> pie plano -> balanceo de antepié), así no patina; rodilla que se flexiona en el
#     balanceo; levante del pie según la velocidad; fase de vuelo al correr (apoyo < 50 % del ciclo);
#   - pelvis: bamboleo lateral hacia la pierna de apoyo, rebote vertical (péndulo invertido al caminar,
#     resorte al correr), giro y caída lateral; hombros que giran al revés que la cadera;
#   - brazos en contrafase con codo flexionado (más al correr); inclinación del torso según la velocidad;
#     cabeza estabilizada.
# También: ciclo de SUBIR ESCALÓN y poses clave de SALTO (impulso, ascenso, caída, aterrizaje).
#
# Marco del cuerpo (derecho): x adelante, y izquierda, z arriba; el origen está en el suelo, bajo el pivote de
# la pelvis. Ángulos en grados. Las poses devuelven vectores unitarios de los huesos en ese marco; el
# módulo Panda (frontend/animacion_humana.py) los traduce a rotaciones de cada esqueleto.
# Fase del ciclo: 0..1; en 0 el pie DERECHO toca el suelo con el talón.

import math

# -- Vectores y rotaciones (matrices 3x3 en convención de columnas: v' = R v) --


def suma(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def escala(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norma(a):
    return math.sqrt(punto(a, a))


def unitario(a):
    n = norma(a)
    return (0.0, 0.0, -1.0) if n < 1e-9 else (a[0] / n, a[1] / n, a[2] / n)


def mat_eje(eje, grados):
    # Rotación de `grados` alrededor de `eje` (regla de la mano derecha), fórmula de Rodrigues.
    x, y, z = unitario(eje)
    a = math.radians(grados)
    c, s = math.cos(a), math.sin(a)
    t = 1 - c
    return ((t * x * x + c, t * x * y - s * z, t * x * z + s * y),
            (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
            (t * x * z - s * y, t * y * z + s * x, t * z * z + c))


def mat_por_vec(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def mat_por_mat(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


IDENTIDAD = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


# Rotación de una zona del cuerpo: giro (z), inclinación adelante (y; positivo = la parte alta va hacia delante)
# y caída lateral (x; positivo = el lado izquierdo sube). Se aplica en ese orden: R = Rz · Ry · Rx.
def mat_euler(giro, inclina, caida):
    return mat_por_mat(mat_eje((0, 0, 1), giro), mat_por_mat(mat_eje((0, 1, 0), inclina), mat_eje((1, 0, 0), caida)))


# Rotación mínima que lleva la dirección `a` a la dirección `b`.
def arco(a, b):
    a, b = unitario(a), unitario(b)
    c = punto(a, b)
    if c > 1 - 1e-9:
        return IDENTIDAD
    if c < -1 + 1e-9:
        eje = cruz(a, (1, 0, 0))
        if norma(eje) < 1e-6:
            eje = cruz(a, (0, 1, 0))
        return mat_eje(eje, 180.0)
    return mat_eje(cruz(a, b), math.degrees(math.acos(c)))


def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _interp(tabla, v):
    # Interpolación lineal sobre VELS; fuera de rango se queda en los extremos.
    if v <= VELS[0]:
        return tabla[0]
    if v >= VELS[-1]:
        return tabla[-1]
    for i in range(len(VELS) - 1):
        if v <= VELS[i + 1]:
            k = (v - VELS[i]) / (VELS[i + 1] - VELS[i])
            return tabla[i] + (tabla[i + 1] - tabla[i]) * k
    return tabla[-1]


# -- Tablas por velocidad (m/s). Las velocidades de diseño son también las de los clips horneados --
VELS = (0.8, 1.5, 3.0, 4.8, 6.6, 8.5)
CADENCIA = (0.85, 1.05, 1.40, 1.70, 1.90, 2.10)      # ciclos (dos pasos) por segundo
APOYO = (0.65, 0.60, 0.46, 0.36, 0.30, 0.26)         # fracción del ciclo con el pie en el suelo
LEVANTE = (0.05, 0.08, 0.17, 0.24, 0.30, 0.34)       # m que sube el tobillo en el balanceo
INCLINACION = (1.5, 3.0, 8.0, 12.0, 15.0, 18.0)      # torso hacia delante (°)
BRAZO = (10.0, 18.0, 30.0, 36.0, 42.0, 46.0)         # amplitud del brazo (°)
CODO_BASE = (12.0, 15.0, 48.0, 62.0, 64.0, 64.0)     # flexión del codo (°)
CODO_EXTRA = (8.0, 12.0, 22.0, 28.0, 30.0, 30.0)     # flexión extra con el brazo adelante (el codo se abre al ir atrás)
GIRO_PELVIS = (3.0, 4.0, 5.0, 6.0, 6.0, 6.0)
GIRO_HOMBROS = (5.0, 7.0, 9.0, 11.0, 12.0, 12.0)
CAIDA_PELVIS = (2.5, 3.0, 3.0, 2.5, 2.0, 1.5)
BAMBOLEO = (0.025, 0.03, 0.025, 0.02, 0.015, 0.01)   # m de la pelvis hacia la pierna de apoyo
AGACHE = (0.02, 0.035, 0.075, 0.095, 0.105, 0.115)       # m que baja la pelvis (rodilla algo flexionada)
REBOTE = (0.012, 0.016, 0.0, -0.02, -0.04, -0.05)    # + = sube en mitad del apoyo; - = baja (correr)
TALON = (12.0, 15.0, 18.0, 20.0, 15.0, 10.0)         # punta arriba al tocar (°)
DESPEGUE = (20.0, 25.0, 30.0, 35.0, 40.0, 40.0)      # punta abajo al despegar (°)
SEPARACION = (0.05, 0.04, 0.025, 0.015, 0.0, 0.0)    # m extra entre tobillo y cadera (lateral)

FRAC_TALON = 0.10                # fracción del apoyo con el balanceo de talón
FRAC_ANTEPIE = 0.72              # a partir de aquí el balanceo de antepié


class Medidas:
    # Medidas de un esqueleto en el marco del cuerpo, de pie en reposo.
    def __init__(self, pivote_pelvis=(0.0, 0.0, 0.963), cadera_i=(-0.012, 0.086, 1.02), cadera_d=(-0.012, -0.086, 1.02),
                 largo_muslo=0.469, largo_pierna=0.474, altura_tobillo=0.085, pie_adelante=0.117, pie_atras=0.06):
        self.pivote_pelvis = pivote_pelvis
        self.cadera_i = cadera_i
        self.cadera_d = cadera_d
        self.largo_muslo = largo_muslo
        self.largo_pierna = largo_pierna
        self.altura_tobillo = altura_tobillo
        self.pie_adelante = pie_adelante
        self.pie_atras = pie_atras


# -- Mezcla de clips de marcha según la velocidad real --

def largo_ciclo(v):
    # Metros que avanza el cuerpo en un ciclo completo a la velocidad de diseño v.
    return v / _interp(CADENCIA, v)


# Dos clips vecinos de VELS y el peso del segundo, más la cadencia (ciclos/s) con la que hay que reproducirlos
# para que el avance por ciclo sea exacto (los pies no patinan): cadencia = v / largo de ciclo mezclado.
def mezcla_marcha(v):
    v = max(0.0, v)
    if v <= VELS[0]:
        i, w = 0, 0.0
    elif v >= VELS[-1]:
        i, w = len(VELS) - 2, 1.0
    else:
        i = 0
        while v > VELS[i + 1]:
            i += 1
        w = (v - VELS[i]) / (VELS[i + 1] - VELS[i])
    largo = (1 - w) * largo_ciclo(VELS[i]) + w * largo_ciclo(VELS[i + 1])
    cadencia = max(v, 0.05) / largo
    return i, w, cadencia


# Cuánto manda la marcha frente al reposo (0 = reposo, 1 = marcha completa).
def peso_marcha(v):
    return _suave((v - 0.1) / 0.5)


# -- Pie: trayectoria del tobillo en el marco del cuerpo --

def _apoyo_suelo(psi, d, largo, theta_t, theta_d, m):
    # Posición del tobillo (x respecto al origen del suelo en el marco del suelo, z) y pitch (punta arriba +)
    # durante el apoyo, psi en [0, d]. Tres balanceos sin deslizar: talón, pie plano, antepié.
    s = psi / d
    ph, pa = m.pie_atras, m.pie_adelante
    alt = m.altura_tobillo
    # r_talon y r_bola: tobillo -> punto de contacto, en el marco del pie
    if s < FRAC_TALON:
        k = s / FRAC_TALON
        th = theta_t * (1 - k) ** 2
        c, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
        rx, rz = -ph, -alt
        return (-(rx * c - rz * sn), -(rx * sn + rz * c), th)
    if s < FRAC_ANTEPIE:
        return (ph, alt, 0.0)
    k = (s - FRAC_ANTEPIE) / (1 - FRAC_ANTEPIE)
    th = -theta_d * k * k
    c, sn = math.cos(math.radians(th)), math.sin(math.radians(th))
    rx, rz = pa, -alt
    return (ph + pa - (rx * c - rz * sn), -(rx * sn + rz * c), th)


def _hermite(p0, p1, m0, m1, t):
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1)


def _estado_apoyo(psi, v, m):
    # (x_cuerpo, z, pitch) del tobillo en la fase psi de apoyo (en el marco del cuerpo, sin balanceo).
    d = _interp(APOYO, v)
    largo = largo_ciclo(v)
    th_t, th_d = _interp(TALON, v), _interp(DESPEGUE, v)
    gx, z, th = _apoyo_suelo(psi, d, largo, th_t, th_d, m)
    # el origen del marco del suelo se elige para que a mitad del pie plano el tobillo quede bajo la pelvis
    s_med = (FRAC_TALON + FRAC_ANTEPIE) / 2 * d
    gx_med = _apoyo_suelo(s_med, d, largo, th_t, th_d, m)[0]
    x = (gx - gx_med) - largo * (psi - s_med)
    return x, z, th


# Tobillo (x, z) y pitch del pie en la fase de pie psi en [0, 1): apoyo en [0, d), balanceo en [d, 1).
def trayectoria_pie(psi, v, m, ascenso=0.0):
    psi = psi % 1.0
    d = _interp(APOYO, v)
    largo = largo_ciclo(v)
    if psi < d:
        x, z, th = _estado_apoyo(psi, v, m)
        return x, z + ascenso * (d - 2 * psi), th
    tau = (psi - d) / (1 - d)
    eps = 1e-4

    def apoyo(p):
        x, z, th = _estado_apoyo(p, v, m)
        return x, z + ascenso * (d - 2 * p), th

    # extremos del balanceo = fin y comienzo del apoyo (el pie sube un ciclo de escalones al despegar)
    x0, z0, t0 = apoyo(d - 1e-6)
    x1, z1, t1 = apoyo(0.0)
    xa, za, _ = apoyo(d - eps)
    xb, zb, _ = apoyo(eps)
    dx0, dx1 = (x0 - xa) / eps, (xb - x1) / eps
    dz0, dz1 = (z0 - za) / eps, (zb - z1) / eps
    esc = 1 - d
    x = _hermite(x0, x1, dx0 * esc, dx1 * esc, tau)
    zl = _hermite(z0, z1, dz0 * esc, dz1 * esc, tau)
    z = zl + _interp(LEVANTE, v) * math.sin(math.pi * tau) ** 2
    th = t0 + (t1 - t0) * _suave(tau / 0.6) if tau < 0.6 else t1
    return x, z, th


# -- IK de dos huesos: devuelve (rodilla, dirección del muslo, dirección de la pierna, error de alcance) --

def ik_pierna(cadera, tobillo, largo_muslo, largo_pierna, polo=(1.0, 0.0, 0.0)):
    d = resta(tobillo, cadera)
    dist = norma(d)
    maximo = (largo_muslo + largo_pierna) * 0.9995
    minimo = abs(largo_muslo - largo_pierna) + 0.01
    error = max(0.0, dist - maximo)
    dist_c = min(maximo, max(minimo, dist))
    eje = unitario(d)
    cos_a = (largo_muslo ** 2 + dist_c ** 2 - largo_pierna ** 2) / (2 * largo_muslo * dist_c)
    cos_a = max(-1.0, min(1.0, cos_a))
    a = math.acos(cos_a)
    perp = resta(polo, escala(eje, punto(polo, eje)))
    if norma(perp) < 1e-6:
        perp = (0.0, 1.0, 0.0)
    perp = unitario(perp)
    rodilla = suma(cadera, suma(escala(eje, largo_muslo * math.cos(a)), escala(perp, largo_muslo * math.sin(a))))
    tobillo_real = suma(cadera, escala(eje, dist_c))
    return rodilla, unitario(resta(rodilla, cadera)), unitario(resta(tobillo_real, rodilla)), error


# Flexión de la rodilla en grados (0 = pierna recta).
def flexion_rodilla(dir_muslo, dir_pierna):
    return math.degrees(math.acos(max(-1.0, min(1.0, punto(dir_muslo, dir_pierna)))))


# -- Brazos --

def dir_brazo(lado, adelante, abduccion):
    # Dirección de un segmento que cuelga, inclinado `adelante` grados hacia delante y `abduccion` hacia fuera
    # (lado: +1 izquierdo, -1 derecho).
    v = mat_por_vec(mat_eje((1, 0, 0), lado * abduccion), (0.0, 0.0, -1.0))
    return mat_por_vec(mat_eje((0, 1, 0), -adelante), v)


# -- Pose completa --

ZONAS = ("pelvis", "lumbar", "pecho", "cuello", "cabeza")


def _pierna(cadera, tobillo, m, pie_pitch, dedos_pitch):
    rodilla, muslo, pierna, error = ik_pierna(cadera, tobillo, m.largo_muslo, m.largo_pierna)
    return {"muslo": muslo, "pierna": pierna, "rodilla": rodilla, "tobillo": tobillo, "pie_pitch": pie_pitch,
            "dedos_pitch": dedos_pitch, "error": error}


def _cadera_mundo(cadera_rep, m, rot_pelvis, desp):
    # Cadera de reposo movida con la pelvis (rígida alrededor del pivote).
    rel = resta(cadera_rep, m.pivote_pelvis)
    return suma(suma(m.pivote_pelvis, mat_por_vec(rot_pelvis, rel)), desp)


def _armar_pose(m, desp, rots, tobillo_i, tobillo_d, brazos, inclinacion_total=0.0):
    # rots: zona -> (giro, inclina, caída). tobillo_*: (x, y, z, pitch, dedos_pitch) en el marco del cuerpo.
    mat_pelvis = mat_euler(*rots["pelvis"])
    cad_i = _cadera_mundo(m.cadera_i, m, mat_pelvis, desp)
    cad_d = _cadera_mundo(m.cadera_d, m, mat_pelvis, desp)
    mat_pecho = mat_euler(*rots["pecho"])
    pose = {"desp_pelvis": desp, "rot": dict(rots),
            "pierna_i": _pierna(cad_i, tobillo_i[:3], m, tobillo_i[3], tobillo_i[4]),
            "pierna_d": _pierna(cad_d, tobillo_d[:3], m, tobillo_d[3], tobillo_d[4])}
    for lado, clave in ((1, "i"), (-1, "d")):
        sup, abd_s, inf, abd_i = brazos[clave]
        pose["brazo_" + clave] = {"sup": unitario(mat_por_vec(mat_pecho, dir_brazo(lado, sup, abd_s))),
                                  "inf": unitario(mat_por_vec(mat_pecho, dir_brazo(lado, inf, abd_i)))}
    return pose


def _pose_ciclo(fase, v, m, ascenso=0.0, paso_escalon=False):
    d = _interp(APOYO, v)
    fase = fase % 1.0
    psi_d = fase
    psi_i = (fase + 0.5) % 1.0
    giro_p, giro_h = _interp(GIRO_PELVIS, v), _interp(GIRO_HOMBROS, v)
    caida = _interp(CAIDA_PELVIS, v)
    inc = _interp(INCLINACION, v) + (10.0 if paso_escalon else 0.0)
    c2, s1 = math.cos(2 * math.pi * fase), math.sin(2 * math.pi * fase)
    sway = -_interp(BAMBOLEO, v) * s1
    dz = -_interp(AGACHE, v) + _interp(REBOTE, v) * math.cos(4 * math.pi * (fase - d / 2)) - ascenso * (d + 0.25)
    desp = (0.0, sway, dz)
    rots = {"pelvis": (giro_p * c2, 0.25 * inc, -caida * s1),
            "lumbar": (-0.3 * giro_h * c2, 0.55 * inc, 0.5 * caida * s1),
            "pecho": (-giro_h * c2, inc, 0.8 * caida * s1),
            "cuello": (-0.3 * giro_h * c2, 0.6 * inc, 0.0),
            "cabeza": (0.0, 0.3 * inc, 0.0)}
    sep = _interp(SEPARACION, v)
    tob = {}
    for clave, psi, lado in (("i", psi_i, 1), ("d", psi_d, -1)):
        x, z, th = trayectoria_pie(psi, v, m, ascenso)
        y = lado * (abs(m.cadera_i[1]) + sep) - sway
        dedos = 0.0 if (psi < d and psi > d * FRAC_ANTEPIE) else th * 0.6
        # pitch del pie: positivo = punta arriba (Ry(-p)); se guarda tal cual, el módulo Panda lo convierte
        tob[clave] = (m.cadera_i[0] + x, y, z, th, dedos)
    amp = _interp(BRAZO, v)
    base, extra = _interp(CODO_BASE, v), _interp(CODO_EXTRA, v)
    # el antebrazo va un poco retrasado respecto al brazo (látigo): el codo se cierra al ir adelante y se abre atrás
    c2_ret = math.cos(2 * math.pi * (fase - 0.06))
    # el brazo llega menos adelante de lo que se va atrás (como al correr de verdad)
    asim = lambda c: c * (0.8 if c > 0 else 1.15)
    adelante_i, adelante_d = amp * asim(c2), amp * asim(-c2)
    ret_i, ret_d = 0.2 * amp * c2_ret, -0.2 * amp * c2_ret
    abd = 6.0 if v < 3 else 10.0
    codo_i = base + extra * (0.5 + 0.5 * c2)
    codo_d = base + extra * (0.5 - 0.5 * c2)
    cruce = 0.0 if v < 3 else 5.0 * (1 if v < 6 else 1.4)       # al ir adelante la mano cruza algo hacia el centro
    brazos = {"i": (adelante_i, abd - cruce * c2, adelante_i + ret_i + codo_i, abd * 0.5 - 0.5 * cruce * c2),
              "d": (adelante_d, abd + cruce * c2, adelante_d + ret_d + codo_d, abd * 0.5 + 0.5 * cruce * c2)}
    return _armar_pose(m, desp, rots, tob["i"], tob["d"], brazos)


# Pose de caminar/correr para la fase del ciclo (0..1) y la velocidad de diseño v.
def pose_marcha(fase, v, m=None):
    return _pose_ciclo(fase, v, m or Medidas())


# Subir escalón: ciclo con rodilla alta en el balanceo, la pierna de apoyo se extiende y la pelvis sube; el
# torso se inclina. `alto` = altura de cada escalón (m).
VEL_ESCALON = 1.5
ALTO_ESCALON_DEFECTO = 0.2


def pose_escalon(fase, m=None, alto=ALTO_ESCALON_DEFECTO):
    m = m or Medidas()
    v = VEL_ESCALON
    pose = _pose_ciclo(fase, v, m, ascenso=alto, paso_escalon=True)
    return pose


# Cadencia de reproducción del ciclo de escalón (ciclos/s) para una velocidad horizontal dada (m/s).
def cadencia_escalon(velocidad):
    return max(0.3, min(1.4, 0.9 + 0.12 * velocidad))


# Poses clave del salto (no cíclicas). Devuelve una pose del mismo formato que pose_marcha.
ETAPAS_SALTO = ("impulso", "ascenso", "caida", "aterrizaje")


def pose_salto(etapa, m=None):
    m = m or Medidas()
    xc = m.cadera_i[0]
    alt = m.altura_tobillo
    yc = abs(m.cadera_i[1])
    z0 = (0.0, 0.0, 0.0)
    if etapa == "impulso":
        desp = (0.0, 0.0, 0.03)
        rots = {"pelvis": z0, "lumbar": (0, -2.0, 0), "pecho": (0, -4.0, 0), "cuello": z0, "cabeza": (0, -3.0, 0)}
        ti = (xc - 0.08, yc + 0.02, alt + 0.04, -40.0, -10.0)
        td = (xc - 0.10, -yc - 0.02, alt + 0.02, -40.0, -10.0)
        brazos = {"i": (150.0, 12.0, 160.0, 8.0), "d": (150.0, 12.0, 160.0, 8.0)}
    elif etapa == "ascenso":
        desp = (0.0, 0.0, 0.0)
        rots = {"pelvis": (0, 5.0, 0), "lumbar": (0, 8.0, 0), "pecho": (0, 10.0, 0), "cuello": (0, 6.0, 0), "cabeza": (0, 2.0, 0)}
        ti = (xc + 0.20, yc + 0.02, 0.45, -15.0, 0.0)
        td = (xc - 0.02, -yc - 0.02, 0.35, -30.0, 0.0)
        brazos = {"i": (110.0, 35.0, 125.0, 25.0), "d": (95.0, 38.0, 110.0, 28.0)}
    elif etapa == "caida":
        desp = (0.0, 0.0, 0.0)
        rots = {"pelvis": (0, 3.0, 0), "lumbar": (0, 4.0, 0), "pecho": (0, 5.0, 0), "cuello": (0, 3.0, 0), "cabeza": (0, 1.0, 0)}
        ti = (xc + 0.10, yc + 0.04, alt + 0.10, 10.0, 0.0)
        td = (xc + 0.04, -yc - 0.04, alt + 0.06, 10.0, 0.0)
        brazos = {"i": (25.0, 55.0, 35.0, 45.0), "d": (25.0, 55.0, 35.0, 45.0)}
    elif etapa == "aterrizaje":
        desp = (-0.05, 0.0, -0.30)
        rots = {"pelvis": (0, 14.0, 0), "lumbar": (0, 22.0, 0), "pecho": (0, 30.0, 0), "cuello": (0, 18.0, 0), "cabeza": (0, 8.0, 0)}
        ti = (xc + 0.04, yc + 0.03, alt, 0.0, 0.0)
        td = (xc + 0.02, -yc - 0.03, alt, 0.0, 0.0)
        brazos = {"i": (35.0, 20.0, 60.0, 12.0), "d": (35.0, 20.0, 60.0, 12.0)}
    else:
        raise ValueError(f"etapa de salto desconocida: {etapa}")
    return _armar_pose(m, desp, rots, ti, td, brazos)


# Pesos (impulso, ascenso, caida) según la velocidad vertical (m/s, + = sube) mientras está en el aire.
def pesos_salto(vel_vertical):
    try:
        vy = float(vel_vertical)
    except (TypeError, ValueError):
        vy = 0.0
    if vy != vy:
        vy = 0.0
    impulso = _suave((vy - 2.0) / 3.0)
    caida = _suave((-vy - 0.5) / 3.0)
    ascenso = max(0.0, 1.0 - impulso - caida)
    total = impulso + ascenso + caida
    return impulso / total, ascenso / total, caida / total


DURACION_ATERRIZAJE = 0.28      # s que tarda en irse la flexión de amortiguación al caer
