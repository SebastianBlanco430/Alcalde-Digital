# Archivo de casos (modelo puro, sin motor gráfico). Reconstruye el historial de la investigación leyendo el
# ArbolImpactos del GameState en INORDEN (orden cronológico): evidencias (con su origen), decisiones, pruebas
# presentadas, acusaciones, resultados y los deltas de confianza por grupo / relación por NPC de cada impacto.
#
# Qué impactos entran: los de tipo «evidencia» (backend/logica/evidencia.py) y los «caso:*» (backend/logica/casos.py:
# decision, contradiccion, error, nodo, final). Los demás (noticias, eventos de otros sistemas) se ignoran: este
# archivo es del caso, no del juego entero.
#
# Categorías de una entrada: evidencia · decision · prueba (contradicción o error) · hallazgo (efectos de un nodo) ·
# acusacion (final con acusado u opción de acusación, incluida «no acusar») · resultado (final sin acusado). Un impacto = una entrada, en el orden en que ocurrió.
# Una decisión sin efectos no deja impacto en el GameState, por lo que no aparece (el rastro de cierre sí: flags).
#
# Los textos no viven aquí: `Contexto` recibe el JSON de textos (backend/datos/archivo_casos_textos.json) y, opcional,
# los casos del catálogo para poner nombres legibles (cuando no hay, se muestra el id).

import string
import textwrap
from dataclasses import dataclass, field

from backend.logica import casos as modulo_casos
from backend.logica.game_state import GRUPOS

CATEGORIAS = ("evidencia", "decision", "prueba", "hallazgo", "acusacion", "resultado")
PREFIJO_NPC = "npc:"
TIPO_EVIDENCIA = "evidencia"
_SUBTIPO_A_CATEGORIA = {"decision": "decision", "contradiccion": "prueba", "error": "prueba", "nodo": "hallazgo"}


# Un impacto ya clasificado. `deltas` = ((clave, valor), ...) con clave = grupo o «npc:<id>». `datos` = el dict del impacto.
@dataclass(frozen=True)
class Entrada:
    orden: int                      # posición cronológica (1 = la primera)
    timestamp: float
    secuencia: int
    categoria: str
    tipo: str                       # tipo crudo del impacto («caso:decision», «evidencia»...)
    caso_id: str | None
    origen: str | None
    deltas: tuple
    datos: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def grupos(self):
        return {k: v for k, v in self.deltas if not k.startswith(PREFIJO_NPC)}

    @property
    def npcs(self):
        return {k[len(PREFIJO_NPC):]: v for k, v in self.deltas if k.startswith(PREFIJO_NPC)}

    @property
    def acusado(self):
        return self.datos.get("acusado")

    @property
    def evidencia_id(self):
        return self.datos.get("evidencia")


@dataclass(frozen=True)
class ResumenActor:
    clave: str                      # grupo o «npc:<id>»
    tipo: str                       # «grupo» | «npc»
    id: str
    total: float
    positivo: float
    negativo: float
    cambios: int


@dataclass(frozen=True)
class EvidenciaObtenida:
    id: str
    origen: str | None
    caso_id: str | None
    orden: int


@dataclass(frozen=True)
class Archivo:
    entradas: tuple
    casos: tuple                    # ResultadoCaso de los casos terminados
    evidencias: tuple               # EvidenciaObtenida, en el orden en que se obtuvieron


# -- Reconstrucción --

# True si hay GameState con un árbol de impactos legible (en línea o con GAMESTATE=0 no hay).
def disponible(game_state):
    return game_state is not None and callable(getattr(game_state, "impactos", None))


def _caso_de(nodo):
    caso = nodo.datos.get("caso")
    if isinstance(caso, str) and caso:
        return caso
    if isinstance(nodo.origen, str) and nodo.origen.startswith(modulo_casos.PREFIJO_FLAG):
        return nodo.origen[len(modulo_casos.PREFIJO_FLAG):] or None
    return None


