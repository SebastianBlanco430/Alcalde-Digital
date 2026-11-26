# Taller de Beto en 3D (Ursina; dentro de EscenaTrabajo, motor RITMO). Bandera ALCALDE_TALLER3D (ver
# frontend/taller3d_calculos.py); con =0 la escena usa el taller 2D de siempre (frontend/taller_vista.JuegoTaller).
#   - Fondo: un taller de favela hecho por código (ladrillo, chapa, hormigón con manchas de aceite, tablero de
#     herramientas, estantería con neumáticos y latas, bicicleta apoyada, bombilla cálida), en UNA malla con sombras.
#   - El personaje del jugador (el modelo 3D de su rol, como en el mundo) está detrás del banco y forja la pieza a
#     martillazos: la mano derecha (IK de frontend/minijuegos_3d/poses_3d) sigue la curva del golpe y sostiene el martillo.
#   - La pieza del turno (frontend/taller3d_piezas.py) está sobre el banco: se forma parte a parte y su acabado sigue a la
#     calidad (prístina con brillo, o deforme, abollada y oxidada).
#   - Cámara fija en tercera persona, 3/4 por detrás del hombro (CamaraMinijuego guarda y devuelve la de Ursina).
# Lo 2D que se queda (heredado de JuegoTaller): el carril de flechas, el cartel con forjado/calidad, los avisos y, en la
# escena, el tiempo, los aciertos y el panel de resultado. La lógica del turno es la de siempre (TurnoRitmo).
# El set vive en `scene` (el mundo está desactivado mientras dura el turno); cerrar_3d() lo deshace todo.

import math
import random
import sys

from ursina import Entity, color, scene
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader, unlit_shader

from backend.logica import taller_ritmo as tr
from frontend import estilo
from frontend import taller3d_calculos as tc
from frontend import taller3d_piezas as tp
from frontend.componentes import destruir_arbol, rgb
from frontend.props_mundo import Malla, anillo, caja, prisma
from frontend.taller_vista import ANGULO_GOLPE, DURACION_SALIDA, JuegoTaller

# Medidas del taller (m). El personaje mira a +z, hacia el banco y la pared del fondo.
ANCHO, FONDO_SALA, ALTO_SALA = 5.2, 4.6, 2.8
Z_FONDO, Z_FRENTE = 1.9, -2.7
Z_BANCO, ALTO_BANCO = 0.55, 0.86
# (x, z, rumbo)
PERSONAJE = (-0.32, -0.12, 0.0)
# sobre el banco, a la derecha del personaje
PIEZA = (0.12, ALTO_BANCO + 0.03, 0.42)
ESCALA_PIEZA = 0.36
TOMA = {"position": (1.35, 2.1, -1.95), "target": (0.2, 1.02, 0.48), "fov": 44}
# Colores del taller (paleta cálida de la favela).
LADRILLO, MORTERO = (164, 84, 60), (196, 170, 146)
REVOQUE, HORMIGON, ACEITE = (214, 192, 152), (124, 120, 114), (70, 66, 64)
CHAPA_A, CHAPA_B = (128, 134, 140), (104, 110, 118)
MADERA, MADERA_OSCURA = (150, 104, 64), (104, 70, 44)
HIERRO, TABLERO = (70, 74, 86), (176, 140, 96)
GOMA, CIELO = (36, 36, 42), (150, 205, 235)
BOMBILLA = (255, 226, 150)
CHISPA = (255, 214, 90)
N_CHISPAS, DURACION_CHISPAS = 9, 0.42
DURACION_RESPINGO = 0.16
# grados que puede inclinarse el torso para llegar a la pieza
INCLINACION_MAX = 10.0
# m que sube la mano sobre la pieza con el martillo en alto
ALTURA_MARTILLO = 0.55


