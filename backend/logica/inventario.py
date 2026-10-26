# Inventario realista del jugador (modelo puro, sin ursina): ubicaciones del cuerpo con ranuras y tamaños,
# peso máximo y una billetera con dinero en R$ (enteros). Serializable a JSON (a_dict / desde_dict tolerantes).
#
# Ubicaciones (id: ranuras, tamaño máximo): bolsillo_der (2, pequeño), bolsillo_izq (2, pequeño),
# bolsillo_trasero (1, pequeño), cintura (2, mediano, solo objetos de cintura), mano_der (1, grande),
# mano_izq (1, grande), espalda (1, solo una mochila) y mochila (las ranuras de la mochila equipada, mediano;
# solo existe mientras haya una mochila en la espalda). Un objeto `dos_manos` ocupa las dos manos (vive en
# mano_der y deja mano_izq bloqueada). Peso máximo: 15 kg + el `peso_extra` de la mochila equipada.
#
# Colocación automática (elegir_ubicacion): completa una pila existente; la mochila va a la espalda;
# los de dos manos a las manos; cintura si el objeto es de cintura; bolsillos si es pequeño; mochila si es
# mediano y hay; manos si no. Todas las operaciones que fallan dejan el inventario SIN tocar y devuelven un
# Resultado con la razón en español.
#
# Dinero: la billetera es un objeto `fijo` con datos["saldo"] (entero 0..SALDO_MAX). Sin billetera no se
# cobra ni se ingresa.

import copy
import math
from dataclasses import dataclass, field

PEQUENO, MEDIANO, GRANDE = 1, 2, 3
PESO_BASE_KG = 15.0
SALDO_MAX = 1_000_000_000
MAX_PILAS_POR_UBICACION = 50      # tope al leer datos guardados (anti datos maliciosos)
DATOS_PERMITIDOS = ("saldo",)     # únicas claves de Pila.datos que se aceptan al cargar

_NOMBRE_TAMANO = {PEQUENO: "pequeñ", MEDIANO: "median"}


@dataclass(frozen=True)
class DefItem:
    id: str
    nombre: str
    tamano: int
    peso_kg: float
    apilable: int = 1
    categoria: str = "otro"
    precio: int | None = None         # None = no se vende
    cintura: bool = False
    dos_manos: bool = False
    fijo: bool = False                # no se suelta, ni se mueve, ni se vende
    efecto: str | None = None         # clave de efectos_items
    ranuras: int = 0                  # > 0 = equipo con espacio (mochila)
    peso_extra: float = 0.0           # kg extra de capacidad que da al equiparlo
    sensible: bool = False
    descripcion: str = ""


@dataclass(frozen=True)
class DefUbicacion:
    id: str
    nombre: str
    ranuras: int
    tamano_max: int
    solo_cintura: bool = False
    requiere_equipo: str | None = None   # id de la ubicación cuyo equipo la activa (mochila -> espalda)
    solo_equipo: bool = False            # solo admite objetos con ranuras > 0 (la espalda)


@dataclass
class Pila:
    item_id: str
    cantidad: int = 1
    datos: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Resultado:
    ok: bool
    codigo: str = "ok"
    mensaje: str = ""


UBICACIONES_BASE = (
    DefUbicacion("bolsillo_der", "Bolsillo derecho", 2, PEQUENO),
    DefUbicacion("bolsillo_izq", "Bolsillo izquierdo", 2, PEQUENO),
    DefUbicacion("bolsillo_trasero", "Bolsillo trasero", 1, PEQUENO),
    DefUbicacion("cintura", "Cintura", 2, MEDIANO, solo_cintura=True),
    DefUbicacion("mano_der", "Mano derecha", 1, GRANDE),
    DefUbicacion("mano_izq", "Mano izquierda", 1, GRANDE),
    DefUbicacion("espalda", "Espalda", 1, GRANDE, solo_equipo=True),
    DefUbicacion("mochila", "Mochila", 8, MEDIANO, requiere_equipo="espalda"),
)
_BOLSILLOS = ("bolsillo_der", "bolsillo_izq", "bolsillo_trasero")
_MANOS = ("mano_der", "mano_izq")


