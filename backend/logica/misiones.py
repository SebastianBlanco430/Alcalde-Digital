# Misiones (modelo puro). Una misión lleva a un jugador a un lugar del mapa,
# donde juega un lote de noticias. SistemaMisiones es la máquina de estados de
# UNA misión activa a la vez (hot-seat: la del jugador del turno):
#
#   SIN_MISION -asignar-> NOTIFICADA -actualizar_posicion-> EN_RUTA
#   EN_RUTA <-> EN_RADIO (con histéresis)
#   EN_RADIO -iniciar_minijuego-> EN_MINIJUEGO -completar-> COMPLETADA
#   EN_MINIJUEGO -cancelar_minijuego-> EN_RADIO (revierte si no se pudo abrir el minijuego)
#   COMPLETADA -terminar-> SIN_MISION (libera el sistema para el siguiente jugador)
#
# El mapa (necesita `coordenada(lugar)`) y el catálogo se INYECTAN; así los
# tests usan versiones falsas. Toda transición inválida lanza ValueError.

import math
from dataclasses import dataclass

SIN_MISION = "sin_mision"
NOTIFICADA = "notificada"
EN_RUTA = "en_ruta"
EN_RADIO = "en_radio"
EN_MINIJUEGO = "en_minijuego"
COMPLETADA = "completada"
ESTADOS = (SIN_MISION, NOTIFICADA, EN_RUTA, EN_RADIO, EN_MINIJUEGO, COMPLETADA)


# rol None = misión genérica (sirve a cualquier rol). destino = nombre de lugar.
@dataclass(frozen=True)
class Mision:
    id: str
    rol: str | None
    titulo: str
    mensaje: str
    destino: str
    cantidad_noticias: int = 2