def _taller():
    """Malla del taller entero (paredes, techo, suelo y muebles): una sola llamada de dibujo."""
    m = Malla()
    ax = ANCHO / 2
    # suelo de hormigón con manchas de aceite
    m.agregar(caja(), (0, -0.05, (Z_FONDO + Z_FRENTE) / 2), (ANCHO, 0.1, FONDO_SALA), 0, HORMIGON, (1, 1), 0.08)
    for x, z, r in ((-0.7, -0.4, 0.5), (1.1, 0.2, 0.35), (0.4, -1.4, 0.6)):
        m.agregar(prisma(14), (x, 0.0, z), (r, 0.004, r * 0.7), 20, ACEITE, (1, 1))
    # pared del fondo de ladrillo (hiladas de mortero) y paredes laterales de revoque
    m.agregar(caja(), (0, ALTO_SALA / 2, Z_FONDO + 0.05), (ANCHO, ALTO_SALA, 0.1), 0, LADRILLO, (0.85, 1.05), 0.12)
    for k in range(15):
        m.agregar(caja(), (0, 0.09 + 0.185 * k, Z_FONDO - 0.002), (ANCHO, 0.018, 0.01), 0, MORTERO, (1, 1))
    for lado in (-1, 1):
        m.agregar(caja(), (lado * (ax + 0.05), ALTO_SALA / 2, (Z_FONDO + Z_FRENTE) / 2), (0.1, ALTO_SALA, FONDO_SALA),
                  0, REVOQUE, (0.8, 1.05), 0.1)
        m.agregar(caja(), (lado * (ax - 0.002), 0.5, (Z_FONDO + Z_FRENTE) / 2), (0.01, 1.0, FONDO_SALA), 0,
                  (150, 112, 82), (1, 1))
    # techo de chapa ondulada (tiras de dos tonos) y viga
    for k in range(13):
        x = -ax + 0.2 + 0.4 * k
        m.agregar(caja(), (x, ALTO_SALA + 0.03, (Z_FONDO + Z_FRENTE) / 2), (0.4, 0.04, FONDO_SALA), 0,
                  CHAPA_A if k % 2 else CHAPA_B, (1, 1))
    m.agregar(caja(), (0, ALTO_SALA - 0.1, 0.4), (ANCHO, 0.14, 0.12), 0, MADERA_OSCURA, (1, 1))
    # ventana en la pared izquierda (cielo de la tarde)
    m.agregar(caja(), (-ax + 0.01, 1.6, -0.6), (0.04, 0.9, 1.2), 0, CIELO, (1, 1.1))
    for dz in (-0.6, 0.0, 0.6):
        m.agregar(caja(), (-ax + 0.03, 1.6, -0.6 + dz), (0.05, 0.94, 0.05), 0, MADERA_OSCURA, (1, 1))
    _banco(m)
    _tablero(m)
    _estanteria(m)
    _bicicleta(m)
    return m


def _banco(m):
    m.agregar(caja(), (0, ALTO_BANCO - 0.03, Z_BANCO), (2.4, 0.06, 0.72), 0, MADERA, (0.85, 1.05), 0.1)
    for x in (-1.1, 1.1):
        for z in (Z_BANCO - 0.3, Z_BANCO + 0.3):
            m.agregar(caja(), (x, (ALTO_BANCO - 0.06) / 2, z), (0.08, ALTO_BANCO - 0.06, 0.08), 0, MADERA_OSCURA)
    m.agregar(caja(), (0, 0.22, Z_BANCO), (2.3, 0.04, 0.66), 0, MADERA_OSCURA)
    # en el estante de abajo: caja de herramientas y bidón
    m.agregar(caja(), (-0.6, 0.36, Z_BANCO), (0.5, 0.24, 0.3), 0, (196, 58, 50))
    m.agregar(prisma(14), (0.7, 0.24, Z_BANCO), (0.3, 0.42, 0.3), 0, (46, 104, 72))
    # tornillo de banco a la izquierda y yunque pequeño
    m.agregar(caja(), (-0.85, ALTO_BANCO + 0.08, Z_BANCO - 0.2), (0.16, 0.16, 0.22), 0, HIERRO)
    m.agregar(caja(), (-0.85, ALTO_BANCO + 0.12, Z_BANCO - 0.36), (0.2, 0.04, 0.04), 0, HIERRO)
    m.agregar(caja(), (PIEZA[0], ALTO_BANCO + 0.012, PIEZA[2]), (0.46, 0.024, 0.4), 0, (88, 92, 104))
    # trapo y llaves sueltas sobre el banco
    m.agregar(caja(), (0.75, ALTO_BANCO + 0.01, Z_BANCO + 0.1), (0.3, 0.02, 0.22), 25, (60, 110, 180))
    m.agregar(caja(), (0.55, ALTO_BANCO + 0.01, Z_BANCO - 0.15), (0.04, 0.02, 0.26), 60, (180, 186, 196))


