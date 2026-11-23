# Ciclo de mañana, tarde y noche del CIELO (Python puro: NO importa ursina). Solo cambia el color del cielo (domo, sol,
# nubes, mar y cerros del fondo) y, para que no quede costura, el de la niebla, que siempre es el del horizonte. La luz del
# sol, las sombras y la ciudad no se tocan.
#
# La hora es la del reloj de 7 días (ambiente_vivo.hora(): 0..24). Sin reloj (en línea, ALCALDE_RELOJ=0, menús) el cielo es
# el atardecer de siempre. Entre dos tramos fijos los colores se mezclan en PASOS_MEZCLA escalones (no cada frame): cada
# escalón reescribe los colores de la malla del cielo y la niebla una sola vez.
#
#   00:00-04:30 noche · 06:00 amanecer (solo de paso) · 07:30-14:30 mañana · 17:00-18:30 tarde (el cielo de siempre) · 20:00 noche
#
# La paleta «tarde» es la de frontend/cielo.py (sus constantes de siempre); aquí están las otras tres.
# Banderas: CICLO_DIA = False o ALCALDE_CICLO_DIA=0 dejan el atardecer fijo de antes. ALCALDE_HORA_CIELO=<0-24> fija la hora
# del cielo (capturas y feria) aunque no haya reloj.

import os

from frontend import atmosfera_calculos as atmosfera

CICLO_DIA = True
PASOS_MEZCLA = 32                # escalones de color entre dos tramos (≈ 0,6 s reales cada uno con la semana de 30 min)
PERIODO_CICLO = 0.5              # s reales entre dos lecturas de la hora

# (hora, paleta): entre dos puntos seguidos se mezclan sus paletas; mismo nombre = tramo fijo.
TRAMOS = (
    (0.0, "noche"), (4.5, "noche"), (6.0, "amanecer"), (7.5, "manana"), (14.5, "manana"),
    (17.0, "tarde"), (18.5, "tarde"), (20.0, "noche"), (24.0, "noche"),
)
# Elevaciones (seno del ángulo sobre el horizonte) de las paradas del degradado: las mismas de cielo.PARADAS_CIELO.
ELEVACIONES = (0.00, 0.08, 0.22, 0.45, 0.75, 1.00)


def _paleta(horizonte, degradado, resplandor, fuerza, sol, mar, reflejo, cerros, nube_arriba, nube_abajo):
    return {"horizonte": horizonte, "paradas": tuple(zip(ELEVACIONES, (horizonte,) + tuple(degradado))),
            "resplandor": resplandor, "fuerza_resplandor": fuerza, "sol": sol, "mar": mar, "reflejo_mar": reflejo,
            "cerros": cerros, "nube_arriba": nube_arriba, "nube_abajo": nube_abajo}


PALETAS = {
    # Mañana despejada: el cielo azul de antes del atardecer (ver el comentario de cielo.PARADAS_CIELO), cerros verdosos.
    "manana": _paleta((238, 224, 204), ((214, 222, 230), (180, 206, 234), (146, 190, 232), (100, 156, 224), (74, 128, 210)),
                      (255, 248, 226), 0.45, (255, 250, 228), (72, 128, 196), (222, 236, 250),
                      ((150, 176, 188), (100, 134, 138)), (255, 255, 255), (196, 210, 228)),
    # Amanecer: franja melocotón pálida en el horizonte que sube enseguida a lila y azul (la tarde es cálida hasta arriba);
    # solo se ve de paso entre la noche y la mañana.
    "amanecer": _paleta((255, 214, 170), ((236, 196, 186), (196, 178, 204), (150, 168, 214), (112, 142, 206), (86, 118, 196)),
                        (255, 226, 190), 0.60, (255, 226, 176), (78, 108, 166), (255, 206, 160),
                        ((160, 140, 170), (104, 100, 140)), (255, 232, 214), (196, 170, 196)),
    # Noche: azul marino casi negro arriba; el disco del sol queda como una luna pálida con un halo frío.
    "noche": _paleta((40, 48, 82), ((32, 40, 74), (24, 32, 64), (18, 24, 54), (12, 18, 44), (8, 12, 34)),
                     (150, 170, 220), 0.25, (226, 232, 246), (14, 22, 44), (70, 86, 130),
                     ((30, 34, 58), (18, 20, 40)), (70, 78, 110), (34, 38, 62)),
}
if atmosfera.activa():       # perspectiva atmosférica (frontend/atmosfera_calculos.py): horizonte, cielo bajo y cerros apagados
    PALETAS = {nombre: atmosfera.atenuar_paleta(paleta) for nombre, paleta in PALETAS.items()}
