# Motor de casos de investigación (modelo puro, sin motor gráfico). Un caso es un DAG de nodos descrito en JSON
# (backend/datos/casos/*.json, cargado por backend/datos/casos_loader.py): diálogos, menús de preguntas, acusación
# y finales. No hay texto ni reglas del caso en el código: todo sale del JSON.
#
# Tipos de nodo:
#   dialogo    texto + `siguiente`. Avanza con continuar().
#   menu       `preguntas` (opciones). Pueden estar bloqueadas por `requiere` (evidencia, flags, confianza...) o
#              agotadas (`una_vez`, por defecto True). Si el nodo trae `contradicciones`, el jugador también puede
#              PRESENTAR una prueba: la correcta abre su `destino`; una equivocada cuenta como error (`error`).
#   acusacion  `acusados` (opciones); cada una elige su final con `rutas` (la primera cuyo `requiere` se cumple) o
#              su `destino` de respaldo. Aquí se puede acertar o fallar.
#   final      `resultado` exito | parcial | fracaso. Cierra el caso y deja el rastro para el Archivo de casos.
#
# DAG: las aristas son `siguiente`, `destino` de opciones/rutas/contradicciones/error y `fin_por_errores.destino`.
# El destino especial «@volver» regresa al menú desde el que se eligió la última opción (así las respuestas no
# crean ciclos): no cuenta como arista. validar() exige: sin ciclos, todo nodo alcanzable, referencias existentes,
# y un menú siempre con una salida. Los errores se juntan TODOS en un solo CasoError con la ruta dentro del JSON.
#
# Temporizador (`temporizador`: {segundos, por_defecto}): solo vale para UNA pregunta. Al agotarse se elige sola la
# opción por defecto (avanzar_tiempo). El tiempo no entra en la fórmula de confianza: GameState solo recibe los
# componentes investigación / moral / secundarios de los `efectos` de la decisión.
#
# Evidencia: se lee SOLO por backend/logica/evidencia.py (flag «evidencia:<id>»); el caso también puede otorgarla
# (`da_evidencia`). Efectos de una decisión -> GameState.aplicar_evento:
#   {"tipo": "...", "grupos": {grupo: {investigacion, moral, secundarios}}, "relaciones": {npc: delta},
#    "flags": ["nombre" | ["nombre", permanente]], "da_evidencia": ["id"]}
# Las relaciones de NPC que el GameState no lleva se descartan con un aviso en el registro (la lista de NPC clave vive en
# backend/datos/npc_clave.json): así un id mal escrito en el JSON no pasa inadvertido.
#
# Rastro para el Archivo de casos (flags permanentes del GameState, se guardan con él):
#   caso:<id>:jugado · caso:<id>:final:<nodo> · caso:<id>:resultado:<res> · caso:<id>:acusado:<opcion>

import logging
import math
from dataclasses import dataclass

from backend.logica import evidencia
from backend.logica.game_state import GRUPOS, RELACION_INICIAL

VOLVER = "@volver"
TIPOS_NODO = ("dialogo", "menu", "acusacion", "final")
RESULTADOS = ("exito", "parcial", "fracaso")
CLAVE_OPCIONES = {"menu": "preguntas", "acusacion": "acusados"}
COMPONENTES = ("investigacion", "moral", "secundarios")
PREFIJO_FLAG = "caso:"

_CLAVES_EFECTOS = ("tipo", "grupos", "relaciones", "flags", "da_evidencia")
_CLAVES_CONDICION = ("evidencia", "alguna_evidencia", "flags", "sin_flags", "confianza", "relacion",
                     "visitado", "no_visitado")
MOTIVO_AGOTADA = "Ya la preguntaste."
MOTIVO_BLOQUEADA = "Te falta una prueba o un dato."


_registro = logging.getLogger(__name__)


class CasoError(ValueError):
    pass


def _texto(v):
    return isinstance(v, str) and v.strip() != ""


def _numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# -- Estructura del caso (acceso al dict del JSON) --

def opciones_de(nodo):
    return nodo.get(CLAVE_OPCIONES.get(nodo.get("tipo"), ""), []) or []


