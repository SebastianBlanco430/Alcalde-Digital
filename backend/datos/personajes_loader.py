# Cargador de la fuente única del aspecto de los personajes con nombre (puro, sin motor gráfico): lee
# backend/datos/personajes_fiscalia.json y devuelve recetas validadas. La usan la Fiscalía, el mundo (NPC clave, Seu Zé)
# y los retratos 2D, así un personaje es el mismo dentro y fuera. Un JSON roto lanza PersonajesError con el motivo.
#
# Reglas que se validan al cargar: cuerpo de los 5 modelos de NPC (nunca el de un protagonista), colores [r, g, b] de 0 a
# 255, cara con valores conocidos, retrato con los estilos del contrato de casos, y ninguna firma visual repetida.

import json
from dataclasses import dataclass
from pathlib import Path

RUTA = Path(__file__).resolve().parent / "personajes_fiscalia.json"

# Cuerpos de los 4 protagonistas jugables: ningún personaje con nombre los usa.
CUERPOS_PROTAGONISTAS = ("periodista.glb", "smoking.glb", "ciudadano.glb", "brasilena.glb")
CUERPOS_HOMBRE = ("npc_hombre_01.glb", "npc_hombre_02.glb", "npc_hombre_03.glb")
CUERPOS_MUJER = ("npc_mujer_01.glb", "npc_mujer_02.glb")
CUERPOS = CUERPOS_HOMBRE + CUERPOS_MUJER
PEINADOS = ("corto", "atras", "pompadour", "afro", "mono", "calvo")     # rostro_calculos.peinado (hombres)
BARBAS = ("incipiente", "chivo", "completa")
PELO_ESTILOS = ("corto", "largo", "calvo")                              # contrato de casos §6
ACCESORIOS = ("ninguno", "gafas", "barba", "corbata")
ESCALA_MIN, ESCALA_MAX = 0.93, 1.06


class PersonajesError(ValueError):
    pass


@dataclass(frozen=True)
class Receta:
    id: str
    nombre: str
    oficio: str
    cuerpo: str
    escala: float
    piel: tuple
    pelo: tuple
    camiseta: tuple
    pantalon: tuple
    zapatos: tuple
    peinado: str | None
    gafas: bool
    bigote: bool
    barba: str | None
    arrugas: bool
    canas: bool
    auriculares: dict | None
    iris: tuple
    corbata: tuple | None
    pelo_estilo: str
    accesorio: str

    @property
    def mujer(self):
        return self.cuerpo in CUERPOS_MUJER

    def retrato(self, expresiones=None):
        """Retrato 2D (dialogo_retratos / contrato de casos) con los colores de la receta; `expresiones` si se pasan."""
        r = {"piel": list(self.piel), "pelo": list(self.pelo), "pelo_estilo": self.pelo_estilo,
             "ropa": list(self.camiseta), "accesorio": self.accesorio}
        if expresiones is not None:
            r["expresiones"] = list(expresiones)
        return r

    def firma(self):
        """Lo que se ve a simple vista: dos personajes con la misma firma se confundirían."""
        return (self.cuerpo, self.peinado, self.gafas, self.bigote, self.barba, self.arrugas,
                bool(self.auriculares), self.corbata is not None, self.pelo, self.camiseta)


def _rgb(valor, donde):
    if not (isinstance(valor, list) and len(valor) == 3
            and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in valor)):
        raise PersonajesError(f"{donde}: [r, g, b] con enteros de 0 a 255.")
    return tuple(valor)


def _texto(valor, donde):
    if not isinstance(valor, str) or not valor.strip():
        raise PersonajesError(f"{donde}: texto no vacío.")
    return valor.strip()


