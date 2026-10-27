# Catálogo semilla de comercios (datos puros). `ancla` = dónde están hoy (zona "mercado" del mercadito y
# lugares existentes); `lugar_ancla` = el lugar REAL del mapa grande donde quedan (backend/datos/ciudad_grande.py:
# ANCLAS_COMERCIOS_GRANDE da el ancla exacta de cada uno; `ancla` sigue siendo la del mundo chico).
# Las tiendas venden objetos de items_semilla (precio del catálogo); `trabajo_id` enlaza con trabajos_semilla.

from backend.logica.comercios import Comercio

CATALOGO_COMERCIOS = (
    Comercio("supermercado", "Supermercado do Bairro", "tienda",
             {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": -4.0},
             ("agua", "pan", "cafe", "bala", "recarga", "bolsa_feria", "bolsita"),
             trabajo_id="supermercado", npc="Dona Lúcia", lugar_ancla="Supermercado Dois Irmãos"),
    Comercio("panaderia", "Padaria Estrela", "tienda",
             {"lugar": "Mercado Municipal", "fuera": 3.0, "lateral": 4.0},
             ("pan", "cafe", "bala"),
             trabajo_id="panaderia", npc="Seu Heitor", lugar_ancla="Padaria Pão Quente"),
    Comercio("lanchonete", "Lanchonete do Parque", "tienda",
             {"lugar": "Parque do Povo", "fuera": 3.0, "lateral": 0.0},
             ("agua", "cafe", "pan", "bala"),
             trabajo_id="lanchonete", npc="Dona Marta", lugar_ancla="Bar do Cabo"),
    Comercio("bar", "Bar da Esquina", "tienda",
             {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": 4.0},
             ("agua", "cafe", "bala"),
             trabajo_id="bar", npc="Seu Nilton", lugar_ancla="Bar do Cabo"),
    Comercio("taller", "Oficina do Beto", "puesto_trabajo",
             {"lugar": "Rodoviária", "fuera": 3.0, "lateral": -4.0},
             (), trabajo_id="taller", npc="Beto", lugar_ancla="Oficina do Seu Zé"),
    Comercio("lan_house", "Lan House da Praça", "tienda",
             {"lugar": "Praça da Sé", "fuera": 3.0, "lateral": -4.0},
             ("audifonos", "pendrive", "recarga"),
             trabajo_id="lan_house", npc="Kauê", lugar_ancla="Lan House da Praça"),
    Comercio("entregas", "Mototáxi e Entregas", "puesto_trabajo",
             {"lugar": "Rodoviária", "fuera": 3.0, "lateral": 4.0},
             (), trabajo_id="entregas", npc="Zeca", lugar_ancla="Ponto de Mototáxi da Entrada"),
    Comercio("feirante", "Banca da Feira", "tienda",
             {"zona": "mercado", "dx": -5.0, "dz": 2.0},
             ("pan", "bolsa_feria", "agua"),
             trabajo_id="feirante", npc="Dona Neide", lugar_ancla="Feira da Ladeira"),
    Comercio("tienda_general", "Tienda Geral", "tienda",
             {"zona": "mercado", "dx": -1.0, "dz": 3.0},
             ("mochila", "agua", "linterna", "destornillador", "libreta", "caja_herramientas", "pelota",
              "botijon_gas"),
             npc="Seu Osvaldo", lugar_ancla="Feira da Ladeira"),
    Comercio("seu_ze", "Seu Zé", "vendedor_calle",
             {"zona": "mercado", "dx": 7.0, "dz": 0.0},
             ("bicarbonato",), npc="Seu Zé", lugar_ancla="Feira da Ladeira"),
)