# Destinos concretos (sin «@volver») a los que puede ir un nodo; `fin_por_errores` cuenta si el nodo admite errores.
def destinos_de(nodo, fin_por_errores=None):
    destinos = [nodo.get("siguiente")]
    for opcion in opciones_de(nodo):
        destinos.append(opcion.get("destino"))
        destinos.extend(ruta.get("destino") for ruta in opcion.get("rutas", []) or [])
    contradicciones = nodo.get("contradicciones", []) or []
    destinos.extend(c.get("destino") for c in contradicciones)
    if contradicciones:
        destinos.append((nodo.get("error") or {}).get("destino"))
        if fin_por_errores:
            destinos.append(fin_por_errores.get("destino"))
    return [d for d in destinos if isinstance(d, str) and d != VOLVER]


def _usa_volver(nodo):
    candidatos = [nodo.get("siguiente")]
    for opcion in opciones_de(nodo):
        candidatos.append(opcion.get("destino"))
        candidatos.extend(r.get("destino") for r in opcion.get("rutas", []) or [])
    candidatos.extend(c.get("destino") for c in nodo.get("contradicciones", []) or [])
    candidatos.append((nodo.get("error") or {}).get("destino"))
    return VOLVER in candidatos


class Caso:

    def __init__(self, datos):
        self.id = datos["id"]
        self.titulo = datos["titulo"]
        self.resumen = datos.get("resumen", "")
        self.inicio = datos["inicio"]
        self.rejugable = bool(datos.get("rejugable", False))
        self.personajes = datos.get("personajes", {})
        self.evidencias = datos.get("evidencias", {})
        self.nodos = datos["nodos"]
        self.fin_por_errores = datos.get("fin_por_errores")
        self.terminal = datos.get("terminal")        # {"nombre", "ancla"}: dónde está el computador del caso (opcional)
        self.datos = datos

    @classmethod
    def desde_dict(cls, datos):
        errores = validar(datos)
        if errores:
            ident = datos.get("id", "?") if isinstance(datos, dict) else "?"
            raise CasoError(f"Caso {ident!r} inválido ({len(errores)} error(es)):\n- " + "\n- ".join(errores))
        return cls(datos)

    def nodo(self, id_nodo):
        return self.nodos[id_nodo]

    def finales(self):
        return [i for i, n in self.nodos.items() if n["tipo"] == "final"]

    def nombre_evidencia(self, id_evidencia):
        return self.evidencias.get(id_evidencia, {}).get("nombre", id_evidencia)

    def nombre_personaje(self, id_personaje):
        return self.personajes.get(id_personaje, {}).get("nombre", id_personaje or "Narrador")

    def __repr__(self):
        return f"Caso({self.id!r}, nodos={len(self.nodos)}, finales={len(self.finales())})"


# -- Validación --