def _receta(pid, d):
    donde = f"personajes.{pid}"
    if not isinstance(d, dict):
        raise PersonajesError(f"{donde}: debe ser un objeto.")
    cuerpo = d.get("cuerpo")
    if cuerpo in CUERPOS_PROTAGONISTAS:
        raise PersonajesError(f"{donde}.cuerpo: {cuerpo} es el cuerpo de un protagonista.")
    if cuerpo not in CUERPOS:
        raise PersonajesError(f"{donde}.cuerpo: uno de {CUERPOS}.")
    escala = d.get("escala", 1.0)
    if isinstance(escala, bool) or not isinstance(escala, (int, float)) or not ESCALA_MIN <= escala <= ESCALA_MAX:
        raise PersonajesError(f"{donde}.escala: número entre {ESCALA_MIN} y {ESCALA_MAX}.")
    ropa = d.get("ropa")
    if not isinstance(ropa, dict):
        raise PersonajesError(f"{donde}.ropa: objeto con camiseta, pantalon y zapatos.")
    r = d.get("rostro")
    if not isinstance(r, dict):
        raise PersonajesError(f"{donde}.rostro: debe ser un objeto.")
    mujer = cuerpo in CUERPOS_MUJER
    peinado = r.get("peinado")
    if mujer and peinado is not None:
        raise PersonajesError(f"{donde}.rostro.peinado: las mujeres traen el pelo en el modelo (null).")
    if not mujer and peinado not in PEINADOS:
        raise PersonajesError(f"{donde}.rostro.peinado: uno de {PEINADOS}.")
    barba = r.get("barba")
    if barba is not None and barba not in BARBAS:
        raise PersonajesError(f"{donde}.rostro.barba: null o uno de {BARBAS}.")
    if mujer and (barba is not None or r.get("bigote")):
        raise PersonajesError(f"{donde}.rostro: sin bigote ni barba en un cuerpo de mujer.")
    for clave in ("gafas", "bigote", "arrugas", "canas"):
        if not isinstance(r.get(clave, False), bool):
            raise PersonajesError(f"{donde}.rostro.{clave}: true o false.")
    aur = r.get("auriculares")
    if aur is not None:
        if not isinstance(aur, dict):
            raise PersonajesError(f"{donde}.rostro.auriculares: null u objeto con color y almohadilla.")
        aur = {"color": _rgb(aur.get("color"), f"{donde}.rostro.auriculares.color"),
               "almohadilla": _rgb(aur.get("almohadilla"), f"{donde}.rostro.auriculares.almohadilla"),
               "al_cuello": bool(aur.get("al_cuello", False))}
    iris = r.get("iris", [0.20, 0.13, 0.07])
    if not (isinstance(iris, list) and len(iris) == 3 and all(isinstance(c, (int, float)) and 0 <= c <= 1 for c in iris)):
        raise PersonajesError(f"{donde}.rostro.iris: [r, g, b] de 0 a 1.")
    corbata = d.get("corbata")
    if corbata is not None:
        if mujer:
            raise PersonajesError(f"{donde}.corbata: solo en cuerpos de hombre (cuelga del esqueleto Rigify).")
        corbata = _rgb(corbata, f"{donde}.corbata")
    ret = d.get("retrato")
    if not isinstance(ret, dict):
        raise PersonajesError(f"{donde}.retrato: objeto con pelo_estilo y accesorio.")
    if ret.get("pelo_estilo") not in PELO_ESTILOS:
        raise PersonajesError(f"{donde}.retrato.pelo_estilo: uno de {PELO_ESTILOS}.")
    if ret.get("accesorio") not in ACCESORIOS:
        raise PersonajesError(f"{donde}.retrato.accesorio: uno de {ACCESORIOS}.")
    receta = Receta(pid, _texto(d.get("nombre"), f"{donde}.nombre"), _texto(d.get("oficio"), f"{donde}.oficio"),
                    cuerpo, float(escala), _rgb(d.get("piel"), f"{donde}.piel"), _rgb(d.get("pelo"), f"{donde}.pelo"),
                    _rgb(ropa.get("camiseta"), f"{donde}.ropa.camiseta"), _rgb(ropa.get("pantalon"), f"{donde}.ropa.pantalon"),
                    _rgb(ropa.get("zapatos"), f"{donde}.ropa.zapatos"), peinado, bool(r.get("gafas", False)),
                    bool(r.get("bigote", False)), barba, bool(r.get("arrugas", False)), bool(r.get("canas", False)), aur,
                    tuple(float(c) for c in iris), corbata, ret["pelo_estilo"], ret["accesorio"])
    _coherencia(receta, donde)
    return receta


