# Comercios (modelo puro): dónde están y qué venden. La posición se da como ANCLA (datos), resuelta contra
# el mundo, así el mapa extenso puede recolocarlos cambiando solo el catálogo semilla:
#   {"zona": "mercado", "dx": m, "dz": m}              -> centro de la primera Zona de ese tipo + desfase
#   {"lugar": "Rodoviária", "fuera": m, "lateral": m}  -> frente a la puerta del edificio: `fuera` m hacia la
#                                                         calle y `lateral` m a lo largo de la fachada
# Ambas aceptan "rumbo" (grados) opcional. `mundo` solo necesita zonas() y edificio_de(lugar) (un falso en tests).
# Lo gráfico (toldos, NPC, panel de compra) vive en frontend/; aquí no hay ursina.

import math
from dataclasses import dataclass

from backend.logica.mundo_ciudad import _NORMAL_FUERA, _TANGENTE

TIPOS = ("tienda", "vendedor_calle", "puesto_trabajo")
RADIO_COMERCIO = 2.0


# stock = ids de objetos a la venta (al precio del catálogo de objetos). trabajo_id = puesto de trabajo del
# lugar (backend/datos/trabajos_semilla.py). npc = nombre del vendedor. lugar_ancla = nombre SIMBÓLICO del
# sitio donde debe ir (el mapa extenso lo ubica); `ancla` es dónde está hoy.
@dataclass(frozen=True)
class Comercio:
    id: str
    nombre: str
    tipo: str
    ancla: dict
    stock: tuple = ()
    trabajo_id: str | None = None
    npc: str | None = None
    lugar_ancla: str = ""

    def __post_init__(self):
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo de comercio inválido: {self.tipo!r}")
        if not isinstance(self.ancla, dict) or ("zona" in self.ancla) == ("lugar" in self.ancla):
            raise ValueError(f"El ancla de {self.id!r} necesita 'zona' o 'lugar' (solo uno).")


def _numero(ancla, clave):
    valor = ancla.get(clave, 0.0)
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"Ancla inválida: {clave!r} debe ser un número finito.")
    return float(valor)


def _normalizar_rumbo(grados):
    return ((grados + 180.0) % 360.0) - 180.0


# (x, z, rumbo) del ancla. ValueError si es inválida, la zona no existe o el lugar no tiene edificio.
# Determinista: mismo mundo y ancla, mismo resultado.
def resolver_ancla(mundo, ancla):
    if not isinstance(ancla, dict) or ("zona" in ancla) == ("lugar" in ancla):
        raise ValueError("El ancla necesita 'zona' o 'lugar' (solo uno).")
    if "zona" in ancla:
        zona = next((z for z in mundo.zonas() if z.tipo == ancla["zona"]), None)
        if zona is None:
            raise ValueError(f"No hay una zona {ancla['zona']!r} en el mundo.")
        rumbo = ancla["rumbo"] if "rumbo" in ancla else getattr(zona, "rumbo", 0.0)
        return (zona.cx + _numero(ancla, "dx"), zona.cz + _numero(ancla, "dz"), float(_numero({"r": rumbo}, "r")))
    edificio = mundo.edificio_de(ancla["lugar"])
    lado = edificio.lado_puerta
    px, pz = edificio.puerta()
    nx, nz = _NORMAL_FUERA[lado]
    tx, tz = _TANGENTE[lado]
    fuera, lateral = _numero(ancla, "fuera"), _numero(ancla, "lateral")
    # Por defecto mira hacia la calle (de espaldas al edificio).
    rumbo = ancla["rumbo"] if "rumbo" in ancla else _normalizar_rumbo(edificio.rumbo_puerta() + 180.0)
    return (px + nx * fuera + tx * lateral, pz + nz * fuera + tz * lateral, float(_numero({"r": rumbo}, "r")))


# Ancla del comercio EN ESTE mundo: si el mundo expone `anclas_comercios` ({id: ancla}; el mapa grande) y trae el id,
# esa; si no, la `ancla` del catálogo (el mundo chico de siempre, sin cambios).
def ancla_de(mundo, comercio):
    anclas = getattr(mundo, "anclas_comercios", None)
    if isinstance(anclas, dict) and comercio.id in anclas:
        return anclas[comercio.id]
    return comercio.ancla


# [(comercio, (x, z, rumbo))] para todos los comercios.
def resolver_comercios(mundo, comercios=None):
    if comercios is None:
        from backend.datos.comercios_semilla import CATALOGO_COMERCIOS
        comercios = CATALOGO_COMERCIOS
    return [(c, resolver_ancla(mundo, ancla_de(mundo, c))) for c in comercios]


# El comercio resuelto más cercano a (x, z) dentro del radio, o None.
def comercio_cercano(resueltos, x, z, radio=RADIO_COMERCIO):
    mejor, mejor_d = None, None
    for comercio, (cx, cz, _rumbo) in resueltos:
        d = math.hypot(x - cx, z - cz)
        if d <= radio and (mejor_d is None or d < mejor_d):
            mejor, mejor_d = comercio, d
    return mejor


# [(DefItem, precio)] de lo que se puede comprar en el comercio, en el orden del stock.
def stock_de(comercio, catalogo=None):
    if catalogo is None:
        from backend.datos.items_semilla import CATALOGO_ITEMS
        catalogo = CATALOGO_ITEMS
    return [(catalogo[i], catalogo[i].precio) for i in comercio.stock
            if i in catalogo and catalogo[i].precio is not None]


# ValueError si el catálogo es incoherente: ids repetidos, stock fuera del catálogo o sin precio, trabajo inexistente.
def validar_catalogo(comercios, catalogo_items, trabajos=None):
    ids = set()
    for c in comercios:
        if c.id in ids:
            raise ValueError(f"Comercio repetido: {c.id!r}")
        ids.add(c.id)
        for item in c.stock:
            if item not in catalogo_items or catalogo_items[item].precio is None:
                raise ValueError(f"{c.id}: {item!r} no está en el catálogo o no tiene precio.")
        if trabajos is not None and c.trabajo_id is not None and c.trabajo_id not in trabajos:
            raise ValueError(f"{c.id}: trabajo desconocido {c.trabajo_id!r}")
