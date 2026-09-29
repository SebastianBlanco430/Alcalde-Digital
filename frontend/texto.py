# Envoltura de texto por medida (Python puro, sin ursina; testeable).
# El wordwrap nativo de ursina.Text cuenta caracteres, pero con una fuente
# proporcional no miden lo mismo. Aquí se mide el ancho real con
# `medir(cadena) -> ancho`, que aporta quien llama.


# Parte una palabra que no cabe sola en `ancho_max` en trozos que sí caben.
def _partir_palabra(palabra, medir, ancho_max):
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


# Envoltura voraz palabra por palabra: colapsa espacios repetidos y parte por
# caracteres las palabras más anchas que `ancho_max`. Devuelve [] si no hay
# palabras; lanza ValueError si `ancho_max` no es positivo.
def envolver_texto(texto, medir, ancho_max):
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
