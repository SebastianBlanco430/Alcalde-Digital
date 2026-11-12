# Carga y validación de los niveles de parkour (JSON en backend/datos/parkour/*.json) -> Nivel de
# backend/logica/parkour_calculos.py. Lógica pura, sin ursina. Todo error de datos es un ValueError en
# español que nombra el nivel y el campo, para arreglar el JSON sin depurar.

import json
import math
import re
from pathlib import Path

from backend.logica.parkour_calculos import (Arista, Interruptor, MEDALLAS, Nivel, Plataforma, TIPOS,
                                            ruta_optima)

CARPETA = Path(__file__).resolve().parent / "parkour"
TEMAS = ("corrupto", "digital")
LIMITE_XZ = 5000.0           # |x|, |z| máximos (m): evita rejillas/mallas de tamaño absurdo en el frontend
LIMITE_Y = 1000.0            # |y| máximo (m)
ID_VALIDO = re.compile(r"[A-Za-z0-9_]+")
CAMPOS_PUNTUACION = ("maximo", "tiempo_referencia_s", "peso_tiempo", "peso_eficiencia")


def _falla(nivel, mensaje):
    raise ValueError(f"Nivel de parkour {nivel!r}: {mensaje}")


def _numero(nivel, valor, campo, minimo=None, maximo=None):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        _falla(nivel, f"{campo} debe ser un número (llegó {valor!r}).")
    if not math.isfinite(valor):
        _falla(nivel, f"{campo} debe ser un número finito (llegó {valor!r}).")
    if minimo is not None and valor < minimo:
        _falla(nivel, f"{campo} debe ser >= {minimo} (llegó {valor!r}).")
    if maximo is not None and valor > maximo:
        _falla(nivel, f"{campo} debe ser <= {maximo} (llegó {valor!r}).")
    return float(valor)


def _coord(nivel, valor, campo, limite=LIMITE_XZ):
    return _numero(nivel, valor, campo, minimo=-limite, maximo=limite)


