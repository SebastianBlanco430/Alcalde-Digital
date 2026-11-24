# Clase base de la PRESENTACIÓN 3D de un minijuego de verificar (Ursina). No es un minijuego: el minijuego es la vista 2D de
# hoy (frontend/minijuegos/<id>.py o su vista visual de frontend/minijuegos_visual/), que la escena crea, empieza y sigue
# llamando como siempre (tecla, avanzar, terminar -> ResultadoMinijuego). La presentación 3D:
#   - cuelga esa vista 2D de una raíz fuera de pantalla (textura_ui.PantallaUI) y, en la familia del PC, la pinta en el
#     monitor 3D con el mouse redirigido (raton.Superficie);
#   - monta el set (sets.py, interior elegido por interiores.py), el protagonista y la cámara de la familia;
#   - imita en 3D lo que hace el jugador (poses_3d.PosesPersonaje) leyendo el estado de la vista 2D, SIN tocar su lógica.
#
# CICLO DE VIDA (lo maneja frontend/escenas/escena_minijuego.py; ver contrato.md):
#   escena: crea la vista 2D en `contenido`, llama minijuego.empezar(contexto)   (igual que hoy)
#   escena: v = Clase3D(Contexto3D(...)); v.abrir()        -> montar(): set, textura, mouse, cámara inicial, personaje
#                                                          -> construir()          [FAMILIA] piezas sobre las anclas
#                                                          -> transición a toma_juego(); al llegar, listo = True
#   cada frame:    v.avanzar(dt)  -> cámara, poses, imitar_pc() y avanzar_3d(dt)   [FAMILIA]
#   cada tecla:    v.tecla(k)     -> imitación por defecto y al_tecla(k)            [FAMILIA] (la tecla llega IGUAL a la 2D)
#   al terminar:   v.resultado(r) -> al_resultado(r)                                [FAMILIA] (el banner es el de siempre)
#   al cerrar:     v.cerrar()     -> destruir()                                     [FAMILIA] y se deshace todo
# Cualquier excepción en abrir/avanzar/tecla/resultado la captura la escena y cae al 2D de hoy con la MISMA vista 2D
# (mismo estado de partida): la escena devuelve `contenido` a camera.ui y llama cerrar().

import math

from frontend.minijuegos import ui as ui_2d
from frontend.minijuegos_3d import camaras_calculos as ccal
from frontend.minijuegos_3d import banderas, interiores, raton, sets, textura_ui
from frontend.minijuegos_3d.camaras import CamaraMinijuego, aspecto_ventana

_activo = {"vista": None}

CAMARA_POR_FAMILIA = {"pc": "sobre_hombro", "corcho": "frente_corcho", "mesa": "sobre_mesa"}
ADELANTE_SENTADO = 0.15           # m: sentado un poco más cerca del escritorio que en la cinemática (la mano llega al ratón)
# Entrada animada (sesión B): espera bajo el fundido y paso máximo por frame de la Secuencia
ALFA_TAPADA = 0.35                # con el fundido por encima de esto la entrada no avanza (empieza cuando la sala se ve)
ESPERA_FUNDIDO_MAX = 2.5          # s: nunca espera más (un fundido atascado no deja la entrada parada)
DT_MAX_SECUENCIA = 0.1            # s: un frame de carga largo avanza la animación como mucho esto


def presentacion_activa():
    """La presentación 3D abierta (o None)."""
    return _activo["vista"]


def minijuego_3d_listo():
    """True si hay un minijuego 3D abierto y su cámara ya llegó a la toma de juego (el jugador ve la mesa/corcho/monitor
    y puede jugar). El tutorial por misión se reproduce ANTES (en 2D, como hoy) y puede consultarlo para esperar."""
    v = _activo["vista"]
    return v is not None and v.listo and not v.cerrada


