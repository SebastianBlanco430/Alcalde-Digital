# Catálogo semilla de comercios (datos puros). `ancla` = dónde están (zona "mercado" del mercadito y lugares existentes).
# Las tiendas venden objetos de items_semilla (precio del catálogo); `trabajo_id` enlaza con trabajos_semilla.

import os
from dataclasses import replace

from backend.logica.comercios import Comercio

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
