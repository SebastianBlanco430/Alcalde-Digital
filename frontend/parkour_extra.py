# Misiones visuales del PARKOUR (Ursina): lo nuevo del paso 6 en un solo controlador que la escena
# (frontend/escenas/escena_parkour.py) llama con enganches mínimos. No toca reglas ni resultados
# (backend/logica/parkour_calculos.py no cambia):
#   - plataformas «desaparece» con glitch y fragmentos (frontend/parkour_glitch.py);
#   - la evidencia es un ORBE que brilla sobre la meta con su estela de partículas; al llegar, vuela hacia ti y estalla;
#   - corredor FANTASMA con tu mejor tiempo (frontend/parkour_fantasma.py);
#   - CÁMARA LENTA breve en los saltos largos (el doble salto): se escala el tiempo de la simulación. El cronómetro y la
#     puntuación usan ese mismo tiempo simulado, así que el resultado es igual; solo se ve más despacio. Los subpasos
#     siguen siendo de 1/60 s como máximo;
#   - MEDALLAS animadas: tres discos (bronce, plata, oro) bajo el cronómetro; al cruzar cada umbral de tiempo la medalla
#     que ya no se alcanza cae y se apaga; al llegar a la meta, la ganada aparece grande.
# La matemática está en frontend/parkour_extra_calculos.py (puro, con tests).
#
# APAGADO: ALCALDE_PARKOUR_VISUAL=0 (o PARKOUR_VISUAL = False): preparar() devuelve None y la escena queda como siempre.
# REDUCIR MOVIMIENTO: sin cámara lenta, sin fragmentos ni temblores; las medallas aparecen sin rebote.
# GUARDIÁN: cada método público atrapa sus errores, avisa una vez por stderr y apaga lo nuevo (la carrera sigue igual).

import math

from ursina import Entity, Text, camera, color

from backend.logica import parkour_calculos as pk
from frontend import banderas_visuales as bv
from frontend import efectos_ui_calculos as fx_calc
from frontend import estilo, tipografia
from frontend import parkour_extra_calculos as calc
from frontend.componentes import escala_fuente

PARKOUR_VISUAL = True
VARIABLE = "ALCALDE_PARKOUR_VISUAL"

TONOS_MEDALLA = {"bronce": (205, 127, 50), "plata": (200, 204, 214), "oro": (255, 205, 64)}
LETRA = {"bronce": "B", "plata": "P", "oro": "O"}
GRIS = (80, 84, 96)
DUR_CAIDA = 0.7
DUR_VUELO_ORBE = 0.6
N_ESTELA = 12
X_DISCOS, Y_DISCOS = 0.25, 0.44      # a la derecha del recuadro del cronómetro (no tapa sus avisos)


def activo():
    return bv.activa(PARKOUR_VISUAL, VARIABLE)


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def preparar(escena, previo=None):
    """Controlador para el mundo actual de la escena (lo rehace si el mundo cambió). None si está apagado o falla."""
    if not activo():
        if previo is not None:
            previo.apagar()
        return None
    try:
        if previo is not None and not previo.roto and previo.mundo is escena.mundo:
            previo.al_entrar()
            return previo
        if previo is not None:
            previo.apagar()
        controlador = ControladorParkour(escena)
        controlador.al_entrar()
        return controlador
    except Exception as error:          # noqa: BLE001
        bv.avisar_una_vez("parkour_extra", error)
        return None


