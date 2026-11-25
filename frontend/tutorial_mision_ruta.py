# Tutoriales de las misiones que se viven en el mundo 3D y NO tienen práctica: LLEGADA (primera misión de verificar: teléfono, ruta,
# puerta y aviso «E») y ENTREGAS en moto (ruta azul y baliza). Los dos son un vistazo de cámara con bocadillos sobre los elementos
# reales del HUD.
#
# SIN CONSECUENCIAS. El tutorial solo mueve la cámara (la entrega el control de la cámara y la devuelve al cerrar) y señala el HUD.
# No toca la misión, el GameState, la billetera, la fatiga ni el reloj de la partida: mientras está abierto la escena queda en
# «cinemática» (controles congelados y reloj parado, igual que el vistazo de llegada_visual) y se registra como bloqueador (Escape lo
# salta). Con la bandeja de otro panel, el teléfono grande o un dilema abiertos, no se abre (el mundo ya está bloqueado).
#
# ENGANCHES (cada uno, pocas líneas con try/except en el archivo existente):
#   - llegada_visual.VigiaLlegada: tras el vistazo al destino (o enseguida si el jugador pidió «reducir movimiento»).
#   - entregas_mundo.EntregasMundo.iniciar: justo antes de empezar el turno, cuando ya hay pedidos; al terminar el tutorial el turno
#     empieza como siempre (su tiempo y su moto no se tocan antes).

from types import SimpleNamespace

_estado = {}          # id(escena) -> {"tutorial": TutorialMision|None}

# Lo que esta vista necesita del controlador (frontend/registro_tutorial_mision.py) se lo da él con conectar(): una vista no
# importa controladores (contrato MVC, R3 de tests/test_arquitectura_mvc.py). Sin conectar no se abre ningún tutorial.
_CONTROL = {}


def conectar(**funciones):
    _CONTROL.update(funciones)


def _controlador():
    """Las funciones conectadas (toca, abrir_si_toca...) o None si el controlador aún no las puso."""
    return SimpleNamespace(**_CONTROL) if "toca" in _CONTROL else None


def _tomar(escena):
    """Estado del tutorial de ruta de esta escena, registrando su bloqueador la primera vez."""
    clave = id(escena)
    estado = _estado.get(clave)
    if estado is None:
        estado = {"tutorial": None}
        _estado.clear()                                   # una escena nueva (otra partida): lo viejo se olvida
        _estado[clave] = estado

        def abierto():
            t = estado["tutorial"]
            return t is not None and not t.cerrado

        def cerrar():
            t = estado["tutorial"]
            if t is not None and not t.cerrado:
                t.saltar_todo()

        escena.registrar_bloqueador(abierto, cerrar)
    return estado


def abrir(escena, id_, contexto, al_cerrar=None, forzar_ver=False):
    """Abre el tutorial `id_` si toca. True si se abrió (quien llama no debe seguir hasta que termine). Nunca lanza."""
    try:
        from ursina import camera

        rtm = _controlador()
        if rtm is None or not rtm.toca(id_, forzar_ver):
            return False
        estado = _tomar(escena)
        if estado["tutorial"] is not None and not estado["tutorial"].cerrado:
            return True

        def terminado(saltado, fallo):
            from frontend.componentes import destruir_arbol
            t, estado["tutorial"] = estado["tutorial"], None
            if t is not None:
                try:
                    destruir_arbol(t)
                except Exception:                      # noqa: BLE001
                    pass
            if al_cerrar is not None:
                al_cerrar()

        contexto = dict(contexto, escena=escena)
        estado["tutorial"] = rtm.abrir_si_toca(camera.ui, id_, terminado, forzar_ver, contexto=contexto)
        return estado["tutorial"] is not None
    except Exception:                                  # noqa: BLE001  el guardián de abrir_si_toca ya avisó
        return False


# ---------------------------------------------------------------- enganches

def llegada_despues_del_vistazo(escena, mision):
    """Llamado por VigiaLlegada tras el vistazo al destino. True si abrió el tutorial."""
    return abrir(escena, "llegada", {"mision": mision})


def entregas_antes_de_iniciar(entregas, puesto, plan):
    """Llamado por EntregasMundo.iniciar con el plan ya elegido. True si abrió el tutorial (el turno sigue al terminar)."""
    if entregas.__dict__.get("_tutorial_continuando"):
        return False

    def continuar():
        entregas._tutorial_continuando = True
        try:
            entregas._plan = plan
            entregas.iniciar(puesto)
        finally:
            entregas._tutorial_continuando = False

    return abrir(entregas.escena, "trabajo_entregas", {"plan": plan}, al_cerrar=continuar)


# ---------------------------------------------------------------- adaptador (misma interfaz que los demás)