def _categoria_de(tipo, datos):
    if tipo == TIPO_EVIDENCIA:
        return "evidencia"
    if not tipo.startswith(modulo_casos.PREFIJO_FLAG):
        return None
    subtipo = tipo[len(modulo_casos.PREFIJO_FLAG):]
    if subtipo == "final":
        return "acusacion" if datos.get("acusado") else "resultado"
    return _SUBTIPO_A_CATEGORIA.get(subtipo, "hallazgo")


# Catálogo de casos por defecto para deducir a qué caso pertenece una evidencia. Si no carga, no se deduce nada.
def _catalogo_por_defecto():
    try:
        from backend.datos import casos_loader
        return casos_loader.cargar_catalogo()
    except (ValueError, OSError):
        return {}


# Caso de una evidencia que no lo trae (la dio el parkour u otro sistema): el ÚNICO caso que la declara en sus
# `evidencias`. Si no la declara ninguno, o la declaran varios, queda sin caso (no se inventa).
def _caso_de_evidencia(id_evidencia, casos):
    candidatos = [id_caso for id_caso, caso in casos.items() if id_evidencia in getattr(caso, "evidencias", {})]
    return candidatos[0] if len(candidatos) == 1 else None


# Entradas del Archivo en orden cronológico (inorden del ArbolImpactos). `casos`: {id: Caso} para deducir el caso de las
# evidencias que no lo traen (None = el catálogo real, cargado solo si hace falta; {} = no deducir).
def reconstruir(game_state, casos=None):
    if not disponible(game_state):
        return []
    entradas = []
    for nodo in game_state.impactos().inorden():
        categoria = _categoria_de(nodo.tipo, nodo.datos)
        if categoria is None:
            continue
        caso_id = _caso_de(nodo)
        if caso_id is None and categoria == "evidencia" and nodo.datos.get("evidencia"):
            if casos is None:
                casos = _catalogo_por_defecto()
            caso_id = _caso_de_evidencia(nodo.datos["evidencia"], casos)
        entradas.append(Entrada(
            orden=len(entradas) + 1, timestamp=nodo.timestamp, secuencia=nodo.secuencia, categoria=categoria,
            tipo=nodo.tipo, caso_id=caso_id, origen=nodo.origen,
            deltas=tuple((str(k), v) for k, v in nodo.deltas.items()), datos=dict(nodo.datos)))
    return entradas


def evidencias_obtenidas(entradas):
    return [EvidenciaObtenida(e.evidencia_id, e.origen, e.caso_id, e.orden)
            for e in entradas if e.categoria == "evidencia" and e.evidencia_id]


# Todo junto para la vista. Sin GameState devuelve None (la vista muestra «Archivo no disponible»).
def construir(game_state, casos=None):
    if not disponible(game_state):
        return None
    entradas = reconstruir(game_state, casos)
    return Archivo(tuple(entradas), tuple(modulo_casos.casos_jugados(game_state)), tuple(evidencias_obtenidas(entradas)))


# -- Filtros y resumen --

# Entradas que cumplen TODOS los filtros dados (None = sin filtro). `grupo`: la entrada cambió la confianza de ese
# grupo; `npc`: cambió la relación con ese NPC. Conserva el orden cronológico.
def filtrar(entradas, caso=None, categoria=None, grupo=None, npc=None):
    resultado = []
    for e in entradas:
        if caso is not None and e.caso_id != caso:
            continue
        if categoria is not None and e.categoria != categoria:
            continue
        if grupo is not None and grupo not in e.grupos:
            continue
        if npc is not None and npc not in e.npcs:
            continue
        resultado.append(e)
    return resultado


def casos_en(entradas):
    return sorted({e.caso_id for e in entradas if e.caso_id})


# Claves de actor presentes en las entradas: primero los grupos (en el orden del juego), luego «npc:<id>» ordenados.
def actores_en(entradas):
    vistos = {k for e in entradas for k, _ in e.deltas}
    grupos = [g for g in GRUPOS if g in vistos]
    otros = sorted(k for k in vistos if k not in GRUPOS and not k.startswith(PREFIJO_NPC))
    npcs = sorted(k for k in vistos if k.startswith(PREFIJO_NPC))
    return grupos + otros + npcs


