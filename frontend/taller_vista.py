# Vista del taller de Beto con ritmo (Ursina, camera.ui; dentro de EscenaTrabajo). Modelo: backend/logica/taller_ritmo.py.
#   - Arriba, el taller: el personaje del jugador (con el aspecto de su rol, ver ASPECTO_ROL) detrás del banco, con el
#     martillo en alto; sobre el yunque, la pieza del turno (repertorio en backend/datos/piezas_taller.py). La pieza
#     empieza como silueta y se va formando con cada nota; cada fallo le deja una abolladura o grieta oscura.
#   - Cada acierto es un martillazo: el brazo baja, la pieza da un respingo y saltan chispas.
#   - Abajo, el carril: las flechas llegan una tras otra de derecha a izquierda hasta el recuadro amarillo. La que
#     toca se pinta en amarillo cuando está dentro del recuadro; al acertar se encoge en verde, al fallar cae en rojo.
#   - A la derecha del taller, el cartel con la pieza, cuánto lleva forjado y la calidad.
# Las coordenadas son las del marco de EscenaTrabajo (1,18 x 0,86; el juego ocupa y de -0,27 a 0,175).

import math
import random
import zlib

from ursina import Entity, color

from backend.logica import taller_ritmo as tr
from frontend import estilo
from frontend.componentes import destruir_arbol, panel_tinta, rgb
from frontend.trabajo_constantes import NOMBRE_DIRECCION
from frontend.trabajo_dibujos import Capa, _caja, _seguro, _texto, dibujar_flecha

# Taller
FONDO_TALLER = (58, 62, 78)
TABLERO = (78, 84, 102)
MADERA, MADERA_OSCURA = (150, 104, 64), (112, 76, 46)
HIERRO, HIERRO_CLARO = (70, 74, 86), (120, 126, 140)
DELANTAL = (96, 66, 44)
PLATA, NEGRO_GOMA, OXIDO = (196, 200, 210), (38, 38, 44), (60, 44, 40)
ROJO_PINTURA, AZUL_PINTURA = (206, 64, 56), (60, 110, 200)
CHISPA = (255, 214, 90)
Y_TALLER_ARRIBA, Y_TALLER_ABAJO = 0.17, -0.13
X_PERSONAJE = -0.27
HOMBRO = (-0.215, 0.075)
PIEZA = (-0.055, -0.012)            # centro de la pieza sobre el yunque
LADO_PIEZA = 0.085
LARGO_BRAZO, LARGO_MANGO = 0.075, 0.085
ANGULO_ARRIBA, ANGULO_GOLPE, ANGULO_TORCIDO = -128.0, -86.0, -62.0
# Animación del martillazo (s): bajar, quedarse, volver arriba.
T_BAJAR, T_QUIETO, T_SUBIR = 0.07, 0.09, 0.22
DURACION_CHISPAS, N_CHISPAS = 0.38, 7
DURACION_RESPINGO = 0.16
DURACION_ROJO = 0.3

# Carril
Y_CARRIL = -0.2
X_ZONA, X_ENTRADA = -0.42, 0.49
LADO_NOTA = 0.082
DURACION_SALIDA = 0.22

# Cartel
X_CARTEL, Y_CARTEL = 0.34, 0.035
ANCHO_CARTEL, ALTO_CARTEL = 0.4, 0.25


# ---------------------------------------------------------------------------
# Piezas: cada una es una lista ordenada de partes (se dibujan en orden según el progreso). `c` es una Capa, `k` el
# lado de la pieza y `fondo` el color de detrás (para los huecos de ruedas y platos).
# ---------------------------------------------------------------------------

def _rueda_bici(k, fondo):
    partes = [lambda c: c.elipse(NEGRO_GOMA, k, k),
              lambda c: c.elipse(PLATA, k * 0.86, k * 0.86),
              lambda c: c.elipse(fondo, k * 0.76, k * 0.76)]
    partes += [lambda c, a=a: c.rect(PLATA, k * 0.025, k * 0.76, rot=a) for a in (0, 45, 90, 135)]
    partes.append(lambda c: c.elipse(HIERRO_CLARO, k * 0.16, k * 0.16))
    return partes


