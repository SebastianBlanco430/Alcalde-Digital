# Piel BOTW de toda la interfaz (docs/ESTILO_BOTW.md): bandera, equivalencias de color y reglas de estado. Python PURO
# (sin ursina), con tests en tests/test_a_ui_botw.py. La paleta vive en frontend/estilo.py (constantes BOTW_*) y las
# piezas que la dibujan en frontend/componentes.py (panel_botw, panel_piel, BotonBotw*, boton_piel).
#
# BANDERA: ALCALDE_UI_BOTW (encendida por defecto). Manda la variable de entorno; si no está, el interruptor de
# Ajustes › Estilo «Estilo de interfaz» (guardado en ajustes.json como «ui_botw»; se aplica al reiniciar, porque muchos
# módulos copian sus colores al importarse); si tampoco, UI_BOTW. =0 deja la interfaz de siempre, idéntica.
# Persona B lee la misma variable del entorno por su cuenta: `publicar_en_entorno()` (lo llama main.py al arrancar) la
# escribe si no estaba, así las dos partes ven lo mismo aunque el jugador la haya elegido en Ajustes.
#
# Uso en una pantalla: `tono(estilo.COLOR_PANEL)` devuelve el color BOTW equivalente con la piel encendida y el mismo
# color sin ella; los colores que no tienen equivalente pasan tal cual (lugares, roles, retratos).

import math
import os

from frontend import estilo

UI_BOTW = True                        # valor por defecto si ni la variable ni los ajustes dicen nada
VARIABLE = "ALCALDE_UI_BOTW"
CLAVE_AJUSTE = "ui_botw"
_APAGADO = ("0", "false", "no", "off")
_ENCENDIDO = ("1", "true", "si", "sí", "on")

# -- Tiempos y medidas de los estados (las mismas del menú de inicio) --
DURACION_HOVER_S = 0.08               # cambio de color o escala al pasar el ratón
DURACION_PRESIONADO_S = 0.06
DURACION_ENTRADA_S = 0.28             # un panel o una opción que aparece (fundido + deslizamiento)
DESLIZAMIENTO_ENTRADA_PX = 18         # desde dónde entra (a la derecha)
DESPLAZAMIENTO_FOCO_PX = 6            # la opción con foco se corre a la izquierda, como en el menú
ESCALA_HOVER = 1.03                   # más contenido que el «cómic» (1,04)
ESCALA_PRESIONADO = 0.97
CONTRASTE_MINIMO = 4.5                # WCAG AA para texto normal

# Equivalencias de la paleta de siempre a la BOTW. Solo colores de interfaz: los de lugares, roles y retratos son
# identidad y no cambian. Si dos nombres comparten valor (COLOR_ACENTO y ACENTO_PRIMARIO), comparten equivalente.
TONOS = {
    estilo.COLOR_FONDO: estilo.BOTW_FONDO,
    estilo.COLOR_PANEL: estilo.BOTW_PANEL,
    estilo.COLOR_TARJETA: estilo.BOTW_TARJETA,
    estilo.COLOR_SUPERFICIE_ALTA: estilo.BOTW_SUPERFICIE_ALTA,
    estilo.COLOR_TEXTO: estilo.BOTW_TEXTO,
    estilo.COLOR_TEXTO_TENUE: estilo.BOTW_TEXTO_TENUE,
    estilo.COLOR_BARRA_FONDO: estilo.BOTW_BOTON_DESHABILITADO,
    estilo.COLOR_BOTON: estilo.BOTW_BOTON,
    estilo.COLOR_BOTON_RESALTADO: estilo.BOTW_BOTON_RESALTADO,
    estilo.COLOR_BOTON_DESHABILITADO: estilo.BOTW_BOTON_DESHABILITADO,
    estilo.COLOR_BOTON_TEXTO: estilo.BOTW_BOTON_TEXTO,
    estilo.TINTA: estilo.BOTW_TINTA,
    estilo.COLOR_ACENTO: estilo.BOTW_ACENTO,
    estilo.ACENTO_SECUNDARIO: estilo.BOTW_INFO,
    estilo.ESTADO_EXITO: estilo.BOTW_EXITO,
    estilo.ESTADO_AVISO: estilo.BOTW_AVISO,
    estilo.ESTADO_ERROR: estilo.BOTW_ERROR,
    estilo.COLOR_BARRA_BAJO: estilo.BOTW_ERROR,
}

# Variantes de botón con la piel (mismas claves que componentes.ESTILOS_BOTON).
ESTILOS_BOTON = {
    "primario": {
        "normal": estilo.BOTW_ACENTO, "hover": estilo.BOTW_ACENTO_SUAVE, "presionado": (232, 192, 40),
        "texto": estilo.BOTW_ACENTO_TEXTO,
    },
    "secundario": {
        "normal": estilo.BOTW_BOTON, "hover": estilo.BOTW_BOTON_RESALTADO, "presionado": estilo.BOTW_BOTON_PRESIONADO,
        "texto": estilo.BOTW_BOTON_TEXTO,
    },
    "peligro": {
        "normal": (172, 50, 60), "hover": (186, 60, 70), "presionado": (148, 40, 50),
        "texto": estilo.BOTW_TEXTO,
    },
}


