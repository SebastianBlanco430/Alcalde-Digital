# Registro cronológico de impactos (modelo puro, sin motor gráfico): un árbol AVL
# ordenado por (timestamp, secuencia). Es INDEPENDIENTE de ArbolNoticias/ArbolStats:
# no toca su raíz ni su forma(), así que el isomorfismo por réplica de camino no cambia.
#
# Por qué AVL: los timestamps llegan casi siempre en orden creciente y un ABB simple
# degeneraría en una lista (altura O(n)). Con las rotaciones del AVL la altura queda
# acotada por ~1.44·log2(n) y insertar/buscar por rango es O(log n).
#
# El recorrido inorden devuelve los impactos en orden cronológico; es lo que lee el
# Archivo de casos. El timestamp lo pone quien llama (no hay reloj global), así los
# tests son deterministas. Dos impactos con el mismo timestamp se desempatan por una
# secuencia creciente, de modo que el orden de llegada se conserva.

import math


# Un impacto registrado: cuándo, de qué tipo, qué deltas produjo y quién lo originó.
# `deltas` y `datos` son dicts libres (p. ej. deltas de confianza por grupo).
class NodoImpacto:

    def __init__(self, timestamp, secuencia, tipo, deltas=None, origen=None, datos=None):
        self.timestamp = timestamp
        self.secuencia = secuencia
        self.tipo = tipo
        self.deltas = dict(deltas) if deltas else {}
        self.origen = origen
        self.datos = dict(datos) if datos else {}
        self.izquierda = None
        self.derecha = None
        self._altura = 1

    def clave(self):
        return (self.timestamp, self.secuencia)

    def a_dict(self):
        return {
            "timestamp": self.timestamp,
            "secuencia": self.secuencia,
            "tipo": self.tipo,
            "deltas": dict(self.deltas),
            "origen": self.origen,
            "datos": dict(self.datos),
        }

    def __repr__(self):
        return f"NodoImpacto(t={self.timestamp}, #{self.secuencia}, {self.tipo!r})"


def _altura(nodo):
    return nodo._altura if nodo is not None else 0


def _actualizar(nodo):
    nodo._altura = 1 + max(_altura(nodo.izquierda), _altura(nodo.derecha))


# balance > 0: más pesado a la izquierda; < 0: a la derecha
def _balance(nodo):
    return _altura(nodo.izquierda) - _altura(nodo.derecha)


def _rotar_derecha(y):
    x = y.izquierda
    y.izquierda = x.derecha
    x.derecha = y
    _actualizar(y)
    _actualizar(x)
    return x


def _rotar_izquierda(x):
    y = x.derecha
    x.derecha = y.izquierda
    y.izquierda = x
    _actualizar(x)
    _actualizar(y)
    return y


# Restablece el balance AVL en `nodo` (|balance| <= 1) y devuelve la nueva raíz del subárbol.
def _rebalancear(nodo):
    _actualizar(nodo)
    b = _balance(nodo)
    if b > 1:
        if _balance(nodo.izquierda) < 0:                 # caso izquierda-derecha
            nodo.izquierda = _rotar_izquierda(nodo.izquierda)
        return _rotar_derecha(nodo)
    if b < -1:
        if _balance(nodo.derecha) > 0:                   # caso derecha-izquierda
            nodo.derecha = _rotar_derecha(nodo.derecha)
        return _rotar_izquierda(nodo)
    return nodo


def _insertar(raiz, nuevo):
    if raiz is None:
        return nuevo
    if nuevo.clave() < raiz.clave():
        raiz.izquierda = _insertar(raiz.izquierda, nuevo)
    else:
        raiz.derecha = _insertar(raiz.derecha, nuevo)
    return _rebalancear(raiz)


