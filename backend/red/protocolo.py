# Protocolo v1 del modo online: JSON por líneas UTF-8 terminadas en "\n".
# Módulo PURO (solo stdlib). Todo dato que llega de la red pasa por `decodificar`, que valida
# tamaño, JSON estricto (sin NaN/Infinity ni claves duplicadas), profundidad, esquema y rangos.
# Nada de lo que llega se usa como ruta, modelo ni escena: aquí solo se obtienen datos tipados.
import json
import math

# ---------------------------------------------------------------------------
# Constantes de versión, límites y tiempos
# ---------------------------------------------------------------------------
PROTOCOLO_V = 1
JUEGO = "AlcaldeDigital"

DIR_C2H = "c2h"   # cliente -> anfitrión
DIR_H2C = "h2c"   # anfitrión -> cliente

MAX_LINEA_C2H = 4 * 1024      # tope de línea cliente -> anfitrión
MAX_LINEA_H2C = 16 * 1024     # tope de línea anfitrión -> cliente
MAX_LINEA_SALUDO = 8 * 1024   # el mensaje «hola» (saludo) puede ser algo mayor
MAX_PROFUNDIDAD = 5           # niveles de anidación admitidos en el JSON

MAX_CONEXIONES = 8
MAX_CONEXIONES_POR_IP = 2
MAX_JUGADORES = 4

T_HANDSHAKE = 5.0             # s para completar el saludo
T_LECTURA = 15.0              # s máximos esperando una línea completa
T_SILENCIO_PING = 10.0        # s sin ping/pos -> desconectado
GRACIA_RECONEXION = 90.0      # s reteniendo rol y reserva tras un corte

HZ_POS = 20                   # frecuencia máxima de «pos» del cliente
HZ_SNAP = 20                  # frecuencia de «snap» del anfitrión
HZ_SNAP_MIN = 15
HZ_LATIDO_POS = 2             # «pos» de latido aunque no cambie

LIMITE_MSG_SOSTENIDO = 60     # mensajes/s por conexión (ver limites.py)
LIMITE_MSG_RAFAGA = 120
LIMITES_POR_TIPO = {"pos": 30, "decision": 2, "saludo_rapido": 1, "iniciar": 2}  # msg/s por tipo

CODIGOS_RECHAZO = ("version", "sala_llena", "rol_tomado", "codigo_malo", "mundo_distinto",
                   "nombre_invalido", "expulsado", "lleno_de_conexiones")

# Vehículos online (T9): motivos admitidos en monta_no / desmontado (conjunto cerrado, nunca texto libre).
MOTIVOS_VEHICULO = frozenset({"ocupado", "lejos", "ya_montado", "no_existe", "fase", "dentro",
                              "desactivado", "desconectado", "bajada"})
N_VEHICULOS_MAX = 8

# Límites numéricos de coordenadas (el mundo es pequeño; evita valores absurdos)
COORD_MAX = 100000.0
ALTURA_MAX = 10000.0
RUMBO_MAX = 100000.0
VEL_MAX = 1000.0
ENTERO_MAX = 2 ** 63 - 1


class ErrorProtocolo(Exception):
    """Error al codificar/decodificar un mensaje de red.

    codigo: texto corto estable (para registros y tests).
    grave: True si el emisor debe ser desconectado (basura, desborde, JSON roto);
           False si basta con descartar el mensaje y contar una infracción.
    """

    def __init__(self, codigo, grave=False, detalle=""):
        super().__init__(f"{codigo}: {detalle}" if detalle else codigo)
        self.codigo = codigo
        self.grave = bool(grave)
        self.detalle = detalle


# ---------------------------------------------------------------------------
# Declaración del esquema
# ---------------------------------------------------------------------------
class Campo:
    """Describe un campo: clase, rango, largo máximo y si es obligatorio.

    clase: "int" | "num" (int o float finito) | "str" | "bool" | "lista_str" | "dic_num"
           | "lista_obj" | "obj".
    minimo/maximo: rango para int/num (inclusivo).
    largo: largo máximo de str, de cada str de lista_str, o nº máx. de elementos de listas;
           para dic_num es el nº máx. de claves.
    largo_item: largo máximo de cada cadena en lista_str / de cada clave en dic_num.
    hijo: dict nombre->Campo para "obj" y "lista_obj".
    opciones: conjunto de cadenas admitidas (str).
    """

    __slots__ = ("clase", "minimo", "maximo", "largo", "largo_item", "obligatorio",
                 "nulo", "hijo", "opciones")

    def __init__(self, clase, minimo=None, maximo=None, largo=None, largo_item=64,
                 obligatorio=True, nulo=False, hijo=None, opciones=None):
        self.clase = clase
        self.minimo = minimo
        self.maximo = maximo
        self.largo = largo
        self.largo_item = largo_item
        self.obligatorio = obligatorio
        self.nulo = nulo
        self.hijo = hijo
        self.opciones = opciones


