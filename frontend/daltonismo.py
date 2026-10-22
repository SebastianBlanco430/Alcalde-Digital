# Filtro de DALTONISMO en pantalla (Ursina/Panda3D 1.10, GL 2.1 / GLSL 1.20), aplicado a TODO lo que se ve:
# el mundo 3D y la interfaz (camera.ui). La matemática vive en frontend/daltonismo_calculos.py (pura).
#
# Cómo funciona (pase de pantalla completa):
#   1. Un FilterManager (direct.filter) saca la cámara 3D de la ventana y la dibuja en una textura.
#   2. En la ventana queda un único cuadrado a pantalla completa con un shader de matriz de color
#      (sRGB -> lineal -> M·c + d -> sRGB).
#   3. La cámara de la interfaz se re-apunta al MISMO búfer (nuevo DisplayRegion), así la UI también pasa por
#      el filtro, y su región original de la ventana se apaga. Ratón y minimapa no se enteran: la geometría
#      y las lentes no cambian.
# Con modo 'ninguno' / intensidad 0 el pase se DESMONTA por completo (coste cero y imagen idéntica a la de
# siempre): solo se paga el búfer extra cuando hay un filtro activo.
#
# No toca el contorno de tinta ni las luces/sombras: es un pase de post-proceso después de dibujar todo.
# Bandera reversible: DALTONISMO = False impide instalarlo (los ajustes se guardan igual, pero no se aplican).
# Trampa (nota 18): el shader va en el cuadrado del filtro, nunca en entidades del mundo; al desmontar
# se llama a FilterManager.cleanup() y se reactiva la región de UI original.

from panda3d.core import Shader, Texture, LVecBase3f

from frontend import daltonismo_calculos as calc

DALTONISMO = True           # bandera reversible: False = sin filtro de pantalla

_VERTICE = """
#version 120
attribute vec4 p3d_Vertex;
attribute vec2 p3d_MultiTexCoord0;
uniform mat4 p3d_ModelViewProjectionMatrix;
varying vec2 uv;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0;
}
"""

# Matriz por filas (fila0..fila2) para no depender del orden de columnas de los mat3 de Panda.
_FRAGMENTO = """
#version 120
varying vec2 uv;
uniform sampler2D escena;
uniform vec3 fila0;
uniform vec3 fila1;
uniform vec3 fila2;
uniform vec3 desplazamiento;

vec3 a_lineal(vec3 c) {
    vec3 bajo = c / 12.92;
    vec3 alto = pow((c + 0.055) / 1.055, vec3(2.4));
    return mix(alto, bajo, vec3(lessThanEqual(c, vec3(0.04045))));
}

vec3 a_srgb(vec3 c) {
    c = clamp(c, 0.0, 1.0);
    vec3 bajo = c * 12.92;
    vec3 alto = 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055;
    return mix(alto, bajo, vec3(lessThanEqual(c, vec3(0.0031308))));
}

void main() {
    vec4 pixel = texture2D(escena, uv);
    vec3 l = a_lineal(pixel.rgb);
    vec3 s = vec3(dot(fila0, l), dot(fila1, l), dot(fila2, l)) + desplazamiento;
    gl_FragColor = vec4(a_srgb(s), 1.0);
}
"""


def _vec(fila):
    return LVecBase3f(*[float(v) for v in fila])


# Pase de pantalla: se monta y desmonta; `aplicar` decide según el modo.
class FiltroPantalla:

    def __init__(self):
        self._fm = None
        self._quad = None
        self._region_ui = None
        self._region_ui_original = None
        self._textura = None
        self.activo = False
        self.ultimo = None          # (matriz, desplazamiento) aplicados, para pruebas

    # Aplica `modo` con `intensidad` (y `simular`): monta, actualiza o desmonta el pase. Devuelve True si
    # queda un filtro activo. Nunca lanza: si algo falla se desmonta y se sigue sin filtro.
    def aplicar(self, modo, intensidad=1.0, simular=False):
        if not DALTONISMO or calc.es_identidad(modo, intensidad, simular):
            self.desmontar()
            self.ultimo = None
            return False
        matriz, desplaza = calc.parametros(modo, intensidad, simular)
        try:
            if not self.activo:
                self._montar()
            self._fijar(matriz, desplaza)
        except Exception as error:      # pragma: no cover - GPU/driver sin soporte
            print(f"[daltonismo] no se pudo aplicar el filtro: {error}")
            self.desmontar()
            return False
        self.ultimo = (matriz, desplaza)
        return True

    def _fijar(self, matriz, desplaza):
        q = self._quad
        q.setShaderInput("fila0", _vec(matriz[0]))
        q.setShaderInput("fila1", _vec(matriz[1]))
        q.setShaderInput("fila2", _vec(matriz[2]))
        q.setShaderInput("desplazamiento", _vec(desplaza))

    def _montar(self):
        from direct.filter.FilterManager import FilterManager
        from ursina import application, camera

        base = application.base
        self._textura = Texture("daltonismo-escena")
        self._textura.setWrapU(Texture.WMClamp)
        self._textura.setWrapV(Texture.WMClamp)
        self._fm = FilterManager(base.win, base.cam)
        self._quad = self._fm.renderSceneInto(colortex=self._textura)
        if self._quad is None:
            self._fm = None
            raise RuntimeError("FilterManager no pudo crear el búfer")
        self._quad.setShader(Shader.make(Shader.SL_GLSL, _VERTICE, _FRAGMENTO))
        self._quad.setShaderInput("escena", self._textura)
        # La interfaz se dibuja en el mismo búfer para que también pase por el filtro.
        self._region_ui_original = camera.ui_display_region
        buffer = self._fm.buffers[0]
        self._region_ui = buffer.makeDisplayRegion()
        self._region_ui.setSort(self._region_ui_original.getSort())
        self._region_ui.setCamera(camera.ui_camera)
        self._region_ui.disableClears()
        self._region_ui.setClearDepthActive(True)
        self._region_ui_original.setActive(False)
        self.activo = True

    # Devuelve todo a como estaba (idempotente).
    def desmontar(self):
        if not self.activo and self._fm is None:
            return
        try:
            if self._region_ui is not None:
                try:
                    self._region_ui.setActive(False)
                except Exception:
                    pass
            if self._region_ui_original is not None:
                self._region_ui_original.setActive(True)
            if self._fm is not None:
                self._fm.cleanup()
        except Exception as error:      # pragma: no cover
            print(f"[daltonismo] al desmontar: {error}")
        finally:
            self._fm = None
            self._quad = None
            self._region_ui = None
            self._region_ui_original = None
            self._textura = None
            self.activo = False


_filtro = None


def filtro():
    global _filtro
    if _filtro is None:
        _filtro = FiltroPantalla()
    return _filtro


# Conecta el filtro a los ajustes: se aplica ya (con lo guardado) y en vivo al cambiar el ajuste.
# Devuelve el filtro. Llamar una vez tras crear la aplicación.
def instalar(gestor_ajustes=None):
    from backend.logica import ajustes as aj

    gestor = gestor_ajustes if gestor_ajustes is not None else aj.obtener()
    f = filtro()

    def reaccionar(ajustes, cambiadas):
        if cambiadas & {"modo_daltonismo", "intensidad", "simular_daltonismo"}:
            f.aplicar(ajustes.modo_daltonismo, ajustes.intensidad, ajustes.simular_daltonismo)

    gestor.suscribir(reaccionar)
    return f
