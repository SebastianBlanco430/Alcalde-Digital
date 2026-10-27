# Ciudad Nova GRANDE (datos puros, sin ursina): 24 lugares (los 11 del núcleo, que NO se mueven, más 13 nuevos al final)
# en ~900 x 650 m, con un barrio de 4000-5200 casas, becos y escaleras. ciudad_3d.py no cambia: esto lo reutiliza.
#
#   COORDENADAS_GRANDES        {lugar: (x, z)} en metros (núcleo = COORDENADAS_EJEMPLO * ESCALA_MUNDO, sin tocarlo).
#   construir_mundo_grande(s)  -> MundoGrande (backend/logica/mundo_grande.py).
#   _lado_libre(mapa, lugar..) -> lado de la puerta que deja el lote del edificio en el lado de la plaza sin calles.
#   ANCLAS_COMERCIOS_GRANDE    {id de comercio: ancla} para resolver los comercios de comercios_semilla en este mundo.
#   resolver_comercios_grande(mundo) -> [(comercio, (x, z, rumbo))].
#
# Lugares sin edificio: Campo de Várzea (Zona "cancha"), Feira da Ladeira (Zona "mercado", toldos) y Mirante do Alto
# (solo plaza; punto_interaccion = su centro). El pipeline es el de construir_mundo_3d con las versiones indexadas
# (barrio_indexado.py) y el TerrenoGrande (terreno_grande.py).

import math

from backend.datos import ciudad_3d
from backend.datos.barrio_indexado import (
    CANTIDAD_BARRIO_GRANDE,
    ESCALERAS_CALLEJON_GRANDE,
    _DespejeIndexado,
    generar_barrio_indexado,
    zonas_por_anclaje,
)
from backend.datos.becos import generar_becos
from backend.datos.conectividad_grande import quitar_bolsas_grande
from backend.datos.ciudad_3d import (
    ANCHO_CALLE,
    ESCALA_MUNDO,
    MARGEN_EDIFICIOS,
    RADIO_PLAZA,
    SEMILLA_CASAS,
    _arboles_parque,
    _bancos,
    _construir_edificios,
    _encajar_modelo,
    _escaleras,
    _farolas,
    _spawns,
)
from backend.datos.terreno_grande import TerrenoGrande
from backend.grafos.grafo_ciudad_grande import construir_grafo_ciudad_grande
from backend.grafos.mapa_ciudad import COORDENADAS_EJEMPLO, MapaCiudad, _distancia_punto_segmento
from backend.logica.mundo_ciudad import Edificio, MundoCiudad, _distancia_punto_caja, _distancia_segmento_caja
from backend.logica.mundo_grande import MundoGrande

VEGETACION_GRANDE = 700            # palmeras, bananeros y matas repartidos por el barrio grande
RADIO_ZONA_ANCLADA = 55.0          # m: la cancha y la feria se buscan a esta distancia de su lugar (si no cabe, en todo el mapa)
HOLGURA_LOTE = 3.0                 # m entre el aro de la plaza y su edificio (como en el núcleo)
SEPARACION_LOTES = 3.0             # m mínimos entre dos lotes
LADOS = ("s", "n", "e", "o")       # orden de preferencia en un empate

COORDENADAS_GRANDES = {lugar: (x * ESCALA_MUNDO, z * ESCALA_MUNDO) for lugar, (x, z) in COORDENADAS_EJEMPLO.items()}
COORDENADAS_GRANDES.update({
    "Posto de Saúde Vila Nova": (140, 130),
    "Ponto de Mototáxi da Entrada": (410, -120),
    "Padaria Pão Quente": (210, 250),
    "Supermercado Dois Irmãos": (250, -120),
    "Oficina do Seu Zé": (-210, -190),
    "Bar do Cabo": (270, -300),
    "Igreja Nossa Senhora da Esperança": (-200, 20),
    "Escola Municipal Paulo Freire": (-230, 200),
    "Salão da Dona Lu": (-360, -70),
    "Campo de Várzea": (-350, 100),
    "Feira da Ladeira": (-400, 230),
    "Mirante do Alto": (-440, 310),
    "Estação Alto do Morro": (-455, 150),
})