NOMBRES_PERIODO = {"manana": "mañana", "amanecer": "mañana", "tarde": "tarde", "noche": "noche"}


def activo():
    valor = os.environ.get("ALCALDE_CICLO_DIA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(CICLO_DIA)


# Hora fijada con ALCALDE_HORA_CIELO (0..24) o None.
def hora_forzada():
    bruto = os.environ.get("ALCALDE_HORA_CIELO", "").strip()
    if not bruto:
        return None
    try:
        return float(bruto.replace(",", ".")) % 24.0
    except ValueError:
        return None


# (paleta_a, paleta_b, t) de la hora: t (0..1, en escalones de 1/PASOS_MEZCLA) va de a hacia b. Sin hora: el atardecer.
def mezcla_de_hora(hora):
    if hora is None:
        return "tarde", "tarde", 0.0
    h = float(hora) % 24.0
    for (h0, a), (h1, b) in zip(TRAMOS, TRAMOS[1:]):
        if h <= h1:
            if a == b or h1 <= h0:
                return a, a, 0.0
            t = round((h - h0) / (h1 - h0) * PASOS_MEZCLA) / PASOS_MEZCLA
            if t <= 0.0:
                return a, a, 0.0
            if t >= 1.0:
                return b, b, 0.0
            return a, b, t
    return TRAMOS[-1][1], TRAMOS[-1][1], 0.0


# VIS-003: la LUZ del mundo sigue al cielo con las mismas paletas y los mismos escalones (mezcla_de_hora). Multiplicadores
# (r, g, b) del sol (DirectionalLight) y del ambiente (AmbientLight) sobre los colores que ya pone la ciudad viva por salud;
# la «tarde» es 1 (la luz de siempre). De noche se oscurece y se enfría sin perder la lectura (el jugador, los NPC, los
# letreros y la línea del GPS, que no reciben luz, siguen claros). Los focos de las farolas (sin sombreado) brillan más.
LUZ_PALETAS = {
    "manana": ((1.0, 1.03, 1.08), (1.0, 1.02, 1.06)),
    "amanecer": ((0.92, 0.82, 0.78), (0.84, 0.80, 0.88)),
    "tarde": ((1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
    "noche": ((0.32, 0.36, 0.52), (0.50, 0.53, 0.70)),
}
FOCOS_DIA, FOCOS_NOCHE = 1.0, 1.3      # escala de color de los focos de las farolas


def _mezclar_tripla(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t, 4) for i in range(3))


def luz_de_hora(hora):
    """((r, g, b) del sol, (r, g, b) del ambiente) multiplicativos para la hora (None = la tarde de siempre: 1)."""
    a, b, t = mezcla_de_hora(hora)
    (sol_a, amb_a), (sol_b, amb_b) = LUZ_PALETAS[a], LUZ_PALETAS[b]
    return _mezclar_tripla(sol_a, sol_b, t), _mezclar_tripla(amb_a, amb_b, t)


def peso_noche(hora):
    """0 de día, 1 de noche, con los mismos escalones del cielo entre medias."""
    a, b, t = mezcla_de_hora(hora)
    return round((1.0 - t) * (a == "noche") + t * (b == "noche"), 4)


def focos_de_hora(hora):
    return round(FOCOS_DIA + (FOCOS_NOCHE - FOCOS_DIA) * peso_noche(hora), 4)


# Luz-noche (retoques 23-nov): la SOMBRA PROYECTADA sigue a la luz del sol de la hora. El shader lit_with_shadows de Ursina
# le RESTA a todo lo que está a la sombra una cantidad fija, (1 - rgb) * alfa del `shadow_color` (frontend/piezas.py), que
# no depende del color de la luz: de día (sol x1) es la sombra de siempre, pero de noche el sol baja a x0,32-0,52 y esa
# resta fija pasa a ser mayor que el color mismo -> las fachadas a la sombra (y lo que cae en su sombra) salen NEGRAS.
# Aquí la resta se escala por canal con el multiplicador del sol de la hora (acotado a 1: de día queda idéntica), así lo
# que está a la sombra de noche es lo mismo que de día por la luz de la noche: sol * (color - resta), nunca recortado a 0.
# Segunda pasada (D2 del verificador): de noche la resta sigue al sol FINAL (hora x salud), porque en crisis la salud baja
# el sol (x0,72/0,78/0,95) y con solo la hora las fachadas oscuras volvían a recortarse a negro. La parte de salud se pondera
# con peso_noche (0 de día, 1 de noche, por los mismos escalones del cielo): continuo al anochecer y al amanecer, y de día
# (peso 0) la sombra es EXACTAMENTE la de siempre en todos los niveles (la crisis de día oscurecida se queda como está).
PASO_SALUD_SOMBRA = 0.01          # se redondea el factor de salud: la sombra no cambia por variaciones de una milésima


def salud_de_noche(hora, salud):
    """Factor RGB de la salud sobre el sol (sol tras la salud / sol base) ponderado por cuánta noche hay:
    1 + peso_noche * (salud - 1), redondeado a PASO_SALUD_SOMBRA. De día (peso 0): (1, 1, 1)."""
    w = peso_noche(hora)
    if w <= 0.0 or salud is None:
        return (1.0, 1.0, 1.0)
    salida = []
    for c in tuple(salud)[:3]:
        f = 1.0 + w * (max(0.0, float(c)) - 1.0)
        salida.append(round(round(f / PASO_SALUD_SOMBRA) * PASO_SALUD_SOMBRA, 4))
    return tuple(salida)


def sombra_de_hora(hora, sombra, salud=None):
    """`shadow_color` (r, g, b, a) para la hora a partir del de siempre (`sombra`): misma alfa y la resta (1 - c) * a
    escalada por k = min(1, sol de luz_de_hora x salud_de_noche(hora, salud)). `salud`: (r, g, b) sol tras la salud / sol
    base (None = 1). Sin hora, de día o con k >= 1: `sombra` tal cual."""
    sol, _ = luz_de_hora(hora)
    f = salud_de_noche(hora, salud)
    k = tuple(min(1.0, max(0.0, float(sol[i]) * f[i])) for i in range(3))
    base = tuple(float(c) for c in sombra[:4])
    if k == (1.0, 1.0, 1.0):
        return base
    return tuple(round(1.0 - (1.0 - base[i]) * k[i], 4) for i in range(3)) + (base[3],)


# «mañana», «tarde» o «noche» de la hora (el amanecer cuenta como mañana). Sin hora: «tarde».
def periodo_de_hora(hora):
    a, b, t = mezcla_de_hora(hora)
    return NOMBRES_PERIODO[b if t >= 0.5 else a]


# Lista plana [r, g, b, a, r, g, b, a...] de una lista de colores RGBA (0..1): así se mezcla y se escribe más rápido.
def plano(colores):
    return [c for color in colores for c in color]


# b - a, componente a componente (dos listas planas del mismo largo): se calcula una vez por par de paletas.
def diferencia(a, b):
    return [y - x for x, y in zip(a, b)]


# a + (b - a)·t con la diferencia ya hecha (listas planas). Medido: ~1,3 ms para el cielo y las nubes (~3.600 vértices).
def mezclar_plano(a, dif, t):
    if t <= 0.0:
        return a
    return [x + d * t for x, d in zip(a, dif)]


# Mezcla de dos colores RGB 0-255 (enteros).
def mezclar_rgb(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))
