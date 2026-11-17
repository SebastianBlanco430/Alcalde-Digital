# Adaptadores de los tutoriales de las misiones que NO son minijuegos de verificar (Ursina): investigación (interrogatorio), y los
# que se añaden después. Misma interfaz que frontend/tutorial_mision_minijuegos.py (crear_vista, elemento, elemento_tecla,
# poner_foco, enviar_tecla, avanzar_juego, avanzar_visual, armar_turno, error, camara, cerrar), más un `contexto` con la escena
# anfitriona: estos tipos no se abren en la escena de minijuegos sino en la suya.
#
# INVESTIGACIÓN. El tutorial se juega DENTRO de la escena real del mundo digital (EscenaMundoDigital): durante la demo la escena
# trabaja con un caso propio (backend/datos/casos_demo/tutorial_interrogatorio.json), una sesión propia y un GameState DESECHABLE
# que nunca se guarda. Al cerrar, se devuelve a la escena exactamente lo que tenía (partida, caso, sesión, decorado, botones).
#   - Las entradas reales de la escena se sustituyen mientras dura el tutorial: Escape, K, U y P no hacen nada (Escape salta el
#     tutorial, no cierra la sesión del caso real); «Salir» nunca se ejecuta; el botón del parkour se esconde.
#   - En «Ahora tú» solo vale la acusación señalada; la otra se explica y no cambia nada.

import json
from pathlib import Path

from backend.logica import evidencia
from backend.logica.game_state import GameState

RUTA_DATOS = Path(__file__).resolve().parent.parent / "backend" / "datos"
TECLAS_PERMITIDAS = ("1", "2", "3", "4", "5", "6", "7", "8", "9", "enter", "space", "return")