class _Validador:

    def __init__(self, datos):
        self.d = datos
        self.errores = []
        self.nodos = datos.get("nodos") if isinstance(datos.get("nodos"), dict) else {}
        self.evidencias = datos.get("evidencias") if isinstance(datos.get("evidencias"), dict) else {}
        self.personajes = datos.get("personajes") if isinstance(datos.get("personajes"), dict) else {}

    def err(self, donde, mensaje):
        self.errores.append(f"{donde}: {mensaje}")

    def ejecutar(self):
        d = self.d
        for clave in ("id", "titulo", "inicio"):
            if not _texto(d.get(clave)):
                self.err(clave, "falta o no es un texto no vacío")
        if _texto(d.get("id")) and (":" in d["id"] or " " in d["id"]):
            self.err("id", "no puede llevar ':' ni espacios (se usa en los flags del Archivo)")
        if not self.nodos:
            self.err("nodos", "debe ser un objeto con al menos un nodo")
            return self.errores
        self._catalogos()
        if d.get("inicio") not in self.nodos:
            self.err("inicio", f"el nodo {d.get('inicio')!r} no existe")
        for id_nodo, nodo in self.nodos.items():
            self._nodo(id_nodo, nodo)
        self._fin_por_errores()
        self._terminal()
        if not self.errores:
            self._grafo()
        return self.errores

    def _catalogos(self):
        for pid, p in self.personajes.items():
            if not isinstance(p, dict) or not _texto(p.get("nombre")):
                self.err(f"personajes.{pid}", "necesita 'nombre'")
                continue
            retrato = p.get("retrato")
            exp = retrato.get("expresiones") if isinstance(retrato, dict) else None
            if not (isinstance(exp, list) and exp and all(_texto(e) for e in exp)):
                self.err(f"personajes.{pid}.retrato.expresiones", "lista no vacía de nombres de expresión")
        for eid, e in self.evidencias.items():
            if ":" in str(eid) or not isinstance(e, dict) or not _texto(e.get("nombre")):
                self.err(f"evidencias.{eid}", "id sin ':' y con 'nombre'")

    def _nodo(self, id_nodo, nodo):
        donde = f"nodos.{id_nodo}"
        if ":" in id_nodo or " " in id_nodo or id_nodo.startswith("@"):
            self.err(donde, "id inválido (sin ':', espacios ni '@' inicial)")
        if not isinstance(nodo, dict) or nodo.get("tipo") not in TIPOS_NODO:
            self.err(donde, f"'tipo' debe ser uno de {TIPOS_NODO}, no {nodo.get('tipo') if isinstance(nodo, dict) else nodo!r}")
            return
        tipo = nodo["tipo"]
        if not _texto(nodo.get("texto")):
            self.err(donde, "falta 'texto'")
        self._personaje(donde, nodo)
        if "efectos" in nodo:
            self._efectos(f"{donde}.efectos", nodo["efectos"])
        if tipo == "final":
            if nodo.get("resultado") not in RESULTADOS:
                self.err(donde, f"'resultado' debe ser uno de {RESULTADOS}, no {nodo.get('resultado')!r}")
            if not _texto(nodo.get("titulo")):
                self.err(donde, "un final necesita 'titulo'")
            return
        if tipo == "dialogo":
            self._referencia(donde + ".siguiente", nodo.get("siguiente"), permitir_volver=True)
            return
        self._opciones(donde, nodo, tipo)
        self._contradicciones(donde, nodo, tipo)
        self._temporizador(donde, nodo, tipo)

    def _personaje(self, donde, nodo):
        pid = nodo.get("personaje")
        if pid is None:
            return
        if pid not in self.personajes:
            self.err(donde, f"personaje {pid!r} no está en 'personajes'")
            return
        exp = nodo.get("expresion")
        if exp is not None and exp not in self.personajes[pid].get("retrato", {}).get("expresiones", []):
            self.err(donde, f"expresión {exp!r} no declarada para {pid!r}")

    def _referencia(self, donde, destino, permitir_volver=False, obligatoria=True):
        if destino is None:
            if obligatoria:
                self.err(donde, "falta el destino")
        elif destino == VOLVER:
            if not permitir_volver:
                self.err(donde, "«@volver» no se permite aquí")
        elif destino not in self.nodos:
            self.err(donde, f"el nodo {destino!r} no existe")

    def _opciones(self, donde, nodo, tipo):
        clave = CLAVE_OPCIONES[tipo]
        opciones = nodo.get(clave)
        if not (isinstance(opciones, list) and opciones):
            self.err(f"{donde}.{clave}", "lista no vacía de opciones")
            return
        ids = set()
        for i, op in enumerate(opciones):
            d = f"{donde}.{clave}[{i}]"
            if not isinstance(op, dict) or not _texto(op.get("id")) or not _texto(op.get("texto")):
                self.err(d, "necesita 'id' y 'texto'")
                continue
            if op["id"] in ids:
                self.err(d, f"id repetido {op['id']!r}")
            ids.add(op["id"])
            if "requiere" in op:
                self._condicion(d + ".requiere", op["requiere"])
            if "efectos" in op:
                self._efectos(d + ".efectos", op["efectos"])
            rutas = op.get("rutas")
            if rutas is not None:
                if not isinstance(rutas, list) or not rutas:
                    self.err(d + ".rutas", "lista no vacía")
                    rutas = []
                for j, ruta in enumerate(rutas):
                    self._condicion(f"{d}.rutas[{j}].requiere", ruta.get("requiere"))
                    self._referencia(f"{d}.rutas[{j}].destino", ruta.get("destino"), permitir_volver=True)
                    if "efectos" in ruta:
                        self._efectos(f"{d}.rutas[{j}].efectos", ruta["efectos"])
                self._referencia(d + ".destino", op.get("destino"), permitir_volver=True, obligatoria=False)
                if op.get("destino") is None:
                    self.err(d, "con 'rutas' hace falta un 'destino' de respaldo")
            else:
                self._referencia(d + ".destino", op.get("destino"), permitir_volver=True)
        if tipo == "menu":
            for op in opciones:
                if isinstance(op, dict) and VOLVER in [op.get("destino")] + [r.get("destino") for r in op.get("rutas") or []]:
                    self.err(f"{donde}.preguntas.{op.get('id')}", "una pregunta del menú no puede ir a «@volver» (usa un nodo de respuesta)")
        if tipo == "menu" and not any(self._es_salida(op) for op in opciones if isinstance(op, dict)):
            self.err(donde, "un menú necesita una opción de salida (sin 'requiere' y con 'una_vez': false)")

    @staticmethod
    def _es_salida(op):
        return not op.get("requiere") and op.get("una_vez", True) is False

    def _contradicciones(self, donde, nodo, tipo):
        contradicciones = nodo.get("contradicciones")
        if contradicciones is None:
            return
        if tipo != "menu" or not isinstance(contradicciones, list) or not contradicciones:
            self.err(donde + ".contradicciones", "solo en menús y como lista no vacía")
            return
        vistas = set()
        for i, c in enumerate(contradicciones):
            d = f"{donde}.contradicciones[{i}]"
            if c.get("evidencia") not in self.evidencias:
                self.err(d, f"evidencia {c.get('evidencia')!r} no declarada en 'evidencias'")
            elif c["evidencia"] in vistas:
                self.err(d, "evidencia repetida en el mismo nodo")
            vistas.add(c.get("evidencia"))
            self._referencia(d + ".destino", c.get("destino"), permitir_volver=True)
            if "efectos" in c:
                self._efectos(d + ".efectos", c["efectos"])
        error = nodo.get("error")
        if error is not None:
            self._referencia(donde + ".error.destino", error.get("destino"), permitir_volver=True, obligatoria=False)
            if "efectos" in error:
                self._efectos(donde + ".error.efectos", error["efectos"])

    def _temporizador(self, donde, nodo, tipo):
        t = nodo.get("temporizador")
        if t is None:
            return
        d = donde + ".temporizador"
        if not isinstance(t, dict) or not _numero(t.get("segundos")) or t["segundos"] <= 0:
            self.err(d, "necesita 'segundos' > 0")
            return
        defecto = next((o for o in opciones_de(nodo) if isinstance(o, dict) and o.get("id") == t.get("por_defecto")), None)
        if defecto is None:
            self.err(d, f"'por_defecto' {t.get('por_defecto')!r} no es una opción del nodo")
            return
        if defecto.get("requiere"):
            self.err(d, "la opción por defecto no puede tener 'requiere' (siempre debe poder elegirse)")
        if tipo == "menu" and defecto.get("una_vez", True) is not False:
            self.err(d, "la opción por defecto de un menú debe llevar 'una_vez': false")
        if _usa_volver({"siguiente": None, "preguntas": [defecto], "tipo": "menu"}):
            self.err(d, "la opción por defecto debe avanzar (no puede ir a «@volver»)")

    def _terminal(self):
        t = self.d.get("terminal")
        if t is None:
            return
        ancla = t.get("ancla") if isinstance(t, dict) else None
        if not _texto(t.get("nombre") if isinstance(t, dict) else None) or not isinstance(ancla, dict)                 or ("zona" in ancla) == ("lugar" in ancla):
            self.err("terminal", "necesita 'nombre' y un 'ancla' con 'zona' o 'lugar' (solo uno), como los comercios")

    def _fin_por_errores(self):
        f = self.d.get("fin_por_errores")
        if f is None:
            return
        if not isinstance(f, dict) or not isinstance(f.get("max"), int) or isinstance(f.get("max"), bool) or f["max"] < 1:
            self.err("fin_por_errores", "necesita 'max' entero >= 1")
        elif f.get("destino") not in self.nodos or self.nodos[f["destino"]].get("tipo") != "final":
            self.err("fin_por_errores.destino", "debe ser un nodo final existente")

    def _efectos(self, donde, efectos):
        if not isinstance(efectos, dict):
            self.err(donde, "debe ser un objeto")
            return
        for clave in efectos:
            if clave not in _CLAVES_EFECTOS:
                self.err(donde, f"clave desconocida {clave!r}; válidas: {_CLAVES_EFECTOS}")
        if "tipo" in efectos and not _texto(efectos["tipo"]):
            self.err(donde + ".tipo", "texto no vacío")
        for grupo, comp in (efectos.get("grupos") or {}).items():
            if grupo not in GRUPOS:
                self.err(f"{donde}.grupos", f"grupo {grupo!r} inexistente; usa {GRUPOS}")
            elif not isinstance(comp, dict) or any(k not in COMPONENTES or not _numero(v) for k, v in comp.items()):
                self.err(f"{donde}.grupos.{grupo}", f"solo {COMPONENTES} con números")
        for npc, delta in (efectos.get("relaciones") or {}).items():
            if not _numero(delta):
                self.err(f"{donde}.relaciones.{npc}", "delta numérico")
        for flag in efectos.get("flags") or []:
            ok = _texto(flag) or (isinstance(flag, list) and len(flag) == 2 and _texto(flag[0]) and isinstance(flag[1], bool))
            if not ok:
                self.err(donde + ".flags", f"flag inválido {flag!r}: texto o [texto, permanente]")
        for eid in efectos.get("da_evidencia") or []:
            if eid not in self.evidencias:
                self.err(donde + ".da_evidencia", f"evidencia {eid!r} no declarada en 'evidencias'")

    def _condicion(self, donde, cond):
        if cond is None:
            return
        if not isinstance(cond, dict):
            self.err(donde, "debe ser un objeto")
            return
        for clave in cond:
            if clave not in _CLAVES_CONDICION:
                self.err(donde, f"clave desconocida {clave!r}; válidas: {_CLAVES_CONDICION}")
        for clave in ("evidencia", "alguna_evidencia"):
            for eid in cond.get(clave) or []:
                if eid not in self.evidencias:
                    self.err(f"{donde}.{clave}", f"evidencia {eid!r} no declarada en 'evidencias'")
        for clave in ("visitado", "no_visitado"):
            for nid in cond.get(clave) or []:
                if nid not in self.nodos:
                    self.err(f"{donde}.{clave}", f"el nodo {nid!r} no existe")
        for clave, validos in (("confianza", GRUPOS), ("relacion", None)):
            for k, rango in (cond.get(clave) or {}).items():
                if validos is not None and k not in validos:
                    self.err(f"{donde}.{clave}", f"grupo {k!r} inexistente")
                if not isinstance(rango, dict) or any(x not in ("min", "max") or not _numero(v) for x, v in rango.items()):
                    self.err(f"{donde}.{clave}.{k}", "rango {min, max} numérico")

    def _grafo(self):
        fin = self.d.get("fin_por_errores")
        # ciclos: DFS iterativo con colores
        color, padre = {}, {}
        for raiz in self.nodos:
            if color.get(raiz):
                continue
            pila = [(raiz, iter(destinos_de(self.nodos[raiz], fin)))]
            color[raiz] = 1
            while pila:
                nodo, it = pila[-1]
                siguiente = next(it, None)
                if siguiente is None:
                    color[nodo] = 2
                    pila.pop()
                elif color.get(siguiente) == 1:
                    ciclo = [n for n, _ in pila]
                    ciclo = ciclo[ciclo.index(siguiente):] + [siguiente]
                    self.err("nodos", "ciclo en el DAG: " + " -> ".join(ciclo))
                    return
                elif not color.get(siguiente):
                    color[siguiente] = 1
                    padre[siguiente] = nodo
                    pila.append((siguiente, iter(destinos_de(self.nodos[siguiente], fin))))
        alcanzables = self._alcanzar(fin, expandir_menus=True)
        for id_nodo in self.nodos:
            if id_nodo not in alcanzables:
                self.err(f"nodos.{id_nodo}", "no es alcanzable desde 'inicio'")
        sin_menu = self._alcanzar(fin, expandir_menus=False)
        for id_nodo in sin_menu:
            nodo = self.nodos[id_nodo]
            if nodo["tipo"] != "menu" and _usa_volver(nodo):
                self.err(f"nodos.{id_nodo}", "usa «@volver» pero se puede llegar sin pasar por un menú")
        if not any(n["tipo"] == "final" for n in self.nodos.values()):
            self.err("nodos", "el caso necesita al menos un nodo final")

    def _alcanzar(self, fin, expandir_menus):
        vistos, pila = set(), [self.d["inicio"]]
        while pila:
            nodo = pila.pop()
            if nodo in vistos:
                continue
            vistos.add(nodo)
            if self.nodos[nodo]["tipo"] == "menu" and not expandir_menus:
                continue
            pila.extend(destinos_de(self.nodos[nodo], fin))
        return vistos


