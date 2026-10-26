# Multitud del mapa grande (Ursina): cientos de peatones simulados con tres niveles de detalle. La lógica (circuitos,
# posición analítica por reloj, reparto de niveles) vive en backend/logica/multitud_calculos.py; aquí solo se dibuja.
#
#   Nivel A (hasta 10, a menos de ~25 m de la cámara): PersonajeNPC animado con esqueleto, de una piscina fija
#           (2 por aspecto). Se anima igual que los peatones del mundo chico (clip de marcha según la velocidad).
#   Nivel B (hasta 36, de 25 a 90 m): figura SIN esqueleto, el mismo personaje horneado en pose fija (frontend/
#           multitud_figuras.py): se alterna una pose de paso con la otra cada ~0,7 m recorridos, y de pie al parar.
#           Una sola malla por figura, sin coste de animación en la CPU; sombra de contacto propia.
#   Nivel C (el resto): solo simulado, sin dibujo ni nodo: su posición se calcula al repartir niveles.
#
# Sin saltos: la posición de cada agente es una función analítica del reloj compartido (posicion_en), así que A, B y C
# lo colocan en el MISMO sitio y rumbo; el aspecto es el mismo en A y en B (misma variante), y un cambio A <-> B de un
# agente a la vista se aplaza mientras no sea obligado (Asignador). Sin fugas: todas las instancias (actores, figuras,
# sombras) se crean UNA vez al empezar y se prestan; nunca se crea ni se destruye nada por frame.
#
# Python por frame: ~0,3-0,6 ms con 10 actores y 36 figuras (scripts/medir_multitud.py). La bandera es
# mundo_config.MULTITUD_GRANDE (o ALCALDE_MULTITUD=0/1) y solo vale con el mapa grande.

import math
import sys
import time as _tiempo

from panda3d.core import NodePath
from ursina import Entity, camera, color, destroy, time

from backend.logica import multitud_calculos as mc
from frontend import multitud_figuras as mf
from frontend import poses
from frontend import sombra_calculos as sc

ACTORES_POR_VARIANTE = 2
FIGURAS_POR_VARIANTE = 12
PERIODO_REASIGNAR = 8             # frames entre dos repartos de niveles (~0,13 s a 60 FPS)
PASO_FIGURA = 0.7                 # m recorridos entre dos poses de paso de una figura
MAX_PROMOCIONES = 12              # cambios de nivel hacia arriba por reparto (un teletransporte se absorbe en varios)
COS_VISTA = 0.6                   # un agente a la vista = a menos de ~53 grados del eje de la cámara
COLOR_SOMBRA = (10, 12, 30)
# Animación del esqueleto por distancia (Panda3D): a menos de LOD_CERCA m se actualiza cada frame; hasta LOD_LEJOS m el
# intervalo crece hasta LOD_RETRASO s. Es el mayor gasto de un actor (160 huesos): ~-0,3 ms con 9 actores.
LOD_CERCA, LOD_LEJOS, LOD_RETRASO = 5.0, 25.0, 0.08


def _escala_agente(semilla):
    return 0.96 + 0.08 * mc._u(semilla, 5)


