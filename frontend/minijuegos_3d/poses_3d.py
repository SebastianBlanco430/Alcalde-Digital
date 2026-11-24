# Poses procedurales del protagonista en los minijuegos 3D (Ursina + Panda3D). Van POR ENCIMA del sistema de animación del
# mundo (frontend/animacion_humana.py, personaje_modelo.py, skinning_gpu.py: NO se tocan) usando la API pública de Panda:
#   - Actor.exposeJoint(...)   para leer dónde está cada hueso (mundo);
#   - Actor.controlJoint(...)  para mandar sobre el brazo/antebrazo (IK de dos huesos) y muslo/espinilla (sentado);
#   - Actor.releaseJoint(...)  para devolverlos a la animación al soltar.
# El resto del cuerpo sigue con sus clips (Idle respira, la cara parpadea). Con el muñeco procedural (sin Actor) cae a las
# poses articuladas de frontend/poses.py (sin IK: brazos aproximados).
#
# Todas las POSICIONES son de MUNDO (coordenadas de `scene`; los sets están en el origen sin rotar). Duraciones en s.
#   p = PosesPersonaje(personaje)
#   p.sentar(x, z, rumbo) / p.de_pie(x, z, rumbo) / p.caminar_a(x, z, rumbo, duracion, al_llegar, girar=True)
#   (de pie, si la mano no llega a su objetivo, da sola un paso de lado: PASO_LATERAL)
#   p.mano_a(punto, lado="d")                -> la mano sigue un punto (suavizado); p.soltar_mano(lado)
#   p.clic(lado) / p.teclear()               -> gestos cortos (índice que pulsa, golpes de tecla)
#   p.alcanzar(punto, duracion, al_llegar, lado)          -> de_pie_alcanzar
#   p.clavar(punto, normal, al_clavar, lado)              -> alcanzar + empujar la chincheta + retirar
#   p.sostener(entidad, lado) / p.colgar(punto, duracion, al_soltar, lado)
#   p.celular_linterna(punto, lado)          -> celular en la mano apuntando a `punto` (cada frame); p.guardar_celular()
#   p.trazar_plumon(punto, normal, lado)     -> mano con plumón cuya punta va a `punto` (cada frame); p.guardar_plumon()
#   p.limitar(punto_plano, normal, margen)   -> la mano no atraviesa ese plano (mesa, corcho): ±2 cm por defecto
#   p.postura(x, z, rumbo, bajada, pies)     -> pelvis continua y pies por IK (frontend/cinematica_silla.py)
#   p.mano_directa(punto, lado) / p.mirar_arriba(grados)   -> mano sin suavizado / levantar la vista
#   p.avanzar(dt)                            -> cada frame (lo llama Minijuego3D.avanzar)
#   p.soltar()                               -> devuelve todo a la animación (lo llama Minijuego3D.cerrar)

import math

from panda3d.core import LMatrix4, LVector3, Point3
from ursina import Entity, color, scene

from frontend import poses as poses_mundo
from frontend.componentes import destruir_arbol, rgb
from frontend.minijuegos_3d import poses_calculos as pc

BAJADA_SENTADO = 0.45            # m que baja el cuerpo al sentarse (pelvis de ~0.97 a ~0.52; silla a 0.45-0.48)
RAPIDEZ_MANO = 14.0              # 1/s: seguimiento suave de la mano hacia su objetivo
DURACION_CLIC = 0.18
DURACION_TECLEO = 0.32
MARGEN_SUPERFICIE = 0.02         # ±2 cm
ALCANCE = 0.56                   # m del hombro a la mano por defecto (sin esqueleto medido)
INCLINAR = True                  # de pie: si la mano no llega, el torso se inclina (hasta pc.INCLINACION_MAXIMA)


def _nombres(lado):
    s = "R" if lado == "d" else "L"
    return {"brazo": (f"DEF-upper_arm.{s}", f"upper_arm.{s}"), "antebrazo": (f"DEF-forearm.{s}", f"forearm.{s}"),
            "mano": (f"DEF-hand.{s}", f"hand.{s}"), "muslo": (f"DEF-thigh.{s}", f"thigh.{s}"),
            "pierna": (f"DEF-shin.{s}", f"shin.{s}"), "pie": (f"DEF-foot.{s}", f"foot.{s}")}


def _v(p):
    return (float(p[0]), float(p[1]), float(p[2]))


