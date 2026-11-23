# Comercios (modelo puro): dónde están y qué venden. La posición se da como ANCLA (datos), resuelta contra
# el mundo, así el mapa extenso puede recolocarlos cambiando solo el catálogo semilla:
#   {"zona": "mercado", "dx": m, "dz": m}              -> centro de la primera Zona de ese tipo + desfase
#   {"lugar": "Rodoviária", "fuera": m, "lateral": m}  -> frente a la puerta del edificio: `fuera` m hacia la
#                                                         calle y `lateral` m a lo largo de la fachada
#   {"zona": "mercado", "fondo": i, ...}             -> el puesto i (0 o 1) del fondo de la feria (backend/logica/feria.py);
#                                                         si la feria no tiene fondo, el dx/dz del ancla
# Ambas aceptan "rumbo" (grados) opcional. `mundo` solo necesita zonas() y edificio_de(lugar) (un falso en tests).
# "fijo": True (ALCALDE_PUESTOS_FIJOS, backend/datos/comercios_semilla.py) = posición revisada a mano: el frontend no la
# corre ni la gira (frontend/comercios_calculos.colocar_puesto); los tests garantizan que es válida.
# El dx/dz de una zona se mide desde el centro de su parte decorativa (feria.region_decorativa): con la feria alargada
# por el fondo, Seu Zé sigue en la entrada; con la losa de siempre es el centro de la zona, como antes.
# Lo gráfico (toldos, NPC, panel de compra) vive en frontend/; aquí no hay ursina.

import math
from dataclasses import dataclass

from backend.logica import feria
from backend.logica.mundo_ciudad import _NORMAL_FUERA, _TANGENTE

TIPOS = ("tienda", "vendedor_calle", "puesto_trabajo")
RADIO_COMERCIO = 2.0


# stock = ids de objetos a la venta (al precio del catálogo de objetos). trabajo_id = puesto de trabajo del
# lugar (backend/datos/trabajos_semilla.py). npc = nombre del vendedor. `ancla` es dónde está.
@dataclass(frozen=True)
class Comercio:
    id: str
    nombre: str
    tipo: str
    ancla: dict
    stock: tuple = ()
    trabajo_id: str | None = None
    npc: str | None = None

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
        if "fondo" in ancla:
            fondo = feria.puestos_del_fondo(zona)
            indice = ancla["fondo"]
            if fondo and isinstance(indice, int) and not isinstance(indice, bool) and 0 <= indice < len(fondo):
                return tuple(float(v) for v in fondo[indice])
        rumbo = ancla["rumbo"] if "rumbo" in ancla else getattr(zona, "rumbo", 0.0)
        centro_a, _largo = feria.region_decorativa(zona) if hasattr(zona, "reserva") else (0.0, 0.0)
        largo_x = zona.ancho >= zona.fondo
        cx, cz = (zona.cx + centro_a, zona.cz) if largo_x else (zona.cx, zona.cz + centro_a)
        return (cx + _numero(ancla, "dx"), cz + _numero(ancla, "dz"), float(_numero({"r": rumbo}, "r")))
    edificio = mundo.edificio_de(ancla["lugar"])
    lado = edificio.lado_puerta
    px, pz = edificio.puerta()
    nx, nz = _NORMAL_FUERA[lado]
    tx, tz = _TANGENTE[lado]
    fuera, lateral = _numero(ancla, "fuera"), _numero(ancla, "lateral")
    # Por defecto mira hacia la calle (de espaldas al edificio).
    rumbo = ancla["rumbo"] if "rumbo" in ancla else _normalizar_rumbo(edificio.rumbo_puerta() + 180.0)
    return (px + nx * fuera + tx * lateral, pz + nz * fuera + tz * lateral, float(_numero({"r": rumbo}, "r")))


# -- Espacio reservado de los puestos fijos (antes de colocar las casas del barrio) --
# Huella de un puesto (m: a lo largo del mostrador, detrás y delante del dependiente): la misma que
# frontend/comercios_calculos (ANCHO_PUESTO, ATRAS_PUESTO, ADELANTE_PUESTO; un test comprueba que coinciden). Delante se
# reserva el pasillo libre del mostrador. Así una casa decorativa nunca cae donde va un puesto fijo anclado a un edificio
# (la misma idea que la losa de la feria, que reserva su sitio antes que las casas): es la casa la que se aparta.
# Además, alrededor de la huella sola, DISTANCIA_PUERTA_CASA m (la regla de frontend/comercios_calculos.DISTANCIA_PUERTA):
# la puerta de una casa está en el borde de su caja, así ninguna queda a menos de 2 m del puesto.
HUELLA_PUESTO = (2.6, 0.95, 1.4)
PASILLO_RESERVADO = 2.0
MARGEN_RESERVA = 0.3
DISTANCIA_PUERTA_CASA = 2.0


class _SoloEdificios:
    """Lo mínimo de un mundo para resolver un ancla de lugar (durante la construcción todavía no hay MundoCiudad)."""

    def __init__(self, edificios):
        self._por_lugar = {e.lugar: e for e in edificios}

    def edificio_de(self, lugar):
        if lugar not in self._por_lugar:
            raise ValueError(f"No hay edificio para {lugar!r}.")
        return self._por_lugar[lugar]

    def zonas(self):
        return []


def caja_reservada(x, z, rumbo, huella=HUELLA_PUESTO, pasillo=PASILLO_RESERVADO, margen=MARGEN_RESERVA):
    """(xmin, xmax, zmin, zmax) que contiene la huella del puesto en (x, z, rumbo) y el pasillo delante, con margen."""
    ancho, atras, adelante = huella
    s, c = math.sin(math.radians(rumbo)), math.cos(math.radians(rumbo))
    xs, zs = [], []
    for da in (-ancho / 2 - margen, ancho / 2 + margen):
        for df in (-atras - margen, adelante + pasillo + margen):
            xs.append(x + c * da + s * df)
            zs.append(z - s * da + c * df)
    return (min(xs), max(xs), min(zs), max(zs))


def cajas_reservadas_puestos(edificios, comercios):
    """Cajas reservadas de los puestos fijos anclados a un edificio, dos por puesto: huella + pasillo delante, y huella +
    DISTANCIA_PUERTA_CASA alrededor (sin ALCALDE_PUESTOS_FIJOS, ninguna: el barrio de siempre). `comercios` = catálogo
    con anclas fijas (comercios_semilla.con_puestos_fijos)."""
    if not feria.puestos_fijos_activo():
        return []
    mundo = _SoloEdificios(edificios)
    cajas = []
    for comercio in comercios:
        ancla = comercio.ancla
        if comercio.tipo == "vendedor_calle" or not ancla.get("fijo") or "lugar" not in ancla:
            continue
        try:
            x, z, rumbo = resolver_ancla(mundo, ancla)
        except ValueError:
            continue
        cajas.append(tuple(round(v, 3) for v in caja_reservada(x, z, rumbo)))
        cajas.append(tuple(round(v, 3) for v in caja_reservada(x, z, rumbo, pasillo=0.0, margen=DISTANCIA_PUERTA_CASA)))
    return cajas


# Ancla del comercio EN ESTE mundo: la `ancla` del catálogo.
def ancla_de(mundo, comercio):
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
