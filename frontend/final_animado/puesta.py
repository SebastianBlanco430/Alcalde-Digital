# Puesta en escena del final animado (PURO: no importa ursina; se prueba con pytest en tests/test_final_animado_puesta.py).
# Por id de plano (los del JSON, «animacion»): qué decorado y qué actores lleva, en qué posición RELATIVA a su ancla
# (frontend/final_animado/lugares.py), con qué acción y en qué tramo de t (0..1 del plano). La escenografía
# (escenografia.py) lo convierte en entidades; aquí solo hay datos y cálculo.
#
# Marco local del ancla: (derecha, alto, frente); «frente» = hacia donde mira el sujeto (y, en casi todos los planos,
# hacia la cámara). Rumbo RELATIVO de un actor: 0 = mira al frente del ancla, 180 = le da la espalda; o un punto
# (derecha, frente) al que mirar.
#
# Reparto (decisión del dueño del proyecto): Octavio Ruedas = el modelo del rol candidato («prota:candidato»); Tomás
# Arenas = NPC de la fábrica, mayor, de traje oscuro («arenas»); vecinos = NPC de la fábrica con semilla fija («v0»..);
# los NPC de oficio de la etapa +3 («npc:florista», «npc:panadero», «npc:escobita», «npc:musico»).
#
#   puesta(id) -> Puesta        ids() -> ids con puesta        estado_actor(actor, t) -> EstadoActor
#   actores_del_pool(puestas)   ventanas(id, t) -> brillos     reparto_vecino(k) -> (índice, semilla)

import math
import random
from dataclasses import dataclass, field

SEMILLA_VECINOS = 7311
N_VECINOS = 10
INDICES_VECINOS = tuple(random.Random(SEMILLA_VECINOS).sample(range(12, 60), N_VECINOS))
SEMILLA_ARENAS = 5417 * 3 + 1

PROTAGONISTAS = ("ciudadano", "periodista", "influencer", "candidato")
OCTAVIO = "prota:candidato"
ARENAS = "arenas"
DISTANCIA_MINIMA = 0.6          # m entre dos actores en cualquier t (sin contacto entre personas)

# Ventanas de la Prefeitura (marco del ancla «prefeitura»: la fachada está en frente -1,2; puerta en derecha 0).
# (derecha, alto) del centro de cada ventana; las 6 de la sede del Partido de la Tradición.
VENTANAS_PREFEITURA = ((0.0, 5.0), (2.3, 5.0), (4.6, 5.0), (0.0, 8.3), (2.3, 8.3), (4.6, 8.3))
VENTANA_DESPACHO = 4            # la del despacho del alcalde (m5: la única encendida)
FRENTE_FACHADA_PREFEITURA = -1.12


@dataclass(frozen=True)
class Paso:
    t0: float
    t1: float
    accion: str
    hasta: tuple = None          # (derecha, frente) a la que llega en t1 (camina)
    alto: float = None           # alto al que llega en t1 (sube un escalón)
    mira: object = None          # rumbo relativo (número) o punto (derecha, frente) mientras dura el paso


@dataclass(frozen=True)
class Actor:
    id: str                      # del pool: "prota:<rol>", "arenas", "npc:<tipo>", "v<k>"
    derecha: float
    frente: float
    rumbo: object = 0.0          # relativo, o punto (derecha, frente) al que mira
    accion: str = "quieto"       # la que hace fuera de los pasos
    pasos: tuple = ()
    alto: float = 0.0
    sobre_ancla: bool = False    # pisa a la altura del ancla (azotea) y no el suelo del punto
    prop: str = None             # "pancarta", "escoba", "guitarra", "tambor", "maracas", "maletin", "canasta", "bandeja"
    texto: str = None            # el de la pancarta
    fase: float = 0.0            # desfase 0..1 de los gestos que se repiten
    fuera_de_calle: bool = False  # se para donde no se camina (azotea, podio, detrás de la ventana del Morro)


@dataclass(frozen=True)
class Pieza:
    tipo: str
    derecha: float = 0.0
    frente: float = 0.0
    alto: float = 0.0
    giro: float = 0.0            # relativo al rumbo del ancla
    texto: str = None
    variante: int = 0
    tramo: tuple = None          # (t0, t1) de su animación
    sobre_ancla: bool = False
    ancla: str = None            # otra ancla (las ventanas de la Prefeitura vistas desde la protesta)
    medida: float = 1.0          # ancho / largo según el tipo


