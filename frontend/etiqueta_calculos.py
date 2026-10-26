# Tamaño aparente de las etiquetas de nombre sobre los personajes (puro, con tests). La etiqueta es un Text 3D de
# tamaño fijo en el mundo (billboard): a 3 m de la cámara ocupaba el doble de pantalla que a 6 m y «Seu Zé» salía
# enorme. Se acota: de DISTANCIA_REFERENCIA hacia fuera se deja como siempre (se achica con la distancia); hacia
# dentro la escala baja con la distancia para que en pantalla nunca pase de lo que mide a esa referencia.

DISTANCIA_REFERENCIA = 6.0     # m de la cámara a partir de los cuales la etiqueta mide su escala base
FACTOR_MINIMO = 0.25           # nunca por debajo de este tramo de la escala base (pegado a la cámara sigue legible)


def factor_etiqueta(distancia, referencia=DISTANCIA_REFERENCIA, minimo=FACTOR_MINIMO):
    if not isinstance(distancia, (int, float)) or distancia != distancia:
        return 1.0
    return min(1.0, max(minimo, distancia / referencia))


# Escala a la que dejar la etiqueta de `base` cuando la cámara está a `distancia` m.
def escala_limitada(base, distancia, referencia=DISTANCIA_REFERENCIA, minimo=FACTOR_MINIMO):
    return base * factor_etiqueta(distancia, referencia, minimo)
