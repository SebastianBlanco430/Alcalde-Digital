# Viaje rápido del mapa grande (modelo PURO, sin ursina ni red): mototáxi y teleférico.
#
#   - Mototáxi: tres PARADAS (Ponto de Mototáxi da Entrada, Praça da Sé y Estação Alto do Morro) con un conductor;
#     desde cada una se ofrecen los demás destinos de la lista FIJA (entrada, se, morro, hospital) con un precio en R$
#     que depende de la distancia. Los viajes NO entran en el grafo de calles (el GPS sigue por calles).
#   - Teleférico: entre la Estação do Teleférico y la Estação Alto do Morro (~430 m), R$ TARIFA_TELEFERICO. Primero se
#     reubica al jugador en la otra estación y luego el cliente reproduce un trayecto animado (frontend/teleferico_vista.py,
#     trazado en backend/datos/teleferico.py).
#
# Esta función la usan IGUAL el cliente (para saber qué ofrecer y cuánto cobrar) y el ANFITRIÓN (para decidir: no se
# confía en el cliente). `resolver_viaje(mundo, destino, x, z)` valida el origen (cerca de una parada o estación) y el
# destino (lista fija) y devuelve dónde aparece el jugador. Solo existe en el mundo grande (`disponible`): con el chico
# nada de esto hace efecto. El cobro es LOCAL del cliente (online no sincroniza dinero): aquí solo se calcula y se aplica
# sobre un PerfilEconomia con las mismas reglas que backend/logica/dinero.py.

import math
from dataclasses import dataclass

from backend.logica.comercios import resolver_ancla

# --- Tarifas (R$ enteros) ---
TARIFA_BASE_MOTO = 3
METROS_POR_REAL = 70.0           # cada 70 m de trayecto suma R$ 1 (Entrada -> Sé ~436 m = R$ 9)
TARIFA_TELEFERICO = 2            # precio bajo y fijo: transporte público del barrio (decisión de diseño)

# --- Geometría de las paradas ---
RADIO_ORIGEN = 9.0               # m: a esta distancia de una parada/estación (el anfitrión usa la posición AUTORIZADA)
MOTIVOS = frozenset({"lejos", "mismo_lugar", "no_existe", "fase", "dentro", "montado", "espera", "desactivado",
                     "desconectado"})

TIPO_MOTO = "mototaxi"
TIPO_TELEFERICO = "teleferico"


@dataclass(frozen=True)
class Parada:
    """Parada de mototáxi: `ancla` = dónde está el conductor (frente a la puerta de `lugar`)."""
    id: str
    lugar: str
    nombre: str
    conductor: str
    ancla: dict


@dataclass(frozen=True)
class Estacion:
    """Estación del teleférico: `ancla` = el punto de embarque (frente a la puerta de `lugar`)."""
    id: str
    lugar: str
    nombre: str
    ancla: dict


@dataclass(frozen=True)
class Destino:
    id: str
    nombre: str
    tipo: str
    llegada: dict                # ancla (comercios.resolver_ancla) donde aparece el jugador


# Paradas (las anclas se comprobaron contra el mundo grande: transitables y a >= 4 m de cualquier comercio).
PARADAS = {
    "entrada": Parada("entrada", "Ponto de Mototáxi da Entrada", "Parada de la Entrada", "Tío Nonato",
                      {"lugar": "Ponto de Mototáxi da Entrada", "fuera": 3.5, "lateral": 6.5}),
    "se": Parada("se", "Praça da Sé", "Parada de la Praça da Sé", "Seu Zequinha",
                 {"lugar": "Praça da Sé", "fuera": 3.5, "lateral": 5.0}),
    "morro": Parada("morro", "Estação Alto do Morro", "Parada del Alto do Morro", "Dona Cleide",
                    {"lugar": "Estação Alto do Morro", "fuera": 3.5, "lateral": 5.0}),
}

ESTACIONES = {
    "tele_base": Estacion("tele_base", "Estação do Teleférico", "Estación del teleférico",
                          {"lugar": "Estação do Teleférico", "fuera": 4.5, "lateral": 0.0}),
    "tele_alta": Estacion("tele_alta", "Estação Alto do Morro", "Estación Alto do Morro",
                          {"lugar": "Estação Alto do Morro", "fuera": 4.5, "lateral": -4.0}),
}

