# Grafo de la ciudad del mapa grande: el del ejemplo (11 lugares del núcleo, sin tocarlos) más 13 lugares
# nuevos AL FINAL del orden. Solo agrega nodos y aristas; construir_grafo_ciudad_ejemplo no cambia.

from backend.grafos.grafo_ciudad import construir_grafo_ciudad_ejemplo

LUGARES_NUEVOS = (
    "Posto de Saúde Vila Nova",
    "Ponto de Mototáxi da Entrada",
    "Padaria Pão Quente",
    "Supermercado Dois Irmãos",
    "Oficina do Seu Zé",
    "Bar do Cabo",
    "Igreja Nossa Senhora da Esperança",
    "Escola Municipal Paulo Freire",
    "Salão da Dona Lu",
    "Campo de Várzea",
    "Feira da Ladeira",
    "Mirante do Alto",
    "Estação Alto do Morro",
)

# (nuevo, vecino): cada nuevo se une a lugares del núcleo o a nuevos anteriores.
CONEXIONES_NUEVAS = (
    ("Posto de Saúde Vila Nova", "Parque do Povo"),
    ("Ponto de Mototáxi da Entrada", "Hospital Santa Casa"),
    ("Ponto de Mototáxi da Entrada", "Posto de Saúde Vila Nova"),
    ("Padaria Pão Quente", "Posto de Saúde Vila Nova"),
    ("Padaria Pão Quente", "Escola de Samba"),
    ("Supermercado Dois Irmãos", "Rádio Comunitária"),
    ("Supermercado Dois Irmãos", "Ponto de Mototáxi da Entrada"),
    ("Oficina do Seu Zé", "Mercado Municipal"),
    ("Bar do Cabo", "Rádio Comunitária"),
    ("Bar do Cabo", "Oficina do Seu Zé"),
    ("Igreja Nossa Senhora da Esperança", "Prefeitura"),
    ("Escola Municipal Paulo Freire", "Estação do Teleférico"),
    ("Escola Municipal Paulo Freire", "Igreja Nossa Senhora da Esperança"),
    ("Salão da Dona Lu", "Igreja Nossa Senhora da Esperança"),
    ("Campo de Várzea", "Igreja Nossa Senhora da Esperança"),
    ("Campo de Várzea", "Salão da Dona Lu"),
    ("Feira da Ladeira", "Escola Municipal Paulo Freire"),
    ("Feira da Ladeira", "Campo de Várzea"),
    ("Mirante do Alto", "Feira da Ladeira"),
    ("Estação Alto do Morro", "Campo de Várzea"),
    ("Estação Alto do Morro", "Mirante do Alto"),
)


def construir_grafo_ciudad_grande():
    grafo = construir_grafo_ciudad_ejemplo()
    for lugar in LUGARES_NUEVOS:
        grafo.agregar_lugar(lugar)
    for a, b in CONEXIONES_NUEVAS:
        grafo.agregar_conexion(a, b)
    return grafo
