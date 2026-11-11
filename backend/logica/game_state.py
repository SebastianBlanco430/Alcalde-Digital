# GameState (modelo puro, sin motor gráfico): confianza 0-100 por grupo (policía,
# ciudadanos, instituciones), relaciones 0-100 con NPC clave y banderas (flags)
# permanentes o recuperables. Las decisiones importantes quedan en un ArbolImpactos
# (AVL cronológico) con el tiempo DE JUEGO, nunca la hora real.
#
# Es global (como los indicadores de la ciudad), solo local (el protocolo en línea no
# lo conoce) y solo serializable: a_dict/desde_dict, sin guardado propio.
#
# Fórmula del cambio de confianza de un evento: 50 % investigación + 30 % moral +
# 20 % secundarios/errores. El tiempo NO cuenta (no hay término temporal).
#
# El nombre de las claves de grupo no choca con el indicador global "confianza" de
# EstadoPartida: aquí son "policia", "ciudadanos" e "instituciones".

import math

from backend.arboles.arbol_impactos import ArbolImpactos
from backend.logica.estado_partida import recortar

GRUPOS = ("policia", "ciudadanos", "instituciones")

CONFIANZA_INICIAL = 50
RELACION_INICIAL = 50

# Pesos de la fórmula; suman 1.
PESO_INVESTIGACION = 0.5
PESO_MORAL = 0.3
PESO_SECUNDARIOS = 0.2

_DECIMALES = 2
_VERSION = 1


# Cambio de confianza que produce un evento. Cada componente es un número finito
# (típicamente -100..100); ausente cuenta 0. Retorna float redondeado.
def calcular_delta(investigacion=0, moral=0, secundarios=0):
    for nombre, valor in (("investigacion", investigacion), ("moral", moral), ("secundarios", secundarios)):
        _validar_numero(valor, nombre)
    delta = PESO_INVESTIGACION * investigacion + PESO_MORAL * moral + PESO_SECUNDARIOS * secundarios
    return round(delta, _DECIMALES)


def _validar_numero(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre} inválido: {valor!r}; se esperaba un número finito.")


def _validar_nombre(valor, que):
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{que} inválido: se esperaba un texto no vacío.")


