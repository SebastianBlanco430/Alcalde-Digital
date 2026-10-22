# Saneado de lo que se escribe o pega en los campos de texto del lobby online (Python puro, sin ursina).
# Motivo: el `Text` de Ursina interpreta «<etiquetas>» (y el TextField «☾color☽»), y el alias viaja a
# otros jugadores. Todo texto escrito, pegado o leído del portapapeles pasa por aquí ANTES de mostrarse
# o enviarse. Reutiliza las reglas del anfitrión (backend.red.saneado) para que lo que el campo acepta
# sea lo que el anfitrión acepta.
#
# Dos tiempos distintos:
#   - `sanear_entrada(tipo, texto)`: mientras se escribe (indulgente: conserva un espacio final para
#     poder seguir tecleando «Ana B»).
#   - `valor_final(tipo, texto)`: lo que se usa al enviar (recortado y normalizado; "" si no vale).
#
# NO PROBADO con un editor de métodos de entrada (IME) real: el chino/japonés/coreano envían la
# composición como eventos de teclado que Ursina entrega carácter a carácter; aquí solo se garantiza
# que el resultado final es NFC, sin controles y con el límite respetado.

import unicodedata

from backend.red import saneado
from backend.red.huellas import ALFABETO_CODIGO

TIPO_ALIAS = "alias"
TIPO_HOST = "host"            # IP o nombre de equipo, con puerto opcional («192.168.1.5:7777»)
TIPO_CODIGO = "codigo"        # código de sala (alfabeto sin ambiguos)
TIPO_PUERTO = "puerto"
TIPO_CONFIRMAR = "confirmar"  # palabra de confirmación (ABRIR)
TIPO_LIBRE = "libre"          # texto corto sin etiquetas (no se usa en red)

# Largo máximo al teclear (el alias es el del protocolo; el código admite grupos con separadores)
LIMITES = {
    TIPO_ALIAS: saneado.LARGO_MAX_NOMBRE,
    TIPO_HOST: 64,
    TIPO_CODIGO: 24,
    TIPO_PUERTO: 5,
    TIPO_CONFIRMAR: 8,
    TIPO_LIBRE: 40,
}
_CARACTERES_HOST = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_[]")
_PROHIBIDOS_SIEMPRE = frozenset("<>☾☽")    # etiquetas de Ursina (Text) y de su TextField
MAX_PEGADO = 200                            # lo que se mira de un pegado (el resto se ignora)


def limite_de(tipo):
    return LIMITES.get(tipo, LIMITES[TIPO_LIBRE])


# Quita controles, saltos de línea, marcas bidi/invisibles y las etiquetas de Ursina. Normaliza a NFC.
def _limpiar_comun(texto):
    if type(texto) is not str:
        return ""
    salida = []
    for c in unicodedata.normalize("NFC", texto):
        if c in _PROHIBIDOS_SIEMPRE:
            continue
        if ord(c) in saneado._BIDI_Y_INVISIBLES:
            continue
        if unicodedata.category(c) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            continue
        salida.append(c)
    return "".join(salida)


# Texto de un campo MIENTRAS se escribe. Nunca lanza; devuelve siempre un valor aceptable.
def sanear_entrada(tipo, texto, limite=None):
    limite = limite_de(tipo) if limite is None else int(limite)
    limpio = _limpiar_comun(texto)
    if tipo == TIPO_ALIAS:
        filtrado = "".join(c for c in limpio if saneado._caracter_permitido(c))
        filtrado = filtrado.lstrip(" ")
        while "  " in filtrado:                       # un solo espacio entre palabras
            filtrado = filtrado.replace("  ", " ")
        resultado = filtrado
    elif tipo == TIPO_HOST:
        resultado = "".join(c for c in limpio if c in _CARACTERES_HOST)
    elif tipo == TIPO_CODIGO:
        resultado = "".join(c for c in limpio.upper() if c in ALFABETO_CODIGO or c in " -")
        resultado = resultado.lstrip(" -")
    elif tipo == TIPO_PUERTO:
        resultado = "".join(c for c in limpio if c in "0123456789")
    elif tipo == TIPO_CONFIRMAR:
        resultado = "".join(c for c in limpio.upper() if c.isalpha())
    else:
        resultado = " ".join(p for p in limpio.split(" ") if p) + (" " if limpio.endswith(" ") else "")
    return resultado[:limite]


# Lo que se usa al enviar: texto final (o "" si no es utilizable).
def valor_final(tipo, texto):
    entrada = sanear_entrada(tipo, texto)
    if tipo == TIPO_ALIAS:
        return saneado.limpiar_nombre(entrada)
    if tipo == TIPO_CODIGO:
        return "".join(c for c in entrada if c not in " -")
    return entrada.strip()


# Un pegado puede traer varias líneas, tabulaciones, espacios de más o un texto enorme: se toma la
# primera línea no vacía, se recorta ANTES de sanear (no se procesa un portapapeles de megabytes).
def sanear_pegado(tipo, texto, limite=None):
    if type(texto) is not str:
        return ""
    recorte = texto[:MAX_PEGADO * 4]
    linea = next((l for l in recorte.replace("\r", "\n").split("\n") if l.strip()), "")
    linea = linea.replace("\t", " ").strip()[:MAX_PEGADO]
    return sanear_entrada(tipo, linea, limite)


# Inserta `fragmento` (ya tecleado o pegado) en `actual` en la posición `cursor`; devuelve
# (texto_nuevo, cursor_nuevo) respetando el saneado y el límite. Lo que no cabe se descarta.
def insertar(tipo, actual, cursor, fragmento, limite=None, pegado=False):
    limite = limite_de(tipo) if limite is None else int(limite)
    actual = sanear_entrada(tipo, actual, limite)
    cursor = max(0, min(len(actual), int(cursor)))
    trozo = sanear_pegado(tipo, fragmento, limite) if pegado else sanear_entrada(tipo, fragmento, limite)
    if tipo == TIPO_ALIAS and trozo.startswith(" ") and (cursor == 0 or actual[cursor - 1:cursor] == " "):
        trozo = trozo.lstrip(" ")
    sitio = limite - len(actual)
    if sitio <= 0 or not trozo:
        return actual, cursor
    trozo = trozo[:sitio]
    nuevo = sanear_entrada(tipo, actual[:cursor] + trozo + actual[cursor:], limite)
    # el cursor queda tras lo insertado (acotado si el saneado acortó algo)
    return nuevo, min(len(nuevo), cursor + len(trozo))


# Pistas legibles para el usuario (qué admite cada campo).
AYUDA = {
    TIPO_ALIAS: "1 a 16 letras, números, espacio, - _ .",
    TIPO_HOST: "Dirección IP o nombre, con puerto opcional (192.168.1.5:7777)",
    TIPO_CODIGO: "Código de sala (letras y números sin O, I, L, 0, 1...)",
    TIPO_PUERTO: "1024 a 65535",
}
