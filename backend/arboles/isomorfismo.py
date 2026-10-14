# Validación del isomorfismo entre ArbolNoticias y ArbolStats.
# estado_partida.py depende de que el camino de una noticia lleve al nodo de stats
# de la MISMA noticia; aquí se comprueba (útil al arrancar o en pruebas).


# True si ambos árboles tienen exactamente la misma forma.
def son_isomorfos(arbol_noticias, arbol_stats):
    return arbol_noticias.forma() == arbol_stats.forma()


# Devuelve la lista de problemas encontrados (vacía = todo coherente):
# forma distinta, ids que no coinciden nodo a nodo, o ABB mal ordenado.
def validar_isomorfismo(arbol_noticias, arbol_stats):
    problemas = []

    if not arbol_noticias.es_abb_valido():
        problemas.append("ArbolNoticias no es un ABB válido (ids repetidos o desordenados)")
    if not arbol_stats.es_abb_valido():
        problemas.append("ArbolStats no es un ABB válido (gravedades repetidas o desordenadas)")

    if not son_isomorfos(arbol_noticias, arbol_stats):
        problemas.append("los árboles no tienen la misma forma")
        return problemas

    # Misma forma: se comparan nodo a nodo siguiendo el camino de cada noticia.
    for nodo in arbol_noticias.recorrido_inorden():
        _, camino = arbol_noticias.buscar_con_camino(nodo.id)
        nodo_stats = arbol_stats.obtener_por_camino(camino)
        if nodo_stats is None or nodo_stats.id != nodo.id:
            encontrado = None if nodo_stats is None else nodo_stats.id
            problemas.append(f"el camino de la noticia {nodo.id} lleva a {encontrado}")

    return problemas