class AdaptadorRuta:
    """Vistazo de cámara + bocadillos sobre el HUD. foco 0 = teléfono, 1 = minimapa, 2 = aviso de «E»."""

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        ctx = contexto or {}
        self.escena = ctx["escena"]
        self.mision = ctx.get("mision")
        self.plan = ctx.get("plan")
        self._inicio = None
        self._cam = None
        self._aviso = None
        self._cinematica_previa = False

    # -- Cámara --

    def _toma_destino(self):
        from frontend import camara_calculos as cc
        mundo = self.escena._mundo
        if self.mision is not None:
            try:
                from frontend import guion_cinematicas as guion
                return guion.toma_fachada(mundo.edificio_de(self.mision.destino))
            except (ValueError, KeyError, AttributeError):
                px, pz = mundo.punto_interaccion(self.mision.destino)
        else:
            pedido = self.plan["pedidos"][0]
            px, pz = float(pedido.x), float(pedido.z)
        y = mundo.altura(px, pz) if hasattr(mundo, "altura") else 0.0
        posicion = (px + 6.0, y + 4.0, pz - 7.0)
        pitch, yaw = cc.rotacion_mirando(posicion, (px, y + 1.2, pz))
        return {"position": posicion, "pitch": pitch, "yaw": yaw}

    def crear_vista(self, padre, al_terminar):
        from ursina import camera
        escena = self.escena
        self._inicio = (tuple(camera.position), camera.rotation_x, camera.rotation_y)
        self._cinematica_previa = bool(getattr(escena, "_cinematica", False))
        escena._cinematica = True                      # controles congelados y reloj parado (motivo CINEMATICA)
        escena.camara.tomar_control()
        hud = escena.hud
        from ursina import Entity, color
        # Hueco del aviso de «E»: solo existe cuando se llega a la puerta; aquí se señala dónde saldrá.
        aviso = getattr(hud, "aviso", None)
        y = getattr(aviso, "y_base", -0.43)
        self._aviso = Entity(parent=camera.ui, model="quad", color=color.clear, scale=(0.5, 0.08), position=(0, y, 0))
        return escena

    def camara(self, vista, paso):
        from ursina import camera
        destino = self._toma_destino() if paso["a"] == "meta" else {
            "position": self._inicio[0], "pitch": self._inicio[1], "yaw": self._inicio[2]}
        actual = (tuple(camera.position), camera.rotation_x, camera.rotation_y)
        self._cam = {"desde": actual, "hasta": destino, "t": 0.0, "dur": max(0.05, float(paso.get("s", 2.5)))}

    def avanzar_visual(self, vista, dt):
        c = self._cam
        if c is None or c["t"] >= c["dur"]:
            return
        from ursina import camera

        from frontend import banderas_visuales as bv
        from frontend.cinematica import ease_in_out, lerp, lerp_angulo, lerp_vec3
        c["t"] = min(c["dur"], c["t"] + dt)
        k = 1.0 if bv.reducir_movimiento() else ease_in_out(c["t"] / c["dur"])
        camera.position = lerp_vec3(c["desde"][0], c["hasta"]["position"], k)
        camera.rotation = (lerp(c["desde"][1], c["hasta"]["pitch"], k), lerp_angulo(c["desde"][2], c["hasta"]["yaw"], k), 0)

    # -- Señalar --

    def elemento(self, vista, foco):
        hud = self.escena.hud
        if foco == 0:
            telefono = getattr(hud, "telefono_ui", None)
            return getattr(telefono, "icono", telefono)
        if foco == 1:
            return getattr(getattr(hud, "minimapa", None), "fondo", None)
        return self._aviso

    def elemento_tecla(self, vista, k):
        return None

    def poner_foco(self, vista, foco):
        """Sin foco."""

    def enviar_tecla(self, vista, k):
        """Sin práctica: las teclas no llegan al mundo."""

    def error(self, vista, paso):
        """Sin error a propósito."""

    def avanzar_juego(self, vista, dt):
        """Sin juego."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        raise NotImplementedError("no tiene «Ahora tú»")

    def cerrar(self, vista):
        escena = self.escena
        if self._inicio is None:
            return
        from ursina import camera
        inicio, self._inicio = self._inicio, None
        try:
            camera.position, camera.rotation = inicio[0], (inicio[1], inicio[2], 0)
            escena.camara.soltar_control()
        finally:
            escena._cinematica = self._cinematica_previa
            try:
                escena._sincronizar_raton()
            except Exception:                          # noqa: BLE001
                pass
            if self._aviso is not None:
                from frontend.componentes import destruir_arbol
                destruir_arbol(self._aviso)
                self._aviso = None


ADAPTADORES = {"llegada": AdaptadorRuta, "trabajo_entregas": AdaptadorRuta}
