# Modelos 3D procedurales de la bicicleta y la moto (Ursina/Panda3D), con la estética del resto del juego: colores
# planos y saturados con bandas de luz horneadas en el color de los vértices, contorno de tinta (casco invertido
# inflado, dibujado por sus caras traseras: el mismo método de frontend/contorno_calculos.py) y una paleta
# determinista por vehículo. Las piezas salen de frontend/vehiculo_piezas.py (puro) y la dinámica de
# frontend/vehiculo_calculos.py.
#
# Jerarquía de un VehiculoModelo (todo con ignore=True salvo el piloto):
#   raiz (x, altura del suelo, z; rotation_y = rumbo)
#     |- sombra            disco oscuro bajo el vehículo (no se inclina)
#     `- pivote_caballito  en el apoyo de la rueda trasera: levanta la delantera (caballito, Shift)
#        `- inclinable     cabeceo (pendiente) y balanceo (lean) alrededor del suelo
#          |- rueda_tras   gira con la distancia recorrida
#          `- suspension   rebote del chasis
#               |- cuadro, biela (gira con el pedaleo), pedal_d / pedal_i (siguen a la biela sin girar), pata
#               |- manubrio (gira con la dirección)
#               |    `- rueda_del
#               |- boca_escape (donde sale el humo) y halo (luz del faro, translúcido)
#               `- piloto (Personaje articulado sentado, pose por cinemática inversa)
#
# Signos de Ursina medidos en una ventana real: rotation_x > 0 baja el morro y adelanta la parte alta (una rueda que
# avanza gira con rotation_x creciente), rotation_z > 0 inclina hacia la derecha, rotation_y > 0 gira a la derecha.
#
# Rendimiento: cada grupo son dos Geom (cuerpo y casco) con color por vértice y sin luces (las bandas ya van en el
# color). El piloto es un Personaje procedural (el mismo muñeco articulado del juego).

import math

from panda3d.core import (CullFaceAttrib, Geom, GeomNode, GeomTriangles, GeomVertexData, GeomVertexFormat,
                          GeomVertexWriter, TransparencyAttrib)
from ursina import Entity, Vec3, color, destroy, scene

from frontend import vehiculo_calculos as vc
from frontend import vehiculo_piezas as vp
from frontend.piezas import silenciar

# Sentido de las caras de las mallas de malla_calculos al usarlas SIN espejo en los ejes del mundo. Si el vehículo
# se ve "del revés" (se ven las caras de dentro) cambiar a True: se comprobó con una captura real (ver MODELOS_3D.md).
INVERTIR_CARAS = False

ELEVACION_SUELO = 0.12            # m sobre altura(x, z): queda sobre las capas de arena/asfalto del suelo (0.10)
COLOR_SOMBRA = (10, 12, 30)


def _nodo_geom(nombre, vertices, colores, triangulos, alfa=1.0, invertir=INVERTIR_CARAS):
    datos = GeomVertexData(nombre, GeomVertexFormat.getV3c4(), Geom.UHStatic)
    datos.setNumRows(len(vertices))
    escribir_v = GeomVertexWriter(datos, "vertex")
    escribir_c = GeomVertexWriter(datos, "color")
    for v, c in zip(vertices, colores):
        escribir_v.addData3(*v)
        escribir_c.addData4(c[0], c[1], c[2], alfa)
    prims = GeomTriangles(Geom.UHStatic)
    for a, b, c in triangulos:
        if invertir:
            prims.addVertices(a, c, b)
        else:
            prims.addVertices(a, b, c)
    geom = Geom(datos)
    geom.addPrimitive(prims)
    nodo = GeomNode(nombre)
    nodo.addGeom(geom)
    return nodo


# Cuelga de `padre` (Entity) el cuerpo de las piezas (bandas horneadas) y su casco de tinta. Sin luces ni texturas:
# el color de los vértices es el color final. Devuelve (nodo_cuerpo, nodo_casco).
def colgar_piezas(padre, piezas, nombre, sin_casco=False):
    cuerpo = padre.attachNewNode(_nodo_geom(nombre, *vp.unir(piezas)))
    cuerpo.setLightOff(1)
    cuerpo.setTextureOff(1)
    casco = None
    if not sin_casco:
        v, c, t = vp.unir_cascos(piezas)
        if v:
            casco = padre.attachNewNode(_nodo_geom(nombre + "_tinta", v, c, t))
            casco.setLightOff(1)
            casco.setTextureOff(1)
            casco.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
    return cuerpo, casco


