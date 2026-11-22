# Catálogo semilla de comercios (datos puros). `ancla` = dónde están (zona "mercado" del mercadito y lugares existentes).
# Las tiendas venden objetos de items_semilla (precio del catálogo); `trabajo_id` enlaza con trabajos_semilla.

import os
from dataclasses import replace

from backend.logica.comercios import Comercio
from backend.logica.feria import puestos_fijos_activo

CATALOGO_COMERCIOS = (
    Comercio("supermercado", "Supermercado do Bairro", "tienda",
             {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": -4.0},
             ("agua", "pan", "cafe", "bala", "recarga", "bolsa_feria", "bolsita"),
             trabajo_id="supermercado", npc="Dona Lúcia"),
    Comercio("panaderia", "Padaria Estrela", "tienda",
             {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": 4.0},
             ("pan", "cafe", "bala"),
             trabajo_id="panaderia", npc="Seu Heitor"),
    Comercio("lanchonete", "Lanchonete do Parque", "tienda",
             {"lugar": "Parque do Povo", "fuera": 3.0, "lateral": 0.0},
             ("agua", "cafe", "pan", "bala"),
             trabajo_id="lanchonete", npc="Dona Marta"),
    Comercio("bar", "Bar da Esquina", "tienda",
             {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": 4.0},
             ("agua", "cafe", "bala"),
             trabajo_id="bar", npc="Seu Nilton"),
    Comercio("taller", "Oficina do Beto", "puesto_trabajo",
             {"lugar": "Rodoviária", "fuera": 3.0, "lateral": -4.0},
             (), trabajo_id="taller", npc="Beto"),
    Comercio("lan_house", "Lan House da Praça", "tienda",
             {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": -4.0},
             ("audifonos", "pendrive", "recarga"),
             trabajo_id="lan_house", npc="Kauê"),
    Comercio("entregas", "Mototáxi e Entregas", "puesto_trabajo",
             {"lugar": "Rodoviária", "fuera": 3.0, "lateral": 4.0},
             (), trabajo_id="entregas", npc="Zeca"),
    Comercio("feirante", "Banca da Feira", "tienda",
             {"zona": "mercado", "dx": -5.0, "dz": 2.0},
             ("pan", "bolsa_feria", "agua"),
             trabajo_id="feirante", npc="Dona Neide"),
    Comercio("tienda_general", "Tienda Geral", "tienda",
             {"zona": "mercado", "dx": -1.0, "dz": 3.0},
             ("mochila", "agua", "linterna", "destornillador", "libreta", "caja_herramientas", "pelota",
              "botijon_gas"),
             npc="Seu Osvaldo"),
    Comercio("seu_ze", "Seu Zé", "vendedor_calle",
             {"zona": "mercado", "dx": 7.0, "dz": 0.0},
             ("bicarbonato",), npc="Seu Zé"),
)

# Puestos fijos (ALCALDE_PUESTOS_FIJOS, backend/logica/feria.py; =0 las anclas de arriba, que el frontend corrige con
# elegir_puesto). Posición y rumbo revisados a mano (2026-11-22) con las semillas 2026, 7 y 11; el frontend NO los
# corre ni los gira ("fijo") y tests/test_puestos_fijos.py comprueba que no pisan nada.
#   - Parejas junto a una puerta: simétricas respecto a la puerta (mismo `fuera`, ±`lateral`, de espaldas al edificio).
#     Mercado y Praça da Sé: 2,7 m a cada lado (pasillo de 2,8 m hasta la puerta; a ≥ 4 m del punto de misión).
#     Las puertas del Mercado y la Rodoviária están a 1,6 m de la esquina oeste de la fachada: el puesto del oeste
#     sobresale de la fachada (no cabe de otro modo con el pasillo de 2,5 m).
#   - Rodoviária (2026-11-22, ajustes para la Feria): Oficina do Beto y Zeca juntos (0,3 m entre huellas), de espaldas a
#     la pared LATERAL OESTE del edificio (la cara que se ve a la derecha de la fachada desde la plaza; caja x 19,6..28,4,
#     z -52..-40), a 0,4 m de ella y mirando al oeste (rumbo -90), con un pasillo libre de >= 2 m delante del mostrador.
#     No van centrados en esa cara (z -46): en las semillas 7 y 11 una casa del barrio ocupa z <= -48 delante del tramo
#     sur, así que la pareja se corre 1,25 m hacia la esquina de la fachada (centro z -44,75); más al norte, Beto queda a
#     < 4 m del punto de misión de la puerta. La calle diagonal no llega a esa pared (pasa al norte de z -40).
#     Coordenadas: puerta (21,216; -40), tangente (1, 0) y normal (0, 1) del lado «n» => lateral = x - 21,216,
#     fuera = z + 40.
#   - Lanchonete: al lado norte de la fachada del Parque do Povo, fuera del letrero (centrado en la fachada) y lejos de
#     la puerta (el sur tiene árboles).
#   - Feria: la Banca da Feira y la Tienda Geral al fondo de la losa alargada, mirando a la entrada.
ANCLAS_FIJAS = {
    "supermercado": {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": -2.7, "rumbo": 0.0, "fijo": True},
    "panaderia": {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": 2.7, "rumbo": 0.0, "fijo": True},
    "lanchonete": {"lugar": "Parque do Povo", "fuera": 2.5, "lateral": 8.5, "rumbo": -90.0, "fijo": True},
    "bar": {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": 2.7, "rumbo": -180.0, "fijo": True},
    "lan_house": {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": -2.7, "rumbo": -180.0, "fijo": True},
    "taller": {"lugar": "Rodoviária", "fuera": -3.3, "lateral": -2.97, "rumbo": -90.0, "fijo": True},
    "entregas": {"lugar": "Rodoviária", "fuera": -6.2, "lateral": -2.97, "rumbo": -90.0, "fijo": True},
    "feirante": {"zona": "mercado", "fondo": 0, "dx": -5.0, "dz": 2.0, "fijo": True},
    "tienda_general": {"zona": "mercado", "fondo": 1, "dx": -1.0, "dz": 3.0, "fijo": True},
}
# Parejas simétricas respecto a la puerta de su lugar (los tests lo comprueban).
PAREJAS_FIJAS = (("supermercado", "panaderia"), ("bar", "lan_house"))
# Pareja contra una pared lateral de su edificio (lado de la caja: «o» = x mínima), lado a lado.
PAREJAS_PARED = ((("taller", "entregas"), "o"),)


# Catálogo con las anclas fijas (los comercios sin ancla fija, como Seu Zé, quedan igual).
def con_puestos_fijos(comercios, anclas=None):
    anclas = ANCLAS_FIJAS if anclas is None else anclas
    return tuple(replace(c, ancla=dict(anclas[c.id])) if c.id in anclas else c for c in comercios)


# Tiendas ampliadas: más objetos de cada comercio, con el contexto brasileño (ids de items_semilla.py). Se añaden
# DETRÁS del stock de siempre. Solo economía local: ni el stock ni los precios entran en la huella de sala.
# TIENDA_AMPLIADA = False (o ALCALDE_TIENDA_AMPLIADA=0) deja el stock de antes.
TIENDA_AMPLIADA = True
STOCK_AMPLIADO = {
    "panaderia": ("pao_frances", "pao_de_queijo", "sonho", "pao_doce", "broa", "bolo_de_fuba", "pao_de_forma",
                  "cafe_com_leite"),
    "lanchonete": ("coxinha", "pastel", "misto_quente", "suco_laranja", "guarana", "acai"),
    "bar": ("guarana", "caldo_de_cana", "agua_de_coco", "pastel"),
    "feirante": ("banana", "laranja", "mandioca", "pastel", "caldo_de_cana"),
    "supermercado": ("arroz", "feijao", "farofa", "leite", "bolacha"),
    "lan_house": ("cabo_usb", "carregador", "capinha"),
    "tienda_general": ("pilhas", "lampada", "fita_isolante", "guarda_chuva", "chinelo"),
}


def tienda_ampliada_activa():
    valor = os.environ.get("ALCALDE_TIENDA_AMPLIADA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(TIENDA_AMPLIADA)


# Catálogo con el stock ampliado (sin repetir ids que ya vendía).
def ampliar_stock(comercios, extra=None):
    extra = STOCK_AMPLIADO if extra is None else extra
    return tuple(replace(c, stock=tuple(c.stock) + tuple(i for i in extra.get(c.id, ()) if i not in c.stock))
                 for c in comercios)


CATALOGO_COMERCIOS_BASE = CATALOGO_COMERCIOS
if tienda_ampliada_activa():
    CATALOGO_COMERCIOS = ampliar_stock(CATALOGO_COMERCIOS)
if puestos_fijos_activo():
    CATALOGO_COMERCIOS = con_puestos_fijos(CATALOGO_COMERCIOS)
