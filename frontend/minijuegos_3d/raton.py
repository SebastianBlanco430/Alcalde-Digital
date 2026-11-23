# Mouse del juego redirigido a superficies 3D (Ursina). Mientras un minijuego 3D está abierto, `instalar()` sustituye
# mouse.update (solo en la INSTANCIA; `desinstalar()` lo devuelve) por una versión que, en este orden:
#   1. prueba camera.ui con el puntero real (lo que está en pantalla manda: banner, previa, capa_pantalla, menús);
#   2. prueba cada SUPERFICIE registrada (la última registrada, primero): rayo del puntero -> plano del quad -> UV ->
#      rayo de la cámara 2D de la textura -> colisiones de la raíz 2D (PantallaUI.ui). Si el puntero está sobre la superficie
#      pero no sobre un botón, no hay nada «hovered» (no se cae al mundo a través del monitor);
#   3. prueba el mundo (scene) como hace Ursina. Si lo tocado es una PIEZA VINCULADA (vincular(pieza3d, objetivo2d)), el
#      «hovered» pasa a ser el objetivo 2D: su on_mouse_enter/on_click/input reciben el mouse como si se hubiera apuntado
#      a él en la vista 2D de hoy.
# Con eso hover y clic de TODOS los botones de la vista 2D funcionan sin tocarla (ui.Tarjeta, BotonPrimario, golpes...):
# Ursina sigue llamando on_click desde mouse.input y los botones siguen mirando `self.hovered`.
#
# También: rayo_a_plano(entidad) da el punto del puntero en el plano local de cualquier entidad (corcho, mesa) y
# CursorMando mueve un cursor virtual con el palo derecho del mando.

from panda3d.core import Point2, Point3
from ursina import application, camera, mouse, scene, window
from ursina.hit_info import HitInfo
from ursina.ursinamath import distance

from frontend.minijuegos_3d import mapeo_calculos as mc

_estado = {"instalado": False, "superficies": [], "vinculos": {}, "ultimo": None, "pieza": None, "ndc_forzado": None}


class Superficie:
    """Un quad del mundo (`quad`, model='quad') que enseña una PantallaUI. `margen` encoge la zona clicable (fracción)."""

    def __init__(self, quad, pantalla, margen=0.0):
        self.quad = quad
        self.pantalla = pantalla
        self.margen = margen

    def mapear_ndc(self, ndc):
        """NDC de la ventana -> (u, v, x_ui, y_ui) sobre esta superficie, o None si el rayo no la toca."""
        extremos = extremos_rayo(ndc)
        if extremos is None or self.quad is None or not self.quad.enabled:
            return None
        cerca, lejos = extremos
        cl = self.quad.getRelativePoint(application.base.render, cerca)
        ll = self.quad.getRelativePoint(application.base.render, lejos)
        return mc.mapear(tuple(cl), tuple(ll), self.pantalla.aspecto, self.margen)


def extremos_rayo(ndc):
    """(cerca, lejos) del rayo de la cámara del mundo por `ndc`, en coordenadas de render. None si la lente no puede."""
    base = application.base
    cerca, lejos = Point3(), Point3()
    if not base.camLens.extrude(Point2(*ndc), cerca, lejos):
        return None
    return (base.render.getRelativePoint(base.cam, cerca), base.render.getRelativePoint(base.cam, lejos))


def ndc_puntero():
    """NDC del puntero en la ventana (o el forzado por forzar_ndc() en las pruebas del arnés). None sin puntero."""
    if _estado["ndc_forzado"] is not None:
        return _estado["ndc_forzado"]
    try:
        if not mouse._mouse_watcher.has_mouse():
            return None
    except Exception:                    # noqa: BLE001
        return None
    return mc.mouse_ui_a_ndc(mouse.x, mouse.y, window.aspect_ratio)


def forzar_ndc(ndc):
    """Arnés: hace como si el puntero estuviera en `ndc` (None = el puntero real). Afecta a superficies y rayo_a_plano."""
    _estado["ndc_forzado"] = None if ndc is None else (float(ndc[0]), float(ndc[1]))


def rayo_a_plano(entidad, ndc=None):
    """Punto (x, y) del puntero en el plano z = 0 LOCAL de `entidad` (sus unidades locales; un quad va de -0.5 a 0.5), o
    None si el rayo es paralelo o el plano queda detrás. No recorta: el llamador decide si está dentro."""
    ndc = ndc if ndc is not None else ndc_puntero()
    if ndc is None:
        return None
    extremos = extremos_rayo(ndc)
    if extremos is None:
        return None
    render = application.base.render
    cerca = entidad.getRelativePoint(render, extremos[0])
    lejos = entidad.getRelativePoint(render, extremos[1])
    return mc.rayo_en_local(tuple(cerca), tuple(lejos))