class _Cadena:
    """Dos huesos (raíz -> medio -> punta) de un Actor controlados por IK. raiz/medio se controlan, punta solo se lee."""

    def __init__(self, actor, raiz, medio, punta):
        self.actor = actor
        self.nombres = (raiz, medio, punta)
        self.exp = {n: actor.exposeJoint(None, "modelRoot", n) for n in self.nombres}
        self.ctrl = {}
        self.l1 = self.l2 = None

    def pos(self, n):
        return _v(self.exp[n].getPos(scene))

    def medir(self):
        r, m, p = self.nombres
        self.l1 = pc.largo(pc.resta(self.pos(m), self.pos(r)))
        self.l2 = pc.largo(pc.resta(self.pos(p), self.pos(m)))

    def tomar(self, continuo=False):
        if self.ctrl:
            return
        if self.l1 is None:
            self.medir()
        for n in self.nombres[:2]:
            actual = _transform_actual(self.actor, n) if continuo else None
            self.ctrl[n] = self.actor.controlJoint(None, "modelRoot", n)
            if actual is not None:                  # parte de la pose animada (no de la de reposo): sin chasquido
                self.ctrl[n].setMat(actual)

    def soltar(self):
        for n, nodo in list(self.ctrl.items()):
            try:
                self.actor.releaseJoint("modelRoot", n)
                nodo.removeNode()
            except Exception:            # noqa: BLE001
                pass
        self.ctrl.clear()

    def _apuntar(self, n, hijo, deseado):
        """Gira el hueso `n` sobre su pivote para que su hijo `hijo` (posición de mundo) vaya hacia `deseado`."""
        pivote = self.pos(n)
        a = pc.resta(self.pos(hijo), pivote)
        b = pc.resta(deseado, pivote)
        angulo = pc.angulo_entre(a, b)             # robusto (angleDeg de Panda exige vectores normalizados)
        if angulo is None or angulo < 1e-4:
            return
        eje = pc.cruz(a, b)
        if pc.largo(eje) < 1e-9:
            return
        girar(self.exp[n], self.ctrl[n], pivote, pc.unitario(eje), angulo, pc.unitario(a), pc.unitario(b))

    def resolver(self, objetivo, polo, continuo=False):
        """IK: la punta a `objetivo` (mundo), el medio doblado hacia `polo`. Entradas no finitas: no hace nada.
        `continuo`: al tomar el hueso parte de su pose animada de ese momento (cinematica_silla)."""
        if not (pc.finito(objetivo) and pc.finito(polo)):
            return
        self.tomar(continuo)
        r, m, p = self.nombres
        hombro = self.pos(r)
        if not pc.finito(hombro) or not self.l1 or not self.l2:
            return
        codo, mano = pc.ik_dos_huesos(hombro, objetivo, self.l1, self.l2, polo)
        if not (pc.finito(codo) and pc.finito(mano)):
            return
        self._apuntar(r, m, codo)
        self._apuntar(m, p, mano)


def _transform_actual(actor, nombre):
    """Matriz LOCAL actual (animada) del hueso `nombre`, o None. controlJoint arranca el hueso en su pose de REPOSO
    (T-pose): sin esto, la primera pasada de IK salta 2-3 frames."""
    try:
        joints = actor.getJoints(partName="modelRoot", jointName=nombre)
        if not joints:
            return None
        m = LMatrix4()
        joints[0].getTransform(m)
        return m if _matriz_finita(m) else None
    except Exception:                    # noqa: BLE001
        return None


def _matriz_finita(m):
    return all(math.isfinite(m.getCell(i, k)) for i in range(4) for k in range(4))


def girar(expuesto, control, pivote, eje, angulo, desde=None, hacia=None):
    """Gira el hueso controlado (`control` = nodo de controlJoint, `expuesto` = su exposeJoint) `angulo` grados alrededor de
    `eje` (mundo, unitario) por `pivote` (mundo). Con `desde`/`hacia` (unitarios) elige el signo que lleva `desde` a
    `hacia`. Si la matriz resultante no es finita (o la del hueso no se puede invertir), NO toca el hueso: la pose anterior
    se conserva (una matriz NaN en Panda es una aserción que puede tumbar el proceso)."""
    if not (pc.finito(pivote) and pc.finito(eje) and math.isfinite(angulo)):
        return False
    eje_v = LVector3(*eje)
    rot = LMatrix4.rotateMat(angulo, eje_v)
    if desde is not None and hacia is not None:
        otra = LMatrix4.rotateMat(-angulo, eje_v)
        d, h = LVector3(*desde), LVector3(*hacia)
        if (otra.xformVec(d) - h).length() < (rot.xformVec(d) - h).length():   # el signo depende de la mano del sistema
            rot = otra
    neto = expuesto.getMat(scene)
    if not _matriz_finita(neto):
        return False
    p = Point3(*pivote)
    neto2 = neto * LMatrix4.translateMat(-p) * rot * LMatrix4.translateMat(p)
    inverso = LMatrix4(neto)
    if not inverso.invertInPlace():
        return False
    nuevo = neto2 * inverso * control.getMat()
    if not _matriz_finita(nuevo):
        return False
    control.setMat(nuevo)
    return True


def padres_de_huesos(actor):
    """{hueso: padre (o None)} del esqueleto del Actor, recorriendo su PartBundle (solo CharacterJoint cuentan)."""
    from panda3d.core import CharacterJoint
    padres = {}

    def recorrer(grupo, padre):
        for i in range(grupo.getNumChildren()):
            hijo = grupo.getChild(i)
            if isinstance(hijo, CharacterJoint):
                padres[hijo.getName()] = padre
                recorrer(hijo, hijo.getName())
            else:
                recorrer(hijo, padre)
    recorrer(actor.getPartBundle("modelRoot"), None)
    return padres


