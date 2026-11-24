# Tipos compartidos del motor de casos v2 (modelo puro, sin motor gráfico). Los escribe el orquestador de la sesión A
# como CONTRATO entre el motor (backend/logica/casos_v2.py), la escena 3D (frontend/fiscalia/) y su interfaz. Formato
# del JSON: sesiones-24nov/fiscalia/contrato-caso.md. Aquí solo hay datos inmutables y la forma de la sesión.
#
# Regla: el frontend NUNCA lee el dict del JSON; solo usa estas vistas y los métodos de `SesionCaso` de abajo.

from dataclasses import dataclass
from typing import Protocol

ESCENAS = ("oficina", "laboratorio", "sala")
TIPOS_NODO = ("dialogo", "rueda", "laboratorio", "acusacion", "final")
RESULTADOS = ("exito", "parcial", "fracaso")
PLANOS = ("general", "pecho", "primer_plano", "contraplano")
MAX_OPCIONES = 4
TERMINAR = "@terminar"
VOLVER = "@volver"
PISTA_POR_DEFECTO = "[Falta una prueba]"

# Estado de una opción de la rueda.
LIBRE, BLOQUEADA = "libre", "bloqueada"


@dataclass(frozen=True)
class VistaOpcion:
    id: str
    etiqueta: str                 # 1-3 palabras: lo que se ve en la rueda
    estado: str = LIBRE           # LIBRE | BLOQUEADA (hueco con candado). Las ya usadas y las ocultas NO vienen.
    pista: str = ""               # texto del hueco bloqueado («[Falta una prueba]»)
    dice: str = ""                # frase completa del jugador al elegirla (puede ser "")
    presenta: str | None = None   # id de la prueba que pone sobre la mesa (para mostrar su ficha)
    personaje: str | None = None  # solo en acusación: a quién acusa (ficha del tablero)
    posicion: int = 0             # 0-3: hueco fijo de la rueda (orden del JSON), para que no salten al gastarse otras


@dataclass(frozen=True)
class VistaNodo:
    id: str
    tipo: str                     # uno de TIPOS_NODO
    escena: str | None            # una de ESCENAS; None en los finales
    personaje: str | None         # id del personaje que habla; None = narrador
    expresion: str | None
    texto: str
    plano: str | None = None      # uno de PLANOS o None (la cámara elige)
    titulo: str = ""              # solo en finales
    resultado: str | None = None  # solo en finales
    opciones: tuple = ()          # VistaOpcion (rueda y acusación), en orden de `posicion`
    reloj_segundos: float | None = None   # None = sin reloj
    restante: float | None = None
    turnos_restantes: int | None = None   # None = sin límite de turnos


@dataclass(frozen=True)
class VistaParkour:
    nivel: str                    # «sector_1» | «sector_2»
    nombre: str                   # nombre en la ficción del caso («Servidor fantasma»)
    descripcion: str
    evidencia: str                # id (sin prefijo) de la prueba que da
    nombre_evidencia: str
    completado: bool


# Lo que pasó desde la última vez que se pidió (para animar «▲ +8 %», la ficha de una prueba nueva...).
@dataclass(frozen=True)
class Cambio:
    tipo: str                     # «solidez» | «evidencia»
    delta: int = 0                # solidez: lo que subió o bajó de verdad (ya recortado a 0..100)
    valor: int = 0                # solidez después del cambio
    evidencia: str | None = None  # id de la prueba conseguida (tipo «evidencia»)
    nombre: str = ""              # nombre visible de la prueba
    motivo: str = ""              # «opcion» | «nodo» | «evidencia» | «parkour»


@dataclass(frozen=True)
class NodoDiagrama:
    id: str
    etiqueta: str                 # texto del hito; lo muestra solo si `visto`
    tipo: str                     # tipo del nodo (para el dibujo: final, laboratorio, acusación...)
    capa: int                     # columna (orden topológico por capas, 0 = inicio)
    fila: int                     # posición dentro de la capa
    visto: bool
    resultado: str | None = None  # en finales


@dataclass(frozen=True)
class Diagrama:
    nodos: tuple                  # NodoDiagrama
    aristas: tuple                # (id_origen, id_destino, recorrida: bool)
    capas: int
    filas_max: int
    vistos: int
    total: int

    @property
    def porcentaje(self):
        return 0 if not self.total else int(round(100 * self.vistos / self.total))


# Forma de la sesión que implementa backend/logica/casos_v2.SesionCasoV2 (y cualquier sesión falsa de pruebas).
class SesionCaso(Protocol):
    caso: object                  # CasoV2: .id .titulo .resumen .personajes (dict) .evidencias (dict) .umbrales (dict)
    solidez: int                  # 0..100

    @property
    def terminado(self) -> bool: ...
    def vista(self) -> VistaNodo: ...
    def continuar(self) -> None: ...                       # en «dialogo»
    def elegir(self, id_opcion: str, por_tiempo: bool = False) -> None: ...   # en «rueda» y «acusacion»
    def avanzar_tiempo(self, dt: float) -> bool: ...       # True si el reloj se agotó y eligió sola
    def parkours(self) -> tuple: ...                       # VistaParkour del caso ((), si no tiene laboratorio)
    def completar_parkour(self, nivel: str) -> bool: ...   # en «laboratorio»: entrega su prueba; False si ya la tenía
    def salir_laboratorio(self) -> None: ...               # en «laboratorio»: sigue al siguiente nodo (se cierra)
    def abandonar(self) -> None: ...                       # cierra el caso en `final_abandono`
    def tomar_cambios(self) -> tuple: ...                  # Cambio, en orden; vacía la lista
    def evidencias_en_mano(self) -> tuple: ...             # ids (sin prefijo) de las pruebas del caso que ya tiene
    def visitados(self) -> set: ...
    def diagrama(self) -> Diagrama: ...
    def a_dict(self) -> dict: ...