def _i(minimo=0, maximo=ENTERO_MAX, **kw):
    return Campo("int", minimo, maximo, **kw)


def _n(minimo, maximo, **kw):
    return Campo("num", minimo, maximo, **kw)


def _s(largo, **kw):
    return Campo("str", largo=largo, **kw)


def _b(**kw):
    return Campo("bool", **kw)


_ID = _i(0, MAX_JUGADORES - 1)
_X = _n(-COORD_MAX, COORD_MAX)
_Y = _n(-ALTURA_MAX, ALTURA_MAX)
_R = _n(-RUMBO_MAX, RUMBO_MAX)
_V = _n(0.0, VEL_MAX)
_BANDERAS = _i(0, 255)
_HASH = _s(64)

_JUGADOR_SNAP = {"i": _ID, "x": _X, "z": _X, "y": _Y, "r": _R, "v": _V, "f": _BANDERAS}
_JUGADOR_SALA = {
    "id": _ID, "nombre": _s(40), "rol": _s(32, nulo=True), "listo": _b(),
    "conectado": _b(), "anfitrion": _b(),
}
_SPAWN = {"id": _ID, "x": _X, "z": _X, "y": _Y}
# i = índice del vehículo (0..7), k = tipo, p = jugador que lo conduce (ausente si está aparcado).
_VEHICULO_SNAP = {"i": _i(0, N_VEHICULOS_MAX - 1), "k": _s(32), "x": _X, "z": _X, "r": _R,
                  "p": _i(0, MAX_JUGADORES - 1, obligatorio=False)}

