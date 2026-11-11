# Escena del PARKOUR del sector corrupto (Ursina, 3D en `scene`). Une la lógica pura
# (backend/logica/parkour_calculos.py: Simulacion), la vista 3D (frontend/parkour_vista.py), el HUD
# (frontend/parkour_hud.py) y la cámara en tercera persona. No decide reglas: traduce teclas a la simulación y
# muestra lo que ésta dice.
#
# Entrada: al_entrar(nivel_id, reiniciar=False, salir=callable). `salir` lo llama la escena cuando el jugador
# elige volver (Esc en pausa o el botón); quien registra la escena decide a dónde ir (el mundo con fundido).
# La carrera se CONSERVA al salir y volver al mismo nivel (salvo `reiniciar` o si ya estaba terminada).
# Recompensa: al llegar a la meta se llama a pk.otorgar_recompensa con el GameState que da `game_state()`; si es
# None (GAMESTATE apagado o en línea) el nivel se juega sin consecuencias.
#
# Guarda y restaura lo que cambia del entorno: cámara (CamaraTerceraPersona), color de fondo de la ventana,
# niebla y bloqueo del ratón.

import math

from ursina import held_keys, mouse, scene, time, window

from backend.datos import parkour_loader
from backend.logica import parkour_calculos as pk
from frontend import materiales as mat
from frontend.camara_tercera_persona import CamaraTerceraPersona
from frontend.componentes import destruir_arbol, rgb
from frontend.escenas.escena_base import Escena
from frontend import parkour_minimapa
from frontend.parkour_hud import HudParkour
from frontend.parkour_vista import MundoParkour

PASO_MAX = 1 / 60             # s: la simulación se parte en pasos de este tamaño como máximo
DT_MAX = 0.05                 # s: un tirón de la ventana no se come el salto
RAPIDEZ_CAMARA_Y = 7.0        # 1/s: suavizado de la altura que sigue la cámara (no rebota con cada salto)
JUGANDO, PAUSA, FIN = "jugando", "pausa", "fin"


