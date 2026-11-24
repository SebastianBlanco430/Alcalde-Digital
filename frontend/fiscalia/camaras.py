# Cámara de la Fiscalía (Ursina). Guarda la cámara de Ursina al tomarla y la devuelve al soltarla (el mundo espera la de
# siempre); va de una toma a otra con una transición corta y suave (DURACION_CORTE, ease in-out) o con un corte seco
# (reducir movimiento o cambio de sala bajo el fundido); y «respira» un poco en reposo (con_deriva).
# Proyecta puntos del mundo a camera.ui para el ancla de la rueda (la cara de quien habla).

from ursina import camera, scene, window

from frontend import banderas_visuales as bv
from frontend.fiscalia import camaras_calculos as cc

NEAR, FAR = 0.03, 80.0


class CamaraFiscalia:

    def __init__(self):
        self._guardada = None
        self.actual = None          # toma base (sin deriva)
        self._desde = None
        self._hacia = None
        self._t = 0.0
        self._dur = 0.0
        self._reloj = 0.0
        self.deriva = True
        self.pausada = False        # otra animación (cinematica_silla de B) lleva la cámara: aquí no se toca
        self._fuente = None         # () -> toma: la toma «viva» que se sigue (la cara se mueve con la postura)

    @property
    def en_transicion(self):
        return self._hacia is not None

    def tomar(self):
        if self._guardada is None:
            self._guardada = {"parent": camera.parent, "orthographic": camera.orthographic, "fov": camera.fov,
                              "position": camera.position, "rotation": camera.rotation,
                              "near": camera.clip_plane_near, "far": camera.clip_plane_far}
        camera.parent = scene
        camera.orthographic = False
        camera.clip_plane_near = NEAR
        camera.clip_plane_far = FAR

    def soltar(self):
        g, self._guardada = self._guardada, None
        self._hacia = None
        if g is None:
            return
        camera.parent = g["parent"]
        camera.orthographic = g["orthographic"]
        camera.fov = g["fov"]
        camera.clip_plane_near = g["near"]
        camera.clip_plane_far = g["far"]
        camera.position = g["position"]
        camera.rotation = g["rotation"]

    def cortar(self, toma, seguir=None):
        self._hacia = None
        self._fuente = seguir
        self.actual = dict(toma)
        self._poner(toma)

    def ir_a(self, toma, duracion=cc.DURACION_CORTE, seguir=None):
        """Va a `toma`. `seguir` (opcional): función sin argumentos que devuelve la toma recalculada con la cabeza de
        AHORA; al terminar la transición la cámara la acompaña suave (la postura de la expresión —cabeza gacha,
        inclinarse— llega después de elegir el plano: sin esto el primer plano se quedaba mirando la coronilla)."""
        if self.actual is None or duracion <= 0 or bv.reducir_movimiento():
            self.cortar(toma, seguir)
            return
        self._fuente = seguir
        self._desde, self._hacia = dict(self._vista()), dict(toma)
        self._t, self._dur = 0.0, float(duracion)

    def _vista(self):
        return self.actual

    def avanzar(self, dt):
        self._reloj += dt
        if self.pausada:
            return
        if self._hacia is not None and self._fuente is not None:
            self._hacia = self._viva(self._hacia, dt, 1.0)       # el destino se mueve con la cara
        if self._hacia is not None:
            self._t += dt
            k = min(1.0, self._t / self._dur)
            self.actual = cc.interpolar(self._desde, self._hacia, cc.suave(k))
            if k >= 1.0:
                self.actual, self._hacia = self._hacia, None
        elif self.actual is not None and self._fuente is not None:
            self.actual = self._viva(self.actual, dt, cc.SEGUIR_K)
        if self.actual is None:
            return
        reducir = bv.reducir_movimiento()
        amplitud = 0.0 if (reducir or not self.deriva) else cc.DERIVA
        self._poner(cc.con_deriva(self._reloj, self.actual, amplitud))

    def _viva(self, base, dt, rapidez):
        """`base` acercada a la toma viva (seguir). Si la fuente falla, se deja de seguir (la toma queda fija)."""
        try:
            meta = self._fuente()
        except Exception:               # noqa: BLE001
            self._fuente = None
            return base
        if not meta:
            return base
        if bv.reducir_movimiento() or rapidez >= 1.0:
            return dict(meta)
        return cc.interpolar(base, meta, cc.seguir_paso(dt, rapidez))

    def retomar(self):
        """Vuelve a mandar desde donde dejó la cámara otra animación (sin salto)."""
        self.pausada = False
        self._fuente = None
        self._hacia = None
        try:
            p, f = camera.world_position, camera.forward
            pos = (float(p[0]), float(p[1]), float(p[2]))
            self.actual = {"position": pos, "target": (pos[0] + f[0] * 3, pos[1] + f[1] * 3, pos[2] + f[2] * 3),
                           "fov": float(camera.fov)}
        except Exception:               # noqa: BLE001
            pass

    def _poner(self, toma):
        camera.position = tuple(toma["position"])
        pitch, yaw = cc.rotacion_mirando(toma["position"], toma["target"])
        camera.rotation = (pitch, yaw, 0)
        camera.fov = float(toma["fov"])


def toma_viva(plano, cabezas, lateral):
    """Función para `seguir`: la toma del `plano` con las cabezas de ahora (`cabezas()` -> (quien habla, jugador)), o
    None si no se pueden usar (las dos en el mismo sitio: nadie enfrente)."""
    def viva():
        h, j = cabezas()
        if cc.distancia(h, j) < 0.3:
            return None
        return cc.toma(plano, h, j, lateral)
    return viva


def a_ui(punto):
    """(x, y) en camera.ui de un punto del mundo, o None si está detrás de la cámara."""
    try:
        from panda3d.core import Point2, Point3
        from ursina import application
        base = application.base
        p_cam = base.cam.getRelativePoint(base.render, Point3(*punto))
        p2 = Point2()
        if not base.camLens.project(p_cam, p2):
            return None
        aspecto = float(window.aspect_ratio or 16 / 9)
        return (float(p2[0]) * aspecto / 2, float(p2[1]) / 2)
    except Exception:                   # noqa: BLE001
        return None