def _articulo(nombre):
    return "la" if nombre.split()[0].lower().endswith("a") else "el"


def _adjetivo(defitem):
    if defitem.tamano >= GRANDE:
        return "grande"
    sufijo = "a" if _articulo(defitem.nombre) == "la" else "o"
    return _NOMBRE_TAMANO.get(defitem.tamano, "median") + sufijo


def _num(valor):
    return f"{valor:.1f}".replace(".", ",")


def _entero_valido(valor, minimo, maximo):
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


def _ok(mensaje=""):
    return Resultado(True, "ok", mensaje)


def _no(codigo, mensaje):
    return Resultado(False, codigo, mensaje)


# Elige dónde va UNA unidad del objeto. Devuelve (ubicacion, "") o (None, motivo en español). No modifica nada.
def elegir_ubicacion(inv, defitem, datos=None):
    datos = datos or {}
    activas = [u.id for u in inv.ubicaciones_activas()]
    if defitem.apilable > 1:
        for ub in activas:
            for pila in inv._pilas[ub]:
                if pila.item_id == defitem.id and pila.cantidad < defitem.apilable and pila.datos == datos:
                    return ub, ""
    candidatos = []
    if defitem.ranuras > 0:
        candidatos.append("espalda")
    if defitem.dos_manos:
        candidatos.append("mano_der")
    else:
        if defitem.cintura:
            candidatos.append("cintura")
        if defitem.tamano == PEQUENO:
            candidatos.extend(_BOLSILLOS)
        if defitem.tamano <= MEDIANO and defitem.ranuras == 0:
            candidatos.append("mochila")
        if defitem.tamano >= MEDIANO:      # lo pequeño nunca va a las manos por su cuenta
            candidatos.extend(_MANOS)
    for ub in candidatos:
        if ub in activas and inv._admite(ub, defitem)[0] and inv._cabe_nueva_pila(ub, defitem):
            return ub, ""
    art, nombre = _articulo(defitem.nombre), defitem.nombre
    if defitem.dos_manos:
        return None, f"No cabe: {art} {nombre} se lleva con las dos manos y las necesitas libres."
    if defitem.tamano == GRANDE:
        return None, (f"No cabe: {art} {nombre} es {_adjetivo(defitem)} y solo se lleva en las manos; "
                      "tienes las dos ocupadas.")
    return None, f"No cabe: no te queda espacio libre para {art} {nombre}."