# Halo de luz: malla translúcida sin casco, sin escribir profundidad.
def colgar_halo(padre, piezas, alfa=0.30):
    v, c, t = vp.unir(piezas)
    nodo = padre.attachNewNode(_nodo_geom("halo", v, c, t, alfa=alfa, invertir=INVERTIR_CARAS))
    nodo.setLightOff(1)
    nodo.setTextureOff(1)
    nodo.setTransparency(TransparencyAttrib.MAlpha)
    nodo.setDepthWrite(False)
    nodo.setTwoSided(True)
    nodo.setBin("fixed", 20)
    return nodo


def _entidad(padre, posicion=(0, 0, 0)):
    entidad = Entity(parent=padre, position=posicion)
    entidad.ignore = True
    return entidad


# Disco oscuro bajo el vehículo (sombra de contacto alargada), sin shader y sin escribir profundidad.
def _sombra(padre, largo, ancho):
    disco = Entity(parent=padre, model="circle", rotation_x=90, y=0.02, scale=(ancho, largo, 1),
                   color=color.rgba32(*COLOR_SOMBRA, 95), shader=None)
    disco.setDepthWrite(False)
    disco.set_depth_offset(1)
    return silenciar(disco)


class VehiculoModelo(Entity):

    # tipo: "bicicleta" o "moto". indice: variante de color (determinista). Aparca el vehículo en el origen.
    def __init__(self, tipo, indice=0, **opciones):
        super().__init__(**opciones)
        self.ignore = True
        self.tipo = tipo
        self.indice = indice
        self.perfil = vc.perfil_de(tipo)
        self.piezas = vp.construir(tipo, indice)
        self.puntos = self.piezas.puntos
        self.paleta = vc.paleta_de(tipo, indice)
        self.piloto = None
        self._pose_aplicada = None
        self._montado = False

        grupos = self.piezas.grupos
        self.sombra = _sombra(self, 2.0 if tipo == vc.BICICLETA else 2.5, 0.75 if tipo == vc.BICICLETA else 0.9)
        # Caballito: el giro se hace alrededor del apoyo de la rueda trasera (en el suelo, bajo su eje), así la
        # trasera no se mueve y el piloto, que cuelga de la suspensión, sigue agarrado al manubrio.
        apoyo_z = grupos["rueda_tras"].pivote[2]
        self.pivote_caballito = _entidad(self, (0.0, 0.0, apoyo_z))
        self.inclinable = _entidad(self.pivote_caballito, (0.0, 0.0, -apoyo_z))
        self.nodos = {}
        self.rueda_tras = self._grupo("rueda_tras", grupos["rueda_tras"], self.inclinable)
        self.suspension = _entidad(self.inclinable)
        for nombre in ("cuadro", "biela", "pedal_d", "pedal_i", "pata"):
            if nombre in grupos:
                self._grupo(nombre, grupos[nombre], self.suspension)
        self._grupo("manubrio", grupos["manubrio"], self.suspension)
        self._grupo("rueda_del", grupos["rueda_del"], self.nodos["manubrio"])
        if "halo" in grupos:
            g = grupos["halo"]
            pm = grupos["manubrio"].pivote                       # el halo gira con el manubrio (cuelga de él)
            self.halo = _entidad(self.nodos["manubrio"], tuple(a - b for a, b in zip(g.pivote, pm)))
            self.halo_nodo = colgar_halo(self.halo, g.piezas)
        else:
            self.halo = None
        escape = self.puntos.get("escape")
        self.boca_escape = _entidad(self.suspension, escape) if escape else None
        self.humo = HumoEscape(self.boca_escape) if self.boca_escape is not None else None
        self.aparcar()

    # Crea el nodo del grupo (Entity en su pivote, relativo a su padre) con su malla y casco.
    def _grupo(self, nombre, grupo, padre_entidad):
        padre_pivote = (0.0, 0.0, 0.0)
        if grupo.padre:
            padre_pivote = self.piezas.grupos[grupo.padre].pivote
        posicion = tuple(a - b for a, b in zip(grupo.pivote, padre_pivote))
        nodo = _entidad(padre_entidad, posicion)
        colgar_piezas(nodo, grupo.piezas, nombre)
        self.nodos[nombre] = nodo
        return nodo

    # -- Piloto -------------------------------------------------------------------------------------------------

    # Sienta a un piloto. `piloto`: Personaje articulado (pivotes) ya creado, que pasa a colgar del vehículo.
    def montar_piloto(self, piloto):
        self.piloto = piloto
        piloto.parent = self.suspension
        piloto.position = (0, 0, 0)
        piloto.automatico = False
        piloto.suelo = None
        piloto.rotation = (0, 0, 0)
        piloto.cuerpo.rotation_y = 0
        piloto.cuerpo.y = 0
        if hasattr(piloto, "_elevar"):
            piloto._elevacion = None
            piloto._elevar()
        for adorno in (getattr(piloto, "aro", None), getattr(piloto, "etiqueta", None)):
            if adorno is not None:
                adorno.enabled = False
        if getattr(piloto, "sombra", None) is not None:
            piloto.sombra.enabled = False
        self._montado = True
        self._pose_aplicada = None
        self.pata_visible(False)
        self._aplicar_pose_piloto(0.0, 0.0)

    # Retira al piloto (queda sin padre). Devuelve el piloto.
    def bajar_piloto(self):
        piloto, self.piloto = self.piloto, None
        self._montado = False
        self.pata_visible(True)
        return piloto

    def pata_visible(self, visible):
        pata = self.nodos.get("pata")
        if pata is not None:
            pata.enabled = bool(visible)

    def _aplicar_pose_piloto(self, fase, balanceo):
        piloto = self.piloto
        if piloto is None:
            return
        clave = round(fase, 3), round(balanceo, 4)
        if clave == self._pose_aplicada:
            return
        self._pose_aplicada = clave
        if hasattr(piloto, "sentar_en"):                            # piloto con modelo .glb (frontend/piloto_glb.py)
            pelvis_z = piloto.sentar_en(self.piezas, fase)
        else:
            pose, pelvis_z = vp.pose_piloto(self.piezas, fase)
            piloto.aplicar_pose(pose)
        piloto.z = pelvis_z
        piloto.x = balanceo
        piloto.rotation_z = -math.degrees(balanceo) * 2.0           # el torso se contrapesa con la pedalada

    # -- Estado -------------------------------------------------------------------------------------------------

    # Pone el modelo como aparcado: sobre la pata de cabra, un poco recostado, sin rebote.
    def aparcar(self, estado=None):
        recostado = 0.14 if self.tipo == vc.BICICLETA else -0.11
        self.inclinable.rotation_z = math.degrees(recostado)
        self.inclinable.rotation_x = 0
        self.pivote_caballito.rotation_x = 0
        self.suspension.y = 0
        self.nodos["manubrio"].rotation_y = -9 if self.tipo == vc.MOTO else 8
        if self.humo is not None:
            self.humo.reiniciar()

    # Aplica un EstadoVehiculo: posición sobre el suelo, rumbo, balanceo, cabeceo, rebote, ruedas, manubrio y pedales.
    # `altura(x, z)` es la altura del terreno (None = plano).
    def aplicar_estado(self, estado, dt=0.0, altura=None, acelerando=False):
        y = ELEVACION_SUELO + (altura(estado.x, estado.z) if altura is not None else 0.0)
        self.position = (estado.x, y, estado.z)
        self.rotation_y = estado.rumbo
        self.inclinable.rotation_z = math.degrees(estado.inclinacion)
        self.inclinable.rotation_x = -math.degrees(estado.cabeceo)
        self.pivote_caballito.rotation_x = -math.degrees(getattr(estado, "caballito", 0.0))   # morro arriba
        self.suspension.y = -estado.rebote * 0.6
        self.nodos["manubrio"].rotation_y = math.degrees(estado.giro_manubrio)
        self.nodos["rueda_del"].rotation_x = math.degrees(estado.giro_rueda_del)
        self.rueda_tras.rotation_x = math.degrees(estado.giro_rueda_tras)
        if self.tipo == vc.BICICLETA:
            self._pedales(estado.fase_pedal)
        self._aplicar_pose_piloto(estado.fase_pedal if self.tipo == vc.BICICLETA else 0.0, estado.balanceo)
        if self.humo is not None:
            self.humo.actualizar(dt, estado.velocidad, self.perfil.vmax, acelerando, self._montado)

    def _pedales(self, fase):
        self.nodos["biela"].rotation_x = math.degrees(fase)
        px = self.puntos["eje_pedal_x"]
        cy, cz = self.puntos["pedalier"][1], self.puntos["pedalier"][2]
        for lado, nombre in ((1, "pedal_d"), (-1, "pedal_i")):
            pz, py = vc.posicion_pedal(fase, lado)
            self.nodos[nombre].position = (px * lado, cy + py, cz + pz)

    def on_destroy(self):
        if self.humo is not None:
            self.humo.destruir()


