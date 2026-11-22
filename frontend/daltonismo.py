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
# PASE ÚNICO con el pixelado (frontend/pixelado.py): este FiltroPantalla es el único dueño del FilterManager. Si hay
# pixelado (divisor > 1) se añade una etapa intermedia (mundo en búfer pequeño -> ampliado NEAREST a resolución nativa,
# con la interfaz dibujada encima, nítida) y el cuadrado final aplica la matriz de color (o ninguna). Con daltonismo y
# pixelado apagados no se monta nada.
#
# No toca el contorno de tinta ni las luces/sombras: es un pase de post-proceso después de dibujar todo.
# Bandera reversible: DALTONISMO = False impide instalarlo (los ajustes se guardan igual, pero no se aplican).
# Trampa (nota 18): el shader va en el cuadrado del filtro, nunca en entidades del mundo; al desmontar
# se llama a FilterManager.cleanup() y se reactiva la región de UI original.

from panda3d.core import Shader, Texture, LVecBase3f

from frontend import daltonismo_calculos as calc
from frontend import pase_final_calculos as pase_calc
from frontend import pixelado

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
# PASE FINAL ÚNICO (T3 + M6, frontend/pase_final_calculos.py): el mismo shader hace, según sus interruptores (float 0/1):
#   usar_tinta    tinta de pantalla: Sobel sobre la profundidad LINEAL con umbral relativo (|Δz|/z), 1 texel a 720p, solo
#                 en el lado cercano del borde, nunca en el cielo; el color va hacia el de la niebla y se apaga a lo lejos.
#   usar_grading  saturación alrededor de la luma y tinte multiplicativo (salud de la ciudad).
#   usar_matriz   la matriz de color del daltonismo (sRGB -> lineal -> M·c + d -> sRGB).
# Con los tres apagados salvo la matriz el resultado es idéntico al del filtro de siempre.
_FRAGMENTO = """
#version 120
varying vec2 uv;
uniform sampler2D escena;
uniform sampler2D profundidad;
uniform vec3 fila0;
uniform vec3 fila1;
uniform vec3 fila2;
uniform vec3 desplazamiento;
uniform float usar_matriz;
uniform float usar_tinta;
uniform float usar_grading;
uniform vec3 camara;          // cerca, lejos, ortográfica (0/1)
uniform vec2 paso;            // texel del vecino del Sobel
uniform vec4 tinta;           // rgb + umbral bajo
uniform vec4 niebla;          // rgb + fuerza
uniform vec4 rango;           // fin de niebla, umbral alto, inicio y fin del desvanecido (fracciones)
uniform float saturacion;
uniform vec3 tinte;
uniform vec4 extra;           // R5: pliegues (0/1), umbral bajo y alto del pliegue, fuerza del violeta lejano
uniform float mezcla_post;    // cierre: 0..1, fundido de tinta+grading al cerrar la pausa (1 = como siempre)

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

float lineal(vec2 p) {
    float d = texture2D(profundidad, p).r;
    if (camara.z > 0.5) {
        return camara.x + d * (camara.y - camara.x);
    }
    return (camara.x * camara.y) / (camara.y - d * (camara.y - camara.x));
}

vec3 con_tinta(vec3 c) {
    float zc = lineal(uv);
    if (zc >= 0.6 * camara.y) {
        return c;
    }
    float z00 = lineal(uv + vec2(-paso.x,  paso.y));
    float z01 = lineal(uv + vec2(0.0,      paso.y));
    float z02 = lineal(uv + vec2( paso.x,  paso.y));
    float z10 = lineal(uv + vec2(-paso.x,  0.0));
    float z12 = lineal(uv + vec2( paso.x,  0.0));
    float z20 = lineal(uv + vec2(-paso.x, -paso.y));
    float z21 = lineal(uv + vec2(0.0,     -paso.y));
    float z22 = lineal(uv + vec2( paso.x, -paso.y));
    float gx = (z02 + 2.0 * z12 + z22) - (z00 + 2.0 * z10 + z20);
    float gy = (z20 + 2.0 * z21 + z22) - (z00 + 2.0 * z01 + z02);
    float borde = length(vec2(gx, gy)) / max(zc, 1e-4);
    float zmax = max(max(max(z00, z01), max(z02, z10)), max(max(z12, z20), max(z21, z22)));
    float zmin = min(min(min(z00, z01), min(z02, z10)), min(min(z12, z20), min(z21, z22)));
    float cercano = step(zc - min(zmin, zc), max(zmax, zc) - zc);
    float fuerza = smoothstep(tinta.a, rango.y, borde) * cercano;
    if (extra.x > 0.5) {
        float wc = 1.0 / max(zc, 1e-4);
        float lap = 1.0 / max(z01, 1e-4) + 1.0 / max(z10, 1e-4) + 1.0 / max(z12, 1e-4) + 1.0 / max(z21, 1e-4) - 4.0 * wc;
        fuerza = max(fuerza, 0.8 * smoothstep(extra.y, extra.z, abs(lap) / wc) * cercano);
    }
    float fin = max(rango.x, 1.0);
    float opacidad = 1.0 - smoothstep(rango.z * fin, rango.w * fin, zc);
    vec3 color_linea = mix(tinta.rgb, niebla.rgb, clamp(zc / fin, 0.0, 1.0) * niebla.a);
    return mix(c, color_linea, fuerza * opacidad);
}

void main() {
    vec4 pixel = texture2D(escena, uv);
    vec3 c = pixel.rgb;
    vec3 sin_post = c;
    if (usar_tinta > 0.5) {
        c = con_tinta(c);
        if (extra.w > 0.0) {
            float z = lineal(uv);
            if (z < 0.6 * camara.y) {
                float fin_v = max(rango.x, 1.0);
                float yl = dot(c, vec3(0.2126, 0.7152, 0.0722));
                vec3 violeta = vec3(88.0, 78.0, 140.0) / 255.0;
                float yv = dot(violeta, vec3(0.2126, 0.7152, 0.0722));
                vec3 objetivo = min(violeta * (yl / yv), vec3(1.0));
                float k = extra.w * (1.0 - smoothstep(0.15, 0.55, yl)) * smoothstep(0.05 * fin_v, rango.w * fin_v, z);
                c = mix(c, objetivo, k);
            }
        }
    }
    if (usar_grading > 0.5) {
        float y = dot(c, vec3(0.2126, 0.7152, 0.0722));
        c = clamp((vec3(y) + (c - vec3(y)) * saturacion) * tinte, 0.0, 1.0);
    }
    c = mix(sin_post, c, clamp(mezcla_post, 0.0, 1.0));
    if (usar_matriz > 0.5) {
        vec3 l = a_lineal(c);
        c = a_srgb(vec3(dot(fila0, l), dot(fila1, l), dot(fila2, l)) + desplazamiento);
    }
    gl_FragColor = vec4(c, 1.0);
}
"""