# Lista de mensajes de error del caso (vacía = válido). No lanza por contenido: un dato raro es un mensaje.
def validar(datos):
    if not isinstance(datos, dict):
        return ["el caso debe ser un objeto JSON"]
    try:
        return _Validador(datos).ejecutar()
    except (AttributeError, TypeError, KeyError) as error:    # estructura demasiado rota para seguir validando
        return [f"estructura inválida ({type(error).__name__}: {error})"]


# -- Condiciones y rastro --

def _nombre_flag(id_caso, *partes):
    return PREFIJO_FLAG + id_caso + ":" + ":".join(partes)


@dataclass(frozen=True)
class ResultadoCaso:
    caso_id: str
    final_id: str
    resultado: str
    acusado: str | None = None


# Casos terminados según el GameState (ordenados por id). Para el Archivo de casos.
def casos_jugados(game_state):
    parciales = {}
    for nombre in game_state.flags():
        if not nombre.startswith(PREFIJO_FLAG):
            continue
        resto = nombre[len(PREFIJO_FLAG):].split(":", 2)
        if len(resto) < 3:
            continue
        id_caso, clave, valor = resto
        parciales.setdefault(id_caso, {})[clave] = valor
    return [ResultadoCaso(i, p.get("final", ""), p.get("resultado", ""), p.get("acusado"))
            for i, p in sorted(parciales.items()) if "final" in p]


