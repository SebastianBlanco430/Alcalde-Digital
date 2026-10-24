# Propagación de una publicación en la red social "Civitas" tras una decisión de misión.
# Lógica pura (sin ursina): envuelve GrafoSocial.propagar_publicacion y devuelve un
# dict JSON-serializable que la UI puede animar salto a salto.
# No decide si el alcance modifica indicadores; solo calcula quién recibe la noticia.

# Ciudadano del grafo de ejemplo asociado a cada rol del jugador.
# influencer -> Ana, la más conectada (máximo alcance: toda su red de 11); candidato y periodista
# tienen un ciudadano con conexiones medias en la misma red; ciudadano -> Marcos, vecino de la
# comunidad del Morro: lo que comparte se queda en su comunidad (5), separada de la red de Ana.
CIUDADANO_POR_ROL = {
    "influencer": "Ana",
    "candidato": "Elena",
    "ciudadano": "Marcos",
    "periodista": "Fábio",
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
        niveles = grafo_social.propagar_por_saltos(origen)

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


# -- Resumen de la red social ---------------------------------------------------------------------


# Ciudadanos más influyentes (mayor grado; desempate por cercanía y orden de inserción).
# Retorno: lista de dicts [{"ciudadano": str, "grado": int}, ...] con a lo sumo `n`
# elementos, de mayor a menor influencia. n=None -> todos. ValueError si n < 0.
def resumen_influyentes(grafo_social, n=3):
    return [
        {"ciudadano": ciudadano, "grado": grado}
        for ciudadano, grado in grafo_social.ciudadanos_influyentes(n)
    ]


# Comunidades que una publicación del `rol` jamás alcanzaría.
# Retorno: lista de listas de nombres [[str, ...], ...], una por comunidad aislada
# (componentes conexas sin el ciudadano del rol). [] si todo está conectado.
# ValueError si el rol es desconocido o su ciudadano no está en el grafo.
def resumen_comunidades_aisladas(grafo_social, rol):
    origen = _origen_de_rol(grafo_social, rol)
    return [list(c) for c in grafo_social.comunidades_aisladas(origen)]


# Alcance acumulado por salto al compartir desde el ciudadano del `rol`.
# Retorno: lista de dicts [{"salto": int (desde 1), "nuevos": int, "acumulado": int}, ...];
# lista vacía si el origen no tiene vecinos. `acumulado` no incluye al origen.
# ValueError si el rol es desconocido o su ciudadano no está en el grafo.
def alcance_por_salto(grafo_social, rol):
    propagacion = calcular_propagacion(grafo_social, rol, "compartir")
    resultado = []
    acumulado = 0
    for salto, nivel in enumerate(propagacion["niveles"], start=1):
        acumulado += len(nivel)
        resultado.append({"salto": salto, "nuevos": len(nivel), "acumulado": acumulado})
    return resultado


# Resumen completo de la red, JSON-serializable. Retorno exacto:
# {
#   "rol": str, "origen": str,
#   "total_ciudadanos": int,
#   "influyentes": [{"ciudadano": str, "grado": int}, ...],     # a lo sumo n_influyentes
#   "comunidades_aisladas": [[str, ...], ...],
#   "alcance_por_salto": [{"salto": int, "nuevos": int, "acumulado": int}, ...],
#   "alcance_total": int,                  # = acumulado del último salto (0 si no hay saltos)
#   "fraccion_alcanzada": float,           # alcance_total / total_ciudadanos (0.0 si total 0)
# }
def resumen_red_social(grafo_social, rol, n_influyentes=3):
    origen = _origen_de_rol(grafo_social, rol)
    saltos = alcance_por_salto(grafo_social, rol)
    total = grafo_social.numero_ciudadanos()
    alcance = saltos[-1]["acumulado"] if saltos else 0
    return {
        "rol": rol,
        "origen": origen,
        "total_ciudadanos": total,
        "influyentes": resumen_influyentes(grafo_social, n_influyentes),
        "comunidades_aisladas": resumen_comunidades_aisladas(grafo_social, rol),
        "alcance_por_salto": saltos,
        "alcance_total": alcance,
        "fraccion_alcanzada": alcance / total if total > 0 else 0.0,
    }


def _origen_de_rol(grafo_social, rol):
    if rol not in CIUDADANO_POR_ROL:
        raise ValueError(f"Rol desconocido: {rol!r}")
    origen = CIUDADANO_POR_ROL[rol]
    if origen not in grafo_social.ciudadanos():
        raise ValueError(f"Ciudadano del rol {rol!r} no está en el grafo: {origen!r}")
    return origen