class SistemaMisiones:

    # Valida el catálogo: ids únicos y destinos con coordenada en el mapa
    # (ValueError si no).
    def __init__(self, mapa, catalogo, radio_interaccion=1.5, histeresis=0.3):
        self._mapa = mapa
        self._catalogo = list(catalogo)
        self.radio_interaccion = radio_interaccion
        self.histeresis = histeresis

        ids = set()
        for mision in self._catalogo:
            if mision.id in ids:
                raise ValueError(f"Id de misión repetido: {mision.id!r}")
            ids.add(mision.id)
            mapa.coordenada(mision.destino)  # lanza ValueError si no existe

        self._estado = SIN_MISION
        self._mision = None
        self._completadas = []
        self._resultado = None

    # -- Consulta --

    def estado(self):
        return self._estado

    def mision_actual(self):
        return self._mision

    # Ids de misiones completadas, en orden (copia).
    def completadas(self):
        return list(self._completadas)

    # Resultado de la última misión completada (se conserva tras terminar()).
    def resultado_ultimo(self):
        return self._resultado

    # Texto para el teléfono de la misión actual, o None si no hay.
    def mensaje_notificacion(self):
        return self._mision.mensaje if self._mision is not None else None

    def puede_interactuar(self):
        return self._estado == EN_RADIO

    # True si queda alguna misión sin completar del rol o genérica.
    def hay_misiones_pendientes(self, rol):
        return self._buscar_pendiente(rol) is not None

    # -- Transiciones --

    # Primera misión no completada del rol; si no hay, la primera genérica; si
    # tampoco, None (queda SIN_MISION). ValueError si ya hay una misión activa.
    def asignar(self, jugador):
        if self._estado != SIN_MISION:
            raise ValueError(
                f"Ya hay una misión activa (estado {self._estado!r}); termínala antes de asignar otra."
            )
        mision = self._buscar_pendiente(jugador.rol)
        if mision is None:
            return None
        self._mision = mision
        self._estado = NOTIFICADA
        return mision

    # Actualiza el estado según la distancia XZ al destino. NOTIFICADA pasa a
    # EN_RUTA en la primera actualización y, en esa misma llamada, se evalúa el
    # radio (así no hace falta una segunda actualización si ya está cerca).
    # Histéresis: entra a EN_RADIO a <= radio; sale a > radio + histéresis.
    # En los demás estados no hace nada.
    def actualizar_posicion(self, x, z):
        if self._estado == NOTIFICADA:
            self._estado = EN_RUTA
        if self._estado not in (EN_RUTA, EN_RADIO):
            return

        cx, cz = self._mapa.coordenada(self._mision.destino)
        distancia = math.hypot(x - cx, z - cz)
        if self._estado == EN_RUTA and distancia <= self.radio_interaccion:
            self._estado = EN_RADIO
        elif self._estado == EN_RADIO and distancia > self.radio_interaccion + self.histeresis:
            self._estado = EN_RUTA

    def iniciar_minijuego(self):
        self._exigir(EN_RADIO, "iniciar el minijuego")
        self._estado = EN_MINIJUEGO

    # Revierte iniciar_minijuego (EN_MINIJUEGO -> EN_RADIO) cuando el minijuego no llegó a
    # abrirse; la misión no cuenta como completada y se puede volver a intentar.
    def cancelar_minijuego(self):
        self._exigir(EN_MINIJUEGO, "cancelar el minijuego")
        self._estado = EN_RADIO

    # Guarda el resultado, registra la misión como completada y la devuelve.
    def completar(self, resultado):
        self._exigir(EN_MINIJUEGO, "completar la misión")
        self._resultado = resultado
        self._completadas.append(self._mision.id)
        self._estado = COMPLETADA
        return self._mision

    # COMPLETADA -> SIN_MISION; el resultado_ultimo se conserva.
    def terminar(self):
        self._exigir(COMPLETADA, "terminar la misión")
        self._mision = None
        self._estado = SIN_MISION

    # -- Serialización (JSON) --
    # El resultado debe ser JSON-serializable (p. ej. dict de deltas).

    def a_dict(self):
        return {
            "estado": self._estado,
            "mision_actual": self._mision.id if self._mision is not None else None,
            "completadas": list(self._completadas),
            "resultado": self._resultado,
            "radio_interaccion": self.radio_interaccion,
            "histeresis": self.histeresis,
        }

    # ValueError si el estado no existe o es incoherente con la misión guardada (un estado
    # activo exige misión; SIN_MISION no puede tener una). Los guardados antiguos sin
    # radio_interaccion / histeresis usan los valores por defecto.
    @classmethod
    def desde_dict(cls, datos, mapa, catalogo):
        estado = datos["estado"]
        if estado not in ESTADOS:
            raise ValueError(f"Estado de misión desconocido en los datos guardados: {estado!r}")
        id_actual = datos["mision_actual"]
        if (estado == SIN_MISION) != (id_actual is None):
            raise ValueError(
                f"Estado {estado!r} incoherente con la misión guardada {id_actual!r}."
            )
        extras = {k: datos[k] for k in ("radio_interaccion", "histeresis") if k in datos}
        sistema = cls(mapa, catalogo, **extras)
        por_id = {m.id: m for m in sistema._catalogo}
        if id_actual is not None and id_actual not in por_id:
            raise ValueError(f"Misión desconocida en los datos guardados: {id_actual!r}")
        sistema._estado = estado
        sistema._mision = por_id[id_actual] if id_actual is not None else None
        sistema._completadas = list(datos["completadas"])
        sistema._resultado = datos["resultado"]
        return sistema

    # -- Internos --

    def _exigir(self, estado_requerido, accion):
        if self._estado != estado_requerido:
            raise ValueError(
                f"No se puede {accion} en el estado {self._estado!r}; se requiere {estado_requerido!r}."
            )

    def _buscar_pendiente(self, rol):
        for mision in self._catalogo:
            if mision.rol == rol and mision.id not in self._completadas:
                return mision
        for mision in self._catalogo:
            if mision.rol is None and mision.id not in self._completadas:
                return mision
        return None
