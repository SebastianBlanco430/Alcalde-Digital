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
#
# «Seguir misión» (casilla del panel, tecla M): preferencia VISUAL de cada jugador. Marcada (por
# defecto) el mundo muestra las ayudas hacia el destino (baliza, ruta del piso, destino del minimapa,
# bandera destacada); desmarcada las oculta, pero la misión sigue igual (no toca su máquina de estados
# ni la E). Es de cada Jugador (su teléfono), así que en hot-seat cada uno conserva la suya; en línea
# no viaja por la red. Bandera SEGUIR_MISION: False = siempre marcada (lo de antes).

from dataclasses import dataclass, replace

CERRADO = "cerrado"
NOTIFICANDO = "notificando"
ABIERTO = "abierto"
ESTADOS = (CERRADO, NOTIFICANDO, ABIERTO)
SEGUIR_MISION = True


@dataclass
class Mensaje:
    texto: str
    remitente: str = "Civitas"
    leido: bool = False


class Telefono:

    def __init__(self):
        self._estado = CERRADO
        self._mensajes = []
        self._seguir_mision = True

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

    # ¿Se muestran las ayudas hacia el destino de la misión? (casilla «Seguir misión»)
    def sigue_mision(self):
        return self._seguir_mision or not SEGUIR_MISION

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

    # Marca o desmarca «Seguir misión». Devuelve el valor nuevo. No cambia el estado del teléfono.
    def alternar_seguir_mision(self):
        self._seguir_mision = not self._seguir_mision
        return self._seguir_mision

    def fijar_seguir_mision(self, valor):
        self._seguir_mision = bool(valor)

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
            "seguir_mision": self._seguir_mision,
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
        telefono._seguir_mision = bool(datos.get("seguir_mision", True))    # guardados de antes: marcada
        return telefono

    def __repr__(self):
        return (f"Telefono(estado={self._estado}, mensajes={len(self._mensajes)}, "
                f"seguir_mision={self._seguir_mision})")