# `npcs`: ids de los NPC clave cuya relación se lleva (la lista viene de datos, no
# está fija aquí). `reloj`: callable sin argumentos que devuelve el tiempo de juego
# (p. ej. el número de turno de la sesión); por defecto 0 siempre.
class GameState:

    def __init__(self, npcs=(), reloj=None):
        self._confianza = {g: float(CONFIANZA_INICIAL) for g in GRUPOS}
        self._relaciones = {}
        for npc in npcs:
            _validar_nombre(npc, "id de NPC")
            self._relaciones[npc] = float(RELACION_INICIAL)
        self._flags = {}                      # nombre -> permanente (bool)
        self._impactos = ArbolImpactos()
        self._reloj = reloj if reloj is not None else (lambda: 0)

    # -- Confianza --

    def confianza(self, grupo):
        self._comprobar_grupo(grupo)
        return self._confianza[grupo]

    # copia: mutarla no altera el estado
    def confianzas(self):
        return dict(self._confianza)

    # Suma `delta` y recorta a [0, 100]. No registra impacto (sirve para depurar);
    # los cambios con consecuencia narrativa van por aplicar_evento. Retorna el valor nuevo.
    def cambiar_confianza(self, grupo, delta):
        self._comprobar_grupo(grupo)
        _validar_numero(delta, "delta")
        self._confianza[grupo] = round(recortar(self._confianza[grupo] + delta), _DECIMALES)
        return self._confianza[grupo]

    @staticmethod
    def _comprobar_grupo(grupo):
        if grupo not in GRUPOS:
            raise ValueError(f"Grupo inexistente: {grupo!r}; se esperaba uno de {GRUPOS}.")

    # -- Relaciones con NPC clave --

    def npcs(self):
        return list(self._relaciones)

    def relacion(self, npc):
        self._comprobar_npc(npc)
        return self._relaciones[npc]

    def cambiar_relacion(self, npc, delta):
        self._comprobar_npc(npc)
        _validar_numero(delta, "delta")
        self._relaciones[npc] = round(recortar(self._relaciones[npc] + delta), _DECIMALES)
        return self._relaciones[npc]

    def _comprobar_npc(self, npc):
        if npc not in self._relaciones:
            raise ValueError(f"NPC clave inexistente: {npc!r}.")

    # -- Banderas --

    def flag(self, nombre):
        return nombre in self._flags

    def es_permanente(self, nombre):
        return self._flags.get(nombre, False)

    def flags(self):
        return dict(self._flags)

    # Activa la bandera. Una permanente nunca se degrada a recuperable.
    def poner_flag(self, nombre, permanente=False):
        _validar_nombre(nombre, "nombre de flag")
        self._flags[nombre] = bool(permanente) or self._flags.get(nombre, False)

    # Quita una bandera recuperable. Retorna False si no existe o es permanente.
    def quitar_flag(self, nombre):
        if nombre not in self._flags or self._flags[nombre]:
            return False
        del self._flags[nombre]
        return True

    # -- Eventos (decisiones importantes) --

    # Registra una decisión en el ArbolImpactos con el tiempo de juego actual y aplica
    # sus efectos. `efectos`: {grupo: {"investigacion": n, "moral": n, "secundarios": n}}
    # (la fórmula 50/30/20 da el delta de cada grupo). `relaciones`: {npc: delta}.
    # `flags`: lista de nombres o (nombre, permanente). Todo se valida ANTES de cambiar
    # nada. Retorna el NodoImpacto creado.
    def aplicar_evento(self, tipo, efectos=None, relaciones=None, flags=(), origen=None, datos=None):
        deltas_grupo = {}
        for grupo, comp in (efectos or {}).items():
            self._comprobar_grupo(grupo)
            deltas_grupo[grupo] = calcular_delta(
                comp.get("investigacion", 0), comp.get("moral", 0), comp.get("secundarios", 0),
            )
        deltas_npc = {}
        for npc, delta in (relaciones or {}).items():
            self._comprobar_npc(npc)
            _validar_numero(delta, "delta")
            deltas_npc[npc] = delta
        banderas = []
        for item in flags:
            nombre, permanente = (item, False) if isinstance(item, str) else item
            _validar_nombre(nombre, "nombre de flag")
            banderas.append((nombre, bool(permanente)))

        deltas = dict(deltas_grupo)
        deltas.update({f"npc:{n}": d for n, d in deltas_npc.items()})
        # insertar valida timestamp/tipo; si lanza, aún no se cambió nada
        nodo = self._impactos.insertar(
            self._reloj(), tipo, deltas=deltas, origen=origen,
            datos=dict(datos or {}, flags=[n for n, _ in banderas]),
        )
        for grupo, delta in deltas_grupo.items():
            self.cambiar_confianza(grupo, delta)
        for npc, delta in deltas_npc.items():
            self.cambiar_relacion(npc, delta)
        for nombre, permanente in banderas:
            self.poner_flag(nombre, permanente)
        return nodo

    # ArbolImpactos vivo (lectura para el Archivo de casos; no insertar a mano).
    def impactos(self):
        return self._impactos

    # -- Serialización (JSON) --

    def a_dict(self):
        return {
            "version": _VERSION,
            "confianza": dict(self._confianza),
            "relaciones": dict(self._relaciones),
            "flags": dict(self._flags),
            "impactos": self._impactos.a_dict(),
        }

    # Reconstruye el estado; ValueError (sin devolver nada) si los datos no son válidos.
    @classmethod
    def desde_dict(cls, datos, reloj=None):
        if datos.get("version") != _VERSION:
            raise ValueError(f"Versión de GameState no soportada: {datos.get('version')!r}.")
        confianza = datos["confianza"]
        if set(confianza) != set(GRUPOS):
            raise ValueError("Confianza guardada con grupos distintos a los esperados.")
        estado = cls(npcs=list(datos["relaciones"]), reloj=reloj)
        for grupo in GRUPOS:
            _validar_numero(confianza[grupo], "confianza")
            estado._confianza[grupo] = round(recortar(confianza[grupo]), _DECIMALES)
        for npc, valor in datos["relaciones"].items():
            _validar_numero(valor, "relación")
            estado._relaciones[npc] = round(recortar(valor), _DECIMALES)
        for nombre, permanente in datos["flags"].items():
            _validar_nombre(nombre, "nombre de flag")
            estado._flags[nombre] = bool(permanente)
        estado._impactos = ArbolImpactos.desde_dict(datos["impactos"])
        return estado

    def __repr__(self):
        return f"GameState(confianza={self._confianza}, flags={len(self._flags)}, impactos={self._impactos.tamano()})"
