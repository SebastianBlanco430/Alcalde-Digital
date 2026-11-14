# Sección «Gráficos» de la pantalla de Ajustes: calidad de imagen (presets Baja · retro / Media / Alta · nativa y
# pixelado del mundo) y minimapa (zoom, giro y nivel de detalle). Entra por el registro público de la escena de Ajustes
# (escena_ajustes.registrar_seccion), sin editarla; la llama daltonismo.instalar() al arrancar. También aparece en el
# menú de pausa porque éste reutiliza PantallaAjustes. La interfaz NUNCA se pixela, solo el mundo.
#
# Qué hace cada opción (verificado en el código, 2026-11-13):
#   Calidad      solo la resolución con que se dibuja el mundo (pixelado.py): Baja ¼, Media ½, Alta completa.
#                No toca sombras, niebla ni distancia (esas son banderas ALCALDE_*, no ajustes).
#   Pixelado     el mismo divisor elegido a mano, en enteros x1..x8 (pixelado_calculos.ajustar_a_divisor_entero).
#   Zoom         solo el minimapa del mapa grande (hud.Minimapa._aplicar_zoom); en el chico la fila sale atenuada.
#   Giro         el minimapa gira con la cámara o deja el norte arriba.
#   Detalle      1 calles y lugares, 2 + casas, 3 + alturas.
#
# Las listas de opciones son funciones puras (se prueban sin ventana); lo de Ursina solo ocurre al construir la sección.

from backend.logica import ajustes as modelo_ajustes
from backend.logica import mundo_config
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


# El zoom solo existe en el minimapa del mapa grande: en el chico la fila se atenúa con este motivo.
def motivo_zoom_inactivo():
    return None if mundo_config.mapa_grande_activo() else "Solo en el mapa grande"


# `s` = escena_ajustes.Seccion (o un doble con los mismos métodos anadir_*).
def construir_seccion(s):
    selector = s.anadir_selector("Calidad", "preset_grafico", opciones_preset())
    descripcion = s.anadir_texto(calc.descripcion_preset(s.gestor.actual.preset_grafico) or " ", alto=0.075)
    deslizador = s.anadir_deslizador("Pixelado del mundo", "pixel_scale", calc.formato_pixel,
                                     paso=calc.paso_deslizador())
    zoom = s.anadir_selector("Zoom del minimapa", "minimapa_zoom", opciones_zoom())
    s.anadir_selector("Giro del minimapa", "minimapa_rotacion", opciones_rotacion())
    s.anadir_selector("Detalle del minimapa", "minimapa_densidad", opciones_densidad())
    s.anadir_texto("Solo el mundo se pixela; los menús y el HUD siguen nítidos. "
                   "En el mapa grande (N): + / - zoom y R giro.", alto=0.075)

    # El deslizador cambia el preset a «Personalizada» (y un preset mueve el deslizador): se mantienen a la par.
    def sincronizar(ajustes, cambiadas):
        if not cambiadas & {"preset_grafico", "pixel_scale"}:
            return
        selector.fijar_indice(calc_ajustes.indice_de_valor(selector.opciones, ajustes.preset_grafico))
        deslizador.fijar_valor(ajustes.pixel_scale)
        s.cambiar_texto(descripcion, calc.descripcion_preset(ajustes.preset_grafico) or " ")

    s.gestor.suscribir(sincronizar, llamar_ya=False)

    # Al abrir la pestaña: el zoom se atenúa si el mapa activo es el chico.
    def al_mostrar():
        motivo = motivo_zoom_inactivo()
        zoom.fijar_habilitado(motivo is None, motivo)

    return al_mostrar


# Registra la sección en Ajustes (idempotente: reemplaza si ya existía). Importa la escena aquí para que este módulo
# se pueda importar sin Ursina.
def registrar():
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
