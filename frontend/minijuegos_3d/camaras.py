# Cámara de los minijuegos 3D (Ursina). Guarda el estado de la cámara de Ursina al tomarla y lo devuelve al soltarla (las
# escenas 2D y el mundo esperan la de siempre), y la lleva de una toma a otra con una transición suave (0,6-1 s, ease
# in-out, sin cortes). Las tomas se calculan en frontend/minijuegos_3d/camaras_calculos.py a partir de las anclas del set.
#
#   cam = CamaraMinijuego(); cam.tomar(toma_inicial)            # corte inicial (la escena viene de un destello/fundido)
#   cam.ir_a(toma, duracion=0.8, al_llegar=None)                # transición suave
#   cam.avanzar(dt)                                             # cada frame (lo llama Minijuego3D.avanzar)
#   cam.llegada  -> True cuando no hay transición en curso
#   cam.poner(toma)                                             # corte a `toma` (cancela la transición); lo usa cinematica_silla
#   cam.soltar()                                                # devuelve la cámara de Ursina como estaba

from ursina import camera, scene

from frontend.minijuegos_3d import camaras_calculos as cc

NEAR, FAR = 0.03, 60.0


class CamaraMinijuego:

    def __init__(self):
        self._guardada = None
        self.actual = None
        self._desde = None
        self._hacia = None
        self._t = 0.0
        self._duracion = 0.0
        self._al_llegar = None

    @property
    def llegada(self):
        return self._hacia is None

    def tomar(self, toma):
        """Toma la cámara de Ursina (guarda su estado una sola vez) y la pone en `toma` sin transición."""
        if self._guardada is None:
            self._guardada = {"parent": camera.parent, "orthographic": camera.orthographic, "fov": camera.fov,
                              "position": camera.position, "rotation": camera.rotation,
                              "near": camera.clip_plane_near, "far": camera.clip_plane_far}
        camera.parent = scene
        camera.orthographic = False
        camera.clip_plane_near = NEAR
        camera.clip_plane_far = FAR
        self._hacia = None
        self._poner(toma)

    def ir_a(self, toma, duracion=cc.DURACION_TRANSICION, al_llegar=None):
        if self.actual is None or duracion <= 0:
            self.tomar(toma)
            if al_llegar is not None:
                al_llegar()
            return
        self._desde, self._hacia = dict(self.actual), toma
        self._t, self._duracion, self._al_llegar = 0.0, float(duracion), al_llegar

    def poner(self, toma):
        """Pone la cámara en `toma` en el acto (sin transición; cancela la que hubiera, SIN llamar su al_llegar). Si aún no
        se había tomado la cámara de Ursina, la toma (como tomar). `actual` queda en `toma`: un ir_a posterior parte de
        ahí. Lo usa frontend/cinematica_silla.py (contrato-silla §3, `camara=`)."""
        if self._guardada is None:
            self.tomar(toma)
            return
        self._hacia = None
        self._al_llegar = None
        self._poner(toma)

    def avanzar(self, dt):
        if self._hacia is None:
            return
        self._t += dt
        k = min(1.0, self._t / self._duracion)
        self._poner(cc.interpolar(self._desde, self._hacia, cc.suave(k)))
        if k >= 1.0:
            self._hacia = None
            callback, self._al_llegar = self._al_llegar, None
            if callback is not None:
                callback()

    def _poner(self, toma):
        self.actual = {"position": tuple(toma["position"]), "target": tuple(toma["target"]), "fov": float(toma["fov"])}
        camera.position = self.actual["position"]
        pitch, yaw = cc.rotacion_mirando(self.actual["position"], self.actual["target"])
        camera.rotation = (pitch, yaw, 0)
        camera.fov = self.actual["fov"]

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


def aspecto_ventana():
    try:
        from ursina import window
        return float(window.aspect_ratio)
    except Exception:                    # noqa: BLE001
        return 16 / 9
