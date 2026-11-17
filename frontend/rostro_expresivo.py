# Cara con EXPRESIÓN para el interrogatorio de novela visual (frontend/interrogatorio_vn.py). Envuelve el RostroAnimado
# de siempre (frontend/rostro_modelo.py, que no se toca) y le da lo que no tiene: cejas, sonrisa, mirada y ritmo de
# parpadeo según un perfil de expresión (frontend/interrogatorio_vn_calculos.PERFILES), con transiciones suaves, y una
# boca que se abre con cada letra del texto que aparece (apertura forzada).
#
# Se instala sustituyendo `personaje.rostro` por este envoltorio: PersonajeModelo.update() lo sigue llamando igual
# (actualizar(t, clip, rumbo, dt)). Usa los aplicadores _ojos/_cejas/_boca del rostro de siempre.
# GUARDIÁN: si algo falla, avisa una vez por stderr y deja la cara con su animación de siempre.

from frontend import banderas_visuales as bv
from frontend import interrogatorio_vn_calculos as calc
from frontend import rostro_animacion_calculos as ra

SUAVIZADO = 0.12           # s de la exponencial de cada rasgo (la mezcla entre perfiles ya dura TIEMPO_MEZCLA)


class RostroExpresivo:

    def __init__(self, base, semilla=0):
        self.base = base
        self.semilla = int(semilla)
        self.perfil = calc.perfil_de("neutral")
        self.apertura_forzada = None      # 0..1 mientras el texto aparece letra a letra; None = la boca de siempre
        self.roto = False
        self._estado = {"alza": 0.1, "frunce": 0.0, "sonrisa": 0.3, "apertura": 0.0, "mx": 0.0, "mz": 0.0}

    def __getattr__(self, nombre):            # lo que no sea de aquí, al rostro de siempre
        return getattr(self.base, nombre)

    def actualizar(self, t, clip, rumbo=None, dt=0.0):
        if self.roto or getattr(self.base, "roto", False):
            return self.base.actualizar(t, clip, rumbo, dt) if not getattr(self.base, "roto", False) else None
        try:
            self._actualizar(t, clip, dt)
        except Exception as error:            # noqa: BLE001
            bv.avisar_una_vez("rostro_expresivo", error)
            self.roto = True

    def _actualizar(self, t, clip, dt):
        p = self.perfil
        dt = ra.acotar(dt, 0.0, 0.25)
        cierre = calc.parpadeo(t, p["parpadeo"], self.semilla)
        mx, mz = calc.mirada(t, p, self.semilla)
        if self.apertura_forzada is not None:
            apertura = self.apertura_forzada
        elif clip == ra.HABLAR:
            apertura = ra.apertura_silaba(t, self.semilla)
        else:
            apertura = 0.0
        objetivos = {"alza": p["alza"], "frunce": p["frunce"], "sonrisa": p["sonrisa"], "apertura": apertura,
                     "mx": mx, "mz": mz}
        for clave, objetivo in objetivos.items():
            tiempo = 0.035 if clave == "apertura" else SUAVIZADO
            self._estado[clave] = ra.suavizar(self._estado[clave], objetivo, dt, tiempo)
        e = self._estado
        self.base._ojos(ra.acotar(cierre), e["mx"], e["mz"])
        self.base._cejas(ra.acotar(e["alza"]), ra.acotar(e["frunce"]))
        self.base._boca(ra.acotar(e["apertura"]), ra.acotar(e["sonrisa"]))


def instalar(personaje, semilla=0):
    """Pone el envoltorio a `personaje.rostro` (si tiene un RostroAnimado). Devuelve el envoltorio o None."""
    base = getattr(personaje, "rostro", None)
    if base is None or not hasattr(base, "_ojos"):
        return None
    if isinstance(base, RostroExpresivo):
        return base
    envoltorio = RostroExpresivo(base, semilla)
    personaje.rostro = envoltorio
    return envoltorio