def resultado_de(game_state, id_caso):
    return next((r for r in casos_jugados(game_state) if r.caso_id == id_caso), None)


def puede_jugar(game_state, caso):
    return caso.rejugable or resultado_de(game_state, caso.id) is None


# -- Sesión --

@dataclass(frozen=True)
class VistaOpcion:
    id: str
    texto: str
    disponible: bool
    motivo: str = ""


@dataclass(frozen=True)
class VistaNodo:
    id: str
    tipo: str
    personaje: str | None
    expresion: str | None
    texto: str
    titulo: str = ""
    opciones: tuple = ()
    admite_presentar: bool = False
    segundos_limite: float | None = None
    restante: float | None = None
    resultado: str | None = None


@dataclass(frozen=True)
class ResultadoPresentacion:
    correcta: bool
    texto: str
    errores: int


class SesionCaso:

    def __init__(self, caso, game_state, estado=None):
        self.caso = caso
        self.gs = game_state
        self.nodo_id = None
        self._hub = None
        self._visitados = set()
        self._usadas = set()
        self.errores = 0
        self.acusado = None
        self.historial = []
        self._restante = None
        if estado is None:
            self._entrar(caso.inicio)
        else:
            self._restaurar(estado)

    # -- Consulta --

    @property
    def terminado(self):
        return self.caso.nodo(self.nodo_id)["tipo"] == "final"

    def nodo_actual(self):
        return self.caso.nodo(self.nodo_id)

    def visitados(self):
        return set(self._visitados)

    def evidencias_en_mano(self):
        return [i for i in evidencia.listar(self.gs) if i in self.caso.evidencias]

    def segundos_limite(self):
        t = self.nodo_actual().get("temporizador")
        return float(t["segundos"]) if t else None

    def restante(self):
        return self._restante

    def vista(self):
        nodo = self.nodo_actual()
        opciones = tuple(v for v in (self._vista_opcion(nodo, o) for o in opciones_de(nodo)) if v is not None)
        return VistaNodo(
            id=self.nodo_id, tipo=nodo["tipo"], personaje=nodo.get("personaje"), expresion=nodo.get("expresion"),
            texto=nodo.get("texto", ""), titulo=nodo.get("titulo", ""), opciones=opciones,
            admite_presentar=bool(nodo.get("contradicciones")), segundos_limite=self.segundos_limite(),
            restante=self._restante, resultado=nodo.get("resultado"))

    def _vista_opcion(self, nodo, opcion):
        disponible, motivo = self._estado_opcion(nodo, opcion)
        if not disponible and opcion.get("oculta") and motivo == MOTIVO_BLOQUEADA:
            return None
        return VistaOpcion(opcion["id"], opcion["texto"], disponible, motivo)

    def _estado_opcion(self, nodo, opcion):
        if nodo["tipo"] == "menu" and opcion.get("una_vez", True) and f"{self.nodo_id}/{opcion['id']}" in self._usadas:
            return False, MOTIVO_AGOTADA
        if not self._cumple(opcion.get("requiere")):
            return False, opcion.get("bloqueo", MOTIVO_BLOQUEADA)
        return True, ""

    # -- Acciones del jugador --

    def continuar(self):
        nodo = self.nodo_actual()
        if nodo["tipo"] != "dialogo":
            raise CasoError(f"continuar() solo en diálogos; el nodo {self.nodo_id!r} es {nodo['tipo']}.")
        self.historial.append({"nodo": self.nodo_id, "accion": "continuar"})
        self._ir(nodo["siguiente"])

    def elegir(self, id_opcion, por_tiempo=False):
        nodo = self.nodo_actual()
        if nodo["tipo"] not in CLAVE_OPCIONES:
            raise CasoError(f"El nodo {self.nodo_id!r} ({nodo['tipo']}) no tiene opciones.")
        opcion = next((o for o in opciones_de(nodo) if o["id"] == id_opcion), None)
        if opcion is None:
            raise CasoError(f"El nodo {self.nodo_id!r} no tiene la opción {id_opcion!r}.")
        disponible, motivo = self._estado_opcion(nodo, opcion)
        if not disponible:
            raise CasoError(f"La opción {id_opcion!r} no está disponible: {motivo}")
        self._usadas.add(f"{self.nodo_id}/{id_opcion}")
        destino, efectos = self._resolver(opcion)
        if nodo["tipo"] == "acusacion":
            self.acusado = opcion.get("personaje", opcion["id"])
        if nodo["tipo"] == "menu":
            self._hub = self.nodo_id
        self.historial.append({"nodo": self.nodo_id, "accion": "elegir", "opcion": id_opcion, "por_tiempo": por_tiempo})
        self._aplicar(opcion.get("efectos"), "decision", {"nodo": self.nodo_id, "opcion": id_opcion, "por_tiempo": por_tiempo})
        self._aplicar(efectos, "decision", {"nodo": self.nodo_id, "opcion": id_opcion, "por_tiempo": por_tiempo})
        self._ir(destino)

    # Presenta la evidencia `id_evidencia` (debe tenerla el jugador) contra la afirmación del nodo.
    def presentar(self, id_evidencia):
        nodo = self.nodo_actual()
        contradicciones = nodo.get("contradicciones")
        if not contradicciones:
            raise CasoError(f"En el nodo {self.nodo_id!r} no se pueden presentar pruebas.")
        if id_evidencia not in self.caso.evidencias or not evidencia.tiene(self.gs, id_evidencia):
            raise CasoError(f"No tienes la evidencia {id_evidencia!r}.")
        self._hub = self.nodo_id
        acierto = next((c for c in contradicciones if c["evidencia"] == id_evidencia), None)
        datos = {"nodo": self.nodo_id, "evidencia": id_evidencia}
        if acierto is not None and self._cumple(acierto.get("requiere")):
            self.historial.append({"nodo": self.nodo_id, "accion": "presentar", "evidencia": id_evidencia, "correcta": True})
            self._aplicar(acierto.get("efectos"), "contradiccion", dict(datos, correcta=True))
            self._ir(acierto["destino"])
            return ResultadoPresentacion(True, acierto.get("texto", ""), self.errores)
        error = nodo.get("error") or {}
        self.errores += 1
        self.historial.append({"nodo": self.nodo_id, "accion": "presentar", "evidencia": id_evidencia, "correcta": False})
        self._aplicar(error.get("efectos"), "error", dict(datos, correcta=False, errores=self.errores))
        limite = self.caso.fin_por_errores
        if limite and self.errores >= limite["max"]:
            self._ir(limite["destino"])
        elif error.get("destino"):
            self._ir(error["destino"])
        return ResultadoPresentacion(False, error.get("texto", ""), self.errores)

    # Descuenta `dt` segundos de la pregunta actual. Al llegar a 0 elige la opción por defecto. True si lo hizo.
    def avanzar_tiempo(self, dt):
        if self._restante is None or self.terminado:
            return False
        self._restante = max(0.0, self._restante - max(0.0, dt))
        if self._restante > 0:
            return False
        self.agotar_tiempo()
        return True

    def agotar_tiempo(self):
        t = self.nodo_actual().get("temporizador")
        if t is None:
            return False
        self.elegir(t["por_defecto"], por_tiempo=True)
        return True

    # -- Interno --

    def _cumple(self, cond):
        if not cond:
            return True
        gs = self.gs
        if not all(evidencia.tiene(gs, e) for e in cond.get("evidencia", [])):
            return False
        alguna = cond.get("alguna_evidencia")
        if alguna and not any(evidencia.tiene(gs, e) for e in alguna):
            return False
        if not all(gs.flag(f) for f in cond.get("flags", [])) or any(gs.flag(f) for f in cond.get("sin_flags", [])):
            return False
        if not all(n in self._visitados for n in cond.get("visitado", [])):
            return False
        if any(n in self._visitados for n in cond.get("no_visitado", [])):
            return False
        for grupo, rango in cond.get("confianza", {}).items():
            if not rango.get("min", -math.inf) <= gs.confianza(grupo) <= rango.get("max", math.inf):
                return False
        for npc, rango in cond.get("relacion", {}).items():
            valor = gs.relacion(npc) if npc in gs.npcs() else RELACION_INICIAL
            if not rango.get("min", -math.inf) <= valor <= rango.get("max", math.inf):
                return False
        return True

    def _resolver(self, opcion):
        for ruta in opcion.get("rutas", []) or []:
            if self._cumple(ruta.get("requiere")):
                return ruta["destino"], ruta.get("efectos")
        return opcion["destino"], None

    def _ir(self, destino):
        if destino == VOLVER:
            if self._hub is None:
                raise CasoError("«@volver» sin un menú al que regresar.")
            destino = self._hub
        self._entrar(destino)

    def _entrar(self, id_nodo):
        nuevo = id_nodo not in self._visitados
        self.nodo_id = id_nodo
        self._visitados.add(id_nodo)
        nodo = self.nodo_actual()
        if nodo["tipo"] == "final":
            self._restante = None
            self._cerrar(id_nodo, nodo)
            return
        if nuevo:
            self._aplicar(nodo.get("efectos"), "nodo", {"nodo": id_nodo})
        t = nodo.get("temporizador")
        self._restante = float(t["segundos"]) if t else None

    def _cerrar(self, id_nodo, nodo):
        id_caso = self.caso.id
        flags = [(_nombre_flag(id_caso, "jugado"), True), (_nombre_flag(id_caso, "final", id_nodo), True),
                 (_nombre_flag(id_caso, "resultado", nodo["resultado"]), True)]
        if self.acusado:
            flags.append((_nombre_flag(id_caso, "acusado", self.acusado), True))
        self._aplicar(nodo.get("efectos"), "final", {"nodo": id_nodo, "resultado": nodo["resultado"],
                                                      "acusado": self.acusado, "errores": self.errores}, flags_extra=flags)

    def _aplicar(self, efectos, tipo, datos, flags_extra=()):
        efectos = efectos or {}
        gs = self.gs
        grupos = efectos.get("grupos") or None
        pedidas = efectos.get("relaciones") or {}
        relaciones = {n: d for n, d in pedidas.items() if n in gs.npcs()} or None
        desconocidos = sorted(n for n in pedidas if n not in gs.npcs())
        if desconocidos:
            _registro.warning("Caso %r: relaciones con NPC que el GameState no lleva, descartadas: %s (hay: %s).",
                              self.caso.id, desconocidos, sorted(gs.npcs()))
        flags = [tuple(f) if isinstance(f, list) else f for f in efectos.get("flags", [])] + list(flags_extra)
        evidencias = efectos.get("da_evidencia", [])
        origen = f"caso:{self.caso.id}"
        if grupos or relaciones or flags:
            gs.aplicar_evento(f"caso:{efectos.get('tipo', tipo)}", efectos=grupos, relaciones=relaciones, flags=flags,
                              origen=origen, datos=dict(datos, caso=self.caso.id))
        for id_evidencia in evidencias:
            evidencia.otorgar(gs, id_evidencia, origen, datos={"caso": self.caso.id})

    # -- Serialización de la sesión (el progreso a medias; los efectos ya viven en el GameState) --

    def a_dict(self):
        return {"caso": self.caso.id, "nodo": self.nodo_id, "hub": self._hub, "visitados": sorted(self._visitados),
                "usadas": sorted(self._usadas), "errores": self.errores, "acusado": self.acusado,
                "restante": self._restante, "historial": list(self.historial)}

    def _restaurar(self, estado):
        if estado.get("caso") != self.caso.id or estado.get("nodo") not in self.caso.nodos:
            raise CasoError("El progreso guardado no corresponde a este caso.")
        self.nodo_id, self._hub = estado["nodo"], estado.get("hub")
        self._visitados, self._usadas = set(estado["visitados"]), set(estado["usadas"])
        self.errores, self.acusado = int(estado["errores"]), estado.get("acusado")
        self._restante, self.historial = estado.get("restante"), list(estado.get("historial", []))
