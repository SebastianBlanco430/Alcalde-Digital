# Teléfono en grande y tarjetas de primera vez (modelo puro, serializable, sin ursina). La vista vive en
# frontend/registro_telefono_grande.py; aquí solo están las banderas, los datos y lo que se guarda.
#
#   CANALES. backend/datos/canales_avisos.json dice en qué «pantalla» de red social se ve cada aviso de la bandeja de
#   Civitas (tecla L) o dilema (tecla K): dm, muro, rectificar, grupo, cadena, notificaciones o feed, y en qué PARTE de esa
#   pantalla se dibuja cada elemento marcable («zonas»). Un caso que no está en el JSON se ve en el panel de texto de
#   siempre. Los JSON de contenido (eventos_digitales, rectificaciones, dilemas_extra) NO se tocan: la huella de sala y lo
#   que usan otros módulos no cambian.
#   EXPLICACIONES. backend/datos/explicaciones_avisos.json: la tarjeta corta que sale ANTES del teléfono la primera vez que
#   llega cada tipo principal (sospechoso, publicar, rectificar, acoso, red, feed) en esta PARTIDA.
#   VISTOS. FlujoConAvisosVistos guarda qué tipos ya se explicaron en la clave OPCIONAL «avisos_vistos» del guardado
#   (partida.json). Un guardado anterior no la trae y carga igual: las tarjetas salen al verlas por primera vez.
#
# Banderas (se leen en cada llamada; 0 / false / no / off apagan):
#   ALCALDE_TELEFONO_GRANDE   1 por defecto; 0 = el panel de texto de siempre para todo
#   ALCALDE_TARJETAS_AVISOS   1 por defecto; 0 = sin tarjetas de primera vez (el teléfono sigue)
# Solo modo local: el flujo en línea no pasa por main.crear_flujo y los paneles no hacen nada con escena.online.
#
#   cargar_canales(ruta=None)        -> {"casos": {id: canal}, "comunes": {elemento_id: zona}}; ValueError si no cuadra
#   cargar_explicaciones(ruta=None)  -> {tipo: {"titulo", "texto", "dibujos"}}; ValueError si no cuadra
#   canal_de(canales, ident)         -> dict del canal o None (sin entrada = panel de antes)
#   tipo_principal(tipo, canal)      -> «sospechoso» | «publicar» | «rectificar» | «acoso» | «red» | «feed» | None
#   envolver(flujo)                  -> FlujoConAvisosVistos o el mismo flujo

import json
import os
import sys
from pathlib import Path

TELEFONO_GRANDE = True
TARJETAS_AVISOS = True

_DATOS = Path(__file__).resolve().parent.parent / "datos"
RUTA_CANALES = _DATOS / "canales_avisos.json"
RUTA_EXPLICACIONES = _DATOS / "explicaciones_avisos.json"
VERSION = 1

CANALES = ("dm", "muro", "rectificar", "grupo", "cadena", "notificaciones", "feed")
# zonas que sabe dibujar cada canal; «detalle» (una fila de «Otros detalles») vale en todos
ZONAS = {
    "dm": ("cabecera", "burbuja", "detalle"),
    "muro": ("foto", "texto", "ubicacion", "etiquetas", "detalle"),
    "rectificar": ("texto", "contador", "fuente", "detalle"),
    "grupo": ("detalle",),
    "cadena": ("detalle",),
    "notificaciones": ("detalle",),
    "feed": ("detalle",),
}
# «red»: los dilemas que pasan en tus grupos o tu muro sin ser ciberacoso (reenviar, publicar, ayudar, desconectarse)
TIPOS = ("sospechoso", "publicar", "rectificar", "acoso", "red", "feed")
MAX_TEXTO = 300
MAX_MENSAJES = 6
MAX_DIBUJOS = 3
MAX_RESPUESTAS = 3

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def _bandera(nombre, constante):
    valor = os.environ.get(nombre, "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(constante)


def telefono_grande_activo():
    return _bandera("ALCALDE_TELEFONO_GRANDE", TELEFONO_GRANDE)


def tarjetas_activas():
    return _bandera("ALCALDE_TARJETAS_AVISOS", TARJETAS_AVISOS)


# -- Datos ------------------------------------------------------------------------------------------------------------

def _leer(ruta, nombre):
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{nombre}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"{nombre}: JSON inválido (línea {error.lineno}): {error.msg}") from None
    if not isinstance(datos, dict) or datos.get("version") != VERSION:
        raise ValueError(f"{nombre}: formato desconocido (se esperaba version {VERSION}).")
    return datos


