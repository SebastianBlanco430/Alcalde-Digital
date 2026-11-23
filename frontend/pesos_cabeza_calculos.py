# Pesos de hueso de la cabeza (Python puro: NO importa ursina ni panda3d). Lo usa frontend/pesos_cabeza.py.
#
# Bug «se ve la calva al caminar» (rework 3D, fase 1b; diagnóstico en rework-3d/bug-pelo/informe.md): en los .glb con
# rig Rigify (ciudadano, periodista, smoking y los NPC que los copian, y npc_hombre_*) la piel de la coronilla pesa ~50 %
# en huesos FACIALES que el exportador dejó como RAÍZ (sin padre: DEF-forehead.*, DEF-temple.*, DEF-ear.*, DEF-brow.*...).
# En cada clip solo esos huesos van rígidos con la cabeza (medido en todos los cuadros de todos los clips), pero Panda
# MEZCLA cada hueso por separado: para un hueso raíz interpola su transformación absoluta (en línea recta) y para la
# cabeza las rotaciones de toda la columna (en arco). Al arrancar, frenar, cambiar de velocidad o aterrizar, la coronilla
# se separaba hasta 3-4 cm del pelo, que cuelga rígido del hueso de la cabeza (rostro_modelo), y asomaba la piel.
# Arreglo en la causa, al cargar: los pesos de esos huesos pasan al hueso de la cabeza. En un clip solo no cambia ni un
# vértice (los huesos eran rígidos con la cabeza); en las mezclas la cabeza entera se mueve como un sólido, con el pelo.
#
# Bandera: PESOS_CABEZA o ALCALDE_PESOS_CABEZA=0/1 (0 = los pesos del .glb tal cual, como antes).

import os

PESOS_CABEZA = True


def activa():
    valor = os.environ.get("ALCALDE_PESOS_CABEZA", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PESOS_CABEZA)


# Mismas palabras con las que animacion_humana.Hornero._padre_virtual cuelga un hueso raíz del cuerpo y no de la cabeza.
_DEL_CUERPO = ("pelvis", "breast", "shoulder")


def huesos_a_cabeza(raices, zonas, explicitos):
    """De los huesos raíz (sin padre) del esqueleto, los que pertenecen a la cabeza: ni de una zona del tronco (`zonas`),
    ni de un miembro (`explicitos`), ni de pelvis/pecho/hombro. Son los que Hornero mueve rígidos con la cabeza."""
    salida = set()
    for nombre in raices:
        if nombre in zonas or nombre in explicitos:
            continue
        bajo = nombre.lower()
        if any(palabra in bajo for palabra in _DEL_CUERPO):
            continue
        salida.add(nombre)
    return salida


def fusionar(pesos, a_cabeza, cabeza):
    """pesos: [(hueso, peso)]. Pasa a `cabeza` el peso de los huesos de `a_cabeza` (sumado con el que ya tuviera).
    Sin nada que pasar devuelve la MISMA lista; si no, la cabeza ocupa el lugar del primero que se le suma."""
    if not any(nombre in a_cabeza for nombre, _ in pesos):
        return pesos
    salida, total_cabeza, puesto = [], 0.0, False
    for nombre, peso in pesos:
        if nombre in a_cabeza or nombre == cabeza:
            total_cabeza += peso
            if not puesto:
                salida.append(None)          # hueco de la cabeza
                puesto = True
        else:
            salida.append((nombre, peso))
    return [(cabeza, total_cabeza) if x is None else x for x in salida]
