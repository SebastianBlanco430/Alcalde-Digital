# Protagonistas v2 (fase Blender, sesión F, 2026-11-24; bandera ALCALDE_PROTAGONISTAS_V2 en backend/logica/modelos_v2.py).
# Puro: sin ursina ni panda3d. Lo usa frontend/personaje_modelo.py y lo prueban tests/test_protagonistas_v2*.py.
#
# Los .glb v2 (assets/modelos/personajes/v2/, generados por blender/protagonistas/arreglar_protagonista.py fuera del repo)
# son los de hoy con los arreglos hechos en el asset:
#   - huesos sin raíces sueltas: cada hueso raíz del Rigify cuelga del padre que ya le daba animacion_humana.Hornero
#     (_padre_virtual), con los 5 clips rehorneados (se ven igual); los pesos faciales están en DEF-spine.006, así que
#     frontend/pesos_cabeza.py no cambia nada;
#   - el pelo por código de hoy (las piezas «pelo_*» de rostro_calculos) va MODELADO en la malla, pesado 100 % a la
#     cabeza (ciudadano, periodista, candidato): el código ya no lo pone;
#   - un solo material de color («paleta», el color va por vértice) + el casco «Contorno»;
#   - Idle con los brazos más pegados (Rigify).
# Solo el JUGADOR (PersonajeModelo) usa el v2; las copias para NPC (npc_modelo, npc_postura) siguen con el de hoy.

from pathlib import PurePosixPath

# Roles cuyo .glb v2 trae el pelo modelado (la brasileña ya traía su afro en el .glb de hoy).
PELO_MODELADO = frozenset({"ciudadano", "periodista", "candidato"})
PREFIJO_PELO = "pelo_"

# Medidas del esqueleto v2 (m, con la escala del Actor), medidas con blender/protagonistas/comprobar_panda.py: el brazo
# (hombro -> muñeca) no cambió respecto a hoy (ver el informe de protagonistas-raiz: alargar el brazo de la brasileña
# cambiaría su silueta). Son las que usa la condición de Señales sentado.
BRAZO_V2 = {"ciudadano": 0.586, "periodista": 0.586, "candidato": 0.586, "influencer": 0.433}


def clave_archivo(archivo):
    """«ciudadano.glb» -> «ciudadano» (la clave de modelos_v2.PROTAGONISTAS_V2)."""
    return PurePosixPath(str(archivo).replace("\\", "/")).stem


def archivo_modelo(archivo_hoy, activo, tabla_v2):
    """(archivo relativo a assets/modelos/personajes, es_v2). Con la bandera activa y el rol en la tabla, el v2; si no,
    el de hoy. Quien llama comprueba que el v2 exista y, si falta o no carga, vuelve al de hoy."""
    if activo:
        v2 = tabla_v2.get(clave_archivo(archivo_hoy))
        if v2:
            return v2, True
    return archivo_hoy, False


def es_pieza_de_pelo(pieza):
    return str(pieza.get("nombre", "")).startswith(PREFIJO_PELO)


def piezas_sin_pelo(piezas):
    """Las piezas del rostro por código sin el pelo (para un .glb v2 que ya lo trae modelado)."""
    return [p for p in piezas if not es_pieza_de_pelo(p)]


def quitar_pelo(rol, es_v2):
    """¿Se quita el pelo por código a este personaje? Solo con el .glb v2 de un rol con pelo modelado."""
    return bool(es_v2) and rol in PELO_MODELADO


def senales_sentado_alcanza(faltas_por_rol, tolerancia=0.0):
    """Señales se juega SENTADO solo si a la mano del plumón no le falta nada (entrada_calculos.falta_alcance_senales)
    con los 4 protagonistas. `faltas_por_rol`: {rol: {punto: m que faltan}}."""
    return bool(faltas_por_rol) and all(max(f.values()) <= tolerancia for f in faltas_por_rol.values())
