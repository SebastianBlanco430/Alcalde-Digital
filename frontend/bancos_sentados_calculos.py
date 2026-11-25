# Cálculos de la gente de las plazas: BANCOS SENTADOS y CORROS (frontend/bancos_sentados.py). Python puro, sin Panda
# ni ursina, con tests en tests/test_bancos_sentados.py.
#   - pose_sentado(fase, m): la pose de una persona SENTADA (pose propia, no la de pie doblada): pelvis baja hasta el
#     asiento, muslos horizontales, rodillas a ~90 grados con los pies apoyados delante (IK de piernas de
#     frontend/animacion_humana_calculos), espalda algo recostada, manos sobre los muslos. A lo largo del ciclo respira
#     (el pecho sube y baja) y mira despacio a un lado y al otro. frontend/animacion_humana.py la hornea como el clip
#     CLIP (con la bandera encendida) en cada modelo .glb, igual que la marcha.
#   - lado_del_banco(u) / posicion_en_banco(...): dónde se sienta cada NPC en su banco (determinista por el sitio).
#   - pose_charla(fase, m): de pie charlando en un corro: cambia el peso de pierna, gesticula con una mano en la primera
#     mitad del ciclo, asiente y mira a los demás. Se hornea como el clip CLIP_CHARLA (con su bandera encendida).
#   - puestos_corro(v): dónde está cada persona del corro (en rueda, mirando al centro), determinista por la variante.
#
# Banderas (la variable de entorno manda sobre la constante):
#   BANCOS_SENTADOS / ALCALDE_BANCOS_SENTADOS=0   las figuras de bloques de siempre en los bancos (ciudad_viva.mesh_sentados)
#   BANCOS_CORROS   / ALCALDE_BANCOS_CORROS=0     las figuras de bloques de siempre en los corros (ciudad_viva.mesh_corro)

import math
import os

from frontend import animacion_humana_calculos as ac

BANCOS_SENTADOS = True
BANCOS_CORROS = True
CLIP = "HumSentado"
CLIP_CHARLA = "HumCharla"
# personas por corro y radio de la rueda (m)
PERSONAS_CORRO = 4
RADIO_CORRO = 0.85
# grados que sube el brazo al gesticular y que gira la cabeza hacia los lados
GESTO = 38.0
MIRADA_CORRO = 18.0
# el ciclo de 24 fotogramas a 30 fps dura 0,8 s: a 0,22 son ~3,6 s (respiración lenta)
VELOCIDAD_CLIP = 0.22
# altura de la cadera sentada respecto a la de pie (asiento a ~0,5 m)
FRACCION_CADERA = 0.6
# el tobillo va esta fracción del muslo por delante de la cadera (rodilla a ~90 grados)
ADELANTE_PIE = 1.2
# grados de la pelvis hacia atrás (negativo = recostado)
RECOSTADO = -6.0
# grados que se mueve el pecho al respirar
RESPIRA = 1.6
# grados que gira la cabeza a cada lado
MIRADA = 14.0
# m del centro del banco a cada sitio (banco de ~1,8 m)
LADO = 0.38
# m hacia el respaldo desde el centro del asiento (negativo: hacia el borde, las rodillas salen de la tabla)
ATRAS = -0.08
# Brazos (hombro adelante, abducción, codo, abducción): mano apoyada sobre el muslo.
BRAZO_REPOSO = (24.0, 10.0, 70.0, 6.0)


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(constante)


def activo():
    return _bandera("ALCALDE_BANCOS_SENTADOS", BANCOS_SENTADOS)


def corros_activos():
    return _bandera("ALCALDE_BANCOS_CORROS", BANCOS_CORROS)