def hueso_lumbar(actor, brazo, muslo):
    """El hueso que se inclina para llevar el hombro hacia delante: el antepasado del `brazo` MÁS CERCANO A LA RAÍZ que NO
    es antepasado del `muslo` (inclinarlo no mueve las piernas). Con Rigify (DEF-*) y con brasilena.glb sale la columna
    baja. KeyError si no hay ninguno."""
    padres = padres_de_huesos(actor)

    def antepasados(n):
        lista, p = [], padres.get(n)
        while p is not None:
            lista.append(p)
            p = padres.get(p)
        return lista
    de_pierna = set(antepasados(muslo))
    candidatos = [n for n in antepasados(brazo) if n not in de_pierna]
    if len(candidatos) < 2:              # solo el hombro (o nada): no hay columna que inclinar
        raise KeyError(brazo)
    return candidatos[-1]


class _Columna:
    """Un hueso de la columna (lumbar) que se inclina hacia delante para que la mano llegue (de pie). Solo se controla
    mientras la inclinación es > 0; al volver a 0 se devuelve a la animación."""

    def __init__(self, actor, nombre):
        self.actor = actor
        self.nombre = nombre
        self.exp = actor.exposeJoint(None, "modelRoot", nombre)
        self.ctrl = None
        self.aplicada = 0.0              # grados ya aplicados al hueso controlado

    def fijar(self, grados, derecha, adelante):
        if grados <= 0.05 and self.ctrl is None:
            return
        if self.ctrl is None:
            self.ctrl = self.actor.controlJoint(None, "modelRoot", self.nombre)
            self.aplicada = 0.0
        delta = grados - self.aplicada
        if abs(delta) > 1e-3:
            pivote = _v(self.exp.getPos(scene))
            arriba = (0.0, 1.0, 0.0)
            hacia = pc.unitario(pc.suma(arriba, pc.escala(adelante, math.tan(math.radians(min(abs(delta), 60.0))))))
            # el signo bueno es el que lleva «arriba» hacia «adelante» (o al revés al enderezarse)
            if girar(self.exp, self.ctrl, pivote, pc.unitario(derecha), abs(delta),
                     arriba if delta > 0 else hacia, hacia if delta > 0 else arriba):
                self.aplicada = grados
        if grados <= 0.05:
            self.soltar()

    def soltar(self):
        if self.ctrl is not None:
            try:
                self.actor.releaseJoint("modelRoot", self.nombre)
                self.ctrl.removeNode()
            except Exception:            # noqa: BLE001
                pass
        self.ctrl = None
        self.aplicada = 0.0


