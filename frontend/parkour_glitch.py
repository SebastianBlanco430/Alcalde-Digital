# Datos falsos como plataformas con GLITCH (Ursina): la vista nueva del tipo de plataforma «desaparece» de
# backend/logica/parkour_calculos.TIPOS (no se cambian sus reglas: aviso_s, oculta_s). Encima de la caja de siempre
# (frontend/parkour_vista.py, que no se toca) se añaden:
#   - durante el AVISO: dos copias de color (rojo y azul) que tiemblan a los lados y franjas oscuras que «cortan»
#     la plataforma de lado a lado (la vista de siempre ya la hace parpadear);
#   - al romperse (aviso -> oculta): fragmentos que caen y se desvanecen.
# Todo sale de POOLS creados una vez; un solo sincronizar(sim, dt) por frame (lo llama frontend/parkour_extra.py).
# REDUCIR MOVIMIENTO: las copias quedan quietas, sin cortes que saltan ni fragmentos.

from ursina import Entity, color

from backend.logica.parkour_calculos import posicion_plataforma
from frontend import parkour_extra_calculos as calc

GROSOR = 0.5                 # mismo espesor que parkour_vista.GROSOR (la cara superior está en `y`)
N_FRAGMENTOS = 48
FRAGMENTOS_POR_ROTURA = 10
DUR_FRAGMENTO = 0.9


def _rgba(r, g, b, a):
    return color.rgba32(int(r), int(g), int(b), int(max(0.0, min(1.0, a)) * 255))


class GlitchPlataformas(Entity):

    def __init__(self, nivel, **opciones):
        super().__init__(**opciones)
        self.nivel = nivel
        self.decorados = {}          # id -> dict de entidades del glitch
        for p in nivel.plataformas.values():
            if p.tipo != "desaparece":
                continue
            # Láminas planas SOBRE la cara superior (la caja neón tiene la cara de arriba en `y` y crece hacia abajo):
            # dos copias de color desplazadas a los lados y franjas oscuras que cruzan la plataforma.
            raiz = Entity(parent=self)          # se apaga DESPUÉS de colgarle los hijos (si no, quedan apagados)
            rojo = Entity(parent=raiz, model="quad", rotation_x=90, scale=(p.ancho, p.fondo), y=0.025,
                          color=_rgba(255, 40, 70, 0.5), double_sided=True)
            azul = Entity(parent=raiz, model="quad", rotation_x=90, scale=(p.ancho, p.fondo), y=0.035,
                          color=_rgba(40, 140, 255, 0.5), double_sided=True)
            franjas = [Entity(parent=raiz, model="quad", rotation_x=90, scale=(p.ancho * 1.08, p.fondo * 0.1), y=0.045,
                              color=_rgba(8, 6, 14, 0.95), double_sided=True) for _ in range(3)]
            raiz.enabled = False
            self.decorados[p.id] = {"raiz": raiz, "rojo": rojo, "azul": azul, "franjas": franjas, "fase": "solida",
                                    "semilla": sum(ord(c) for c in p.id)}
        self._fragmentos = [{"e": Entity(parent=self, model="cube", scale=0.18, enabled=False), "t": 0.0, "activo": False}
                            for _ in range(N_FRAGMENTOS)]

    def sincronizar(self, sim, dt, reducir=False):
        for pid, d in self.decorados.items():
            p = self.nivel.plataformas[pid]
            fase = sim.fase(p) if sim.activa(p) else "oculta"
            if d["fase"] == "aviso" and fase == "oculta" and not reducir:
                self._romper(p, sim)
            d["fase"] = fase
            raiz = d["raiz"]
            raiz.enabled = fase == "aviso"
            if fase != "aviso":
                continue
            x, y, z = posicion_plataforma(p, sim.t)
            raiz.position = (x, y, z)
            dx_rojo, dx_azul = calc.desfase_color(sim.t, d["semilla"], amplitud=0.22, reducir=reducir)
            d["rojo"].x, d["azul"].x = dx_rojo, dx_azul
            d["azul"].z = -dx_rojo * 0.5
            for franja, (fz, fx) in zip(d["franjas"], calc.cortes(sim.t, d["semilla"], reducir=reducir)):
                franja.z = fz * p.fondo
                franja.x = fx
        self._avanzar_fragmentos(dt)

    def _romper(self, p, sim):
        x, y, z = posicion_plataforma(p, sim.t)
        for dx, dz, vx, vy, vz, giro in calc.fragmentos(FRAGMENTOS_POR_ROTURA, int(sim.t * 100)):
            item = next((f for f in self._fragmentos if not f["activo"]), None)
            if item is None:
                return
            item.update(t=0.0, activo=True, origen=(x + dx * p.ancho, y - GROSOR / 2, z + dz * p.fondo),
                        v=(vx, vy, vz), giro=giro)
            item["e"].color = _rgba(255, 60, 90, 1.0) if vx > 0 else _rgba(80, 160, 255, 1.0)
            item["e"].enabled = True

    def _avanzar_fragmentos(self, dt):
        for item in self._fragmentos:
            if not item["activo"]:
                continue
            item["t"] += dt
            t = item["t"]
            if t >= DUR_FRAGMENTO:
                item["activo"] = False
                item["e"].enabled = False
                continue
            ox, oy, oz = item["origen"]
            px, py, pz = calc.posicion_fragmento(t, *item["v"])
            e = item["e"]
            e.position = (ox + px, oy + py, oz + pz)
            e.rotation = (item["giro"] * t, item["giro"] * t * 0.7, 0)
            e.scale = 0.18 * (1 - t / DUR_FRAGMENTO)
