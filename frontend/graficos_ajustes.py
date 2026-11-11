# Sección «Gráficos» de la pantalla de Ajustes: calidad de imagen (presets Retro / Nítido / Normal y tamaño del píxel
# del mundo) y minimapa (zoom, giro y nivel de detalle). Entra por el registro público de la escena de Ajustes
# (escena_ajustes.registrar_seccion), sin editarla; la llama daltonismo.instalar() al arrancar. También aparece en el
# menú de pausa porque éste reutiliza PantallaAjustes. La interfaz NUNCA se pixela, solo el mundo.
#
# Las listas de opciones son funciones puras (se prueban sin ventana); lo de Ursina solo ocurre al construir la sección.

from backend.logica import ajustes as modelo_ajustes
from frontend import ajustes_calculos as calc_ajustes
from frontend import pixelado_calculos as calc

NOMBRE_SECCION = "Gráficos"


def opciones_preset():
    return calc.nombres_presets()


def opciones_zoom():
    return [(f"{z:g}x".replace(".", ","), z) for z in modelo_ajustes.MINIMAPA_ZOOMS]


def opciones_rotacion():
    return [("Con la cámara", "camara"), ("Norte arriba", "norte")]


def opciones_densidad():
    return [("Básico", 1), ("Normal", 2), ("Detallado", 3)]


# `s` = escena_ajustes.Seccion (o un doble con los mismos métodos anadir_*).
def construir_seccion(s):
    selector = s.anadir_selector("Calidad", "preset_grafico", opciones_preset())
    deslizador = s.anadir_deslizador("Tamaño del píxel", "pixel_scale", calc.formato_pixel)
    s.anadir_selector("Zoom del minimapa", "minimapa_zoom", opciones_zoom())
    s.anadir_selector("Giro del minimapa", "minimapa_rotacion", opciones_rotacion())
    s.anadir_selector("Detalle del minimapa", "minimapa_densidad", opciones_densidad())
    s.anadir_texto("Solo el mundo se pixela; los menús y el HUD siguen nítidos. Retro es el más pixelado. "
                   "En el mapa grande (N): + / - zoom y R giro.", alto=0.075)

    # El deslizador cambia el preset a «Personalizado» (y un preset mueve el deslizador): se mantienen a la par.
    def sincronizar(ajustes, cambiadas):
        if not cambiadas & {"preset_grafico", "pixel_scale"}:
            return
        selector.fijar_indice(calc_ajustes.indice_de_valor(selector.opciones, ajustes.preset_grafico))
        deslizador.fijar_valor(ajustes.pixel_scale)

    s.gestor.suscribir(sincronizar, llamar_ya=False)


# Registra la sección en Ajustes (idempotente: reemplaza si ya existía). Importa la escena aquí para que este módulo
# se pueda importar sin Ursina.
def registrar():
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