def _texto(nivel, valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        _falla(nivel, f"{campo} debe ser un texto no vacío.")
    return valor.strip()


def _plataforma(nivel, d):
    id_p = _texto(nivel, d.get("id"), "plataforma.id")
    tipo = d.get("tipo", "fija")
    if tipo not in TIPOS:
        _falla(nivel, f"plataforma {id_p!r}: tipo {tipo!r} desconocido; usa {TIPOS}.")
    movimiento = d.get("movimiento")
    if tipo == "movil":
        if not isinstance(movimiento, dict) or len(movimiento.get("eje", ())) != 3:
            _falla(nivel, f"plataforma {id_p!r}: una móvil necesita movimiento {{eje:[dx,dy,dz], periodo}}.")
        _numero(nivel, movimiento.get("periodo", 4.0), f"{id_p}.movimiento.periodo", minimo=0.5)
        movimiento = {"eje": tuple(_numero(nivel, v, f"{id_p}.movimiento.eje") for v in movimiento["eje"]),
                      "periodo": float(movimiento.get("periodo", 4.0)), "fase": float(movimiento.get("fase", 0.0))}
    else:
        movimiento = None
    return Plataforma(
        id=id_p, x=_coord(nivel, d.get("x"), f"{id_p}.x"), y=_coord(nivel, d.get("y"), f"{id_p}.y", LIMITE_Y),
        z=_coord(nivel, d.get("z"), f"{id_p}.z"),
        ancho=_numero(nivel, d.get("ancho"), f"{id_p}.ancho", minimo=0.5),
        fondo=_numero(nivel, d.get("fondo"), f"{id_p}.fondo", minimo=0.5),
        tipo=tipo, movimiento=movimiento,
        aviso_s=_numero(nivel, d.get("aviso_s", 1.0), f"{id_p}.aviso_s", minimo=0.1),
        oculta_s=_numero(nivel, d.get("oculta_s", 2.0), f"{id_p}.oculta_s", minimo=0.1),
        requiere=d.get("requiere"), checkpoint=bool(d.get("checkpoint", False)))


# Convierte un dict (el JSON ya leído) en Nivel validado. ValueError si algo no cuadra.
def nivel_desde_dict(datos):
    if not isinstance(datos, dict):
        raise ValueError("Nivel de parkour: se esperaba un objeto JSON.")
    nid = _texto("?", datos.get("id"), "id")
    plataformas = {}
    for d in datos.get("plataformas") or []:
        p = _plataforma(nid, d)
        if p.id in plataformas:
            _falla(nid, f"plataforma {p.id!r} repetida.")
        plataformas[p.id] = p
    if not plataformas:
        _falla(nid, "no tiene plataformas.")
    inicio = _texto(nid, datos.get("inicio"), "inicio")
    meta = _texto(nid, datos.get("meta"), "meta")
    for nombre, valor in (("inicio", inicio), ("meta", meta)):
        if valor not in plataformas:
            _falla(nid, f"{nombre} {valor!r} no es una plataforma.")
    if inicio == meta:
        _falla(nid, "inicio y meta no pueden ser la misma plataforma.")
    if plataformas[inicio].requiere or plataformas[inicio].tipo != "fija":
        _falla(nid, "la plataforma de inicio debe ser fija y sin interruptor.")
    tema = datos.get("tema", "corrupto")
    if tema not in TEMAS:
        _falla(nid, f"tema {tema!r} desconocido; usa {TEMAS}.")

    interruptores = {}
    for d in datos.get("interruptores") or []:
        id_i = _texto(nid, d.get("id"), "interruptor.id")
        if id_i in interruptores:
            _falla(nid, f"interruptor {id_i!r} repetido.")
        activa = tuple(d.get("activa") or ())
        for destino in activa:
            if destino not in plataformas:
                _falla(nid, f"interruptor {id_i!r} activa {destino!r}, que no es una plataforma.")
            if plataformas[destino].requiere != id_i:
                _falla(nid, f"la plataforma {destino!r} debe declarar requiere={id_i!r} (lo activa ese interruptor).")
        duracion = d.get("duracion_s")
        interruptores[id_i] = Interruptor(
            id=id_i, x=_coord(nid, d.get("x"), f"{id_i}.x"), y=_coord(nid, d.get("y"), f"{id_i}.y", LIMITE_Y),
            z=_coord(nid, d.get("z"), f"{id_i}.z"), activa=activa,
            radio=_numero(nid, d.get("radio", 0.9), f"{id_i}.radio", minimo=0.2),
            duracion_s=None if duracion is None else _numero(nid, duracion, f"{id_i}.duracion_s", minimo=1.0))
    for p in plataformas.values():
        if p.requiere is not None and p.requiere not in interruptores:
            _falla(nid, f"plataforma {p.id!r} requiere {p.requiere!r}, que no es un interruptor.")

    aristas = []
    for d in datos.get("aristas") or []:
        a, b = d.get("desde"), d.get("hasta")
        for extremo in (a, b):
            if extremo not in plataformas:
                _falla(nid, f"arista {a!r}->{b!r}: {extremo!r} no es una plataforma.")
        riesgo = d.get("riesgo", 0)
        if isinstance(riesgo, bool) or not isinstance(riesgo, int) or riesgo < 0:
            _falla(nid, f"arista {a!r}->{b!r}: riesgo debe ser un entero >= 0.")
        aristas.append(Arista(a, b, _numero(nid, d.get("coste"), f"arista {a}->{b}.coste", minimo=0.01), riesgo))

    puntuacion = datos.get("puntuacion") or {}
    for campo in CAMPOS_PUNTUACION:
        _numero(nid, puntuacion.get(campo), f"puntuacion.{campo}", minimo=0.0)
    if puntuacion["tiempo_referencia_s"] <= 0:
        _falla(nid, "puntuacion.tiempo_referencia_s debe ser > 0.")
    medallas = datos.get("medallas") or {}
    previo = None
    for nombre in MEDALLAS:
        if nombre not in medallas:
            _falla(nid, f"falta la medalla {nombre!r} (umbral de puntos).")
        umbral = _numero(nid, medallas[nombre], f"medallas.{nombre}", minimo=0.0)
        if previo is not None and umbral <= previo:
            _falla(nid, "los umbrales de medalla deben ser crecientes (bronce < plata < oro).")
        previo = umbral
    recompensa = datos.get("recompensa") or {}
    if recompensa.get("evidencia") is not None:
        _texto(nid, recompensa["evidencia"], "recompensa.evidencia")
    if recompensa.get("caso") is not None:          # caso al que pertenece la evidencia (para el Archivo de casos)
        _texto(nid, recompensa["caso"], "recompensa.caso")
    pedida = recompensa.get("requiere_medalla")
    if pedida is not None and pedida not in MEDALLAS:
        _falla(nid, f"recompensa.requiere_medalla {pedida!r} desconocida; usa {MEDALLAS} o null.")

    nivel = Nivel(
        id=nid, nombre=str(datos.get("nombre", nid)), tema=tema, inicio=inicio, meta=meta,
        plataformas=plataformas, aristas=tuple(aristas), interruptores=interruptores,
        y_muerte=_numero(nid, datos.get("y_muerte", -8.0), "y_muerte", minimo=-LIMITE_Y, maximo=LIMITE_Y),
        penalizacion_caida_s=_numero(nid, datos.get("penalizacion_caida_s", 3.0), "penalizacion_caida_s", minimo=0.0),
        puntuacion=dict(puntuacion), medallas={k: float(v) for k, v in medallas.items()},
        recompensa=dict(recompensa), descripcion=str(datos.get("descripcion", "")))
    if ruta_optima(nivel)[0] is None:
        _falla(nid, "no hay camino de inicio a meta en las aristas.")
    return nivel


# Ids de los niveles disponibles (nombre de archivo sin .json), ordenados.
def listar_niveles(carpeta=None):
    return sorted(p.stem for p in Path(carpeta or CARPETA).glob("*.json"))


# Carga un nivel por id. ValueError si no existe o es inválido.
def cargar_nivel(nivel_id, carpeta=None):
    if not isinstance(nivel_id, str) or not ID_VALIDO.fullmatch(nivel_id):
        raise ValueError(f"Nivel de parkour {nivel_id!r}: id inválido (solo letras, números y guion bajo).")
    ruta = Path(carpeta or CARPETA) / f"{nivel_id}.json"
    if not ruta.is_file():
        raise ValueError(f"Nivel de parkour {nivel_id!r} inexistente; disponibles: {listar_niveles(carpeta)}.")
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Nivel de parkour {nivel_id!r}: JSON inválido ({error}).") from error
    return nivel_desde_dict(datos)