# (lugar, ancho del lote, fondo del lote, alto, letrero, modelo). Los lotes se ubican con _lado_libre.
_EDIFICIOS_NUEVOS = (
    ("Posto de Saúde Vila Nova", 10, 8, 7, "Posto de Saúde Vila Nova", "casa4"),
    ("Ponto de Mototáxi da Entrada", 10, 9, 5, "Ponto de Mototáxi", "casa3"),
    ("Padaria Pão Quente", 10, 9, 6, "Padaria Pão Quente", "casa1"),
    ("Supermercado Dois Irmãos", 14, 12, 7, "Supermercado Dois Irmãos", "casa2"),
    ("Oficina do Seu Zé", 14, 12, 6, "Oficina do Seu Zé", "casa3"),
    ("Bar do Cabo", 10, 9, 6, "Bar do Cabo", "casa1"),
    ("Igreja Nossa Senhora da Esperança", 14, 12, 9, "Igreja Nossa Senhora da Esperança", "casa4"),
    ("Escola Municipal Paulo Freire", 16, 12, 8, "Escola Municipal Paulo Freire", "casa2"),
    ("Salão da Dona Lu", 10, 9, 6, "Salão da Dona Lu", "casa3"),
    ("Estação Alto do Morro", 14, 10, 8, "Estação Alto do Morro", "casa4"),
)