def _tablero(m):
    """Tablero de herramientas en la pared del fondo, con siluetas pintadas y las herramientas colgadas."""
    y0, z = 1.75, Z_FONDO - 0.03
    m.agregar(caja(), (0, y0, z), (1.9, 0.9, 0.03), 0, TABLERO, (0.9, 1.05), 0.06)
    herramientas = ((-0.75, 0.0, 0.05, 0.5, HIERRO), (-0.55, 0.05, 0.04, 0.42, (190, 196, 206)),
                    (-0.35, -0.02, 0.05, 0.38, (196, 58, 50)), (-0.12, 0.08, 0.36, 0.05, HIERRO),
                    (0.2, 0.0, 0.04, 0.48, MADERA_OSCURA), (0.42, 0.05, 0.04, 0.4, (220, 180, 60)),
                    (0.62, -0.05, 0.05, 0.32, (190, 196, 206)), (0.8, 0.02, 0.04, 0.44, HIERRO))
    for x, dy, sx, sy, tono in herramientas:
        m.agregar(caja(), (x, y0 + dy, z - 0.025), (sx, sy, 0.025), 0, tono)
        m.agregar(caja(), (x, y0 + dy + sy / 2 + 0.03, z - 0.02), (0.03, 0.03, 0.03), 0, HIERRO)
    # martillo grande y calendario
    m.agregar(caja(), (0.2, y0 + 0.27, z - 0.04), (0.16, 0.07, 0.05), 0, HIERRO)
    m.agregar(caja(), (1.65, 1.7, z), (0.42, 0.55, 0.01), 0, (240, 236, 224))
    m.agregar(caja(), (1.65, 1.88, z - 0.006), (0.42, 0.16, 0.01), 0, (200, 60, 56))


def _estanteria(m):
    """Estantería en la pared derecha con neumáticos y latas de pintura."""
    x = ANCHO / 2 - 0.25
    for k in range(4):
        m.agregar(caja(), (x, 0.3 + 0.55 * k, -0.2), (0.4, 0.04, 1.4), 0, MADERA_OSCURA)
    for z in (-0.88, 0.48):
        m.agregar(caja(), (x, 1.0, z), (0.42, 2.0, 0.04), 0, MADERA_OSCURA)
    for k, z in enumerate((-0.6, -0.2, 0.2)):
        m.agregar(anillo(18, 0.5, 0.3), (x, 0.32, z), (0.5, 0.16, 0.5), 0, GOMA, (0.9, 1.1), 0, 90)
    for k, z in enumerate((-0.7, -0.45, -0.2, 0.1, 0.35)):
        tono = ((220, 180, 60), (60, 120, 196), (200, 70, 60), (90, 160, 100), (230, 230, 226))[k]
        m.agregar(prisma(12), (x, 0.87, z), (0.18, 0.22, 0.18), 0, tono)
    m.agregar(caja(), (x, 1.5, -0.3), (0.3, 0.3, 0.5), 0, (176, 136, 90))


def _bicicleta(m):
    """Bicicleta apoyada en la pared izquierda, junto a la puerta."""
    x, z = -ANCHO / 2 + 0.22, 1.0
    for dz in (-0.5, 0.5):
        m.agregar(anillo(24, 0.5, 0.44), (x, 0.35, z + dz), (0.68, 0.05, 0.68), 90, GOMA, (1, 1), 0, 90)
    for (dy, dz, largo, inclinacion) in ((0.35, -0.25, 0.62, 60), (0.35, 0.22, 0.6, -50), (0.62, 0.0, 0.55, 90)):
        m.agregar(caja(), (x, dy + 0.15, z + dz), (0.04, largo, 0.04), 90, (200, 60, 56), (1, 1), 0, inclinacion)
    m.agregar(caja(), (x, 0.82, z - 0.32), (0.06, 0.04, 0.2), 0, GOMA)