class EscenaParkour(Escena):

    def __init__(self, game_state=None, al_terminar=None):
        super().__init__(parent=scene)
        self._game_state = game_state or (lambda: None)
        self._al_terminar = al_terminar
        self.hud = HudParkour(al_continuar=self.reanudar, al_reiniciar=self.reiniciar, al_salir=self._salir)
        self.camara = CamaraTerceraPersona(parent=self, suelo=lambda x, z: self._y_camara)
        self.camara.objetivo = lambda: (self.sim.x, self.sim.z)
        self.nivel = None
        self.mundo = None
        self.sim = None
        self.estado = JUGANDO
        self.resultados = {}          # nivel_id -> último resultado (dict de pk.resultado_del_nivel)
        self._partidas = {}           # nivel_id -> Simulacion conservada al salir
        self._salir_a = None
        self._salto = False
        self._y_camara = 0.0
        self._guardado = None

    # -- Gestor de escenas --

    def al_entrar(self, nivel_id="sector_1", reiniciar=False, salir=None, **_):
        nivel = parkour_loader.cargar_nivel(nivel_id)
        if self.nivel is None or self.nivel.id != nivel.id:
            if self.mundo is not None:
                destruir_arbol(self.mundo)
            self.mundo = MundoParkour(nivel, parent=self)
        self.nivel = nivel
        self._salir_a = salir
        previa = self._partidas.get(nivel.id)
        self.sim = pk.Simulacion(nivel) if (reiniciar or previa is None or previa.terminado) else previa
        self._partidas[nivel.id] = self.sim

        self._guardar_entorno()
        self.camara.preparar_camara()
        self.camara.yaw, self.camara.pitch = 0.0, 28.0
        self._y_camara = self.sim.y
        self.camara.colocar_ya()
        self.hud.enabled = True
        self.hud.ocultar_resultado()
        self._poner_estado(JUGANDO)
        self.mundo.marcar_checkpoint(self.sim.checkpoint)
        self.mundo.sincronizar(self.sim)
        self.hud.avisar(f"{nivel.nombre}")
        alturas = pk.alturas_para_minimapa(nivel)
        parkour_minimapa.publicar(alturas)                               # alturas en el minimapa mientras se juega
        parkour_minimapa.actualizar_altura(self.sim.y)
        self.hud.plano.fijar(alturas)
        self.hud.plano.actualizar(self.sim.x, self.sim.z, self.sim.y)

    def al_salir(self):
        parkour_minimapa.limpiar()
        mouse.locked = False
        self.camara.bloquear(False)
        self.camara.restaurar_camara()
        self.hud.mostrar_pausa(False)
        self.hud.enabled = False
        self._restaurar_entorno()

    def _guardar_entorno(self):
        if self._guardado is None:
            self._guardado = {"fondo": window.color, "niebla_color": scene.fog_color,
                              "niebla_densidad": scene.fog_density}
        window.color = rgb(mat.tema(self.nivel.tema)["fondo"])
        scene.fog_density = 0

    def _restaurar_entorno(self):
        if self._guardado is not None:
            window.color = self._guardado["fondo"]
            scene.fog_color = self._guardado["niebla_color"]
            scene.fog_density = self._guardado["niebla_densidad"]
            self._guardado = None

    # -- Estado (juego / pausa / fin) --

    def _poner_estado(self, estado):
        self.estado = estado
        jugando = estado == JUGANDO
        self.camara.bloquear(not jugando)
        mouse.locked = jugando
        self.hud.mostrar_pausa(estado == PAUSA)

    def pausar(self):
        if self.estado == JUGANDO:
            self._poner_estado(PAUSA)

    def reanudar(self):
        if self.estado == PAUSA:
            self._poner_estado(JUGANDO)

    def reiniciar(self):
        self.sim = pk.Simulacion(self.nivel)
        self._partidas[self.nivel.id] = self.sim
        self.hud.ocultar_resultado()
        self._y_camara = self.sim.y
        self.camara.colocar_ya()
        self.mundo.marcar_checkpoint(self.sim.checkpoint)
        self.mundo.sincronizar(self.sim)
        self._poner_estado(JUGANDO)

    def _salir(self):
        if self._salir_a is not None:
            self._salir_a()

    # -- Entrada --

    def input(self, key):
        if key == "escape":
            if self.estado == JUGANDO:
                self.pausar()
            elif self.estado == PAUSA:
                self.reanudar()
            else:
                self._salir()
        elif self.estado == JUGANDO:
            if key == "space":
                self._salto = True
            elif key == "r":
                self._procesar(self.sim.reaparecer_manual())

    # Dirección deseada en el MUNDO a partir de WASD/flechas y el yaw de la cámara (adelante = hacia donde mira).
    def _direccion(self):
        avance = (held_keys["w"] or held_keys["up arrow"]) - (held_keys["s"] or held_keys["down arrow"])
        lateral = (held_keys["d"] or held_keys["right arrow"]) - (held_keys["a"] or held_keys["left arrow"])
        yaw = math.radians(self.camara.yaw)
        return (math.sin(yaw) * avance + math.cos(yaw) * lateral,
                math.cos(yaw) * avance - math.sin(yaw) * lateral)

    # -- Frame --

    def update(self):
        if self.sim is None or self.estado != JUGANDO:
            return
        dt = min(time.dt, DT_MAX)
        mx, mz = self._direccion()
        pasos = max(1, math.ceil(dt / PASO_MAX))
        eventos = []
        for i in range(pasos):
            eventos += self.sim.paso(dt / pasos, mx, mz, salto=self._salto and i == 0)
        self._salto = False
        self._seguir_con_camara(dt)
        parkour_minimapa.actualizar_altura(self.sim.y)
        self.mundo.orientar_avatar(mx, mz, dt)
        self.mundo.sincronizar(self.sim, dt)
        self.hud.actualizar(self.sim, self.nivel, dt)
        self._procesar(eventos)

    def _seguir_con_camara(self, dt):
        _, alto = self.sim.soporte_actual()
        if alto is not None:
            self._y_camara += (alto - self._y_camara) * (1 - math.exp(-RAPIDEZ_CAMARA_Y * dt))

    def _procesar(self, eventos):
        for evento in eventos:
            if evento == "caida":
                self.hud.avisar(f"Caíste: +{self.nivel.penalizacion_caida_s:g} s")
                self._y_camara = self.sim.y
                self.camara.colocar_ya()
                self.mundo.marcar_checkpoint(self.sim.checkpoint)
            elif evento.startswith("checkpoint:"):
                self.hud.avisar("¡Checkpoint!")
                self.mundo.marcar_checkpoint(self.sim.checkpoint)
            elif evento.startswith("interruptor:"):
                self.hud.avisar("¡Interruptor activado! Aparecen plataformas")
            elif evento.startswith("interruptor_apagado:"):
                self.hud.avisar("El interruptor se apagó")
            elif evento == "meta":
                self._terminar()

    def _terminar(self):
        resultado = self.sim.resultado()
        self.resultados[self.nivel.id] = resultado
        estado = self._game_state()
        nueva = pk.otorgar_recompensa(self.nivel, resultado, estado)
        self._poner_estado(FIN)
        self.hud.mostrar_resultado(resultado, nueva_evidencia=nueva, con_estado=estado is not None,
                                   hay_recompensa=bool(self.nivel.recompensa.get("evidencia")))
        if self._al_terminar is not None:
            self._al_terminar(resultado, nueva)
