# Registro de las CONSECUENCIAS en el mundo (Ola 3, subagente D). frontend/extensiones.py llama a registrar(); no se
# edita main.py. Cuelga del GameState de la partida (se lee de `escena_mundo.flujo` en el momento de uso: None en línea
# o con ALCALDE_GAMESTATE=0, y entonces todo queda inerte) tres cosas:
#   1. NPC clave con diálogo reactivo (frontend/npc_reactivo.py + dialogo_ui.py): se crean en el ancla de
#      backend/datos/npc_clave.json y se registran como Interaccion de la economía (E cerca = hablar).
#   2. Seu Zé (frontend/vendedor_calle.py) reacciona a la confianza: tras comprar añade su frase al aviso.
#   3. Vigilancia policial en el minimapa (backend/logica/vigilancia.py): una FUENTE del registro del minimapa
#      (frontend/minimapa_calculos.registro) que muestra los NPC clave como marcadores `npc` y, según la confianza de la
#      policía, zonas restringida/vigilancia/segura y el marcador de ayuda. Se reevalúa como mucho cada `refresco_s`
#      (backend/datos/vigilancia.json), no en cada sondeo del minimapa.
#
# Se apaga con ALCALDE_CONSECUENCIAS=0 (economia_config.CONSECUENCIAS) o con ALCALDE_GAMESTATE=0. Un fallo al instalar
# se avisa por stderr y NO tumba el juego. Este módulo no importa ursina al cargarse (lo hacen npc_reactivo/dialogo_ui).

import sys
import time

from backend.datos import npc_clave_loader
from backend.logica import dialogos, vigilancia
from frontend import economia_config as cfg
from frontend import minimapa_calculos as mm

FUENTE_MINIMAPA = "consecuencias"
_estado = {"proveedor": None}


def _aviso(texto):
    print(f"[consecuencias] {texto}", file=sys.stderr)


# Proveedor para RegistroMinimapa.registrar_fuente: () -> (marcadores, zonas). `presentes`: [(NpcClave, x, z)] de los NPC
# que existen en el mundo. `resolver(ancla) -> (x, z, rumbo)` coloca las anclas del JSON en el mundo (ValueError si no
# se puede: ese elemento se omite, una sola vez). Recalcula como mucho cada config.refresco_s (o al cambiar de partida).
def crear_proveedor(config, presentes, obtener_gs, resolver, reloj=time.monotonic):
    posiciones = {}
    cache = {"gs": None, "t": None, "res": ([], [])}

    def donde(elemento):
        if elemento.id not in posiciones:
            try:
                x, z, _ = resolver(elemento.ancla)
                posiciones[elemento.id] = (x, z)
            except (ValueError, KeyError, AttributeError) as error:
                _aviso(f"elemento {elemento.id!r} sin ancla en este mundo: {error}")
                posiciones[elemento.id] = None
        return posiciones[elemento.id]

    def construir(gs):
        marcadores = [mm.MarcadorMinimapa("npc", x, z, id=f"npc-{n.id}", etiqueta=n.nombre) for n, x, z in presentes]
        zonas = []
        for e in vigilancia.activos(config, gs):
            pos = donde(e)
            if pos is None:
                continue
            if e.clase == "zona":
                zonas.append(mm.ZonaMinimapa.rectangulo(e.id, pos[0], pos[1], e.ancho, e.fondo, tipo=e.tipo, etiqueta=e.etiqueta))
            else:
                marcadores.append(mm.MarcadorMinimapa(e.tipo, pos[0], pos[1], id=e.id, etiqueta=e.etiqueta))
        return marcadores, zonas

    def proveedor():
        gs = obtener_gs()
        if gs is None:
            cache.update(gs=None, t=None, res=([], []))
            return cache["res"]
        ahora = reloj()
        if cache["gs"] is gs and cache["t"] is not None and ahora - cache["t"] < config.refresco_s:
            return cache["res"]
        cache.update(gs=gs, t=ahora, res=construir(gs))
        return cache["res"]

    return proveedor


# Frase corta de un NPC según el GameState (para el aviso de Seu Zé); "" si no hay GameState o nada que decir.
def frase_de(clave, obtener_gs, catalogo):
    gs = obtener_gs()
    if gs is None:
        return ""
    return dialogos.elegir(clave, gs, catalogo).comentario


def _instalar(conexion, escena_mundo):
    npcs = npc_clave_loader.cargar_npcs()
    catalogo = dialogos.cargar()
    config = vigilancia.cargar()
    obtener_gs = lambda: getattr(escena_mundo.flujo, "game_state", None)
    presentes = []
    economia = escena_mundo.economia
    if economia is None:
        _aviso("ALCALDE_ECONOMIA=0: sin NPC con diálogo ni reacción de Seu Zé (solo la vigilancia del minimapa).")
    else:
        presentes = _instalar_npcs(escena_mundo, economia, npcs, catalogo, obtener_gs)
    resolver = lambda ancla: _resolver(escena_mundo, ancla)
    proveedor = crear_proveedor(config, presentes, obtener_gs, resolver)
    mm.registro().registrar_fuente(FUENTE_MINIMAPA, proveedor)
    _estado["proveedor"] = proveedor
    return proveedor


def _resolver(escena_mundo, ancla):
    from backend.logica.comercios import resolver_ancla
    return resolver_ancla(escena_mundo._mundo, ancla)


def _instalar_npcs(escena_mundo, economia, npcs, catalogo, obtener_gs):
    from frontend.dialogo_ui import CajaDialogo
    from frontend.npc_reactivo import NpcReactivo
    from frontend.vendedor_calle import VendedorCalle
    caja = CajaDialogo(parent=escena_mundo.hud)
    presentes = []
    for clave in npcs:
        if clave.origen == "vendedor":
            vendedor = next((i for i in economia.interacciones if isinstance(i, VendedorCalle)), None)
            if vendedor is None:
                continue
            vendedor.reaccion = lambda c=clave: frase_de(c, obtener_gs, catalogo)
            presentes.append((clave, vendedor.x, vendedor.z))
            continue
        try:
            x, z, rumbo = _resolver(escena_mundo, clave.ancla)
        except (ValueError, KeyError, AttributeError) as error:
            _aviso(f"{clave.id}: sin ancla en este mundo ({error}); no aparece")
            continue
        reactivo = NpcReactivo(escena_mundo, clave, x, z, rumbo, caja, obtener_gs, catalogo)
        economia.registrar(reactivo)
        presentes.append((clave, reactivo.x, reactivo.z))
    return presentes


def registrar(gestor, conexion, escena_mundo):
    if not (cfg.CONSECUENCIAS and cfg.GAMESTATE):
        return None
    try:
        return _instalar(conexion, escena_mundo)
    except Exception as error:
        _aviso(f"no se pudo instalar ({type(error).__name__}: {error}); el juego sigue sin consecuencias visibles")
        return None