class ArbolImpactos:

    def __init__(self):
        self._raiz = None
        self._tamano = 0
        self._siguiente_secuencia = 0

    # -- Inserción --

    # `timestamp`: número finito (float/int, no bool) elegido por quien llama; ValueError
    # si no lo es. `tipo`: texto no vacío. Retorna el NodoImpacto creado.
    def insertar(self, timestamp, tipo, deltas=None, origen=None, datos=None):
        self._validar(timestamp, tipo)
        nodo = NodoImpacto(timestamp, self._siguiente_secuencia, tipo, deltas, origen, datos)
        self._siguiente_secuencia += 1
        self._raiz = _insertar(self._raiz, nodo)
        self._tamano += 1
        return nodo

    @staticmethod
    def _validar(timestamp, tipo):
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise ValueError(f"timestamp inválido: {timestamp!r}; se esperaba un número finito.")
        if not isinstance(tipo, str) or not tipo.strip():
            raise ValueError("tipo inválido: se esperaba un texto no vacío.")

    # -- Consulta --

    def tamano(self):
        return self._tamano

    def esta_vacio(self):
        return self._raiz is None

    def altura(self):
        return _altura(self._raiz)

    # Impactos en orden cronológico (inorden). Lista nueva; los nodos son los mismos objetos.
    def inorden(self):
        resultado = []
        pila = []
        actual = self._raiz
        while pila or actual is not None:
            while actual is not None:
                pila.append(actual)
                actual = actual.izquierda
            actual = pila.pop()
            resultado.append(actual)
            actual = actual.derecha
        return resultado

    # Impactos con desde <= timestamp <= hasta, en orden cronológico. Poda las ramas que
    # no pueden contener el rango, así que cuesta O(log n + k). Rango invertido -> [].
    def rango(self, desde, hasta):
        resultado = []
        self._rango(self._raiz, desde, hasta, resultado)
        return resultado

    def _rango(self, nodo, desde, hasta, salida):
        if nodo is None:
            return
        if nodo.timestamp > desde:
            self._rango(nodo.izquierda, desde, hasta, salida)
        if desde <= nodo.timestamp <= hasta:
            salida.append(nodo)
        if nodo.timestamp < hasta:
            self._rango(nodo.derecha, desde, hasta, salida)

    # Impactos de un tipo, en orden cronológico (recorre todo: O(n)).
    def por_tipo(self, tipo):
        return [n for n in self.inorden() if n.tipo == tipo]

    def primero(self):
        nodo = self._raiz
        while nodo is not None and nodo.izquierda is not None:
            nodo = nodo.izquierda
        return nodo

    def ultimo(self):
        nodo = self._raiz
        while nodo is not None and nodo.derecha is not None:
            nodo = nodo.derecha
        return nodo

    # Verifica orden de claves, alturas guardadas y |balance| <= 1 en todos los nodos.
    def es_avl_valido(self):
        return self._validar_subarbol(self._raiz, None, None)[0]

    def _validar_subarbol(self, nodo, minimo, maximo):
        if nodo is None:
            return True, 0
        clave = nodo.clave()
        if (minimo is not None and clave <= minimo) or (maximo is not None and clave >= maximo):
            return False, 0
        ok_i, alt_i = self._validar_subarbol(nodo.izquierda, minimo, clave)
        ok_d, alt_d = self._validar_subarbol(nodo.derecha, clave, maximo)
        if not (ok_i and ok_d):
            return False, 0
        if abs(alt_i - alt_d) > 1 or nodo._altura != 1 + max(alt_i, alt_d):
            return False, 0
        return True, nodo._altura

    # -- Serialización (JSON) --

    # Lista cronológica de impactos + el contador de secuencia (para no repetir claves).
    def a_dict(self):
        return {
            "siguiente_secuencia": self._siguiente_secuencia,
            "impactos": [n.a_dict() for n in self.inorden()],
        }

    # Reconstruye el árbol reinsertando; ValueError si los datos son inválidos.
    @classmethod
    def desde_dict(cls, datos):
        arbol = cls()
        maxima = -1
        for d in datos["impactos"]:
            cls._validar(d["timestamp"], d["tipo"])
            secuencia = d["secuencia"]
            if isinstance(secuencia, bool) or not isinstance(secuencia, int) or secuencia < 0:
                raise ValueError(f"secuencia inválida: {secuencia!r}.")
            nodo = NodoImpacto(
                d["timestamp"], secuencia, d["tipo"], d.get("deltas"), d.get("origen"), d.get("datos"),
            )
            arbol._raiz = _insertar(arbol._raiz, nodo)
            arbol._tamano += 1
            maxima = max(maxima, secuencia)
        siguiente = datos.get("siguiente_secuencia", maxima + 1)
        if isinstance(siguiente, bool) or not isinstance(siguiente, int) or siguiente <= maxima:
            raise ValueError("siguiente_secuencia inconsistente con los impactos.")
        arbol._siguiente_secuencia = siguiente
        if not arbol.es_avl_valido():
            raise ValueError("Impactos con claves repetidas o inconsistentes.")
        return arbol

    def __repr__(self):
        return f"ArbolImpactos(tamano={self._tamano}, altura={self.altura()})"
