# Perfil de economía de UN jugador (modelo puro): su inventario, fatiga (0..100), turnos trabajados, dinero
# ganado y un libro con los últimos movimientos. Vive en `Jugador.economia`, creado perezosamente con
# `perfil_de(jugador)` (los guardados viejos no lo traen). a_dict / desde_dict tolerantes y con validación:
# nunca lanzan por datos guardados raros; lo inválido se descarta o se pone en su valor por defecto.

from dataclasses import dataclass, field

from backend.datos.items_semilla import CATALOGO_ITEMS
from backend.logica.inventario import Inventario, _entero_valido, SALDO_MAX

FATIGA_MAX = 100
LIBRO_MAX = 20
LARGO_CONCEPTO = 60


@dataclass
class PerfilEconomia:
    inventario: Inventario
    fatiga: int = 0
    turnos: int = 0
    ganado: int = 0
    libro: list = field(default_factory=list)     # [{"concepto": str, "monto": int}], los últimos LIBRO_MAX
    avisos: list = field(default_factory=list)    # advertencias de desde_dict

    # Anota un movimiento (monto positivo = ingreso, negativo = gasto).
    def registrar(self, concepto, monto):
        self.libro.append({"concepto": str(concepto)[:LARGO_CONCEPTO], "monto": int(monto)})
        del self.libro[:-LIBRO_MAX]

    def agotado(self):
        return self.fatiga >= FATIGA_MAX

    def a_dict(self):
        return {
            "inventario": self.inventario.a_dict(),
            "fatiga": self.fatiga,
            "turnos": self.turnos,
            "ganado": self.ganado,
            "libro": [dict(m) for m in self.libro],
        }

    @classmethod
    def desde_dict(cls, datos, catalogo=None):
        catalogo = catalogo if catalogo is not None else CATALOGO_ITEMS
        if not isinstance(datos, dict):
            perfil = cls(Inventario(catalogo))
            perfil.avisos.append("Perfil de economía ilegible: se empieza de cero.")
            return perfil
        inventario = Inventario.desde_dict(datos.get("inventario"), catalogo)
        perfil = cls(inventario, avisos=list(inventario.avisos))
        for nombre, maximo in (("fatiga", FATIGA_MAX), ("turnos", SALDO_MAX), ("ganado", SALDO_MAX)):
            valor = datos.get(nombre, 0)
            if _entero_valido(valor, 0, maximo):
                setattr(perfil, nombre, valor)
            else:
                perfil.avisos.append(f"{nombre} inválido: se usa 0.")
        libro = datos.get("libro", [])
        for mov in libro[-LIBRO_MAX:] if isinstance(libro, list) else []:
            if (isinstance(mov, dict) and isinstance(mov.get("concepto"), str)
                    and _entero_valido(mov.get("monto"), -SALDO_MAX, SALDO_MAX)):
                perfil.libro.append({"concepto": mov["concepto"][:LARGO_CONCEPTO], "monto": mov["monto"]})
        return perfil


# Objetos con los que arranca cualquier rol: celular, billetera con R$ 20 y llaves. (`rol` queda para
# diferenciar kits más adelante; hoy es igual para todos.)
def kit_inicial(rol=None, catalogo=None):
    catalogo = catalogo if catalogo is not None else CATALOGO_ITEMS
    inventario = Inventario(catalogo)
    inventario.guardar("celular", ubicacion="bolsillo_der")
    inventario.guardar("billetera", ubicacion="bolsillo_trasero", datos={"saldo": 20})
    inventario.guardar("llaves", ubicacion="bolsillo_izq")
    return PerfilEconomia(inventario)


# Perfil del jugador; lo crea con el kit inicial la primera vez.
def perfil_de(jugador, catalogo=None):
    perfil = getattr(jugador, "economia", None)
    if perfil is None:
        perfil = kit_inicial(getattr(jugador, "rol", None), catalogo)
        jugador.economia = perfil
    return perfil