# Cada entrada: (direcciones admitidas, {campo: Campo}). La clave «t» la pone el codec.
ESQUEMAS = {
    "reto": ((DIR_H2C,), {"nonce": _s(64)}),
    "hola": ((DIR_C2H,), {
        "juego": _s(32), "v": _i(0, 1000), "nombre": _s(64),
        "huella_mundo": _HASH, "huella_contenido": _HASH, "prueba": _HASH,
        "token": _s(64, obligatorio=False),
    }),
    "bienvenida": ((DIR_H2C,), {
        "v": _i(0, 1000), "semilla": _i(-ENTERO_MAX, ENTERO_MAX),
        "huellas": Campo("obj", hijo={"mundo": _HASH, "contenido": _HASH}),
        "tu_id": _ID, "token": _s(64), "sala": _s(32),
    }),
    "rechazo": ((DIR_H2C,), {
        "codigo": _s(32, opciones=frozenset(CODIGOS_RECHAZO)), "texto": _s(200),
    }),
    "rol": ((DIR_C2H,), {"rol": _s(32)}),
    "listo": ((DIR_C2H,), {"listo": _b()}),
    # T8: el anfitrión-jugador pide pasar de la sala al juego (válido solo del id anfitrión)
    "iniciar": ((DIR_C2H,), {}),
    "sala": ((DIR_H2C,), {
        "jugadores": Campo("lista_obj", largo=MAX_JUGADORES, hijo=_JUGADOR_SALA),
        "roles_libres": Campo("lista_str", largo=MAX_JUGADORES, largo_item=32),
    }),
    "inicio": ((DIR_H2C,), {
        "cuenta": _i(0, 60),
        "spawns": Campo("lista_obj", largo=MAX_JUGADORES, hijo=_SPAWN),
        "mision": _s(64, nulo=True),
    }),
    "pos": ((DIR_C2H,), {
        "n": _i(0, 2 ** 31), "x": _X, "z": _X, "y": _Y, "r": _R, "v": _V,
        "f": _BANDERAS, "veh": _s(32, obligatorio=False),
    }),
    "snap": ((DIR_H2C,), {
        "n": _i(0, 2 ** 31), "tt": _n(0.0, 1e9),
        "jugadores": Campo("lista_obj", largo=MAX_JUGADORES, hijo=_JUGADOR_SNAP),
        "ind": Campo("dic_num", largo=16, largo_item=48, minimo=-1e6, maximo=1e6,
                     obligatorio=False),
        "veh": Campo("lista_obj", largo=8, hijo=_VEHICULO_SNAP, obligatorio=False),
    }),
    "corregir": ((DIR_H2C,), {"x": _X, "z": _X, "y": _Y, "seq": _i(0, 2 ** 31)}),
    "mision": ((DIR_H2C,), {
        "id": _s(64),
        "mano": Campo("lista_str", largo=8, largo_item=64),
        "hechas": Campo("lista_str", largo=16, largo_item=64),
    }),
    "interactuar": ((DIR_C2H,), {}),
    # T9 (vehículos online): el cliente pide montar el vehículo `veh` / bajar; el anfitrión decide.
    "montar": ((DIR_C2H,), {"veh": _i(0, N_VEHICULOS_MAX - 1)}),
    "bajar": ((DIR_C2H,), {}),
    "monta_ok": ((DIR_H2C,), {"veh": _i(0, N_VEHICULOS_MAX - 1)}),
    "monta_no": ((DIR_H2C,), {"motivo": _s(24, opciones=MOTIVOS_VEHICULO)}),
    "desmontado": ((DIR_H2C,), {"motivo": _s(24, opciones=MOTIVOS_VEHICULO)}),
    "ok": ((DIR_H2C,), {}),
    "rechazo_interactuar": ((DIR_H2C,), {"motivo": _s(120)}),
    "decision": ((DIR_C2H,), {
        "mision": _s(64), "noticia": _s(64), "tipo": _s(32), "n": _i(0, 2 ** 31),
    }),
    "ind": ((DIR_H2C,), {
        "valores": Campo("dic_num", largo=16, largo_item=48, minimo=-1e6, maximo=1e6),
        "autor": _ID,
        "deltas": Campo("dic_num", largo=16, largo_item=48, minimo=-1e6, maximo=1e6),
    }),
    "mision_cerrada": ((DIR_H2C,), {"id": _s(64), "siguiente": _s(64, nulo=True)}),
    "salir_edificio": ((DIR_C2H,), {}),
    "fin": ((DIR_H2C,), {
        "indicadores": Campo("dic_num", largo=16, largo_item=48, minimo=-1e6, maximo=1e6),
        "resumen": _s(1000),
    }),
    "ping": ((DIR_C2H, DIR_H2C), {"n": _i(0, 2 ** 31), "tt": _n(0.0, 1e9)}),
    "pong": ((DIR_C2H, DIR_H2C), {"n": _i(0, 2 ** 31), "tt": _n(0.0, 1e9)}),
    "jugador_entra": ((DIR_H2C,), {"id": _ID}),
    "jugador_sale": ((DIR_H2C,), {"id": _ID}),
    "jugador_desconectado": ((DIR_H2C,), {"id": _ID}),
    "jugador_reconectado": ((DIR_H2C,), {"id": _ID}),
    "adios": ((DIR_C2H,), {}),
    "sala_cerrada": ((DIR_H2C,), {}),
    "error": ((DIR_H2C,), {"motivo": _s(200)}),
    "saludo_rapido": ((DIR_C2H,), {"indice": _i(0, 15)}),
    "saludo": ((DIR_H2C,), {"id": _ID, "indice": _i(0, 15)}),   # reenvío del saludo rápido
}
# NOTA: en ping/pong y snap el campo de tiempo se llama «tt» en el esquema porque «t» está
# reservada para el tipo de mensaje (el diseño escribe «t» para ambos; aquí se desambigua).

# Mensajes que descartar con contrapresión (no críticos): nunca eventos.
MENSAJES_DESCARTABLES = frozenset({"pos", "snap"})


def mensajes_de(direccion):
    """Tipos de mensaje que puede enviar el emisor en `direccion`."""
    return frozenset(t for t, (dirs, _) in ESQUEMAS.items() if direccion in dirs)


def limite_linea(direccion, tipo=None):
    """Tope en bytes de una línea según la dirección (y el tipo, para «hola»)."""
    if direccion == DIR_H2C:
        return MAX_LINEA_H2C
    if tipo == "hola":
        return MAX_LINEA_SALUDO
    return MAX_LINEA_C2H


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
def _rechazar_constante(nombre):
    # parse_constant: se invoca para NaN, Infinity y -Infinity
    raise ErrorProtocolo("json_invalido", True, f"constante no permitida {nombre}")