class AdaptadorInvestigacion:

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        self.escena = (contexto or {})["escena"]
        self._guardado = None
        self._clave_turno = None
        self._al_acertar = self._al_fallar = None
        self._demo_decorado = None
        self._accion_original = None
        self._acciones_originales = {}

    # -- Vista: la propia escena del mundo digital, con el caso de demo --

    def crear_vista(self, padre, al_terminar):
        from backend.logica.casos import Caso, SesionCaso
        escena = self.escena
        ruta = RUTA_DATOS / self.guion["caso_demo"]["archivo"]
        with open(ruta, encoding="utf-8") as archivo:
            caso = Caso.desde_dict(json.load(archivo))
        gs = GameState()                                  # desechable: no es el de la partida y nunca se guarda
        for id_evidencia in caso.evidencias:
            evidencia.otorgar(gs, id_evidencia, "tutorial")
        self._guardado = {"gs": getattr(escena, "_gs", None), "caso": escena._caso, "sesion": escena._sesion,
                          "decorado": escena._decorado, "modo": escena._modo,
                          "segundo": getattr(escena, "_segundo_parkour", None)}
        self._accion_original = escena._accion_fila
        self._acciones_originales = dict(escena.interfaz._acciones)
        escena._gs, escena._caso, escena._modo = gs, caso, "opciones"
        escena._sesion = SesionCaso(caso, gs)
        self._demo_decorado = escena._decorado_de(caso)
        escena._decorado = self._demo_decorado
        for d in escena._decorados.values():
            d.enabled = d is self._demo_decorado
        escena.interfaz.fijar_caso(caso)
        escena.interfaz.mostrar_enlace(None, None, "k", None)          # sin botón del parkour durante la demo
        if self._guardado["segundo"] is not None:
            self._guardado["segundo"].enabled = False
        escena.input = lambda key: None                                 # Escape/K/U/P de la escena real: nada
        escena._accion_fila = self._puerta
        escena.interfaz._acciones["fila"] = self._puerta
        escena._refrescar(colocar=True)
        return escena

    def _puerta(self, fila):
        """Toda fila elegida (clic o teclado) pasa por aquí: «Salir» nunca; en «Ahora tú» solo la señalada."""
        if fila.tipo == "salir":
            return
        if self._clave_turno is not None and fila.clave != self._clave_turno:
            if self._al_fallar is not None:
                self._al_fallar()
            return
        self._accion_original(fila)
        if self._clave_turno is not None and fila.clave == self._clave_turno and self._al_acertar is not None:
            self._al_acertar()

    # -- Señalar y mandar entradas --

    def _filas(self):
        return list(getattr(self.escena, "_filas", []) or [])

    def elemento(self, vista, foco):
        botones = getattr(self.escena.interfaz, "_botones", None)
        if botones and foco < len(botones) and botones[foco].enabled:
            return botones[foco]
        return getattr(self.escena.interfaz, "panel_opciones", None)

    def elemento_tecla(self, vista, k):
        return self.elemento(vista, int(k) - 1) if str(k).isdigit() else None

    def poner_foco(self, vista, foco):
        """Las filas no tienen foco de teclado: se eligen por número."""

    def enviar_tecla(self, vista, k):
        if k not in TECLAS_PERMITIDAS:
            return
        escena = self.escena
        if k in ("enter", "space", "return"):
            filas = self._filas()
            if len(filas) == 1 and filas[0].tipo == "continuar":
                self._puerta(filas[0])
            return
        i = int(k) - 1
        filas = self._filas()
        if 0 <= i < len(filas) and filas[i].habilitada:
            self._puerta(filas[i])
        elif 0 <= i < len(filas) and filas[i].motivo:
            escena.interfaz.mostrar_mensaje(filas[i].motivo)

    def error(self, vista, paso):
        """El error a propósito: presenta la prueba equivocada con la acción real de la escena."""
        filas = self._filas()
        if 0 <= paso["foco"] < len(filas):
            self._puerta(filas[paso["foco"]])

    def avanzar_juego(self, vista, dt):
        """La escena avanza sola cada frame (decorado, texto letra a letra, reacciones)."""

    def avanzar_visual(self, vista, dt):
        """Ídem."""

    def camara(self, vista, paso):
        """Sin cámara propia: la escena ya enfoca al personaje."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        filas = self._filas()
        self._clave_turno = filas[paso["foco"]].clave
        self._al_acertar, self._al_fallar = al_acertar, al_fallar

    # -- Cierre: la escena vuelve a ser exactamente la del caso real --

    def cerrar(self, vista):
        escena, g = self.escena, self._guardado
        if g is None:
            return
        self._guardado = None
        self._clave_turno = None
        escena.__dict__.pop("input", None)
        escena.__dict__.pop("_accion_fila", None)
        escena._gs, escena._caso, escena._sesion, escena._modo = g["gs"], g["caso"], g["sesion"], g["modo"]
        escena._decorado = g["decorado"]                       # lo esencial primero; lo visual, después
        try:
            escena.interfaz._acciones.update(self._acciones_originales)
        except Exception:                                      # noqa: BLE001
            pass
        demo = self._demo_decorado
        if demo is not None:
            for id_, d in list(escena._decorados.items()):
                if d is demo:
                    del escena._decorados[id_]
            try:
                from frontend.componentes import destruir_arbol
                destruir_arbol(demo)
            except Exception:                    # noqa: BLE001  limpieza de mejor esfuerzo
                pass
        escena._decorado = g["decorado"]
        for d in escena._decorados.values():
            d.enabled = d is g["decorado"]
        if g["segundo"] is not None:
            g["segundo"].enabled = True
        if g["caso"] is not None:
            escena.interfaz.fijar_caso(g["caso"])
            escena._refrescar(colocar=True)
            escena._refrescar_enlace_parkour()


class AdaptadorParkour:
    """Parkour del mundo digital: la escena real (EscenaParkour) con la carrera REAL en pausa. «Mira»: sobrevuelo de cámara del
    inicio al orbe (la carrera no corre). «Ahora tú»: una Simulacion PROPIA de práctica (la real queda intacta) con el reloj y las
    caídas a cero siempre: no cuenta ninguna caída, tiempo, fantasma ni medalla. Al cerrar, la escena recupera su carrera."""

    TECLAS_AVANCE = ("w", "a", "s", "d", "up arrow", "down arrow", "left arrow", "right arrow")

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        self.escena = (contexto or {})["escena"]
        self._guardado = None
        self._camara = None
        self._practica = False
        self._fase = 0
        self._al_acertar = self._al_fallar = None
        self._input_original = None

    def crear_vista(self, padre, al_terminar):
        escena = self.escena
        self._guardado = {"sim": escena.sim, "objetivo": escena.camara.objetivo, "y_camara": escena._y_camara}
        self._input_original = escena.input
        escena.input = lambda key: None                  # Escape/R de la escena real: nada (Escape salta el tutorial)
        escena._terminar = lambda: None                  # la práctica nunca llega a la meta real
        escena._poner_estado("tutorial")                 # sin simulación ni teclas de juego mientras se mira
        return escena

    # -- Cámara: sobrevuelo corto por la ruta (el nivel decide inicio y meta) --

    def _punto(self, a):
        nivel = self.escena.nivel
        p = nivel.plataformas[nivel.meta if a == "meta" else nivel.inicio]
        return (p.x, p.y, p.z)

    def camara(self, vista, paso):
        escena = self.escena
        desde = self._camara["pos"] if self._camara else self._punto("inicio")
        self._camara = {"desde": desde, "hasta": self._punto(paso["a"]), "t": 0.0, "pos": desde,
                        "dur": max(0.05, float(paso.get("s", 2.5)))}
        escena.camara.objetivo = lambda: (self._camara["pos"][0], self._camara["pos"][2])

    def avanzar_visual(self, vista, dt):
        escena = self.escena
        if self._practica and escena.sim is not None:
            escena.sim.t = 0.0                           # el reloj de la práctica no corre
            escena.sim.caidas = 0
            return
        c = self._camara
        if c is None:
            return
        from frontend import banderas_visuales as bv
        c["t"] = min(c["dur"], c["t"] + dt)
        f = 1.0 if bv.reducir_movimiento() else c["t"] / c["dur"]
        f = f * f * (3 - 2 * f)
        c["pos"] = tuple(c["desde"][i] + (c["hasta"][i] - c["desde"][i]) * f for i in range(3))
        escena._y_camara = c["pos"][1]

    # -- Señalar y entradas --

    def elemento(self, vista, foco):
        return None

    def elemento_tecla(self, vista, k):
        return None

    def poner_foco(self, vista, foco):
        """Sin elementos que señalar."""

    def error(self, vista, paso):
        """Sin error a propósito."""

    def avanzar_juego(self, vista, dt):
        """La práctica corre sola en la escena (update real); no hay tiempo de juego propio de la demo."""

    def _paso_turno(self):
        return next(p for p in self.guion["pasos"] if p["accion"] == "turno_jugador")

    def enviar_tecla(self, vista, k):
        if not self._practica:
            return
        if k in ("space", "r"):
            self._input_original(k)
        if k != "space":
            return
        from ursina import held_keys
        corriendo = any(held_keys[t] for t in self.TECLAS_AVANCE)
        if not corriendo:                                              # MANDO: el palo izquierdo también es avanzar
            from frontend import mando_calculos
            corriendo = mando_calculos.palo(held_keys) != (0.0, 0.0)
        paso = self._paso_turno()
        if self._fase == 0:
            self._fase = 1
            self._al_fallar(paso["texto2"], True)        # «saltaste»: ahora corre y salta
        elif self._fase == 1 and corriendo:
            self._fase = 2
            self._al_acertar()
        elif self._fase == 1:
            self._al_fallar(paso["si_falla"], False)

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        """Práctica: Simulacion propia en la plataforma de inicio, con la carrera real guardada aparte."""
        from ursina import mouse

        from backend.logica import parkour_calculos as pk
        escena = self.escena
        self._al_acertar, self._al_fallar = al_acertar, al_fallar
        escena.camara.objetivo = self._guardado["objetivo"]            # vuelve a seguir al jugador
        escena.sim = pk.Simulacion(escena.nivel)
        escena._y_camara, escena._y_apoyo = escena.sim.y, None
        escena.camara.colocar_ya()
        escena.mundo.marcar_checkpoint(escena.sim.checkpoint)
        escena.mundo.sincronizar(escena.sim)
        escena._poner_estado("jugando")
        mouse.locked = False                                           # el botón «Saltar tutorial» tiene que poder pulsarse
        try:                                                           # MANDO: aquí el palo camina, no mueve el cursor
            from frontend import mando
            mando.pausar_cursor(True)
        except Exception:                                              # noqa: BLE001
            pass
        self._practica, self._fase = True, 0

    # -- Cierre: la escena recupera su carrera, intacta --

    def cerrar(self, vista):
        escena, g = self.escena, self._guardado
        if g is None:
            return
        self._guardado = None
        self._practica = False
        try:
            from frontend import mando
            mando.pausar_cursor(False)
        except Exception:                                              # noqa: BLE001
            pass
        escena.__dict__.pop("input", None)
        escena.__dict__.pop("_terminar", None)
        escena.camara.objetivo = g["objetivo"]
        escena.sim = g["sim"]
        escena._y_camara, escena._y_apoyo = g["y_camara"], None
        escena._poner_estado("jugando")
        escena.camara.colocar_ya()
        escena.mundo.marcar_checkpoint(escena.sim.checkpoint)
        escena.mundo.sincronizar(escena.sim)
        escena.hud.actualizar(escena.sim, escena.nivel, 0.0)
        extra = getattr(escena, "_extra", None)
        if extra is not None:                    # el fantasma y los discos vuelven a empezar (la práctica los pudo mover)
            extra.reiniciar()


class AdaptadorBoton2:
    """Novedad de UN bocadillo: el botón de la tecla U (segundo parkour) en la escena del caso. No cambia nada del caso: solo
    señala el botón; las entradas reales de la escena (Escape, U, clics) quedan quietas mientras dura."""

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        self.escena = (contexto or {})["escena"]
        self._activo = False

    def crear_vista(self, padre, al_terminar):
        escena = self.escena
        if getattr(escena, "_segundo_parkour", None) is None:
            raise RuntimeError("sin segundo botón que señalar")
        escena.input = lambda key: None
        self._activo = True
        return escena

    def elemento(self, vista, foco):
        segundo = getattr(self.escena, "_segundo_parkour", None)
        return getattr(segundo, "boton", None)

    def elemento_tecla(self, vista, k):
        return None

    def poner_foco(self, vista, foco):
        """Nada que enfocar."""

    def enviar_tecla(self, vista, k):
        """Las teclas no llegan a la escena."""

    def error(self, vista, paso):
        """Sin error a propósito."""

    def avanzar_juego(self, vista, dt):
        """Sin juego."""

    def avanzar_visual(self, vista, dt):
        """Sin efectos propios."""

    def camara(self, vista, paso):
        """Sin cámara."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        raise NotImplementedError("no tiene «Ahora tú»")

    def cerrar(self, vista):
        if self._activo:
            self._activo = False
            self.escena.__dict__.pop("input", None)


ADAPTADORES = {"investigacion": AdaptadorInvestigacion, "parkour": AdaptadorParkour, "parkour_boton2": AdaptadorBoton2}
