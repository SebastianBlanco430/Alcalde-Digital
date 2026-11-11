# Comandos de depuración sobre el GameState (modelo puro, sin ursina ni consola propia): recibe una línea de texto y
# devuelve un mensaje. Nada se ejecuta solo; quien quiera una consola (o un script/REPL) llama a ejecutar().
#
#   mostrar
#   confianza <grupo> <delta>        (suma; recorta a 0-100)
#   fijar_confianza <grupo> <valor>
#   relacion <npc> <delta>
#   flag poner <nombre> [permanente]
#   flag quitar <nombre>
#   evento <tipo> <grupo> <investigacion> <moral> <secundarios>   (aplica la fórmula 50/30/20 y registra el impacto)
#   impactos                         (lista cronológica del ArbolImpactos)
#
# Errores de uso devuelven un mensaje que empieza por «Error:»; nunca lanzan.

from backend.logica.game_state import GRUPOS


def _numero(texto):
    try:
        return float(texto)
    except ValueError:
        raise ValueError(f"no es un número: {texto!r}")


def ejecutar(estado, linea):
    partes = (linea or "").split()
    if not partes:
        return "Error: comando vacío."
    comando, args = partes[0].lower(), partes[1:]
    try:
        return _COMANDOS[comando](estado, args)
    except KeyError:
        return f"Error: comando desconocido {comando!r}."
    except (ValueError, IndexError) as error:
        if isinstance(error, IndexError):
            return f"Error: faltan argumentos para {comando!r}."
        return f"Error: {error}"


def _mostrar(estado, args):
    lineas = ["confianza: " + ", ".join(f"{g}={v:g}" for g, v in estado.confianzas().items())]
    if estado.npcs():
        lineas.append("relaciones: " + ", ".join(f"{n}={estado.relacion(n):g}" for n in estado.npcs()))
    banderas = [f"{n}{'*' if p else ''}" for n, p in estado.flags().items()]
    lineas.append("flags: " + (", ".join(banderas) if banderas else "(ninguna)") + "  (* = permanente)")
    lineas.append(f"impactos: {estado.impactos().tamano()}")
    return "\n".join(lineas)


def _confianza(estado, args):
    valor = estado.cambiar_confianza(args[0], _numero(args[1]))
    return f"{args[0]} = {valor:g}"


def _fijar_confianza(estado, args):
    grupo, objetivo = args[0], _numero(args[1])
    valor = estado.cambiar_confianza(grupo, objetivo - estado.confianza(grupo))
    return f"{grupo} = {valor:g}"


def _relacion(estado, args):
    valor = estado.cambiar_relacion(args[0], _numero(args[1]))
    return f"{args[0]} = {valor:g}"


def _flag(estado, args):
    accion, nombre = args[0].lower(), args[1]
    if accion == "poner":
        estado.poner_flag(nombre, permanente=len(args) > 2 and args[2].lower().startswith("perm"))
        return f"flag {nombre} activa" + (" (permanente)" if estado.es_permanente(nombre) else "")
    if accion == "quitar":
        return f"flag {nombre} quitada" if estado.quitar_flag(nombre) else f"flag {nombre} no se puede quitar (no existe o es permanente)"
    raise ValueError("flag: usa «poner» o «quitar».")


def _evento(estado, args):
    tipo, grupo = args[0], args[1]
    inv, mor, sec = (_numero(a) for a in args[2:5])
    nodo = estado.aplicar_evento(tipo, efectos={grupo: {"investigacion": inv, "moral": mor, "secundarios": sec}}, origen="debug")
    return f"evento {tipo!r} t={nodo.timestamp}: {grupo} {nodo.deltas.get(grupo, 0):+g} -> {estado.confianza(grupo):g}"


def _impactos(estado, args):
    nodos = estado.impactos().inorden()
    if not nodos:
        return "(sin impactos)"
    return "\n".join(f"t={n.timestamp} #{n.secuencia} {n.tipo} {n.deltas}" for n in nodos)


_COMANDOS = {
    "mostrar": _mostrar,
    "confianza": _confianza,
    "fijar_confianza": _fijar_confianza,
    "relacion": _relacion,
    "flag": _flag,
    "evento": _evento,
    "impactos": _impactos,
}

GRUPOS_VALIDOS = GRUPOS
