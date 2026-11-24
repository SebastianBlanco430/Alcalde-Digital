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
#
# ANTESALA (sesión B, ALCALDE_ANIM_SILLA, frontend/parkour_antesala.py): con la bandera encendida y partida en curso,
# al_entrar(..., antesala=None|True) no arranca el nivel en el acto: muestra el «terminal del servidor» (el protagonista
# llega, saca la silla, se sienta y la cámara entra en la pantalla con el glitch) y al terminar arranca el nivel como
# siempre (_arrancar_nivel). Mientras dura: la simulación no corre, el HUD está oculto, el ratón libre y Espacio/Enter
# (conexion.saltadores -> saltar_antesala) la saltan sin convertirse en el primer salto del avatar. Al salir (_salir) se
# vuelve a la antesala: sale de la pantalla, se levanta, empuja la silla y después la salida de siempre (`salir`).
# antesala=False (el laboratorio de la Fiscalía, que hace su propia animación), bandera en 0, sin partida (modo
# desarrollo) o cualquier fallo de la antesala: exactamente el camino de antes.

import math

from ursina import held_keys, mouse, scene, time, window

from backend.datos import parkour_loader
from backend.logica import parkour_calculos as pk
from frontend import camara_calculos as cc
from frontend import materiales as mat
from frontend.camara_tercera_persona import CamaraTerceraPersona
from frontend.componentes import destruir_arbol, rgb
from frontend.escenas.escena_base import Escena
from frontend import parkour_antesala_calculos as pac
from frontend import parkour_minimapa
from frontend import parkour_skin_calculos as psc
from frontend import parkour_visual_calculos as pvc
from frontend.parkour_hud import HudParkour
from frontend.parkour_vista import MundoParkour

PASO_MAX = 1 / 60             # s: la simulación se parte en pasos de este tamaño como máximo
DT_MAX = 0.05                 # s: un tirón de la ventana no se come el salto
RAPIDEZ_CAMARA_Y = 7.0        # 1/s: suavizado de la altura que sigue la cámara (no rebota con cada salto)
JUGANDO, PAUSA, FIN = "jugando", "pausa", "fin"
ANTESALA, SALIENDO = "antesala", "saliendo"     # terminal del servidor: entrando al nivel / volviendo de él


