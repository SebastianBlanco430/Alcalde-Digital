# Geometría pura del casco de tinta (sin ursina ni panda3d): qué caras de un modelo son EXTERIORES.
# Una cara es exterior si un rayo que sale de su centro en la dirección de su normal (orden antihorario = hacia fuera)
# no choca con ninguna otra cara del modelo. Las interiores (losas bajo un antepecho, paredes de un cuarto, caras
# internas de un patio) siempre tienen otra cara delante. Ver frontend/casas_decorativas.quitar_caras_interiores.


def _resta(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cruz(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _punto(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# Como caras_exteriores_orientadas, pero averigua el sentido de las normales: según el cargador, el mismo .glb llega con
# el orden de los vértices invertido (el de Ursina lo invierte respecto a panda3d-gltf). En el sentido bueno casi todas
# las caras de una casa cerrada son exteriores; en el malo, casi ninguna. Se queda con el que más deja.
def caras_exteriores(triangulos, eps=1e-3):
    directo = caras_exteriores_orientadas(triangulos, eps)
    if sum(directo) * 2 >= len(directo):
        return directo
    invertido = caras_exteriores_orientadas([(a, c, b) for a, b, c in triangulos], eps)
    return invertido if sum(invertido) > sum(directo) else directo


# [bool] por triángulo: True = exterior. `triangulos`: lista de (a, b, c), cada vértice (x, y, z). Los triángulos
# degenerados cuentan como exteriores (no estorban). Möller-Trumbore contra todos (O(n²); ~500 caras = ~0,2 s).
# Sentido de la normal: el del orden (a, b, c) antihorario.
def caras_exteriores_orientadas(triangulos, eps=1e-3):
    datos = []
    for a, b, c in triangulos:
        e1, e2 = _resta(b, a), _resta(c, a)
        normal = _cruz(e1, e2)
        datos.append((a, e1, e2, normal, _punto(normal, normal) ** 0.5))
    resultado = []
    for i, (a, e1, e2, normal, largo) in enumerate(datos):
        if largo < 1e-12:
            resultado.append(True)
            continue
        d = (normal[0] / largo, normal[1] / largo, normal[2] / largo)
        centro = tuple(a[k] + (e1[k] + e2[k]) / 3 for k in range(3))
        origen = tuple(centro[k] + d[k] * eps for k in range(3))
        libre = True
        for j, (a2, f1, f2, _n, largo2) in enumerate(datos):
            if j == i or largo2 < 1e-12:
                continue
            p = _cruz(d, f2)
            det = _punto(f1, p)
            if -1e-12 < det < 1e-12:
                continue
            inv = 1.0 / det
            s = _resta(origen, a2)
            u = _punto(s, p) * inv
            if u < 0.0 or u > 1.0:
                continue
            q = _cruz(s, f1)
            v = _punto(d, q) * inv
            if v < 0.0 or u + v > 1.0:
                continue
            if _punto(f2, q) * inv > eps:
                libre = False
                break
        resultado.append(libre)
    return resultado