# Destinos: la lista FIJA. Los ids viajan por la red (backend/red/protocolo.DESTINOS_VIAJE: hay una prueba de paridad).
DESTINOS = {
    "entrada": Destino("entrada", "Entrada del barrio", TIPO_MOTO,
                       {"lugar": "Ponto de Mototáxi da Entrada", "fuera": 5.5, "lateral": 4.0}),
    "se": Destino("se", "Praça da Sé", TIPO_MOTO, {"lugar": "Praça da Sé", "fuera": 5.5, "lateral": 2.5}),
    "morro": Destino("morro", "Alto do Morro", TIPO_MOTO, {"lugar": "Estação Alto do Morro", "fuera": 5.5, "lateral": 2.5}),
    "hospital": Destino("hospital", "Hospital Santa Casa", TIPO_MOTO,
                        {"lugar": "Hospital Santa Casa", "fuera": 4.5, "lateral": 0.0}),
    # El teleférico deja al jugador a ~4,5 m del poste de embarque (fuera de su radio de la E: no sale el aviso al llegar).
    "tele_alta": Destino("tele_alta", "Teleférico: Alto do Morro", TIPO_TELEFERICO,
                         {"lugar": "Estação Alto do Morro", "fuera": 6.5, "lateral": 0.0}),
    "tele_base": Destino("tele_base", "Teleférico: estación de abajo", TIPO_TELEFERICO,
                         {"lugar": "Estação do Teleférico", "fuera": 8.0, "lateral": 3.0}),
}
# Cada estación lleva a la OTRA.
DESTINO_DE_ESTACION = {"tele_base": "tele_alta", "tele_alta": "tele_base"}


@dataclass(frozen=True)
class ResultadoViaje:
    ok: bool
    motivo: str = ""
    destino: str = ""
    tipo: str = ""
    x: float = 0.0
    z: float = 0.0
    y: float = 0.0
    precio: int = 0
    origen: str = ""


def disponible(mundo):
    """¿Hay transporte en este mundo? Solo con un MundoGrande (duck typing); el chico no tiene paradas ni estaciones."""
    return hasattr(mundo, "contenido_de_chunk") and hasattr(mundo, "muros_de_chunk")


def _punto(mundo, ancla):
    x, z, rumbo = resolver_ancla(mundo, ancla)
    return float(x), float(z), float(rumbo)


def posicion_de_parada(mundo, parada_id):
    """(x, z, rumbo) del conductor de la parada."""
    return _punto(mundo, PARADAS[parada_id].ancla)


def posicion_de_estacion(mundo, estacion_id):
    """(x, z, rumbo) del punto de embarque de la estación."""
    return _punto(mundo, ESTACIONES[estacion_id].ancla)


def punto_de_llegada(mundo, destino_id):
    """(x, z) donde aparece el jugador al llegar a `destino_id` (KeyError si no existe)."""
    x, z, _ = _punto(mundo, DESTINOS[destino_id].llegada)
    return x, z


def y_de(mundo, x, z):
    suelo = getattr(mundo, "altura_con_escaleras", None) or mundo.altura
    return float(suelo(x, z))


def tarifa_moto(distancia):
    """Precio (R$) de un viaje en mototáxi de `distancia` metros."""
    return TARIFA_BASE_MOTO + int(round(max(0.0, float(distancia)) / METROS_POR_REAL))


def precio_de(mundo, destino_id, origen_id):
    """Precio del viaje a `destino_id` saliendo de la parada/estación `origen_id`."""
    destino = DESTINOS[destino_id]
    if destino.tipo == TIPO_TELEFERICO:
        return TARIFA_TELEFERICO
    ox, oz, _ = posicion_de_parada(mundo, origen_id)
    dx, dz = punto_de_llegada(mundo, destino_id)
    return tarifa_moto(math.hypot(dx - ox, dz - oz))


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def parada_cercana(mundo, x, z, radio=RADIO_ORIGEN):
    """Id de la parada de mototáxi más cercana a (x, z) dentro del radio, o None."""
    if not (_numero(x) and _numero(z)):
        return None
    mejor, mejor_d = None, radio
    for pid in PARADAS:
        px, pz, _ = posicion_de_parada(mundo, pid)
        d = math.hypot(px - x, pz - z)
        if d <= mejor_d:
            mejor, mejor_d = pid, d
    return mejor


