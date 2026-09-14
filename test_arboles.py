from backend.arboles.arbol_noticias import ArbolNoticias
from backend.arboles.arbol_stats import ArbolStats

arbol_noticias = ArbolNoticias()
arbol_stats = ArbolStats()

datos_noticias = [
    (50, "Candidato propone cerrar colegios", False, "Periodista"),
    (25, "Alcalde inaugura nuevo parque", True, "Ciudadano"),
    (75, "Rumor sobre aumento de impuestos", False, "Influencer"),
    (10, "Campaña de reciclaje en la ciudad", True, "Ciudadano"),
    (40, "Corte de agua programado mañana", True, "Periodista"),
]

datos_stats = [
    (50, [-5, 10, -2], [10, -15, 5]),
    (25, [2, 5, 1], [-1, -2, -1]),
    (75, [-10, 20, -5], [15, -20, 10]),
    (10, [5, 5, 5], [0, 0, 0]),
    (40, [1, 2, 0], [-2, -5, 1]),
]

for noti in datos_noticias:
    arbol_noticias.agregar(*noti)

for stat in datos_stats:
    arbol_stats.agregar(*stat)

print("\n\n")
arbol_noticias.imprimir()

id_buscar = 25
nodo_hallado = arbol_noticias.buscar(arbol_noticias.raiz, id_buscar)
print(f"\nBusqueda de ID {id_buscar}:")
if nodo_hallado:
    print(f"Encontrado: {nodo_hallado.noticia}\n\n")
else:
    print("No encontrado\n\n")

id_eliminar = 25
arbol_noticias.eliminar(id_eliminar)
arbol_stats.eliminar(id_eliminar)

arbol_noticias.imprimir()

print("\n", arbol_noticias.isomorfo(arbol_noticias.raiz, arbol_stats.raiz))