# Humo ligero del escape: pocas bolitas translúcidas grises que se sueltan en coordenadas del mundo (dejan estela),
# suben, crecen y se desvanecen. Solo mientras el vehículo está encendido y se mueve o acelera.
class HumoEscape:

    BOLITAS = 5
    VIDA = 0.9                     # s
    CADENCIA = 0.16                # s entre bolitas

    def __init__(self, boca):
        self.boca = boca
        self.puntos = []
        self._t = 0.0
        self._siguiente = 0
        for _ in range(self.BOLITAS):
            bolita = Entity(parent=scene, model="sphere", color=color.rgba32(170, 170, 178, 0), shader=None, scale=0.05,
                            enabled=False)
            bolita.setTransparency(TransparencyAttrib.MAlpha)
            bolita.setLightOff(1)
            bolita.setDepthWrite(False)
            silenciar(bolita)
            self.puntos.append([bolita, 0.0])        # [entidad, edad; < 0 = libre]
        self.reiniciar()

    def reiniciar(self):
        for p in self.puntos:
            p[0].enabled = False
            p[1] = -1.0

    def actualizar(self, dt, velocidad, vmax, acelerando, encendido):
        if dt <= 0:
            return
        self._t += dt
        if encendido and self._t >= self.CADENCIA:
            self._t = 0.0
            ritmo = 0.35 + 0.65 * min(1.0, abs(velocidad) / vmax)
            libre = next((p for p in self.puntos if p[1] < 0), None)
            if libre is not None and (acelerando or abs(velocidad) > 0.5 or self._siguiente % 3 == 0):
                self._siguiente += 1
                libre[0].position = Vec3(*self.boca.world_position)
                libre[1] = 0.0
                libre[0].enabled = True
                libre[0].scale = 0.05 + 0.04 * ritmo
        for p in self.puntos:
            if p[1] < 0:
                continue
            p[1] += dt
            t = p[1] / self.VIDA
            if t >= 1.0:
                p[0].enabled = False
                p[1] = -1.0
                continue
            p[0].y += dt * 0.5
            p[0].scale = 0.06 + 0.22 * t
            p[0].color = color.rgba32(176, 176, 184, int(120 * (1.0 - t)))

    def destruir(self):
        for p in self.puntos:
            destroy(p[0])
        self.puntos = []


# -- Piloto ---------------------------------------------------------------------------------------------------


# Crea el muñeco articulado del piloto con el color del rol y la cara del rol (ciudadano / influencer si el rol no
# tiene cara procedural). Es un Personaje del juego (mismo cuerpo, contorno y cara de cómic). Sin padre: lo cuelga
# VehiculoModelo.montar_piloto.
def crear_piloto(nombre, color_rol, rasgos="ciudadano"):
    from frontend.personaje import Personaje
    return Personaje(nombre, color_rol, apariencia={"rasgos": rasgos})