# Anclas de los comercios de comercios_semilla en el mapa grande (los ids son los del catálogo). Las tiendas de la
# feria usan la Zona "mercado" (que en este mundo queda junto a la Feira da Ladeira) con desfases de ±3 m: caben
# en el rectángulo sea cual sea su orientación (16 x 9 o 9 x 16).
ANCLAS_COMERCIOS_GRANDE = {
    "supermercado": {"lugar": "Supermercado Dois Irmãos", "fuera": 3.0, "lateral": -3.0},
    "panaderia": {"lugar": "Padaria Pão Quente", "fuera": 3.0, "lateral": 0.0},
    "lanchonete": {"lugar": "Bar do Cabo", "fuera": 3.0, "lateral": 3.0},
    "bar": {"lugar": "Bar do Cabo", "fuera": 3.0, "lateral": -3.0},
    "taller": {"lugar": "Oficina do Seu Zé", "fuera": 3.0, "lateral": 0.0},
    "lan_house": {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": -4.0},
    "entregas": {"lugar": "Ponto de Mototáxi da Entrada", "fuera": 3.0, "lateral": 0.0},
    "feirante": {"zona": "mercado", "dx": -3.0, "dz": 3.0},
    "tienda_general": {"zona": "mercado", "dx": 3.0, "dz": 3.0},
    "seu_ze": {"zona": "mercado", "dx": 0.0, "dz": -3.0},
}


def _construir_mapa_grande():
    mapa = MapaCiudad(construir_grafo_ciudad_grande(), COORDENADAS_GRANDES, ancho_calle=ANCHO_CALLE, radio_plaza=RADIO_PLAZA)
    problemas = mapa.validar()
    if problemas:
        raise ValueError(f"El mapa grande no es válido: {problemas}")
    return mapa


# Normal hacia afuera de la cara con la puerta (la puerta mira a la plaza; el lote queda del lado opuesto).
_NORMAL = {"n": (0, 1), "s": (0, -1), "e": (1, 0), "o": (-1, 0)}


def _centro_lote(mapa, lugar, lado, ancho, fondo):
    cx, cz = mapa.coordenada(lugar)
    nx, nz = _NORMAL[lado]
    prof = fondo if lado in ("n", "s") else ancho
    d = mapa.radio_plaza + HOLGURA_LOTE + prof / 2
    return round(cx - nx * d, 3), round(cz - nz * d, 3)


def _caja_lote(mapa, lugar, lado, ancho, fondo):
    cx, cz = _centro_lote(mapa, lugar, lado, ancho, fondo)
    return (cx - ancho / 2, cx + ancho / 2, cz - fondo / 2, cz + fondo / 2)


def _lado_libre(mapa, lugar, ancho=12.0, fondo=10.0, ocupadas=()):
    """El `lado_puerta` ('n', 's', 'e', 'o') cuyo lote de ancho x fondo (en x, z) cabe en el lado de la plaza de `lugar`
    sin calles: no toca ninguna calle (con acera), ni otra plaza, ni las cajas `ocupadas`. Entre los que caben gana el que
    más se aleja de las calles (empate: el orden de LADOS). ValueError si ninguno cabe."""
    calles = [(mapa.coordenada(a), mapa.coordenada(b)) for a, b in mapa.segmentos()]
    plazas = [mapa.coordenada(l) for l in mapa.lugares() if l != lugar]
    mejor = None
    for lado in LADOS:
        caja = _caja_lote(mapa, lugar, lado, ancho, fondo)
        holgura = min(_distancia_segmento_caja(a, b, caja) for a, b in calles) - mapa.ancho_calle / 2
        if holgura < 0.5:
            continue
        if any(_distancia_punto_caja(px, pz, caja) < mapa.radio_plaza + 3.0 for px, pz in plazas):
            continue
        if any(caja[0] < o[1] + SEPARACION_LOTES and o[0] < caja[1] + SEPARACION_LOTES
               and caja[2] < o[3] + SEPARACION_LOTES and o[2] < caja[3] + SEPARACION_LOTES for o in ocupadas):
            continue
        if mejor is None or holgura > mejor[0] + 1e-9:
            mejor = (holgura, lado)
    if mejor is None:
        raise ValueError(f"No hay un lado libre en la plaza de {lugar!r} para un lote de {ancho} x {fondo}.")
    return mejor[1]


def _construir_edificios_grandes(mapa):
    edificios = _construir_edificios()                      # los 11 del núcleo, sin cambios
    ocupadas = [e.caja() for e in edificios]
    for lugar, ancho, fondo, alto, nombre, modelo in _EDIFICIOS_NUEVOS:
        lado = _lado_libre(mapa, lugar, ancho, fondo, ocupadas)
        cx, cz = _centro_lote(mapa, lugar, lado, ancho, fondo)
        lote = Edificio(lugar, cx, cz, ancho, fondo, alto, lado, nombre)
        edificios.append(_encajar_modelo(lote, modelo))
        ocupadas.append(lote.caja())
    return edificios


def _anclajes_zonas(mapa):
    return {"cancha": mapa.coordenada("Campo de Várzea"), "mercado": mapa.coordenada("Feira da Ladeira")}


def construir_mundo_grande(semilla=SEMILLA_CASAS, casas=None):
    """El mundo grande completo (determinista para una `semilla`). `casas` = tope de casas (None = CANTIDAD_BARRIO_GRANDE)."""
    mapa = _construir_mapa_grande()
    edificios = _construir_edificios_grandes(mapa)
    spawns = _spawns()
    despeje = _DespejeIndexado(mapa, edificios, spawns)
    obstaculos = _bancos(mapa, despeje) + _arboles_parque(mapa, despeje) + _farolas(mapa, despeje)
    plano = MundoCiudad(mapa, edificios, obstaculos, spawns=spawns, margen_edificios=MARGEN_EDIFICIOS)
    limites = plano.limites()
    previo = TerrenoGrande.para_mapa_grande(mapa, edificios, limites)
    zonas = zonas_por_anclaje(mapa, edificios, previo.altura_natural, limites, anclajes=_anclajes_zonas(mapa),
                                 radio=RADIO_ZONA_ANCLADA)
    terreno = TerrenoGrande.para_mapa_grande(mapa, edificios, limites, chunks_en_cache=256,
                                             zonas_planas=[(z.cx, z.cz, z.ancho, z.fondo) for z in zonas])
    edificios = [_con_altura(e, terreno) for e in edificios]
    escaleras = _escaleras(mapa, edificios, obstaculos, terreno)
    for e in escaleras:
        despeje.agregar_linea((e.ax, e.az), (e.bx, e.bz))
    becos = generar_becos(mapa, terreno, despeje, semilla)
    escaleras = escaleras + [e for b in becos for e in b.escaleras]
    barrio = generar_barrio_indexado(mapa, edificios, despeje, obstaculos, terreno, zonas, escaleras, limites, semilla,
                                     cantidad=CANTIDAD_BARRIO_GRANDE if casas is None else casas,
                                     maximo_escaleras=ESCALERAS_CALLEJON_GRANDE, vegetacion=VEGETACION_GRANDE)
    def armar(obstaculos):
        return MundoGrande(mapa, edificios, obstaculos, semilla=semilla, becos=becos,
                           lineas_libres=despeje.lineas(), spawns=spawns, margen_edificios=MARGEN_EDIFICIOS,
                           terreno=terreno, escaleras=barrio.escaleras, muros=(), callejones=barrio.callejones,
                           zonas=barrio.zonas)

    mundo = armar(barrio.obstaculos)
    # F4: el barrio de generar_barrio_indexado ya quita bolsas sin mirar el talud; aquí se quitan las que quedan por
    # pendiente (casas, y plantas si hace falta) para que no haya celdas libres aisladas (conectividad_grande.py).
    obstaculos, quitados = quitar_bolsas_grande(mundo)
    return armar(obstaculos) if quitados else mundo


def _con_altura(e, terreno):
    from dataclasses import replace
    return replace(e, y=round(terreno.altura_plaza(e.lugar), 3))


def resolver_comercios_grande(mundo, comercios=None):
    """[(comercio, (x, z, rumbo))] de los comercios de comercios_semilla ubicados con ANCLAS_COMERCIOS_GRANDE."""
    from dataclasses import replace
    from backend.logica.comercios import resolver_ancla
    if comercios is None:
        from backend.datos.comercios_semilla import CATALOGO_COMERCIOS as comercios
    return [(c, resolver_ancla(mundo, ANCLAS_COMERCIOS_GRANDE[c.id])) for c in comercios]
