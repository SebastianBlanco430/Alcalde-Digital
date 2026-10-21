# Rostro y pelo de los personajes con modelo .glb: ojos, cejas, nariz, boca, orejas y pelo como
# geometría ADITIVA colgada del hueso de la cabeza (exposeJoint), así acompañan las animaciones.
# Las formas (elipsoides y cajas de color plano, sin luz ni shader) y sus medidas salen de
# frontend/rostro_calculos.py; el pelo lleva un casco negro un poco mayor, como el contorno del modelo.
#
# colocar_rostro(actor, rol) NUNCA lanza: si algo falla avisa una sola vez por stderr y el modelo
# queda como estaba. Sin colliders. Los nodos cuelgan del Actor: desaparecen cuando se suelta.
# Las medidas están en los ejes del glb crudo (z arriba, cara hacia -y); en el juego Ursina carga
# con y-up-left, así que el contenedor lleva la matriz de conversión de un sistema al otro.

import math
import sys

from panda3d.core import (CS_zup_right, CullFaceAttrib, Geom, GeomNode, GeomTriangles,
                          GeomVertexData, GeomVertexFormat, GeomVertexWriter, Mat4, Vec3,
                          getDefaultCoordinateSystem)

from frontend import rostro_animacion_calculos as ra
from frontend import malla_calculos as ml
from frontend import rostro_calculos as rc

SEGMENTOS = 10                   # meridianos de cada esfera (low-poly, como el modelo)
ANILLOS = 6                      # paralelos de cada esfera

_avisados = set()


def _avisar(rol, motivo):
    if rol not in _avisados:
        _avisados.add(rol)
        print(f"[assets] {rol}: no se pudo colocar el rostro ({motivo}). El modelo queda sin rasgos.",
              file=sys.stderr)


# -- Mallas --

