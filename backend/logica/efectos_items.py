# Efectos de los objetos al usarlos (modelo puro). `aplicar` recibe la clave de efecto del DefItem, el
# perfil de economía (puede ser None: entonces solo se informa) y el DefItem.
#   comer / beber -> bajan la fatiga y consumen una unidad.
#   info          -> solo muestra la descripción del objeto; no se consume.
# Claves desconocidas devuelven None (el Inventario las rechaza).

from dataclasses import dataclass

FATIGA_COMER = 10
FATIGA_BEBER = 8
# Ajustes por objeto (id -> puntos de fatiga que baja); si no está, vale el valor de la clave.
FATIGA_POR_ITEM = {"cafe": 12, "bala": 3, "pan": 10, "agua": 8}


@dataclass(frozen=True)
class ResultadoEfecto:
    consumir: bool
    mensaje: str
    fatiga_delta: int = 0


def aplicar(clave, perfil, defitem):
    if clave in ("comer", "beber"):
        base = FATIGA_COMER if clave == "comer" else FATIGA_BEBER
        baja = FATIGA_POR_ITEM.get(defitem.id, base)
        if perfil is not None:
            perfil.fatiga = max(0, perfil.fatiga - baja)
        verbo = "Comiste" if clave == "comer" else "Bebiste"
        return ResultadoEfecto(True, f"{verbo} {defitem.nombre.lower()}: te sientes menos cansado.", -baja)
    if clave == "info":
        return ResultadoEfecto(False, defitem.descripcion or defitem.nombre, 0)
    return None
