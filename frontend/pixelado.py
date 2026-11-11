# PIXELADO del mundo (Ursina/Panda3D 1.10): el mundo 3D se dibuja en un búfer offscreen MÁS PEQUEÑO y se amplía con
# filtro NEAREST (píxeles grandes y nítidos); la interfaz (camera.ui) se dibuja siempre a la resolución nativa.
# La matemática (divisor, presets, tamaño interno) vive en frontend/pixelado_calculos.py (pura).
#
# Un ÚNICO pase de pantalla con el daltonismo (frontend/daltonismo.py es dueño del FilterManager): este módulo solo
# añade la etapa intermedia y la conexión a los ajustes. Cadena con el pixelado activo:
#
#   cámara 3D --> [búfer A: ventana / divisor] textura A (NEAREST)
#   textura A --> [búfer B: ventana nativa] cuadrado + región de la interfaz (camera.ui, nítida)  --> textura B
#   textura B --> ventana: cuadrado final con la matriz de color del daltonismo (o sin shader si no hay filtro)
#
# Sin pixelado (escala 0) esta etapa NO existe: el pase es el de siempre del daltonismo (o ninguno, coste cero).
# Bandera reversible: PIXELADO = False impide montar la etapa (los ajustes se guardan igual, pero no se aplican).

from panda3d.core import FrameBufferProperties, SamplerState, Texture

from frontend import pixelado_calculos as calc

PIXELADO = True             # bandera reversible: False = sin pixelado


# Añade al FilterManager `fm` (que ya hizo renderSceneInto con `textura_mundo`) la etapa de resolución nativa.
# Devuelve la textura final (la que debe mostrar el cuadrado de la ventana). Lanza si no se puede crear el búfer.
def anadir_etapa_nativa(fm, textura_mundo, divisor):
    textura_mundo.setMagfilter(SamplerState.FT_nearest)
    textura_mundo.setMinfilter(SamplerState.FT_nearest)
    textura_final = Texture("pixelado-nativo")
    textura_final.setWrapU(Texture.WMClamp)
    textura_final.setWrapV(Texture.WMClamp)
    # renderQuadInto crea el búfer SIN profundidad si no se le da una textura de profundidad; la interfaz la necesita.
    propiedades = FrameBufferProperties()
    propiedades.setDepthBits(24)
    cuadro = fm.renderQuadInto("pixelado-nativo", colortex=textura_final, fbprops=propiedades)
    if cuadro is None:
        raise RuntimeError("FilterManager no pudo crear el búfer nativo")
    cuadro.setTexture(textura_mundo)
    cuadro.setColor(1, 1, 1, 1)
    fijar_divisor(fm, divisor)
    return textura_final


# Cambia el tamaño del búfer del mundo (etapa A). Los búferes siguen la ventana al redimensionarla (sizes).
def fijar_divisor(fm, divisor):
    divisor = max(1.0, float(divisor))
    fm.sizes[0] = (1.0 / divisor, 1, 1)
    fm.resizeBuffers()


# Conecta el pixelado a los ajustes: mantiene coherentes preset y escala, y aplica el divisor al filtro de pantalla en
# vivo. `filtro` = daltonismo.FiltroPantalla. Devuelve la función suscrita (para pruebas).
def instalar(gestor, filtro):
    def reaccionar(ajustes, cambiadas):
        if not cambiadas & {"pixel_scale", "preset_grafico"}:
            return
        preset, escala = calc.reconciliar(ajustes.preset_grafico, ajustes.pixel_scale, cambiadas)
        if (preset, escala) != (ajustes.preset_grafico, ajustes.pixel_scale):
            gestor.cambiar(preset_grafico=preset, pixel_scale=escala)    # reentra con las dos claves ya coherentes
            return
        divisor = 1.0 if (not PIXELADO or calc.es_nativa(escala)) else calc.divisor_de_escala(escala)
        filtro.fijar_pixelado(divisor)

    gestor.suscribir(reaccionar)
    return reaccionar