def _malla(nombre, vertices, triangulos, color):
    datos = GeomVertexData(nombre, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    datos.setNumRows(len(vertices))
    escribir_v = GeomVertexWriter(datos, "vertex")
    escribir_c = GeomVertexWriter(datos, "color")
    for vertice in vertices:
        escribir_v.addData3(*vertice)
        escribir_c.addData4(color[0], color[1], color[2], 1.0)
    prims = GeomTriangles(Geom.UHStatic)
    for a, b, c in triangulos:
        prims.addVertices(a, b, c)
    geom = Geom(datos)
    geom.addPrimitive(prims)
    nodo = GeomNode(nombre)
    nodo.addGeom(geom)
    return nodo


def _esfera(nombre, color):
    # Esfera unidad con caras hacia fuera (sentido antihorario visto desde fuera).
    vertices = [(0.0, 0.0, 1.0)]
    for i in range(1, ANILLOS):
        phi = math.pi * i / ANILLOS
        for j in range(SEGMENTOS):
            theta = 2 * math.pi * j / SEGMENTOS
            vertices.append((math.sin(phi) * math.cos(theta), math.sin(phi) * math.sin(theta), math.cos(phi)))
    vertices.append((0.0, 0.0, -1.0))
    polo_sur = len(vertices) - 1
    triangulos = []
    for j in range(SEGMENTOS):
        k = (j + 1) % SEGMENTOS
        triangulos.append((0, 1 + k, 1 + j))
        base = 1 + (ANILLOS - 2) * SEGMENTOS
        triangulos.append((polo_sur, base + j, base + k))
    for i in range(ANILLOS - 2):
        for j in range(SEGMENTOS):
            k = (j + 1) % SEGMENTOS
            a, b = 1 + i * SEGMENTOS + j, 1 + i * SEGMENTOS + k
            c, d = a + SEGMENTOS, b + SEGMENTOS
            triangulos += [(a, b, d), (a, d, c)]
    return _malla(nombre, vertices, triangulos, color)


def _caja(nombre, color):
    # Cubo de lado 2 con caras hacia fuera.
    vertices = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    caras = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    triangulos = []
    for a, b, c, d in caras:
        triangulos += [(a, b, c), (a, c, d)]
    return _malla(nombre, vertices, triangulos, color)


FORMAS = {"esfera": _esfera, "caja": _caja}


# -- Construcción --

def _matriz_cabeza(rol=None):
    # Ejes del glb crudo -> sistema del juego, con el origen en el hueso de la cabeza en bind pose.
    conversion = Mat4.convertMat(CS_zup_right, getDefaultCoordinateSystem())
    reposo = Mat4.translateMat(Vec3(*rc.reposo_cabeza(rol)))
    return reposo * conversion


def _pieza(padre, datos, orden):
    forma = FORMAS[datos["forma"]]
    nodo = padre.attachNewNode(forma(datos["nombre"], datos["color"]))
    nodo.setPos(*datos["pos"])
    nodo.setHpr(*datos.get("rot", (0, 0, 0)))
    nodo.setScale(*datos["escala"])
    nodo.setBin("fixed", orden)          # nada de z-fighting contra la piel: se dibuja después
    if datos.get("contorno"):
        # Casco invertido en negro, un poco mayor: se ve solo por el borde (caras traseras).
        casco = padre.attachNewNode(forma(datos["nombre"] + "_contorno", rc.CONTORNO_COLOR))
        casco.setPos(*datos["pos"])
        casco.setHpr(*datos.get("rot", (0, 0, 0)))
        casco.setScale(*(e * rc.CONTORNO_ESCALA for e in datos["escala"]))
        casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        casco.setBin("fixed", orden - 1)
        casco.setLightOff(1)
        casco.setTwoSided(False, 1)


def _geom_fusionada(nombre, vertices, colores, triangulos):
    # Un solo GeomNode con color por vértice (las bandas de luz ya vienen horneadas en el color).
    datos = GeomVertexData(nombre, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    datos.setNumRows(len(vertices))
    escribir_v = GeomVertexWriter(datos, "vertex")
    escribir_c = GeomVertexWriter(datos, "color")
    for v, c in zip(vertices, colores):
        escribir_v.addData3(*v)
        escribir_c.addData4(c[0], c[1], c[2], 1.0)
    prims = GeomTriangles(Geom.UHStatic)
    for a, b, c in triangulos:
        prims.addVertices(a, b, c)
    geom = Geom(datos)
    geom.addPrimitive(prims)
    nodo = GeomNode(nombre)
    nodo.addGeom(geom)
    return nodo


def _colgar_estaticas(raiz, piezas):
    # Todas las piezas sin animación (pelo, gafas, barba, nariz...) en UN nodo con bandas de luz horneadas, y
    # sus cascos de tinta (los que llevan `contorno`) en otro con las caras traseras: dos llamadas de dibujo.
    if not piezas:
        return
    vertices, colores, triangulos = ml.unir_piezas(piezas)
    nodo = raiz.attachNewNode(_geom_fusionada("estaticas", vertices, colores, triangulos))
    nodo.setBin("fixed", 10)
    por_grosor = {}
    for datos in piezas:
        if datos.get("contorno"):
            por_grosor.setdefault(datos["contorno"], []).append(datos)
    cv, cc, ct = [], [], []
    for grosor, grupo in por_grosor.items():
        v, c, t = ml.unir_piezas(grupo, bandas=False, color_fijo=rc.CONTORNO_COLOR, grosor_extra=grosor)
        base = len(cv)
        cv += v
        cc += c
        ct += [(a + base, b + base, d + base) for a, b, d in t]
    if cv:
        casco = raiz.attachNewNode(_geom_fusionada("contorno", cv, cc, ct))
        casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        casco.setBin("fixed", 8)
        casco.setLightOff(1)
        casco.setTwoSided(False, 1)


# Piezas que solo existen para la animación (párpados cerrados, interior de la boca): un rostro sin animación las omite.
SOLO_ANIMACION = frozenset({"parpado_-1", "parpado_1", "boca_interior", "labio_inf"})


def _armar(raiz, piezas, animar=True):
    # Con `animar`: las piezas animadas, cada una en su nodo (se mueven por su nombre) y el resto fusionadas. Sin
    # `animar` (peatones): todo en un solo nodo fusionado, sin las piezas que solo sirven para animar (menos dibujos).
    estaticas = []
    for orden, datos in enumerate(piezas):
        if animar and datos["nombre"] in rc.ANIMADAS:
            _pieza(raiz, datos, 10 + 2 * orden)
        elif animar or datos["nombre"] not in SOLO_ANIMACION:
            estaticas.append(datos)
    _colgar_estaticas(raiz, estaticas)
    raiz.setLightOff(1)
    raiz.setTextureOff(1)
    raiz.setTwoSided(True)


def construir_rostro(actor, rol):
    # Cuelga del hueso de la cabeza un nodo con todas las piezas del rol. Devuelve ese nodo.
    hueso = actor.exposeJoint(None, "modelRoot", rc.hueso_cabeza(rol))
    if hueso is None:
        raise ValueError(f"no existe el hueso {rc.hueso_cabeza(rol)}")
    raiz = actor.attachNewNode("rostro")          # provisional: fija la pose en el espacio del modelo
    raiz.setMat(_matriz_cabeza(rol))
    _armar(raiz, rc.rostro_del_modelo(rol))
    raiz.wrtReparentTo(hueso)                     # conserva la posición actual (bind pose) y desde ahora sigue al hueso
    return raiz


def construir_rostro_procedural(cabeza, piezas, animar=True):
    # Cabeza del muñeco procedural (`cabeza`: NodePath del pivote de la cabeza, y arriba, la cara a +z): coloca las
    # mismas piezas con una matriz que lleva los ejes del glb a los del muñeco. Devuelve el nodo del rostro.
    raiz = cabeza.attachNewNode("rostro")
    raiz.setMat(Mat4(*(valor for fila in ml.matriz_procedural(rc.ESCALA_PROCEDURAL, rc.CENTRO_CABEZA) for valor in fila)))
    _armar(raiz, piezas, animar)
    return raiz


def colocar_rostro(actor, rol):
    # Nunca lanza: si falla, avisa una vez y el modelo queda como estaba.
    try:
        if rc.rostro_del_modelo(rol) is None:
            return None
        return construir_rostro(actor, rol)
    except Exception as error:
        _avisar(rol, error)
        return None


# -- Animación facial --
# RostroAnimado mueve las piezas del rostro (ojos, pupilas, párpados, cejas, boca) con los gestos de
# frontend/rostro_animacion_calculos.py. Solo cambia posición, giro y escala de nodos que ya cuelgan
# del hueso de la cabeza: sigue al hueso y se libera con actor.removeNode(). actualizar() NUNCA lanza.

MIRADA_X = 0.006                 # m que se desplaza la pupila a cada lado (la esclera deja ~0.0077)
MIRADA_Z = 0.0045                # m hacia arriba/abajo
SIGNO_MIRADA_X = -1.0            # x del glb crudo es la izquierda del personaje (cara hacia -y, z arriba)
SIGNO_FRUNCE = -1.0              # giro de la ceja que baja el extremo interior
ABERTURA_MAX = 0.026             # m que baja el labio inferior con la boca del todo abierta
OJO_RADIO_Z = 0.0185             # semieje vertical del párpado (cubre la esclera entera al cerrar)
AVISO_ANIMACION = "animacion facial"


class RostroAnimado:

    def __init__(self, raiz, rol, semilla=0):
        self.rol = rol
        self.semilla = int(semilla)
        self.roto = False
        self._rumbo = None
        self._giro = 0.0
        self._sonrisa = 0.3
        self._alza = 0.0
        self._frunce = 0.0
        self._apertura = 0.0
        self._visto = None       # último gesto aplicado: si no cambia no se tocan los nodos
        self.nodos = {}
        self._base = {}
        nombres = ["boca", "boca_interior", "labio_inf"]
        for lado in (-1, 1):
            nombres += [f"{base}_{lado}" for base in ("esclera", "iris", "pupila", "ceja", "comisura", "parpado")]
        for nombre in nombres:
            nodo = raiz.find(nombre)
            if nodo.isEmpty():
                raise ValueError(f"falta la pieza {nombre}")
            self.nodos[nombre] = nodo
            self._base[nombre] = (nodo.getPos(), nodo.getHpr(), nodo.getScale())
        self._lids = {lado: True for lado in (-1, 1)}
        self._interior = True
        self._abrir_todo()

    def _abrir_todo(self):
        # Estado de reposo: párpados arriba y ocultos, boca cerrada.
        for lado in (-1, 1):
            self.nodos[f"parpado_{lado}"].hide()
            self._lids[lado] = False
        self.nodos["boca_interior"].hide()
        self.nodos["labio_inf"].hide()
        self._interior = False

    def actualizar(self, t, clip, rumbo=None, dt=0.0):
        # t: segundos acumulados; clip: el que suena; rumbo: grados (para mirar hacia donde gira).
        if self.roto:
            return
        try:
            self._actualizar(t, clip, rumbo, dt)
        except Exception as error:
            self.roto = True
            for lado in (-1, 1):                  # sin párpados visibles: no quedar con los ojos cerrados
                parpado = self.nodos.get(f"parpado_{lado}")
                if parpado is not None:
                    parpado.hide()
            print(f"[assets] {self.rol}: se detiene la {AVISO_ANIMACION} ({error}).", file=sys.stderr)

    def _actualizar(self, t, clip, rumbo, dt):
        dt = ra.acotar(dt, 0.0, 0.25)
        if rumbo is not None and math.isfinite(rumbo) and dt > 0.0:
            if self._rumbo is not None:
                giro = (((rumbo - self._rumbo + 180.0) % 360.0) - 180.0) / dt   # grados/s con signo
                self._giro = ra.suavizar(self._giro, ra.acotar(giro / 150.0, -1.0, 1.0), dt, 0.25)
            self._rumbo = rumbo
        cierre, mx, mz, alza, frunce, apertura, sonrisa = ra.gesto(t, clip, self.semilla, self._giro)
        self._sonrisa = ra.suavizar(self._sonrisa, sonrisa, dt, 0.15)
        self._alza = ra.suavizar(self._alza, alza, dt, 0.10)
        self._frunce = ra.suavizar(self._frunce, frunce, dt, 0.15)
        self._apertura = ra.suavizar(self._apertura, apertura, dt, 0.035)
        estado = (round(cierre, 3), round(mx, 3), round(mz, 3), round(self._alza, 3),
                  round(self._frunce, 3), round(self._apertura, 3), round(self._sonrisa, 3))
        if estado == self._visto:
            return
        self._visto = estado
        self._ojos(cierre, mx, mz)
        self._cejas(self._alza, self._frunce)
        self._boca(self._apertura, self._sonrisa)

    def _ojos(self, cierre, mx, mz):
        n, b = self.nodos, self._base
        for lado in (-1, 1):
            for pieza in ("iris", "pupila"):
                nodo, pos = n[f"{pieza}_{lado}"], b[f"{pieza}_{lado}"][0]
                nodo.setPos(pos.x + SIGNO_MIRADA_X * mx * MIRADA_X, pos.y, pos.z + mz * MIRADA_Z)
            parpado = n[f"parpado_{lado}"]
            if cierre < 0.03:
                if self._lids[lado]:
                    parpado.hide()
                    self._lids[lado] = False
                continue
            if not self._lids[lado]:
                parpado.show()
                self._lids[lado] = True
            base_pos, _, base_esc = b[f"parpado_{lado}"]
            sz = OJO_RADIO_Z * cierre
            parpado.setPos(base_pos.x, base_pos.y, base_pos.z + OJO_RADIO_Z - sz)   # el borde de arriba no se mueve
            parpado.setSz(sz)

    def _cejas(self, alza, frunce):
        for lado in (-1, 1):
            nodo = self.nodos[f"ceja_{lado}"]
            pos, hpr, _ = self._base[f"ceja_{lado}"]
            nodo.setZ(pos.z + 0.007 * alza - 0.0035 * frunce)
            nodo.setR(hpr.z + SIGNO_FRUNCE * lado * (20.0 * frunce - 5.0 * alza))

    def _boca(self, apertura, sonrisa):
        n, b = self.nodos, self._base
        h = ABERTURA_MAX * apertura
        z_sup = b["boca"][0].z + 0.15 * h
        n["boca"].setZ(z_sup)
        if h > 0.0015:
            if not self._interior:
                n["boca_interior"].show()
                n["labio_inf"].show()
                self._interior = True
            interior = n["boca_interior"]
            interior.setZ(z_sup - 0.5 * h)
            interior.setScale(b["boca_interior"][2].x * (1.0 + 0.1 * sonrisa), b["boca_interior"][2].y, 0.5 * h + 0.001)
            n["labio_inf"].setZ(z_sup - h - 0.002)
        elif self._interior:
            n["boca_interior"].hide()
            n["labio_inf"].hide()
            self._interior = False
        # Las comisuras se mantienen pegadas al labio: su extremo interior queda en el borde de la boca
        # y solo sube el exterior, con un giro que crece con la sonrisa (0.3 = la del rostro estático).
        theta = math.radians(25.0 + 30.0 * (sonrisa - 0.3))
        z_borde = z_sup - 0.5 * h
        for lado in (-1, 1):
            nodo = n[f"comisura_{lado}"]
            nodo.setX(lado * (0.0195 + 0.0125 * math.cos(theta)))
            nodo.setZ(z_borde + 0.0125 * math.sin(theta) - 0.0005)
            nodo.setR(-lado * math.degrees(theta))

def colocar_rostro_animado(actor, rol, semilla=0):
    # Como colocar_rostro, pero devuelve además el RostroAnimado (o None si algo falla: el modelo
    # queda con el rostro estático y se avisa una sola vez).
    raiz = colocar_rostro(actor, rol)
    if raiz is None:
        return None
    try:
        return RostroAnimado(raiz, rol, semilla)
    except Exception as error:
        _avisar(rol, f"{AVISO_ANIMACION}: {error}")
        for pieza in ("parpado_-1", "parpado_1", "boca_interior", "labio_inf"):
            nodo = raiz.find(pieza)
            if not nodo.isEmpty():
                nodo.hide()
        return None


def colocar_rostro_procedural(cabeza, piezas, animado=False, rol="procedural", semilla=0):
    # Rostro del muñeco procedural. Devuelve (nodo, RostroAnimado o None); NUNCA lanza: si algo falla avisa una vez
    # y devuelve (None, None) (el muñeco queda con su cabeza de siempre).
    try:
        raiz = construir_rostro_procedural(cabeza, piezas, animado)
    except Exception as error:
        _avisar(rol, error)
        return None, None
    if not animado:
        return raiz, None
    try:
        return raiz, RostroAnimado(raiz, rol, semilla)
    except Exception as error:
        _avisar(rol, f"{AVISO_ANIMACION}: {error}")
        return raiz, None


# Como colocar_rostro_animado, pero con las piezas dadas (los NPC arman una cara distinta cada uno con
# rostro_calculos.piezas_rostro). Nunca lanza: devuelve (nodo, RostroAnimado o None); si algo falla avisa una
# sola vez y el modelo queda como estaba.
def colocar_rostro_animado_piezas(actor, rol, piezas, semilla=0):
    try:
        hueso = actor.exposeJoint(None, "modelRoot", rc.hueso_cabeza(rol))
        if hueso is None:
            raise ValueError(f"no existe el hueso {rc.hueso_cabeza(rol)}")
        raiz = actor.attachNewNode("rostro")
        raiz.setMat(_matriz_cabeza(rol))
        _armar(raiz, piezas)
        raiz.wrtReparentTo(hueso)
    except Exception as error:
        _avisar(rol, error)
        return None
    try:
        return RostroAnimado(raiz, rol, semilla)
    except Exception as error:
        _avisar(rol, f"{AVISO_ANIMACION}: {error}")
        for pieza in ("parpado_-1", "parpado_1", "boca_interior", "labio_inf"):
            nodo = raiz.find(pieza)
            if not nodo.isEmpty():
                nodo.hide()
        return None