def _sin_duplicados(pares):
    # object_pairs_hook: una clave repetida es ambigua y se rechaza
    d = {}
    for k, v in pares:
        if k in d:
            raise ErrorProtocolo("json_invalido", True, "clave duplicada")
        d[k] = v
    return d


def _profundidad(valor, limite):
    """True si el valor no supera `limite` niveles (iterativo: sin recursión)."""
    pila = [(valor, 1)]
    while pila:
        v, nivel = pila.pop()
        if isinstance(v, (dict, list)):
            if nivel > limite:
                return False
            hijos = v.values() if isinstance(v, dict) else v
            pila.extend((h, nivel + 1) for h in hijos)
    return True


def _es_num(x):
    # Estricto: int o float, jamás bool (bool es subclase de int)
    return (type(x) is int) or (type(x) is float)


def _validar_texto(valor, campo, ruta):
    if type(valor) is not str:
        raise ErrorProtocolo("tipo_invalido", False, ruta)
    if len(valor) > campo.largo:
        raise ErrorProtocolo("texto_largo", False, ruta)
    if campo.opciones is not None and valor not in campo.opciones:
        raise ErrorProtocolo("opcion_invalida", False, ruta)


def _validar_numero(valor, campo, ruta):
    if campo.clase == "int":
        if type(valor) is not int:
            raise ErrorProtocolo("tipo_invalido", False, ruta)
    elif not _es_num(valor):
        raise ErrorProtocolo("tipo_invalido", False, ruta)
    if type(valor) is float and not math.isfinite(valor):
        raise ErrorProtocolo("no_finito", False, ruta)
    if (campo.minimo is not None and valor < campo.minimo) or \
            (campo.maximo is not None and valor > campo.maximo):
        raise ErrorProtocolo("fuera_de_rango", False, ruta)


def _validar_dic(valor, esquema, ruta):
    """Valida un dict contra {campo: Campo}; rechaza claves desconocidas y faltantes."""
    if type(valor) is not dict:
        raise ErrorProtocolo("tipo_invalido", False, ruta)
    for clave in valor:
        if clave not in esquema:
            raise ErrorProtocolo("campo_desconocido", False, f"{ruta}{clave}")
    for nombre, campo in esquema.items():
        if nombre not in valor:
            if campo.obligatorio:
                raise ErrorProtocolo("campo_faltante", False, f"{ruta}{nombre}")
            continue
        _validar_valor(valor[nombre], campo, f"{ruta}{nombre}")


def _validar_valor(valor, campo, ruta):
    if valor is None:
        if campo.nulo:
            return
        raise ErrorProtocolo("tipo_invalido", False, ruta)
    c = campo.clase
    if c == "str":
        _validar_texto(valor, campo, ruta)
    elif c in ("int", "num"):
        _validar_numero(valor, campo, ruta)
    elif c == "bool":
        if type(valor) is not bool:
            raise ErrorProtocolo("tipo_invalido", False, ruta)
    elif c == "lista_str":
        if type(valor) is not list:
            raise ErrorProtocolo("tipo_invalido", False, ruta)
        if len(valor) > campo.largo:
            raise ErrorProtocolo("lista_larga", False, ruta)
        for k, s in enumerate(valor):
            if type(s) is not str or len(s) > campo.largo_item:
                raise ErrorProtocolo("tipo_invalido", False, f"{ruta}[{k}]")
    elif c == "dic_num":
        if type(valor) is not dict:
            raise ErrorProtocolo("tipo_invalido", False, ruta)
        if len(valor) > campo.largo:
            raise ErrorProtocolo("lista_larga", False, ruta)
        for k, n in valor.items():
            if len(k) > campo.largo_item:
                raise ErrorProtocolo("texto_largo", False, f"{ruta}.{k[:8]}")
            _validar_numero(n, Campo("num", campo.minimo, campo.maximo), f"{ruta}.{k[:8]}")
    elif c == "lista_obj":
        if type(valor) is not list:
            raise ErrorProtocolo("tipo_invalido", False, ruta)
        if len(valor) > campo.largo:
            raise ErrorProtocolo("lista_larga", False, ruta)
        for k, el in enumerate(valor):
            _validar_dic(el, campo.hijo, f"{ruta}[{k}].")
    elif c == "obj":
        _validar_dic(valor, campo.hijo, f"{ruta}.")
    else:  # esquema mal declarado: error de programación
        raise ErrorProtocolo("esquema_invalido", True, c)