def _plato(k, fondo):
    partes = [lambda c, a=a: c.rect(HIERRO_CLARO, k * 0.09, k * 1.0, rot=a) for a in range(0, 180, 30)]
    partes += [lambda c: c.elipse(PLATA, k * 0.88, k * 0.88),
               lambda c: c.elipse(fondo, k * 0.56, k * 0.56)]
    partes += [lambda c, a=a: c.rect(PLATA, k * 0.1, k * 0.56, rot=a) for a in (0, 72, 144)]
    partes.append(lambda c: c.elipse(HIERRO, k * 0.18, k * 0.18))
    return partes


def _cuadro(k, fondo):
    t = k * 0.07
    return [lambda c: c.rect(ROJO_PINTURA, t, k * 0.9, (-k * 0.05, -k * 0.02), rot=55),     # tubo diagonal
            lambda c: c.rect(ROJO_PINTURA, k * 0.8, t, (k * 0.05, k * 0.3)),                 # tubo superior
            lambda c: c.rect(ROJO_PINTURA, t, k * 0.8, (k * 0.3, -k * 0.02), rot=-10),       # tubo del sillín
            lambda c: c.rect(ROJO_PINTURA, k * 0.62, t, (-k * 0.02, -k * 0.38)),             # vainas
            lambda c: c.rect(ROJO_PINTURA, t, k * 0.42, (-k * 0.42, k * 0.17), rot=-15),     # pipa
            lambda c: c.elipse(HIERRO_CLARO, k * 0.16, k * 0.16, (k * 0.3, -k * 0.38)),       # eje del pedalier
            lambda c: c.rect(NEGRO_GOMA, k * 0.3, k * 0.08, (k * 0.36, k * 0.46))]            # sillín


def _manillar(k, fondo):
    t = k * 0.08
    return [lambda c: c.rect(PLATA, k * 0.62, t, (0, k * 0.15)),
            lambda c: c.rect(PLATA, k * 0.22, t, (-k * 0.38, k * 0.22), rot=-30),
            lambda c: c.rect(PLATA, k * 0.22, t, (k * 0.38, k * 0.22), rot=30),
            lambda c: c.rect(NEGRO_GOMA, k * 0.2, t * 1.4, (-k * 0.54, k * 0.3), rot=-30),
            lambda c: c.rect(NEGRO_GOMA, k * 0.2, t * 1.4, (k * 0.54, k * 0.3), rot=30),
            lambda c: c.rect(HIERRO_CLARO, t * 1.3, k * 0.5, (0, -k * 0.12)),
            lambda c: c.elipse(HIERRO, k * 0.16, k * 0.16, (0, k * 0.15))]


def _llanta_moto(k, fondo):
    partes = [lambda c: c.elipse(NEGRO_GOMA, k * 1.05, k * 1.05),
              lambda c: c.elipse((70, 70, 78), k * 0.66, k * 0.66),
              lambda c: c.elipse(fondo, k * 0.56, k * 0.56)]
    partes += [lambda c, a=a: c.rect(HIERRO_CLARO, k * 0.08, k * 0.27, (math.sin(math.radians(a)) * k * 0.14,
                                                                       math.cos(math.radians(a)) * k * 0.14), rot=a)
               for a in range(0, 360, 72)]
    partes.append(lambda c: c.elipse(PLATA, k * 0.16, k * 0.16))
    return partes


def _escape(k, fondo):
    return [lambda c: c.rect(HIERRO_CLARO, k * 0.6, k * 0.1, (-k * 0.3, k * 0.18), rot=-20),
            lambda c: c.rect(HIERRO_CLARO, k * 0.3, k * 0.1, (-k * 0.62, k * 0.32), rot=-60),
            lambda c: c.elipse(PLATA, k * 0.75, k * 0.34, (k * 0.2, -k * 0.02), rot=-12),
            lambda c: c.rect(HIERRO, k * 0.05, k * 0.3, (k * 0.05, -k * 0.0), rot=-12),
            lambda c: c.rect(HIERRO, k * 0.05, k * 0.3, (k * 0.25, -k * 0.04), rot=-12),
            lambda c: c.elipse(HIERRO, k * 0.16, k * 0.2, (k * 0.58, -k * 0.1)),
            lambda c: c.elipse(NEGRO_GOMA, k * 0.08, k * 0.11, (k * 0.6, -k * 0.1))]