def pose_sentado(fase, m=None):
    """Pose (formato de animacion_humana_calculos) de una persona sentada en la `fase` (0..1) de su ciclo."""
    m = m or ac.Medidas()
    fase = fase % 1.0
    c = math.cos(2 * math.pi * fase)
    s = math.sin(2 * math.pi * fase)
    alto_cadera = m.cadera_i[2]
    bajada = alto_cadera * (FRACCION_CADERA - 1.0)
    desp = (0.0, 0.0, bajada)
    respira = RESPIRA * (0.5 - 0.5 * c)
    mira = MIRADA * s
    rots = {"pelvis": (0.0, RECOSTADO, 0.0), "lumbar": (0.0, 3.0, 0.0), "pecho": (0.3 * mira, 2.0 - respira, 0.0),
            "cuello": (0.3 * mira, -2.0, 0.0), "cabeza": (0.6 * mira, -2.0 + 0.5 * respira, 0.0)}
    yc = abs(m.cadera_i[1]) + 0.04
    x_pie = m.cadera_i[0] + ADELANTE_PIE * m.largo_muslo
    tobillo_i = (x_pie, yc, m.altura_tobillo, 0.0, 0.0)
    tobillo_d = (x_pie, -yc, m.altura_tobillo, 0.0, 0.0)
    brazos = {"i": BRAZO_REPOSO, "d": BRAZO_REPOSO}
    return ac._armar_pose(m, desp, rots, tobillo_i, tobillo_d, brazos)


def lado_del_banco(u):
    """-1 (izquierda) o +1 (derecha) según el número fijo `u` (0..1) del sitio."""
    return -1 if u < 0.5 else 1


def posicion_en_banco(x, z, giro, u):
    """(x, z) del NPC en el banco centrado en (x, z) y girado `giro` (su frente mira a +z local girado): a un lado y
    algo hacia el respaldo."""
    dx, dz = LADO * lado_del_banco(u), -ATRAS
    sen, cos = math.sin(math.radians(giro)), math.cos(math.radians(giro))
    return x + dx * cos + dz * sen, z - dx * sen + dz * cos


def pose_charla(fase, m=None):
    """Pose (formato de animacion_humana_calculos) de una persona de pie charlando, en la `fase` (0..1) de su ciclo."""
    m = m or ac.Medidas()
    fase = fase % 1.0
    s1, c1 = math.sin(2 * math.pi * fase), math.cos(2 * math.pi * fase)
    # gesto: la mano derecha sube y se mueve solo en la primera mitad del ciclo (habla); en la otra escucha
    g = max(0.0, s1) ** 2
    vaiven = math.sin(6 * math.pi * fase) * g
    sway = 0.012 * c1
    desp = (0.0, sway, -0.006 * (1 + c1))
    rots = {"pelvis": (2.0 * c1, 0.0, 1.5 * c1), "lumbar": (0, 1.0, 0), "pecho": (4.0 * s1, 2.0 + 1.5 * g, 0.0),
            "cuello": (0.3 * MIRADA_CORRO * c1, 0.0, 0.0),
            "cabeza": (0.6 * MIRADA_CORRO * c1, -2.0 + 4.0 * math.sin(4 * math.pi * fase) * (1 - g), 0.0)}
    xc = m.cadera_i[0]
    yc = abs(m.cadera_i[1]) + 0.05
    alt = m.altura_tobillo
    reposo = (4.0, 6.0, 14.0, 3.0)
    habla = (14.0 + GESTO * g, 10.0 + 8.0 * vaiven, 60.0 + GESTO * g + 10.0 * vaiven, 6.0)
    brazos = {"i": reposo, "d": habla}
    return ac._armar_pose(m, desp, rots, (xc, yc, alt, 0.0, 0.0), (xc, -yc, alt, 0.0, 0.0), brazos)


def puestos_corro(v, n=PERSONAS_CORRO, radio=RADIO_CORRO):
    """[(x, z, rumbo)] locales de las `n` personas del corro de variante `v`: en rueda, con un poco de desorden
    determinista, cada una mirando al centro (rumbo en grados, convención de Ursina: 0 = mira a +z)."""
    from backend.logica.azar_fijo import azar_de
    puestos = []
    for k in range(n):
        a = 2 * math.pi * (k + 0.3 * azar_de(k, v)) / n
        r = radio * (0.9 + 0.2 * azar_de(k + 7, v))
        x, z = r * math.cos(a), r * math.sin(a)
        puestos.append((x, z, math.degrees(math.atan2(-x, -z))))
    return puestos
