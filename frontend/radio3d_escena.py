# Emisión de la Rádio Comunitária en 3D (Ursina; docs/RADIO_3D.md). Cuando la radio emite, la cámara del juego deja al
# jugador, se acerca a la torre de la radio (frontend/radio_torre_modelo.py) y da vueltas alrededor de la antena durante
# TODA la emisión. Del resto de la escena solo cambian el CIELO (noche estrellada con luna, amanecer o atardecer del día
# 7, según vineta["radio_momento"]) y el GLOBO: el de las cinemáticas (frontend/globo_dialogo.py), con el rótulo amarillo
# «Rádio Comunitária» en la esquina y la línea del recuento. El HUD se esconde; los NPC siguen con lo suyo.
#
# Contrato (frontend/radio_emision.py la crea, dentro del fundido de frontend/radio_fundido.py): `.terminada`,
# `.saltar()`, `al_poner(vineta, indice)` al poner cada línea y `al_terminar()` una sola vez, DESPUÉS de devolver cámara,
# HUD, cielo y ratón. Cada línea
# pasa sola a su tiempo de lectura (1,5 s + 0,06 s por carácter, mínimo 2,5 s); Espacio, Enter o clic adelantan y Escape
# salta la emisión entera. La pausa, el reloj y los controles ya los frena frontend/radio_registro.py (la emisión es un
# bloqueador de la escena del mundo).
# Las cuentas (órbita, horas, estrellas, rótulo) están en frontend/radio3d_camara_calculos.py.
# BANDERA: ALCALDE_RADIO3D. REDUCIR MOVIMIENTO: plano fijo de la torre, sin acercamiento ni giro.

import sys

from ursina import Entity, Mesh, camera, color, destroy, time

from frontend import ambiente_vivo, banderas_visuales
from frontend import radio3d_camara_calculos as r3c
from frontend.componentes import destruir_arbol
from frontend.globo_dialogo import GloboDialogo

TECLAS_SEGUIR = ("space", "enter", "left mouse down", "gamepad a")
TECLAS_SALTAR = ("escape", "gamepad b", "gamepad start")
Z_UI = -0.95
FRAMES_GUARDIA = 4              # tras cerrar: frames en que se cierra la pausa si el Escape la abrió
DT_MAXIMO = 0.1                 # un frame largo (carga) no se come el acercamiento
ESCALA_ESTRELLAS = 0.94         # dentro de la cúpula del cielo (que mide 1 en su escala)
GROSOR_ESTRELLA = 2.5
# Hijos de camera.ui que NO se esconden (capas de efectos y del motor), como en frontend/final_animado/director.py.
NO_ESCONDER = ("tinta", "cel", "niebla", "pase", "filtro", "dalton", "postpro", "vineta", "viñeta", "tinte", "fundido",
               "transicion", "cursor", "mando", "pantalla_carga", "pixel", "suaviz", "msaa")


def _aviso(texto):
    print(f"[radio3d] {texto}", file=sys.stderr)


def torre_de(escena):
    return getattr(getattr(escena, "ciudad", None), "radio_torre", None)


def disponible(escena):
    """¿Se puede emitir en 3D? Bandera, torre construida y la cámara de tercera persona del mundo."""
    return r3c.activo() and torre_de(escena) is not None and getattr(escena, "camara", None) is not None


