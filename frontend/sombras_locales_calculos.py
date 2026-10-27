# F6: lo PURO de las sombras locales del mapa grande (sin ventana ni Panda). Un volumen de sombra de LADO m centrado en el
# jugador se hornea una vez (buffer one-shot) y se vuelve a hornear al alejarse del centro o al cambiar los chunks de
# alrededor. El centro de la película de la luz se ajusta a la rejilla de texels: así, dos horneados vecinos dibujan
# exactamente la misma sombra en la zona común y no hay parpadeo del borde de sombra al re-hornear.

import math

LADO = 170.0                  # m: lado de la película (cuadrada) de la luz; el volumen útil es el círculo inscrito
TEXELS = 2048                 # resolución del mapa de sombras (8,3 cm por texel)
RANGO_PROFUNDIDAD = 600.0     # m entre el plano cercano y el lejano de la luz (el bias del shader -0,0008 equivale a ~0,5 m)
UMBRAL_MOVIMIENTO = 24.0      # m que se aleja el jugador del centro horneado antes de re-hornear
INTERVALO_MIN = 0.6           # s mínimos entre dos horneados (el cambio de chunks se junta en uno solo)
TRANSICION = 1.4              # s que tarda el centro del desvanecimiento en pasar del centro viejo al nuevo tras un horneado
FADE_INICIO = 0.70            # fracción del radio de película donde la sombra empieza a desvanecerse
FADE_FIN = 0.93               # ... y donde ya vale 0 (todo iluminado, como en F5). Menos de 1: deja margen en el mapa
MARGEN_CHUNKS = 20.0          # m extra al mirar qué chunks cambian dentro del volumen (sombras de edificios altos que caen dentro)
CADA_N_FRAMES = 6             # cada cuántos frames se mira la firma de chunks


def radio_volumen(lado=LADO):
    return lado / 2.0


def tamano_texel(lado=LADO, texels=TEXELS):
    return lado / float(texels)


def rango_fade(lado=LADO, inicio=FADE_INICIO, fin=FADE_FIN):
    """(r0, r1) en m desde el centro: sombra completa hasta r0, nula desde r1 (desvanecimiento suave entre ambos)."""
    r = radio_volumen(lado)
    return (r * inicio, r * fin)


def ajustar_a_rejilla(valor, texel):
    """Redondea una coordenada al múltiplo de `texel` más cercano."""
    return round(valor / texel) * texel


def lente_local(punto_luz, lado=LADO, texels=TEXELS, rango=RANGO_PROFUNDIDAD):
    """Parámetros de la lente ortográfica de la luz para un volumen centrado en `punto_luz` = (x, y, z) del centro EN EL
    ESPACIO DE LA LUZ. Devuelve (offset_x, offset_y, cerca, lejos, lado) con el offset ajustado a la rejilla de texels."""
    t = tamano_texel(lado, texels)
    ox = ajustar_a_rejilla(punto_luz[0], t)
    oy = ajustar_a_rejilla(punto_luz[1], t)
    return ox, oy, punto_luz[2] - rango / 2.0, punto_luz[2] + rango / 2.0, lado


def debe_rehornear(centro, foco, firma_horneada, firma_actual, t_ultimo, ahora, umbral=UMBRAL_MOVIMIENTO,
                   intervalo=INTERVALO_MIN):
    """¿Hay que re-hornear? Sin horneado previo: en cuanto haya algo que dibujar. Si no: al alejarse más de `umbral` m del
    centro, o al cambiar la firma de chunks, pero nunca antes de `intervalo` s desde el último."""
    if centro is None:
        return bool(firma_actual)
    if ahora - t_ultimo < intervalo:
        return False
    if math.hypot(foco[0] - centro[0], foco[1] - centro[1]) > umbral:
        return True
    return firma_actual != firma_horneada


def firma_de_chunks(claves_lod0, limites, x, z, radio=radio_volumen() + MARGEN_CHUNKS):
    """Conjunto (frozenset) de los chunks LOD0 que tocan el círculo de `radio` m alrededor de (x, z). `limites`: clave ->
    (xmin, xmax, zmin, zmax). Cambia cuando aparece o desaparece un chunk con edificios dentro del volumen."""
    dentro = []
    for clave in claves_lod0:
        xmin, xmax, zmin, zmax = limites[clave]
        d = math.hypot(x - min(max(x, xmin), xmax), z - min(max(z, zmin), zmax))
        if d <= radio:
            dentro.append(clave)
    return frozenset(dentro)


def factor_de_sombra(d, r0, r1):
    """Réplica en Python del desvanecimiento del shader: 1 = sombra completa, 0 = nada, a `d` m del centro horneado."""
    if r1 <= 0.0:
        return 0.0
    if r1 <= r0:
        return 1.0 if d < r1 else 0.0
    t = min(1.0, max(0.0, (d - r0) / (r1 - r0)))
    return 1.0 - t * t * (3.0 - 2.0 * t)


def avance_transicion(ahora, t0, duracion=TRANSICION):
    """0..1 (suavizado) de la transición que empezó en t0."""
    if duracion <= 0.0:
        return 1.0
    t = min(1.0, max(0.0, (ahora - t0) / duracion))
    return t * t * (3.0 - 2.0 * t)


def centro_de_fade(viejo, nuevo, k):
    """Centro (x, z) del desvanecimiento: empieza en el del horneado anterior (donde las sombras ya se veían así) y se desliza al
    nuevo. Dentro del mapa nuevo la sombra cambia de forma continua; sin `viejo` (primer horneado) vale `nuevo`."""
    if viejo is None:
        return nuevo
    return (viejo[0] + (nuevo[0] - viejo[0]) * k, viejo[1] + (nuevo[1] - viejo[1]) * k)
