# Catálogo de assets del mundo 3D: UN solo lugar donde se dice qué modelo (.glb) y qué textura
# usa cada entidad del juego. Cambiar un modelo = editar una línea de CATALOGO; no se toca
# ninguna escena. Mientras `modelo` sea None se usa el constructor procedural de siempre
# (cubos y esferas), así el juego se ve igual sin archivos.
#
# Rutas: relativas a la carpeta `assets/` (ver assets/LEEME.md), p. ej.
#   "modelos/edificios/hospital.glb", "texturas/edificios/hospital.png".
# Nombres de archivo ÚNICOS en todo assets/ (Ursina cachea los modelos por nombre sin extensión).
#
# Claves del catálogo:
#   "rol:ciudadano" | "rol:periodista" | "rol:influencer" | "rol:candidato", "peaton",
#   "edificio:<lugar>" (uno por lugar), "edificio_generico", "arbol", "farola", "banco", "puerta".
#
# Fábrica: crear_entidad(clave, **opciones) -> Entity. Sin modelo, o si el archivo no existe o no
# carga -> constructor procedural registrado con registrar_procedural() (UNA advertencia por
# clave, nunca un crash). Con modelo -> Entity con el shader de pieza(), escala, rotación y
# desplazamiento del catálogo. Los modelos se cargan una vez y se copian.
#
# Verificación (sin abrir ventana):  python -m frontend.catalogo_assets --verificar

import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_ASSETS = Path(__file__).resolve().parents[1] / "assets"

# Poses que el juego pide a un personaje importado: nombre de pose -> clip del archivo.
POSES = ("parado", "caminar", "correr", "sentado", "teclear")


@dataclass(frozen=True)
class Asset:
    """Cómo se dibuja una entidad. `modelo=None` = constructor procedural."""

    modelo: str | None = None                 # "modelos/<tipo>/<archivo>.glb"
    textura: str | None = None                # "texturas/<tipo>/<archivo>.png" (opcional si el .glb ya la trae)
    escala: float = 1.0                       # multiplicador uniforme (1 unidad = 1 m)
    rotacion_y: float = 0.0                   # grados extra sobre el rumbo de la entidad
    desplazamiento: tuple = (0.0, 0.0, 0.0)   # (x, y, z) local, en metros
    tinte: tuple | None = None                # (r, g, b) 0-255 que multiplica la textura
    animaciones: dict = field(default_factory=dict, compare=False, hash=False)   # pose -> nombre de clip
    ajustar_a_huella: bool = False            # edificios: escalar el modelo a la huella del backend
    ocultar_puerta: bool = False              # edificios: el modelo trae su puerta, no dibujar la procedural


# Clips por defecto que usaría un personaje exportado desde Blender (ajusta si los nombras distinto).
_CLIPS = {"parado": "Idle", "caminar": "Walk", "correr": "Run", "sentado": "Sit", "teclear": "Type"}

# --- EDITA AQUÍ: una línea por entidad ---------------------------------------------------------
CATALOGO = {
    # Personajes (uno por rol jugable) y peatón.
    "rol:ciudadano": Asset(),
    "rol:periodista": Asset(),
    "rol:influencer": Asset(),
    "rol:candidato": Asset(),
    "peaton": Asset(),
    # Edificios: uno por lugar. Ejemplo:
    #   "edificio:Hospital Las Flores": Asset(modelo="modelos/edificios/hospital.glb",
    #                                         textura="texturas/edificios/hospital.png",
    #                                         ajustar_a_huella=True, ocultar_puerta=True),
    "edificio:Plaza Central": Asset(),
    "edificio:Alcaldía": Asset(),
    "edificio:Universidad de Ciudad Nova": Asset(),
    "edificio:Parque Municipal": Asset(),
    "edificio:Barrio Las Flores": Asset(),
    "edificio:Terminal de Buses": Asset(),
    "edificio:Hospital Las Flores": Asset(),
    "edificio_generico": Asset(),             # lo que usa un lugar sin entrada propia
    # Props repetidos (se cargan una vez y se copian).
    "arbol": Asset(),
    "farola": Asset(),
    "banco": Asset(),
    "puerta": Asset(),
}
# -----------------------------------------------------------------------------------------------