def _tanque(k, fondo):
    return [lambda c: c.elipse(AZUL_PINTURA, k * 1.0, k * 0.62, (0, -k * 0.05)),
            lambda c: c.elipse(AZUL_PINTURA, k * 0.6, k * 0.5, (-k * 0.12, k * 0.08)),
            lambda c: c.rect(estilo.PAPEL, k * 0.8, k * 0.07, (0, -k * 0.08), rot=-8),
            lambda c: c.rect(estilo.COLOR_ACENTO, k * 0.7, k * 0.04, (0, -k * 0.16), rot=-8),
            lambda c: c.elipse(PLATA, k * 0.18, k * 0.1, (-k * 0.1, k * 0.32)),
            lambda c: c.elipse(HIERRO, k * 0.1, k * 0.06, (-k * 0.1, k * 0.34)),
            lambda c: c.rect(HIERRO, k * 0.5, k * 0.06, (0, -k * 0.37))]


def _guardabarros(k, fondo):
    partes = []
    for i in range(7):
        a = math.radians(-75 + 25 * i)
        x, y = math.sin(a) * k * 0.46, math.cos(a) * k * 0.46 - k * 0.15
        partes.append(lambda c, x=x, y=y, a=a: c.rect(ROJO_PINTURA, k * 0.22, k * 0.11, (x, y), rot=math.degrees(a)))
    partes += [lambda c: c.rect(PLATA, k * 0.05, k * 0.3, (-k * 0.4, -k * 0.3), rot=10),
               lambda c: c.rect(PLATA, k * 0.05, k * 0.3, (k * 0.4, -k * 0.3), rot=-10),
               lambda c: c.rect(estilo.PAPEL, k * 0.3, k * 0.05, (0, k * 0.33))]
    return partes


DIBUJOS = {"rueda_bici": _rueda_bici, "plato": _plato, "cuadro": _cuadro, "manillar": _manillar,
           "llanta_moto": _llanta_moto, "escape": _escape, "tanque": _tanque, "guardabarros": _guardabarros}


# Capa que pinta todo de un solo color (la silueta de lo que falta por forjar).
class _CapaSilueta(Capa):

    def __init__(self, padre, tono, z=-0.002):
        super().__init__(padre, z)
        self.tono = tono

    def forma(self, modelo, tono, escala, pos=(0, 0), rot=0):
        return super().forma(modelo, self.tono, escala, pos, rot)


# Dibuja la pieza `pieza_id` en `pos`: las primeras `progreso` (0..1) de sus partes de color, el resto en silueta, y
# `defectos` marcas de golpes malos. Devuelve el contenedor.
def dibujar_pieza(padre, pieza_id, pos, k, progreso=1.0, defectos=0, fondo=FONDO_TALLER, z=-0.004):
    contenedor = Entity(parent=padre, position=(pos[0], pos[1], z))
    partes = DIBUJOS.get(pieza_id, _rueda_bici)(k, fondo)
    hechas = min(len(partes), int(math.floor(progreso * len(partes) + 1e-6)))
    silueta = color.rgba32(*estilo.PAPEL, 40)
    capa_s = _CapaSilueta(contenedor, silueta, z=0)
    for parte in partes[hechas:]:
        parte(capa_s)
    capa = Capa(contenedor, z=-0.01)
    for parte in partes[:hechas]:
        parte(capa)
    azar = random.Random(zlib.crc32(pieza_id.encode()))
    marcas = Capa(contenedor, z=-0.02)
    for _ in range(defectos):
        x, y = azar.uniform(-0.38, 0.38) * k, azar.uniform(-0.38, 0.38) * k
        marcas.elipse(OXIDO, k * 0.13, k * 0.09, (x, y), rot=azar.uniform(0, 180))
        marcas.rect(estilo.TINTA, k * 0.16, k * 0.025, (x + k * 0.04, y + k * 0.02), rot=azar.uniform(-60, 60))
    return contenedor


# ---------------------------------------------------------------------------
# El juego
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# El trabajador: el mismo aspecto que el modelo 3D de cada rol (assets/modelos/personajes/*.glb, ver MODELOS_3D.md):
#   ciudadano  - sin camisa, pelo corto negro (ciudadano.glb);
#   influencer - afro, top verde con la bandera de Brasil, aros y pulseras doradas (brasilena.glb);
#   periodista - camisa verde clara con bolsillo y mangas remangadas, gafas, pelo castaño (periodista.glb);
#   candidato  - esmoquin blanco, pajarita negra, bigote, pelo negro peinado hacia atrás (smoking.glb).
# Todos llevan el delantal de cuero del taller encima.
# ---------------------------------------------------------------------------