class Contexto3D:
    """Lo que la escena le da a la presentación. Atributos (todos de solo lectura para la familia):
    minijuego_id, minijuego (la vista 2D ya empezada), contenido (Entity que la contiene), jugador, mision, lugar (destino),
    fabrica_interior (callable -> EscenaInterior), escena (EscenaMinijuego; solo para casos raros)."""

    def __init__(self, minijuego_id, minijuego, contenido, jugador=None, mision=None, lugar="", fabrica_interior=None,
                 escena=None):
        self.minijuego_id = minijuego_id
        self.minijuego = minijuego
        self.contenido = contenido
        self.jugador = jugador
        self.mision = mision
        self.lugar = lugar
        self.fabrica_interior = fabrica_interior
        self.escena = escena


class Minijuego3D:

    FAMILIA = "pc"                    # 'pc' | 'corcho' | 'mesa': set, cámara y entrada del personaje
    CAMARA = None                     # None = la de la familia ('sobre_hombro' | 'frente_corcho' | 'sobre_mesa')
    FRACCION = None                   # None = la de la familia (camaras_calculos.FRACCION_*)
    DIBUJAR_VISTA_2D = None           # None = True en 'pc' (la vista 2D en el monitor), False en corcho/mesa
    MOSTRAR_AYUDA = True              # la línea de teclas de la vista 2D también en pantalla, abajo (capa_pantalla)
    DURACION_ENTRADA = 0.9            # s de la transición de cámara de entrada (0,6-1)
    DURACION_CAMINAR = 1.1            # s que tarda el personaje de la puerta al corcho/mesa (corcho y mesa)

    def __init__(self, contexto):
        self.ctx = contexto
        self.minijuego = contexto.minijuego
        self.set = None
        self.eleccion = None
        self.pantalla = None
        self.superficie = None
        self.camara = None
        self.poses = None
        self.capa = None
        self.listo = False
        self.cerrada = False
        self.resultado_3d = None
        self._frames = 0
        # Entrada/salida animadas (sesión B, ALCALDE_ANIM_SILLA): la Secuencia de frontend/cinematica_silla en curso
        # (auto=False, la avanza avanzar()) y si esta presentación entró por el camino nuevo.
        self._secuencia = None
        self.entrada_animada = False

    # -- Lo que implementa la FAMILIA (todo opcional) --

    def construir(self):
        """Pon tus piezas sobre self.set.anclas (corcho, mesa, monitor). Se llama una vez, con la cámara en la toma inicial."""

    def avanzar_3d(self, dt):
        """Cada frame: lee el estado de self.minijuego (la vista 2D: foco, partida, terminado...) y sincroniza tus piezas."""

    def al_tecla(self, k):
        """Cada tecla/botón del mouse que recibe la escena (DESPUÉS de mandarla a la vista 2D). Para imitar, no para decidir."""

    def al_resultado(self, resultado):
        """El minijuego 2D terminó (ResultadoMinijuego). El banner lo pinta la escena como siempre."""

    def destruir(self):
        """Destruye lo que creaste fuera de las anclas del set (lo colgado de las anclas se va con el set)."""

    # -- Tomas (se pueden sobrescribir) --

    def nombre_camara(self):
        return self.CAMARA or CAMARA_POR_FAMILIA[self.FAMILIA]

    def toma_juego(self):
        aspecto = aspecto_ventana()
        nombre = self.nombre_camara()
        if nombre == "sobre_hombro":
            return ccal.toma_sobre_hombro(self.set.anclas["monitor"].datos_toma(), aspecto,
                                          self.FRACCION or ccal.FRACCION_MONITOR, rol=getattr(self.set.personaje, "rol", None))
        if nombre == "frente_corcho":
            return ccal.toma_frente_corcho(self.set.anclas["corcho"].datos_toma(), aspecto,
                                           self.FRACCION or ccal.FRACCION_CORCHO)
        if nombre == "sobre_mesa":
            return ccal.toma_sobre_mesa(self.set.anclas["mesa"].datos_toma(), aspecto, self.FRACCION or ccal.FRACCION_MESA,
                                        techo=self.set.techo)
        raise ValueError(f"cámara desconocida: {nombre!r}")

    def toma_inicial(self):
        """PC: el monitor llenando la pantalla (donde acabó la cinemática de sentarse). Corcho/mesa: desde la puerta."""
        aspecto = aspecto_ventana()
        if self.FAMILIA == "pc":
            d = self.set.anclas["monitor"].datos_toma()
            return ccal.toma_frente(d["centro"], d["normal"], d["arriba"], d["alto"], d["ancho"], 0.98, aspecto)
        juego = self.toma_juego()
        x, z = self.set.puerta
        return {"position": (x * 0.6, 1.75, z), "target": juego["target"], "fov": juego["fov"] + 12}

    # -- Ciclo de vida (lo llama la escena) --

    def abrir(self):
        _activo["vista"] = self
        from frontend.minijuegos_3d import estado as _estado
        _estado.presentacion_abierta(True)         # sesión B: sus Espacio/Enter los trata la escena del minijuego
        ctx = self.ctx
        self.eleccion = interiores.elegir(ctx.minijuego_id, ctx.lugar, familia=self.FAMILIA)
        self.set = sets.crear(self.eleccion, ctx.jugador, ctx.lugar, ctx.fabrica_interior)
        self.set.encender(True)
        dibujar = self.DIBUJAR_VISTA_2D if self.DIBUJAR_VISTA_2D is not None else self.FAMILIA == "pc"
        self.pantalla = textura_ui.obtener()
        self.pantalla.vaciar()
        self.pantalla.activar(True, dibujar=dibujar)
        ctx.contenido.parent = self.pantalla.ui
        ctx.contenido.position = (0, 0, 0)
        ctx.contenido.scale = 1
        ctx.contenido.enabled = True              # (si vaciar() lo había soltado, quedó apagado)
        monitor = self.set.anclas.get("monitor")
        if dibujar and monitor is not None and monitor.quad is not None:
            self.pantalla.aplicar_a(monitor.quad)
            self.superficie = raton.registrar_superficie(raton.Superficie(monitor.quad, self.pantalla))
        raton.instalar()
        self.camara = CamaraMinijuego()
        self.camara.tomar(self.toma_inicial())
        from frontend.minijuegos_3d.poses_3d import PosesPersonaje
        self.poses = PosesPersonaje(self.set.personaje)
        self._colocar_personaje()
        self.construir()
        self._sin_destello()
        if self.MOSTRAR_AYUDA:
            from frontend.minijuegos_3d.capa_pantalla import CapaPantalla
            self.capa = CapaPantalla()
            self.capa.ayuda(ui_2d.ayuda_legible(getattr(self.minijuego, "AYUDA", "")))
        if not self._entrada_nueva():
            self.camara.ir_a(self.toma_juego(), self.DURACION_ENTRADA, al_llegar=self._llegar)
        self._fallo("abrir")

    # -- Entrada/salida animadas (sesión B, ALCALDE_ANIM_SILLA; frontend/cinematica_silla.py) --
    # Con la bandera encendida: el personaje empieza en el punto de partida (bajo el fundido), la cámara en la toma de
    # establecimiento, y la Secuencia (sentarse_en en PC y mesa, acercarse_a_corcho en corcho) lo lleva hasta la toma de
    # juego EXACTA (toma_final = toma_juego()); al terminar (o al saltarla) listo = True. Cualquier excepción al crearla:
    # el set vuelve a como lo dejó crear() y sigue la entrada de hoy (toma inicial + ir_a + personaje colocado).

    def _modulo_silla(self):
        """frontend.cinematica_silla si la bandera está encendida (None si no, o si no se puede importar)."""
        if not banderas.anim_silla():
            return None
        from frontend import cinematica_silla
        return cinematica_silla if cinematica_silla.activa() else None

    def manos_entrada(self):
        """[FAMILIA] Dónde terminan las manos al sentarse ({"i", "d"} mundo) o None (las de la mesa del set)."""
        return None

    def al_terminar_entrada(self):
        """[FAMILIA] La entrada animada terminó (normal, saltada o con fallo), justo antes de listo = True."""

    def toma_establecimiento(self):
        """[FAMILIA] Toma (dict) donde empieza la cámara de la entrada animada, o "establecimiento" (la del módulo:
        toma de juego retrocedida). La cámara va de ahí a toma_juego() en una sola curva."""
        return "establecimiento"

    def partida_entrada(self):
        """[FAMILIA] (x, z, rumbo) donde está el personaje al abrirse el fundido (silla), o None = el del módulo."""
        return None

    def _limites(self):
        lim = self.set.limites
        if lim is None:
            return None
        if self.set.techo is not None:
            return tuple(lim) + (0.05, self.set.techo - 0.15)
        return tuple(lim)

    def _entrada_nueva(self):
        """Lanza la entrada animada. True si quedó en marcha (o ya terminó y listo es True); False = la de hoy."""
        try:
            cs = self._modulo_silla()
            if cs is None:
                return False
            if not sets.preparar_entrada(self.set, self.FAMILIA, self.ctx.minijuego_id, manos=self.manos_entrada()):
                return False
        except Exception as error:               # noqa: BLE001  sin módulo o set raro: la entrada de hoy
            self._avisar("entrada_silla", error)
            sets.deshacer_entrada(self.set)
            return False
        try:
            self._lanzar_entrada(cs)
            return True
        except Exception as error:               # noqa: BLE001
            self._avisar("entrada_silla", error)
            self._cancelar_secuencia()
            sets.deshacer_entrada(self.set)
            self.entrada_animada = False
            self._volver_a_la_entrada_de_hoy()
            return False

    def _lanzar_entrada(self, cs):
        from frontend.minijuegos_3d import entrada_calculos as ec
        p = self.set.personaje
        toma = self.toma_juego()
        limites = self._limites()
        clave = ec.CLAVES[self.FAMILIA]
        self.poses.soltar_mano("d")
        self.poses.soltar_mano("i")
        quitar = getattr(self, "_quitar_velo", None)      # PC: sin velo de entrada (no hay destello que tapar)
        if callable(quitar):
            quitar()
        self.entrada_animada = True
        comunes = dict(toma_final=toma, toma_inicial=self.toma_establecimiento(), clave=clave, al_terminar=self._fin_entrada,
                       poses=self.poses, camara=self.camara, auto=False, limites=limites, avanzar_poses=False)
        if self.FAMILIA == "corcho":
            c = self.set.corcho_desc
            x, z, rumbo = ec.partida_corcho(c.pie, c.normal, self.set.limites)
            self.poses.de_pie(x, z, rumbo)
            self._secuencia = cs.acercarse_a_corcho(p, c, **comunes)
        else:
            x, z, rumbo = self.partida_entrada() or cs.punto_de_partida(self.set.silla)
            if not ec.dentro((x, z), self.set.limites, ec.MARGEN_PARTIDA):
                x, z, rumbo = ec.partida_silla(vars(self.set.silla), self.set.limites)
            self.poses.de_pie(x, z, rumbo)
            self._secuencia = cs.sentarse_en(p, self.set.silla, self.set.mesa_silla, entidad_silla=self.set.entidad_silla,
                                             **comunes)

    def _fin_entrada(self):
        try:
            self.al_terminar_entrada()
        finally:
            self._llegar()

    def _volver_a_la_entrada_de_hoy(self):
        """La entrada animada no pudo arrancar: personaje como hoy y cámara de hoy (nunca queda sin listo)."""
        try:
            self.poses.soltar()
            self._colocar_personaje()
        except Exception:                        # noqa: BLE001
            pass
        self.camara.tomar(self.toma_inicial())

    def secuencia_activa(self):
        s = self._secuencia
        return s is not None and bool(getattr(s, "activa", False))

    def saltar_secuencia(self):
        """Espacio / Enter / botón del mando durante la entrada o la salida animadas: la termina en su estado final.
        True si había una en curso (la tecla no se usa para nada más)."""
        s = self._secuencia
        if s is None or not getattr(s, "activa", False):
            return False
        try:
            return bool(s.saltar())
        except Exception as error:               # noqa: BLE001  solo puede venir de al_terminar: lo de hoy
            self._avisar("saltar_silla", error)
            self._rescatar_secuencia()
            return True

    def _avanzar_secuencia(self, dt):
        s = self._secuencia
        if s is None:
            return False
        activa = bool(getattr(s, "activa", False))
        if activa and not self.listo and self._bajo_el_fundido(dt):
            return True                          # la entrada espera (quieta, en su primer frame) a que se vea la sala
        try:
            s.avanzar(min(dt, DT_MAX_SECUENCIA))     # un frame de carga largo no se come la animación
        except Exception as error:               # noqa: BLE001  (al_terminar lanzó): estado de hoy y sigue el juego
            self._avisar("avanzar_silla", error)
            self._rescatar_secuencia()
        return activa

    def _bajo_el_fundido(self, dt):
        """¿La pantalla sigue tapada por el fundido de entrada (el del nombre del lugar)? Entonces la entrada animada no
        avanza: empieza cuando la sala ya se ve (si no, media animación pasaba en negro: capturas m3_*). Como mucho
        ESPERA_FUNDIDO_MAX s. Nunca lanza."""
        self._espera_fundido = getattr(self, "_espera_fundido", 0.0) + dt
        if self._espera_fundido > ESPERA_FUNDIDO_MAX:
            return False
        try:
            from ursina import camera
            for e in camera.ui.children:
                if type(e).__name__ == "Transicion" and e.enabled and float(getattr(e, "alfa", 0.0)) > ALFA_TAPADA:
                    return True
        except Exception:                        # noqa: BLE001
            return False
        return False

    def _rescatar_secuencia(self):
        """Una secuencia que lanzó: se cancela; si era la entrada y aún no estaba listo, entrada de hoy al instante."""
        self._cancelar_secuencia()
        if not self.listo:
            self.entrada_animada = False
            sets.deshacer_entrada(self.set)
            self._volver_a_la_entrada_de_hoy()
            self.camara.ir_a(self.toma_juego(), 0, al_llegar=self._llegar)
        self.al_rescatar_secuencia()

    def al_rescatar_secuencia(self):
        """[FAMILIA] La secuencia de salida falló: deja el estado de hoy (p. ej. el banner a la vista)."""
        self._mostrar_banner_salida()

    def _esconder_banner_salida(self):
        banner = getattr(getattr(self.ctx, "escena", None), "banner", None)
        if banner is not None:
            banner.enabled = False
            self._banner_salida = banner

    def _mostrar_banner_salida(self):
        banner, self._banner_salida = getattr(self, "_banner_salida", None), None
        if banner is not None:
            try:
                banner.enabled = True
            except Exception:                    # noqa: BLE001  el banner ya no existe: nada que enseñar
                pass

    def _cancelar_secuencia(self):
        s, self._secuencia = self._secuencia, None
        if s is not None:
            try:
                s.cancelar()
            except Exception:                    # noqa: BLE001
                pass

    def salida_silla(self, al_terminar=None, toma_final=None):
        """Salida animada de la silla (PC y mesa): levantarse_de. True si quedó en marcha; False = la salida de hoy (y
        `al_terminar` NO se llama)."""
        if not self.entrada_animada or self.set is None or self.set.silla is None:
            return False
        try:
            cs = self._modulo_silla()
            if cs is None:
                return False
            from frontend.minijuegos_3d import entrada_calculos as ec
            self._cancelar_secuencia()
            self._secuencia = cs.levantarse_de(
                self.set.personaje, self.set.silla, self.set.mesa_silla, toma_final=toma_final,
                clave=ec.CLAVES[self.FAMILIA], al_terminar=al_terminar, entidad_silla=self.set.entidad_silla,
                poses=self.poses, camara=self.camara, auto=False, limites=self._limites(), avanzar_poses=False)
            return True
        except Exception as error:               # noqa: BLE001
            self._avisar("salida_silla", error)
            self._cancelar_secuencia()
            return False

    def _avisar(self, clave, error):
        try:
            from frontend import banderas_visuales as bv
            bv.avisar_una_vez(f"{clave}_{self.ctx.minijuego_id}", error)
        except Exception:                        # noqa: BLE001
            pass

    def _fallo(self, fase):
        """PRUEBAS (ALCALDE_3D_FALLO=fase): lanza para ver el respaldo al 2D. En avanzar, a los 30 frames."""
        if banderas.fallo_inyectado(fase) and (fase != "avanzar" or self._frames > 30):
            raise RuntimeError(f"fallo inyectado por ALCALDE_3D_FALLO en {fase}")

    def _sin_destello(self):
        """Entrada sin destello (ConexionFlujo + EscenaInterior, familia PC): no hay destello que continuar, así que se
        quita el velo de entrada de la familia si lo creó (pc_base: `_quitar_velo`). La toma inicial (el monitor llenando la
        pantalla) es la misma en la que termina la cinemática; el personaje no está en cuadro."""
        from frontend.minijuegos_3d import estado
        if not estado.consumir_sin_destello():
            return
        quitar = getattr(self, "_quitar_velo", None)
        if callable(quitar):
            quitar()

    def _llegar(self):
        self.listo = True

    def _colocar_personaje(self):
        p = self.poses
        if self.FAMILIA == "pc" and self.set.asiento is not None:
            x, z, rumbo = self.set.asiento
            p.sentar(x, z + ADELANTE_SENTADO, rumbo)
            for nombre in ("mesa", "monitor"):
                ancla = self.set.anclas.get(nombre)
                if ancla is not None:
                    d = ancla.datos_toma()
                    p.limitar(d["centro"], d["normal"])          # la mano no atraviesa la mesa ni la pantalla
            raton_ancla = self.set.anclas.get("raton")
            if raton_ancla is not None:
                p.mano_a(raton_ancla.mundo(0, 0.03, -0.07), lado="d")
            teclado = self.set.anclas.get("teclado")
            if teclado is not None:
                p.mano_a(teclado.mundo(-0.14, 0.03, -0.05), lado="i")
            return
        if self.set.pie is not None:
            x0, z0 = self.set.puerta
            x, z, rumbo = self.set.pie
            p.de_pie(x0, z0, rumbo)
            p.caminar_a(x, z, rumbo, duracion=self.DURACION_CAMINAR)

    def avanzar(self, dt):
        if self.cerrada:
            return
        if not (isinstance(dt, (int, float)) and math.isfinite(dt) and dt >= 0):
            dt = 0.0                             # un dt no finito (reloj del arnés) nunca llega a cámara ni a poses
        self._frames += 1
        self._fallo("avanzar")
        self.camara.avanzar(dt)
        animando = self._avanzar_secuencia(dt)          # entrada/salida animadas: mandan en el cuerpo, la silla y la cámara
        if self.FAMILIA == "pc" and not animando and not self._levantandose():
            self.imitar_pc()
        self.poses.avanzar(dt)
        self.avanzar_3d(dt)
        if self.capa is not None:
            self.capa.avanzar(dt)

    def _levantandose(self):
        """¿La salida animada ya empezó o terminó? (las manos ya no vuelven al ratón/teclado)."""
        return self.resultado_3d is not None and self.entrada_animada and self._secuencia is not None

    def imitar_pc(self):
        """La mano derecha sigue en el ratón del escritorio la posición del puntero sobre el monitor."""
        raton_ancla = self.set.anclas.get("raton") if self.set is not None else None
        if raton_ancla is None:
            return
        ultimo = raton.ultimo()
        if ultimo is None or ultimo[0] is not self.superficie:
            du, dv = 0.0, 0.0
        else:
            du, dv = ultimo[1][0] - 0.5, ultimo[1][1] - 0.5
        # el ratón físico se mueve 12 x 8 cm para recorrer la pantalla entera
        self.poses.mano_a(raton_ancla.mundo(du * 0.12, 0.03, -0.07 + dv * 0.08), lado="d")

    def tecla(self, k):
        if self.cerrada:
            return
        if self.secuencia_activa():
            return                               # durante la entrada/salida animadas no hay gestos de juego
        if self.FAMILIA == "pc":
            if k == "left mouse down":
                self.poses.clic("d")
            elif len(k) == 1 or k in ("space", "enter", "backspace", "up arrow", "down arrow", "left arrow",
                                       "right arrow", "tab"):
                self.poses.teclear()
        self._fallo("tecla")
        self.al_tecla(k)

    def usar_minijuego(self, minijuego):
        """La previa ya estaba en el monitor (familia PC) y ahora empieza el minijuego: su vista 2D (ya empezada, en el mismo
        `contenido`) pasa a ser `self.minijuego`. La capa de ayuda enseña sus teclas. Hook de familia: al_minijuego()."""
        self.minijuego = minijuego
        self.ctx.minijuego = minijuego
        if self.capa is not None:
            self.capa.ayuda(ui_2d.ayuda_legible(getattr(minijuego, "AYUDA", "")))
        self.al_minijuego()

    def al_minijuego(self):
        """[FAMILIA, opcional] El minijuego empezó con la presentación ya abierta (previa en el monitor)."""

    def resultado(self, resultado):
        if self.cerrada or self.resultado_3d is not None:
            return
        if self.secuencia_activa():
            self.saltar_secuencia()              # (resultado antes de acabar la entrada animada) estado final al instante
        self.resultado_3d = resultado
        from frontend.minijuegos_3d import estado
        estado.jugado_en_3d(self.FAMILIA)       # la salida del edificio será la del 3D (si luego cae al 2D, se borra)
        if self.capa is not None:
            self.capa.ayuda("")                  # el banner de resultado ocupa esa franja (como el pie de la vista 2D)
        silla_mesa = self.FAMILIA == "mesa" and self.entrada_animada
        if self.FAMILIA != "pc" and self.poses is not None and not silla_mesa:
            self.poses.soltar_mano("d")          # se aparta: los dos brazos vuelven a la animación de reposo
            self.poses.soltar_mano("i")
        self._fallo("resultado")
        self.al_resultado(resultado)
        if silla_mesa:
            # sesión B: sentado a la mesa, se levanta, empuja la silla y se aparta; la cámara vuelve a la toma de
            # establecimiento de la entrada para que se le vea (en la toma de juego, casi cenital, queda fuera de cuadro;
            # la toma abierta del módulo giraba 180° mirando hacia abajo: capturas m3_sen_ciu); el resultado lo dice el
            # banner de siempre. Si no arranca: de pie con los brazos sueltos (hoy).
            # Como en el PC, el banner de siempre aparece cuando ya se apartó (y nunca se queda escondido: cerrar,
            # respaldo, fallo de la salida).
            self._esconder_banner_salida()
            abierta = self.toma_establecimiento()
            if not self.salida_silla(al_terminar=self._mostrar_banner_salida,
                                     toma_final=abierta if isinstance(abierta, dict) else None):
                self._mostrar_banner_salida()
                self.poses.soltar_mano("d")
                self.poses.soltar_mano("i")

    def cerrar(self):
        """Deshace todo (idempotente, nunca lanza). La vista 2D NO se destruye aquí: es de la escena."""
        if self.cerrada:
            return
        self.cerrada = True
        secuencia, self._secuencia = self._secuencia, None
        for paso in (lambda: secuencia is not None and secuencia.cancelar(),
                     lambda: secuencia is not None and secuencia.soltar(),
                     self._mostrar_banner_salida,         # nunca queda escondido el banner de siempre
                     self.destruir, raton.desinstalar,
                     lambda: self.capa is not None and self.capa.destruir(),
                     lambda: self.poses is not None and self.poses.soltar(),
                     lambda: self.camara is not None and self.camara.soltar(),
                     lambda: self.set is not None and self.set.destruir(),
                     lambda: self.pantalla is not None and self.pantalla.activar(False)):
            try:
                paso()
            except Exception:            # noqa: BLE001  limpieza de mejor esfuerzo
                pass
        if _activo["vista"] is self:
            _activo["vista"] = None
            try:
                from frontend.minijuegos_3d import estado as _estado
                _estado.presentacion_abierta(False)
            except Exception:            # noqa: BLE001
                pass
