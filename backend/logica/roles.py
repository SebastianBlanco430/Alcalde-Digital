# Roles exclusivos del juego (modelo puro). Cada rol tiene datos inmutables:
# texto visible, color y punto de aparición (spawn) en el mapa.
#
# spawn_x / spawn_y: coordenadas del plano del mundo. OJO: spawn_y es la
# coordenada z del mundo (el mapa trabaja en el plano XZ), no una altura.
# Decisión: el spawn es el centro del lugar de inicio desplazado (0, -1.0) en z,
# para que el avatar no nazca encima del computador del centro de la plaza.
# Los valores están escritos a mano (el módulo no depende del mapa); un test
# verifica que coinciden con construir_mapa_ejemplo().

import types
from dataclasses import dataclass


@dataclass(frozen=True)
class InfoRol:
    nombre: str
    descripcion: str
    color: tuple  # RGB 0-255
    lugar_inicio: str
    spawn_x: float
    spawn_y: float


# Orden en que se muestran y se eligen los roles.
ORDEN_ROLES = ("ciudadano", "periodista", "influencer", "candidato")

# Solo lectura: id -> InfoRol.
ROLES = types.MappingProxyType({
    "ciudadano": InfoRol(
        nombre="Ciudadano",
        descripcion="Vecino común: lo que comparte influye en su barrio.",
        color=(66, 133, 244),
        lugar_inicio="Barrio Las Flores",
        spawn_x=14.0,
        spawn_y=-5.0,
    ),
    "periodista": InfoRol(
        nombre="Periodista",
        descripcion="Verifica los hechos y decide qué se publica.",
        color=(234, 67, 53),
        lugar_inicio="Terminal de Buses",
        spawn_x=6.0,
        spawn_y=-8.0,
    ),
    "influencer": InfoRol(
        nombre="Influencer",
        descripcion="Su alcance es enorme: cada publicación se viraliza.",
        color=(251, 188, 4),
        lugar_inicio="Universidad de Ciudad Nova",
        spawn_x=6.0,
        spawn_y=6.0,
    ),
    "candidato": InfoRol(
        nombre="Candidato a alcalde",
        descripcion="Busca ganar la confianza de Ciudad Nova.",
        color=(52, 168, 83),
        lugar_inicio="Alcaldía",
        spawn_x=-8.0,
        spawn_y=-1.0,
    ),
})