ORO = (240, 196, 64)
ASPECTO_ROL = {
    "ciudadano": dict(piel=(176, 128, 96), pelo=(34, 28, 26), torso=None, manga=None, antebrazo=None, ancho=0.15),
    "influencer": dict(piel=(122, 84, 60), pelo=(52, 38, 30), torso=(52, 186, 116), manga=None, antebrazo=None,
                       ancho=0.13, pulsera=ORO),
    "periodista": dict(piel=(226, 192, 160), pelo=(86, 52, 30), torso=(178, 208, 172), manga=(178, 208, 172),
                       antebrazo=None, ancho=0.15),
    "candidato": dict(piel=(146, 98, 54), pelo=(24, 20, 26), torso=(236, 234, 228), manga=(236, 234, 228),
                      antebrazo=(236, 234, 228), ancho=0.16),
}
for _a in ASPECTO_ROL.values():         # sin ropa en esa parte = la piel
    _a["torso"] = _a["torso"] or _a["piel"]
    _a["manga"] = _a["manga"] or _a["piel"]
    _a["antebrazo"] = _a["antebrazo"] or _a["piel"]


def _oscuro(tono, f=0.75):
    return tuple(int(v * f) for v in tono)


# Dibuja al trabajador del rol `rol` (de cintura para arriba, detrás del banco) con el centro del cuerpo en x.
def dibujar_trabajador(p, rol, x):
    asp = ASPECTO_ROL.get(rol, ASPECTO_ROL["ciudadano"])
    piel, pelo, torso, ancho = asp["piel"], asp["pelo"], asp["torso"], asp["ancho"]
    # Afro detrás de la cabeza.
    if rol == "influencer":
        for dx, dy, r in ((-0.04, 0.17, 0.06), (0.0, 0.185, 0.065), (0.035, 0.17, 0.055), (-0.05, 0.135, 0.05),
                          (0.045, 0.135, 0.045), (-0.03, 0.105, 0.04)):
            p.elipse(pelo, r, r, (x + dx, dy))
    # Torso y hombros.
    p.rect(torso, ancho, 0.2, (x, -0.015))
    p.elipse(torso, ancho, 0.06, (x, 0.08))
    if rol == "ciudadano":                                   # pecho al aire
        p.rect(_oscuro(piel), 0.04, 0.005, (x - 0.035, 0.035), rot=-12)
        p.rect(_oscuro(piel), 0.04, 0.005, (x + 0.035, 0.035), rot=12)
    elif rol == "influencer":                                # top corto con la bandera
        p.rect(piel, ancho, 0.07, (x, -0.08))
        p.rect((250, 215, 60), ancho, 0.008, (x, -0.044))
        p.rect((250, 215, 60), 0.026, 0.026, (x - 0.042, 0.045), rot=45)
        p.elipse((40, 80, 180), 0.016, 0.016, (x - 0.042, 0.045))
    elif rol == "periodista":                                # bolsillo y botones
        p.rect(_oscuro(torso, 0.85), 0.028, 0.026, (x - 0.045, 0.045))
        p.rect(_oscuro(torso, 0.7), 0.03, 0.004, (x - 0.045, 0.058))
        for dy in (0.07, 0.045):
            p.elipse(estilo.PAPEL, 0.007, 0.007, (x + 0.004, dy))
    elif rol == "candidato":                                 # camisa, solapas y pajarita
        p.forma("triangulo", estilo.PAPEL, (0.05, 0.07), (x, 0.065), rot=180)
        p.rect(_oscuro(torso, 0.7), 0.006, 0.075, (x - 0.02, 0.06), rot=-18)
        p.rect(_oscuro(torso, 0.7), 0.006, 0.075, (x + 0.02, 0.06), rot=18)
    # Delantal de cuero.
    p.rect(DELANTAL, 0.1, 0.15, (x + 0.005, -0.05))
    p.rect(DELANTAL, 0.012, 0.07, (x - 0.035, 0.045), rot=10)
    p.rect(DELANTAL, 0.012, 0.07, (x + 0.045, 0.045), rot=-10)
    # Cuello y cabeza.
    p.rect(piel, 0.04, 0.03, (x, 0.1))
    p.elipse(piel, 0.09, 0.095, (x, 0.13))
    if rol == "candidato":                                   # pajarita bajo la barbilla
        p.forma("triangulo", estilo.TINTA, (0.022, 0.018), (x - 0.011, 0.076), rot=90)
        p.forma("triangulo", estilo.TINTA, (0.022, 0.018), (x + 0.011, 0.076), rot=-90)
        p.elipse(estilo.TINTA, 0.009, 0.009, (x, 0.076))
    if rol == "ciudadano":                                   # pelo corto
        p.elipse(pelo, 0.094, 0.05, (x - 0.002, 0.162))
        p.rect(pelo, 0.03, 0.03, (x - 0.035, 0.145))
    elif rol == "periodista":                                # pelo corto con raya
        p.elipse(pelo, 0.096, 0.055, (x - 0.004, 0.16))
        p.rect(pelo, 0.034, 0.034, (x - 0.034, 0.142))
        p.rect(_oscuro(pelo), 0.03, 0.004, (x - 0.012, 0.178), rot=-10)
    elif rol == "candidato":                                 # peinado hacia atrás
        p.elipse(pelo, 0.098, 0.045, (x - 0.008, 0.165))
        p.rect(pelo, 0.04, 0.04, (x - 0.032, 0.148))
    elif rol == "influencer":                                # aros
        p.elipse(ORO, 0.016, 0.016, (x - 0.042, 0.11))
    # Cara mirando a la pieza (a la derecha).
    p.elipse(estilo.TINTA, 0.011, 0.014, (x + 0.012, 0.13))
    p.elipse(estilo.TINTA, 0.011, 0.014, (x + 0.034, 0.13))
    if rol == "periodista":                                  # gafas
        for ox in (0.012, 0.034):
            p.elipse(estilo.TINTA, 0.024, 0.022, (x + ox, 0.131))
            p.elipse((215, 230, 240), 0.017, 0.015, (x + ox, 0.131))
            p.elipse(estilo.TINTA, 0.008, 0.01, (x + ox, 0.13))
        p.rect(estilo.TINTA, 0.01, 0.003, (x + 0.023, 0.134))
    if rol == "candidato":                                   # bigote
        p.rect(estilo.TINTA, 0.03, 0.008, (x + 0.024, 0.114))
    boca = (200, 80, 100) if rol == "influencer" else estilo.TINTA
    p.rect(boca, 0.022, 0.005 if rol != "influencer" else 0.008, (x + 0.024, 0.104))
    # Brazo izquierdo apoyado en el banco.
    p.rect(asp["manga"], 0.04, 0.07, (x - 0.078, 0.04), rot=12)
    p.rect(asp["antebrazo"], 0.035, 0.065, (x - 0.088, -0.015), rot=6)
    if asp.get("pulsera"):
        p.rect(asp["pulsera"], 0.04, 0.008, (x - 0.09, -0.04), rot=6)
    p.elipse(piel, 0.035, 0.035, (x - 0.09, -0.055))