# Clips por defecto para quien asigne un modelo de personaje sin configurarlos.
ANIMACIONES_POR_DEFECTO = dict(_CLIPS)


# Asset de una clave. "edificio:<lugar>" sin entrada cae en "edificio_generico"; una clave
# desconocida da un Asset() vacío (procedural).
def asset_de(clave):
    if clave in CATALOGO:
        return CATALOGO[clave]
    if clave and clave.startswith("edificio:"):
        return CATALOGO.get("edificio_generico", Asset())
    return Asset()


def clave_rol(rol):
    return f"rol:{rol}"


def clave_edificio(lugar):
    return f"edificio:{lugar}"


# Ruta absoluta de un archivo del catálogo (relativa a assets/).
def ruta_asset(relativa):
    return RAIZ_ASSETS / relativa


# -- Advertencias de una sola vez ------------------------------------------------------------------

_advertidas = set()


def _advertir(clave, mensaje):
    if clave in _advertidas:
        return
    _advertidas.add(clave)
    print(f"[assets] {clave}: {mensaje}. Se usa el modelo procedural.", file=sys.stderr)


# -- Constructores procedurales (los registran ciudad_3d.py y personaje.py) -----------------------

_PROCEDURALES = {}


# `tipo`: la parte de la clave antes de ":" ("arbol", "edificio", "rol", "peaton", ...).
def registrar_procedural(tipo, constructor):
    _PROCEDURALES[tipo] = constructor


def _tipo(clave):
    return clave.split(":", 1)[0]


# -- Carga de modelos -------------------------------------------------------------------------------

_prototipos = {}          # ruta -> NodePath cargado una vez (o None si falló)


# Carga (una vez) el .glb del asset. None (con advertencia) si falta o falla.
def cargar_prototipo(clave, asset=None):
    asset = asset or asset_de(clave)
    if asset.modelo is None:
        return None
    ruta = ruta_asset(asset.modelo)
    if ruta in _prototipos:
        return _prototipos[ruta]
    prototipo = None
    if not ruta.is_file():
        _advertir(clave, f"no existe {asset.modelo}")
    else:
        try:
            from ursina.mesh_importer import load_model
            prototipo = load_model(ruta.name, folder=ruta.parent)
            if prototipo is None:
                _advertir(clave, f"no se pudo cargar {asset.modelo}")
        except Exception as error:               # un asset roto nunca debe tumbar el juego
            _advertir(clave, f"falló al cargar {asset.modelo} ({error})")
            prototipo = None
    _prototipos[ruta] = prototipo
    return prototipo


def _cargar_textura(clave, asset):
    if asset.textura is None:
        return None
    ruta = ruta_asset(asset.textura)
    if not ruta.is_file():
        _advertir(f"{clave}#textura", f"no existe {asset.textura}")
        return None
    try:
        from ursina.texture_importer import load_texture
        return load_texture(ruta.name, folder=ruta.parent)
    except Exception as error:
        _advertir(f"{clave}#textura", f"falló al cargar {asset.textura} ({error})")
        return None


# -- Fábrica ---------------------------------------------------------------------------------------------


# Entity para `clave`. Opciones comunes: parent, position, rotation_y, color; para edificios,
# `huella=(ancho, fondo, alto)` (las usa ajustar_a_huella); el resto se pasa tal cual al
# constructor procedural.
def crear_entidad(clave, **opciones):
    asset = asset_de(clave)
    if asset.modelo is not None:
        entidad = _crear_importada(clave, asset, opciones)
        if entidad is not None:
            return entidad
    constructor = _PROCEDURALES.get(_tipo(clave))
    if constructor is None:
        raise KeyError(f"No hay constructor procedural para {clave!r}.")
    return constructor(clave, **opciones)