# Agarre del martillo según el esqueleto del personaje (medido con capturas de la mano): eje y grados con que se curva
# cada falange para cerrar el puño, y centro del puño en el marco del hueso de la mano (m; +y va hacia los dedos). El
# martillo sale de ese punto; su giro lo marca la curva del golpe (no el hueso: así golpea igual con cualquier esqueleto).
#   rigify: DEF-hand.R con dedos DEF-f_*.R y DEF-thumb.*.R (ciudadano, periodista, candidato)
#   otro:   hand.R con dedos hand.R.002..007 (influencer)
AGARRE = {"rigify": ("p", 70.0, (0.0, 0.075, 0.03)), "otro": ("r", 70.0, (0.0, 0.07, 0.0))}
DEDOS_RIGIFY = ("f_index", "f_middle", "f_ring", "f_pinky", "thumb")
PULGAR = 0.6                                 # el pulgar se cierra menos que los demás dedos


def huesos_dedos(nombres):
    """(tipo de esqueleto, [huesos de los dedos de la mano derecha]) a partir de los nombres de los huesos."""
    rigify = [n for n in nombres if n.startswith("DEF-") and n.endswith(".R") and any(k in n for k in DEDOS_RIGIFY)]
    if rigify:
        return "rigify", rigify
    return "otro", [n for n in nombres if n.startswith("hand.R.")]


def cerrar_puno(actor):
    """Cierra los dedos de la mano derecha del Actor (controlJoint). Devuelve (tipo de esqueleto, huesos tomados)."""
    tipo, huesos = huesos_dedos([j.getName() for j in actor.getJoints()])
    eje, grados = AGARRE[tipo][:2]
    tomados = []
    for nombre in huesos:
        nodo = actor.controlJoint(None, "modelRoot", nombre)
        if nodo is None or nodo.isEmpty():
            continue
        g = grados * (PULGAR if "thumb" in nombre else 1.0)
        h, p, r = nodo.getHpr()
        nodo.setHpr(h + (g if eje == "h" else 0.0), p + (g if eje == "p" else 0.0), r + (g if eje == "r" else 0.0))
        tomados.append(nombre)
    return tipo, tomados


def _martillo():
    """Martillo: mango de madera con la cabeza de hierro arriba; el origen es la mano (donde se agarra)."""
    m = Malla()
    m.agregar(caja(), (0, 0.0, 0.12), (0.03, 0.03, 0.34), 0, MADERA_OSCURA)
    m.agregar(caja(), (0, -0.02, 0.29), (0.05, 0.12, 0.05), 0, HIERRO, (0.8, 1.2))
    return m.mesh()


BANDAS_TALLER = ((0.43, 0.185), (-0.27, -0.43))


def esconder_fondo(escena, bandas=BANDAS_TALLER, extra=()):
    """Esconde el fondo opaco y el marco de la EscenaTrabajo (y las entidades `extra`) para que se vea el set 3D, y pone
    bandas translúcidas (y0, y1) detrás de los textos 2D que se quedan para que se lean sobre el 3D. Devuelve
    (ocultos, bandas) para devolver_fondo(). Sin escena no hace nada. También lo usa frontend/mostrador3d_escena.py."""
    if escena is None:
        return [], []
    ocultos = []
    for entidad in [getattr(escena, "_fondo", None), getattr(escena, "marco", None), *extra]:
        if entidad is not None and entidad.enabled:
            entidad.enabled = False
            ocultos.append(entidad)
    from frontend.componentes import modelo_redondeado
    tinta = color.rgba32(*estilo.TINTA, 205)
    creadas = []
    for y0, y1 in bandas:
        alto = y0 - y1
        creadas.append(Entity(parent=escena.raiz, model=modelo_redondeado(1.18, alto, estilo.RADIO_PANEL_PX),
                              color=tinta, scale=(1.18, alto), position=(0, (y0 + y1) / 2, -0.025)))
    return ocultos, creadas


def devolver_fondo(ocultos, bandas):
    for entidad in ocultos:
        # La EscenaTrabajo pudo destruir ya esa entidad (_limpiar vacía sus capas antes de soltar la vista): encender
        # un nodo vacío hace saltar el assert de Panda «!is_singleton() && !is_empty()».
        if _destruida(entidad):
            continue
        entidad.enabled = True
    for banda in bandas:
        destruir_arbol(banda)


# True si la entidad ya se destruyó (su nodo de Panda quedó vacío) o no se puede preguntar.
def _destruida(entidad):
    try:
        return entidad is None or entidad.is_empty()
    except Exception:                            # noqa: BLE001
        return True


def _fotograma():
    try:
        from panda3d.core import ClockObject
        return ClockObject.getGlobalClock().getFrameCount()
    except Exception:                            # noqa: BLE001
        return None


