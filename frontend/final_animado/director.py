# Director del final animado (Ursina). Recorre la Ciudad Nova real con los planos del guion (finales_historia.json
# «animacion»), con fundidos, subtítulos y «Mantén para saltar». Lo lanza frontend/registro_reloj.py; contrato:
# frontend/final_animado/contrato.md.
#
#   Fases: «a_negro» (fundido a negro sobre el juego) -> «cargar» (preparar la escenografía con la pantalla en negro; dos
#   frames de respiro para que el tirón de la carga quede tapado) -> «reproducir» (línea de tiempo: entrar/avanzar de la
#   escenografía, cámara, subtítulos, negro de los cortes) -> «saliendo» (solo al saltar: fundido corto a negro) -> cerrar.
#   Cerrar = limpiar TODO (escenografía, raíces, escena devuelta) y LUEGO avisar al registro una sola vez:
#   al_terminar(saltada) o al_fallo(error).
#   - Escena tomada como en la intro: escena._cinematica = True (reloj parado, sin pausa, controles congelados), HUD
#     escondido (hud.visible = False: el chip, los avisos y el panel final cuelgan de él) y la cámara tomada. Además se
#     esconde lo que cuelga de camera.ui fuera del HUD y está a la vista (avisos del teléfono, medidor de fps…), salvo
#     las capas de efectos (no se apaga ningún efecto); al terminar vuelve cada cosa a como estaba.
#   - Todo lo creado cuelga de dos raíces: raiz3d (hija de `scene`, para la escenografía) y raizui (camera.ui).
#   - Cualquier excepción (al crear, al cargar o en un frame) -> limpiar y al_fallo(error): el registro abre las viñetas.
#   - Voz de la narradora (frontend/narrador.py, ALCALDE_NARRADOR): cada subtítulo NUEVO se dice una vez, al empezar su
#     tramo; se calla al saltar, al cerrar, al limpiar y si falla. Con escala != 1 (pruebas) no suena.

import math
import sys

from ursina import Entity, Text, camera, color, destroy, held_keys, scene, time, window

from frontend import narrador
from frontend.final_animado import _calculos as calc
from frontend.final_animado import camaras

Z_CAPA = -0.95                  # por delante de todo lo de camera.ui (panel final -0.5, viñetas -0.9)
A_NEGRO_S = 0.45                # fundido a negro inicial (tapa la carga)
FRAMES_RESPIRO = 2              # frames en negro tras preparar (el primer frame después de una carga larga llega con un dt enorme)
SALIDA_SALTAR_S = 0.35          # fundido a negro al saltar
DT_MAX = 0.1
TECLAS_SALTAR = ("space", "escape", "gamepad a", "gamepad b", "gamepad start", "gamepad x")
Y_SUBTITULO = -0.5 + 0.085      # centro del bloque de subtítulos (camera.ui)
ANCHO_SUBTITULO = 0.70          # fracción del ancho de la ventana para las líneas
ALFA_FONDO_SUBTITULO = 0.62
PUNTOS_ANILLO = 24
FRAMES_GUARDIA = 4              # tras cerrar: frames en que se cierra la pausa si el Escape la abrió
VELO_S = 0.45                   # tras cerrar: el negro se aclara sobre el panel final en este tiempo
# Hijos de camera.ui que NO se esconden (capas de efectos y cosas propias del motor). Se compara con el nombre de la
# clase y con el `name` de la entidad (en minúsculas, por subcadena).
NO_ESCONDER = ("tinta", "cel", "niebla", "pase", "filtro", "dalton", "postpro", "vineta", "viñeta", "tinte", "fundido",
               "transicion", "cursor", "mando", "pantalla_carga", "pixel", "suaviz", "msaa")


def _aviso(texto):
    print(f"[final_animado] {texto}", file=sys.stderr)


class EscenografiaNula:
    """La de pruebas: mismos 4 métodos que la real (contrato), sin hacer nada."""

    def __init__(self, escena=None, raiz3d=None, conexion=None):
        self.llamadas = []

    def preparar(self, final, roles, planos):
        self.llamadas.append(("preparar", final))

    def entrar(self, plano):
        self.llamadas.append(("entrar", plano.id))

    def avanzar(self, plano, t, dt):
        pass

    def limpiar(self):
        self.llamadas.append(("limpiar",))


def _fabrica_real(escena, raiz3d, conexion):
    from frontend.final_animado.escenografia import Escenografia      # import tardío (otro subagente)
    return Escenografia(escena, raiz3d, conexion)