# Filtra por una clave de actor (grupo o «npc:<id>»); None = todas.
def filtrar_actor(entradas, actor):
    if actor is None:
        return list(entradas)
    return [e for e in entradas if any(k == actor for k, _ in e.deltas)]


# Acumulado de deltas por grupo y por NPC de las entradas dadas (suma, parte positiva y negativa, nº de cambios).
def resumen_por_actor(entradas):
    acumulado = {}
    for e in entradas:
        for clave, valor in e.deltas:
            if not isinstance(valor, (int, float)) or isinstance(valor, bool):
                continue
            total, pos, neg, n = acumulado.get(clave, (0.0, 0.0, 0.0, 0))
            acumulado[clave] = (total + valor, pos + max(valor, 0), neg + min(valor, 0), n + 1)
    resumen = []
    for clave in actores_en(entradas):
        if clave not in acumulado:
            continue
        total, pos, neg, n = acumulado[clave]
        es_npc = clave.startswith(PREFIJO_NPC)
        resumen.append(ResumenActor(clave, "npc" if es_npc else "grupo", clave[len(PREFIJO_NPC):] if es_npc else clave,
                                    round(total, 2), round(pos, 2), round(neg, 2), n))
    return resumen


# Siguiente valor al pulsar un filtro cíclico: None -> v0 -> v1 -> ... -> None. Si `actual` ya no existe, vuelve a None.
def siguiente(valores, actual):
    valores = list(valores)
    if actual is None:
        return valores[0] if valores else None
    if actual not in valores:
        return None
    i = valores.index(actual) + 1
    return valores[i] if i < len(valores) else None


# Ventana visible: índice inicial acotado para `filas` filas sobre `total` entradas.
def acotar_desplazamiento(inicio, total, filas):
    return max(0, min(int(inicio), max(0, total - max(1, filas))))


# -- Textos legibles --

class _Seguro(dict):
    def __missing__(self, clave):
        return "?"


def _rellenar(plantilla, **valores):
    return string.Formatter().vformat(plantilla, (), _Seguro(valores))


