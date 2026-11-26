# Prólogo de Alcalde Digital en 3D (Ursina), rodado en la Ciudad Nova real con el motor del juego y sus modelos. Se ve
# en una partida LOCAL NUEVA, DESPUÉS de elegir personaje (al entrar al mundo) y ANTES de la cinemática del tutorial
# (frontend/intro_cinematica.py, que lanza frontend/registro_tutorial.py y no cambia). Contexto de Ciudad Nova y de la
# elección, un presagio de los dos futuros y una pantalla negra: «La decisión depende de ti y de tus acciones.». Al
# terminar la pantalla queda en negro y de ahí sale el tutorial.
#
#   - Qué se ve: frontend/prologo_calculos.py con backend/datos/prologo_cinematica.json. Los tramos «animado» los rueda
#     el director del final animado (frontend/final_animado/director.py: cámara, actores de Tomás Arenas, Octavio Ruedas
#     y los vecinos, estado de la ciudad, subtítulos, «Mantén para saltar»), con un guion propio; las «cartela», este
#     módulo (negro + texto).
#   - Un velo negro propio (camera.ui, por delante del director) tapa las cargas y los cortes entre tramos: el jugador
#     no ve el mundo hasta que empieza el primer plano, y al acabar sigue en negro hasta que el tutorial toma la escena.
#     Se llama «fundido_prologo» para que el director no lo esconda (final_animado.director.NO_ESCONDER).
#   - Mientras dura: escena._cinematica = True (reloj parado, sin pausa, controles congelados) y el HUD escondido. El
#     vigía del tutorial espera a que _cinematica vuelva a False: así su cinemática sale justo después.
#   - Saltar: mantener Espacio/Escape en los planos (como el final) o Escape en una cartela salta TODO el prólogo; Espacio,
#     Enter o clic en una cartela pasan a lo siguiente. Si algo falla, se salta lo que falta y el juego sigue.
#   - Voz de la narradora (frontend/narrador.py, ALCALDE_NARRADOR): en los planos la pone el director; en las cartelas,
#     este módulo (la cartela dura lo que su voz si hace falta, pc.duracion_cartela) y la calla al avanzar, saltar,
#     abortar o cerrar.
#
# BANDERA. PROLOGO = True; ALCALDE_PROLOGO=0 lo quita (se va directo al tutorial). Lo carga main.py (MODULOS_HILO).
#
#   activo()
#   registrar(gestor, conexion, escena_mundo)      engancha escena_mundo.al_entrar
#   crear_prologo(escena, conexion, al_terminar)   -> entidad (.terminada, .saltar())

import os
import sys

from frontend import narrador
from frontend import prologo_calculos as pc

PROLOGO = True
NOMBRE = "fundido_prologo"
Z_CAPA = -0.97                  # por delante del director del final animado (-0.95) y de todo el HUD
NEGRO_FINAL_S = 0.4             # negro sostenido tras la última cartela antes de soltar la escena
ACLARAR_S = 0.8                 # después, el velo se aclara sobre lo que venga (el tutorial)
PX_CARTELA = 38
TECLAS_AVANZAR = ("space", "enter", "left mouse down", "gamepad a")
TECLAS_SALTAR = ("escape", "gamepad b", "gamepad start")