def activo(entorno=None, extras=None):
    """¿Piel BOTW? Variable de entorno > ajuste guardado («ui_botw») > UI_BOTW. `extras` solo para pruebas."""
    valor = (os.environ if entorno is None else entorno).get(VARIABLE, "").strip().lower()
    if valor in _APAGADO:
        return False
    if valor in _ENCENDIDO:
        return True
    if extras is None:
        try:
            from backend.logica import ajustes
            extras = ajustes.obtener().actual.extras
        except Exception:                    # noqa: BLE001  sin ajustes legibles: el valor por defecto
            extras = {}
    return bool(extras.get(CLAVE_AJUSTE, UI_BOTW))


def publicar_en_entorno(entorno=None):
    """Escribe ALCALDE_UI_BOTW («1» o «0») si no estaba, para que los módulos que solo miran el entorno coincidan con
    el ajuste guardado. Devuelve el valor efectivo."""
    entorno = os.environ if entorno is None else entorno
    efectivo = activo(entorno)
    if not entorno.get(VARIABLE, "").strip():
        entorno[VARIABLE] = "1" if efectivo else "0"
    return efectivo


def tono(rgb, con_piel=None):
    """El equivalente BOTW de un color de estilo (o el mismo color sin piel o sin equivalente)."""
    if con_piel is None:
        con_piel = activo()
    return TONOS.get(tuple(rgb), tuple(rgb)) if con_piel else tuple(rgb)


def estilo_boton(variante, clasicos):
    """Colores de una variante de botón con la piel; si no tiene versión BOTW, la de siempre (`clasicos`)."""
    return ESTILOS_BOTON.get(variante, clasicos.get(variante))


def suavizar(x):
    """0..1 → 0..1 con arranque y llegada suaves (coseno), la curva del menú de inicio."""
    x = min(1.0, max(0.0, x))
    return 0.5 - 0.5 * math.cos(math.pi * x)


def entrada(t, reducir=False):
    """(alfa, desplazamiento_px) de algo que aparece hace `t` segundos: fundido y deslizamiento desde la derecha. Con
    «reducir movimiento», solo el fundido."""
    f = suavizar(t / DURACION_ENTRADA_S) if DURACION_ENTRADA_S > 0 else 1.0
    return f, 0.0 if reducir else DESLIZAMIENTO_ENTRADA_PX * (1.0 - f)


def pares_de_texto():
    """(nombre, texto, fondo) de las combinaciones de la piel que llevan letra: todas deben pasar CONTRASTE_MINIMO."""
    e = estilo
    return [
        ("texto/panel", e.BOTW_TEXTO, e.BOTW_PANEL),
        ("texto/tarjeta", e.BOTW_TEXTO, e.BOTW_TARJETA),
        ("texto/fondo", e.BOTW_TEXTO, e.BOTW_FONDO),
        ("tenue/panel", e.BOTW_TEXTO_TENUE, e.BOTW_PANEL),
        ("tenue/tarjeta", e.BOTW_TEXTO_TENUE, e.BOTW_TARJETA),
        ("detalle/velo", e.BOTW_TEXTO_DETALLE, e.BOTW_VELO),
        ("acento/panel", e.BOTW_ACENTO, e.BOTW_PANEL),
        ("tinta/acento", e.BOTW_ACENTO_TEXTO, e.BOTW_ACENTO),
        ("tinta/acento_suave", e.BOTW_ACENTO_TEXTO, e.BOTW_ACENTO_SUAVE),
        ("boton/normal", e.BOTW_BOTON_TEXTO, e.BOTW_BOTON),
        ("boton/hover", e.BOTW_BOTON_TEXTO, e.BOTW_BOTON_RESALTADO),
        ("exito/panel", e.BOTW_EXITO, e.BOTW_PANEL),
        ("aviso/panel", e.BOTW_AVISO, e.BOTW_PANEL),
        ("error/panel", e.BOTW_ERROR, e.BOTW_PANEL),
        ("info/panel", e.BOTW_INFO, e.BOTW_PANEL),
    ]


# -- Interruptor de Ajustes › Estilo (frontend/hud_ajustes.py) --
# «Estilo de interfaz: BOTW / Clásico». Se guarda en ajustes.json como la clave extra «ui_botw» y se aplica al
# reiniciar: los colores y las piezas se eligen al construir cada pantalla (y main.py lo publica al arrancar).
ETIQUETA_AJUSTE = "Estilo de interfaz"
OPCIONES_AJUSTE = (("BOTW", True), ("Clásico", False))
DESCRIPCION_AJUSTE = ("BOTW: paneles de velo violeta con filo claro, como el menú de inicio. Clásico: los paneles de "
                      "tinta de antes. Se aplica al reiniciar el juego.")


def valor_guardado(extras):
    """Lo que dice el ajuste guardado (o el valor por defecto si no está)."""
    return bool((extras or {}).get(CLAVE_AJUSTE, UI_BOTW))


def indice_ajuste(valor):
    """Posición de `valor` en OPCIONES_AJUSTE (0 = BOTW)."""
    return 0 if valor else 1