class Inventario:

    # `catalogo` = {id: DefItem}. ValueError si las ubicaciones se repiten o el peso no es positivo.
    def __init__(self, catalogo, ubicaciones=UBICACIONES_BASE, peso_max=PESO_BASE_KG):
        if not isinstance(peso_max, (int, float)) or isinstance(peso_max, bool) or not peso_max > 0:
            raise ValueError("peso_max debe ser un número positivo.")
        ids = [u.id for u in ubicaciones]
        if len(set(ids)) != len(ids):
            raise ValueError("Ubicaciones repetidas en el inventario.")
        self.catalogo = catalogo
        self._ubicaciones = {u.id: u for u in ubicaciones}
        self._base_peso = float(peso_max)
        self._pilas = {u.id: [] for u in ubicaciones}
        self.avisos = []          # advertencias de desde_dict (objetos descartados)

    # -- Consulta --

    def _equipo(self):
        pilas = self._pilas.get("espalda")
        if pilas and pilas[0].item_id in self.catalogo and self.catalogo[pilas[0].item_id].ranuras > 0:
            return self.catalogo[pilas[0].item_id]
        return None

    def ubicaciones_activas(self):
        activas = []
        for u in self._ubicaciones.values():
            if u.requiere_equipo is not None:
                equipo = self._pilas.get(u.requiere_equipo)
                if not equipo or self._equipo() is None:
                    continue
            activas.append(u)
        return activas

    def _ranuras_totales(self, ub):
        u = self._ubicaciones[ub]
        if u.requiere_equipo is not None:
            equipo = self._equipo()
            return equipo.ranuras if equipo is not None else 0
        return u.ranuras

    def _dos_manos_en_uso(self):
        return any(self.catalogo[p.item_id].dos_manos for p in self._pilas.get("mano_der", []))

    def ranuras_libres(self, ubicacion):
        if ubicacion not in self._pilas or ubicacion not in {u.id for u in self.ubicaciones_activas()}:
            return 0
        usadas = len(self._pilas[ubicacion])
        if ubicacion == "mano_izq" and self._dos_manos_en_uso():
            usadas += 1
        return max(0, self._ranuras_totales(ubicacion) - usadas)

    # Copia de las pilas: de una ubicación (lista) o de todas las activas ({ubicacion: lista}).
    def pilas(self, ubicacion=None):
        if ubicacion is not None:
            return [copy.deepcopy(p) for p in self._pilas.get(ubicacion, [])]
        return {u.id: [copy.deepcopy(p) for p in self._pilas[u.id]] for u in self.ubicaciones_activas()}

    def peso_total(self):
        return sum(self.catalogo[p.item_id].peso_kg * p.cantidad for lista in self._pilas.values() for p in lista)

    def peso_max(self):
        equipo = self._equipo()
        return self._base_peso + (equipo.peso_extra if equipo is not None else 0.0)

    def cantidad_de(self, item_id):
        return sum(p.cantidad for lista in self._pilas.values() for p in lista if p.item_id == item_id)

    def tiene(self, item_id, cantidad=1):
        return self.cantidad_de(item_id) >= cantidad

    # -- Colocación --

    # (True, "") o (False, motivo): ¿admite la ubicación este tipo de objeto? (sin mirar las ranuras)
    def _admite(self, ub, defitem):
        if ub not in self._ubicaciones:
            return False, "Esa ubicación no existe."
        if ub not in {u.id for u in self.ubicaciones_activas()}:
            return False, "No llevas mochila."
        u = self._ubicaciones[ub]
        art, nombre = _articulo(defitem.nombre), defitem.nombre
        if u.solo_equipo and defitem.ranuras <= 0:
            return False, "En la espalda solo se lleva una mochila."
        if defitem.ranuras > 0 and ub == "mochila":
            return False, "La mochila no cabe dentro de otra."
        if u.solo_cintura and not defitem.cintura:
            return False, f"A la cintura solo van objetos de cintura; {art} {nombre} no."
        if defitem.dos_manos and ub not in _MANOS:
            return False, f"{art.capitalize()} {nombre} se lleva con las dos manos."
        if defitem.tamano > u.tamano_max:
            if ub in _BOLSILLOS:
                return False, (f"No cabe en los bolsillos: {art} {nombre} es {_adjetivo(defitem)}. "
                               "Usa la cintura, la mochila o una mano.")
            return False, f"No cabe en {u.nombre.lower()}: {art} {nombre} es {_adjetivo(defitem)}."
        return True, ""

    # ¿Hay ranura para una pila NUEVA de este objeto en la ubicación? (dos manos: ambas libres)
    def _cabe_nueva_pila(self, ub, defitem):
        if defitem.dos_manos:
            return ub == "mano_der" and self.ranuras_libres("mano_der") > 0 and self.ranuras_libres("mano_izq") > 0
        return self.ranuras_libres(ub) > 0

    def _snapshot(self):
        return {ub: [copy.deepcopy(p) for p in lista] for ub, lista in self._pilas.items()}

    def _restaurar(self, snap):
        self._pilas = snap

    # Pone UNA unidad en la ubicación (completa pila o abre una). Resultado; modifica solo si ok.
    def _poner_una(self, ub, defitem, datos):
        ok, motivo = self._admite(ub, defitem)
        if not ok:
            return _no("no_cabe", motivo)
        if defitem.apilable > 1:
            for pila in self._pilas[ub]:
                if pila.item_id == defitem.id and pila.cantidad < defitem.apilable and pila.datos == datos:
                    pila.cantidad += 1
                    return _ok()
        if not self._cabe_nueva_pila(ub, defitem):
            if defitem.dos_manos:
                return _no("no_cabe", f"No cabe: {_articulo(defitem.nombre)} {defitem.nombre} necesita las dos manos libres.")
            return _no("no_cabe", f"No hay ranuras libres en {self._ubicaciones[ub].nombre.lower()}.")
        self._pilas[ub].append(Pila(defitem.id, 1, copy.deepcopy(datos)))
        return _ok()

    def _validar_peticion(self, item_id, cantidad):
        if item_id not in self.catalogo:
            return None, _no("item_desconocido", "Ese objeto no existe.")
        if not _entero_valido(cantidad, 1, 999):
            return None, _no("cantidad_invalida", "La cantidad debe ser un entero entre 1 y 999.")
        return self.catalogo[item_id], None

    def _guardar_sin_pesar(self, defitem, cantidad, ubicacion, datos):
        for _ in range(cantidad):
            if ubicacion is None:
                ub, motivo = elegir_ubicacion(self, defitem, datos)
                if ub is None:
                    return _no("no_cabe", motivo)
            else:
                ub = ubicacion
            resultado = self._poner_una(ub, defitem, datos)
            if not resultado.ok:
                return resultado
        return _ok()

    def _comprobar_peso(self):
        if self.peso_total() > self.peso_max() + 1e-9:
            maximo = f"{self.peso_max():g}".replace(".", ",")
            return _no("peso", f"Llevas demasiado peso ({_num(self.peso_total())} de {maximo} kg).")
        return _ok()

    # Guarda `cantidad` unidades (atómico). ubicacion=None = automático. Devuelve Resultado.
    def guardar(self, item_id, cantidad=1, ubicacion=None, datos=None):
        defitem, error = self._validar_peticion(item_id, cantidad)
        if error:
            return error
        datos = self._limpiar_datos(datos)
        snap = self._snapshot()
        resultado = self._guardar_sin_pesar(defitem, cantidad, ubicacion, datos)
        if resultado.ok:
            resultado = self._comprobar_peso()
        if not resultado.ok:
            self._restaurar(snap)
            return resultado
        return _ok(f"Guardaste {cantidad} × {defitem.nombre}.")

    # Igual que guardar, pero sin modificar nada.
    def puede_guardar(self, item_id, cantidad=1, ubicacion=None):
        snap = self._snapshot()
        try:
            return self.guardar(item_id, cantidad, ubicacion)
        finally:
            self._restaurar(snap)

    @staticmethod
    def _limpiar_datos(datos):
        if not isinstance(datos, dict):
            return {}
        return {k: copy.deepcopy(v) for k, v in datos.items() if k in DATOS_PERMITIDOS}

    # -- Quitar / mover / soltar / usar --

    def _pila_en(self, ubicacion, indice):
        lista = self._pilas.get(ubicacion) if isinstance(ubicacion, str) else None
        if lista is None or not isinstance(indice, int) or isinstance(indice, bool) or not 0 <= indice < len(lista):
            return None
        return lista[indice]

    def _mochila_bloqueada(self, ubicacion, pila):
        return ubicacion == "espalda" and self._equipo() is not None and any(self._pilas.get("mochila", []))

    # Saca `cantidad` unidades de la pila; la Pila sacada, o None si no se puede (fija, índice o cantidad
    # inválidos, o mochila con cosas dentro).
    def quitar(self, ubicacion, indice, cantidad=1):
        pila = self._pila_en(ubicacion, indice)
        if pila is None or not _entero_valido(cantidad, 1, 999) or cantidad > pila.cantidad:
            return None
        if self.catalogo[pila.item_id].fijo or self._mochila_bloqueada(ubicacion, pila):
            return None
        sacada = Pila(pila.item_id, cantidad, copy.deepcopy(pila.datos))
        pila.cantidad -= cantidad
        if pila.cantidad <= 0:
            self._pilas[ubicacion].pop(indice)
        return sacada

    # Mueve la pila entera a otra ubicación (atómico).
    def mover(self, origen, indice, destino):
        pila = self._pila_en(origen, indice)
        if pila is None:
            return _no("indice", "No hay nada ahí.")
        defitem = self.catalogo[pila.item_id]
        if defitem.fijo:
            return _no("fijo", f"{_articulo(defitem.nombre).capitalize()} {defitem.nombre} no se puede mover.")
        if self._mochila_bloqueada(origen, pila):
            return _no("mochila_llena", "Vacía la mochila antes de quitártela.")
        if origen == destino:
            return _ok()
        snap = self._snapshot()
        cantidad, datos = pila.cantidad, copy.deepcopy(pila.datos)
        self._pilas[origen].pop(indice)
        resultado = self._guardar_sin_pesar(defitem, cantidad, destino, datos)
        if resultado.ok:
            resultado = self._comprobar_peso()
        if not resultado.ok:
            self._restaurar(snap)
            return resultado
        return _ok(f"Moviste {defitem.nombre}.")

    # Tira unidades al suelo: (Resultado, Pila|None).
    def soltar(self, ubicacion, indice, cantidad=1):
        pila = self._pila_en(ubicacion, indice)
        if pila is None:
            return _no("indice", "No hay nada ahí."), None
        defitem = self.catalogo[pila.item_id]
        if defitem.fijo:
            return _no("fijo", f"{_articulo(defitem.nombre).capitalize()} {defitem.nombre} no se puede soltar."), None
        if self._mochila_bloqueada(ubicacion, pila):
            return _no("mochila_llena", "Vacía la mochila antes de soltarla."), None
        sacada = self.quitar(ubicacion, indice, cantidad)
        if sacada is None:
            return _no("cantidad_invalida", "Cantidad inválida."), None
        return _ok(f"Soltaste {sacada.cantidad} × {defitem.nombre}."), sacada

    # Usa una unidad. Con efecto (efectos_items) lo aplica al `perfil` (puede ser None) y la consume si el
    # efecto es de consumo. Sin efecto: rechazo.
    def usar(self, ubicacion, indice, perfil=None):
        pila = self._pila_en(ubicacion, indice)
        if pila is None:
            return _no("indice", "No hay nada ahí.")
        defitem = self.catalogo[pila.item_id]
        if not defitem.efecto:
            return _no("sin_efecto", f"No sabes qué hacer con {_articulo(defitem.nombre)} {defitem.nombre} ahora.")
        from backend.logica import efectos_items
        efecto = efectos_items.aplicar(defitem.efecto, perfil, defitem)
        if efecto is None:
            return _no("sin_efecto", f"{defitem.nombre} no se puede usar.")
        if efecto.consumir:
            self.quitar(ubicacion, indice, 1)
        return _ok(efecto.mensaje)

    # -- Dinero --

    def _billetera(self):
        for lista in self._pilas.values():
            for pila in lista:
                if pila.item_id == "billetera" and self.catalogo[pila.item_id].fijo and "saldo" in pila.datos:
                    return pila
        return None

    def saldo(self):
        pila = self._billetera()
        return pila.datos["saldo"] if pila is not None else 0

    def ingresar(self, monto):
        if not _entero_valido(monto, 1, SALDO_MAX):
            return _no("monto_invalido", "El monto debe ser un entero positivo.")
        pila = self._billetera()
        if pila is None:
            return _no("sin_billetera", "No llevas billetera.")
        if pila.datos["saldo"] + monto > SALDO_MAX:
            return _no("saldo_maximo", "La billetera no aguanta tanto dinero.")
        pila.datos["saldo"] += monto
        return _ok(f"Recibiste R$ {monto}.")

    def cobrar(self, monto):
        if not _entero_valido(monto, 0, SALDO_MAX):
            return _no("monto_invalido", "El monto debe ser un entero no negativo.")
        pila = self._billetera()
        if pila is None:
            return _no("sin_billetera", "No llevas billetera.")
        if pila.datos["saldo"] < monto:
            return _no("sin_dinero", "Sin dinero.")
        pila.datos["saldo"] -= monto
        return _ok(f"Pagaste R$ {monto}.")

    # -- Serialización (JSON) --

    def a_dict(self):
        return {
            "pilas": {
                ub: [{"item": p.item_id, "cantidad": p.cantidad, "datos": copy.deepcopy(p.datos)} for p in lista]
                for ub, lista in self._pilas.items() if lista
            },
        }

    # Carga tolerante: datos mal formados no lanzan; lo inválido se descarta y queda en `avisos`.
    # Nunca falla por un objeto: si no cabe donde estaba, se intenta la colocación automática.
    @classmethod
    def desde_dict(cls, datos, catalogo):
        inv = cls(catalogo)
        inv._cargar(datos)
        return inv

    # Reemplaza las pilas por las de `datos` (misma validación que desde_dict).
    def _cargar(self, datos):
        self._pilas = {ub: [] for ub in self._ubicaciones}
        self.avisos = []
        if not isinstance(datos, dict) or not isinstance(datos.get("pilas", {}), dict):
            self.avisos.append("Inventario guardado ilegible: se empieza vacío.")
            return
        crudas = datos.get("pilas", {})
        orden = [ub for ub in self._ubicaciones if ub != "mochila"] + ["mochila"]   # la mochila va después de la espalda
        for ub in crudas:
            if ub not in self._ubicaciones:
                self.avisos.append(f"Ubicación desconocida descartada: {str(ub)[:30]!r}.")
        for ub in orden:
            lista = crudas.get(ub)
            if lista is None:
                continue
            if not isinstance(lista, list):
                self.avisos.append(f"Ubicación {ub} ilegible: descartada.")
                continue
            for bruta in lista[:MAX_PILAS_POR_UBICACION]:
                self._cargar_pila(ub, bruta)

    def _cargar_pila(self, ub, bruta):
        if not isinstance(bruta, dict):
            self.avisos.append("Entrada de inventario ilegible: descartada.")
            return
        item_id = bruta.get("item")
        if not isinstance(item_id, str) or item_id not in self.catalogo:
            self.avisos.append(f"Objeto desconocido descartado: {str(item_id)[:30]!r}.")
            return
        defitem = self.catalogo[item_id]
        cantidad = bruta.get("cantidad")
        if not _entero_valido(cantidad, 1, defitem.apilable):
            self.avisos.append(f"Cantidad inválida de {item_id}: descartado.")
            return
        datos = bruta.get("datos", {})
        datos = datos if isinstance(datos, dict) else {}
        limpios = {}
        for clave, valor in datos.items():
            # `saldo` solo se acepta en la billetera: un guardado manipulado no puede dar saldo a otro objeto.
            if clave == "saldo" and item_id == "billetera" and _entero_valido(valor, 0, SALDO_MAX):
                limpios["saldo"] = valor
            else:
                self.avisos.append(f"Dato inválido de {item_id} descartado.")
        if defitem.fijo and "saldo" not in limpios and item_id == "billetera":
            limpios["saldo"] = 0
        snap = self._snapshot()
        resultado = _no("x", "")
        for _ in range(cantidad):
            resultado = self._poner_una(ub, defitem, limpios)
            if not resultado.ok:
                break
        if resultado.ok:
            resultado = self._comprobar_peso()
        if resultado.ok:
            return
        self._restaurar(snap)
        # No cupo donde estaba: colocación automática; si tampoco, se descarta.
        resultado = self._guardar_sin_pesar(defitem, cantidad, None, limpios)
        if resultado.ok:
            resultado = self._comprobar_peso()
        if not resultado.ok:
            self._restaurar(snap)
            self.avisos.append(f"{defitem.nombre} no cabe: descartado.")