@dataclass(frozen=True)
class Puesta:
    id: str
    ancla: str
    actores: tuple = ()
    piezas: tuple = ()


@dataclass(frozen=True)
class EstadoActor:
    derecha: float
    frente: float
    alto: float
    rumbo: float                 # relativo al ancla
    accion: str
    k: float                     # avance 0..1 dentro del paso actual (1 fuera de pasos)
    t_paso: float                # t en que empezó el paso actual
    moviendo: bool


# -- Cálculo ---------------------------------------------------------------------------------------------------------

def rumbo_rel(desde, hasta):
    """Rumbo relativo (grados, 0 = frente del ancla, 90 = derecha) para mirar de (d, f) a (d, f)."""
    return math.degrees(math.atan2(hasta[0] - desde[0], hasta[1] - desde[1])) % 360.0


def _rumbo(mira, pos):
    if isinstance(mira, (tuple, list)):
        return rumbo_rel(pos, mira)
    return float(mira) % 360.0


def _suave(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def estado_actor(actor, t):
    """Posición (relativa), alto, rumbo y acción del actor en t (0..1). Los pasos van en orden; antes del primero y
    entre pasos el actor está quieto donde quedó, con su `accion` de fondo."""
    t = max(0.0, min(1.0, float(t)))
    pos = (actor.derecha, actor.frente)
    alto = actor.alto
    rumbo = _rumbo(actor.rumbo, pos)
    for paso in actor.pasos:
        if t < paso.t0:
            break
        destino = paso.hasta if paso.hasta is not None else pos
        alto_fin = paso.alto if paso.alto is not None else alto
        largo = max(1e-6, paso.t1 - paso.t0)
        if t < paso.t1:                                       # dentro del paso
            k = (t - paso.t0) / largo
            camina = paso.hasta is not None and math.dist(pos, destino) > 1e-3
            q = k if camina else _suave(k)
            d = pos[0] + (destino[0] - pos[0]) * q
            f = pos[1] + (destino[1] - pos[1]) * q
            a = alto + (alto_fin - alto) * _suave(k)
            if camina:
                r = rumbo_rel(pos, destino)
            elif paso.mira is not None:
                r = _rumbo(paso.mira, (d, f))
            else:
                r = rumbo
            return EstadoActor(d, f, a, r, "caminar" if camina and paso.accion == "quieto" else paso.accion, k,
                               paso.t0, camina)
        if paso.hasta is not None and math.dist(pos, destino) > 1e-3:
            rumbo = rumbo_rel(pos, destino)
        pos, alto = destino, alto_fin
        if paso.mira is not None:
            rumbo = _rumbo(paso.mira, pos)
    ultimo = None
    for paso in actor.pasos:
        if paso.t1 <= t:
            ultimo = paso
    if ultimo is not None and ultimo.t1 >= 0.999 and t >= ultimo.t1:     # el último paso dura hasta el final
        return EstadoActor(pos[0], pos[1], alto, rumbo, ultimo.accion, 1.0, ultimo.t0, False)
    return EstadoActor(pos[0], pos[1], alto, rumbo, actor.accion, 1.0, 0.0, False)


def puntos_de_pie(actor):
    """(derecha, frente) donde el actor está parado: el de salida y el final de cada paso que camina."""
    puntos = [(actor.derecha, actor.frente)]
    for paso in actor.pasos:
        if paso.hasta is not None:
            puntos.append(tuple(paso.hasta))
    return puntos


def muestras_t(n=41):
    return [k / (n - 1) for k in range(n)]


def distancia_minima(puesta_, n=41):
    """Distancia mínima (m, en el plano) entre dos actores de la puesta a lo largo del plano. inf con < 2 actores."""
    minima = math.inf
    for t in muestras_t(n):
        estados = [estado_actor(a, t) for a in puesta_.actores]
        for i in range(len(estados)):
            for j in range(i + 1, len(estados)):
                a, b = estados[i], estados[j]
                if abs(a.alto - b.alto) > 1.2:
                    continue
                minima = min(minima, math.hypot(a.derecha - b.derecha, a.frente - b.frente))
    return minima


def ventanas(plano_id, t):
    """Brillo (0..1) de cada una de las ventanas de la Prefeitura (VENTANAS_PREFEITURA) en t; None si el plano no
    lleva ventanas. b2: las 6 encendidas se apagan una a una entre t 0,2 y 0,8 (de la de arriba a la derecha a la de
    abajo a la izquierda). m5: solo la del despacho, con un parpadeo muy leve. n5: la mitad."""
    t = max(0.0, min(1.0, float(t)))
    if plano_id == "b2_sede_oscura":
        orden = (5, 4, 3, 2, 1, 0)
        out = [1.0] * 6
        for paso, k in enumerate(orden):
            t_apaga = 0.2 + 0.6 * paso / 5
            out[k] = 1.0 - _suave((t - t_apaga) / 0.06)
        return tuple(out)
    if plano_id == "m5_plaza_vacia":
        parpadeo = 0.9 + 0.06 * math.sin(2 * math.pi * 1.7 * t * 9.0) + 0.04 * math.sin(2 * math.pi * 4.3 * t * 9.0)
        return tuple(parpadeo if k == VENTANA_DESPACHO else 0.0 for k in range(6))
    if plano_id == "n5_candidatos":
        return tuple(1.0 if k in (0, 2, 4) else 0.0 for k in range(6))
    return None


def reparto_vecino(k):
    """(índice de NPC, semilla) del vecino k: determinista (semilla fija), distinto de los peatones del juego."""
    return INDICES_VECINOS[k % N_VECINOS] + 100 * (k // N_VECINOS), SEMILLA_VECINOS


PELO_GRIS = (130, 130, 134)


def aspecto_vecino(aspecto):
    """Ningún vecino con canas: el pelo gris (el de Arenas) pasa a castaño oscuro. Puro: devuelve otra copia."""
    if tuple(aspecto.get("pelo", ())) == PELO_GRIS:
        return dict(aspecto, pelo=(48, 36, 30))
    return aspecto


# -- Ayudas para escribir las puestas -------------------------------------------------------------------------------

def _v(k, d, f, accion="quieto", rumbo=0.0, **kw):
    return Actor(f"v{k}", d, f, rumbo, accion, **kw)


def _papeletas(n, d0, d1, f0, f1, semilla):
    azar = random.Random(semilla)
    return tuple(Pieza("papeleta", azar.uniform(d0, d1), azar.uniform(f0, f1), giro=azar.uniform(0, 360),
                       variante=azar.randrange(4)) for _ in range(n))


def _podio(con_confeti=False):
    piezas = [Pieza("podio"), Pieza("atril", 0.0, 0.48, 0.5)]
    if con_confeti:
        piezas.append(Pieza("confeti", 0.0, 1.5, 0.0, medida=6.0))
    return tuple(piezas)


CIERRE_FILA = (("ciudadano", -2.4), ("periodista", -0.8), ("influencer", 0.8), ("candidato", 2.4))
FRENTE_CIERRE = 2.4


def _cierre(acciones):
    """Los cuatro protagonistas en fila al borde de la azotea, de espaldas a la cámara. `acciones`: rol -> (accion de
    fondo, pasos)."""
    actores = []
    for k, (rol, d) in enumerate(CIERRE_FILA):
        accion, pasos = acciones.get(rol, ("quieto", ()))
        actores.append(Actor(f"prota:{rol}", d, FRENTE_CIERRE, 0.0, accion, tuple(pasos), sobre_ancla=True,
                             fase=0.23 * k, fuera_de_calle=True))
    piezas = (Pieza("baranda", 0.0, FRENTE_CIERRE + 1.05, 0.0, sobre_ancla=True, medida=7.6),)
    return tuple(actores), piezas


# -- Las puestas ----------------------------------------------------------------------------------------------------

def _construir():
    p = {}

    # ===== MALO =====
    p["m1_reelegido"] = Puesta("m1_reelegido", "prefeitura", (
        Actor(ARENAS, 0.0, 0.4, 0.0, "saludar", fase=0.1),
        _v(0, -3.0, 9.0, "brazos_cruzados", 180.0),
        _v(1, 3.2, 9.6, "manos_atras", 185.0),
    ), (
        Pieza("rotulo", 2.3, FRENTE_FACHADA_PREFEITURA + 0.55, 3.2, texto="ARENAS · REELEGIDO", medida=5.6),
        Pieza("mesa", 2.6, 0.6), Pieza("urna", 2.6, 0.6, 0.76),
    ) + _papeletas(26, -4.5, 4.5, 2.0, 8.5, 11))

    p["m2_calles_arden"] = Puesta("m2_calles_arden", "plaza")

    pancartas = ("¿QUIÉN DICE\nLA VERDAD?", "RESPUESTAS", "NO MÁS\nRUMORES", "¿A QUIÉN\nLE CREO?", "BASTA")
    p["m3_protesta"] = Puesta("m3_protesta", "protesta", (
        _v(0, -3.0, -1.0, "protestar", prop="pancarta", texto=pancartas[0], fase=0.0),
        _v(1, 0.0, -1.2, "puno", fase=0.35),
        _v(2, 3.0, -1.0, "protestar", prop="pancarta", texto=pancartas[1], fase=0.55),
        _v(3, -4.2, -3.1, "puno", fase=0.7),
        _v(4, -1.5, -3.0, "protestar", prop="pancarta", texto=pancartas[2], fase=0.25),
        _v(5, 1.5, -3.2, "puno", fase=0.1),
        _v(6, 4.2, -3.0, "protestar", prop="pancarta", texto=pancartas[3], fase=0.8),
        _v(7, -2.6, -5.0, "protestar", prop="pancarta", texto=pancartas[4], fase=0.4),
        _v(8, 2.6, -5.2, "puno", fase=0.6),
    ))

    p["m5_plaza_vacia"] = Puesta("m5_plaza_vacia", "protesta", (), (
        Pieza("pancarta_suelo", -0.6, -2.0, giro=24.0, texto=pancartas[0], variante=0),
        Pieza("pancarta_suelo", 2.8, -0.6, giro=-35.0, texto=pancartas[1], variante=1),
        Pieza("pancarta_suelo", -2.4, -3.6, giro=160.0, texto=pancartas[2], variante=2),
        Pieza("pancarta_suelo", 3.6, -3.4, giro=95.0, texto=pancartas[3], variante=3),
        Pieza("pancarta_suelo", -4.2, -1.2, giro=-120.0, texto=pancartas[4], variante=4),
        Pieza("ventanas", ancla="prefeitura", frente=FRENTE_FACHADA_PREFEITURA),
    ) + _papeletas(18, -5.0, 5.0, -5.5, 3.0, 23))

    actores, baranda = _cierre({rol: ("cabeza_baja", ()) for rol in PROTAGONISTAS})
    p["m6_cierre"] = Puesta("m6_cierre", "azotea", actores, baranda)

    # ===== BUENO =====
    p["b1_gana"] = Puesta("b1_gana", "urna", (
        Actor(OCTAVIO, -1.6, 0.3, 10.0, "saludar"),
        _v(0, -3.8, 1.6, "aplaudir", (-0.8, 0.2), fase=0.0),
        _v(1, -3.3, 3.4, "celebrar", (-0.8, 0.2), fase=0.3),
        _v(2, -1.7, 4.4, "aplaudir", (-0.8, 0.2), fase=0.6),
        _v(3, 3.4, 1.4, "aplaudir", (-0.8, 0.2), fase=0.15),
        _v(4, 3.7, 3.2, "celebrar", (-0.8, 0.2), fase=0.75),
        _v(5, 1.8, 4.5, "aplaudir", (-0.8, 0.2), fase=0.45),
    ), (
        Pieza("mesa"), Pieza("urna", 0.0, 0.0, 0.76), Pieza("papeletas_mesa", 0.32, 0.05, 0.76),
        Pieza("caballete", 2.0, -0.2, giro=-12.0, texto="RUEDAS GANA\nLA ALCALDÍA"),
    ))

    p["b2_sede_oscura"] = Puesta("b2_sede_oscura", "prefeitura", (
        Actor(ARENAS, 0.0, -0.5, 0.0, "quieto", (
            Paso(0.08, 0.26, "quieto", hasta=(0.0, 1.0)),
            Paso(0.26, 0.34, "cabeza_baja", mira=90.0),
            Paso(0.34, 0.98, "quieto", hasta=(4.6, 3.4)),
        ), prop="maletin"),
    ), (
        Pieza("rotulo", 2.3, FRENTE_FACHADA_PREFEITURA + 0.55, 3.2, texto="PARTIDO DE LA TRADICIÓN", medida=6.6),
        Pieza("ventanas", frente=FRENTE_FACHADA_PREFEITURA),
    ))

    p["b3_calles_limpias"] = Puesta("b3_calles_limpias", "calle", (
        Actor("npc:florista", -2.6, 0.6, 15.0, "hablar", prop="canasta"),
        Actor("npc:panadero", 2.6, 0.2, -15.0, "saludar", prop="bandeja", fase=0.4),
        Actor("npc:escobita", -0.9, -1.4, 0.0, "barrer", prop="escoba", fase=0.0),
        _v(0, 1.3, -3.2, "barrer", prop="escoba", fase=0.33),
        _v(1, -0.6, -5.2, "barrer", prop="escoba", fase=0.66),
    ), (
        Pieza("puesto_flores", -3.7, 0.0, giro=90.0),
    ))

    p["b4_musica"] = Puesta("b4_musica", "calle", (
        Actor("npc:musico", -1.5, -12.0, 0.0, "guitarra", prop="guitarra"),
        _v(2, 0.1, -12.6, "tambor", prop="tambor", fase=0.2),
        _v(3, 1.6, -12.0, "maracas", prop="maracas", fase=0.5),
        _v(4, -3.0, -10.0, "bailar", (-0.5, -12.4), fase=0.1),
        _v(5, 3.0, -10.3, "aplaudir", (0.0, -12.4), fase=0.4),
        _v(6, -2.7, -14.2, "aplaudir", (-0.5, -12.0), fase=0.7),
        _v(7, 3.1, -14.0, "bailar", (0.5, -12.0), fase=0.9),
    ), (
        Pieza("guirnalda_calle", 0.0, -13.6, medida=8.6, variante=1),
        Pieza("guirnalda_calle", 0.0, -17.5, medida=8.6, variante=3),
    ))

    publico = ((-3.6, 3.2), (-1.8, 3.4), (1.8, 3.3), (3.6, 3.1), (-4.3, 5.2), (-2.4, 5.4), (2.4, 5.3), (4.3, 5.1),
               (-1.3, 7.2), (1.4, 7.0))
    p["b6_podio"] = Puesta("b6_podio", "podio", (
        Actor(OCTAVIO, 1.9, -0.1, 270.0, "quieto", (
            Paso(0.0, 0.16, "quieto", hasta=(1.35, -0.1)),
            Paso(0.16, 0.3, "quieto", hasta=(0.0, -0.15), alto=0.5),
            Paso(0.3, 0.6, "saludar", mira=0.0),
            Paso(0.6, 1.0, "gracias", mira=0.0),
        ), fuera_de_calle=True),
    ) + tuple(_v(k, d, f, "aplaudir" if k % 3 else "celebrar", (0.0, 0.0), fase=(0.37 * k) % 1.0)
              for k, (d, f) in enumerate(publico)), _podio(con_confeti=True))

    actores, baranda = _cierre({
        "ciudadano": ("quieto", (Paso(0.52, 1.0, "aplaudir"),)),
        "periodista": ("quieto", (Paso(0.55, 1.0, "aplaudir"),)),
        "influencer": ("quieto", (Paso(0.5, 1.0, "aplaudir"),)),
        "candidato": ("quieto", (Paso(0.45, 1.0, "brazo_arriba"),)),
    })
    p["b7_cierre"] = Puesta("b7_cierre", "azotea", actores, baranda)

    # ===== NEUTRO =====
    p["n1_conteo"] = Puesta("n1_conteo", "urna", (
        _v(0, -0.45, -0.75, "contar", 0.0, fase=0.0),
        _v(1, 0.5, -0.75, "contar", 0.0, fase=0.5),
        _v(2, -2.6, -0.4, "brazos_cruzados", (0.0, 0.0)),
        _v(3, -2.3, 1.5, "cintura", (0.0, 0.0)),
        _v(4, 2.6, -0.3, "brazos_cruzados", (0.0, 0.0), fase=0.3),
        _v(5, 2.3, 1.6, "cintura", (0.0, 0.0), fase=0.6),
        _v(6, 0.2, -2.5, "manos_atras", (0.0, 0.0)),
    ), (
        Pieza("mesa"), Pieza("urna", 0.0, 0.0, 0.76, variante=1),
        Pieza("monton", -0.38, 0.1, 0.76, variante=0), Pieza("monton", 0.38, 0.1, 0.76, variante=1),
    ))

    p["n2_plaza_a_medias"] = Puesta("n2_plaza_a_medias", "podio", (
        _v(0, -5.0, 3.6, "aplaudir", 0.0, fase=0.0),
        _v(1, -3.6, 4.4, "celebrar", 0.0, fase=0.4),
        _v(2, -2.1, 3.4, "aplaudir", 0.0, fase=0.7),
        _v(3, -4.4, 5.8, "aplaudir", 0.0, fase=0.2),
        _v(4, 2.2, 3.6, "brazos_cruzados", 0.0),
        _v(5, 3.6, 4.5, "pancarta_abajo", 0.0, prop="pancarta", texto="¿Y AHORA?"),
        _v(6, 5.1, 3.4, "brazos_cruzados", 0.0),
        _v(7, 4.3, 5.8, "manos_atras", 0.0),
    ), _podio() + (Pieza("guirnalda_corta", -3.6, 2.6, medida=3.6, variante=2),))

    p["n3_calle"] = Puesta("n3_calle", "calle", (
        _v(0, -2.4, -6.0, "quieto", pasos=(Paso(0.0, 1.0, "quieto", hasta=(-2.4, 2.0)),)),
        _v(1, -1.4, 3.0, "quieto", pasos=(Paso(0.0, 1.0, "quieto", hasta=(-1.4, -5.0)),)),
        _v(2, 1.6, -8.0, "quieto", pasos=(Paso(0.0, 1.0, "quieto", hasta=(1.6, 0.5)),)),
        _v(3, 2.6, 1.0, "quieto", pasos=(Paso(0.0, 1.0, "quieto", hasta=(2.6, -7.0)),)),
        _v(4, 0.4, -11.0, "quieto", pasos=(Paso(0.0, 1.0, "quieto", hasta=(0.4, -3.5)),)),
        Actor("npc:escobita", 3.4, -2.6, -30.0, "barrer", prop="escoba"),
        Actor("npc:florista", -3.5, -0.8, 30.0, "brazos_cruzados", prop="canasta"),
    ), (
        Pieza("puesto_flores", -3.9, -2.0, giro=90.0),
    ))

    actores, baranda = _cierre({
        "ciudadano": ("quieto", (Paso(0.5, 1.0, "nuca"),)),
        "periodista": ("quieto", (Paso(0.48, 1.0, "quieto", mira=42.0),)),
        "influencer": ("quieto", (Paso(0.52, 1.0, "quieto", mira=-42.0),)),
        "candidato": ("quieto", (Paso(0.55, 1.0, "cabeza_baja"),)),
    })
    p["n6_cierre"] = Puesta("n6_cierre", "azotea", actores, baranda)

    p["n5_candidatos"] = Puesta("n5_candidatos", "prefeitura", (
        Actor(OCTAVIO, -2.2, 0.6, 0.0, "manos_atras"),
        Actor(ARENAS, 2.2, 0.6, 0.0, "reloj", fase=0.3),
    ), (
        Pieza("ventanas", frente=FRENTE_FACHADA_PREFEITURA),
    ))

    # ===== POR ROL =====
    for final, pre in (("bueno", "b5"), ("malo", "m4"), ("neutro", "n4")):
        p[f"{pre}_ciudadano"] = _ciudadano(f"{pre}_ciudadano", final)
        p[f"{pre}_periodista"] = _periodista(f"{pre}_periodista", final)
        p[f"{pre}_influencer"] = _influencer(f"{pre}_influencer", final)
        p[f"{pre}_candidato"] = _candidato(f"{pre}_candidato", final)
    return p


# Ventana del Morro: un paño de fachada con ventana delante de la pared de verdad (que no tiene hueco), con el ciudadano
# entre las dos, visible de la cintura para arriba.
VENTANA_MORRO = (2.2, -0.62)          # (derecha, frente) del paño
CIUDADANO_MORRO = (2.2, -0.98)


def _ciudadano(pid, final):
    d, f = CIUDADANO_MORRO
    piezas = [Pieza("ventana_morro", VENTANA_MORRO[0], VENTANA_MORRO[1], variante={"bueno": 0, "malo": 1, "neutro": 2}[final],
                    tramo={"bueno": (0.06, 0.26), "malo": (0.5, 0.74), "neutro": None}[final])]
    if final == "bueno":
        prota = Actor("prota:ciudadano", d, f, 0.0, "quieto", (
            Paso(0.06, 0.26, "abrir"), Paso(0.26, 0.34, "apoyado"),
            Paso(0.34, 0.72, "saludar", mira=(4.0, 4.5)), Paso(0.72, 1.0, "apoyado")), fuera_de_calle=True)
        vecinos = (
            _v(0, -4.5, 3.1, "quieto", pasos=(Paso(0.0, 0.42, "quieto", hasta=(0.6, 3.1)),
                                              Paso(0.42, 0.7, "saludar", mira=(d, f)),
                                              Paso(0.7, 1.0, "quieto", hasta=(4.6, 3.1)))),
            _v(1, 7.0, 2.2, "quieto", pasos=(Paso(0.0, 0.44, "quieto", hasta=(3.8, 2.2)),
                                             Paso(0.44, 0.7, "saludar", mira=(d, f)),
                                             Paso(0.7, 1.0, "quieto", hasta=(-1.0, 2.2)))),
        )
        piezas.append(Pieza("banderin_ventana", VENTANA_MORRO[0], VENTANA_MORRO[1] + 0.12, 2.3, medida=1.5))
        return Puesta(pid, "morro", (prota,) + vecinos, tuple(piezas))
    if final == "malo":
        prota = Actor("prota:ciudadano", d, f, 0.0, "apoyado", (
            Paso(0.0, 0.5, "apoyado", mira=-25.0), Paso(0.5, 0.74, "abrir", mira=0.0),
            Paso(0.74, 1.0, "cabeza_baja", hasta=(d, f - 0.12))), fuera_de_calle=True)
        return Puesta(pid, "morro", (prota,), tuple(piezas))
    prota = Actor("prota:ciudadano", d, f, 0.0, "apoyado", (
        Paso(0.15, 0.7, "mirar_lados"), Paso(0.7, 1.0, "apoyado")), fuera_de_calle=True)
    return Puesta(pid, "morro", (prota,), tuple(piezas))


NOTAS = {"bueno": "CIUDAD NOVA\nVOTÓ INFORMADA", "malo": "DESMENTIDO", "neutro": "RESULTADO\nAJUSTADO"}


def _periodista(pid, final):
    piezas = [Pieza("mesa_redaccion", 0.0, 0.75), Pieza("nota", -1.35, 0.9, 1.9, texto=NOTAS[final], tramo=(0.32, 0.56),
                                                          variante={"bueno": 0, "malo": 1, "neutro": 2}[final])]
    prota_pasos = [Paso(0.0, 0.32, "teclear"), Paso(0.32, 0.58, "levantar_nota", mira=-20.0)]
    actores = []
    if final == "bueno":
        prota_pasos.append(Paso(0.58, 1.0, "asentir", mira=-10.0))
        actores += [_v(0, -4.2, 4.6, "quieto", pasos=(Paso(0.42, 0.72, "quieto", hasta=(-2.3, 2.3)),
                                                    Paso(0.72, 1.0, "leer", mira=(-1.35, 0.9)))),
                    _v(1, 3.8, 4.8, "quieto", pasos=(Paso(0.48, 0.8, "quieto", hasta=(-0.9, 2.6)),
                                                   Paso(0.8, 1.0, "leer", mira=(-1.35, 0.9))))]
    elif final == "malo":
        prota_pasos.append(Paso(0.58, 1.0, "cabeza_baja", mira=0.0))
        piezas += list(_papeletas(14, -3.0, 3.0, 1.6, 4.5, 31))
    else:
        prota_pasos.append(Paso(0.58, 1.0, "quieto", mira=-10.0))
        actores += [_v(0, -4.2, 4.4, "quieto", pasos=(Paso(0.4, 0.68, "quieto", hasta=(-2.3, 2.4)),
                                                    Paso(0.68, 1.0, "leer", mira=(-1.35, 0.9)))),
                    _v(1, 3.6, 4.8, "quieto", pasos=(Paso(0.36, 0.6, "quieto", hasta=(0.0, 2.8)),
                                                   Paso(0.6, 0.78, "negar", mira=(-1.35, 0.9)),
                                                   Paso(0.78, 1.0, "quieto", hasta=(4.2, 4.2))))]
    prota = Actor("prota:periodista", 0.0, 0.2, 0.0, "quieto", tuple(prota_pasos))
    return Puesta(pid, "radio", (prota,) + tuple(actores), tuple(piezas))


def _influencer(pid, final):
    piezas = (Pieza("tripode", 0.95, 0.95, giro=225.0, variante={"bueno": 0, "malo": 1, "neutro": 2}[final],
                    tramo=(0.62, 0.8) if final == "malo" else None),
              Pieza("iconos", 0.0, 0.6, 1.6, variante={"bueno": 0, "malo": 1, "neutro": 2}[final]))
    if final == "bueno":
        pasos = (Paso(0.0, 0.5, "hablar"), Paso(0.5, 1.0, "saludar"))
    elif final == "malo":
        pasos = (Paso(0.0, 0.34, "hablar"), Paso(0.34, 0.62, "encogerse"), Paso(0.62, 1.0, "cabeza_baja"))
    else:
        pasos = (Paso(0.0, 0.45, "hablar"), Paso(0.45, 1.0, "mas_o_menos"))
    return Puesta(pid, "directo", (Actor("prota:influencer", 0.0, 0.0, 0.0, "hablar", pasos),), piezas)


def _candidato(pid, final):
    if final == "bueno":
        actores = (Actor(OCTAVIO, 0.0, 0.0, 0.0, "quieto", (
            Paso(0.0, 0.3, "respirar"), Paso(0.3, 0.55, "acomodar_banda"),
            Paso(0.55, 0.92, "dar_mano", mira=(1.1, 0.9)), Paso(0.92, 1.0, "quieto", mira=0.0))),
            _v(0, 3.4, 2.6, "quieto", pasos=(Paso(0.2, 0.5, "quieto", hasta=(1.1, 0.95)),
                                             Paso(0.5, 0.92, "dar_mano", mira=(0.0, 0.0)),
                                             Paso(0.92, 1.0, "aplaudir"))))
        piezas = (Pieza("microfono", 0.0, 0.75),) + tuple(
            Pieza(pz.tipo, pz.derecha - 2.6, pz.frente - 0.9, pz.alto) for pz in _podio())
        return Puesta(pid, "tarima", actores, piezas)
    if final == "malo":
        actores = (Actor(OCTAVIO, 0.0, 0.0, 0.0, "quieto", (Paso(0.12, 0.5, "cabeza_baja"), Paso(0.5, 1.0, "gracias"))),
                   _v(0, -2.7, 2.0, "aplaudir", (0.0, 0.0), fase=0.2),
                   _v(1, 2.5, 1.8, "brazos_cruzados", (0.0, 0.0)),
                   _v(2, 3.5, 3.0, "manos_atras", (0.0, 0.0)))
        return Puesta(pid, "tarima", actores, (Pieza("microfono", 0.0, 0.75),))
    actores = (Actor(OCTAVIO, 0.0, 0.0, 0.0, "reloj", (Paso(0.5, 1.0, "frotar"),)),)
    return Puesta(pid, "tarima", actores, (Pieza("microfono", 0.0, 0.75), Pieza("mesa", 1.3, 0.2),
                                           Pieza("urna", 1.3, 0.2, 0.76)))


PUESTAS = _construir()
_pulidas = {}


# Las puestas que valen ahora: con ALCALDE_FINALES_PULIDOS (final_pulido_calculos.py), las corregidas; si no, las de
# siempre. Las corregidas se calculan una vez.
def vigentes():
    from frontend.final_animado import final_pulido_calculos as pulido
    if not pulido.activo():
        return PUESTAS
    if not _pulidas:
        _pulidas.update(pulido.corregir_puestas(PUESTAS))
    return _pulidas


def ids():
    return tuple(PUESTAS)


def puesta(plano_id):
    """La puesta del plano (KeyError si no hay)."""
    return vigentes()[plano_id]


def actores_del_pool(ids_planos):
    """Ids del pool que hacen falta para esos planos (sin repetir, en orden estable)."""
    vistos = []
    for pid in ids_planos:
        pz = vigentes().get(pid)
        if pz is None:
            continue
        for actor in pz.actores:
            if actor.id not in vistos:
                vistos.append(actor.id)
    return vistos


def a_mundo(ancla, derecha, frente, alto=0.0):
    """(x, z, y_relativa) en el mundo de un punto del marco del ancla (atajo sobre lugares.a_mundo)."""
    from frontend.final_animado import lugares
    x, y, z = lugares.a_mundo(ancla, derecha, alto, frente)
    return x, y, z
