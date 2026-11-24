# Motor de casos v2 de la Fiscalía (modelo puro, sin motor gráfico). Sesión A del 2026-11-23. Formato del JSON:
# sesiones-24nov/fiscalia/contrato-caso.md; tipos compartidos con la escena y la interfaz: casos_v2_tipos.py. Solo se usa
# con ALCALDE_FISCALIA_V2 encendida (backend/logica/fiscalia_bandera.py); el motor v1 (casos.py) queda intacto.
#
# Piezas:
#   validar(datos)   TODAS las reglas del §13 del contrato, con todos los errores juntos y su ruta en el JSON. Nunca
#                    lanza por contenido. Incluye el RECORRIDO REAL (§13.14): búsqueda en anchura sobre los estados del
#                    juego (nodo, opciones usadas, turnos, marcas, pruebas, solidez...) con 0, 1 y 2 parkours.
#   analizar(caso)   por cada combinación de parkours: solidez máxima y finales alcanzables (tests y script).
#   CasoV2           el caso ya validado (desde_dict lanza casos.CasoError con todos los errores).
#   SesionCasoV2     una partida del caso; cumple casos_v2_tipos.SesionCaso.
#
# Las reglas del juego viven UNA sola vez en _Reglas (transiciones puras sobre un Estado inmutable): las usan la sesión
# (que además escribe en el GameState y anota los Cambio) y la búsqueda del validador. Así lo que el validador da por
# alcanzable es exactamente lo que se puede jugar.
#
# GameState: las pruebas se guardan como «evidencia:<id_caso>.<id_prueba>» (evidencia.id_de_caso). Al llegar a un final
# se deja el MISMO rastro que el v1 (caso:<id>:jugado · :final:<nodo> · :resultado:<res> · :acusado:<opcion>) y se
# aplican sus efectos.grupos: casos.resultado_de, las misiones y el Archivo de casos siguen funcionando.

import math
from collections import deque
from dataclasses import dataclass, replace

from backend.logica import casos, diagrama_caso, evidencia
from backend.logica.casos import PREFIJO_FLAG, CasoError
from backend.logica.casos_v2_tipos import (BLOQUEADA, ESCENAS, LIBRE, MAX_OPCIONES, PISTA_POR_DEFECTO, PLANOS,
                                           RESULTADOS, TERMINAR, TIPOS_NODO, VOLVER, Cambio, VistaNodo, VistaOpcion,
                                           VistaParkour)
from backend.logica.game_state import GRUPOS

FORMATO = 2
NIVELES = ("sector_1", "sector_2")
MODELOS = ("smoking.glb", "periodista.glb", "ciudadano.glb", "brasilena.glb", "npc_hombre_01.glb", "npc_hombre_02.glb",
           "npc_hombre_03.glb", "npc_mujer_01.glb", "npc_mujer_02.glb")
EXPRESIONES = ("neutral", "serio", "nervioso", "enojado", "satisfecho", "triste", "sorprendido")
PELO_ESTILOS = ("corto", "largo", "calvo")
ACCESORIOS = ("ninguno", "gafas", "barba", "corbata")
DIFICULTADES = ("facil", "media", "dificil")
COMPONENTES = ("investigacion", "moral", "secundarios")
ROTULOS = {"oficina": "Despacho del fiscal", "laboratorio": "Laboratorio forense", "sala": "Sala de interrogatorio"}

# Límites del §13 (para que el recorrido real sea rápido) y del resto del contrato.
MAX_NODOS, MAX_PRUEBAS, MAX_MARCAS, MAX_RUEDAS_VOLVER = 80, 10, 12, 10
HITOS_MIN, HITOS_MAX = 8, 24
TOPE_ESTADOS = 200_000

_COMUNES = {"tipo", "escena", "personaje", "expresion", "texto", "plano", "solidez", "efectos", "hito"}
_CLAVES_NODO = {"dialogo": _COMUNES | {"siguiente"}, "rueda": _COMUNES | {"opciones", "reloj", "turnos", "al_terminar"},
                "laboratorio": _COMUNES | {"siguiente"}, "acusacion": _COMUNES | {"acusados", "reloj"},
                "final": _COMUNES | {"resultado", "titulo"}}
_CLAVES_OPCION = {"id", "etiqueta", "dice", "destino", "requiere", "pista", "oculta", "una_vez", "solidez", "presenta",
                  "efectos"}
_CLAVES_ACUSADO = {"id", "etiqueta", "personaje", "rutas", "destino", "requiere", "pista", "oculta", "dice"}
_CLAVES_CONDICION = {"evidencia", "alguna_evidencia", "sin_evidencia", "marcas", "sin_marcas", "visitado",
                     "no_visitado", "solidez"}
_CLAVES_EFECTOS = {"da_evidencia", "marcas", "grupos"}
_OBSOLETAS = ("relaciones", "flags", "confianza", "relacion", "contradicciones", "temporizador", "preguntas",
              "fin_por_errores", "terminal", "parkour")
_ORIGEN_PARKOUR = "parkour"


def _texto(v):
    return isinstance(v, str) and v.strip() != ""