class JuegoTaller:

    # padre: Entity del juego (EscenaTrabajo.juego). turno: TurnoRitmo. jugador: el que trabaja (para su color).
    def __init__(self, padre, turno, jugador=None):
        self.padre, self.turno = padre, turno
        self.raiz = Entity(parent=padre)
        self._notas = {}               # indice -> (entidad, estado pintado)
        self._saliendo = []            # [entidad, segundos, tipo]
        self._chispas = []             # [entidad, vx, vy, segundos]
        self._golpe = None             # segundos desde que empezó el martillazo (o None)
        self._angulo_golpe = ANGULO_GOLPE
        self._respingo = 0.0
        self._rojo = 0.0
        self._t = 0.0
        self._firma_pieza = None
        self._pieza = None
        self.rol = getattr(jugador, "rol", None) if getattr(jugador, "rol", None) in ASPECTO_ROL else "ciudadano"
        self.aspecto = ASPECTO_ROL[self.rol]
        self._construir_taller()
        self._construir_carril()
        self._construir_cartel()
        self._pintar_pieza()

    # -- Construcción --

    def _construir_taller(self):
        r = self.raiz
        alto = Y_TALLER_ARRIBA - Y_TALLER_ABAJO
        _caja(r, 1.08, alto, FONDO_TALLER, (0, (Y_TALLER_ARRIBA + Y_TALLER_ABAJO) / 2), 8, -0.001)
        # Tablero de herramientas y una rueda colgada al fondo.
        c = Capa(r, z=-0.002)
        c.rect(TABLERO, 0.3, 0.17, (-0.46 + 0.15, 0.06))
        for i, (x, y, rot) in enumerate(((-0.4, 0.09, 20), (-0.34, 0.05, -15), (-0.25, 0.08, 70))):
            c.rect(HIERRO_CLARO, 0.012, 0.09, (x, y), rot=rot)
            c.elipse(HIERRO_CLARO, 0.026, 0.026, (x + math.sin(math.radians(rot)) * 0.045,
                                                   y + math.cos(math.radians(rot)) * 0.045))
        c.elipse(NEGRO_GOMA, 0.11, 0.11, (0.1, 0.1))
        c.elipse(FONDO_TALLER, 0.07, 0.07, (0.1, 0.1))
        # Personaje (detrás del banco), con el aspecto de su rol.
        dibujar_trabajador(Capa(r, z=-0.006), self.rol, X_PERSONAJE)
        # Banco y yunque (delante del personaje).
        b = Capa(r, z=-0.012)
        b.rect(MADERA, 0.66, 0.024, (-0.13, -0.106))
        b.rect(MADERA_OSCURA, 0.64, 0.024, (-0.13, -0.118))
        yx, yy = PIEZA[0], PIEZA[1] - LADO_PIEZA / 2
        b.rect(HIERRO, 0.1, 0.018, (yx, -0.094))
        b.rect(HIERRO, 0.045, 0.03, (yx, yy - 0.032))
        b.rect(HIERRO_CLARO, 0.15, 0.022, (yx, yy - 0.011))
        b.forma("triangulo", HIERRO_CLARO, (0.022, 0.05), (yx + 0.098, yy - 0.011), rot=90)
        # Brazo del martillo: pivote en el hombro; el brazo cuelga hacia -y, luego mano, mango y cabeza.
        self.brazo = Entity(parent=r, position=(HOMBRO[0], HOMBRO[1], -0.02))
        a = Capa(self.brazo, z=0)
        asp = self.aspecto
        a.rect(asp["manga"], 0.042, LARGO_BRAZO * 0.55, (0, -LARGO_BRAZO * 0.275))
        a.rect(asp["antebrazo"], 0.036, LARGO_BRAZO * 0.5, (0, -LARGO_BRAZO * 0.72))
        if asp.get("pulsera"):
            a.rect(asp["pulsera"], 0.04, 0.008, (0, -LARGO_BRAZO * 0.88))
        a.rect(MADERA_OSCURA, 0.014, LARGO_MANGO, (0, -LARGO_BRAZO - LARGO_MANGO / 2 + 0.01))
        a.elipse(asp["piel"], 0.034, 0.034, (0, -LARGO_BRAZO))
        largo = LARGO_BRAZO + LARGO_MANGO
        a.rect(HIERRO, 0.055, 0.03, (-0.018, -largo))
        a.rect(HIERRO_CLARO, 0.012, 0.03, (-0.046, -largo))
        self.brazo.rotation_z = ANGULO_ARRIBA
        self.capa_pieza = Entity(parent=r, position=(PIEZA[0], PIEZA[1], -0.008))
        self.capa_chispas = Entity(parent=r, z=-0.03)

    def _construir_carril(self):
        r = self.raiz
        _caja(r, 1.08, 0.106, estilo.TINTA, (0, Y_CARRIL), 8, -0.001)
        _caja(r, 1.06, 0.088, estilo.COLOR_BARRA_FONDO, (0, Y_CARRIL), 6, -0.002)
        _caja(r, LADO_NOTA + 0.026, LADO_NOTA + 0.026, estilo.COLOR_ACENTO, (X_ZONA, Y_CARRIL), 8, -0.003)
        _caja(r, LADO_NOTA + 0.01, LADO_NOTA + 0.01, estilo.COLOR_BARRA_FONDO, (X_ZONA, Y_CARRIL), 6, -0.004)
        self.capa_notas = Entity(parent=r, z=-0.01)

    def _construir_cartel(self):
        r = self.raiz
        cartel = panel_tinta(r, ANCHO_CARTEL, ALTO_CARTEL, tono=estilo.COLOR_TARJETA, radio_px=estilo.RADIO_TARJETA_PX,
                             position=(X_CARTEL, Y_CARTEL), z=-0.005)
        izq = -ANCHO_CARTEL / 2 + 0.02
        _texto(cartel, "FABRICANDO", 12, estilo.COLOR_TEXTO_TENUE, (izq, 0.095), (-0.5, 0), z=-0.01)
        _texto(cartel, self.turno.pieza.nombre, 19, estilo.COLOR_ACENTO, (izq, 0.062), (-0.5, 0), negrita=True,
               z=-0.01)
        self.t_forjado = _texto(cartel, "", 14, estilo.COLOR_TEXTO, (izq, 0.022), (-0.5, 0), z=-0.01)
        ancho = ANCHO_CARTEL - 0.04
        _caja(cartel, ancho, 0.02, estilo.TINTA, (0, -0.005), 4, -0.01)
        self.barra_forjado = Entity(parent=cartel, model="quad", color=rgb(estilo.COLOR_BARRA_ALTO), origin=(-0.5, 0),
                                    scale=(0.0001, 0.014), position=(izq + 0.003, -0.005, -0.012))
        self._ancho_barra = ancho - 0.006
        self.t_calidad = _texto(cartel, "", 16, estilo.COLOR_TEXTO, (izq, -0.045), (-0.5, 0), negrita=True, z=-0.01)
        self.t_siguiente = _texto(cartel, "", 14, estilo.COLOR_TEXTO_TENUE, (izq, -0.09), (-0.5, 0), z=-0.01)

    # -- Pieza --

    def _pintar_pieza(self):
        t = self.turno
        firma = (round(t.progreso(), 4), t.errores())
        if firma == self._firma_pieza:
            return
        self._firma_pieza = firma
        if self._pieza is not None:
            destruir_arbol(self._pieza)
        self._pieza = dibujar_pieza(self.capa_pieza, t.pieza.id, (0, 0), LADO_PIEZA, firma[0], firma[1], z=0)

    # -- Notas --

    def _tile(self, direccion, tono, tinta):
        tile = panel_tinta(self.capa_notas, LADO_NOTA, LADO_NOTA, tono=tono, radio_px=estilo.RADIO_TARJETA_PX,
                           borde_px=estilo.GROSOR_BORDE_DENSO_PX, z=0)
        dibujar_flecha(tile, direccion, tinta, LADO_NOTA * 0.8)
        return tile

    def _x_nota(self, posicion):
        return X_ZONA + posicion * (X_ENTRADA - X_ZONA)

    def _pintar_notas(self):
        t = self.turno
        siguiente = t.siguiente()
        visibles = set()
        for nota, posicion in t.notas_en_carril():
            visibles.add(nota.indice)
            activa = nota is siguiente and t.en_ventana(nota)
            entidad, pintada = self._notas.get(nota.indice, (None, None))
            if entidad is None or pintada != activa:
                if entidad is not None:
                    destruir_arbol(entidad)
                tono, tinta = (estilo.COLOR_ACENTO, estilo.TINTA) if activa else (estilo.COLOR_TARJETA, estilo.PAPEL)
                entidad = self._tile(nota.direccion, tono, tinta)
                self._notas[nota.indice] = (entidad, activa)
            entidad.position = (self._x_nota(posicion), Y_CARRIL, -0.002 if activa else 0)
        for indice in [i for i in self._notas if i not in visibles]:
            entidad, _ = self._notas.pop(indice)
            destruir_arbol(entidad)

    # -- Eventos del turno --

    # Aplica los eventos de TurnoRitmo.sacar_eventos(). Devuelve el texto de aviso del último (o None) y si fue bueno.
    def eventos(self, eventos):
        aviso = None
        for tipo, nota in eventos:
            x = self._x_nota(max(-tr.SALIDA_VISIBLE, min(1.0, self.turno.posicion(nota))))
            entidad, _ = self._notas.pop(nota.indice, (None, None))
            if entidad is not None:
                destruir_arbol(entidad)
            if tipo == tr.ACIERTO:
                tile = self._tile(nota.direccion, estilo.COLOR_BARRA_ALTO, estilo.TINTA)
                self._martillazo(ANGULO_GOLPE)
                aviso = ("¡Buen golpe!", True)
                self._sonar("aterrizaje", 0.9, 1.7)
            else:
                tile = self._tile(nota.direccion, estilo.ESTADO_ERROR, estilo.PAPEL)
                self._rojo = DURACION_ROJO
                if tipo == tr.FALLO:
                    self._martillazo(ANGULO_TORCIDO)
                    aviso = ("Golpe torcido: esa no era la flecha. La pieza se abolla.", False)
                else:
                    aviso = ("¡Se te pasó! La pieza queda con un defecto.", False)
                self._sonar("clic_ui", 0.9, 0.55)
            tile.position = (x, Y_CARRIL, -0.003)
            self._saliendo.append([tile, DURACION_SALIDA, tipo])
        return aviso

    def _martillazo(self, angulo):
        self._golpe = 0.0
        self._angulo_golpe = angulo
        if angulo == ANGULO_GOLPE:
            self._respingo = DURACION_RESPINGO
            self._soltar_chispas()

    def _soltar_chispas(self):
        cx, cy = PIEZA[0], PIEZA[1] + LADO_PIEZA * 0.45
        for i in range(N_CHISPAS):
            angulo = math.radians(random.uniform(-80, 80))
            rapidez = random.uniform(0.25, 0.5)
            e = Entity(parent=self.capa_chispas, model="quad", color=rgb(CHISPA), scale=(0.008, 0.008),
                       position=(cx, cy, 0))
            self._chispas.append([e, math.sin(angulo) * rapidez, math.cos(angulo) * rapidez, DURACION_CHISPAS])

    @staticmethod
    def _sonar(nombre, volumen, pitch):
        try:
            from frontend import audio
            audio.obtener().efecto(nombre, volumen, pitch)
        except Exception:
            pass

    # -- Cada fotograma --

    def animar(self, dt):
        self._t += dt
        # Brazo: martillazo en curso o reposo con el martillo en alto (balanceo suave).
        if self._golpe is not None:
            self._golpe += dt
            g = self._golpe
            if g < T_BAJAR:
                angulo = ANGULO_ARRIBA + (self._angulo_golpe - ANGULO_ARRIBA) * (g / T_BAJAR) ** 2
            elif g < T_BAJAR + T_QUIETO:
                angulo = self._angulo_golpe
            elif g < T_BAJAR + T_QUIETO + T_SUBIR:
                f = (g - T_BAJAR - T_QUIETO) / T_SUBIR
                angulo = self._angulo_golpe + (ANGULO_ARRIBA - self._angulo_golpe) * (1 - (1 - f) ** 2)
            else:
                self._golpe = None
                angulo = ANGULO_ARRIBA
        else:
            angulo = ANGULO_ARRIBA + 4 * math.sin(self._t * 3.0)
        self.brazo.rotation_z = angulo
        # Respingo de la pieza y tinte rojo tras un fallo.
        self._respingo = max(0.0, self._respingo - dt)
        self.capa_pieza.scale = 1 + 0.12 * (self._respingo / DURACION_RESPINGO)
        self._rojo = max(0.0, self._rojo - dt)
        self.capa_pieza.x = PIEZA[0] + (0.006 * math.sin(self._t * 70) if self._rojo > 0 else 0)
        # Chispas: vuelan, caen y se apagan.
        for chispa in list(self._chispas):
            e, vx, vy, resta = chispa
            chispa[3] = resta - dt
            chispa[2] = vy - 1.4 * dt
            e.x += vx * dt
            e.y += chispa[2] * dt
            e.scale = 0.008 * max(0.0, chispa[3] / DURACION_CHISPAS) + 0.001
            if chispa[3] <= 0:
                destruir_arbol(e)
                self._chispas.remove(chispa)
        # Notas que salen: el acierto se encoge, el fallo cae.
        for saliendo in list(self._saliendo):
            e, resta, tipo = saliendo
            saliendo[1] = resta - dt
            f = max(0.0, saliendo[1] / DURACION_SALIDA)
            if tipo == tr.ACIERTO:
                e.scale = 0.4 + 0.8 * f
            else:
                e.y -= 0.25 * dt
                e.scale = 0.6 + 0.4 * f
            if saliendo[1] <= 0:
                destruir_arbol(e)
                self._saliendo.remove(saliendo)

    def refrescar(self):
        t = self.turno
        self._pintar_pieza()
        self._pintar_notas()
        progreso = t.progreso()
        self.barra_forjado.scale_x = max(0.0001, self._ancho_barra * progreso)
        self._poner(self.t_forjado, f"Forjado: {round(progreso * 100)} %")
        calidad = t.calidad()
        self._poner(self.t_calidad, f"Calidad: {round(calidad * 100)} % ({tr.etiqueta_calidad(calidad)})")
        self.t_calidad.color = rgb(estilo.rgb_por_valor(calidad * 100))
        siguiente = t.siguiente()
        self._poner(self.t_siguiente, "" if siguiente is None else
                    f"Siguiente: {NOMBRE_DIRECCION[siguiente.direccion]}")

    @staticmethod
    def _poner(texto, cadena):
        if texto.text != cadena:
            texto.text = _seguro(cadena)

    def destruir(self):
        destruir_arbol(self.raiz)