class FinalAnimado(Entity):
    """Ver el comentario del módulo. `escenografia`: fábrica (escena, raiz3d, conexion) -> objeto con preparar / entrar /
    avanzar / limpiar; None = la real de escenografia.py."""

    def __init__(self, escena, final, roles, al_terminar, al_fallo, conexion=None, guardia=None, escala=1.0,
                 escenografia=None, guion=None):
        super().__init__(parent=camera.ui, z=Z_CAPA)
        self.escena = escena
        self.final = final
        self.roles = list(roles or [])
        self.conexion = conexion
        self._al_terminar = al_terminar
        self._al_fallo = al_fallo
        self._guardia = guardia
        self._fabrica = escenografia or _fabrica_real
        self.escala = max(0.0, float(escala))
        self.terminada = False
        self.saltada = False
        self.fase = "a_negro"
        self.tiempo = 0.0
        self.plano_actual = None
        self._indice = -1
        self._t_fase = 0.0
        self._respiro = FRAMES_RESPIRO
        self._cola_guardia = 0
        self._velo = None
        self._t_velo = 0.0
        self._previo = None
        self._restaurado = True
        self._escondidos = []
        self.escenografia = None
        self.raiz3d = self.raizui = None
        self.tomas = {}
        self._texto_sub = None
        self._texto_voz = None          # último subtítulo dicho por la narradora (no se toca al cambiar la ventana)
        self._alto_ventana = None
        self._tiempo_real = 0.0
        self.mediciones = []            # dt de cada frame de la fase «reproducir» (rendimiento)
        try:
            g = calc.cargar_guion(guion)
            self.planos = calc.planos_de(final, self.roles, g)
            self.linea = calc.LineaTiempo(self.planos, self.escala)
            self.estado_ciudad = calc.estado_ciudad(final, g)
            self.duracion_total = self.linea.duracion
            self.saltar_ctrl = calc.MantenerParaSaltar()
            self._texto_saltar = calc.texto_saltar(g)
            self._tomar_escena()
            self._construir_ui()
        except Exception:
            self.limpiar()
            destroy(self)                        # ni la entidad vacía queda: el registro abre las viñetas
            raise

    # -- Escena: se toma al empezar y se devuelve en restaurar() (idempotente) ---------------------------------------

    def _tomar_escena(self):
        escena = self.escena
        self._previo = {"cinematica": bool(getattr(escena, "_cinematica", False)),
                        "hud": bool(getattr(escena.hud, "visible", True)),
                        "fov": camera.fov}
        self._restaurado = False
        escena._cinematica = True
        escena.hud.visible = False
        self._esconder_ui_ajena()
        escena.camara.tomar_control()
        self._sincronizar_raton()

    def _esconder_ui_ajena(self):
        """Esconde lo que cuelga de camera.ui fuera del HUD y está a la vista (no las capas de efectos)."""
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
        """¿Sigue el mundo a la vista? (al salir de él, EscenaMundo.al_salir apaga su HUD y devuelve la cámara)."""
        try:
            return bool(getattr(self.escena, "enabled", True)) and bool(getattr(self.escena.hud, "enabled", True))
        except Exception:
            return False

    def restaurar(self):
        if self._restaurado or self._previo is None:
            return
        self._restaurado = True
        escena, previo = self.escena, self._previo
        pasos = [lambda: setattr(escena, "_cinematica", previo["cinematica"]),
                 lambda: setattr(escena.hud, "visible", previo["hud"]),
                 self._devolver_ui_ajena]
        if self._escena_activa():               # si ya se salió del mundo, la cámara es de otra escena: no se toca
            pasos += [lambda: setattr(camera, "fov", previo["fov"]),
                      escena.camara.soltar_control,
                      escena.camara.colocar_ya,
                      self._sincronizar_raton]
        else:
            pasos.append(escena.camara.soltar_control)
        for paso in pasos:              # cada paso por separado: que uno falle no deja a medias los demás
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
        try:
            self.escena._sincronizar_raton()
        except Exception:
            pass

    # -- UI: telón, subtítulos y aviso de saltar ----------------------------------------------------------------------

    def _construir_ui(self):
        from frontend import tipografia
        from frontend.componentes import escala_fuente
        self.raizui = Entity(parent=camera.ui, z=Z_CAPA)
        self.telon = Entity(parent=self.raizui, model="quad", scale=(8.0, 2.2), z=0.02, color=color.rgba(0, 0, 0, 0))
        # Subtítulos: fondo oscuro semitransparente a la medida del texto, abajo y centrado.
        self.sub = Entity(parent=self.raizui, position=(0, Y_SUBTITULO, -0.01))
        self.sub_fondo = Entity(parent=self.sub, model="quad", z=0.005, color=color.rgba(0, 0, 0, 0))
        self.sub_texto = Text("", parent=self.sub, origin=(0, 0), z=-0.005, color=color.rgba(1, 1, 1, 0),
                              font=tipografia.FUENTE_TITULO)
        self.sub_texto.line_height = 1.15
        self.sub.enabled = False
        # «Mantén para saltar»: abajo a la derecha, con un anillo de puntos que se llena.
        self.salto = Entity(parent=self.raizui, z=-0.02)
        self.salto_fondo = Entity(parent=self.salto, model="quad", z=0.005, color=color.rgba(0, 0, 0, 0))
        self.salto_texto = Text(self._texto_saltar, parent=self.salto, origin=(0.5, 0), scale=escala_fuente(16),
                                color=color.rgba(1, 1, 1, 0.9), font=tipografia.fuente_piel(titulo=True))
        self.anillo = []
        for k in range(PUNTOS_ANILLO):
            ang = 2 * math.pi * k / PUNTOS_ANILLO
            punto = Entity(parent=self.salto, model="circle", scale=0.0055,
                           position=(0.022 * math.sin(ang), 0.022 * math.cos(ang), 0), color=color.rgba(1, 1, 1, 0.3))
            self.anillo.append(punto)
        self._colocar_ui()
        self.salto.enabled = False

    def _colocar_ui(self):
        """Tamaños y posiciones según la ventana (se rehace si cambia de tamaño)."""
        alto = int(window.size[1]) if window.size else 720
        if alto == self._alto_ventana:
            return
        self._alto_ventana = alto
        aspecto = window.aspect_ratio
        self.sub_texto.scale = calc.alto_subtitulo(alto) / Text.size
        self._ancho_sub = ANCHO_SUBTITULO * aspecto
        self.salto.position = (aspecto / 2 - 0.05, -0.5 + 0.05, -0.02)    # el anillo en la esquina, el texto a su izquierda
        self.salto_texto.position = (-0.036, 0, 0)
        try:                                      # fondo oscuro del aviso: legible sobre la plaza clara
            from frontend import diseno_adaptable
            ancho = diseno_adaptable.medidor(self.salto_texto)(self._texto_saltar)
        except Exception:
            ancho = 0.2
        izquierda, derecha = -0.036 - ancho - 0.018, 0.022 + 0.016
        self.salto_fondo.position = ((izquierda + derecha) / 2, 0, 0.005)
        self.salto_fondo.scale = (derecha - izquierda, 0.066)
        self._texto_sub = None                    # se vuelve a partir con el tamaño nuevo

    def _poner_subtitulo(self, texto, alfa):
        if not texto or alfa <= 0.0:
            self.sub.enabled = False
            return
        self.sub.enabled = True
        if texto != self._texto_sub:
            self._texto_sub = texto
            from frontend import diseno_adaptable
            medir = diseno_adaptable.medidor(self.sub_texto)
            lineas, _ = calc.partir_lineas(texto, medir, self._ancho_sub, 2)
            self.sub_texto.text = "\n".join(lineas)
            ancho = max(medir(linea) for linea in lineas)
            alto_linea = calc.alto_subtitulo(self._alto_ventana or 720)
            relleno = alto_linea * 0.6
            self.sub_fondo.scale = (ancho + 2 * relleno, alto_linea * 1.15 * len(lineas) + relleno * 1.4)
        self.sub_texto.color = color.rgba(1, 1, 1, alfa)
        self.sub_fondo.color = color.rgba(0, 0, 0, ALFA_FONDO_SUBTITULO * alfa)

    def _decir_subtitulo(self, texto):
        """La voz del subtítulo, una vez, cuando empieza su tramo (aunque su alfa aún sea 0). Nunca lanza."""
        if texto == self._texto_voz:
            return
        self._texto_voz = texto
        if not texto or self.escala != 1.0:
            return
        try:
            narrador.decir(texto)
        except Exception as error:
            _aviso(f"voz: {type(error).__name__}: {error}")

    @staticmethod
    def _callar():
        try:
            narrador.callar()
        except Exception as error:
            _aviso(f"callar: {type(error).__name__}: {error}")

    def _poner_aviso_saltar(self):
        ctrl = self.saltar_ctrl
        visible = ctrl.aviso_visible and self.fase == "reproducir"
        self.salto.enabled = visible
        if not visible:
            return
        alfa = ctrl.alfa_aviso
        self.salto_texto.color = color.rgba(1, 1, 1, 0.92 * alfa)
        self.salto_fondo.color = color.rgba(0, 0, 0, ALFA_FONDO_SUBTITULO * alfa)
        llenos = int(round(ctrl.progreso * PUNTOS_ANILLO))
        for k, punto in enumerate(self.anillo):
            punto.color = color.rgba(0.98, 0.81, 0.22, alfa) if k < llenos else color.rgba(1, 1, 1, 0.32 * alfa)

    def _telon(self, alfa):
        self.telon.color = color.rgba(0, 0, 0, max(0.0, min(1.0, alfa)))

    # -- Carga ----------------------------------------------------------------------------------------------------------

    def _cargar(self):
        from frontend.final_animado import lugares
        self.raiz3d = Entity(parent=scene)
        self.escenografia = self._fabrica(self.escena, self.raiz3d, self.conexion)
        self.escenografia.preparar(self.final, list(self.roles), list(self.planos))
        mundo = self.escena._mundo
        self.tomas = camaras.tomas_de(self.planos, lugares.anclas(mundo), mundo)
        self._sonido_inicial()

    def _sonido_inicial(self):
        nombre = self.estado_ciudad.get("sonido")
        if not nombre:
            return
        try:
            from frontend import audio
            audio.obtener().efecto(nombre, 0.6)
        except Exception as error:               # sin audio no pasa nada
            _aviso(f"sonido: {type(error).__name__}: {error}")

    # -- Frame ----------------------------------------------------------------------------------------------------------

    def update(self):
        if self.terminada:
            self._frame_guardia()
            return
        try:
            self._frame(min(time.dt, DT_MAX))
        except Exception as error:
            self._fallar(error)

    def _frame_guardia(self):
        # Unos frames de guardia: el Escape que saltó el final también llega a la escena y podría abrir la pausa. Mientras,
        # el velo negro del cierre se aclara sobre el panel final (o las viñetas) y después se destruye con la entidad.
        dt = min(time.dt, DT_MAX)
        velo_vivo = self._aclarar_velo(dt)
        if self._cola_guardia > 0:
            self._cola_guardia -= 1
            try:
                if getattr(self.escena, "en_pausa", False):
                    self.escena.alternar_pausa(False)
            except Exception:
                pass
        elif not velo_vivo:
            self.enabled = False
            try:
                destroy(self)                    # ni la entidad queda en camera.ui
            except Exception:
                pass

    def _aclarar_velo(self, dt):
        velo = self._velo
        if velo is None:
            return False
        try:
            self._t_velo += dt
            f = 1.0 if VELO_S <= 0 else min(1.0, self._t_velo / VELO_S)
            if f >= 1.0:
                destroy(velo)
                self._velo = None
                return False
            velo.color = color.rgba(0, 0, 0, 1.0 - calc.suave(f))
            return True
        except Exception:
            self._quitar_velo()
            return False

    def _quitar_velo(self):
        velo, self._velo = self._velo, None
        if velo is not None:
            try:
                destroy(velo)
            except Exception:
                pass

    def _frame(self, dt):
        if not self._escena_activa():            # alguien sacó al jugador del mundo a mitad: se cierra sin más
            self.saltada = True
            self._cerrar(lambda: self._al_terminar(True))
            return
        if self._guardia is not None:
            try:
                self._guardia()
            except Exception:
                pass
        self._colocar_ui()
        if self.fase == "a_negro":
            self._t_fase += dt
            duracion = A_NEGRO_S * min(1.0, self.escala) if self.escala < 1.0 else A_NEGRO_S
            self._telon(1.0 if duracion <= 0 else self._t_fase / duracion)
            if self._t_fase >= duracion:
                self._telon(1.0)
                self.fase = "cargar"
            return
        if self.fase == "cargar":
            self._telon(1.0)
            self._cargar()
            self.fase = "respiro"
            return
        if self.fase == "respiro":
            self._telon(1.0)
            self._respiro -= 1
            if self._respiro <= 0:
                self.fase = "reproducir"
                self.tiempo = 0.0
                self.saltar_ctrl._aviso = calc.AVISO_INICIAL + self.linea.entrada
                self._colocar_plano(0.0, 0.0)
            return
        if self.fase == "reproducir":
            self.mediciones.append(time.dt)
            self.tiempo += dt
            if self.saltar_ctrl.avanzar(dt, self._mantenido()):
                self.saltada = True
                self.fase = "saliendo"
                self._t_fase = 0.0
                self._alfa_saltar = self.telon.color.a
                self.sub.enabled = False
                self.salto.enabled = False
                self._callar()
                return
            if self.tiempo >= self.duracion_total:
                self._colocar_plano(self.duracion_total, dt)
                self._telon(1.0)
                self._cerrar(lambda: self._al_terminar(False))
                return
            self._colocar_plano(self.tiempo, dt)
            self._telon(self.linea.negro(self.tiempo))
            texto, alfa = self.linea.subtitulo(self.tiempo)
            self._decir_subtitulo(texto)
            self._poner_subtitulo(texto, alfa)
            self._poner_aviso_saltar()
            return
        if self.fase == "saliendo":
            self._t_fase += dt
            f = 1.0 if SALIDA_SALTAR_S <= 0 else min(1.0, self._t_fase / SALIDA_SALTAR_S)
            self._telon(self._alfa_saltar + (1.0 - self._alfa_saltar) * f)
            if f >= 1.0:
                self._cerrar(lambda: self._al_terminar(True))

    def _colocar_plano(self, tiempo, dt):
        indice, t = self.linea.en(tiempo)
        plano = self.planos[indice]
        if indice != self._indice:
            self._indice = indice
            self.plano_actual = plano
            self.escenografia.entrar(plano)
        self._poner_camara(self.tomas[plano.id], t)
        self.escenografia.avanzar(plano, t, dt)

    @staticmethod
    def _poner_camara(toma, t):
        posicion, mira, fov = camaras.camara_en(toma, t)
        pitch, yaw = calc.rotacion_mirando(posicion, mira)
        camera.position = posicion
        camera.rotation = (pitch, yaw, 0)
        camera.fov = fov

    def _mantenido(self):
        for tecla in TECLAS_SALTAR:
            try:
                if held_keys[tecla]:
                    return True
            except Exception:
                continue
        return False

    def input(self, key):
        if self.terminada:
            return
        if key in TECLAS_SALTAR or key in ("enter", "left mouse down"):
            self.saltar_ctrl.pulsacion()

    # -- API ------------------------------------------------------------------------------------------------------------

    def saltar(self):
        """Salta ya (sin mantener): fundido corto a negro y cierre como al mantener."""
        if self.terminada or self.fase == "saliendo":
            return
        self._callar()
        if self.fase != "reproducir":
            self._cerrar(lambda: self._al_terminar(True))
            self.saltada = True
            return
        self.saltada = True
        self.fase = "saliendo"
        self._t_fase = 0.0
        self._alfa_saltar = self.telon.color.a

    # -- Cierre ---------------------------------------------------------------------------------------------------------

    def _fallar(self, error):
        _aviso(f"falló ({type(error).__name__}: {error}); cae a las viñetas")
        self._callar()
        self._cerrar(lambda: self._al_fallo(error) if self._al_fallo is not None else self._al_terminar(True))

    def _cerrar(self, aviso):
        if self.terminada:
            return
        self.terminada = True
        self._cola_guardia = FRAMES_GUARDIA
        self._callar()
        self.limpiar()
        try:                                     # la pantalla estaba en negro: el panel aparece con un fundido corto
            self._velo = Entity(parent=camera.ui, model="quad", scale=(8.0, 2.2), z=Z_CAPA, color=color.rgba(0, 0, 0, 1))
            self._t_velo = 0.0
        except Exception:
            self._velo = None
        try:
            aviso()
        except Exception as error:
            _aviso(f"aviso final: {type(error).__name__}: {error}")

    def limpiar(self):
        """Limpia la escenografía, destruye las raíces y devuelve la escena. Idempotente; nunca lanza."""
        from frontend.componentes import destruir_arbol
        self._callar()
        escenografia, self.escenografia = self.escenografia, None
        if escenografia is not None:
            try:
                escenografia.limpiar()
            except Exception as error:
                _aviso(f"limpiar escenografía: {type(error).__name__}: {error}")
        for raiz in (self.raiz3d, self.raizui):
            if raiz is not None:
                try:
                    destruir_arbol(raiz)
                except Exception as error:
                    _aviso(f"limpiar: {type(error).__name__}: {error}")
        self.raiz3d = self.raizui = None
        self.restaurar()


def crear_final_animado(escena, final, roles, al_terminar, al_fallo, conexion=None, guardia=None, escala=1.0,
                        escenografia=None, guion=None):
    """Crea y arranca el final animado. `al_terminar(saltada: bool)` UNA vez, con todo limpio. `al_fallo(error)` UNA vez,
    con todo limpio, si algo lanzó al cargar o en un frame. Lanza si no se puede ni construir (ya limpio). `escala`
    multiplica las duraciones (pruebas). `escenografia`: fábrica de pruebas (None = la real)."""
    return FinalAnimado(escena, final, roles, al_terminar, al_fallo, conexion=conexion, guardia=guardia, escala=escala,
                        escenografia=escenografia, guion=guion)
