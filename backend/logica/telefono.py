# Teléfono del jugador (modelo puro): bandeja de mensajes de Civitas y una
# máquina de estados CERRADO / NOTIFICANDO / ABIERTO. Vive en paralelo al
# movimiento (estado concurrente), no es una escena.
#
#   CERRADO --notificar--> NOTIFICANDO --terminar_notificacion--> CERRADO
#   CERRADO/NOTIFICANDO --abrir--> ABIERTO --cerrar--> CERRADO
#
# Decisión de diseño: mientras está ABIERTO el jugador no se mueve
# (bloquea_movimiento). El tiempo de la notificación lo maneja la vista, que
# llama a terminar_notificacion(); aquí no hay reloj.

from dataclasses import dataclass, replace

CERRADO = "cerrado"
NOTIFICANDO = "notificando"
ABIERTO = "abierto"
ESTADOS = (CERRADO, NOTIFICANDO, ABIERTO)


@dataclass
class Mensaje:
    texto: str
    remitente: str = "Civitas"
    leido: bool = False


class Telefono:

    def __init__(self):
        self._estado = CERRADO
        self._mensajes = []

    # -- Consulta --

    def estado(self):
        return self._estado

    # Copia en orden cronológico (los Mensaje también se copian).
    def mensajes(self):
        return [replace(m) for m in self._mensajes]

    def no_leidos(self):
        return sum(1 for m in self._mensajes if not m.leido)

    # True solo con el teléfono ABIERTO.
    def bloquea_movimiento(self):
        return self._estado == ABIERTO

    # -- Transiciones --

    # Agrega un mensaje. Abierto: queda leído y el estado no cambia.
    # Cerrado: pasa a NOTIFICANDO. Notificando: se mantiene.
    def notificar(self, texto, remitente="Civitas"):
        leido = self._estado == ABIERTO
        self._mensajes.append(Mensaje(texto=texto, remitente=remitente, leido=leido))
        if self._estado == CERRADO:
            self._estado = NOTIFICANDO

    # Abre el teléfono y marca todo como leído.
    def abrir(self):
        self._estado = ABIERTO
        for mensaje in self._mensajes:
            mensaje.leido = True

    def cerrar(self):
        self._estado = CERRADO

    def alternar(self):
        if self._estado == ABIERTO:
            self.cerrar()
        else:
            self.abrir()

    # NOTIFICANDO -> CERRADO (los mensajes siguen sin leer); otros estados: nada.
    def terminar_notificacion(self):
        if self._estado == NOTIFICANDO:
            self._estado = CERRADO

    # -- Serialización (JSON) --

    def a_dict(self):
        return {
            "estado": self._estado,
            "mensajes": [
                {"texto": m.texto, "remitente": m.remitente, "leido": m.leido}
                for m in self._mensajes
            ],
        }

    # ValueError si el estado guardado no es CERRADO / NOTIFICANDO / ABIERTO.
    @classmethod
    def desde_dict(cls, datos):
        if datos["estado"] not in ESTADOS:
            raise ValueError(f"Estado de teléfono inválido en los datos guardados: {datos['estado']!r}")
        telefono = cls()
        telefono._estado = datos["estado"]
        telefono._mensajes = [
            Mensaje(texto=m["texto"], remitente=m["remitente"], leido=m["leido"])
            for m in datos["mensajes"]
        ]
        return telefono

    def __repr__(self):
        return f"Telefono(estado={self._estado}, mensajes={len(self._mensajes)})"