def _texto(valor, nombre, obligatorio=True):
    if valor is None and not obligatorio:
        return ""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{nombre}: falta el texto.")
    if len(valor.strip()) > MAX_TEXTO:
        raise ValueError(f"{nombre}: el texto pasa de {MAX_TEXTO} caracteres.")
    return valor.strip()


def _numero(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0.0 <= float(valor) <= 1.0:
        raise ValueError(f"{nombre}: debe ser un número entre 0 y 1.")
    return float(valor)


# Una zona: {"zona": ..., "fragmento"?: texto literal del mensaje, "x"/"y"?: posición relativa en la foto (0..1)}.
def _zona(crudo, nombre, canal):
    if isinstance(crudo, str):
        crudo = {"zona": crudo}
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto o el nombre de la zona.")
    zona = crudo.get("zona")
    validas = ZONAS[canal] if canal is not None else tuple({z for zs in ZONAS.values() for z in zs})
    if zona not in validas:
        raise ValueError(f"{nombre}: zona {zona!r} desconocida para el canal {canal!r}.")
    salida = {"zona": zona}
    if crudo.get("fragmento") is not None:
        salida["fragmento"] = _texto(crudo["fragmento"], f"{nombre}.fragmento")
    if crudo.get("x") is not None or crudo.get("y") is not None:
        salida["x"] = _numero(crudo.get("x"), f"{nombre}.x")
        salida["y"] = _numero(crudo.get("y"), f"{nombre}.y")
    return salida


def _mensajes(crudo, nombre):
    if crudo is None:
        return []
    if not isinstance(crudo, list) or len(crudo) > MAX_MENSAJES:
        raise ValueError(f"{nombre}: «mensajes» debe ser una lista de hasta {MAX_MENSAJES}.")
    salida = []
    for i, m in enumerate(crudo):
        if not isinstance(m, dict):
            raise ValueError(f"{nombre}.mensajes[{i}]: se esperaba un objeto.")
        foto = m.get("foto")
        if foto is not None and not isinstance(foto, str):
            raise ValueError(f"{nombre}.mensajes[{i}].foto: debe ser el nombre de una foto.")
        salida.append({"autor": _texto(m.get("autor"), f"{nombre}.mensajes[{i}].autor"),
                       "texto": _texto(m.get("texto"), f"{nombre}.mensajes[{i}].texto"),
                       "foto": foto or "", "reenviado": bool(m.get("reenviado", False))})
    return salida


# Lo que se ve en el teléfono tras elegir una opción: {"mio": texto, "sistema": texto, "respuestas": [{autor, texto}],
# "publica": la opción deja la publicación subida a tu muro (si no, el muro la muestra como borrador)}.
def _resultado(crudo, nombre):
    if isinstance(crudo, str):
        crudo = {"sistema": crudo}
    if not isinstance(crudo, dict):
        raise ValueError(f"{nombre}: se esperaba un objeto o un texto.")
    respuestas = crudo.get("respuestas") or []
    if not isinstance(respuestas, list) or len(respuestas) > MAX_RESPUESTAS:
        raise ValueError(f"{nombre}: «respuestas» debe ser una lista de hasta {MAX_RESPUESTAS}.")
    return {"mio": _texto(crudo.get("mio"), f"{nombre}.mio", obligatorio=False),
            "sistema": _texto(crudo.get("sistema"), f"{nombre}.sistema", obligatorio=False),
            "respuestas": _mensajes(respuestas, f"{nombre}.respuestas"),
            "publica": bool(crudo.get("publica", False))}


def _canal(ident, crudo):
    if not isinstance(crudo, dict):
        raise ValueError(f"{ident}: se esperaba un objeto.")
    canal = crudo.get("canal")
    if canal not in CANALES:
        raise ValueError(f"{ident}: canal {canal!r} desconocido (se esperaba uno de {CANALES}).")
    zonas = crudo.get("zonas") or {}
    if not isinstance(zonas, dict):
        raise ValueError(f"{ident}: «zonas» debe ser un objeto.")
    comentarios = crudo.get("comentarios") or {}
    if not isinstance(comentarios, dict):
        raise ValueError(f"{ident}: «comentarios» debe ser un objeto.")
    resultados = crudo.get("resultados") or {}
    if not isinstance(resultados, dict):
        raise ValueError(f"{ident}: «resultados» debe ser un objeto.")
    tarjeta = crudo.get("tarjeta")
    if tarjeta is not None and tarjeta not in TIPOS:
        raise ValueError(f"{ident}: tarjeta {tarjeta!r} desconocida (se esperaba una de {TIPOS}).")
    reenvios = crudo.get("reenvios", 0)
    if isinstance(reenvios, bool) or not isinstance(reenvios, int) or reenvios < 0:
        raise ValueError(f"{ident}: «reenvios» debe ser un entero >= 0.")
    return {
        "canal": canal,
        "zonas": {str(k): _zona(v, f"{ident}.zonas.{k}", canal) for k, v in zonas.items()},
        "nombre_grupo": _texto(crudo.get("nombre_grupo"), f"{ident}.nombre_grupo", obligatorio=False),
        "mensajes": _mensajes(crudo.get("mensajes"), ident),
        "comentarios": {str(k): _texto(v, f"{ident}.comentarios.{k}") for k, v in comentarios.items()},
        "resultados": {str(k): _resultado(v, f"{ident}.resultados.{k}") for k, v in resultados.items()},
        "reenvios": reenvios,
        "tarjeta": tarjeta,
        "foto": _texto(crudo.get("foto"), f"{ident}.foto", obligatorio=False),
        "leyenda": _texto(crudo.get("leyenda"), f"{ident}.leyenda", obligatorio=False),
        "ubicacion": _texto(crudo.get("ubicacion") or None, f"{ident}.ubicacion", obligatorio=False),
        "etiquetas": _texto(crudo.get("etiquetas") or None, f"{ident}.etiquetas", obligatorio=False),
    }


def cargar_canales(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_CANALES
    datos = _leer(ruta, ruta.name)
    casos = datos.get("casos")
    if not isinstance(casos, dict) or not casos:
        raise ValueError(f"{ruta.name}: falta «casos».")
    comunes = datos.get("comunes") or {}
    if not isinstance(comunes, dict):
        raise ValueError(f"{ruta.name}: «comunes» debe ser un objeto.")
    return {"casos": {str(k): _canal(str(k), v) for k, v in casos.items()},
            "comunes": {str(k): _zona(v, f"comunes.{k}", None) for k, v in comunes.items()}}


def cargar_explicaciones(ruta=None):
    ruta = Path(ruta) if ruta is not None else RUTA_EXPLICACIONES
    datos = _leer(ruta, ruta.name)
    tarjetas = datos.get("tarjetas")
    if not isinstance(tarjetas, dict) or set(tarjetas) != set(TIPOS):
        raise ValueError(f"{ruta.name}: «tarjetas» debe traer exactamente {TIPOS}.")
    salida = {}
    for tipo in TIPOS:
        crudo = tarjetas[tipo]
        if not isinstance(crudo, dict):
            raise ValueError(f"{ruta.name}/{tipo}: se esperaba un objeto.")
        dibujos = crudo.get("dibujos") or []
        if not isinstance(dibujos, list) or not 1 <= len(dibujos) <= MAX_DIBUJOS or not all(isinstance(d, str) for d in dibujos):
            raise ValueError(f"{ruta.name}/{tipo}: «dibujos» debe ser una lista de 1 a {MAX_DIBUJOS} nombres.")
        salida[tipo] = {"titulo": _texto(crudo.get("titulo"), f"{tipo}.titulo"),
                        "texto": _texto(crudo.get("texto"), f"{tipo}.texto"), "dibujos": list(dibujos)}
    return salida


def canal_de(canales, ident):
    if not canales or ident is None:
        return None
    return canales["casos"].get(str(ident))


# Zona de un elemento: la del caso, si no la común (p. ej. «personal», el dato que añade habitos_digitales.personalizar),
# si no «detalle». Una zona que el canal no sabe dibujar también cae en «detalle».
def zona_de(canales, canal, elemento_id):
    zona = canal["zonas"].get(elemento_id) if canal else None
    if zona is None and canales:
        zona = canales["comunes"].get(elemento_id)
    if zona is None or (canal and zona["zona"] not in ZONAS[canal["canal"]]):
        return {"zona": "detalle"}
    return zona


def tipo_principal(tipo, canal):
    """El tipo de tarjeta de primera vez de un aviso. `tipo`: el del evento de la bandeja («estafa», «publicar»,
    «rectificar»), «dilema» o «feed». Sin canal no hay teléfono y tampoco tarjeta. Si el canal dice su «tarjeta», esa."""
    if tipo == "feed":
        return "feed"
    if canal is None:
        return None
    if canal.get("tarjeta"):
        return canal["tarjeta"]
    nombre = canal["canal"]
    if nombre in ("grupo", "cadena"):
        return "acoso"
    if nombre == "dm" or tipo == "estafa":
        return "sospechoso"
    if nombre == "muro" or tipo == "publicar":
        return "publicar"
    if nombre == "rectificar" or tipo == "rectificar":
        return "rectificar"
    if tipo == "dilema" or nombre == "notificaciones":
        return "red"
    return None


# -- Tipos ya explicados ----------------------------------------------------------------------------------------------

class AvisosVistos:
    """Conjunto de tipos principales ya explicados en esta partida."""

    def __init__(self, tipos=()):
        self._tipos = {t for t in tipos if t in TIPOS}

    def visto(self, tipo):
        return tipo in self._tipos

    def marcar(self, tipo):
        if tipo in TIPOS:
            self._tipos.add(tipo)

    def a_lista(self):
        return sorted(self._tipos)

    @classmethod
    def desde_lista(cls, crudo):
        if not isinstance(crudo, list):
            raise ValueError("«avisos_vistos» debe ser una lista.")
        return cls(t for t in crudo if isinstance(t, str))


_PROPIOS = ("_flujo", "avisos_vistos")


class FlujoConAvisosVistos:
    """Envoltorio fino: solo añade `avisos_vistos` y su clave opcional en el guardado. El resto se delega."""

    def __init__(self, flujo):
        self._flujo = flujo
        self.avisos_vistos = AvisosVistos()

    def tiempo_a_dict(self):
        datos = self._flujo.tiempo_a_dict()
        datos["avisos_vistos"] = self.avisos_vistos.a_lista()
        return datos

    def restaurar_tiempo(self, datos):
        self._flujo.restaurar_tiempo(datos)
        crudo = datos.get("avisos_vistos") if isinstance(datos, dict) else None
        self.avisos_vistos = AvisosVistos()
        if crudo is None:            # guardado anterior a las tarjetas: se explican al verlas
            return
        try:
            self.avisos_vistos = AvisosVistos.desde_lista(crudo)
        except ValueError as error:
            print(f"[telefono] «avisos_vistos» del guardado no se pudo leer ({error}); se empieza de cero", file=sys.stderr)

    def __getattr__(self, nombre):
        if nombre.startswith("__") or nombre in _PROPIOS:
            raise AttributeError(nombre)
        return getattr(self._flujo, nombre)


# Lo que llama main.crear_flujo. Sin bandera o sin guardado de tiempo devuelve `flujo` tal cual (nunca impide jugar).
def envolver(flujo):
    if not telefono_grande_activo() or not tarjetas_activas():
        return flujo
    if not callable(getattr(flujo, "tiempo_a_dict", None)) or not callable(getattr(flujo, "restaurar_tiempo", None)):
        return flujo
    return FlujoConAvisosVistos(flujo)
