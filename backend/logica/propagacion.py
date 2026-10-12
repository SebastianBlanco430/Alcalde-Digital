# Propagación de una publicación en la red social "Civitas" tras una decisión de misión.
# Lógica pura (sin ursina): envuelve GrafoSocial.propagar_publicacion y devuelve un
# dict JSON-serializable que la UI puede animar salto a salto.
# No decide si el alcance modifica indicadores; solo calcula quién recibe la noticia.

# Ciudadano del grafo de ejemplo asociado a cada rol del jugador.
# influencer -> Ana, la más conectada (máximo alcance); los demás tienen un
# ciudadano con conexiones medias.
CIUDADANO_POR_ROL = {
    "influencer": "Ana",
    "candidato": "Elena",
    "ciudadano": "Beto",
    "periodista": "Fabio",
}

ACCIONES = ("compartir", "reportar")


# niveles[k] = ciudadanos alcanzados exactamente en el salto k+1 (sin el origen).
# "compartir" propaga a toda la componente conexa; "reportar" frena la publicación.
# Lanza ValueError si la acción o el rol son desconocidos, o si el ciudadano del rol
# no está en el grafo.
def calcular_propagacion(grafo_social, rol, accion):
    if accion not in ACCIONES:
        raise ValueError(f"Acción desconocida: {accion!r}")
    if rol not in CIUDADANO_POR_ROL:
        raise ValueError(f"Rol desconocido: {rol!r}")

    origen = CIUDADANO_POR_ROL[rol]
    if origen not in grafo_social.ciudadanos():
        raise ValueError(f"Ciudadano del rol {rol!r} no está en el grafo: {origen!r}")

    niveles = []
    if accion == "compartir":
        # Se restan los alcanzados con k-1 saltos a los alcanzados con k saltos.
        previos = 0
        saltos = 1
        while True:
            acumulado = grafo_social.propagar_publicacion(origen, saltos)
            if len(acumulado) == previos:
                break
            niveles.append(acumulado[previos:])
            previos = len(acumulado)
            saltos += 1

    return {
        "origen": origen,
        "accion": accion,
        "niveles": niveles,
        "alcance": sum(len(nivel) for nivel in niveles),
    }


# Proporción 0-1 de ciudadanos alcanzados; 0.0 si el total es 0.
def fraccion_alcanzada(propagacion, total_ciudadanos):
    if total_ciudadanos <= 0:
        return 0.0
    return propagacion["alcance"] / total_ciudadanos