def validar(mensaje, direccion):
    """Valida un mensaje ya parseado (dict con clave «t») y lo devuelve tal cual."""
    if type(mensaje) is not dict:
        raise ErrorProtocolo("no_es_objeto", True)
    tipo = mensaje.get("t")
    if type(tipo) is not str:
        raise ErrorProtocolo("falta_t", False)
    if tipo not in ESQUEMAS:
        raise ErrorProtocolo("tipo_desconocido", False, tipo[:32])
    dirs, esquema = ESQUEMAS[tipo]
    if direccion not in dirs:
        raise ErrorProtocolo("direccion_invalida", False, tipo)
    cuerpo = {k: v for k, v in mensaje.items() if k != "t"}
    if not _profundidad(cuerpo, MAX_PROFUNDIDAD):
        raise ErrorProtocolo("profundidad", True)
    _validar_dic(cuerpo, esquema, "")
    return mensaje


# ---------------------------------------------------------------------------
# Codec
# ---------------------------------------------------------------------------
def codificar(mensaje, direccion=None):
    """Serializa un mensaje a bytes JSON terminados en «\\n».

    Con `direccion` también valida el esquema y aplica el tope de esa dirección;
    sin ella solo aplica el tope mayor (H2C). Lanza ErrorProtocolo si algo falla.
    """
    if direccion is not None:
        validar(mensaje, direccion)
    try:
        texto = json.dumps(mensaje, separators=(",", ":"), allow_nan=False,
                           ensure_ascii=True, sort_keys=False)
    except (ValueError, TypeError) as e:
        raise ErrorProtocolo("no_serializable", False, str(e)[:60])
    datos = texto.encode("ascii") + b"\n"
    tope = limite_linea(direccion or DIR_H2C, mensaje.get("t") if isinstance(mensaje, dict) else None)
    if len(datos) > tope:
        raise ErrorProtocolo("demasiado_grande", False, f"{len(datos)}>{tope}")
    return datos


def decodificar(linea, direccion):
    """Convierte una línea recibida (bytes o str) en un dict validado.

    Orden: tope de tamaño -> UTF-8 -> JSON estricto -> profundidad -> esquema.
    """
    if direccion not in (DIR_C2H, DIR_H2C):
        raise ErrorProtocolo("direccion_invalida", True, str(direccion)[:16])
    if isinstance(linea, str):
        try:
            linea = linea.encode("utf-8")
        except UnicodeEncodeError:
            raise ErrorProtocolo("utf8", True)
    elif not isinstance(linea, (bytes, bytearray)):
        raise ErrorProtocolo("tipo_invalido", True, "linea")
    linea = bytes(linea)
    # El tamaño de una línea cuenta su «\n» final, aunque quien llama no lo incluya
    tam = len(linea) + (0 if linea.endswith(b"\n") else 1)
    # Tope duro antes de parsear (el de «hola» es el mayor del sentido C2H)
    duro = MAX_LINEA_H2C if direccion == DIR_H2C else MAX_LINEA_SALUDO
    if tam > duro:
        raise ErrorProtocolo("demasiado_grande", True, str(tam))
    if linea.endswith(b"\n"):
        linea = linea[:-1]
    if b"\n" in linea or not linea:
        raise ErrorProtocolo("json_invalido", True, "linea vacia o con salto")
    try:
        texto = linea.decode("utf-8")
    except UnicodeDecodeError:
        raise ErrorProtocolo("utf8", True)
    demasiado = direccion == DIR_C2H and tam > MAX_LINEA_C2H
    try:
        mensaje = json.loads(texto, parse_constant=_rechazar_constante,
                             object_pairs_hook=_sin_duplicados)
    except ErrorProtocolo:
        if demasiado:       # una línea sobredimensionada y rota: se informa el tamaño
            raise ErrorProtocolo("demasiado_grande", True, str(tam))
        raise
    except RecursionError:
        raise ErrorProtocolo("profundidad", True)
    except ValueError:
        raise ErrorProtocolo("demasiado_grande" if demasiado else "json_invalido", True)
    # Tope fino por tipo: solo «hola» puede pasar de 4 KiB en sentido C2H
    if demasiado:
        if type(mensaje) is not dict or mensaje.get("t") != "hola":
            raise ErrorProtocolo("demasiado_grande", True, str(tam))
    return validar(mensaje, direccion)