class EmisionRadio3D(Entity):

    def __init__(self, escena, vinetas, al_terminar, al_poner=None, guardia=None):
        super().__init__(parent=camera.ui, z=Z_UI, name="radio3d_emision")
        self.escena, self.vinetas = escena, list(vinetas)
        self._al_terminar, self._al_poner, self._guardia = al_terminar, al_poner, guardia
        self.torre = torre_de(escena)
        self.terminada = False
        self.indice = -1
        self.t = 0.0                   # reloj de la órbita
        self.t_vineta = 0.0
        self._segundos = 0.0
        self._momento = None
        self._previo = None
        self._estrellas = None
        self._frames_guardia = 0
        self.reducir = bool(banderas_visuales.reducir_movimiento())
        self.preset = r3c.orbita()
        self.globo = GloboDialogo(parent=self)
        self._tomar_escena()
        self._siguiente()

    # -- Escena: se toma al empezar y se devuelve al terminar (cada paso por separado) --------------------------------

    def _tomar_escena(self):
        escena = self.escena
        posicion = tuple(camera.world_position)
        mirada = tuple(camera.world_position + camera.forward * 10)
        self._inicio = (posicion, mirada)
        self._angulo0 = r3c.angulo_inicial((posicion[0], posicion[2]), self.torre.centro)
        self._previo = {"hud": bool(getattr(escena.hud, "visible", True)), "fov": camera.fov,
                        "hora": getattr(ambiente_vivo, "_hora_forzada", None)}
        escena.hud.visible = False
        self._esconder_ui_ajena()
        escena.camara.tomar_control()
        self._colocar_camara()
        self._sincronizar_raton()

    def _esconder_ui_ajena(self):
        """Esconde lo que cuelga de camera.ui fuera del HUD y está a la vista (avisos, teléfono), no las capas de
        efectos."""
        self._escondidos = []
        for hijo in list(camera.ui.children):
            try:
                if (hijo is self or hijo is self.escena.hud or hijo is getattr(camera, "overlay", None)
                        or not hijo.enabled or not hijo.visible):
                    continue
                nombre = (type(hijo).__name__ + " " + str(getattr(hijo, "name", ""))).lower()
                if any(clave in nombre for clave in NO_ESCONDER):
                    continue
                hijo.visible = False
                self._escondidos.append(hijo)
            except Exception:
                continue

    def _escena_activa(self):
        try:
            return bool(getattr(self.escena, "enabled", True)) and bool(getattr(self.escena.hud, "enabled", True))
        except Exception:
            return False

    def _restaurar(self):
        previo, self._previo = self._previo, None
        if previo is None:
            return
        escena = self.escena
        pasos = [lambda: setattr(escena.hud, "visible", previo["hud"]),
                 self._devolver_ui_ajena,
                 self._quitar_estrellas,
                 lambda: ambiente_vivo.fijar_hora_forzada(previo["hora"]),
                 self._repintar_cielo]
        if self._escena_activa():      # si ya se salió del mundo, la cámara es de otra escena: no se coloca
            pasos += [lambda: setattr(camera, "fov", previo["fov"]),
                      escena.camara.soltar_control,
                      escena.camara.colocar_ya,
                      self._sincronizar_raton]
        else:
            pasos.append(escena.camara.soltar_control)
        for paso in pasos:
            try:
                paso()
            except Exception as error:
                _aviso(f"restaurar: {type(error).__name__}: {error}")

    def _devolver_ui_ajena(self):
        escondidos, self._escondidos = self._escondidos, []
        for hijo in escondidos:
            try:
                if hijo is not None and not hijo.is_empty():
                    hijo.visible = True
            except Exception:
                continue

    def _sincronizar_raton(self):
        sincronizar = getattr(self.escena, "_sincronizar_raton", None)
        if callable(sincronizar):
            sincronizar()

    # -- Cielo: la hora del momento y, de noche, estrellas --------------------------------------------------------------

    def _cielo(self):
        return getattr(getattr(self.escena, "ciudad", None), "cielo", None)

    def _repintar_cielo(self):
        cielo = self._cielo()
        if cielo is not None and hasattr(cielo, "aplicar_hora"):
            cielo.aplicar_hora(type(cielo)._hora() if hasattr(type(cielo), "_hora") else None)
            cielo._t_ciclo = 0.0

    def _aplicar_momento(self, momento):
        momento = momento or r3c.MOMENTO_POR_DEFECTO
        if momento == self._momento:
            return
        self._momento = momento
        try:
            ambiente_vivo.fijar_hora_forzada(r3c.hora_de_momento(momento))
            self._repintar_cielo()
        except Exception as error:
            _aviso(f"cielo sin cambiar ({type(error).__name__}: {error})")
        if r3c.con_estrellas(momento):
            self._poner_estrellas()
        else:
            self._quitar_estrellas()

    def _poner_estrellas(self):
        cielo = self._cielo()
        if self._estrellas is not None or cielo is None:
            return
        puntos = r3c.estrellas()
        vertices = [(x * ESCALA_ESTRELLAS, y * ESCALA_ESTRELLAS, z * ESCALA_ESTRELLAS) for x, y, z, _ in puntos]
        colores = [color.rgba(1, 1, 0.94, b) for *_, b in puntos]
        self._estrellas = Entity(parent=cielo, model=Mesh(vertices=vertices, colors=colores, mode="point",
                                                          thickness=GROSOR_ESTRELLA),
                                 shader=None, unlit=True, name="radio3d_estrellas")
        self._estrellas.setBin("background", 2)
        self._estrellas.setDepthWrite(False)
        self._estrellas.setFogOff()
        self._estrellas.setLightOff()

    def _quitar_estrellas(self):
        if self._estrellas is not None:
            destruir_arbol(self._estrellas)
            self._estrellas = None

    # -- Líneas -----------------------------------------------------------------------------------------------------

    def _siguiente(self):
        self.indice += 1
        if self.indice >= len(self.vinetas):
            self._terminar()
            return
        vineta = self.vinetas[self.indice]
        self.t_vineta = 0.0
        self._segundos = r3c.segundos_vineta(vineta)
        self._aplicar_momento(vineta.get("radio_momento"))
        self.globo.mostrar(r3c.nombre_rotulo(vineta.get("titulo")), str(vineta.get("texto") or ""))
        if self._al_poner is not None:
            try:
                self._al_poner(vineta, self.indice)
            except Exception as error:
                _aviso(f"al_poner: {type(error).__name__}: {error}")

    def saltar(self):
        if not self.terminada:
            self._terminar()

    def _terminar(self):
        self.terminada = True
        self._frames_guardia = FRAMES_GUARDIA
        try:
            self.globo.ocultar()
        except Exception:
            pass
        self._restaurar()
        al_terminar, self._al_terminar = self._al_terminar, None
        if al_terminar is not None:
            al_terminar()

    # -- Frame --------------------------------------------------------------------------------------------------------

    def _colocar_camara(self):
        torre = self.torre
        posicion, pitch, yaw = r3c.toma(self.t, self._inicio, torre.centro, torre.y_base, torre.alto, self.preset,
                                        self._angulo0, self.reducir)
        camera.position = posicion
        camera.rotation = (pitch, yaw, 0)

    def _vigilar_pausa(self):
        if self._guardia is not None:
            try:
                self._guardia()
            except Exception:
                pass

    def update(self):
        self._vigilar_pausa()
        if self.terminada:
            self._frames_guardia -= 1
            if self._frames_guardia <= 0:
                destroy(self)
            return
        dt = min(time.dt, DT_MAXIMO)
        self.t += dt
        self.t_vineta += dt
        try:
            self._colocar_camara()
        except Exception as error:     # sin torre o sin cámara: se cierra limpia y la noche sigue su curso
            _aviso(f"cámara: {type(error).__name__}: {error}")
            self._terminar()
            return
        if self.t_vineta >= self._segundos:
            self._siguiente()

    def input(self, key):
        if self.terminada:
            return
        if key in TECLAS_SALTAR:
            self.saltar()
        elif key in TECLAS_SEGUIR:
            self._siguiente()