class PosesPersonaje:

    def __init__(self, personaje):
        self.p = personaje
        self.actor = getattr(personaje, "actor", None)
        self.sentado = False
        self._cadenas = {}
        self._objetivos = {}             # lado -> punto deseado (mundo)
        self._actuales = {}              # lado -> punto suavizado
        self._gestos = {}                # lado -> (tipo, t)
        self._t = 0.0
        self._planos = []
        self._camino = None              # caminar_a
        self._alcance = {}               # lado -> dict(desde, hacia, t, dur, al_llegar, altura)
        self._sostenido = {}             # lado -> entidad
        self._giros = {}                 # lado -> (padre original, hpr relativo a él) de lo sostenido
        self._celular = None
        self._plumon = None
        self._piernas = []               # [(cadena, pie, polo)] mientras está sentado
        self._sentar_pendiente = False
        self._postura = None             # postura(): {"pies": (x, z)} mientras la pelvis baja de forma continua
        self._tobillo = None             # y del tobillo sobre la base, de pie (medido; 0,08 hasta medirlo)
        self._mirar = 0.0                # grados que levanta la vista (mirar_arriba)
        self.tomar_continuo = False      # True (cinematica_silla): al tomar un hueso parte de su pose animada
        self._cabeza = None              # _Columna del hueso de la cabeza (None = aún no; False = no hay)
        if self.actor is not None:
            try:
                for lado in ("d", "i"):
                    n = {k: self._hueso(v) for k, v in _nombres(lado).items()}
                    self._cadenas[lado] = _Cadena(self.actor, n["brazo"], n["antebrazo"], n["mano"])
                    self._cadenas["pierna_" + lado] = _Cadena(self.actor, n["muslo"], n["pierna"], n["pie"])
            except Exception:            # noqa: BLE001  esqueleto desconocido: sin IK (poses articuladas)
                self._cadenas = {}
        self.inclinacion = 0.0           # grados que el torso está inclinado hacia delante (de pie, para llegar)
        # Tope público por instancia (grados; 0 = nunca se inclina). Se puede cambiar en cualquier momento: si baja por
        # debajo de la inclinación actual, el torso vuelve suave hasta el tope. Sin objetivo de mano activo (soltar_mano)
        # el torso vuelve suave a 0.
        self.inclinacion_max = pc.INCLINACION_MAXIMA
        self._columna = None
        if self._cadenas:
            try:
                self._columna = _Columna(self.actor, hueso_lumbar(self.actor, self._cadenas["d"].nombres[0],
                                                                  self._cadenas["pierna_d"].nombres[0]))
            except Exception:            # noqa: BLE001  sin hueso lumbar: sin inclinación
                self._columna = None

    def _hueso(self, candidatos):
        nombres = {j.getName() for j in self.actor.getJoints()}
        for c in candidatos:
            if c in nombres:
                return c
        raise KeyError(candidatos)

    @property
    def con_ik(self):
        return bool(self._cadenas)

    # -- Cuerpo --

    def _base(self):
        return _v(self.p.world_position)

    def _ejes(self):
        """(adelante, derecha) del personaje en el plano del suelo (mundo)."""
        r = math.radians(getattr(self.p, "rumbo", 0.0))
        return (math.sin(r), 0.0, math.cos(r)), (math.cos(r), 0.0, -math.sin(r))

    def de_pie(self, x, z, rumbo):
        self._levantar()
        self.p.colocar(x, z)
        self.p.fijar_rumbo(rumbo)
        self._camino = None

    def _huesos_validos(self):
        """¿Ya se dibujó el esqueleto al menos una vez? (los huesos expuestos valen 0 hasta entonces)."""
        cad = self._cadenas.get("d")
        if cad is None:
            return False
        try:
            if cad.l1 is None or cad.l1 < 0.05:
                cad.medir()
            return cad.l1 is not None and cad.l1 > 0.05 and cad.l2 > 0.05
        except Exception:                # noqa: BLE001
            return False

    def sentar(self, x, z, rumbo):
        self.p.colocar(x, z)
        self.p.fijar_rumbo(rumbo)
        self.sentado = True
        if not self.con_ik:
            self.p.aplicar_pose(poses_mundo.pose_teclear(0))
            return
        self.p.cuerpo.position = (0, -BAJADA_SENTADO, 0)
        self._postura = None
        self._sentar_pendiente = True            # los objetivos de las piernas se fijan cuando los huesos ya se dibujaron

    def postura(self, x, z, rumbo, bajada, pies=None):
        """Postura continua (frontend/cinematica_silla.py): el personaje en (x, z) mirando a `rumbo` con la pelvis `bajada`
        m más abajo. bajada > 0: piernas por IK con los pies plantados alrededor de `pies` (x, z) (cada pie a la altura del
        tobillo, separado como sus caderas) y las rodillas hacia delante; bajada ~0: de pie, piernas de la animación. Se
        llama cada frame mientras dura la bajada/subida; sostener el resultado = seguir llamando avanzar(). Sin esqueleto
        (muñeco procedural): con bajada > 0,2 la pose sentada articulada."""
        self._camino = None
        self.p.colocar(x, z)
        self.p.fijar_rumbo(rumbo)
        if bajada <= 0.005:
            if self.sentado:
                self._levantar()
            self._postura = None
            return
        if not self.con_ik:
            if bajada > 0.2:
                self.sentado = True
                self.p.aplicar_pose(poses_mundo.pose_teclear(0))
            return
        self.sentado = True
        self._sentar_pendiente = False
        self.p.cuerpo.position = (0, -float(bajada), 0)
        if pies is None:
            adelante, _ = self._ejes()
            pies = (x + adelante[0] * 0.45, z + adelante[2] * 0.45)
        self._postura = {"pies": (float(pies[0]), float(pies[1]))}

    def _piernas_postura(self):
        """Objetivos de las piernas para postura(): cada pie en `pies` + su desplazamiento lateral de cadera."""
        adelante, derecha = self._ejes()
        fx, fz = self._postura["pies"]
        base = self._base()
        tobillo = self._tobillo if self._tobillo is not None else 0.08
        piernas = []
        for lado in ("d", "i"):
            cad = self._cadenas["pierna_" + lado]
            if cad.l1 is None:
                cad.medir()
            cadera = cad.pos(cad.nombres[0])
            if not pc.finito(cadera):
                continue
            lateral = pc.punto(pc.resta(cadera, base), derecha)
            pie = (fx + derecha[0] * lateral, base[1] + tobillo, fz + derecha[2] * lateral)
            polo = pc.suma(pc.suma(cadera, pc.escala(adelante, 0.8)), (0.0, -0.1, 0.0))
            piernas.append((cad, pie, polo))
        self._piernas = piernas

    def mirar_arriba(self, grados):
        """Levanta la vista `grados` (la cabeza se echa atrás sobre su hueso; 0 = vuelve a la animación). Sin esqueleto o
        sin hueso de cabeza no hace nada."""
        try:
            grados = float(grados)
        except (TypeError, ValueError):
            grados = 0.0
        self._mirar = min(30.0, max(0.0, grados)) if math.isfinite(grados) else 0.0
        if self._cabeza is None and self._mirar > 0.05 and self.con_ik:
            try:
                self._cabeza = _Columna(self.actor, self._hueso(("DEF-spine.006", "spine.006")))
            except Exception:            # noqa: BLE001  sin hueso de cabeza: no mira arriba
                self._cabeza = False

    def mano_directa(self, punto, lado="d"):
        """Como mano_a pero sin suavizado: la mano va a `punto` este mismo frame (la curva ya la da quien llama)."""
        punto = tuple(punto)
        self._objetivos[lado] = punto
        self._actuales[lado] = punto

    def _sentar_piernas(self):
        """Objetivos de pie y rodilla (mundo) de las dos piernas; la IK los resuelve cada frame en avanzar() (Panda
        refresca los huesos expuestos al dibujar: una pasada por frame es consistente y converge en 1-2 frames)."""
        adelante, _ = self._ejes()
        self._piernas = []
        for lado in ("d", "i"):
            cad = self._cadenas["pierna_" + lado]
            if cad.l1 is None:
                cad.medir()
            cadera = cad.pos(cad.nombres[0])
            rodilla = pc.suma(pc.suma(cadera, pc.escala(adelante, cad.l1 * 0.97)), (0, -0.04, 0))
            pie = pc.suma(rodilla, (adelante[0] * 0.06, -cad.l2, adelante[2] * 0.06))
            self._piernas.append((cad, pie, pc.suma(rodilla, pc.escala(adelante, 0.4))))
        self._sentar_pendiente = False

    def _levantar(self):
        if not self.sentado:
            return
        self.sentado = False
        for cad, _, _ in self._piernas:
            cad.soltar()
        self._piernas = []
        self._sentar_pendiente = False
        self._postura = None
        try:
            self.p.cuerpo.position = (0, 0, 0)
        except Exception:                # noqa: BLE001
            pass

    def caminar_a(self, x, z, rumbo, duracion=0.8, al_llegar=None, girar=True):
        """Camina hasta (x, z) y termina mirando a `rumbo`. Con girar=False da el paso sin girarse (paso de lado)."""
        self._levantar()
        x0, _, z0 = self._base()
        self._camino = {"desde": (x0, z0), "hacia": (x, z), "rumbo": rumbo, "t": 0.0, "dur": max(0.05, duracion),
                        "al_llegar": al_llegar}
        dx, dz = x - x0, z - z0
        if girar and abs(dx) + abs(dz) > 1e-3:
            self.p.fijar_rumbo(math.degrees(math.atan2(dx, dz)))

    # -- Manos --

    def limitar(self, punto_plano, normal, margen=MARGEN_SUPERFICIE):
        self._planos.append((tuple(punto_plano), tuple(normal), margen))

    def mano_a(self, punto, lado="d"):
        self._objetivos[lado] = tuple(punto)

    def mano_reposo(self, lado="i"):
        """Punto (mundo) donde descansa la mano `lado` colgando junto al costado, fuera de la mesa (pc.mano_colgando con
        el hombro y el alcance medidos de ESTE personaje). None sin esqueleto o si los huesos aún no se dibujaron."""
        cad = self._cadenas.get(lado)
        if cad is None or not self._huesos_validos():
            return None
        try:
            hombro = cad.pos(cad.nombres[0])
        except Exception:                # noqa: BLE001
            return None
        adelante, derecha = self._ejes()
        return pc.mano_colgando(hombro, adelante, derecha, 1.0 if lado == "d" else -1.0, self._alcance_de(cad))

    def soltar_mano(self, lado="d"):
        self._objetivos.pop(lado, None)
        self._actuales.pop(lado, None)
        self._alcance.pop(lado, None)
        cad = self._cadenas.get(lado)
        if cad is not None:
            cad.soltar()

    def clic(self, lado="d"):
        self._gestos[lado] = ("clic", 0.0)

    def teclear(self):
        self._gestos["i"] = ("tecleo", 0.0)

    def alcanzar(self, punto, duracion=0.45, al_llegar=None, lado="d", altura=0.05):
        desde = self._actuales.get(lado) or self._mano_actual(lado) or tuple(punto)
        self._alcance[lado] = {"desde": desde, "hacia": tuple(punto), "t": 0.0, "dur": max(0.05, duracion),
                               "al_llegar": al_llegar, "altura": altura}

    def _alcance_de(self, cad):
        """Alcance real (m) del brazo de `cad`: el largo medido de brazo + antebrazo al 97 % (los roles no miden igual: el
        de brasilena.glb es ~0,43 m y el de los demás ~0,58 m)."""
        if cad is not None and cad.l1 and cad.l2:
            return (cad.l1 + cad.l2) * 0.97
        return ALCANCE

    def alcanzable(self, punto, lado="d", alcance=None):
        """¿Llega la mano a `punto` sin moverse? (distancia al hombro; sin esqueleto, siempre True). `alcance` None = el
        del brazo medido de este personaje."""
        cad = self._cadenas.get(lado)
        if cad is None or not self._huesos_validos():
            return True
        return pc.largo(pc.resta(punto, cad.pos(cad.nombres[0]))) <= (alcance or self._alcance_de(cad))

    def acercarse_a(self, punto, normal, distancia=0.5, duracion=0.45, al_llegar=None, lado="d"):
        """Unos pasos hasta quedar de pie frente a `punto` de una superficie VERTICAL (normal hacia la sala), a `distancia`
        m, con la mano `lado` delante del punto. Para el corcho: llegar a una nota lejana antes de clavar/colgar."""
        n = pc.unitario((normal[0], 0.0, normal[2]))
        f = (-n[0], 0.0, -n[2])
        derecha = (f[2], 0.0, -f[0])
        signo = 1.0 if lado == "d" else -1.0
        x = punto[0] + n[0] * distancia - derecha[0] * 0.18 * signo
        z = punto[2] + n[2] * distancia - derecha[2] * 0.18 * signo
        self.caminar_a(x, z, math.degrees(math.atan2(f[0], f[2])), duracion, al_llegar)

    def clavar(self, punto, normal=(0, 0, -1), al_clavar=None, lado="d", acercarse=True):
        """Lleva la mano a 6 cm delante de `punto` (normal hacia fuera de la superficie), empuja hasta tocarla (llama
        `al_clavar` en el contacto) y se retira. Con `acercarse`, si no llega, primero da unos pasos (acercarse_a)."""
        if acercarse and not self.alcanzable(punto, lado):
            self.acercarse_a(punto, normal, al_llegar=lambda: self.clavar(punto, normal, al_clavar, lado, False), lado=lado)
            return
        n = pc.unitario(normal)
        fuera = pc.suma(punto, pc.escala(n, 0.06))
        toque = pc.suma(punto, pc.escala(n, 0.012))

        def empujar():
            def tocar():
                if al_clavar is not None:
                    al_clavar()
                self.alcanzar(fuera, 0.15, None, lado, altura=0.0)
            self.alcanzar(toque, 0.12, tocar, lado, altura=0.0)
        self.alcanzar(fuera, 0.4, empujar, lado)

    def sostener(self, entidad, lado="d"):
        """La entidad viaja en la mano (se reengancha a la mano conservando su posición de mundo)."""
        mano = self._nodo_mano(lado)
        if mano is None:
            return False
        padre = entidad.getParent()
        hpr = entidad.getHpr(padre)              # su giro sobre la superficie: se le devuelve al colgarla
        entidad.wrtReparentTo(mano)
        self._sostenido[lado] = entidad
        self._giros[lado] = (padre, hpr)
        return True

    def colgar(self, punto, duracion=0.5, al_soltar=None, lado="d", padre=None, normal=None):
        """Lleva la mano (y lo sostenido) a `punto` y lo suelta ahí, colgado de `padre` (por defecto la raíz del set).
        Con `normal` (superficie vertical) y el punto fuera de alcance, primero da unos pasos (acercarse_a)."""
        if normal is not None and not self.alcanzable(punto, lado):
            self.acercarse_a(punto, normal, lado=lado,
                             al_llegar=lambda: self.colgar(punto, duracion, al_soltar, lado, padre, None))
            return
        entidad = self._sostenido.get(lado)

        def soltar():
            if entidad is not None:
                destino = padre if padre is not None else self.p.parent
                entidad.wrtReparentTo(destino)
                entidad.setPos(scene, Point3(*punto))
                origen, hpr = self._giros.pop(lado, (None, None))
                if hpr is not None:                    # plano sobre la superficie, con su giro de antes (no de canto)
                    entidad.setHpr(origen if origen is not None and not origen.isEmpty() else destino, hpr)
                self._sostenido.pop(lado, None)
            if al_soltar is not None:
                al_soltar()
        self.alcanzar(punto, duracion, soltar, lado, altura=0.08)

    def celular_linterna(self, punto, lado="d", normal=(0, 1, 0), junto_al_pecho=False):
        """Celular en la mano a ~28 cm del punto (por el lado de `normal`) apuntando a él: la muñeca sigue al punto. Con
        `junto_al_pecho`, la mano se queda delante del pecho (lado `lado`) y solo el celular gira hacia el punto (para
        puntos lejanos: el brazo no se estira por encima de lo que se alumbra)."""
        if not pc.finito(punto) or not pc.finito(normal):
            return
        if self._celular is None:
            self._celular = Entity(parent=scene, model="cube", color=rgb((30, 32, 40)), scale=(0.07, 0.14, 0.012))
            Entity(parent=self._celular, model="quad", color=color.rgb32(250, 246, 210), scale=(0.8, 0.85), z=-0.6,
                   shader=None)
        n = pc.unitario(normal)
        if junto_al_pecho:
            adelante, derecha = self._ejes()
            x, y, z = self._base()
            signo = 1.0 if lado == "d" else -1.0
            mano = (x + adelante[0] * 0.32 + derecha[0] * 0.12 * signo, y + 1.15 - (0.45 if self.sentado else 0.0),
                    z + adelante[2] * 0.32 + derecha[2] * 0.12 * signo)
        else:
            mano = pc.suma(punto, pc.escala(n, 0.28))
        self.mano_a(mano, lado)
        real = self._mano_actual(lado)                  # el celular va en la mano de verdad (aunque aún no llegue)
        real = real if real is not None and pc.finito(real) else mano
        pos = pc.suma(real, pc.escala(n, -0.03))
        self._celular.position = pos
        if pc.largo(pc.resta(punto, pos)) > 1e-3:      # look_at a su propio sitio da una matriz NaN
            self._celular.look_at(Point3(*punto))

    def guardar_celular(self):
        if self._celular is not None:
            destruir_arbol(self._celular)
            self._celular = None

    def trazar_plumon(self, punto, normal=(0, 1, 0), lado="d", tono=None, inclinacion=0.03):
        """Plumón con la punta en `punto` (a 2 mm de la superficie) y la mano 13 cm por encima, siguiendo el trazo.
        `tono` (r, g, b) = color del cuerpo del plumón (por defecto azul; se fija al crearlo). `inclinacion` = m que la mano
        se queda hacia el cuerpo respecto de la punta (0,03 por defecto: casi vertical; más = plumón más tumbado)."""
        if not pc.finito(punto) or not pc.finito(normal):
            return
        n = pc.unitario(normal)
        if self._plumon is None:
            self._plumon = Entity(parent=scene)
            Entity(parent=self._plumon, model="cube", color=rgb(tono or (30, 90, 200)), scale=(0.018, 0.018, 0.13), z=0.065)
            Entity(parent=self._plumon, model="cube", color=rgb((20, 20, 24)), scale=(0.008, 0.008, 0.012), z=0.0)
        punta = pc.suma(punto, pc.escala(n, 0.002))
        adelante, _ = self._ejes()
        mano = pc.suma(pc.suma(punto, pc.escala(n, 0.13)), pc.escala(adelante, -float(inclinacion)))
        self.mano_a(mano, lado)
        real = self._mano_actual(lado)                  # el plumón va en la mano: la punta llega al punto cuando la mano llega
        real = real if real is not None and pc.finito(real) else mano
        punta = pc.suma(punta, pc.resta(real, mano))
        self._plumon.position = punta
        if pc.largo(pc.resta(real, punta)) > 1e-3:
            self._plumon.look_at(Point3(*real))

    def guardar_plumon(self):
        if self._plumon is not None:
            destruir_arbol(self._plumon)
            self._plumon = None

    def _nodo_mano(self, lado):
        try:
            return self.p.mano(lado)
        except Exception:                # noqa: BLE001
            return None

    def _mano_actual(self, lado):
        cad = self._cadenas.get(lado)
        if cad is None:
            return None
        try:
            return cad.pos(cad.nombres[2])
        except Exception:                # noqa: BLE001
            return None

    PASO_LATERAL = True              # de pie: si la mano no llega, el personaje da un paso de lado (corcho y mesa)

    def _paso_lateral(self, cad, lado, objetivo, derecha):
        """De pie y quieto: si `objetivo` queda fuera del alcance del brazo, el paso MÍNIMO a lo largo de la superficie (sin
        acercarse ni alejarse de ella) para alcanzarlo: el personaje no se planta en el centro del corcho o la mesa."""
        if not self.PASO_LATERAL or self.sentado or self._camino is not None:
            return
        hombro = cad.pos(cad.nombres[0])
        if not pc.finito(hombro):
            return
        delta = pc.resta(objetivo, hombro)
        largo = pc.largo(delta)
        alcance = self._alcance_de(cad)
        if largo <= alcance + 0.04:
            return
        lateral = pc.punto(delta, derecha)
        resto2 = max(0.0, largo * largo - lateral * lateral)
        maximo = math.sqrt(max(0.0, alcance * alcance - resto2)) * 0.85
        paso = lateral - math.copysign(min(maximo, abs(lateral)), lateral)
        if abs(paso) < 0.08:
            return
        x, _, z = self._base()
        self.caminar_a(x + derecha[0] * paso, z + derecha[2] * paso, getattr(self.p, "rumbo", 0.0),
                       duracion=min(0.7, 0.25 + abs(paso) * 0.5), girar=False)

    # -- Cada frame --

    def avanzar(self, dt):
        self._t += dt
        self._avanzar_camino(dt)
        for lado in list(self._alcance):
            a = self._alcance[lado]
            a["t"] += dt
            k = pc.suave(a["t"] / a["dur"])
            self._objetivos[lado] = pc.arco(a["desde"], a["hacia"], k, a["altura"])
            self._actuales[lado] = self._objetivos[lado]
            if a["t"] >= a["dur"]:
                if self._alcance.get(lado) is a:
                    del self._alcance[lado]
                if a["al_llegar"] is not None:
                    a["al_llegar"]()
        if not self.con_ik or not self._huesos_validos():
            return
        if self._sentar_pendiente:
            self._sentar_piernas()
        if self._tobillo is None and not self.sentado:
            self._medir_tobillo()
        if self._postura is not None:
            self._piernas_postura()
        for cad, pie, polo in self._piernas:
            cad.resolver(pie, polo, self.tomar_continuo)
        adelante, derecha = self._ejes()
        self._inclinar(dt, adelante, derecha)
        if self._cabeza:
            try:
                self._cabeza.fijar(self._mirar, derecha, pc.escala(adelante, -1.0))
            except Exception:            # noqa: BLE001  una cabeza rara nunca rompe la pose
                self._cabeza.soltar()
                self._cabeza = False
        for lado, objetivo in list(self._objetivos.items()):
            cad = self._cadenas.get(lado)
            if cad is None:
                continue
            objetivo = self._gesto(lado, objetivo, dt)
            for plano in self._planos:
                objetivo = pc.no_atravesar(objetivo, *plano)
            if not pc.finito(objetivo):            # un objetivo no finito nunca llega a la IK ni a Panda
                continue
            self._paso_lateral(cad, lado, objetivo, derecha)
            previo = self._actuales.get(lado)
            actual = pc.seguir(previo if previo is not None and pc.finito(previo) else None, objetivo, dt, RAPIDEZ_MANO)
            if lado not in self._alcance:
                self._actuales[lado] = actual
            hombro = cad.pos(cad.nombres[0])
            signo = 1.0 if lado == "d" else -1.0
            polo = pc.suma(pc.suma(hombro, (0, -0.35, 0)), pc.suma(pc.escala(derecha, 0.35 * signo),
                                                                     pc.escala(adelante, -0.25)))
            cad.resolver(actual, polo, self.tomar_continuo)

    def _medir_tobillo(self):
        try:
            cad = self._cadenas.get("pierna_d")
            y = cad.pos(cad.nombres[2])[1] - self._base()[1]
            if math.isfinite(y) and 0.0 < y < 0.25:
                self._tobillo = y
        except Exception:                # noqa: BLE001
            pass

    def _inclinar(self, dt, adelante, derecha):
        """De pie: el torso se inclina hacia delante mientras a alguna mano le falte para llegar y se endereza cuando
        sobra (pc.paso_inclinacion). Sentado, caminando o sin hueso lumbar: derecho."""
        if self._columna is None:
            return
        falta = -1.0
        if INCLINAR and not self.sentado and self._camino is None:
            for lado, objetivo in self._objetivos.items():
                cad = self._cadenas.get(lado)
                if cad is None or not pc.finito(objetivo):
                    continue
                hombro = cad.pos(cad.nombres[0])
                if pc.finito(hombro):
                    falta = max(falta, pc.largo(pc.resta(objetivo, hombro)) - self._alcance_de(cad))
        self.inclinacion = pc.paso_inclinacion(self.inclinacion, falta, dt, self.inclinacion_max)
        try:
            self._columna.fijar(self.inclinacion, derecha, adelante)
        except Exception:                # noqa: BLE001  una columna rara nunca rompe la pose de los brazos
            self._columna.soltar()
            self._columna = None

    def _gesto(self, lado, objetivo, dt):
        g = self._gestos.get(lado)
        if g is None:
            return objetivo
        tipo, t = g
        t += dt
        dur = DURACION_CLIC if tipo == "clic" else DURACION_TECLEO
        if t >= dur:
            del self._gestos[lado]
            return objetivo
        self._gestos[lado] = (tipo, t)
        baja = 0.014 * pc.curva_golpe(t, dur) if tipo == "clic" else pc.tecleo(t)
        return (objetivo[0], objetivo[1] - baja, objetivo[2])

    def _avanzar_camino(self, dt):
        c = self._camino
        if c is None:
            return
        c["t"] += dt
        k = pc.suave(c["t"] / c["dur"])
        x = c["desde"][0] + (c["hacia"][0] - c["desde"][0]) * k
        z = c["desde"][1] + (c["hacia"][1] - c["desde"][1]) * k
        distancia = math.hypot(c["hacia"][0] - c["desde"][0], c["hacia"][1] - c["desde"][1])
        velocidad = distancia / c["dur"] * 1.5 * (1 - abs(2 * k - 1)) if c["t"] < c["dur"] else 0.0
        self.p.colocar(x, z)
        try:
            self.p.animar_caminar(velocidad, dt)
        except Exception:                # noqa: BLE001
            pass
        if c["t"] >= c["dur"]:
            self.p.fijar_rumbo(c["rumbo"])
            self._camino = None
            try:
                self.p.animar_caminar(0.0, dt)
            except Exception:            # noqa: BLE001
                pass
            if c["al_llegar"] is not None:
                c["al_llegar"]()

    def soltar(self):
        """Devuelve brazos, piernas y columna a la animación, guarda celular y plumón. Nunca lanza."""
        if self._columna is not None:
            self._columna.soltar()
            self.inclinacion = 0.0
        if self._cabeza:
            self._cabeza.soltar()
        self._mirar = 0.0
        for cad in list(self._cadenas.values()):
            try:
                cad.soltar()
            except Exception:            # noqa: BLE001
                pass
        self.guardar_celular()
        self.guardar_plumon()
        self._objetivos.clear()
        self._actuales.clear()
        self._alcance.clear()
        self._levantar()