def _coherencia(p, donde):
    """El retrato 2D no puede contradecir al modelo 3D."""
    if p.accesorio == "gafas" and not p.gafas:
        raise PersonajesError(f"{donde}: el retrato lleva gafas y el modelo no.")
    if p.accesorio == "barba" and not (p.barba or p.bigote):
        raise PersonajesError(f"{donde}: el retrato lleva barba y el modelo no.")
    if p.accesorio == "corbata" and p.corbata is None:
        raise PersonajesError(f"{donde}: el retrato lleva corbata y el modelo no.")
    if p.gafas and p.accesorio != "gafas":
        raise PersonajesError(f"{donde}: el modelo lleva gafas y el retrato no (accesorio 'gafas').")
    if p.mujer != (p.pelo_estilo == "largo"):
        raise PersonajesError(f"{donde}: pelo_estilo 'largo' sí y solo si el cuerpo es de mujer (el VN viejo elige así).")
    if not p.mujer and (p.peinado == "calvo") != (p.pelo_estilo == "calvo"):
        raise PersonajesError(f"{donde}: peinado 'calvo' y pelo_estilo 'calvo' van juntos.")


def cargar(ruta=None):
    """{id: Receta} validado. Lanza PersonajesError (nunca devuelve una lista a medias)."""
    ruta = Path(ruta) if ruta is not None else RUTA
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PersonajesError(f"{ruta.name}: el archivo no existe.") from None
    except json.JSONDecodeError as error:
        raise PersonajesError(f"{ruta.name}: JSON inválido (línea {error.lineno}, columna {error.colno}): {error.msg}") from None
    lista = datos.get("personajes") if isinstance(datos, dict) else None
    if not isinstance(lista, dict) or not lista:
        raise PersonajesError(f"{ruta.name}: 'personajes' debe ser un objeto no vacío.")
    recetas = {pid: _receta(pid, d) for pid, d in lista.items()}
    firmas, nombres = {}, {}
    for p in recetas.values():
        otro = firmas.setdefault(p.firma(), p.id)
        if otro != p.id:
            raise PersonajesError(f"personajes.{p.id}: se ve igual que {otro!r} (misma firma visual).")
        otro = nombres.setdefault(p.nombre, p.id)
        if otro != p.id:
            raise PersonajesError(f"personajes.{p.id}: nombre repetido con {otro!r}.")
    return recetas


_cache = {}


def recetas():
    """Las recetas de la fuente por defecto, cargadas una vez. {} si el archivo está roto (avisa por stderr)."""
    if "r" not in _cache:
        try:
            _cache["r"] = cargar()
        except PersonajesError as error:
            import sys
            print(f"[personajes] {error} Se usan los modelos de antes.", file=sys.stderr)
            _cache["r"] = {}
    return _cache["r"]


def por_id(pid, fuente=None):
    return (fuente if fuente is not None else recetas()).get(pid)


def por_nombre(nombre, fuente=None):
    if not nombre:
        return None
    return next((p for p in (fuente if fuente is not None else recetas()).values() if p.nombre == nombre), None)


def de_caso(pid, datos, fuente=None):
    """Receta de un personaje de un caso: su clave 'personaje' (id de la fuente) o, si no la trae, su id en el caso;
    y si tampoco, su nombre. None = el caso usa su propio modelo/retrato (casos de terceros)."""
    datos = datos if isinstance(datos, dict) else {}
    ref = datos.get("personaje")
    return (por_id(ref, fuente) if ref else None) or por_id(pid, fuente) or por_nombre(datos.get("nombre"), fuente)


def completar_caso(pid, datos, fuente=None):
    """Copia del personaje del caso con 'modelo' y 'retrato' rellenados desde la fuente (conserva las expresiones del
    caso). Sin receta, la copia tal cual."""
    datos = dict(datos) if isinstance(datos, dict) else {}
    p = de_caso(pid, datos, fuente)
    if p is None:
        return datos
    expresiones = (datos.get("retrato") or {}).get("expresiones")
    datos["modelo"] = p.cuerpo
    datos["retrato"] = p.retrato(expresiones)
    return datos
