# Límite central de texto de DATOS (rumores, mensajes, opciones) antes de pintarlos. Puede venir de partidas en línea:
# se recorta (con «…») y se neutralizan «<» y «>», que Ursina interpreta como etiquetas de formato. Función pura, sin Ursina.

MAX_PREDETERMINADO = 400
MAX_RUMOR = 280
MAX_OPCION = 160


def limitar_texto(texto, maximo=MAX_PREDETERMINADO, neutralizar=True):
    """`texto` como cadena de a lo sumo `maximo` caracteres (el último es «…» si se recortó) y sin «<» ni «>»."""
    cadena = "" if texto is None else str(texto)
    if neutralizar:
        cadena = cadena.replace("<", "(").replace(">", ")")
    if maximo is not None and maximo > 0 and len(cadena) > maximo:
        cadena = cadena[:maximo - 1].rstrip() + "…"
    return cadena
