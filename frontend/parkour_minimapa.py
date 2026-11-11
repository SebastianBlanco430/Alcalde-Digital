# Puente parkour -> minimapa (modelo puro respecto a Ursina: solo usa frontend/minimapa_calculos.py). Mientras se juega
# un nivel publica en el registro global del minimapa un marcador «altura» por plataforma (fuente «parkour») y la altura
# del jugador, para que los rótulos digan «+3 m» / «-2 m» / «Nivel». Al salir del nivel LIMPIA ambas cosas: las
# coordenadas del parkour son locales y no deben quedar pintadas sobre el mapa de la ciudad.

from frontend import minimapa_calculos as mm

FUENTE = "parkour"


def _etiqueta(plataforma):
    return str(plataforma["id"])


# Marcadores «altura» de los datos de backend.logica.parkour_calculos.alturas_para_minimapa.
def marcadores_de(alturas):
    return [mm.MarcadorMinimapa("altura", p["x"], p["z"], altura=p["y"], etiqueta=_etiqueta(p), id=f"plataforma-{p['id']}")
            for p in alturas.get("plataformas", [])]


# Plano de alturas para el widget del HUD del parkour: el nivel entero visto desde arriba, encajado en un cuadrado de
# lado 1 centrado en (0, 0) sin deformarlo (misma escala en x y en z; +z del nivel queda hacia arriba). Devuelve
# {"plataformas": [{id, x, y, ancho, alto, nivel, texto, meta, inicio, checkpoint}], "jugador": (x, y) o None}.
# `nivel` es «arriba» / «abajo» / «igual» respecto a la altura `y_jugador`; `texto` es «+3 m» / «-2 m» / «Nivel».
#
# Con `radio_m` (y la posición del jugador) el plano ya no muestra el nivel entero sino una ventana de ±radio_m metros
# CENTRADA EN EL JUGADOR: las plataformas se ven grandes en niveles largos. Cada rectángulo se recorta al cuadrado y
# lleva "visible" (False si queda fuera del todo).
def plano_de_alturas(alturas, x_jugador=None, z_jugador=None, y_jugador=None, margen=0.06, radio_m=None):
    plataformas = alturas.get("plataformas", [])
    if not plataformas:
        return {"plataformas": [], "jugador": None}
    if radio_m is not None and x_jugador is not None and z_jugador is not None:
        escala = 0.5 / radio_m
        cx, cz = x_jugador, z_jugador
    else:
        x0 = min(p["x"] - p["ancho"] / 2 for p in plataformas)
        x1 = max(p["x"] + p["ancho"] / 2 for p in plataformas)
        z0 = min(p["z"] - p["fondo"] / 2 for p in plataformas)
        z1 = max(p["z"] + p["fondo"] / 2 for p in plataformas)
        escala = (1.0 - 2 * margen) / max(x1 - x0, z1 - z0, 1e-6)
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    salida = []
    for p in plataformas:
        izq = max(-0.5, (p["x"] - p["ancho"] / 2 - cx) * escala)
        der = min(0.5, (p["x"] + p["ancho"] / 2 - cx) * escala)
        abajo = max(-0.5, (p["z"] - p["fondo"] / 2 - cz) * escala)
        arriba = min(0.5, (p["z"] + p["fondo"] / 2 - cz) * escala)
        visible = der > izq and arriba > abajo
        salida.append({
            "id": p["id"], "x": (izq + der) / 2, "y": (abajo + arriba) / 2,
            "ancho": max(0.0, der - izq), "alto": max(0.0, arriba - abajo), "visible": visible,
            "nivel": mm.nivel_relativo(p["y"], y_jugador), "texto": mm.texto_altura(p["y"], y_jugador),
            "meta": bool(p.get("meta")), "inicio": bool(p.get("inicio")), "checkpoint": bool(p.get("checkpoint")),
        })
    jugador = None
    if x_jugador is not None and z_jugador is not None:
        jugador = (max(-0.5, min(0.5, (x_jugador - cx) * escala)), max(-0.5, min(0.5, (z_jugador - cz) * escala)))
    return {"plataformas": salida, "jugador": jugador}


def publicar(alturas, registro=None):
    registro = registro if registro is not None else mm.registro()
    registro.reemplazar_fuente(FUENTE, marcadores_de(alturas))


# Cada frame de juego: no sube la versión del registro (solo cambia el texto de los rótulos).
def actualizar_altura(y, registro=None):
    (registro if registro is not None else mm.registro()).fijar_altura_jugador(y)


def limpiar(registro=None):
    registro = registro if registro is not None else mm.registro()
    registro.limpiar_fuente(FUENTE)
    registro.fijar_altura_jugador(None)