def _entero(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _id_valido(v, prohibidos=(":", ".", "/", " ")):
    return _texto(v) and not any(c in v for c in prohibidos)


def _dicts(valor):
    return valor if isinstance(valor, dict) else {}


def _listas(valor):
    return valor if isinstance(valor, list) else []


def _opciones(nodo):
    clave = "acusados" if nodo.get("tipo") == "acusacion" else "opciones"
    return [o for o in _listas(nodo.get(clave)) if isinstance(o, dict)]


# -- Estado del juego (inmutable: la búsqueda lo guarda en un conjunto) --

@dataclass(frozen=True)
class Estado:
    nodo: str
    solidez: int
    hub: str | None = None             # rueda a la que regresa «@volver» (la última en que se eligió)
    usadas: frozenset = frozenset()    # (rueda, opción) gastadas (una_vez)
    turnos: tuple = ()                 # ((rueda, elecciones), ...) ordenado
    marcas: frozenset = frozenset()
    pruebas: tuple = ()                # ids sin prefijo, en el orden en que se consiguieron
    visitados: frozenset = frozenset()
    acusado: str | None = None


def _turnos_de(estado, rueda):
    return dict(estado.turnos).get(rueda, 0)


def _con_turno(estado, rueda):
    t = dict(estado.turnos)
    t[rueda] = t.get(rueda, 0) + 1
    return tuple(sorted(t.items()))


# -- Reglas del juego (transiciones puras) --

# Un evento de una transición: ("evidencia", id, motivo) · ("solidez", delta, valor, motivo) · ("final", nodo).
class _Reglas:

    def __init__(self, datos):
        self.nodos = datos["nodos"]
        self.evidencias = _dicts(datos.get("evidencias"))
        sol = _dicts(datos.get("solidez"))
        self.inicial = sol.get("inicial", 0)
        self.umbrales = _dicts(sol.get("umbrales"))
        self.parkours = [p for p in _listas(_dicts(datos.get("laboratorio")).get("parkours")) if isinstance(p, dict)]
        self.inicio = datos["inicio"]

    def nodo(self, estado):
        return self.nodos[estado.nodo]

    def estado_inicial(self, eventos):
        return self.entrar(Estado(self.inicio, max(0, min(100, self.inicial))), self.inicio, eventos)

    # -- Condiciones --

    def valor_umbral(self, v):
        return self.umbrales.get(v) if isinstance(v, str) else v

    def cumple(self, cond, estado):
        if not cond:
            return True
        pruebas = set(estado.pruebas)
        if not all(e in pruebas for e in cond.get("evidencia", [])):
            return False
        alguna = cond.get("alguna_evidencia")
        if alguna and not any(e in pruebas for e in alguna):
            return False
        if any(e in pruebas for e in cond.get("sin_evidencia", [])):
            return False
        if not all(m in estado.marcas for m in cond.get("marcas", [])):
            return False
        if any(m in estado.marcas for m in cond.get("sin_marcas", [])):
            return False
        if not all(n in estado.visitados for n in cond.get("visitado", [])):
            return False
        if any(n in estado.visitados for n in cond.get("no_visitado", [])):
            return False
        rango = cond.get("solidez")
        if rango:
            minimo, maximo = self.valor_umbral(rango.get("min", 0)), self.valor_umbral(rango.get("max", 100))
            if not minimo <= estado.solidez <= maximo:
                return False
        return True

    def estado_opcion(self, estado, opcion):
        """LIBRE, BLOQUEADA o None (gastada)."""
        if opcion.get("una_vez", True) and (estado.nodo, opcion["id"]) in estado.usadas:
            return None
        return LIBRE if self.cumple(opcion.get("requiere"), estado) else BLOQUEADA

    def libres(self, estado):
        return [o for o in _opciones(self.nodo(estado)) if self.estado_opcion(estado, o) == LIBRE]

    # -- Efectos --

    def _solidez(self, estado, delta, motivo, eventos):
        if not delta:
            return estado
        nuevo = max(0, min(100, estado.solidez + delta))
        if nuevo == estado.solidez:
            return estado
        eventos.append(("solidez", nuevo - estado.solidez, nuevo, motivo))
        return replace(estado, solidez=nuevo)

    def dar_prueba(self, estado, id_prueba, motivo, eventos):
        if id_prueba in estado.pruebas:
            return estado
        eventos.append(("evidencia", id_prueba, motivo))
        estado = replace(estado, pruebas=estado.pruebas + (id_prueba,))
        delta = _dicts(self.evidencias.get(id_prueba)).get("solidez", 0)
        return self._solidez(estado, delta, _ORIGEN_PARKOUR if motivo == _ORIGEN_PARKOUR else "evidencia", eventos)

    def _efectos(self, estado, efectos, motivo, eventos):
        efectos = efectos or {}
        for id_prueba in efectos.get("da_evidencia", []):
            estado = self.dar_prueba(estado, id_prueba, motivo, eventos)
        if efectos.get("marcas"):
            estado = replace(estado, marcas=estado.marcas | frozenset(efectos["marcas"]))
        return estado

    # -- Movimiento --

    def entrar(self, estado, destino, eventos, limite=200):
        """Entra a `destino` (resuelve «@volver»), aplica lo de la primera visita y salta las ruedas sin turnos u opciones."""
        for _ in range(limite):
            if destino == VOLVER:
                if estado.hub is None:
                    raise CasoError(f"«@volver» sin una rueda a la que regresar (desde {estado.nodo!r}).")
                destino = estado.hub
            nuevo = destino not in estado.visitados
            nodo = self.nodos[destino]
            estado = replace(estado, nodo=destino, visitados=estado.visitados | {destino})
            if nuevo:
                estado = self._solidez(estado, nodo.get("solidez", 0), "nodo", eventos)
                estado = self._efectos(estado, nodo.get("efectos"), "nodo", eventos)
            if nodo["tipo"] == "final":
                eventos.append(("final", destino))
                return estado
            if nodo["tipo"] != "rueda" or nodo.get("al_terminar") is None:
                return estado
            agotada = nodo.get("turnos") is not None and _turnos_de(estado, destino) >= nodo["turnos"]
            if not agotada and self.libres(estado):
                return estado
            destino = nodo["al_terminar"]
        raise CasoError(f"Demasiados saltos seguidos al entrar a {destino!r}: ¿un ciclo de al_terminar?")

    def continuar(self, estado, eventos):
        nodo = self.nodo(estado)
        if nodo["tipo"] != "dialogo":
            raise CasoError(f"continuar() solo en diálogos; el nodo {estado.nodo!r} es {nodo['tipo']}.")
        return self.entrar(estado, nodo["siguiente"], eventos)

    def elegir(self, estado, id_opcion, eventos):
        nodo = self.nodo(estado)
        if nodo["tipo"] not in ("rueda", "acusacion"):
            raise CasoError(f"El nodo {estado.nodo!r} ({nodo['tipo']}) no tiene opciones.")
        if id_opcion == TERMINAR:
            if _dicts(nodo.get("reloj")).get("por_defecto") != TERMINAR or nodo.get("al_terminar") is None:
                raise CasoError(f"El nodo {estado.nodo!r} no termina por reloj («{TERMINAR}»).")
            estado = replace(estado, turnos=_con_turno(estado, estado.nodo))
            return self.entrar(estado, nodo["al_terminar"], eventos)
        opcion = next((o for o in _opciones(nodo) if o.get("id") == id_opcion), None)
        if opcion is None:
            raise CasoError(f"El nodo {estado.nodo!r} no tiene la opción {id_opcion!r}.")
        if self.estado_opcion(estado, opcion) != LIBRE:
            raise CasoError(f"La opción {id_opcion!r} no está disponible en {estado.nodo!r}.")
        if nodo["tipo"] == "acusacion":
            destino = next((r["destino"] for r in opcion.get("rutas") or [] if self.cumple(r.get("requiere"), estado)),
                           opcion["destino"])
            estado = replace(estado, acusado=opcion.get("personaje") or opcion["id"])
            return self.entrar(estado, destino, eventos)
        usadas = estado.usadas | {(estado.nodo, id_opcion)} if opcion.get("una_vez", True) else estado.usadas
        estado = replace(estado, usadas=usadas, turnos=_con_turno(estado, estado.nodo), hub=estado.nodo)
        estado = self._solidez(estado, opcion.get("solidez", 0), "opcion", eventos)
        estado = self._efectos(estado, opcion.get("efectos"), "opcion", eventos)
        return self.entrar(estado, opcion["destino"], eventos)

    def parkour(self, nivel):
        return next((p for p in self.parkours if p.get("nivel") == nivel), None)

    def completar_parkour(self, estado, nivel, eventos):
        """(estado, True) si entregó su prueba; (estado, False) fuera del laboratorio, nivel ajeno o prueba ya tenida."""
        p = self.parkour(nivel)
        if self.nodo(estado)["tipo"] != "laboratorio" or p is None or p["evidencia"] in estado.pruebas:
            return estado, False
        return self.dar_prueba(estado, p["evidencia"], _ORIGEN_PARKOUR, eventos), True

    def salir_laboratorio(self, estado, eventos):
        nodo = self.nodo(estado)
        if nodo["tipo"] != "laboratorio":
            raise CasoError(f"salir_laboratorio() solo en el laboratorio; el nodo {estado.nodo!r} es {nodo['tipo']}.")
        return self.entrar(estado, nodo["siguiente"], eventos)

    # -- Acciones posibles (para la búsqueda) --

    def sucesores(self, estado, permitidos):
        nodo = self.nodo(estado)
        tipo = nodo["tipo"]
        if tipo == "final":
            return []
        if tipo == "dialogo":
            return [self.continuar(estado, [])]
        if tipo == "laboratorio":
            salida = [self.salir_laboratorio(estado, [])]
            for nivel in permitidos:
                nuevo, entregado = self.completar_parkour(estado, nivel, [])
                if entregado:
                    salida.append(nuevo)
            return salida
        salida = [self.elegir(estado, o["id"], []) for o in self.libres(estado)]
        if _dicts(nodo.get("reloj")).get("por_defecto") == TERMINAR and nodo.get("al_terminar") is not None:
            salida.append(self.elegir(estado, TERMINAR, []))
        return salida


# -- Caso --

class CasoV2:

    def __init__(self, datos):
        self.datos = datos
        self.id = datos["id"]
        self.titulo = datos["titulo"]
        self.resumen = datos.get("resumen", "")
        self.rejugable = bool(datos.get("rejugable", False))
        self.mision = dict(_dicts(datos.get("mision")))
        sol = _dicts(datos.get("solidez"))
        self.solidez_inicial = sol.get("inicial", 0)
        self.umbrales = dict(_dicts(sol.get("umbrales")))
        self.personajes = _dicts(datos.get("personajes"))
        self.evidencias = _dicts(datos.get("evidencias"))
        self.laboratorio = [p for p in _listas(_dicts(datos.get("laboratorio")).get("parkours")) if isinstance(p, dict)]
        escenas = _dicts(datos.get("escenas"))
        self.escenas = {e: (_dicts(escenas.get(e)).get("rotulo") or ROTULOS[e]) for e in ESCENAS}
        self.nodos = datos["nodos"]
        self.inicio = datos["inicio"]
        self.final_abandono = datos["final_abandono"]

    @classmethod
    def desde_dict(cls, datos, niveles_validos=None):
        errores = validar(datos, niveles_validos)
        if errores:
            ident = datos.get("id", "?") if isinstance(datos, dict) else "?"
            raise CasoError(f"Caso v2 {ident!r} inválido ({len(errores)} error(es)):\n- " + "\n- ".join(errores))
        return cls(datos)

    def nodo(self, id_nodo):
        return self.nodos[id_nodo]

    def finales(self):
        return [i for i, n in self.nodos.items() if n["tipo"] == "final"]

    def nombre_evidencia(self, id_evidencia):
        return _dicts(self.evidencias.get(id_evidencia)).get("nombre", id_evidencia)

    def nombre_personaje(self, id_personaje):
        return _dicts(self.personajes.get(id_personaje)).get("nombre", id_personaje or "Narrador")

    def __repr__(self):
        return f"CasoV2({self.id!r}, nodos={len(self.nodos)}, finales={len(self.finales())})"


# -- Rastro (el mismo del v1: se leen con las funciones de casos.py) --

def resultado_de(game_state, id_caso):
    return casos.resultado_de(game_state, id_caso)


def puede_jugar(game_state, caso):
    return caso.rejugable or resultado_de(game_state, caso.id) is None


# -- Sesión --

def _flag(id_caso, *partes):
    return PREFIJO_FLAG + id_caso + ":" + ":".join(partes)


# Abandonar el caso (pausa -> «Abandonar caso») deja además «caso:<id>:abandonado:si». La misión se cierra igual (no
# queda atascada) pero NO se paga (decisión del orquestador, sesión E; P5 de la verificación): lo consulta
# misiones_digitales.cobra. casos.casos_jugados ignora la clave extra.
ABANDONADO = "abandonado"


def abandonado(game_state, id_caso):
    """¿El caso `id_caso` se cerró abandonándolo?"""
    try:
        return game_state is not None and bool(game_state.flag(_flag(id_caso, ABANDONADO, "si")))
    except (AttributeError, TypeError):
        return False


class SesionCasoV2:

    def __init__(self, caso, game_state, estado=None):
        self.caso = caso
        self.gs = game_state
        self._reglas = _Reglas(caso.datos)
        self._cambios = []
        self._restante = None
        self.historial = []
        if estado is None:
            eventos = []
            self._estado = self._reglas.estado_inicial(eventos)
            self._procesar(eventos)
        else:
            self._restaurar(estado)

    # -- Consulta --

    @property
    def solidez(self):
        return self._estado.solidez

    @property
    def terminado(self):
        return self._nodo()["tipo"] == "final"

    def _nodo(self):
        return self.caso.nodo(self._estado.nodo)

    def visitados(self):
        return set(self._estado.visitados)

    def evidencias_en_mano(self):
        return tuple(self._estado.pruebas)

    def tomar_cambios(self):
        cambios, self._cambios = tuple(self._cambios), []
        return cambios

    def diagrama(self):
        return diagrama_caso.construir(self.caso.nodos, self.caso.inicio, self._estado.visitados)

    def parkours(self):
        return tuple(VistaParkour(p["nivel"], p.get("nombre", p["nivel"]), p.get("descripcion", ""), p["evidencia"],
                                  self.caso.nombre_evidencia(p["evidencia"]), p["evidencia"] in self._estado.pruebas)
                     for p in self.caso.laboratorio)

    def _reloj(self):
        nodo = self._nodo()
        reloj = nodo.get("reloj") if nodo["tipo"] in ("rueda", "acusacion") else None
        return float(reloj["segundos"]) if reloj else None

    def vista(self):
        nodo, e = self._nodo(), self._estado
        opciones = []
        for posicion, o in enumerate(_opciones(nodo)):
            estado = self._reglas.estado_opcion(e, o)
            if estado is None or (estado == BLOQUEADA and o.get("oculta")):
                continue
            pista = (o.get("pista") or PISTA_POR_DEFECTO) if estado == BLOQUEADA else ""
            opciones.append(VistaOpcion(o["id"], o.get("etiqueta", o["id"]), estado, pista, o.get("dice", ""),
                                        o.get("presenta"), o.get("personaje"), posicion))
        turnos = nodo.get("turnos") if nodo["tipo"] == "rueda" else None
        return VistaNodo(
            id=e.nodo, tipo=nodo["tipo"], escena=nodo.get("escena") if nodo["tipo"] != "final" else None,
            personaje=nodo.get("personaje"), expresion=nodo.get("expresion"), texto=nodo.get("texto", ""),
            plano=nodo.get("plano"), titulo=nodo.get("titulo", "") if nodo["tipo"] == "final" else "",
            resultado=nodo.get("resultado"), opciones=tuple(opciones), reloj_segundos=self._reloj(),
            restante=self._restante, turnos_restantes=None if turnos is None else max(0, turnos - _turnos_de(e, e.nodo)))

    # -- Acciones --

    def _hacer(self, accion, registro):
        if self.terminado:
            raise CasoError(f"El caso {self.caso.id!r} ya terminó en {self._estado.nodo!r}.")
        eventos = []
        nodo_antes = self._estado.nodo
        resultado = accion(eventos)
        self.historial.append(dict(registro, nodo=nodo_antes))
        self._procesar(eventos)
        return resultado

    def continuar(self):
        def accion(eventos):
            self._estado = self._reglas.continuar(self._estado, eventos)
        self._hacer(accion, {"accion": "continuar"})

    def elegir(self, id_opcion, por_tiempo=False):
        def accion(eventos):
            self._estado = self._reglas.elegir(self._estado, id_opcion, eventos)
        self._hacer(accion, {"accion": "elegir", "opcion": id_opcion, "por_tiempo": bool(por_tiempo)})

    def avanzar_tiempo(self, dt):
        if self._restante is None or self.terminado:
            return False
        self._restante = max(0.0, self._restante - max(0.0, float(dt)))
        if self._restante > 0:
            return False
        self.elegir(self._nodo()["reloj"]["por_defecto"], por_tiempo=True)
        return True

    def completar_parkour(self, nivel):
        if self.terminado:
            return False
        def accion(eventos):
            self._estado, entregado = self._reglas.completar_parkour(self._estado, nivel, eventos)
            return entregado
        return self._hacer(accion, {"accion": "parkour", "nivel": nivel, "_origen": f"{_ORIGEN_PARKOUR}:{nivel}"})

    def salir_laboratorio(self):
        def accion(eventos):
            self._estado = self._reglas.salir_laboratorio(self._estado, eventos)
        self._hacer(accion, {"accion": "salir_laboratorio"})

    def abandonar(self):
        if self.terminado:
            return
        def accion(eventos):
            self._abandono = True
            self._estado = self._reglas.entrar(replace(self._estado, acusado=None), self.caso.final_abandono, eventos)
        self._hacer(accion, {"accion": "abandonar"})

    # -- Efectos de los eventos: Cambio para la interfaz y escrituras en el GameState --

    def _procesar(self, eventos):
        origen = self.historial[-1].pop("_origen", None) if self.historial else None
        for evento in eventos:
            if evento[0] == "solidez":
                _, delta, valor, motivo = evento
                self._cambios.append(Cambio("solidez", delta=delta, valor=valor, motivo=motivo))
            elif evento[0] == "evidencia":
                _, id_prueba, motivo = evento
                self._cambios.append(Cambio("evidencia", evidencia=id_prueba,
                                            nombre=self.caso.nombre_evidencia(id_prueba), motivo=motivo))
                if self.gs is not None:
                    evidencia.otorgar(self.gs, evidencia.id_de_caso(self.caso.id, id_prueba),
                                      origen if motivo == _ORIGEN_PARKOUR and origen else f"caso:{self.caso.id}",
                                      datos={"caso": self.caso.id})
            elif evento[0] == "final":
                self._cerrar(evento[1])
        # El reloj se reinicia cada vez que una rueda (o la acusación) sale en pantalla.
        self._restante = self._reloj()

    def _cerrar(self, id_final):
        if self.gs is None:
            return
        nodo, id_caso, acusado = self.caso.nodo(id_final), self.caso.id, self._estado.acusado
        flags = [(_flag(id_caso, "jugado"), True), (_flag(id_caso, "final", id_final), True),
                 (_flag(id_caso, "resultado", nodo["resultado"]), True)]
        if acusado:
            flags.append((_flag(id_caso, "acusado", acusado), True))
        datos = {"caso": id_caso, "nodo": id_final, "resultado": nodo["resultado"], "acusado": acusado,
                 "solidez": self.solidez}
        if getattr(self, "_abandono", False):
            flags.append((_flag(id_caso, ABANDONADO, "si"), True))
            datos["abandonado"] = True
        self.gs.aplicar_evento("caso:final", efectos=_dicts(nodo.get("efectos")).get("grupos") or None, flags=flags,
                               origen=f"caso:{id_caso}", datos=datos)

    # -- Guardado del progreso a medias (los efectos ya viven en el GameState) --

    def a_dict(self):
        e = self._estado
        return {"formato": FORMATO, "caso": self.caso.id, "nodo": e.nodo, "solidez": e.solidez, "hub": e.hub,
                "usadas": sorted([n, o] for n, o in e.usadas), "turnos": dict(e.turnos), "marcas": sorted(e.marcas),
                "pruebas": list(e.pruebas), "visitados": sorted(e.visitados), "acusado": e.acusado,
                "restante": self._restante, "historial": list(self.historial)}

    def _restaurar(self, d):
        try:
            if d.get("caso") != self.caso.id or d.get("nodo") not in self.caso.nodos:
                raise CasoError("El progreso guardado no corresponde a este caso.")
            self._estado = Estado(
                nodo=d["nodo"], solidez=max(0, min(100, int(d["solidez"]))), hub=d.get("hub"),
                usadas=frozenset((n, o) for n, o in d.get("usadas", [])),
                turnos=tuple(sorted((str(k), int(v)) for k, v in _dicts(d.get("turnos")).items())),
                marcas=frozenset(d.get("marcas", [])), pruebas=tuple(d.get("pruebas", [])),
                visitados=frozenset(d.get("visitados", [])), acusado=d.get("acusado"))
            self._restante = d.get("restante")
            self.historial = list(d.get("historial", []))
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            if isinstance(error, CasoError):
                raise
            raise CasoError(f"Progreso guardado ilegible: {error}") from None


# -- Recorrido real (búsqueda sobre los estados del juego) --

class _Recorrido:
    """Búsqueda en anchura sobre los Estado alcanzables con los parkours `permitidos`. El conjunto de estados vistos es
    la memoización. Para que no explote, cada estado se CANONIZA: se olvida lo que ya no puede influir (opciones y
    turnos de ruedas que ya no se pueden volver a pisar, visitas a nodos que no vuelven a salir ni se consultan, la rueda
    de «@volver» si no hay un «@volver» por delante)."""

    def __init__(self, reglas, permitidos, tope):
        self.r = reglas
        self.permitidos = permitidos
        self.tope = tope
        nodos = reglas.nodos
        grafo = diagrama_caso.aristas(nodos)
        self.alcance = {n: diagrama_caso.alcanzables(grafo, n) for n in nodos}
        self.consultados = set()
        for nodo in nodos.values():
            for cond in _condiciones_de(nodo):
                self.consultados.update(cond.get("visitado", []) + cond.get("no_visitado", []))
        sin_eleccion = {n: [d for d in ([nodos[n].get("siguiente")] if nodos[n]["tipo"] in ("dialogo", "laboratorio")
                                         else [nodos[n].get("al_terminar")] if nodos[n]["tipo"] == "rueda" else [])
                            if d in nodos] for n in nodos}
        self.vuelve = {n: any(nodos[m].get("siguiente") == VOLVER for m in diagrama_caso.alcanzables(sin_eleccion, n))
                       for n in nodos}

    def canon(self, e):
        hub = e.hub if self.vuelve.get(e.nodo) else None
        vivos = set(self.alcance[e.nodo]) | (self.alcance[hub] if hub else set())
        return replace(
            e, hub=hub, usadas=frozenset(u for u in e.usadas if u[0] in vivos),
            turnos=tuple(t for t in e.turnos if t[0] in vivos), pruebas=tuple(sorted(e.pruebas)),
            visitados=frozenset(v for v in e.visitados if v in vivos or v in self.consultados))

    def ejecutar(self):
        self.tocados = set()
        self.finales = {}
        self.solidez_max = 0
        self.completo = True
        self.errores_juego = []
        inicial = self.r.estado_inicial([])
        self.tocados |= inicial.visitados
        inicial = self.canon(inicial)
        indice = {inicial: 0}
        estados = [inicial]
        sucesores = []
        cola = deque([0])
        while cola:
            i = cola.popleft()
            e = estados[i]
            self.solidez_max = max(self.solidez_max, e.solidez)
            if self.r.nodos[e.nodo]["tipo"] == "final":
                self.finales[e.nodo] = max(self.finales.get(e.nodo, 0), e.solidez)
            try:
                siguientes = self.r.sucesores(e, self.permitidos)
            except CasoError as error:
                self.errores_juego.append((e, str(error)))
                siguientes = []
            hijos = []
            for s in siguientes:
                self.tocados |= s.visitados
                s = self.canon(s)
                j = indice.get(s)
                if j is None:
                    if len(estados) >= self.tope:
                        self.completo = False
                        continue
                    j = indice[s] = len(estados)
                    estados.append(s)
                    cola.append(j)
                hijos.append(j)
            sucesores.append(hijos)
        self.estados = estados
        self.sin_salida = []
        if self.completo:
            hacia_final = {i for i, e in enumerate(estados) if self.r.nodos[e.nodo]["tipo"] == "final"}
            padres = [[] for _ in estados]
            for i, hijos in enumerate(sucesores):
                for j in hijos:
                    padres[j].append(i)
            pila = list(hacia_final)
            while pila:
                for p in padres[pila.pop()]:
                    if p not in hacia_final:
                        hacia_final.add(p)
                        pila.append(p)
            self.sin_salida = [e for i, e in enumerate(estados) if i not in hacia_final]
        return self


def _condiciones_de(nodo):
    conds = []
    for o in _opciones(nodo):
        conds.append(_dicts(o.get("requiere")))
        conds.extend(_dicts(_dicts(r).get("requiere")) for r in _listas(o.get("rutas")))
    return conds


def _combinaciones(parkours):
    niveles = sorted(p.get("nivel") for p in parkours if isinstance(p.get("nivel"), str))
    if not niveles:
        return [()]
    combos = [()] + ([(n,) for n in niveles] if len(niveles) > 1 else []) + [tuple(niveles)]
    return combos


def _exigencia_de_finales(nodos, umbrales):
    """{final: exigencia}: el mayor `solidez.min` (resuelto) de las rutas de acusación que llevan a él (0 si ninguna)."""
    exigencia = {i: 0 for i, n in nodos.items() if n.get("tipo") == "final"}
    for nodo in nodos.values():
        if nodo.get("tipo") != "acusacion":
            continue
        for o in _opciones(nodo):
            for r in _listas(o.get("rutas")):
                minimo = _dicts(_dicts(_dicts(r).get("requiere")).get("solidez")).get("min", 0)
                minimo = umbrales.get(minimo, 0) if isinstance(minimo, str) else minimo
                if r.get("destino") in exigencia and _numero(minimo):
                    exigencia[r["destino"]] = max(exigencia[r["destino"]], minimo)
    return exigencia


def mejores_finales(nodos, umbrales):
    """Los finales de resultado «exito» de mayor exigencia (el «mejor final» del §5)."""
    exigencia = _exigencia_de_finales(nodos, umbrales)
    exitos = {i: x for i, x in exigencia.items() if nodos[i].get("resultado") == "exito"}
    if not exitos:
        return []
    tope = max(exitos.values())
    return sorted(i for i, x in exitos.items() if x == tope)


def _analizar_datos(datos, tope_estados=TOPE_ESTADOS):
    reglas = _Reglas(datos)
    combos = _combinaciones(reglas.parkours)
    salida = {"combinaciones": {}, "avisos": [], "alcanzados": set(), "sin_salida": {}, "errores_juego": {},
              "mejores": mejores_finales(reglas.nodos, reglas.umbrales), "con_laboratorio": bool(reglas.parkours)}
    for combo in combos:
        rec = _Recorrido(reglas, combo, tope_estados).ejecutar()
        salida["combinaciones"][combo] = {"solidez_max": rec.solidez_max, "finales": dict(rec.finales),
                                          "estados": len(rec.estados), "completo": rec.completo}
        salida["alcanzados"] |= rec.tocados
        salida["sin_salida"][combo] = rec.sin_salida
        salida["errores_juego"][combo] = rec.errores_juego
        if not rec.completo:
            salida["avisos"].append(f"recorrido ({_nombre_combo(combo)}): se superó el tope de {tope_estados} estados; "
                                    "no se comprobaron la alcanzabilidad jugando, la tabla de solidez ni los estados "
                                    "sin salida")
    return salida


def analizar(caso, tope_estados=TOPE_ESTADOS):
    """Por cada combinación de parkours (tupla ordenada de niveles; () = ninguno): solidez máxima, finales alcanzables
    {final: mejor solidez al llegar}, estados explorados y si la búsqueda fue completa. Más `avisos`, `mejores` (el o
    los mejores finales del §5) y `alcanzados` (nodos que se pisan jugando, con cualquier combinación)."""
    datos = caso.datos if isinstance(caso, CasoV2) else caso
    return _analizar_datos(datos, tope_estados)


def _nombre_combo(combo):
    if not combo:
        return "0 parkours"
    return f"{len(combo)} parkour{'s' if len(combo) > 1 else ''}: {', '.join(combo)}"


# -- Validación --

class _Validador:

    def __init__(self, datos, niveles_validos, tope_estados):
        self.d = datos
        self.niveles = tuple(niveles_validos) if niveles_validos is not None else NIVELES
        self.tope = tope_estados
        self.errores = []
        self.avisos = []
        self.grave = False                  # estructura que impide recorrer el grafo con seguridad
        self.nodos = datos.get("nodos") if isinstance(datos.get("nodos"), dict) else {}
        self.personajes = _dicts(datos.get("personajes"))
        self.evidencias = _dicts(datos.get("evidencias"))
        self.umbrales = {}
        self.otorgadas_parkour = {}
        self.otorgadas_efecto = {}
        self.marcas = set()

    def err(self, donde, mensaje, grave=False):
        self.errores.append(f"{donde}: {mensaje}")
        self.grave = self.grave or grave

    def ejecutar(self):
        self._raiz()
        self._mision()
        self._solidez()
        self._personajes()
        self._evidencias()
        if not self.nodos:
            self.err("nodos", "debe ser un objeto con al menos un nodo", grave=True)
            return self.errores
        if len(self.nodos) > MAX_NODOS:
            self.err("nodos", f"como mucho {MAX_NODOS} nodos (hay {len(self.nodos)})")
        self._laboratorio()
        for id_nodo, nodo in self.nodos.items():
            self._nodo(id_nodo, nodo)
        self._conjunto()
        if not self.grave:
            self._grafo()
        if not self.grave:
            self._recorrido()
        return self.errores

    # -- 1 Raíz --

    def _raiz(self):
        d = self.d
        if d.get("formato") != FORMATO:
            self.err("formato", f"debe ser {FORMATO}, no {d.get('formato')!r}")
        for clave in ("id", "titulo", "resumen", "inicio", "final_abandono"):
            if not _texto(d.get(clave)):
                self.err(clave, "falta o no es un texto no vacío", grave=clave in ("inicio", "final_abandono"))
        if _texto(d.get("id")) and not _id_valido(d["id"]):
            self.err("id", "sin ':', '.', '/' ni espacios (se usa en los flags del GameState)")
        if "rejugable" in d and not isinstance(d["rejugable"], bool):
            self.err("rejugable", "true o false")
        for clave in _OBSOLETAS:
            if clave in d:
                self.err(clave, "no existe en el formato v2")
        if "escenas" in d:
            escenas = d["escenas"]
            if not isinstance(escenas, dict):
                self.err("escenas", "debe ser un objeto")
            else:
                for nombre, valor in escenas.items():
                    if nombre not in ESCENAS:
                        self.err(f"escenas.{nombre}", f"solo existen {ESCENAS}")
                    elif not isinstance(valor, dict) or set(valor) - {"rotulo"} \
                            or not (_texto(valor.get("rotulo")) and len(valor["rotulo"]) <= 32):
                        self.err(f"escenas.{nombre}", "solo {'rotulo': texto de hasta 32 caracteres}")

    # -- 2 Misión --

    def _mision(self):
        m = self.d.get("mision")
        if not isinstance(m, dict):
            self.err("mision", "falta (objeto con id, titulo, mensaje, pago, dificultad, grupo y dia)")
            return
        if not _texto(m.get("id")):
            self.err("mision.id", "texto no vacío (convención: fiscalia_<id del caso>)")
        for clave, maximo in (("titulo", 28), ("mensaje", 140)):
            if not _texto(m.get(clave)) or len(m[clave]) > maximo:
                self.err(f"mision.{clave}", f"texto de 1 a {maximo} caracteres")
        if _texto(m.get("mensaje")) and "fiscal" not in m["mensaje"].lower():
            self.err("mision.mensaje", "debe decir que hay que ir a la Fiscalía")
        pago = m.get("pago")
        if not _entero(pago) or not 20 <= pago <= 120 or pago % 5:
            self.err("mision.pago", f"entero múltiplo de 5 entre 20 y 120, no {pago!r}")
        if m.get("dificultad") not in DIFICULTADES:
            self.err("mision.dificultad", f"una de {DIFICULTADES}")
        if m.get("grupo") not in GRUPOS:
            self.err("mision.grupo", f"uno de {GRUPOS}")
        if not _entero(m.get("dia")) or not 1 <= m["dia"] <= 7:
            self.err("mision.dia", f"entero de 1 a 7, no {m.get('dia')!r}")

    # -- 3 Solidez --

    def _solidez(self):
        s = self.d.get("solidez")
        if not isinstance(s, dict):
            self.err("solidez", "falta (objeto con inicial y umbrales)")
            return
        if not _entero(s.get("inicial")) or not 0 <= s["inicial"] <= 100:
            self.err("solidez.inicial", f"entero de 0 a 100, no {s.get('inicial')!r}")
        umbrales = s.get("umbrales")
        if not isinstance(umbrales, dict) or not 1 <= len(umbrales) <= 3:
            self.err("solidez.umbrales", "de 1 a 3 umbrales {nombre: entero 1-100}")
            umbrales = umbrales if isinstance(umbrales, dict) else {}
        for nombre, valor in umbrales.items():
            if not _id_valido(nombre) or not _entero(valor) or not 1 <= valor <= 100:
                self.err(f"solidez.umbrales.{nombre}", f"entero de 1 a 100, no {valor!r}")
            else:
                self.umbrales[nombre] = valor
        if len(set(self.umbrales.values())) != len(self.umbrales):
            self.err("solidez.umbrales", "los valores deben ser distintos")

    # -- 4 Personajes --

    def _personajes(self):
        p = self.d.get("personajes")
        if not isinstance(p, dict) or not 2 <= len(p) <= 5:
            self.err("personajes", "entre 2 y 5 personajes")
        if "fiscal" not in self.personajes:
            self.err("personajes", "falta 'fiscal' (recibe en la oficina y ante él se acusa)")
        for pid, per in self.personajes.items():
            d = f"personajes.{pid}"
            if not isinstance(per, dict):
                self.err(d, "debe ser un objeto")
                continue
            if not _texto(per.get("nombre")):
                self.err(d + ".nombre", "texto no vacío")
            if "rol" in per and not _texto(per["rol"]):
                self.err(d + ".rol", "texto no vacío")
            if per.get("modelo") not in MODELOS:
                self.err(d + ".modelo", f"uno de {MODELOS}")
            r = per.get("retrato")
            if not isinstance(r, dict):
                self.err(d + ".retrato", "falta el retrato")
                continue
            for color in ("piel", "pelo", "ropa"):
                c = r.get(color)
                if not (isinstance(c, list) and len(c) == 3 and all(_entero(x) and 0 <= x <= 255 for x in c)):
                    self.err(f"{d}.retrato.{color}", "[r, g, b] con enteros de 0 a 255")
            if r.get("pelo_estilo") not in PELO_ESTILOS:
                self.err(f"{d}.retrato.pelo_estilo", f"uno de {PELO_ESTILOS}")
            if r.get("accesorio") not in ACCESORIOS:
                self.err(f"{d}.retrato.accesorio", f"uno de {ACCESORIOS}")
            exp = r.get("expresiones")
            if not (isinstance(exp, list) and exp and all(e in EXPRESIONES for e in exp)):
                self.err(f"{d}.retrato.expresiones", f"lista no vacía de {EXPRESIONES}")

    # -- 5 Evidencias --

    def _evidencias(self):
        e = self.d.get("evidencias")
        if not isinstance(e, dict) or not e:
            self.err("evidencias", "objeto con al menos una prueba")
            return
        if len(e) > MAX_PRUEBAS:
            self.err("evidencias", f"como mucho {MAX_PRUEBAS} pruebas (hay {len(e)})")
        for eid, ev in e.items():
            d = f"evidencias.{eid}"
            if not _id_valido(eid):
                self.err(d, "id sin ':', '.', '/' ni espacios")
            if not isinstance(ev, dict):
                self.err(d, "debe ser un objeto")
                continue
            for clave, maximo in (("nombre", 28), ("descripcion", 160)):
                if not _texto(ev.get(clave)) or len(ev[clave]) > maximo:
                    self.err(f"{d}.{clave}", f"texto de 1 a {maximo} caracteres")
            if "solidez" in ev and (not _entero(ev["solidez"]) or not 0 <= ev["solidez"] <= 30):
                self.err(f"{d}.solidez", f"entero de 0 a 30, no {ev['solidez']!r}")

    def _prueba(self, donde, eid):
        if eid not in self.evidencias:
            self.err(donde, f"la prueba {eid!r} no está declarada en 'evidencias'", grave=True)
            return False
        return True

    # -- 6 Laboratorio --

    def _laboratorio(self):
        lab = self.d.get("laboratorio")
        nodos_lab = [i for i, n in self.nodos.items() if isinstance(n, dict) and n.get("tipo") == "laboratorio"]
        if lab is None:
            for i in nodos_lab:
                self.err(f"nodos.{i}", "hay un nodo 'laboratorio' pero el caso no tiene bloque 'laboratorio'")
            return
        if len(nodos_lab) != 1:
            self.err("laboratorio", f"con laboratorio el caso necesita exactamente un nodo 'laboratorio' "
                                    f"(hay {len(nodos_lab)})")
        parkours = lab.get("parkours") if isinstance(lab, dict) else None
        if not isinstance(parkours, list) or not 1 <= len(parkours) <= 2:
            self.err("laboratorio.parkours", "lista de 1 o 2 parkours", grave=True)
            return
        niveles, pruebas = set(), set()
        for i, p in enumerate(parkours):
            d = f"laboratorio.parkours[{i}]"
            if not isinstance(p, dict):
                self.err(d, "debe ser un objeto", grave=True)
                continue
            for clave in set(p) - {"nivel", "nombre", "descripcion", "evidencia"}:
                if not clave.startswith("_"):
                    self.err(d, f"clave desconocida {clave!r}")
            if p.get("nivel") not in self.niveles:
                self.err(d + ".nivel", f"nivel {p.get('nivel')!r} inexistente; hay {self.niveles}", grave=True)
            elif p["nivel"] in niveles:
                self.err(d + ".nivel", f"nivel {p['nivel']!r} repetido", grave=True)
            niveles.add(p.get("nivel"))
            for clave, maximo in (("nombre", 28), ("descripcion", 140)):
                if not _texto(p.get(clave)) or len(p[clave]) > maximo:
                    self.err(f"{d}.{clave}", f"texto de 1 a {maximo} caracteres")
            if self._prueba(d + ".evidencia", p.get("evidencia")):
                if p["evidencia"] in pruebas:
                    self.err(d + ".evidencia", "cada parkour debe dar una prueba distinta")
                pruebas.add(p["evidencia"])
                self.otorgadas_parkour.setdefault(p["evidencia"], []).append(d)

    # -- 7-9 Nodos --

    def _nodo(self, id_nodo, nodo):
        d = f"nodos.{id_nodo}"
        if not _texto(id_nodo) or ":" in id_nodo or " " in id_nodo or id_nodo.startswith("@"):
            self.err(d, "id inválido (sin ':', espacios ni '@' inicial)")
        if not isinstance(nodo, dict) or nodo.get("tipo") not in TIPOS_NODO:
            tipo = nodo.get("tipo") if isinstance(nodo, dict) else nodo
            self.err(d, f"'tipo' debe ser uno de {TIPOS_NODO}, no {tipo!r}", grave=True)
            return
        tipo = nodo["tipo"]
        for clave in nodo:
            if clave.startswith("_"):
                continue
            if clave in _OBSOLETAS:
                self.err(d, f"{clave!r} no existe en el formato v2")
            elif clave not in _CLAVES_NODO[tipo]:
                self.err(d, f"clave desconocida {clave!r} para un nodo {tipo}")
        if tipo == "final":
            if "escena" in nodo:
                self.err(d + ".escena", "un final no lleva escena")
        elif nodo.get("escena") not in ESCENAS:
            self.err(d + ".escena", f"una de {ESCENAS}, no {nodo.get('escena')!r}", grave=True)
        maximo = 260 if tipo == "final" else 220
        if not _texto(nodo.get("texto")) or len(nodo["texto"]) > maximo:
            self.err(d + ".texto", f"texto de 1 a {maximo} caracteres")
        self._personaje(d, nodo.get("personaje"), nodo.get("expresion"))
        if "plano" in nodo and nodo["plano"] not in PLANOS:
            self.err(d + ".plano", f"uno de {PLANOS}")
        if "hito" in nodo and (not _texto(nodo["hito"]) or len(nodo["hito"]) > 32):
            self.err(d + ".hito", "texto de 1 a 32 caracteres")
        self._delta(d + ".solidez", nodo, "solidez")
        if "efectos" in nodo:
            self._efectos(d + ".efectos", nodo["efectos"], permitir_grupos=tipo == "final")
        if tipo in ("dialogo", "laboratorio"):
            self._referencia(d + ".siguiente", nodo.get("siguiente"), permitir_volver=tipo == "dialogo")
        elif tipo == "rueda":
            self._rueda(d, id_nodo, nodo)
        elif tipo == "acusacion":
            self._acusacion(d, nodo)
        else:
            if nodo.get("resultado") not in RESULTADOS:
                self.err(d + ".resultado", f"uno de {RESULTADOS}", grave=True)
            if not _texto(nodo.get("titulo")) or len(nodo["titulo"]) > 32:
                self.err(d + ".titulo", "texto de 1 a 32 caracteres")

    def _personaje(self, d, pid, expresion):
        if pid is None:
            if expresion is not None:
                self.err(d + ".expresion", "el narrador no tiene expresión")
            return
        if pid not in self.personajes:
            self.err(d + ".personaje", f"personaje {pid!r} no está en 'personajes'")
            return
        if expresion is not None:
            declaradas = _dicts(_dicts(self.personajes[pid]).get("retrato")).get("expresiones") or []
            if expresion not in declaradas:
                self.err(d + ".expresion", f"expresión {expresion!r} no declarada para {pid!r}")

    def _delta(self, donde, contenedor, clave):
        if clave in contenedor:
            v = contenedor[clave]
            if not _entero(v) or not -30 <= v <= 30:
                self.err(donde, f"entero de -30 a 30, no {v!r}")

    def _referencia(self, donde, destino, permitir_volver=False):
        if destino == VOLVER:
            if not permitir_volver:
                self.err(donde, "«@volver» no se permite aquí", grave=True)
        elif not isinstance(destino, str) or destino not in self.nodos:
            self.err(donde, f"el nodo {destino!r} no existe", grave=True)

    def _referencia_final(self, donde, destino):
        self._referencia(donde, destino)
        n = self.nodos.get(destino) if isinstance(destino, str) else None
        if isinstance(n, dict) and n.get("tipo") != "final":
            self.err(donde, f"debe ser un nodo final ({destino!r} es {n.get('tipo')})")

    def _etiqueta(self, donde, etiqueta):
        if not _texto(etiqueta) or len(etiqueta) > 18 or not 1 <= len(etiqueta.split()) <= 3:
            self.err(donde, f"de 1 a 3 palabras y hasta 18 caracteres, no {etiqueta!r}")

    def _pista(self, donde, op):
        if "pista" in op:
            p = op["pista"]
            if not _texto(p) or len(p) > 24 or not (p.startswith("[") and p.endswith("]")):
                self.err(donde, f"entre corchetes y hasta 24 caracteres, no {p!r}")
        if "oculta" in op and not isinstance(op["oculta"], bool):
            self.err(donde.rsplit(".", 1)[0] + ".oculta", "true o false")

    def _rueda(self, d, id_nodo, nodo):
        opciones = nodo.get("opciones")
        if not isinstance(opciones, list) or not 2 <= len(opciones) <= MAX_OPCIONES:
            self.err(d + ".opciones", f"entre 2 y {MAX_OPCIONES} opciones (nunca más de {MAX_OPCIONES})",
                     grave=not isinstance(opciones, list))
            opciones = opciones if isinstance(opciones, list) else []
        ids = set()
        for i, op in enumerate(opciones):
            do = f"{d}.opciones[{i}]"
            if not isinstance(op, dict) or not _texto(op.get("id")):
                self.err(do, "necesita 'id'", grave=True)
                continue
            for clave in op:
                if not clave.startswith("_") and clave not in _CLAVES_OPCION:
                    self.err(do, f"clave desconocida {clave!r}")
            if op["id"] in ids or op["id"] == TERMINAR:
                self.err(do + ".id", f"id repetido o reservado {op['id']!r}")
            ids.add(op["id"])
            self._etiqueta(do + ".etiqueta", op.get("etiqueta"))
            if "dice" in op and (not _texto(op["dice"]) or len(op["dice"]) > 120):
                self.err(do + ".dice", "texto de 1 a 120 caracteres")
            self._referencia(do + ".destino", op.get("destino"))
            self._pista(do + ".pista", op)
            if "una_vez" in op and not isinstance(op["una_vez"], bool):
                self.err(do + ".una_vez", "true o false")
            self._delta(do + ".solidez", op, "solidez")
            if "requiere" in op:
                self._condicion(do + ".requiere", op["requiere"])
            if "efectos" in op:
                self._efectos(do + ".efectos", op["efectos"], permitir_grupos=False)
            if "presenta" in op:
                self._prueba(do + ".presenta", op["presenta"])
                if op["presenta"] not in (_dicts(op.get("requiere")).get("evidencia") or []):
                    self.err(do + ".presenta", "la prueba que presenta debe estar en 'requiere.evidencia'")
        validas = [o for o in opciones if isinstance(o, dict)]
        self._reloj(d, nodo, validas, por_defecto_valido=lambda o: not o.get("requiere") and o.get("una_vez") is False)
        if "turnos" in nodo and (not _entero(nodo["turnos"]) or nodo["turnos"] < 1):
            self.err(d + ".turnos", f"entero >= 1, no {nodo['turnos']!r}")
        vuelve = any(diagrama_caso.cadena_que_vuelve(self.nodos, o.get("destino")) for o in validas)
        hace_falta = "turnos" in nodo or _dicts(nodo.get("reloj")).get("por_defecto") == TERMINAR or vuelve
        if nodo.get("al_terminar") is not None:
            self._referencia(d + ".al_terminar", nodo["al_terminar"])
        elif hace_falta:
            self.err(d + ".al_terminar", "obligatorio: la rueda tiene turnos, termina por reloj o alguna opción "
                                         "regresa con «@volver»")
        elif not any(not o.get("requiere") for o in validas):
            self.err(d, "una rueda sin 'al_terminar' necesita al menos una opción sin 'requiere'")

    def _reloj(self, d, nodo, opciones, por_defecto_valido):
        reloj = nodo.get("reloj")
        if reloj is None:
            return
        dr = d + ".reloj"
        if not isinstance(reloj, dict):
            self.err(dr, "objeto {segundos, por_defecto}")
            return
        for clave in reloj:
            if not clave.startswith("_") and clave not in ("segundos", "por_defecto"):
                self.err(dr, f"clave desconocida {clave!r}")
        if nodo["tipo"] == "rueda" and nodo.get("escena") != "sala":
            self.err(dr, "el reloj solo va en la escena 'sala' (y en la acusación)")
        if not _numero(reloj.get("segundos")) or not 6 <= reloj["segundos"] <= 60:
            self.err(dr + ".segundos", f"entre 6 y 60, no {reloj.get('segundos')!r}")
        defecto = reloj.get("por_defecto")
        if defecto == TERMINAR and nodo["tipo"] == "rueda":
            return
        opcion = next((o for o in opciones if o.get("id") == defecto), None)
        if opcion is None or not por_defecto_valido(opcion):
            regla = ("una opción sin 'requiere' y con 'una_vez': false, o «@terminar»" if nodo["tipo"] == "rueda"
                     else "un acusado sin 'requiere'")
            self.err(dr + ".por_defecto", f"debe ser {regla}; no {defecto!r}", grave=opcion is None)

    def _acusacion(self, d, nodo):
        if nodo.get("escena") != "oficina":
            self.err(d + ".escena", "la acusación va en la escena 'oficina'")
        acusados = nodo.get("acusados")
        if not isinstance(acusados, list) or not 2 <= len(acusados) <= 4:
            self.err(d + ".acusados", "entre 2 y 4 acusados", grave=not isinstance(acusados, list))
            acusados = acusados if isinstance(acusados, list) else []
        ids = set()
        for i, ac in enumerate(acusados):
            da = f"{d}.acusados[{i}]"
            if not isinstance(ac, dict) or not _texto(ac.get("id")):
                self.err(da, "necesita 'id'", grave=True)
                continue
            for clave in ac:
                if not clave.startswith("_") and clave not in _CLAVES_ACUSADO:
                    self.err(da, f"clave desconocida {clave!r}")
            if ac["id"] in ids:
                self.err(da + ".id", f"id repetido {ac['id']!r}")
            ids.add(ac["id"])
            self._etiqueta(da + ".etiqueta", ac.get("etiqueta"))
            if ac.get("personaje") is not None and ac["personaje"] not in self.personajes:
                self.err(da + ".personaje", f"personaje {ac['personaje']!r} no está en 'personajes'")
            self._pista(da + ".pista", ac)
            if "requiere" in ac:
                self._condicion(da + ".requiere", ac["requiere"])
            rutas = ac.get("rutas")
            if rutas is not None:
                if not isinstance(rutas, list) or not rutas:
                    self.err(da + ".rutas", "lista no vacía de {requiere, destino}", grave=True)
                    rutas = []
                for j, ruta in enumerate(rutas):
                    dj = f"{da}.rutas[{j}]"
                    if not isinstance(ruta, dict):
                        self.err(dj, "objeto {requiere, destino}", grave=True)
                        continue
                    for clave in ruta:
                        if not clave.startswith("_") and clave not in ("requiere", "destino"):
                            self.err(dj, f"clave desconocida {clave!r}")
                    self._condicion(dj + ".requiere", ruta.get("requiere") or {})
                    self._referencia_final(dj + ".destino", ruta.get("destino"))
            self._referencia_final(da + ".destino", ac.get("destino"))
        self._reloj(d, nodo, [a for a in acusados if isinstance(a, dict)],
                    por_defecto_valido=lambda a: not a.get("requiere"))

    # -- 11 Condiciones y efectos --

    def _lista_textos(self, donde, valor):
        if not isinstance(valor, list) or not all(_texto(x) for x in valor):
            self.err(donde, "lista de textos", grave=True)
            return []
        return valor

    def _condicion(self, donde, cond):
        if not isinstance(cond, dict):
            self.err(donde, "debe ser un objeto", grave=True)
            return
        for clave in cond:
            if not clave.startswith("_") and clave not in _CLAVES_CONDICION:
                self.err(donde, f"clave desconocida {clave!r}; válidas: {sorted(_CLAVES_CONDICION)}", grave=True)
        for clave in ("evidencia", "alguna_evidencia", "sin_evidencia"):
            if clave in cond:
                for eid in self._lista_textos(f"{donde}.{clave}", cond[clave]):
                    self._prueba(f"{donde}.{clave}", eid)
        for clave in ("marcas", "sin_marcas"):
            if clave in cond:
                self.marcas.update(self._lista_textos(f"{donde}.{clave}", cond[clave]))
        for clave in ("visitado", "no_visitado"):
            if clave in cond:
                for nid in self._lista_textos(f"{donde}.{clave}", cond[clave]):
                    if nid not in self.nodos:
                        self.err(f"{donde}.{clave}", f"el nodo {nid!r} no existe", grave=True)
        if "solidez" in cond:
            rango = cond["solidez"]
            if not isinstance(rango, dict) or not rango or set(rango) - {"min", "max"}:
                self.err(f"{donde}.solidez", "objeto {min, max}", grave=True)
                return
            for k, v in rango.items():
                if isinstance(v, str):
                    if v not in self.umbrales:
                        self.err(f"{donde}.solidez", f"umbral {v!r} inexistente; hay {sorted(self.umbrales)}",
                                 grave=True)
                elif not _entero(v) or not 0 <= v <= 100:
                    self.err(f"{donde}.solidez", f"'{k}' debe ser un entero 0-100 o el nombre de un umbral", grave=True)

    def _efectos(self, donde, efectos, permitir_grupos):
        if not isinstance(efectos, dict):
            self.err(donde, "debe ser un objeto", grave=True)
            return
        for clave in efectos:
            if clave.startswith("_"):
                continue
            if clave not in _CLAVES_EFECTOS:
                self.err(donde, f"clave desconocida {clave!r}; válidas: {sorted(_CLAVES_EFECTOS)}")
        if "da_evidencia" in efectos:
            for eid in self._lista_textos(donde + ".da_evidencia", efectos["da_evidencia"]):
                if self._prueba(donde + ".da_evidencia", eid):
                    self.otorgadas_efecto.setdefault(eid, []).append(donde)
        if "marcas" in efectos:
            self.marcas.update(self._lista_textos(donde + ".marcas", efectos["marcas"]))
        if "grupos" in efectos:
            if not permitir_grupos:
                self.err(donde + ".grupos", "la confianza de los grupos solo cambia en los nodos 'final'")
            grupos = efectos["grupos"]
            if not isinstance(grupos, dict):
                self.err(donde + ".grupos", "objeto {grupo: {componente: número}}")
                return
            for grupo, comp in grupos.items():
                if grupo not in GRUPOS:
                    self.err(donde + ".grupos", f"grupo {grupo!r} inexistente; usa {GRUPOS}")
                elif not isinstance(comp, dict) or any(k not in COMPONENTES or not _numero(v) for k, v in comp.items()):
                    self.err(f"{donde}.grupos.{grupo}", f"solo {COMPONENTES} con números")

    # -- 5, 8-10 y límites: lo que mira el caso entero --

    def _conjunto(self):
        tipos = {i: n.get("tipo") for i, n in self.nodos.items() if isinstance(n, dict)}
        acusaciones = [i for i, t in tipos.items() if t == "acusacion"]
        if len(acusaciones) != 1:
            self.err("nodos", f"debe haber exactamente un nodo 'acusacion' (hay {len(acusaciones)})")
        finales = [i for i, t in tipos.items() if t == "final"]
        if not 3 <= len(finales) <= 6:
            self.err("nodos", f"entre 3 y 6 finales (hay {len(finales)})")
        resultados = {self.nodos[i].get("resultado") for i in finales}
        for r in RESULTADOS:
            if r not in resultados:
                self.err("nodos", f"falta un final con resultado {r!r}")
        inicio, abandono = self.d.get("inicio"), self.d.get("final_abandono")
        if _texto(inicio) and inicio not in self.nodos:
            self.err("inicio", f"el nodo {inicio!r} no existe", grave=True)
        if _texto(abandono):
            if tipos.get(abandono) != "final" or self.nodos[abandono].get("resultado") != "fracaso":
                self.err("final_abandono", f"debe ser un nodo final con resultado 'fracaso', no {abandono!r}",
                         grave=abandono not in self.nodos)
        for eid in self.evidencias:
            parkour, efecto = self.otorgadas_parkour.get(eid), self.otorgadas_efecto.get(eid)
            if not parkour and not efecto:
                self.err(f"evidencias.{eid}", "ninguna cosa del caso la otorga (ni un parkour ni un 'da_evidencia')")
            elif parkour and efecto:
                self.err(f"evidencias.{eid}", f"la otorgan a la vez un parkour y un 'da_evidencia' ({efecto[0]})")
        if len(self.marcas) > MAX_MARCAS:
            self.err("nodos", f"como mucho {MAX_MARCAS} marcas distintas (hay {len(self.marcas)})")
        con_volver = [i for i, n in self.nodos.items() if isinstance(n, dict) and n.get("tipo") == "rueda"
                      and any(diagrama_caso.cadena_que_vuelve(self.nodos, o.get("destino")) for o in _opciones(n))]
        if len(con_volver) > MAX_RUEDAS_VOLVER:
            self.err("nodos", f"como mucho {MAX_RUEDAS_VOLVER} ruedas con «@volver» (hay {len(con_volver)})")
        hitos = sum(1 for n in self.nodos.values() if isinstance(n, dict) and (n.get("hito") or n.get("tipo") == "final"))
        if not HITOS_MIN <= hitos <= HITOS_MAX:
            self.avisos.append(f"nodos: se recomiendan entre {HITOS_MIN} y {HITOS_MAX} hitos contando finales "
                               f"(hay {hitos})")

    # -- 12-13 Grafo --

    def _grafo(self):
        grafo = diagrama_caso.aristas(self.nodos)
        ciclo = diagrama_caso.buscar_ciclo(grafo)
        if ciclo:
            self.err("nodos", "ciclo en el grafo (debe ser acíclico): " + " -> ".join(ciclo), grave=True)
            return
        inicio = self.d["inicio"]
        for i in diagrama_caso.inalcanzables(grafo, inicio):
            self.err(f"nodos.{i}", "no es alcanzable desde 'inicio' por las aristas")
        # «@volver» solo detrás de una elección en una rueda: lo que se alcanza sin elegir (desde el inicio o desde un
        # al_terminar) no puede volver.
        sin_eleccion = {i: [d for d in ([n.get("siguiente")] if n["tipo"] in ("dialogo", "laboratorio")
                                        else [n.get("al_terminar")] if n["tipo"] == "rueda" else salidas_de(n))
                            if d in self.nodos] for i, n in self.nodos.items()}
        semillas = [inicio] + [n["al_terminar"] for n in self.nodos.values()
                               if n["tipo"] == "rueda" and n.get("al_terminar") in self.nodos]
        sin_rueda = set()
        for s in semillas:
            sin_rueda |= diagrama_caso.alcanzables(sin_eleccion, s)
        for i in self.nodos:
            if i in sin_rueda and self.nodos[i].get("siguiente") == VOLVER:
                self.err(f"nodos.{i}", "usa «@volver» pero se puede llegar sin elegir antes en una rueda")
        # Desde todo nodo se llega a un final (las respuestas con «@volver» siguen por su rueda).
        extendido = {i: list(d) for i, d in grafo.items()}
        for i, n in self.nodos.items():
            if n["tipo"] == "rueda":
                for o in _opciones(n):
                    que_vuelve = diagrama_caso.cadena_que_vuelve(self.nodos, o.get("destino"))
                    if que_vuelve:
                        extendido[que_vuelve].append(i)
        llegan = set()
        for f in (i for i, n in self.nodos.items() if n["tipo"] == "final"):
            llegan.add(f)
        inverso = {i: [] for i in self.nodos}
        for u, destinos in extendido.items():
            for v in destinos:
                inverso[v].append(u)
        pila = list(llegan)
        while pila:
            for u in inverso[pila.pop()]:
                if u not in llegan:
                    llegan.add(u)
                    pila.append(u)
        for i in self.nodos:
            if i not in llegan:
                self.err(f"nodos.{i}", "desde aquí no se llega a ningún final")
        self._escenas(grafo)

    def _escenas(self, grafo):
        inicio = self.d["inicio"]
        if self.nodos[inicio].get("escena") != "oficina":
            self.err("inicio", "el primer nodo debe estar en la escena 'oficina'")
            return
        # Fases: 0 oficina (antes) · 1 laboratorio · 2 sala · 3 oficina (después de la sala).
        def pasar(fase, escena):
            if escena == "oficina":
                return {0: 0, 2: 3, 3: 3}.get(fase)
            if escena == "laboratorio":
                return {0: 1, 1: 1}.get(fase)
            return {0: 2, 1: 2, 2: 2}.get(fase)
        fases = {i: set() for i in self.nodos}
        fases[inicio].add(0)
        avisados = set()
        for u in diagrama_caso.orden_topologico(grafo):
            for v in grafo[u]:
                destino = self.nodos[v]
                if destino["tipo"] == "final":
                    continue
                for fase in fases[u]:
                    nueva = pasar(fase, destino.get("escena"))
                    if nueva is None:
                        if (u, v) not in avisados:
                            avisados.add((u, v))
                            nombre = ("oficina", "laboratorio", "sala", "oficina")[fase]
                            self.err(f"nodos.{u}", f"la escena no puede pasar de '{nombre}' a '{destino.get('escena')}'"
                                                   f" (hacia {v!r}); orden: oficina -> laboratorio -> sala -> oficina")
                    else:
                        fases[v].add(nueva)

    # -- 14 Recorrido real --

    def _recorrido(self):
        try:
            analisis = _analizar_datos(self.d, self.tope)
        except (CasoError, KeyError, TypeError, ValueError) as error:
            self.err("recorrido", f"no se pudo jugar el caso: {error}")
            return
        self.avisos.extend(analisis["avisos"])
        combos = analisis["combinaciones"]
        if not all(c["completo"] for c in combos.values()):
            return
        ya = {e.split(":")[0] for e in self.errores}
        for i in self.nodos:
            if i not in analisis["alcanzados"] and f"nodos.{i}" not in ya:
                self.err(f"nodos.{i}", "no es alcanzable jugando (sus 'requiere' nunca se cumplen) con ningún número "
                                       "de parkours")
        for combo, estados in analisis["sin_salida"].items():
            vistos = set()
            for e in estados:
                if e.nodo not in vistos:
                    vistos.add(e.nodo)
                    self.err(f"nodos.{e.nodo}", f"estado sin salida jugando ({_nombre_combo(combo)}, solidez "
                                                f"{e.solidez}): no queda nada que elegir o no se llega a un final")
        for combo, errores in analisis["errores_juego"].items():
            for e, mensaje in errores[:3]:
                self.err(f"nodos.{e.nodo}", f"al jugar ({_nombre_combo(combo)}): {mensaje}")
        if analisis["con_laboratorio"]:
            self._tabla(analisis)

    def _tabla(self, analisis):
        combos = analisis["combinaciones"]
        mejores = analisis["mejores"]
        exito = {i for i, n in self.nodos.items() if n["tipo"] == "final" and n["resultado"] == "exito"}
        parcial = {i for i, n in self.nodos.items() if n["tipo"] == "final" and n["resultado"] == "parcial"}
        todos = max(combos, key=len)
        if not mejores:
            self.err("solidez", "(§5) el caso no tiene un final de resultado 'exito'")
        elif not set(combos[todos]["finales"]) & set(mejores):
            self.err("solidez", f"(§5) con {_nombre_combo(todos)} el mejor final ({', '.join(mejores)}) debe ser "
                                f"alcanzable; la solidez máxima es {combos[todos]['solidez_max']}")
        for combo, info in combos.items():
            if len(combo) == 1 and combo != todos:
                alcanzados = set(info["finales"])
                if alcanzados & set(mejores):
                    self.err("solidez", f"(§5) con {_nombre_combo(combo)} se alcanza "
                                        f"{', '.join(sorted(alcanzados & set(mejores)))}, el mejor final: debe hacer "
                                        f"falta {_nombre_combo(todos)}")
                if not alcanzados & (exito | parcial):
                    self.err("solidez", f"(§5) con {_nombre_combo(combo)} no se alcanza ningún final 'exito' ni "
                                        f"'parcial' (solidez máxima {info['solidez_max']})")
        sin = combos.get(())
        if sin is not None and set(sin["finales"]) & exito:
            self.err("solidez", f"(§5) con 0 parkours se alcanza {', '.join(sorted(set(sin['finales']) & exito))} "
                                f"(exito); como mucho debe ser 'parcial' (solidez máxima {sin['solidez_max']})")


def salidas_de(nodo):
    return diagrama_caso.salidas(nodo)


def validar(datos, niveles_validos=None, avisos=None, tope_estados=TOPE_ESTADOS):
    """Lista de errores del caso v2 (vacía = válido), cada uno con su ruta en el JSON. Nunca lanza por contenido.
    `niveles_validos`: ids de los niveles de parkour que existen (None = sector_1 y sector_2). `avisos`: lista opcional
    donde se añaden los avisos (tope de estados superado, número de hitos fuera de lo recomendado)."""
    if not isinstance(datos, dict):
        return ["el caso debe ser un objeto JSON"]
    try:
        v = _Validador(datos, niveles_validos, tope_estados)
        errores = v.ejecutar()
    except (AttributeError, TypeError, KeyError, ValueError) as error:     # estructura demasiado rota
        return [f"estructura inválida ({type(error).__name__}: {error})"]
    if avisos is not None:
        avisos.extend(v.avisos)
    return errores
