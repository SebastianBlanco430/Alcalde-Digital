"""
Envoltura de texto por MEDIDA (Python puro, sin ursina; testeable).

El `wordwrap` nativo de `ursina.Text` cuenta CARACTERES, pero con una fuente
proporcional (OpenSans) los caracteres no miden lo mismo ("iii" es mucho más
estrecho que "WWW"), así que un límite en caracteres deja líneas demasiado
cortas o que se salen del recuadro. Aquí se envuelve midiendo el ancho real
con una función `medir(cadena) -> ancho` que aporta quien llama (en la
interfaz, la medida de Panda3D con la misma fuente con que se dibuja).
"""


def _partir_palabra(palabra, medir, ancho_max):
    """Parte una palabra que no cabe sola en `ancho_max` en trozos que sí caben."""
    trozos = []
    actual = ""
    for letra in palabra:
        if actual and medir(actual + letra) > ancho_max:
            trozos.append(actual)
            actual = letra
        else:
            actual += letra
    if actual:
        trozos.append(actual)
    return trozos


def envolver_texto(texto, medir, ancho_max):
    """Parte `texto` en líneas cuyo ancho medido no supera `ancho_max`.

    Envoltura voraz palabra por palabra (misma idea que `_envolver_texto` de la
    versión pygame). Las palabras se separan por espacios; los espacios
    repetidos se colapsan. Una palabra más ancha que `ancho_max` se parte por
    caracteres, para no desbordar nunca. Devuelve [] si el texto no tiene
    palabras. Lanza ValueError si `ancho_max` no es positivo.
    """
    if ancho_max <= 0:
        raise ValueError(f"ancho_max debe ser positivo, no {ancho_max!r}.")

    lineas = []
    linea_actual = ""

    for palabra in texto.split():
        for trozo in (
            [palabra] if medir(palabra) <= ancho_max else _partir_palabra(palabra, medir, ancho_max)
        ):
            candidata = f"{linea_actual} {trozo}" if linea_actual else trozo
            if medir(candidata) <= ancho_max:
                linea_actual = candidata
            else:
                lineas.append(linea_actual)
                linea_actual = trozo

    if linea_actual:
        lineas.append(linea_actual)
    return lineas