# Resuelve nombres legibles. `textos`: el JSON de archivo_casos_textos.json. `casos`: {id: Caso} (opcional).
# `nombre_nivel`: callable(id_nivel) -> nombre del nivel de parkour (opcional).
class Contexto:

    def __init__(self, textos, casos=None, nombre_nivel=None):
        self.textos = textos
        self.casos = casos or {}
        self.nombre_nivel = nombre_nivel

    def nombre_caso(self, caso_id):
        caso = self.casos.get(caso_id)
        return caso.titulo if caso is not None else (caso_id or "?")

    def nombre_evidencia(self, evidencia_id, caso_id=None):
        candidatos = [self.casos[caso_id]] if caso_id in self.casos else list(self.casos.values())
        for caso in candidatos:
            if evidencia_id in caso.evidencias:
                return caso.nombre_evidencia(evidencia_id)
        return evidencia_id or "?"

    def texto_opcion(self, caso_id, nodo_id, opcion_id):
        caso = self.casos.get(caso_id)
        if caso is not None and nodo_id in caso.nodos:
            for opcion in modulo_casos.opciones_de(caso.nodos[nodo_id]):
                if opcion.get("id") == opcion_id:
                    return opcion.get("texto", opcion_id)
        return opcion_id or "?"

    def titulo_final(self, caso_id, nodo_id):
        caso = self.casos.get(caso_id)
        if caso is not None and nodo_id in caso.nodos:
            return caso.nodos[nodo_id].get("titulo", nodo_id)
        return nodo_id or "?"

    # ¿`acusado` es un personaje del caso? (sin catálogo se asume que sí). Si no lo es, fue una opción como «no acusar».
    def es_personaje(self, caso_id, acusado):
        caso = self.casos.get(caso_id)
        return caso is None or acusado in caso.personajes

    # Texto de la opción de acusación cuya id o personaje es `acusado` (o el propio id si no se encuentra).
    def texto_acusacion(self, caso_id, acusado):
        caso = self.casos.get(caso_id)
        if caso is not None:
            for nodo in caso.nodos.values():
                for opcion in modulo_casos.opciones_de(nodo) if nodo.get("tipo") == "acusacion" else ():
                    if acusado in (opcion.get("id"), opcion.get("personaje")):
                        return opcion.get("texto", acusado)
        return acusado or "?"

    def nombre_personaje(self, caso_id, personaje_id):
        caso = self.casos.get(caso_id)
        return caso.nombre_personaje(personaje_id) if caso is not None else (personaje_id or "?")

    # Primeras palabras del texto del nodo (para decir de qué fue la novedad).
    def resumen_nodo(self, caso_id, nodo_id, maximo=70):
        caso = self.casos.get(caso_id)
        if caso is not None and nodo_id in caso.nodos:
            return recortar(caso.nodos[nodo_id].get("texto", ""), maximo)
        return nodo_id or "?"

    def nombre_resultado(self, resultado):
        return self.textos["resultados"].get(resultado, str(resultado or "?"))

    def nombre_actor(self, clave):
        if clave.startswith(PREFIJO_NPC):
            return clave[len(PREFIJO_NPC):].replace("_", " ").capitalize()
        return self.textos["grupos"].get(clave, clave)

    def nombre_categoria(self, categoria):
        return self.textos["categorias"].get(categoria, categoria)

    # «parkour:sector_1» -> «Parkour «Sector corrupto 1...»»; «caso:x» -> «Caso «Título»».
    def describir_origen(self, origen):
        origenes = self.textos["origenes"]
        if isinstance(origen, str) and ":" in origen:
            tipo, _, resto = origen.partition(":")
            if tipo == "parkour":
                nombre = self.nombre_nivel(resto) if callable(self.nombre_nivel) else resto
                return _rellenar(origenes["parkour"], nombre=nombre or resto)
            if tipo == "caso":
                return _rellenar(origenes["caso"], nombre=self.nombre_caso(resto))
        return _rellenar(origenes["desconocido"], origen=origen or "?")


# (título, detalle) de una entrada, con los nombres del catálogo.
def describir(entrada, ctx):
    plantillas = ctx.textos["plantillas"]
    d, caso = entrada.datos, entrada.caso_id
    comunes = {"caso": ctx.nombre_caso(caso) if caso else ""}
    if entrada.categoria == "evidencia":
        p = plantillas["evidencia"]
        return (_rellenar(p["titulo"], evidencia=ctx.nombre_evidencia(entrada.evidencia_id, caso)),
                _rellenar(p["detalle"], origen=ctx.describir_origen(entrada.origen)))
    if entrada.categoria == "decision":
        p = plantillas["decision"]
        por_tiempo = ctx.textos.get("por_tiempo", "") if d.get("por_tiempo") else ""
        return (_rellenar(p["titulo"], opcion=ctx.texto_opcion(caso, d.get("nodo"), d.get("opcion"))),
                _rellenar(p["detalle"], por_tiempo=por_tiempo, **comunes))
    if entrada.categoria == "prueba":
        p = plantillas["prueba_correcta" if d.get("correcta") else "prueba_incorrecta"]
        return (_rellenar(p["titulo"], evidencia=ctx.nombre_evidencia(d.get("evidencia"), caso)),
                _rellenar(p["detalle"], errores=d.get("errores", "?"), **comunes))
    if entrada.categoria in ("acusacion", "resultado"):
        clave = entrada.categoria
        if clave == "acusacion" and not ctx.es_personaje(caso, entrada.acusado):
            clave = "acusacion_otra"                  # p. ej. «No acusar a nadie todavía»: no hay un nombre que mostrar
        p = plantillas[clave]
        return (_rellenar(p["titulo"], acusado=ctx.nombre_personaje(caso, entrada.acusado),
                          opcion=ctx.texto_acusacion(caso, entrada.acusado),
                          final=ctx.titulo_final(caso, d.get("nodo"))),
                _rellenar(p["detalle"], final=ctx.titulo_final(caso, d.get("nodo")),
                          resultado=ctx.nombre_resultado(d.get("resultado")), **comunes))
    p = plantillas["hallazgo"]
    return (_rellenar(p["titulo"], **comunes),
            _rellenar(p["detalle"], texto=ctx.resumen_nodo(caso, d.get("nodo")), **comunes))