def _vec(fila):
    return LVecBase3f(*[float(v) for v in fila])


# Pase de pantalla: se monta y desmonta; `aplicar` (color), `fijar_pixelado` (resolución) y `fijar_post` (tinta y grading
# del pase final, frontend/pase_final.py) deciden qué hace falta (pase_final_calculos.topologia).
class FiltroPantalla:

    def __init__(self):
        self._fm = None
        self._quad = None
        self._cuadro_etapa = None       # cuadro de la etapa nativa (pixel/etapa): ahí van la tinta y el grading
        self._region_ui = None
        self._region_ui_original = None
        self._textura = None            # lo que dibuja la cámara 3D
        self._profundidad = None        # profundidad del mundo (solo con tinta de pantalla)
        self._textura_final = None      # lo que lee el cuadrado de la ventana (= _textura, o la etapa nativa)
        self._topologia = None          # pase_final_calculos.topologia: "simple" | "post" | "etapa" | "pixel"
        self._con_profundidad = False
        self.activo = False
        self.ultimo = None              # (matriz, desplazamiento) aplicados, para pruebas
        self._color = None              # (matriz, desplazamiento) pedidos, o None = sin filtro de color
        self.divisor = 1.0              # pixelado pedido (1 = nativo)
        self._tinta = False             # tinta de pantalla pedida
        self._grading = False           # grading de salud pedido
        self.tinta_ok = True            # False si el búfer no da profundidad (la tinta se apaga, el resto sigue)
        self._uniformes = {}            # entradas del shader del pase final (las fija frontend/pase_final.py)
        self.en_menu = False            # R2: menú de pausa abierto -> pase neutro (pase_calc.interruptores_post)
        self._mezcla = 1.0              # cierre (punto 5): mezcla del pase final (fundido al cerrar la pausa)
        self._tarea_fundido = None

    # Aplica `modo` con `intensidad` (y `simular`): monta, actualiza o desmonta el pase. Devuelve True si
    # queda un filtro de color activo. Nunca lanza: si algo falla se desmonta y se sigue sin filtro.
    def aplicar(self, modo, intensidad=1.0, simular=False):
        if not DALTONISMO or calc.es_identidad(modo, intensidad, simular):
            self._color = None
        else:
            self._color = calc.parametros(modo, intensidad, simular)
        self._reconciliar()
        return self.ultimo is not None

    # Pide el pixelado: `divisor` 1 = nativo (sin etapa), 4 = el mundo a un cuarto de resolución. Devuelve True si queda
    # una etapa de pixelado montada.
    def fijar_pixelado(self, divisor):
        try:
            divisor = float(divisor)
        except (TypeError, ValueError):
            divisor = 1.0
        self.divisor = divisor if divisor == divisor and divisor > 1.0 else 1.0
        self._reconciliar()
        return self.activo and self._topologia == "pixel"

    # Pase final (T3 + M6): `tinta` = tinta de pantalla, `grading` = saturación/tinte de salud. Devuelve True si queda
    # montado un pase con alguno de los dos.
    def fijar_post(self, tinta, grading):
        self._tinta, self._grading = bool(tinta), bool(grading)
        self._reconciliar()
        return self._cuadro_post() is not None

    # Entradas del shader del pase final (dict nombre -> valor); solo se mandan las que cambian.
    def fijar_uniformes(self, valores):
        cambiadas = {k: v for k, v in valores.items() if self._uniformes.get(k) != v}
        self._uniformes.update(cambiadas)
        q = self._cuadro_post()
        if q is not None and cambiadas:
            for nombre, valor in cambiadas.items():
                q.setShaderInput(nombre, _entrada(valor))

    # R2: con un menú a pantalla completa (pausa) abierto el pase va neutro: el velo translúcido no deja ver el mundo
    # teñido ni entintado. Cambia los interruptores al momento, sin remontar nada.
    def fijar_menu(self, abierto):
        abierto = bool(abierto)
        if abierto == self.en_menu:
            return
        self.en_menu = abierto
        q = self._cuadro_post()
        if q is not None:
            tinta, grading = self._interruptores()
            q.setShaderInput("usar_tinta", _entrada(tinta))
            q.setShaderInput("usar_grading", _entrada(grading))
        self._parar_fundido()
        if not abierto and pase_calc.neutro_en_menus_activo() and pase_calc.fundido_pausa_activo():
            self._empezar_fundido()                  # cierre: vuelve en 0,3 s, no de golpe

    def _fijar_mezcla(self, valor):
        self._mezcla = float(valor)
        q = self._cuadro_post()
        if q is not None:
            q.setShaderInput("mezcla_post", _entrada(self._mezcla))

    def _parar_fundido(self):
        if self._tarea_fundido is not None:
            try:
                from ursina import application
                application.base.taskMgr.remove(self._tarea_fundido)
            except Exception:                         # noqa: BLE001
                pass
            self._tarea_fundido = None
        if self._mezcla != 1.0:
            self._fijar_mezcla(1.0)

    def _empezar_fundido(self):
        try:
            from panda3d.core import ClockObject
            from ursina import application
            reloj = ClockObject.getGlobalClock()
            inicio = reloj.getRealTime()
            self._fijar_mezcla(0.0)

            def paso(tarea):
                m = pase_calc.mezcla_fundido(reloj.getRealTime() - inicio)
                self._fijar_mezcla(m)
                if m >= 1.0:
                    self._tarea_fundido = None
                    return tarea.done
                return tarea.cont

            self._tarea_fundido = application.base.taskMgr.add(paso, "fundido_pausa")
        except Exception:                             # noqa: BLE001  sin bucle de Panda: como antes (de golpe)
            self._tarea_fundido = None
            self._fijar_mezcla(1.0)

    def _interruptores(self):
        return pase_calc.interruptores_post(self._tinta, self._grading, self._con_profundidad, self.en_menu,
                                            pase_calc.neutro_en_menus_activo())

    def tinta_montada(self):
        return self._con_profundidad and self._tinta and self._cuadro_post() is not None

    def _con_post(self):
        return self._grading or (self._tinta and self.tinta_ok)

    def _reconciliar(self):
        con_color = DALTONISMO and self._color is not None
        con_pixel = pixelado.PIXELADO and self.divisor > 1.0
        topologia = pase_calc.topologia(con_color, con_pixel, self._con_post())
        if topologia is None:
            self.desmontar()
            self.ultimo = None
            return
        con_profundidad = self._tinta and self.tinta_ok
        try:
            if self.activo and (self._topologia != topologia or self._con_profundidad != con_profundidad):
                self.desmontar()
            if not self.activo:
                self._montar(topologia, con_profundidad)
            if not self.activo:
                self.ultimo = None
                return
            if self._topologia == "pixel":
                pixelado.fijar_divisor(self._fm, self.divisor)
            self._fijar(self._color if con_color else None)
        except Exception as error:      # pragma: no cover - GPU/driver sin soporte
            print(f"[daltonismo] no se pudo aplicar el pase de pantalla: {error}")
            self.desmontar()
            self.ultimo = None
            return
        self.ultimo = self._color if con_color else None

    # Cuadro que lleva la tinta y el grading: el de la ventana en "post", el de la etapa nativa en "etapa"/"pixel".
    def _cuadro_post(self):
        if not self.activo or not self._con_post():
            return None
        if self._topologia == "post":
            return self._quad
        if self._topologia in ("etapa", "pixel"):
            return self._cuadro_etapa
        return None

    # Matriz de color en el cuadrado final; None = sin filtro de color (solo pixelado): se muestra la textura tal cual,
    # sin shader. La tinta y el grading van en _cuadro_post() (nunca debajo de la interfaz).
    def _fijar(self, filtro_color):
        q = self._quad
        post = self._cuadro_post()
        if post is not None and post is not q:
            self._fijar_shader(post, self._textura, None, con_post=True)
        elif self._cuadro_etapa is not None and post is None:
            self._cuadro_etapa.clearShader()        # pixelado sin pase final: el cuadro ampliado de siempre
            self._cuadro_etapa.setTexture(self._textura)
            self._cuadro_etapa.setColor(1, 1, 1, 1)
        if post is q:
            self._fijar_shader(q, self._textura_final, filtro_color, con_post=True)
            return
        if filtro_color is None:
            q.clearShader()
            q.setTexture(self._textura_final)
            q.setColor(1, 1, 1, 1)
            return
        self._fijar_shader(q, self._textura_final, filtro_color, con_post=False)

    def _fijar_shader(self, q, textura, filtro_color, con_post):
        q.setShader(_shader())
        q.setShaderInput("escena", textura)
        q.setShaderInput("profundidad", self._profundidad if self._profundidad is not None else textura)
        if filtro_color is None:
            matriz, desplaza = ((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0)
        else:
            matriz, desplaza = filtro_color
        q.setShaderInput("fila0", _vec(matriz[0]))
        q.setShaderInput("fila1", _vec(matriz[1]))
        q.setShaderInput("fila2", _vec(matriz[2]))
        q.setShaderInput("desplazamiento", _vec(desplaza))
        q.setShaderInput("usar_matriz", 1.0 if filtro_color is not None else 0.0)
        valores = dict(_UNIFORMES_NEUTROS)
        if con_post:
            valores.update(self._uniformes)
            valores["usar_tinta"], valores["usar_grading"] = self._interruptores()
            valores["mezcla_post"] = self._mezcla
        for nombre, valor in valores.items():
            q.setShaderInput(nombre, _entrada(valor))

    # Suavizado (frontend/suavizado.py): con MSAA en la ventana, el búfer del mundo lo pide también (cuando va a resolución
    # nativa: no con pixelado, donde el MSAA casi no se nota). Si el búfer multimuestra no se puede crear o no queda con las
    # muestras pedidas, se monta otra vez sin MSAA (un aviso en consola) y nunca se cae. Si el búfer con profundidad falla,
    # se apaga SOLO la tinta de pantalla (un aviso por stderr) y se monta sin profundidad.
    def _montar(self, topologia, con_profundidad=False):
        try:
            self._montar_msaa(topologia, con_profundidad)
            if con_profundidad:
                self._comprobar_profundidad()
        except Exception as error:
            if not con_profundidad:
                raise
            self.desmontar()
            self._apagar_tinta(error)
            topologia = pase_calc.topologia(DALTONISMO and self._color is not None,
                                            pixelado.PIXELADO and self.divisor > 1.0, self._con_post())
            if topologia is not None:
                self._montar_msaa(topologia, False)

    def _montar_msaa(self, topologia, con_profundidad):
        from frontend import suavizado
        con_msaa = topologia != "pixel" and suavizado.filtro_con_msaa()
        try:
            self._montar_con(topologia, suavizado.propiedades_filtro(con_msaa), con_profundidad)
            if con_msaa:
                self._comprobar_msaa(suavizado.pedidas())
        except Exception as error:
            if not con_msaa:
                raise
            self.desmontar()
            suavizado.desactivar_filtro(error)
            self._montar_con(topologia, suavizado.propiedades_filtro(False), con_profundidad)
        suavizado.registrar_filtro(self._muestras_mundo())

    def _muestras_mundo(self):
        """VIS-009: muestras del búfer donde se dibuja el mundo (el primero del FilterManager); 0 si no se sabe."""
        try:
            buffer = self._fm.buffers[0]
            return buffer.getFbProperties().getMultisamples() if buffer.isValid() else 0
        except Exception:
            return 0

    def _apagar_tinta(self, motivo):
        import sys
        self.tinta_ok = False
        print(f"[pase_final] la tinta de pantalla no tiene profundidad ({motivo}); sigo sin ella.", file=sys.stderr)

    # Abre ya el búfer (sin dibujar) y mira si es válido y multimuestra; si no, lanza.
    def _comprobar_msaa(self, pedidas):
        from ursina import application
        application.base.graphicsEngine.openWindows()
        buffer = self._fm.buffers[0]
        obtenidas = buffer.getFbProperties().getMultisamples() if buffer.isValid() else -1
        if obtenidas < pedidas:
            raise RuntimeError(f"búfer con {obtenidas} muestras, pedidas {pedidas}")

    # Abre el búfer y mira que sea válido y tenga bits de profundidad; si no, lanza.
    def _comprobar_profundidad(self):
        from ursina import application
        application.base.graphicsEngine.openWindows()
        buffer = self._fm.buffers[0]
        if not buffer.isValid():
            raise RuntimeError("búfer del mundo no válido")
        bits = buffer.getFbProperties().getDepthBits()
        if bits <= 0:
            raise RuntimeError(f"búfer sin profundidad ({bits} bits)")

    def _montar_con(self, topologia, propiedades, con_profundidad=False):
        from direct.filter.FilterManager import FilterManager
        from ursina import application, camera

        base = application.base
        self._textura = Texture("daltonismo-escena")
        self._textura.setWrapU(Texture.WMClamp)
        self._textura.setWrapV(Texture.WMClamp)
        self._fm = FilterManager(base.win, base.cam)
        argumentos = {"colortex": self._textura}
        if con_profundidad:
            self._profundidad = Texture("pase-profundidad")
            self._profundidad.setWrapU(Texture.WMClamp)
            self._profundidad.setWrapV(Texture.WMClamp)
            argumentos["depthtex"] = self._profundidad
        if propiedades is not None:     # sin el prc de MSAA: la llamada de siempre
            argumentos["fbprops"] = propiedades
        self._quad = self._fm.renderSceneInto(**argumentos)
        if self._quad is None:
            self._fm = None
            self._profundidad = None
            raise RuntimeError("FilterManager no pudo crear el búfer")
        self._con_profundidad = con_profundidad
        self._textura_final = self._textura
        if topologia in ("pixel", "etapa"):
            divisor = self.divisor if topologia == "pixel" else 1.0
            self._textura_final, self._cuadro_etapa = pixelado.anadir_etapa_nativa(
                self._fm, self._textura, divisor, devolver_cuadro=True)
        self._topologia = topologia
        self.activo = True
        if topologia == "post":
            return          # la interfaz sigue en su región de la ventana, encima del cuadro: sin tinta ni grading
        # La interfaz se dibuja en el ÚLTIMO búfer (a resolución nativa) para que también pase por el filtro de color
        # y nunca por la reducción del pixelado (ni por la tinta/grading, que van en el cuadro de la etapa, debajo).
        self._region_ui_original = camera.ui_display_region
        buffer = self._fm.buffers[-1]
        self._region_ui = buffer.makeDisplayRegion()
        orden = self._region_ui_original.getSort()
        self._region_ui.setSort(max(orden, 10) if topologia in ("pixel", "etapa") else orden)
        self._region_ui.setCamera(camera.ui_camera)
        self._region_ui.disableClears()
        self._region_ui.setClearDepthActive(True)
        self._region_ui_original.setActive(False)

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
            try:
                from frontend import suavizado
                suavizado.registrar_filtro(None)        # VIS-009: el mundo vuelve a la ventana
            except Exception:
                pass
            self._fm = None
            self._quad = None
            self._cuadro_etapa = None
            self._region_ui = None
            self._region_ui_original = None
            self._textura = None
            self._profundidad = None
            self._textura_final = None
            self._topologia = None
            self._con_profundidad = False
            self.activo = False


# Valores del pase final cuando no hay tinta ni grading (el shader hace solo lo que pidan sus interruptores).
_UNIFORMES_NEUTROS = {
    "usar_tinta": 0.0, "usar_grading": 0.0,
    "camara": (0.1, 500.0, 0.0), "paso": (1.0 / 1280.0, 1.0 / 720.0),
    "tinta": (*pase_calc.COLOR_TINTA, pase_calc.UMBRAL_BAJO),
    "niebla": (0.0, 0.0, 0.0, 0.0),
    "rango": (pase_calc.FIN_SIN_NIEBLA, pase_calc.UMBRAL_ALTO, pase_calc.DESVANECE_INICIO, pase_calc.DESVANECE_FIN),
    "saturacion": 1.0, "tinte": (1.0, 1.0, 1.0),
    "extra": (0.0, pase_calc.PLIEGUE_BAJO, pase_calc.PLIEGUE_ALTO, 0.0),
    "mezcla_post": 1.0,
}


def _entrada(valor):
    if isinstance(valor, (tuple, list)):
        from panda3d.core import LVecBase2f, LVecBase4f
        valores = [float(v) for v in valor]
        return {2: LVecBase2f, 3: LVecBase3f, 4: LVecBase4f}[len(valores)](*valores)
    return float(valor)


_shader_cache = None


def _shader():
    global _shader_cache
    if _shader_cache is None:
        _shader_cache = Shader.make(Shader.SL_GLSL, _VERTICE, _FRAGMENTO)
    return _shader_cache


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
    # Pixelado (mismo pase) y sección «Gráficos» de Ajustes. Si fallan, el daltonismo sigue funcionando.
    try:
        pixelado.instalar(gestor, f)
        from frontend import graficos_ajustes
        graficos_ajustes.registrar()
    except Exception as error:      # pragma: no cover
        print(f"[daltonismo] no se pudo instalar el pixelado: {error}")
    # Pase final (tinta de pantalla + grading de salud) en el mismo cuadro. Si falla, lo demás sigue igual.
    try:
        from frontend import pase_final
        pase_final.ui_sin_niebla()       # R2: independiente de las banderas del pase
        pase_final.instalar(gestor, f)
    except Exception as error:      # pragma: no cover
        import sys
        print(f"[pase_final] no se pudo instalar: {error}", file=sys.stderr)
    return f