class ControladorParkour:

    def __init__(self, escena):
        self.escena = escena
        self.mundo = escena.mundo
        self.nivel = escena.nivel
        self.roto = False
        self._t_lenta = None
        self._enfriamiento = 0.0
        self._sim = None
        self.reducir = bv.reducir_movimiento()
        from frontend.parkour_fantasma import Fantasma
        from frontend.parkour_glitch import GlitchPlataformas
        self.glitch = GlitchPlataformas(self.nivel, parent=self.mundo)
        self.fantasma = Fantasma(self.nivel, self.mundo, self.mundo)
        self._construir_orbe()
        self._construir_medallas()

    # -- Construcción --

    def _construir_orbe(self):
        self.orbe = None
        if not self.nivel.recompensa.get("evidencia"):
            return
        meta = self.nivel.plataformas[self.nivel.meta]
        self._base_orbe = (meta.x, meta.y, meta.z)
        self.orbe = Entity(parent=self.mundo, model="sphere", scale=0.55, color=_rgba((120, 255, 230)))
        self.halo = Entity(parent=self.orbe, model="sphere", scale=1.7, color=_rgba((120, 255, 230), 0.25))
        self.estela = [Entity(parent=self.mundo, model="sphere", scale=0.12, color=_rgba((180, 255, 240), 0.8))
                       for _ in range(N_ESTELA)]
        self._t_orbe = None              # vuelo hacia el jugador al llegar a la meta

    def _construir_medallas(self):
        self.medallas_ui = Entity(parent=camera.ui, z=-0.05)
        self.discos = {}
        for i, nombre in enumerate(calc.ORDEN):
            disco = Entity(parent=self.medallas_ui, position=(X_DISCOS + i * 0.062, Y_DISCOS, 0))
            Entity(parent=disco, model="circle", scale=0.05, color=_rgba(estilo.TINTA), z=0.001)
            disco.cara = Entity(parent=disco, model="circle", scale=0.043, color=_rgba(TONOS_MEDALLA[nombre]))
            disco.letra = Text(LETRA[nombre], parent=disco, origin=(0, 0), z=-0.001, scale=escala_fuente(14),
                               font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA))
            disco.t_caida = None
            self.discos[nombre] = disco
        self.grande = Entity(parent=camera.ui, position=(-0.66, 0.24, -0.06), enabled=False)
        Entity(parent=self.grande, model="circle", scale=0.17, color=_rgba(estilo.TINTA), z=0.001)
        self.grande.cara = Entity(parent=self.grande, model="circle", scale=0.15)
        self.grande.texto = Text("", parent=self.grande, origin=(0, 0.5), position=(0, -0.1, -0.001),
                                 scale=escala_fuente(20), font=tipografia.FUENTE_TITULO, color=_rgba(estilo.COLOR_ACENTO))
        self.grande.letra = Text("", parent=self.grande, origin=(0, 0), z=-0.002, scale=escala_fuente(40),
                                 font=tipografia.FUENTE_TITULO, color=_rgba(estilo.TINTA))
        self._t_grande = None
        self._alcanzable = None

    # -- Llamadas de la escena --

    def al_entrar(self):
        self._vigilar(self._al_entrar)

    def _al_entrar(self):
        self.medallas_ui.enabled = True
        self.reducir = bv.reducir_movimiento()
        self._alcanzable = pk.medalla_alcanzable(self.nivel, self.escena.sim.t, self.escena.sim.caidas)
        self._pintar_discos()
        self.grande.enabled = False
        if self.orbe is not None and not self.escena.sim.terminado:
            self.orbe.enabled = True
            self._t_orbe = None

    def escala_tiempo(self, dt):
        """dt de la SIMULACIÓN para este frame (más pequeño durante la cámara lenta). Nunca lanza."""
        if self.roto or self._t_lenta is None:
            return dt
        try:
            return dt * calc.factor_tiempo(self._t_lenta, reducir=self.reducir)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("parkour_extra", error)
            self.apagar()
            return dt

    def tras_paso(self, eventos, dt):
        """Tras avanzar la simulación (dt REAL del frame). Eventos de la simulación de este frame."""
        self._vigilar(self._tras_paso, eventos, dt)

    def _tras_paso(self, eventos, dt):
        sim = self.escena.sim
        if sim is not self._sim:                     # carrera nueva (reiniciar) o vuelta a otra partida
            if self._sim is not None and sim.t < getattr(self._sim, "t", 0):
                self.fantasma.reiniciar()
            self._sim = sim
        # Cámara lenta.
        self._enfriamiento = max(0.0, self._enfriamiento - dt)
        if self._t_lenta is not None:
            self._t_lenta += dt
            if self._t_lenta >= calc.DUR_LENTA:
                self._t_lenta = None
        if calc.dispara_lenta(eventos) and self._enfriamiento <= 0 and not self.reducir:
            self._t_lenta = 0.0
            self._enfriamiento = calc.ENFRIAMIENTO
        # Glitch, fantasma, orbe y medallas.
        self.glitch.sincronizar(sim, dt, self.reducir)
        self.fantasma.grabar(sim, self._rumbo_jugador())
        self.fantasma.sincronizar(sim, dt)
        if "meta" in eventos and self.orbe is not None:
            self._t_orbe = 0.0
        self._pintar_orbe(sim, dt)
        if not sim.terminado:
            ahora = pk.medalla_alcanzable(self.nivel, sim.t, sim.caidas)
            for perdida in calc.perdidas(self._alcanzable, ahora):
                self.discos[perdida].t_caida = 0.0
            self._alcanzable = ahora
        self._animar_medallas(dt)

    def al_terminar(self, resultado):
        self._vigilar(self._al_terminar, resultado)

    def _al_terminar(self, resultado):
        record = self.fantasma.al_terminar(resultado)
        medalla = resultado.get("medalla")
        if medalla:
            self.grande.cara.color = _rgba(TONOS_MEDALLA[medalla])
            self.grande.letra.text = LETRA[medalla]
            self.grande.texto.text = f"¡Medalla de {pk.NOMBRE_MEDALLA[medalla].lower()}!" + ("\nRécord nuevo" if record else "")
            self.grande.enabled = True
            self._t_grande = 0.0
        elif record:
            self.grande.enabled = False

    def reiniciar(self):
        self._vigilar(self._reiniciar)

    def _reiniciar(self):
        self.fantasma.reiniciar()
        self._t_lenta = None
        self._al_entrar()
        for disco in self.discos.values():
            disco.t_caida = None
        self._pintar_discos()

    def al_salir(self):
        self._vigilar(self._al_salir)

    def _al_salir(self):
        self.medallas_ui.enabled = False
        self.grande.enabled = False
        self.fantasma.esconder()
        self._t_lenta = None

    # -- Detalles --

    def _rumbo_jugador(self):
        skin = getattr(self.mundo, "_skin", None)
        if skin is not None:
            return float(getattr(skin, "rumbo", 0.0))
        return float(getattr(self.mundo, "_yaw_avatar", 0.0))

    def _pintar_orbe(self, sim, dt):
        if self.orbe is None or not self.orbe.enabled:
            return
        if self._t_orbe is not None:                 # vuela hacia el jugador y estalla
            self._t_orbe += dt
            k = min(1.0, self._t_orbe / DUR_VUELO_ORBE)
            ox, oy, oz = calc.posicion_orbe(sim.t, self._base_orbe)
            self.orbe.position = (ox + (sim.x - ox) * k, oy + (sim.y + 1.0 - oy) * k, oz + (sim.z - oz) * k)
            self.orbe.scale = 0.55 * (1 - 0.7 * k)
            if k >= 1.0:
                self.orbe.enabled = False
                for e in self.estela:
                    e.enabled = False
            return
        self.orbe.position = calc.posicion_orbe(sim.t, self._base_orbe)
        if not self.reducir:
            self.halo.scale = 1.6 + 0.25 * math.sin(sim.t * 4.0)
        for i, (e, p) in enumerate(zip(self.estela, calc.estela_orbe(sim.t, self._base_orbe, N_ESTELA))):
            e.enabled = True
            e.position = p
            e.scale = 0.13 * (1 - i / N_ESTELA)

    def _pintar_discos(self):
        rango = calc.ORDEN.index(self._alcanzable) if self._alcanzable in calc.ORDEN else -1
        for i, nombre in enumerate(calc.ORDEN):
            disco = self.discos[nombre]
            viva = i <= rango
            disco.cara.color = _rgba(TONOS_MEDALLA[nombre] if viva else GRIS)
            disco.y, disco.rotation_z, disco.alpha = Y_DISCOS, 0, 1

    def _animar_medallas(self, dt):
        for nombre, disco in self.discos.items():
            if disco.t_caida is None:
                continue
            disco.t_caida += dt
            k = min(1.0, disco.t_caida / DUR_CAIDA)
            if self.reducir:
                disco.cara.color = _rgba(GRIS)
            else:
                disco.cara.color = _rgba(tuple(TONOS_MEDALLA[nombre][c] + (GRIS[c] - TONOS_MEDALLA[nombre][c]) * k
                                               for c in range(3)))
                disco.y = Y_DISCOS - 0.03 * math.sin(math.pi * k)
                disco.rotation_z = 25 * math.sin(k * math.pi * 3) * (1 - k)
            if k >= 1.0:
                disco.t_caida = None
                disco.y, disco.rotation_z = Y_DISCOS, 0
        if self._t_grande is not None:
            self._t_grande += dt
            self.grande.scale = fx_calc.rebote(self._t_grande, desde=0.0, reducir=self.reducir)
            if self._t_grande > fx_calc.DUR_REBOTE:
                self._t_grande = None

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self.roto:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("parkour_extra", error)
            self.apagar()
            return None

    def apagar(self):
        self.roto = True
        self._t_lenta = None
        for nombre in ("glitch", "orbe", "medallas_ui", "grande"):
            e = getattr(self, nombre, None)
            if e is not None:
                try:
                    e.enabled = False
                except Exception:        # noqa: BLE001
                    pass
        for e in getattr(self, "estela", []):
            try:
                e.enabled = False
            except Exception:            # noqa: BLE001
                pass
        fantasma = getattr(self, "fantasma", None)
        if fantasma is not None:
            try:
                fantasma.esconder()
            except Exception:            # noqa: BLE001
                pass
        # La interfaz cuelga de camera.ui (no del mundo): se destruye para no dejar entidades sueltas.
        for nombre in ("medallas_ui", "grande"):
            e = getattr(self, nombre, None)
            if e is not None:
                try:
                    from frontend.componentes import destruir_arbol
                    destruir_arbol(e)
                except Exception:        # noqa: BLE001
                    pass
                setattr(self, nombre, None)