# «Policía +5 · Ciudadanos -2 · Jefe +3»: los deltas de la entrada con TEXTO y signo (no solo color). "" si no hay.
def texto_deltas(entrada, ctx):
    partes = []
    for clave, valor in entrada.deltas:
        if isinstance(valor, (int, float)) and not isinstance(valor, bool):
            partes.append(f"{ctx.nombre_actor(clave)} {valor:+g}")
    return " · ".join(partes)


def texto_caso_jugado(resultado, ctx):
    claves = "caso_jugado_acusado" if resultado.acusado else "caso_jugado"
    return _rellenar(ctx.textos[claves], caso=ctx.nombre_caso(resultado.caso_id),
                     final=ctx.titulo_final(resultado.caso_id, resultado.final_id),
                     resultado=ctx.nombre_resultado(resultado.resultado),
                     acusado=ctx.nombre_personaje(resultado.caso_id, resultado.acusado))


def texto_evidencia(obtenida, ctx):
    return _rellenar(ctx.textos["evidencia_linea"], evidencia=ctx.nombre_evidencia(obtenida.id, obtenida.caso_id),
                     origen=ctx.describir_origen(obtenida.origen))


# «Ciudadanos: +2.6 en 1 cambio»; si hubo subidas Y bajadas se desglosan: «Vecinos: +1.4 en 3 cambios (subió 4, bajó 2.6)».
# (Antes: «Ciudadanos: +2.6 (+2.6 / 0, 1)», que no se entendía sin leer el código.)
def texto_resumen(resumen, ctx):
    cambios = "1 cambio" if resumen.cambios == 1 else f"{resumen.cambios} cambios"
    texto = f"{ctx.nombre_actor(resumen.clave)}: {resumen.total:+g} en {cambios}"
    if resumen.positivo and resumen.negativo:
        texto += f" (subió {resumen.positivo:g}, bajó {abs(resumen.negativo):g})"
    return texto


# -- Consulta (filtros + desplazamiento) para la vista --

# Estado de lo que el jugador está mirando: filtros cíclicos (caso, categoría, actor) y la ventana de desplazamiento.
# Cambiar un filtro vuelve al inicio de la lista. No dibuja nada.
class ConsultaArchivo:

    def __init__(self, archivo, filas_visibles=10):
        self.archivo = archivo
        self.filas_visibles = max(1, int(filas_visibles))
        self.caso = None
        self.categoria = None
        self.actor = None
        self.inicio = 0

    def entradas(self):
        porcategoria = filtrar(self.archivo.entradas, caso=self.caso, categoria=self.categoria)
        return filtrar_actor(porcategoria, self.actor)

    def visibles(self):
        todas = self.entradas()
        self.inicio = acotar_desplazamiento(self.inicio, len(todas), self.filas_visibles)
        return todas[self.inicio:self.inicio + self.filas_visibles]

    # (desde, hasta, total) de la ventana actual, contando desde 1; (0, 0, 0) si no hay nada.
    def posicion(self):
        total = len(self.entradas())
        if total == 0:
            return 0, 0, 0
        visibles = len(self.visibles())
        return self.inicio + 1, self.inicio + visibles, total

    def resumen(self):
        return resumen_por_actor(self.entradas())

    def hay_filtros(self):
        return not (self.caso is None and self.categoria is None and self.actor is None)

    def ciclar_caso(self):
        self.caso = siguiente(casos_en(self.archivo.entradas), self.caso)
        self.inicio = 0

    def ciclar_categoria(self):
        presentes = {e.categoria for e in self.archivo.entradas}
        self.categoria = siguiente([c for c in CATEGORIAS if c in presentes], self.categoria)
        self.inicio = 0

    def ciclar_actor(self):
        self.actor = siguiente(actores_en(self.archivo.entradas), self.actor)
        self.inicio = 0

    def quitar_filtros(self):
        self.caso = self.categoria = self.actor = None
        self.inicio = 0

    def desplazar(self, filas):
        self.inicio = acotar_desplazamiento(self.inicio + int(filas), len(self.entradas()), self.filas_visibles)

    def pagina(self, sentido):
        self.desplazar(sentido * self.filas_visibles)

    def al_inicio(self):
        self.inicio = 0

    def al_final(self):
        self.inicio = acotar_desplazamiento(10 ** 9, len(self.entradas()), self.filas_visibles)


