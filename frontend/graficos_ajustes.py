# Sección «Gráficos» de la pantalla de Ajustes: calidad de imagen (presets Baja · retro / Media / Alta · nativa y
# pixelado del mundo) y minimapa (giro y nivel de detalle). Entra por el registro público de la escena de Ajustes
# (escena_ajustes.registrar_seccion), sin editarla; la llama daltonismo.instalar() al arrancar. También aparece en el
# menú de pausa porque éste reutiliza PantallaAjustes. La interfaz NUNCA se pixela, solo el mundo.
#
# Qué hace cada opción (verificado en el código, 2026-11-13):
#   Calidad      solo la resolución con que se dibuja el mundo (pixelado.py): Baja ¼, Media ½, Alta completa.
#                No toca sombras, niebla ni distancia (esas son banderas ALCALDE_*, no ajustes).
#   Pixelado     el mismo divisor elegido a mano, en enteros x1..x8 (pixelado_calculos.ajustar_a_divisor_entero).
#   Giro         el minimapa gira con la cámara o deja el norte arriba.
#   Detalle      1 calles y lugares, 2 + casas, 3 + alturas.
#
# Las listas de opciones son funciones puras (se prueban sin ventana); lo de Ursina solo ocurre al construir la sección.

from frontend import ajustes_calculos as calc_ajustes
from frontend import pixelado_calculos as calc

NOMBRE_SECCION = "Gráficos"
# Con la fila «Pantalla completa» no cabe la ayuda de abajo (la pestaña ya iba justa de alto): sus teclas pasan a la
# segunda línea de la descripción de la calidad (que ya dice que los menús no se pixelan).
TEXTO_AYUDA_TECLAS = "Solo el mundo se pixela. Mapa grande (N): + / - zoom y R giro."


# Descripción de la calidad, con la ayuda de teclas detrás si la fila de pantalla completa ocupa su sitio.
def texto_descripcion(preset, con_ayuda):
    texto = calc.descripcion_preset(preset) or ""
    if con_ayuda:
        texto = f"{texto} {TEXTO_AYUDA_TECLAS}".strip()
    return texto or " "


# La fila sale solo si el gestor de pantalla completa está activo (frontend/pantalla_completa.py).
def pantalla_completa_en_ajustes():
    from frontend import pantalla_completa
    return pantalla_completa.activo()


def opciones_preset():
    return calc.nombres_presets()


def opciones_rotacion():
    return [("Con la cámara", "camara"), ("Norte arriba", "norte")]


def opciones_densidad():
    return [("Básico", 1), ("Normal", 2), ("Detallado", 3)]


# `s` = escena_ajustes.Seccion (o un doble con los mismos métodos anadir_*).
def construir_seccion(s):
    selector = s.anadir_selector("Calidad", "preset_grafico", opciones_preset())
    con_pantalla = pantalla_completa_en_ajustes()
    descripcion = s.anadir_texto(texto_descripcion(s.gestor.actual.preset_grafico, con_pantalla), alto=0.075)
    deslizador = s.anadir_deslizador("Pixelado del mundo", "pixel_scale", calc.formato_pixel,
                                     paso=calc.paso_deslizador())
    s.anadir_selector("Giro del minimapa", "minimapa_rotacion", opciones_rotacion())
    s.anadir_selector("Detalle del minimapa", "minimapa_densidad", opciones_densidad())
    interruptor = None
    if con_pantalla:
        # Pantalla completa (frontend/pantalla_completa.py, F11 igual) en el sitio de la fila de ayuda.
        interruptor = s.anadir_interruptor("Pantalla completa (F11)", "pantalla_completa")
    else:
        s.anadir_texto("Solo el mundo se pixela; los menús y el HUD siguen nítidos. "
                       "En el mapa grande (N): + / - zoom y R giro.", alto=0.075)

    # El deslizador cambia el preset a «Personalizada» (y un preset mueve el deslizador): se mantienen a la par.
    def sincronizar(ajustes, cambiadas):
        if interruptor is not None and "pantalla_completa" in cambiadas:
            interruptor.fijar_valor(ajustes.pantalla_completa)      # F11 con la pantalla de Ajustes abierta
        if not cambiadas & {"preset_grafico", "pixel_scale"}:
            return
        selector.fijar_indice(calc_ajustes.indice_de_valor(selector.opciones, ajustes.preset_grafico))
        deslizador.fijar_valor(ajustes.pixel_scale)
        s.cambiar_texto(descripcion, texto_descripcion(ajustes.preset_grafico, con_pantalla))

    s.gestor.suscribir(sincronizar, llamar_ya=False)

    return None


# Registra la sección en Ajustes (idempotente: reemplaza si ya existía). Importa la escena aquí para que este módulo
# se pueda importar sin Ursina.
def registrar():
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