def _personaje(jugador, parent):
    from backend.logica.roles import ROLES
    from frontend.personaje_modelo import crear_personaje
    rol = getattr(jugador, "rol", None) or "ciudadano"
    nombre = getattr(jugador, "nombre", None) or "Jugador"
    color_rol = ROLES[rol].color if rol in ROLES else (200, 200, 200)
    p = crear_personaje(nombre, rol, color_rol, parent=parent)
    p.automatico = False
    for parte in ("etiqueta", "aro"):
        if getattr(p, parte, None) is not None:
            getattr(p, parte).enabled = False
    return p


class JuegoTaller3D(JuegoTaller):

    # padre: Entity del juego (EscenaTrabajo.juego). turno: TurnoRitmo con piezas de PIEZAS_TALLER_3D. escena: la
    # EscenaTrabajo (se le esconden el fondo y el marco 2D mientras se ve el taller, y se le devuelven al cerrar).
    def __init__(self, padre, turno, jugador=None, escena=None):
        self.escena = escena
        self.jugador = jugador
        self.set = None
        self._luces = []
        self._camara = None
        self._poses = None
        self._ocultos = []
        self._bandas = []
        self._torcido = False
        self._entidad_pieza = None
        self._chispas3d = []
        self._ultimo_fotograma = None
        self._puno = None
        self._tipo_mano, self._dedos = None, []
        self._semilla = sum(ord(c) for c in getattr(turno.pieza, "nombre", "")) + 7
        try:
            super().__init__(padre, turno, jugador)
        except Exception:
            self.cerrar_3d()
            raise

    # -- Construcción (sustituye al dibujo 2D del taller) --

    def _construir_taller(self):
        from frontend.minijuegos_3d.camaras import CamaraMinijuego
        from frontend.piezas import encender_luz, silenciar
        self._esconder_2d()
        raiz = self.set = Entity(parent=scene, name="set_taller3d")
        sala = Entity(parent=raiz, model=_taller().mesh(), shader=lit_with_shadows_shader)
        silenciar(sala)
        # bombilla colgada sobre el banco (sin sombreado: es la fuente de luz)
        Entity(parent=raiz, model="cube", color=rgb((30, 30, 34)), position=(0.1, ALTO_SALA - 0.35, Z_BANCO),
               scale=(0.012, 0.7, 0.012), shader=unlit_shader)
        Entity(parent=raiz, model="sphere", color=rgb(BOMBILLA), position=(0.1, ALTO_SALA - 0.74, Z_BANCO), scale=0.11,
               shader=unlit_shader)
        sol = DirectionalLight(parent=raiz, shadows=True, shadow_map_resolution=(1024, 1024))
        sol.look_at((0.5, -1.4, 0.9))
        sol.color = color.rgba32(255, 236, 206, 255)
        ambiente = AmbientLight(parent=raiz, color=color.rgba32(132, 116, 104, 255))
        self._luces = [sol, ambiente]
        for luz in self._luces:
            encender_luz(luz, True)
        self.personaje = _personaje(self.jugador, raiz)
        x, z, rumbo = PERSONAJE
        try:
            from frontend.minijuegos_3d.poses_3d import PosesPersonaje
            self._poses = PosesPersonaje(self.personaje)
            self._poses.de_pie(x, z, rumbo)
            self._poses.inclinacion_max = INCLINACION_MAX
            # quieto en su sitio del banco: sin el paso de lado automático de poses_3d
            self._poses.PASO_LATERAL = False
        # sin poses: el personaje queda de pie, sin brazo
        except Exception as error:  # noqa: BLE001
            print(f"[taller3d] sin poses del personaje ({error})", file=sys.stderr)
            self._poses = None
            self.personaje.position = (x, 0, z)
        self.martillo = Entity(parent=raiz, model=_martillo(), shader=lit_with_shadows_shader)
        self._agarrar_martillo()
        self.ancla_pieza = Entity(parent=raiz, position=PIEZA)
        # destello de pieza bien hecha: estrella de dos rayos finos que siempre mira a la cámara
        self.destello = Entity(parent=raiz, billboard=True, position=(PIEZA[0] + 0.05, PIEZA[1] + 0.13, PIEZA[2]))
        for giro in (0, 90):
            Entity(parent=self.destello, model="quad", scale=(0.11, 0.008), rotation_z=giro, shader=unlit_shader)
        self._camara = CamaraMinijuego()
        self._camara.tomar(TOMA)
        # Lo que el 2D usa en animar()/eventos() y aquí no existe como tal.
        self.capa_pieza = self.ancla_pieza
        self.capa_chispas = raiz

    def _esconder_2d(self):
        self._ocultos, self._bandas = esconder_fondo(self.escena)

    # -- Pieza --

    def _pintar_pieza(self):
        t = self.turno
        firma = (round(t.progreso(), 4), t.errores())
        if firma == self._firma_pieza:
            return
        self._firma_pieza = firma
        malla = tp.construir(t.pieza, firma[0], t.calidad(), firma[1], self._semilla)
        if self._entidad_pieza is not None:
            destruir_arbol(self._entidad_pieza)
        self._entidad_pieza = Entity(parent=self.ancla_pieza, model=malla.mesh(), scale=ESCALA_PIEZA,
                                     shader=lit_with_shadows_shader)
        self._pieza = self._entidad_pieza

    # -- Martillazo y chispas --

    def _martillazo(self, angulo):
        self._golpe = 0.0
        self._torcido = angulo != ANGULO_GOLPE
        if not self._torcido:
            self._respingo = DURACION_RESPINGO
            self._soltar_chispas()

    def _soltar_chispas(self):
        x, y, z = PIEZA
        for _ in range(N_CHISPAS):
            ang = random.uniform(0, 2 * math.pi)
            rapidez = random.uniform(0.6, 1.3)
            e = Entity(parent=self.set, model="cube", color=rgb(CHISPA), scale=0.012, shader=unlit_shader,
                       position=(x, y + 0.1, z))
            self._chispas3d.append([e, math.cos(ang) * rapidez, random.uniform(0.9, 1.6), math.sin(ang) * rapidez,
                                    DURACION_CHISPAS])

    # -- Cada fotograma --

    def animar(self, dt):
        self._t += dt
        if self._golpe is not None:
            self._golpe += dt
            if tc.golpe_terminado(self._golpe):
                self._golpe = None
        bajada = tc.bajada_martillo(self._golpe, self._torcido)
        self._mover_brazo(bajada)
        # La IK lee los huesos que Panda refresca al dibujar: una sola pasada por fotograma (dos seguidas con los huesos
        # sin refrescar hacen que el brazo tiemble).
        fotograma = _fotograma()
        if self._poses is not None and (fotograma is None or fotograma != self._ultimo_fotograma):
            self._ultimo_fotograma = fotograma
            self._poses.avanzar(dt)
        # respingo de la pieza y temblor rojo tras un fallo
        self._respingo = max(0.0, self._respingo - dt)
        self._rojo = max(0.0, self._rojo - dt)
        if self._entidad_pieza is not None:
            self._entidad_pieza.scale = ESCALA_PIEZA * (1 + 0.1 * (self._respingo / DURACION_RESPINGO))
            temblor = 0.006 * math.sin(self._t * 70) if self._rojo > 0 else 0.0
            self._entidad_pieza.x = temblor
            self._entidad_pieza.color = color.rgb(1, 0.55, 0.5) if self._rojo > 0 else color.white
        # brillo de pieza bien hecha (destello que late sobre ella)
        b = tc.brillo(self.turno.calidad()) * min(1.0, self.turno.progreso() * 3)
        latido = 0.5 + 0.5 * math.sin(self._t * 4.0)
        self.destello.enabled = b > 0.05
        self.destello.scale = 0.4 + 0.8 * b * latido
        for rayo in self.destello.children:
            rayo.color = color.rgba32(255, 252, 230, int(230 * b))
        self._mover_chispas(dt)
        self._mover_notas(dt)

    def _agarrar_martillo(self):
        """Cierra el puño derecho y apunta el centro del puño (en el hueso de la mano) para que el martillo salga de ahí.
        Sin esqueleto (muñeco procedural) el martillo sigue al objetivo de la mano como antes. Nunca lanza."""
        actor = getattr(self.personaje, "actor", None)
        mano = self.personaje.mano("d") if actor is not None and hasattr(self.personaje, "mano") else None
        if mano is None:
            return
        try:
            self._tipo_mano, self._dedos = cerrar_puno(actor)
            x, y, z = AGARRE[self._tipo_mano][2]
            k = 1.0 / (mano.getScale(scene)[0] or 1.0)
            self._puno = (mano, (x * k, y * k, z * k))
        except Exception as error:               # noqa: BLE001
            print(f"[taller3d] el martillo no quedó en la mano ({error})", file=sys.stderr)

    def _mover_brazo(self, bajada):
        """Mano derecha (y martillo) entre arriba y sobre la pieza. La izquierda sigue con su animación: un objetivo
        lejano para ella hacía que el torso se inclinara al máximo y descolocaba el brazo del martillo."""
        x, y, z = PIEZA
        alto = (x + 0.08, y + ALTURA_MARTILLO, z - 0.36)
        golpe = (x + 0.05, y + 0.14, z - 0.26)
        mano = tuple(alto[i] + (golpe[i] - alto[i]) * bajada for i in range(3))
        if self._poses is not None:
            self._poses.mano_directa(mano, "d")
        if self._puno is not None:
            nodo, local = self._puno
            mano = tuple(scene.getRelativePoint(nodo, local))
        self.martillo.position = mano
        # en alto el mango apunta atrás y arriba; al golpear queda horizontal con la cabeza sobre la pieza
        self.martillo.rotation = (-55 + 75 * bajada, -8, 0)

    def _mover_chispas(self, dt):
        for chispa in list(self._chispas3d):
            e, vx, vy, vz, resta = chispa
            chispa[4] = resta - dt
            chispa[2] = vy - 5.0 * dt
            e.position = (e.x + vx * dt, max(ALTO_BANCO, e.y + chispa[2] * dt), e.z + vz * dt)
            e.scale = 0.012 * max(0.0, chispa[4] / DURACION_CHISPAS) + 0.002
            if chispa[4] <= 0:
                destruir_arbol(e)
                self._chispas3d.remove(chispa)

    def _mover_notas(self, dt):
        """Notas que salen del carril (2D): el acierto se encoge, el fallo cae. Igual que JuegoTaller.animar."""
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

    # -- Cierre --

    def cerrar_3d(self):
        """Deshace todo lo 3D: luces, poses, set y cámara; devuelve el fondo y el marco a la escena. Idempotente."""
        from frontend.piezas import encender_luz
        for luz in self._luces:
            try:
                encender_luz(luz, False)
            except Exception:                    # noqa: BLE001
                pass
        self._luces = []
        # los dedos del puño están tomados con controlJoint: se devuelven a la animación
        self._puno = None
        actor = getattr(getattr(self, "personaje", None), "actor", None)
        for nombre in self._dedos:
            try:
                actor.releaseJoint("modelRoot", nombre)
            except Exception:                    # noqa: BLE001
                pass
        self._dedos = []
        if self._poses is not None:
            try:
                self._poses.soltar()
            except Exception:                    # noqa: BLE001
                pass
            self._poses = None
        if self.set is not None:
            destruir_arbol(self.set)
            self.set = None
        self._chispas3d = []
        if self._camara is not None:
            self._camara.soltar()
            self._camara = None
        devolver_fondo(self._ocultos, self._bandas)
        self._ocultos, self._bandas = [], []

    def destruir(self):
        self.cerrar_3d()
        super().destruir()


class PiezaGiratoria(Entity):
    """La pieza terminada en el panel de resultado (camera.ui): la misma malla 3D, girando despacio sobre sí misma."""

    def __init__(self, pieza, calidad, errores, lado, **opciones):
        malla = tp.construir(pieza, 1.0, calidad, errores, sum(ord(c) for c in getattr(pieza, "nombre", "")) + 7)
        centro, mayor = tp.medidas(malla)
        super().__init__(**opciones)
        self.giro = Entity(parent=self, rotation_x=-28)
        Entity(parent=self.giro, model=malla.mesh(), shader=unlit_shader, scale=lado / mayor,
               position=tuple(-c * lado / mayor for c in centro))

    def update(self):
        from ursina import time
        self.giro.rotation_y += 40 * time.dt


def pieza_en_panel(panel, pieza, calidad, errores, pos, lado=0.13, z=-0.03):
    """Pone la pieza 3D terminada (girando) en `pos` del panel de resultado. Devuelve la Entity."""
    return PiezaGiratoria(pieza, calidad, errores, lado, parent=panel, position=(pos[0], pos[1], z))