# -- Líneas listas para dibujar (la vista solo las coloca) --

# Recorta a `maximo` caracteres con «...» (sin glifos raros: la fuente por defecto los dibuja todos).
def recortar(texto, maximo):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= maximo else texto[:max(0, maximo - 3)].rstrip() + "..."


# Parte `texto` en líneas de `ancho` caracteres; si pasa de `max_lineas`, la última termina en «...».
def envolver(texto, ancho, max_lineas, sangria=""):
    lineas = textwrap.wrap(str(texto), width=max(8, ancho), subsequent_indent=sangria) or [""]
    if len(lineas) > max_lineas:
        lineas = lineas[:max_lineas]
        lineas[-1] = recortar(lineas[-1], max(8, ancho) - 3) + "..."
    return lineas


# Las 3 líneas de una fila del registro: «N · Categoría · título», detalle y deltas (esta última puede ir vacía).
def lineas_de_entrada(entrada, ctx, ancho=100):
    titulo, detalle = describir(entrada, ctx)
    cabecera = f"{entrada.orden}. [{ctx.nombre_categoria(entrada.categoria)}] {titulo}"
    return [recortar(cabecera, ancho), recortar(detalle, ancho), recortar(texto_deltas(entrada, ctx), ancho)]


def lineas_casos_jugados(archivo, ctx, ancho=44, maximo=5):
    if not archivo.casos:
        return [ctx.textos.get("sin_casos", "")]
    lineas = []
    for resultado in archivo.casos:
        lineas += envolver(texto_caso_jugado(resultado, ctx), ancho, 3, "  ")
    return lineas[:maximo] if len(lineas) > maximo else lineas


def lineas_evidencias(archivo, ctx, ancho=44, maximo=8):
    if not archivo.evidencias:
        return [ctx.textos.get("sin_evidencias", "")]
    lineas = []
    for obtenida in archivo.evidencias:
        lineas += envolver(texto_evidencia(obtenida, ctx), ancho, 3, "  ")
    return lineas[:maximo] if len(lineas) > maximo else lineas


def lineas_resumen(consulta, ctx, ancho=44, maximo=8):
    resumen = consulta.resumen()
    if not resumen:
        return [ctx.textos.get("sin_efectos", "")]
    lineas = [recortar(texto_resumen(r, ctx), ancho) for r in resumen]
    return lineas[:maximo]


# Etiqueta de un filtro: «Caso: Cuentas fantasma» o «Caso: Todos». `cual`: "caso" | "tipo" | "actor".
def etiqueta_filtro(consulta, cual, ctx):
    filtros = ctx.textos["filtros"]
    valor = {"caso": consulta.caso, "tipo": consulta.categoria, "actor": consulta.actor}[cual]
    if valor is None:
        nombre = filtros["todos"]
    elif cual == "caso":
        nombre = ctx.nombre_caso(valor)
    elif cual == "tipo":
        nombre = ctx.nombre_categoria(valor)
    else:
        nombre = ctx.nombre_actor(valor)
    return f"{filtros[cual]}: {nombre}"