# True si la clave tiene un modelo propio que carga bien (los constructores procedurales lo usan
# para saber si deben dibujar su versión de primitivas).
def usa_modelo(clave):
    asset = asset_de(clave)
    return asset.modelo is not None and cargar_prototipo(clave, asset) is not None


# Escala/posiciona, texturiza y tiñe un nodo de modelo según el asset. `huella=(ancho, fondo, alto)`
# solo se usa con ajustar_a_huella. False (con advertencia) si algo falla.
def aplicar_asset(nodo, clave, asset, huella=None, color=None):
    try:
        if asset.ajustar_a_huella and huella is not None:
            minimo, maximo = nodo.getTightBounds()
            tam = maximo - minimo
            if tam.x > 1e-6 and tam.y > 1e-6 and tam.z > 1e-6:
                ancho, fondo, alto = huella
                nodo.setScale(ancho / tam.x, alto / tam.y, fondo / tam.z)
                centro = (minimo + maximo) / 2
                nodo.setPos(-centro.x * ancho / tam.x, -minimo.y * alto / tam.y, -centro.z * fondo / tam.z)
        else:
            nodo.setScale(asset.escala)
        dx, dy, dz = asset.desplazamiento
        nodo.setPos(nodo.getPos() + (dx, dy, dz))
        nodo.setH(asset.rotacion_y)
    except Exception as error:
        _advertir(clave, f"no se pudo posicionar el modelo ({error})")
        return False
    textura = _cargar_textura(clave, asset)
    if textura is not None:
        nodo.setTexture(textura._texture, 1)
    if asset.tinte is not None:
        r, g, b = asset.tinte
        nodo.setColorScale(r / 255, g / 255, b / 255, 1)
    elif color is not None:
        nodo.setColorScale(*color)
    return True


def _crear_importada(clave, asset, opciones):
    prototipo = cargar_prototipo(clave, asset)
    if prototipo is None:
        return None
    from frontend.piezas import pieza

    entidad = pieza(parent=opciones.get("parent"), position=opciones.get("position", (0, 0, 0)),
                    rotation_y=opciones.get("rotation_y", 0.0))
    copia = prototipo.copy_to(entidad)
    if not aplicar_asset(copia, clave, asset, opciones.get("huella"), opciones.get("color")):
        entidad.removeNode()
        return None
    return entidad


# -- Verificación (python -m frontend.catalogo_assets --verificar) ------------------------------


# [(clave, estado, detalle)] con estado "propio" | "procedural" | "falta".
def verificar():
    filas = []
    for clave, asset in CATALOGO.items():
        if asset.modelo is None:
            filas.append((clave, "procedural", "sin modelo (constructor de primitivas)"))
            continue
        faltan = [r for r in (asset.modelo, asset.textura) if r and not ruta_asset(r).is_file()]
        if faltan:
            filas.append((clave, "falta", "cae al procedural; faltan: " + ", ".join(faltan)))
        else:
            filas.append((clave, "propio", asset.modelo))
    return filas


def _imprimir_verificacion():
    filas = verificar()
    ancho = max(len(c) for c, _, _ in filas)
    for clave, estado, detalle in filas:
        print(f"{clave:<{ancho}}  {estado:<10}  {detalle}")
    n = {e: sum(1 for _, s, _ in filas if s == e) for e in ("propio", "procedural", "falta")}
    print(f"\nCarpeta de assets: {RAIZ_ASSETS}")
    print(f"{n['propio']} con modelo propio, {n['procedural']} procedurales, {n['falta']} con archivos faltantes.")
    return 1 if n["falta"] else 0


if __name__ == "__main__":
    if "--verificar" in sys.argv[1:]:
        sys.exit(_imprimir_verificacion())
    print("Uso: python -m frontend.catalogo_assets --verificar")