class EscenaParkour(Escena):

    def __init__(self, game_state=None, al_terminar=None, jugador=None):
        super().__init__(parent=scene)
        self._game_state = game_state or (lambda: None)
        self._al_terminar = al_terminar
        self._jugador = jugador or (lambda: None)      # jugador activo (su skin .glb); None = sin partida
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
        self._y_apoyo = None          # altura del último apoyo en tierra (cámara estable, camara_calculos)
        self._guardado = None
        self._fov_extra = 0.0         # grados de FOV extra suavizados (aspecto nuevo: al caer rápido o saltar)
        # Antesala (terminal del servidor). `velo()` = alfa del fundido que tapa la pantalla (lo cuelga registro_parkour):
        # la secuencia espera debajo del negro.
        self.velo = lambda: 0.0
        self._antesala = None         # parkour_antesala.Antesala (se construye una vez, en la primera entrada con ella)
        self._antesala_rota = False   # falló al construirse: no se reintenta en este proceso (camino de hoy)
        self._con_antesala = False    # esta entrada pasó por la antesala (la salida también la usa)
        self._saliendo = False        # la salida animada ya empezó (el `salir` de siempre se llama una sola vez)
        self._descartar_salto = False  # la tecla que saltó la antesala no es el primer salto del avatar
        self._t_antesala = 0.0

    # -- Gestor de escenas --

    def al_entrar(self, nivel_id="sector_1", reiniciar=False, salir=None, antesala=None, **_):
        nivel = parkour_loader.cargar_nivel(nivel_id)
        jugador = self._jugador_activo()
        if self.nivel is None or self.nivel.id != nivel.id or self._skin_cambio(jugador):
            if self.mundo is not None:
                destruir_arbol(self.mundo)
            self.mundo = MundoParkour(nivel, jugador=jugador, parent=self)
        self.nivel = nivel
        self._salir_a = salir
        fijar_retorno = getattr(self.hud, "fijar_retorno", None)
        if fijar_retorno is not None:
            fijar_retorno(getattr(salir, "con_retorno", False))
        previa = self._partidas.get(nivel.id)
        self.sim = pk.Simulacion(nivel) if (reiniciar or previa is None or previa.terminado) else previa
        self._partidas[nivel.id] = self.sim
        self._con_antesala = self._saliendo = self._descartar_salto = False
        if self._quiere_antesala(antesala, jugador) and self._abrir_antesala(jugador):
            return
        self._arrancar_nivel()

    # El nivel en marcha: cámara de tercera persona, HUD, estado JUGANDO, minimapa, misiones visuales y tutorial.
    # Sin antesala corre dentro de al_entrar (lo de siempre); con ella, cuando la cámara ya entró en la pantalla.
    def _arrancar_nivel(self):
        nivel = self.nivel
        self._guardar_entorno()
        self.camara.preparar_camara()
        self.camara.yaw, self.camara.pitch = 0.0, 28.0
        self._y_camara = self.sim.y
        self._y_apoyo = None
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
        # Misiones visuales (frontend/parkour_extra.py, ALCALDE_PARKOUR_EXTRA=0 lo apaga): glitch, orbe, fantasma,
        # cámara lenta y medallas. None = la escena de siempre.
        try:
            from frontend import parkour_extra
            self._extra = parkour_extra.preparar(self, getattr(self, "_extra", None))
        except Exception:                        # noqa: BLE001
            self._extra = None
        self._abrir_tutorial()

    # Tutorial de la primera vez en el mundo digital (frontend/registro_tutorial_mision.py, ALCALDE_TUTORIAL_MISION=0 lo apaga):
    # la carrera real queda en pausa y la práctica usa una simulación propia. Nunca rompe la entrada al parkour.
    def _abrir_tutorial(self):
        self._tutorial = None
        try:
            from ursina import camera
            from frontend import registro_tutorial_mision as tutorial_mision
            self._tutorial = tutorial_mision.abrir_si_toca(camera.ui, "parkour", self._tras_tutorial, contexto={"escena": self})
        except Exception:                        # noqa: BLE001
            self._tutorial = None

    def _tras_tutorial(self, saltado, fallo):
        tutorial, self._tutorial = getattr(self, "_tutorial", None), None
        if tutorial is not None:
            try:
                destruir_arbol(tutorial)
            except Exception:                    # noqa: BLE001
                pass

    # -- Antesala (terminal del servidor) --

    def _quiere_antesala(self, pedida, jugador):
        if pedida is False or self._antesala_rota:
            return False
        try:
            from frontend import cinematica_silla
            activa = cinematica_silla.activa()
        except Exception:                        # noqa: BLE001  sin el módulo de la silla: el camino de hoy
            activa = False
        return pac.quiere_antesala(pedida, activa, jugador is not None)

    # Pone la antesala y lanza la entrada. False (y todo como estaba) si algo falla: entonces arranca el nivel de hoy.
    def _abrir_antesala(self, jugador):
        try:
            if self._antesala is None:
                from frontend.parkour_antesala import Antesala
                self._antesala = Antesala(parent=self)
            self._guardar_entorno()
            self.camara.preparar_camara()
            self._ceder_camara()
            self.estado = ANTESALA
            self._t_antesala = 0.0
            self._con_antesala = True
            self._antesala.entrar(jugador, self.nivel.nombre, self._tras_antesala, window.aspect_ratio)
            return True
        except Exception as error:               # noqa: BLE001
            self._avisar_antesala("entrada", error)
            self._antesala_rota = self._antesala is None
            self._recuperar_camara()
            self._con_antesala = False
            return False

    # Mientras se ve la antesala: nivel y HUD ocultos, ratón libre, la cámara la mueve la secuencia.
    def _ceder_camara(self):
        self.hud.mostrar_pausa(False)
        self.hud.enabled = False
        mouse.locked = False
        self.camara.bloquear(True)
        self.camara.tomar_control()
        if self.mundo is not None:
            self.mundo.enabled = False

    def _recuperar_camara(self):
        if self._antesala is not None:
            try:
                self._antesala.ocultar()
            except Exception:                    # noqa: BLE001
                pass
        if self.mundo is not None:
            self.mundo.enabled = True
        self.camara.soltar_control()

    # al_terminar de entrar_a_pantalla (pantalla llena + glitch): fuera la antesala y el nivel arranca como siempre.
    def _tras_antesala(self):
        if self.estado != ANTESALA:
            return
        self._recuperar_camara()
        self._descartar_salto = True
        self.estado = JUGANDO                     # si _arrancar_nivel fallara, no se reintenta cada frame
        self._arrancar_nivel()

    # al_terminar de la salida animada (se levantó y se apartó): la salida de siempre, una sola vez.
    def _tras_salida(self):
        if self.estado != SALIENDO:
            return
        self.estado = FIN
        if self._salir_a is not None:
            self._salir_a()

    # Saltador de conexion.saltadores (Espacio / Enter / botón del mando). True si había antesala que saltar.
    def saltar_antesala(self):
        if not self.enabled or self.estado not in (ANTESALA, SALIENDO) or self._antesala is None:
            return False
        if pac.tapado(self._alfa_velo()):        # bajo el negro manda el fundido (una pulsación, una cosa)
            return False
        try:
            self._antesala.saltar()
        except Exception as error:               # noqa: BLE001
            self._fallo_antesala(error)
            return True
        if self.estado in (ANTESALA, SALIENDO) and not self._antesala.activa():
            self._forzar_fin_antesala()          # la secuencia terminó sin avisar (o no había): se sigue igual
        return True

    def _avanzar_antesala(self, dt):
        if self.estado == ANTESALA and pac.tapado(self._alfa_velo()):
            return                                # el fundido de entrada aún tapa: la secuencia espera
        self._t_antesala += dt
        tope = pac.TOPE_ENTRADA if self.estado == ANTESALA else pac.TOPE_SALIDA
        try:
            if self._t_antesala > tope:
                raise TimeoutError(f"la antesala no terminó en {tope:g} s")
            self._antesala.avanzar(dt)
        except Exception as error:               # noqa: BLE001
            self._fallo_antesala(error)

    # Termina lo que faltara sin la animación: entrando -> el nivel arranca; saliendo -> la salida de siempre.
    def _forzar_fin_antesala(self):
        if self.estado == ANTESALA:
            self._tras_antesala()
        elif self.estado == SALIENDO:
            self._tras_salida()

    def _fallo_antesala(self, error):
        self._avisar_antesala("secuencia", error)
        self._forzar_fin_antesala()

    def _alfa_velo(self):
        try:
            return self.velo()
        except Exception:                        # noqa: BLE001
            return 0.0

    _avisados = set()

    @classmethod
    def _avisar_antesala(cls, donde, error):
        if donde not in cls._avisados:
            cls._avisados.add(donde)
            import sys
            print(f"[parkour] antesala ({donde}) desactivada para esta entrada: {error!r}", file=sys.stderr)

    # Salida animada: vuelve a la antesala (HUD fuera), sale de la pantalla y se levanta. False si no se puede.
    def _abrir_salida(self):
        try:
            tutorial = getattr(self, "_tutorial", None)
            if tutorial is not None and not tutorial.cerrado:
                tutorial.saltar_todo()
            if getattr(self, "_extra", None) is not None:              # medallas fuera de la vista
                self._extra.al_salir()
            self._ceder_camara()
            self.estado = SALIENDO
            self._t_antesala = 0.0
            self._antesala.salir(self._tras_salida, window.aspect_ratio)
            return True
        except Exception as error:               # noqa: BLE001
            self._avisar_antesala("salida", error)
            return False

    def _jugador_activo(self):
        try:
            return self._jugador()
        except Exception:
            return None

    # ¿Otro jugador/rol que el del mundo ya construido? (la skin se rehace; la partida de la simulación se conserva)
    def _skin_cambio(self, jugador):
        if self.mundo is None or not psc.skin_activa():
            return False
        return self.mundo.clave_pedida != psc.datos_de_skin(jugador)

    def al_salir(self):
        tutorial = getattr(self, "_tutorial", None)
        if tutorial is not None and not tutorial.cerrado:
            tutorial.saltar_todo()                # devuelve la carrera real antes de salir
        if self._con_antesala or self.estado in (ANTESALA, SALIENDO):   # antesala: fuera, sin luces, personaje suelto
            self._recuperar_camara()
            if self._antesala is not None:
                try:
                    self._antesala.ocultar(soltar=True)
                except Exception:                # noqa: BLE001
                    pass
            if self.estado in (ANTESALA, SALIENDO):
                self.estado = FIN
            self._con_antesala = False
        parkour_minimapa.limpiar()
        mouse.locked = False
        self.camara.bloquear(False)
        self._fov_extra = self.camara.fov_extra = 0.0
        self.camara.restaurar_camara()
        self.hud.mostrar_pausa(False)
        self.hud.enabled = False
        self._restaurar_entorno()
        if getattr(self, "_extra", None) is not None:                    # misiones visuales
            self._extra.al_salir()

    def _guardar_entorno(self):
        if self._guardado is None:
            self._guardado = {"fondo": window.color, "niebla_color": scene.fog_color,
                              "niebla_densidad": scene.fog_density}
        window.color = rgb(pvc.tema_base(self.nivel.tema)["fondo"])      # temas nuevos: su paleta o la «digital»
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
        self._y_apoyo = None
        self.camara.colocar_ya()
        self.mundo.marcar_checkpoint(self.sim.checkpoint)
        self.mundo.sincronizar(self.sim)
        self._poner_estado(JUGANDO)
        if getattr(self, "_extra", None) is not None:                    # misiones visuales
            self._extra.reiniciar()

    def _salir(self):
        if self._salir_a is None:
            return
        if self._con_antesala:                   # salida animada por la antesala (una sola vez)
            if self._saliendo:
                return
            self._saliendo = True
            if self._abrir_salida():
                return
            self._recuperar_camara()             # respaldo: la salida de siempre, sin animación
            if self.estado == SALIENDO:
                self.estado = FIN
        self._salir_a()

    # -- Entrada --

    def input(self, key):
        if self.estado in (ANTESALA, SALIENDO):  # la antesala no deja pasar teclas al nivel (saltar: saltar_antesala)
            return
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
        if not avance and not lateral:          # MANDO: sin teclas, manda el palo izquierdo
            try:
                from frontend import mando_calculos as mc
                lateral, avance = mc.palo(held_keys)
            except Exception:                   # noqa: BLE001
                pass
        yaw = math.radians(self.camara.yaw)
        return (math.sin(yaw) * avance + math.cos(yaw) * lateral,
                math.cos(yaw) * avance - math.sin(yaw) * lateral)

    # -- Frame --

    def update(self):
        if self.estado in (ANTESALA, SALIENDO):
            self._avanzar_antesala(min(time.dt, 0.1))
            return
        if self._descartar_salto:               # la pulsación que saltó la antesala no salta en el nivel
            self._descartar_salto = False
            self._salto = False
        if self.sim is not None and self.estado == FIN and self.mundo is not None and self.mundo.visual:
            self.mundo.sincronizar(self.sim, min(time.dt, DT_MAX))      # que los efectos de la meta terminen de animarse
            if getattr(self, "_extra", None) is not None:                # misiones visuales: orbe y medalla de la meta
                self._extra.tras_paso([], min(time.dt, DT_MAX))
            self.hud.avanzar(min(time.dt, DT_MAX))
            if cc.camara_parkour_estable_activa():          # la cámara termina de asentarse sobre la meta
                self._seguir_con_camara(min(time.dt, DT_MAX))
                self._fov_extra = pvc.suavizar_fov(self._fov_extra, 0.0, min(time.dt, DT_MAX))
                self.camara.fov_extra = self._fov_extra
            return
        if self.sim is None or self.estado != JUGANDO:
            return
        dt = min(time.dt, DT_MAX)
        mx, mz = self._direccion()
        # Misiones visuales: cámara lenta = menos tiempo de simulación este frame (el cronómetro es ese mismo tiempo).
        dt_sim = self._extra.escala_tiempo(dt) if getattr(self, "_extra", None) is not None else dt
        pasos = max(1, math.ceil(dt_sim / PASO_MAX))
        eventos = []
        for i in range(pasos):
            eventos += self.sim.paso(dt_sim / pasos, mx, mz, salto=self._salto and i == 0)
        self._salto = False
        self._seguir_con_camara(dt)
        self._ajustar_fov(dt)
        parkour_minimapa.actualizar_altura(self.sim.y)
        self.mundo.orientar_avatar(mx, mz, dt)
        self.mundo.sincronizar(self.sim, dt)
        self.hud.actualizar(self.sim, self.nivel, dt)
        self._procesar(eventos)
        if getattr(self, "_extra", None) is not None:                    # misiones visuales (nunca lanza)
            self._extra.tras_paso(eventos, dt)

    def _seguir_con_camara(self, dt):
        _, alto = self.sim.soporte_actual()
        if cc.camara_parkour_estable_activa():
            en_aire = self.sim.vertical.en_aire
            if not en_aire and alto is not None:
                self._y_apoyo = alto
            objetivo = cc.objetivo_altura_parkour(self.sim.y, alto, en_aire, self._y_apoyo)
            self._y_camara = cc.suavizar_altura(self._y_camara, objetivo, dt, RAPIDEZ_CAMARA_Y)
            return
        if alto is not None:
            self._y_camara += (alto - self._y_camara) * (1 - math.exp(-RAPIDEZ_CAMARA_Y * dt))

    # FOV extra suave (solo con el aspecto nuevo): se abre un poco al caer rápido y al subir; no toca los controles.
    def _ajustar_fov(self, dt):
        if not self.mundo.visual:
            return
        v = self.sim.vertical
        meta = pvc.fov_extra_objetivo(v.vy, v.en_aire)
        self._fov_extra = pvc.suavizar_fov(self._fov_extra, meta, dt)
        self.camara.fov_extra = self._fov_extra

    def _procesar(self, eventos):
        for evento in eventos:
            self.mundo.reaccionar(evento, self.sim)
            if evento == "caida":
                self.hud.destello(mat.NEON_ROJO)
                self.hud.avisar(f"Caíste: +{self.nivel.penalizacion_caida_s:g} s", mat.NEON_ROJO)
                self._y_camara = self.sim.y
                self.camara.colocar_ya()
                self.mundo.marcar_checkpoint(self.sim.checkpoint)
            elif evento.startswith("checkpoint:"):
                self.hud.destello(mat.NEON_VERDE, 0.28)
                purga = getattr(self.nivel, "purga", None)
                if not (purga and evento == f"checkpoint:{purga.get('activa_en')}"):   # ahí manda el aviso de la purga
                    self.hud.avisar("¡Checkpoint!", mat.NEON_VERDE)
                self.mundo.marcar_checkpoint(self.sim.checkpoint)
            elif evento.startswith("interruptor:"):
                self.hud.avisar("¡Interruptor activado! Aparecen plataformas", mat.NEON_MAGENTA)
            elif evento.startswith("interruptor_apagado:"):
                self.hud.avisar("El interruptor se apagó")
            elif evento == "meta":
                self.hud.destello(mat.NEON_AMARILLO, 0.4)
                self._terminar()

    def _terminar(self):
        resultado = self.sim.resultado()
        self.resultados[self.nivel.id] = resultado
        estado = self._game_state()
        nueva = pk.otorgar_recompensa(self.nivel, resultado, estado)
        self._poner_estado(FIN)
        if getattr(self, "_extra", None) is not None:                    # misiones visuales: fantasma y medalla
            self._extra.al_terminar(resultado)
        self.hud.mostrar_resultado(resultado, nueva_evidencia=nueva, con_estado=estado is not None,
                                   hay_recompensa=bool(self.nivel.recompensa.get("evidencia")))
        if self._al_terminar is not None:
            self._al_terminar(resultado, nueva)