def activo():
    """¿Hay prólogo? ALCALDE_PROLOGO=1/0 manda sobre PROLOGO."""
    valor = os.environ.get("ALCALDE_PROLOGO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PROLOGO)


def _aviso(texto):
    print(f"[prologo] {texto}", file=sys.stderr)


def _decir(texto):
    try:
        narrador.decir(texto)
    except Exception as error:
        _aviso(f"voz: {type(error).__name__}: {error}")


def _callar():
    try:
        narrador.callar()
    except Exception as error:
        _aviso(f"callar: {type(error).__name__}: {error}")


def _roles(escena):
    try:
        return [j.rol for j in escena.flujo.sesion.jugadores()]
    except Exception:
        return []


def _crear_animado(escena, conexion, tramo, guion, al_terminar, al_fallo, guardia):
    from frontend.final_animado.director import crear_final_animado
    return crear_final_animado(escena, tramo["final"], _roles(escena), al_terminar, al_fallo, conexion=conexion,
                               guardia=guardia, guion=pc.guion_animado(guion, tramo))


def crear_prologo(escena, conexion, al_terminar=None, guion=None, fabrica_animado=None):
    from ursina import Entity, Text, camera, color, destroy, time

    from frontend import diseno_adaptable, tipografia
    from frontend.componentes import escala_fuente

    guion = pc.cargar_guion() if guion is None else guion
    fabrica = fabrica_animado or _crear_animado

    class Prologo3D(Entity):

        def __init__(self):
            super().__init__(parent=camera.ui, z=Z_CAPA, name=NOMBRE)
            self.tramos = pc.tramos(guion)
            self.indice = -1
            self.fase = "siguiente"
            self.terminada = False
            self.saltada = False
            self.animado = None
            self._t = 0.0
            self._duracion = 0.0
            self._tramo_listo = None        # (saltada,) cuando el tramo animado avisó que terminó
            self._previo = {"cinematica": bool(getattr(escena, "_cinematica", False)),
                            "hud": bool(getattr(escena.hud, "visible", True))}
            self.negro = Entity(parent=self, model="quad", scale=(8.0, 2.2), color=color.black)
            self.contenido = Entity(parent=self, z=-0.01)
            self.texto = Text("", parent=self.contenido, origin=(0, 0), scale=escala_fuente(PX_CARTELA),
                              color=color.rgba(1, 1, 1, 0), font=tipografia.FUENTE_TITULO)
            diseno_adaptable.ajustar_escala(self.contenido)
            escena._cinematica = True
            escena.hud.visible = False
            self._raton()

        # -- Escena ------------------------------------------------------------------------------------------------

        def _raton(self):
            try:
                escena._sincronizar_raton()
            except Exception:
                pass

        def _guardia(self):
            # El Escape que salta también llega a la escena: que no deje la pausa abierta debajo.
            try:
                if getattr(escena, "en_pausa", False):
                    escena.alternar_pausa(False)
            except Exception:
                pass

        def _soltar(self):
            for paso in (lambda: setattr(escena, "_cinematica", self._previo["cinematica"]),
                         lambda: setattr(escena.hud, "visible", self._previo["hud"]),
                         self._raton):
                try:
                    paso()
                except Exception as error:
                    _aviso(f"soltar: {type(error).__name__}: {error}")

        # -- Frame -------------------------------------------------------------------------------------------------

        def update(self):
            dt = min(time.dt, 0.1)
            try:
                self._frame(dt)
            except Exception as error:
                _aviso(f"falló ({type(error).__name__}: {error}); se salta lo que falta")
                self._abortar()

        def _frame(self, dt):
            self._guardia()
            if self.fase == "siguiente":
                self._siguiente()
            elif self.fase == "animado":
                self._frame_animado()
            elif self.fase == "cartela":
                self._t += dt
                self.texto.color = color.rgba(1, 1, 1, pc.alfa_cartela(self._t, self._duracion))
                if self._t >= self._duracion:
                    self.fase = "siguiente"
            elif self.fase == "cierre":
                self._velo(1.0)
                self._t += dt
                if self._t >= NEGRO_FINAL_S:
                    self._terminar()
            elif self.fase == "aclarar":
                self._t += dt
                f = min(1.0, self._t / ACLARAR_S)
                self._velo(1.0 - f * f * (3 - 2 * f))
                if f >= 1.0:
                    self.fase = "fin"
                    destroy(self)

        def _velo(self, alfa):
            self.negro.enabled = alfa > 0.0
            self.negro.color = color.rgba(0, 0, 0, max(0.0, min(1.0, alfa)))

        def _siguiente(self):
            self._velo(1.0)
            self.texto.color = color.rgba(1, 1, 1, 0)
            self.indice += 1
            if self.saltada or self.indice >= len(self.tramos):
                self._al_cierre()
                return
            tramo = self.tramos[self.indice]
            if tramo["tipo"] == "cartela":
                self.fase = "cartela"
                self._t = 0.0
                self._duracion = pc.duracion_cartela(tramo["texto"])
                self.texto.text = tramo["texto"]
                _decir(tramo["texto"])
                return
            self._tramo_listo = None
            try:
                self.animado = fabrica(escena, conexion, tramo, guion, self._fin_tramo, self._fallo_tramo, self._guardia)
                self.fase = "animado"
            except Exception as error:
                _aviso(f"tramo «{tramo['final']}» sin rodar ({type(error).__name__}: {error})")
                self.animado = None

        def _frame_animado(self):
            if self._tramo_listo is not None:
                saltada, = self._tramo_listo
                self.animado = None
                self._tramo_listo = None
                if saltada:
                    self.saltada = True
                self.fase = "siguiente"
                self._velo(1.0)
                return
            # Velo encendido mientras el director funde y carga: el mundo no se ve hasta el primer plano.
            rodando = self.animado is not None and getattr(self.animado, "fase", None) in ("reproducir", "saliendo")
            self._velo(0.0 if rodando else 1.0)

        def _fin_tramo(self, saltada=False):
            self._velo(1.0)                 # ya: el director acaba de soltar la cámara del jugador
            self._tramo_listo = (bool(saltada),)

        def _fallo_tramo(self, error):
            _aviso(f"tramo animado falló ({type(error).__name__}: {error}); sigue el prólogo")
            self._fin_tramo(False)

        def _al_cierre(self):
            _callar()
            self.fase = "cierre"
            self._t = 0.0
            self._velo(1.0)
            self.texto.text = ""

        def _terminar(self):
            if self.terminada:
                return
            self.terminada = True
            _callar()
            self._soltar()
            self.fase = "aclarar"
            self._t = 0.0
            if al_terminar is not None:
                try:
                    al_terminar(self.saltada)
                except Exception as error:
                    _aviso(f"aviso final: {type(error).__name__}: {error}")

        def _abortar(self):
            _callar()
            animado, self.animado = self.animado, None
            if animado is not None and not getattr(animado, "terminada", True):
                try:
                    animado.limpiar()
                    destroy(animado)
                except Exception:
                    pass
            self.saltada = True
            self._velo(1.0)
            self._terminar()

        # -- Teclas ------------------------------------------------------------------------------------------------

        def input(self, key):
            if self.terminada or self.fase != "cartela":
                return                      # en los planos manda el director («Mantén para saltar»)
            if key in TECLAS_SALTAR:
                self.saltar()
            elif key in TECLAS_AVANZAR:
                _callar()
                self._t = max(self._t, self._duracion - pc.CARTELA_SALIDA)

        def saltar(self):
            if self.terminada:
                return
            _callar()
            self.saltada = True
            if self.fase == "animado" and self.animado is not None:
                self.animado.saltar()       # su aviso llega a _fin_tramo y de ahí al cierre
                return
            self._al_cierre()

    return Prologo3D()


# En línea el prólogo no salía. Con ALCALDE_MULTI_PARIDAD cada cliente lo ve en local al entrar a la partida (es una
# cinemática: no hay nada que sincronizar; el reloj de la sala sigue corriendo y se puede saltar como siempre).
# Al volver a una sala ya empezada (reconexión) no sale otra vez: solo si el reloj de la sala sigue en las 08:00 del día 1
# (el anfitrión lo tiene parado mientras dura el prólogo, multi_reloj.ESPERA_INICIO) o aún no llegó su hora.
def _en_linea_sin_prologo(escena_mundo):
    if getattr(escena_mundo, "online", None) is None:
        return False
    from backend.red import multi_reloj
    if not multi_reloj.activo():
        return True
    reloj = getattr(getattr(escena_mundo.flujo, "tiempo_en_linea", None), "reloj", None)
    if reloj is None or not reloj.recibido:
        return False
    from backend.logica import reloj_partida
    return reloj.dia() > 1 or reloj.hora() > reloj_partida.HORA_INICIO + 0.05


def registrar(gestor, conexion, escena_mundo):
    """Engancha la entrada al mundo: la primera vez que se ve una partida local nueva, el prólogo toma la escena ANTES
    del primer frame (el vigía del tutorial espera a que termine)."""
    if not activo():
        return None
    try:
        from frontend import registro_tutorial

        estado = {"flujo": None, "entidad": None}
        original = escena_mundo.al_entrar

        def al_entrar(*args, **kwargs):
            resultado = original(*args, **kwargs)
            try:
                _quizas_empezar()
            except Exception as error:
                _aviso(f"omitido ({type(error).__name__}: {error})")
            return resultado

        def _quizas_empezar():
            flujo = escena_mundo.flujo
            if flujo is None or flujo is estado["flujo"]:
                return
            estado["flujo"] = flujo
            restaurada = bool(getattr(conexion, "partida_restaurada", False))
            if not registro_tutorial.activo():
                conexion.partida_restaurada = False     # sin tutorial nadie la limpia: que no tape la próxima partida
            if not registro_tutorial.debe_abrirse(flujo, restaurada, _en_linea_sin_prologo(escena_mundo)):
                return
            estado["entidad"] = crear_prologo(escena_mundo, conexion)

        escena_mundo.al_entrar = al_entrar
        conexion.prologo = estado
        return estado
    except Exception as error:
        _aviso(f"no instalado ({type(error).__name__}: {error})")
        return None
