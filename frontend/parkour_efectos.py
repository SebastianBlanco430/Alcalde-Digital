# Efectos de juego del parkour (Ursina): anillos expansivos al saltar/aterrizar, polvo de datos, pulso del checkpoint,
# baliza de meta con anillos giratorios y el pulso de los interruptores. POCAS entidades REUTILIZADAS (pools fijos creados
# al construir y apagados con enabled=False); nada tiene update(): MundoParkour llama a `sincronizar(sim, dt)` una vez por
# frame y a `reaccionar(evento, sim)` por cada evento de la simulación. Hija de MundoParkour: se destruye con ella.
# La matemática (curvas de los anillos, física del polvo, pulsos) vive en parkour_visual_calculos.py.

import math

from ursina import Entity, color

from frontend import materiales as mat
from frontend import parkour_visual_calculos as pvc
from frontend.parkour_decoracion import aditivo, nodo_malla
from frontend.piezas import silenciar

N_ANILLOS = 9
N_HACES = 4
N_POLVO = 18
ALTO_BALIZA = 16.0


def _c(rgb, alfa=1.0):
    return color.rgba(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255, max(0.0, min(1.0, alfa)))


class EfectosParkour(Entity):

    def __init__(self, nivel, **opciones):
        super().__init__(**opciones)
        self.nivel = nivel
        self._t = 0.0
        self._vy_previa = 0.0
        self._anillos, self._haces, self._polvo = [], [], []
        self._geom_anillo = nodo_malla(*pvc.malla_anillo(), nombre="anillo")
        self._geom_arcos = nodo_malla(*pvc.malla_anillo(0.88, 48, arcos=4), nombre="arcos")
        self._geom_tubo = nodo_malla(*pvc.malla_tubo(), nombre="tubo")
        for _ in range(N_ANILLOS):
            self._anillos.append(self._nuevo(self._geom_anillo))
        for _ in range(N_HACES):
            self._haces.append(self._nuevo(self._geom_tubo))
        for _ in range(N_POLVO):
            e = Entity(parent=self, model="cube", enabled=False)
            self._polvo.append({"e": e, "pos": (0, 0, 0), "vel": (0, 0, 0), "edad": 0.0, "dur": 0.0, "color": (255, 255, 255),
                                "activo": False})
        self._cp = {}                  # id de plataforma -> haz fijo del checkpoint
        self._cp_activo = None
        self._construir_hitos()
        silenciar(self)

    def _nuevo(self, geom):
        e = Entity(parent=self, enabled=False)
        nodo = geom.copyTo(e)
        aditivo(nodo)
        return {"e": e, "edad": 0.0, "dur": 0.0, "r0": 1.0, "r1": 1.0, "alto": 1.0, "color": (255, 255, 255), "a0": 1.0,
                "activo": False}

    # -- Hitos fijos (baliza de meta, haces de checkpoint, anillos de interruptor) --

    def _fijo(self, geom, **opciones):
        e = Entity(parent=self, **opciones)
        aditivo(geom.copyTo(e))
        return e

    def _construir_hitos(self):
        meta = self.nivel.plataformas[self.nivel.meta]
        self._meta = meta
        dorado = mat.NEON_AMARILLO
        self.haz_meta = self._fijo(self._geom_tubo, position=(meta.x, meta.y, meta.z), scale=(0.45, ALTO_BALIZA, 0.45))
        self.haz_meta_ancho = self._fijo(self._geom_tubo, position=(meta.x, meta.y, meta.z), scale=(1.25, ALTO_BALIZA * 0.7, 1.25))
        self.arcos_meta = [self._fijo(self._geom_arcos, position=(meta.x, meta.y + 1.0, meta.z)) for _ in range(3)]
        self._dorado = dorado
        for p in self.nivel.plataformas.values():
            if p.checkpoint and p.id != self.nivel.meta:
                self._cp[p.id] = self._fijo(self._geom_tubo, scale=(0.16, 4.5, 0.16),
                                            position=(p.x + p.ancho / 2 - 0.45, p.y, p.z + p.fondo / 2 - 0.45))
        self._sw = {}
        for sw in self.nivel.interruptores.values():
            anillo = self._fijo(self._geom_anillo, position=(sw.x, sw.y + 0.15, sw.z))
            haz = self._fijo(self._geom_tubo, position=(sw.x, sw.y, sw.z), scale=(0.28, 3.2, 0.28))
            self._sw[sw.id] = (anillo, haz, sw.radio)

    def marcar_checkpoint(self, id_plataforma):
        self._cp_activo = id_plataforma

    # -- Lanzadores --

    def _libre(self, pool):
        for it in pool:
            if not it["activo"]:
                return it
        return min(pool, key=lambda it: it["dur"] - it["edad"])       # todos ocupados: recicla el más viejo

    def anillo(self, pos, tono, r0, r1, dur, alfa=1.0):
        it = self._libre(self._anillos)
        it.update(edad=0.0, dur=dur, r0=r0, r1=r1, color=tono, a0=alfa, activo=True)
        it["e"].position = pos
        it["e"].enabled = True
        return it

    def haz(self, pos, tono, radio, alto, dur, alfa=0.9):
        it = self._libre(self._haces)
        it.update(edad=0.0, dur=dur, r0=radio, r1=radio * 1.3, alto=alto, color=tono, a0=alfa, activo=True)
        it["e"].position = pos
        it["e"].enabled = True
        return it

    def polvo(self, pos, n, rapidez, tono, dur=0.55, semilla=0):
        for i in range(n):
            it = self._libre(self._polvo)
            it.update(pos=(pos[0], pos[1] + 0.05, pos[2]), vel=pvc.velocidad_polvo(i, n, rapidez, semilla), edad=0.0,
                      dur=dur * (0.7 + 0.3 * ((i * 37) % 10) / 10), color=tono, activo=True)
            it["e"].enabled = True

    def _tono_bajo(self, sim):
        p = self.nivel.plataformas.get(sim.sobre) if sim.sobre else None
        if p is None:
            return mat.NEON_CIAN
        return pvc.ESTILOS[pvc.clave_estilo(p.tipo, p.requiere, p.id == self.nivel.meta, p.checkpoint)]["borde"]

    # Reacciona a un evento de la simulación (los mismos textos que devuelve Simulacion.paso).
    def reaccionar(self, evento, sim):
        pos = (sim.x, sim.y + 0.04, sim.z)
        if evento == "salto":
            self.anillo(pos, self._tono_bajo(sim), 0.25, 1.3, 0.32, 0.9)
            self.haz(pos, mat.NEON_CIAN, 0.32, 1.7, 0.26, 0.7)
            self.polvo(pos, 5, 2.2, mat.NEON_CIAN, semilla=1)
        elif evento == "doble_salto":
            self.anillo((sim.x, sim.y + 0.3, sim.z), (255, 140, 225), 0.3, 1.9, 0.42, 0.95)
            self.anillo((sim.x, sim.y + 0.3, sim.z), mat.NEON_CIAN, 0.2, 1.2, 0.3, 0.8)
            self.polvo(pos, 6, 2.6, (255, 140, 225), semilla=2)
        elif evento == "aterrizo":
            fuerza = max(0.35, min(1.0, -self._vy_previa / 13.0))
            tono = self._tono_bajo(sim)
            self.anillo(pos, tono, 0.3, 1.6 + 1.6 * fuerza, 0.5, 1.0)
            self.anillo(pos, (255, 255, 255), 0.2, 1.0 + 1.1 * fuerza, 0.32, 0.7)
            self.polvo(pos, int(4 + 7 * fuerza), 2.0 + 2.2 * fuerza, tono, semilla=3)
        elif evento.startswith("checkpoint:"):
            self.pulso_checkpoint(evento.split(":", 1)[1], sim)
        elif evento == "caida":
            self.anillo(pos, mat.NEON_ROJO, 0.3, 3.6, 0.6, 1.0)
            self.anillo(pos, (255, 255, 255), 0.2, 2.2, 0.4, 0.8)
            self.polvo(pos, 10, 3.0, mat.NEON_ROJO, semilla=4)
        elif evento == "meta":
            for k in range(3):
                self.anillo((self._meta.x, self._meta.y + 0.1 + 0.9 * k, self._meta.z), self._dorado, 0.5, 5.0 + 1.5 * k,
                            0.7 + 0.15 * k, 1.0)
            self.haz((self._meta.x, self._meta.y, self._meta.z), (255, 255, 255), 0.7, 14.0, 0.8, 1.0)
            self.polvo(pos, 16, 4.0, self._dorado, dur=0.9, semilla=5)

    def pulso_checkpoint(self, id_plataforma, sim):
        p = self.nivel.plataformas.get(id_plataforma)
        if p is None:
            return
        pos = (p.x, p.y + 0.06, p.z)
        radio = max(p.ancho, p.fondo) * 0.75 + 1.0
        self.anillo(pos, mat.NEON_VERDE, 0.4, radio, 0.8, 1.0)
        self.anillo(pos, (255, 255, 255), 0.3, radio * 0.6, 0.5, 0.8)
        self.haz((p.x + p.ancho / 2 - 0.45, p.y, p.z + p.fondo / 2 - 0.45), mat.NEON_VERDE, 0.2, 9.0, 0.9, 1.0)
        self.polvo((p.x, p.y, p.z), 10, 3.0, mat.NEON_VERDE, dur=0.8, semilla=6)

    # -- Frame --

    def sincronizar(self, sim, dt):
        self._t = sim.t
        t = sim.t
        # baliza de la meta: haz pulsante + 3 arcos que suben girando y se desvanecen
        p = pvc.pulso(t, 0.55)
        self.haz_meta.setColorScale(_c(self._dorado, 0.35 + 0.35 * p))
        self.haz_meta_ancho.setColorScale(_c(self._dorado, 0.10 + 0.10 * p))
        for k, arco in enumerate(self.arcos_meta):
            fase = (t * 0.28 + k / 3) % 1.0
            arco.y = self._meta.y + 0.8 + fase * 8.5
            arco.rotation_y = t * (70 if k % 2 == 0 else -95) + k * 40
            r = 1.7 + 0.5 * math.sin(fase * math.pi)
            arco.scale = (r, 1, r)
            arco.setColorScale(_c(self._dorado if k != 1 else (255, 250, 225), math.sin(fase * math.pi) ** 0.7))
        for id_p, haz in self._cp.items():
            activo = id_p == self._cp_activo
            haz.setColorScale(_c(mat.NEON_VERDE, (0.55 if activo else 0.16) + (0.1 * pvc.pulso(t, 1.0) if activo else 0)))
        for id_i, (anillo, haz, radio) in self._sw.items():
            activo = sim.interruptor_activo(id_i)
            if activo:
                r = radio * 1.5
                anillo.setColorScale(_c(mat.NEON_VERDE, 0.9))
                haz.setColorScale(_c(mat.NEON_VERDE, 0.5))
            else:
                f = pvc.pulso(t, 1.4)                                 # pulso que invita a pisar el interruptor
                r = radio * (1.2 + 0.7 * f)
                anillo.setColorScale(_c(mat.NEON_MAGENTA, 0.95 - 0.55 * f))
                haz.setColorScale(_c(mat.NEON_MAGENTA, 0.35 + 0.25 * f))
            anillo.scale = (r, 1, r)
        # efectos activos
        for it in self._anillos:
            if it["activo"]:
                it["edad"] += dt
                if it["edad"] >= it["dur"]:
                    it["activo"], it["e"].enabled = False, False
                    continue
                r, a = pvc.estado_anillo(it["edad"], it["dur"], it["r0"], it["r1"], it["a0"])
                it["e"].scale = (r, 1, r)
                it["e"].setColorScale(_c(it["color"], a))
        for it in self._haces:
            if it["activo"]:
                it["edad"] += dt
                if it["edad"] >= it["dur"]:
                    it["activo"], it["e"].enabled = False, False
                    continue
                r, a = pvc.estado_anillo(it["edad"], it["dur"], it["r0"], it["r1"], it["a0"])
                it["e"].scale = (r, it["alto"] * (0.6 + 0.4 * it["edad"] / it["dur"]), r)
                it["e"].setColorScale(_c(it["color"], a))
        for it in self._polvo:
            if it["activo"]:
                it["edad"] += dt
                if it["edad"] >= it["dur"]:
                    it["activo"], it["e"].enabled = False, False
                    continue
                it["pos"], it["vel"] = pvc.paso_particula(it["pos"], it["vel"], dt)
                k = 1 - it["edad"] / it["dur"]
                it["e"].position = it["pos"]
                it["e"].scale = 0.05 + 0.1 * k
                it["e"].color = _c(it["color"], 1)
        if sim.vertical.en_aire:
            self._vy_previa = sim.vertical.vy