# -- Registro --

def registrar_superficie(superficie):
    if superficie not in _estado["superficies"]:
        _estado["superficies"].append(superficie)
    return superficie


def quitar_superficie(superficie):
    if superficie in _estado["superficies"]:
        _estado["superficies"].remove(superficie)


def vincular(pieza, objetivo):
    """La pieza 3D `pieza` (con collider) apunta al objetivo 2D `objetivo` (la entidad con collider de la vista de hoy)."""
    _estado["vinculos"][pieza] = objetivo


def desvincular(pieza=None):
    if pieza is None:
        _estado["vinculos"].clear()
    else:
        _estado["vinculos"].pop(pieza, None)


def ultimo():
    """(superficie, (u, v, x_ui, y_ui)) del último frame si el puntero estaba sobre una superficie; si no, None."""
    return _estado["ultimo"]


def pieza_bajo_cursor():
    """Pieza 3D vinculada que está bajo el puntero (para resaltarla en 3D), o None."""
    return _estado["pieza"]


def instalado():
    return _estado["instalado"]


def instalar():
    proteger_clic()
    if _estado["instalado"]:
        return
    mouse.update = _update
    _estado["instalado"] = True


def desinstalar():
    """Devuelve mouse.update al de Ursina y olvida superficies y vínculos. Nunca lanza."""
    try:
        if "update" in vars(mouse):
            del mouse.update
    except Exception:                    # noqa: BLE001
        pass
    _estado.update(instalado=False, ultimo=None, pieza=None, ndc_forzado=None)
    _estado["superficies"].clear()
    _estado["vinculos"].clear()
    try:
        _soltar_todo()
    except Exception:                    # noqa: BLE001
        pass


# -- El update sustituto --

# Clic protegido. Ursina 8.3.0 (mouse.input, 'left mouse down') hace `if self.hovered_entity: on_click()` y DESPUÉS recorre
# `self.hovered_entity.scripts` sin volver a comprobar. Si el on_click cierra el minijuego 3D (p. ej. «Continuar» del banner:
# continuar -> cerrar -> desinstalar) y eso pone hovered_entity = None en ese mismo instante, Ursina revienta con
# AttributeError: 'NoneType' object has no attribute 'scripts'. Por eso, mientras dura un mouse.input, soltar el hover se
# APLAZA y se hace en cuanto mouse.input termina (mismo frame). El envoltorio va en la INSTANCIA, se pone una sola vez y no
# se quita (fuera de los minijuegos 3D no cambia nada: solo cuenta la profundidad del input).
_clic = {"profundidad": 0, "pendiente": False, "protegido": False}


def proteger_clic():
    """Pone (una vez) el envoltorio de mouse.input que aplaza _soltar_todo() hasta que termina el clic. Nunca lanza."""
    if _clic["protegido"]:
        return
    try:
        original = type(mouse).input

        def _input_protegido(key):
            _clic["profundidad"] += 1
            try:
                return original(mouse, key)
            finally:
                _clic["profundidad"] -= 1
                if _clic["profundidad"] == 0 and _clic["pendiente"]:
                    _clic["pendiente"] = False
                    _soltar_ya()

        mouse.input = _input_protegido
        _clic["protegido"] = True
    except Exception:                    # noqa: BLE001
        pass


def _soltar_todo():
    if _clic["profundidad"] > 0:         # dentro de mouse.input: Ursina aún va a leer hovered_entity.scripts
        _clic["pendiente"] = True
        return
    _soltar_ya()


def _soltar_ya():
    mouse.hovered_entity = None
    mouse.collision = None
    mouse.unhover_everything_not_hit()


def _hover(objetivo):
    mouse.hovered_entity = objetivo
    if not getattr(objetivo, "hovered", False):
        objetivo.hovered = True
        if hasattr(objetivo, "on_mouse_enter"):
            objetivo.on_mouse_enter()
        for s in getattr(objetivo, "scripts", ()):
            if hasattr(s, "on_mouse_enter"):
                s.on_mouse_enter()
    mouse.unhover_everything_not_hit()