class Multitud(Entity):

    def __init__(self, mundo, cantidad=mc.POBLACION, semilla=mc.SEMILLA_MULTITUD, reloj=None, hora=None, **opciones):
        """`reloj`: callable() -> segundos compartidos (por defecto time.time). `hora`: callable() -> hora de juego 0-24
        para el horario simple (None = sin horario)."""
        super().__init__(**opciones)
        self._mundo = mundo
        self._reloj = reloj or _tiempo.time
        self._hora = hora
        self.poblacion = mc.crear_poblacion(mundo, cantidad, semilla)
        self.agentes = self.poblacion.agentes
        n = len(self.agentes)
        self.asignador = mc.Asignador(self.agentes, ACTORES_POR_VARIANTE, FIGURAS_POR_VARIANTE)
        self._pos = [None] * n
        self._celdas_escaleras = mc.indice_escaleras(mundo)
        self._escala = [_escala_agente(a.semilla) for a in self.agentes]
        self._frame = 0
        self._quietos = set()
        self._camara = (0.0, 0.0, 0.0, 1.0)         # x, z, fx, fz de la cámara en el último reparto
        self.reasignaciones = 0
        self.nodos_creados = 0                       # solo en __init__ (la prueba de fugas comprueba que no crece)
        self._actores = self._crear_actores()
        self._figuras = self._crear_figuras()
        self._en_a, self._en_b = set(), set()

    # -- Piscinas (se crean una vez) --

    def _crear_actores(self):
        actores = []
        for variante in range(mc.VARIANTES):
            for _ in range(ACTORES_POR_VARIANTE):
                p = mf.crear_actor_variante(variante, parent=self)
                p.etiqueta.enabled = False
                p.aro.enabled = False
                p.automatico = False                  # se anima desde aquí
                p.suelo = self._altura
                self._lod_animacion(p)
                p.enabled = False
                actores.append(p)
                self.nodos_creados += 1
        return actores

    @staticmethod
    def _lod_animacion(p):
        try:
            p.actor.find("**/+Character").node().setLodAnimation((0, 0, 0), LOD_LEJOS, LOD_CERCA, LOD_RETRASO)
        except Exception as error:
            print(f"[multitud] sin LOD de animación ({error})", file=sys.stderr)

    def _crear_figuras(self):
        figuras = []
        sombra = Entity(model="circle", rotation_x=90, scale=sc.radio_sombra(0.0) * 2,
                        color=color.rgba32(*COLOR_SOMBRA, round(255 * sc.alfa_sombra(0.0))), shader=None)
        sombra.setDepthWrite(False)
        sombra.set_depth_offset(1)
        y_sombra = sc.elevacion_pies(True) + sc.SESGO_SOMBRA
        for variante in range(mc.VARIANTES):
            moldes = mf.hornear_variante(variante)
            for _ in range(FIGURAS_POR_VARIANTE):
                if moldes is None:
                    figuras.append(None)
                    continue
                raiz = NodePath("figura")
                hijos = [molde.copyTo(raiz) for molde in moldes]
                for h in hijos[1:]:
                    h.hide()
                disco = sombra.copyTo(raiz)
                disco.setY(y_sombra)
                raiz.reparentTo(self)
                raiz.stash()
                figuras.append({"raiz": raiz, "hijos": hijos, "pose": 0})
                self.nodos_creados += 1
        destroy(sombra)
        return figuras

    def _altura(self, x, z):
        return mc.altura_pies(self._mundo, self._celdas_escaleras, x, z)

    # -- Estado de un agente --

    def _estado(self, i, t):
        a = self.agentes[i]
        e = mc.posicion_en(t, a.ruta, a.semilla)
        self._pos[i] = e
        return e

    def estado_de(self, i, t=None):
        """(x, z, rumbo, velocidad, en_movimiento, distancia) del agente `i` ahora (o en `t`)."""
        return self._estado(i, self._reloj() if t is None else t)

    # -- Reparto de niveles --

    def _en_vista(self, i):
        cx, cz, fx, fz = self._camara
        e = self._pos[i]
        dx, dz = e[0] - cx, e[1] - cz
        d = math.hypot(dx, dz)
        return d < 1e-6 or (dx * fx + dz * fz) / d > COS_VISTA

    def _repartir(self, t, cx, cz):
        n = len(self.agentes)
        pos = self._pos
        distancias = [0.0] * n
        for i in range(n):
            e = self._estado(i, t)
            distancias[i] = math.hypot(e[0] - cx, e[1] - cz)
        yaw = math.radians(camera.world_rotation_y)
        self._camara = (cx, cz, math.sin(yaw), math.cos(yaw))
        activos = None
        if self._hora is not None:
            hora = self._hora()
            activos = [mc.activo_a_la_hora(a, hora) for a in self.agentes]
        eventos = self.asignador.actualizar(distancias, activos, self._en_vista, MAX_PROMOCIONES)
        self.reasignaciones += len(eventos)
        for evento in eventos:
            self._aplicar(evento)

    def _aplicar(self, evento):
        i, antes, rec_antes, nuevo, rec_nuevo = evento
        if antes == mc.NIVEL_A:
            self._soltar_actor(i, rec_antes)
        elif antes == mc.NIVEL_B:
            self._soltar_figura(i, rec_antes)
        if nuevo == mc.NIVEL_A:
            self._tomar_actor(i, rec_nuevo)
        elif nuevo == mc.NIVEL_B:
            self._tomar_figura(i, rec_nuevo)

    def _tomar_actor(self, i, rid):
        p = self._actores[rid]
        x, z, rumbo, vel, mov, _ = self._pos[i]
        p.scale = self._escala[i]
        p.colocar(x, z)
        p.fijar_rumbo(rumbo)
        self._quietos.discard(p)
        if mov:
            p.animar_caminar(vel, 0.0)
        else:
            p.aplicar_pose(poses.POSE_PARADO)
            self._quietos.add(p)
        p.enabled = True
        self._en_a.add(i)

    def _soltar_actor(self, i, rid):
        self._actores[rid].enabled = False
        self._quietos.discard(self._actores[rid])
        self._en_a.discard(i)

    def _tomar_figura(self, i, rid):
        f = self._figuras[rid]
        if f is None:
            return
        f["raiz"].setScale(self._escala[i])
        self._poner_figura(i, f, self._pos[i])
        f["raiz"].unstash()
        self._en_b.add(i)

    def _soltar_figura(self, i, rid):
        f = self._figuras[rid]
        if f is not None:
            f["raiz"].stash()
        self._en_b.discard(i)

    def _poner_figura(self, i, f, e):
        x, z, rumbo, _, mov, distancia = e
        f["raiz"].setPosHpr(x, self._altura(x, z), z, -rumbo, 0.0, 0.0)
        pose = (int(distancia / PASO_FIGURA) & 1) if mov else mf.FIGURA_PARADO
        if pose != f["pose"]:
            f["hijos"][f["pose"]].hide()
            f["hijos"][pose].show()
            f["pose"] = pose

    # -- Frame --

    def avanzar(self, dt, t=None, cx=None, cz=None):
        """Un paso de `dt` s (update() lo llama con el reloj y la cámara; las pruebas lo llaman a mano)."""
        t = self._reloj() if t is None else t
        if cx is None:
            cx, cz = camera.world_x, camera.world_z
        self._frame += 1
        if self._frame % PERIODO_REASIGNAR == 1:
            self._repartir(t, cx, cz)
        asig = self.asignador
        pos = self._pos
        for i in self._en_a:
            e = self._estado(i, t)
            p = self._actores[asig.recurso[i]]
            p.colocar(e[0], e[1])
            if e[4]:
                p.mirar_hacia(e[2])
                p.girar(dt)
                p.animar_caminar(e[3], dt)
                self._quietos.discard(p)
            elif p not in self._quietos:
                p.aplicar_pose(poses.POSE_PARADO)
                self._quietos.add(p)
        figuras = self._figuras
        for i in self._en_b:
            f = figuras[asig.recurso[i]]
            self._poner_figura(i, f, self._estado(i, t))

    def update(self):
        self.avanzar(min(time.dt, 0.1))

    def estadisticas(self):
        a = self.asignador
        return {"agentes": len(self.agentes), "A": a.usados_a, "B": a.usados_b,
                "C": len(self.agentes) - a.usados_a - a.usados_b, "rutas": len(self.poblacion.rutas),
                "reasignaciones": self.reasignaciones, "nodos_creados": self.nodos_creados}

    def on_destroy(self):
        for f in self._figuras:
            if f is not None:
                f["raiz"].removeNode()
        self._figuras = []