def estacion_cercana(mundo, x, z, radio=RADIO_ORIGEN):
    """Id de la estación del teleférico más cercana a (x, z) dentro del radio, o None."""
    if not (_numero(x) and _numero(z)):
        return None
    mejor, mejor_d = None, radio
    for eid in ESTACIONES:
        ex, ez, _ = posicion_de_estacion(mundo, eid)
        d = math.hypot(ex - x, ez - z)
        if d <= mejor_d:
            mejor, mejor_d = eid, d
    return mejor


def ofertas_de_parada(mundo, parada_id):
    """[(destino_id, nombre, precio)] que ofrece la parada: los demás destinos de mototáxi, en orden fijo."""
    return [(d.id, d.nombre, precio_de(mundo, d.id, parada_id))
            for d in DESTINOS.values() if d.tipo == TIPO_MOTO and d.id != parada_id]


def oferta_de_estacion(mundo, estacion_id):
    """(destino_id, nombre, precio) del único trayecto de la estación."""
    destino = DESTINO_DE_ESTACION[estacion_id]
    return destino, DESTINOS[destino].nombre, TARIFA_TELEFERICO


def resolver_viaje(mundo, destino_id, x, z):
    """Decide un viaje a `destino_id` pedido desde la posición (x, z). Misma regla en cliente y anfitrión.

    ok -> dónde aparece (x, z, y), el precio y el origen (parada o estación). Si no: `motivo` de MOTIVOS."""
    if not disponible(mundo):
        return ResultadoViaje(False, "desactivado", destino_id if isinstance(destino_id, str) else "")
    if not isinstance(destino_id, str) or destino_id not in DESTINOS:
        return ResultadoViaje(False, "no_existe")
    destino = DESTINOS[destino_id]
    if destino.tipo == TIPO_TELEFERICO:
        origen = estacion_cercana(mundo, x, z)
        if origen is None or DESTINO_DE_ESTACION[origen] != destino_id:
            return ResultadoViaje(False, "lejos", destino_id, destino.tipo)
    else:
        origen = parada_cercana(mundo, x, z)
        if origen is None:
            return ResultadoViaje(False, "lejos", destino_id, destino.tipo)
        if origen == destino_id:
            return ResultadoViaje(False, "mismo_lugar", destino_id, destino.tipo, origen=origen)
    llx, llz = punto_de_llegada(mundo, destino_id)
    return ResultadoViaje(True, "", destino_id, destino.tipo, llx, llz, y_de(mundo, llx, llz),
                          precio_de(mundo, destino_id, origen), origen)


# --- Cobro (local del cliente; las mismas reglas que dinero.comprar: atómico y con anotación en el libro) ---

def cobrar_viaje(perfil, destino_id, precio):
    """Cobra el viaje de la billetera. Devuelve el Resultado del inventario (ok / sin_dinero / sin_billetera)."""
    resultado = perfil.inventario.cobrar(precio)
    if resultado.ok and precio > 0:
        perfil.registrar(f"Viaje: {DESTINOS[destino_id].nombre}", -int(precio))
    return resultado


def reembolsar_viaje(perfil, destino_id, precio):
    """Devuelve el importe de un viaje que no se hizo (el anfitrión lo rechazó o no contestó)."""
    if precio <= 0:
        return None
    resultado = perfil.inventario.ingresar(int(precio))
    if resultado.ok:
        perfil.registrar(f"Reembolso: {DESTINOS[destino_id].nombre}", int(precio))
    return resultado


def duracion_negro(distancia):
    """Segundos de pantalla negra de un viaje en mototáxi de `distancia` m (8-15 s, más larga con la distancia)."""
    return min(15.0, max(8.0, 8.0 + float(distancia) / 120.0))