def _update():
    m = mouse
    if application.window_type != "onscreen" and _estado["ndc_forzado"] is None:
        return
    forzado = _estado["ndc_forzado"]
    if forzado is None:
        if not m.enabled or not m._mouse_watcher.has_mouse() or m._locked_mouse_last_frame:
            m.velocity = m.velocity * 0
            m._locked_mouse_last_frame = False
            return
        x, y = m.x, m.y
        m.moving = x + y != m.prev_x + m.prev_y
        if m.moving and not m.locked:
            m.velocity = type(m.velocity)(x - m.prev_x, (y - m.prev_y) / window.aspect_ratio, 0)
        elif not m.moving:
            m.velocity = m.velocity * 0
        if m.left or m.right or m.middle:
            m.delta = type(m.delta)(x - m.start_x, y - m.start_y, 0)
        m.prev_x, m.prev_y = x, y
        ndc = mc.mouse_ui_a_ndc(x, y, window.aspect_ratio)
    else:
        ndc = forzado
    # 1. lo que está en pantalla (camera.ui)
    m._pickerNP.reparent_to(scene.ui_camera)
    m._pickerRay.set_from_lens(camera._ui_lens_node, ndc[0], ndc[1])
    m._picker.traverse(camera.ui)
    if m._pq.get_num_entries() > 0:
        _estado["ultimo"] = None
        _estado["pieza"] = None
        m.find_collision()
        return
    # 2. superficies (la última registrada está encima)
    for superficie in reversed(_estado["superficies"]):
        r = superficie.mapear_ndc(ndc)
        if r is None:
            continue
        _estado["ultimo"] = (superficie, r)
        _estado["pieza"] = None
        pantalla = superficie.pantalla
        m._pickerNP.reparent_to(pantalla.camara)
        m._pickerRay.set_from_lens(pantalla.nodo_lente, *mc.uv_a_ndc(r[0], r[1]))
        m._picker.traverse(pantalla.ui)
        if m._pq.get_num_entries() > 0:
            m.find_collision()
        else:
            _soltar_todo()
        return
    _estado["ultimo"] = None
    # 3. el mundo, con las piezas vinculadas
    m._pickerNP.reparent_to(camera)
    m._pickerRay.set_from_lens(scene.camera.lens_node, ndc[0], ndc[1])
    if m.traverse_target:
        m._picker.traverse(m.traverse_target)
    if m._pq.get_num_entries() == 0:
        _estado["pieza"] = None
        _soltar_todo()
        return
    vinculos = _estado["vinculos"]
    if vinculos:
        m._pq.sortEntries()
        entrada = m._pq.getEntry(0)
        nodo = entrada.getIntoNodePath().parent
        for pieza, objetivo in vinculos.items():
            if nodo == pieza and getattr(pieza, "collision", False):
                _estado["pieza"] = pieza
                m.collision = HitInfo(hit=entrada.collided(), entity=pieza,
                                      distance=distance(entrada.getSurfacePoint(scene), camera.getPos()),
                                      point=entrada.getSurfacePoint(pieza), world_point=entrada.getSurfacePoint(scene),
                                      normal=entrada.getSurfaceNormal(pieza), world_normal=entrada.getSurfaceNormal(scene))
                _hover(objetivo)
                return
    _estado["pieza"] = None
    m.find_collision()


class CursorMando:
    """Cursor virtual en el plano local de una entidad, movido con el PALO DERECHO del mando (y que sigue al mouse cuando
    el mouse se mueve). Coordenadas locales del plano (un quad: [-0.5, 0.5]); `limites` = (xmin, xmax, ymin, ymax).
    Las familias lo usan para la linterna, el plumón o el punto del corcho/mesa. avanzar(dt) devuelve (x, y)."""

    VELOCIDAD = 0.6          # fracción del plano por segundo con el palo a fondo

    def __init__(self, plano, limites=(-0.5, 0.5, -0.5, 0.5), inicio=(0.0, 0.0)):
        self.plano = plano
        self.limites = limites
        self.x, self.y = inicio
        self._ultimo_mouse = None

    def avanzar(self, dt):
        from ursina import held_keys
        try:
            from frontend import mando_calculos as mdc
            px, py = mdc.palo(held_keys, mdc.PALO_DERECHO)
        except Exception:                # noqa: BLE001
            px, py = 0.0, 0.0
        if px or py:
            ancho = self.limites[1] - self.limites[0]
            alto = self.limites[3] - self.limites[2]
            self.x += px * self.VELOCIDAD * ancho * dt
            self.y += py * self.VELOCIDAD * alto * dt
        else:
            punto = rayo_a_plano(self.plano)
            if punto is not None and punto != self._ultimo_mouse:
                self._ultimo_mouse = punto
                self.x, self.y = punto
        self.x = min(max(self.x, self.limites[0]), self.limites[1])
        self.y = min(max(self.y, self.limites[2]), self.limites[3])
        return (self.x, self.y)
