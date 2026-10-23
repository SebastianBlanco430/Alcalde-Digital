# Enlace simulado EN PROCESO con reloj virtual (solo stdlib, sin sockets ni hilos) para pruebas
# deterministas. T4 ya cubre el protocolo con localhost real; esto aporta lo que ese camino no
# puede dar sin flakiness: latencia, jitter, pérdida, duplicados, reordenado y cortes
# REPRODUCIBLES (semilla fija) sobre mensajes que pasan por el codec real
# (protocolo.codificar / decodificar), de modo que PartidaCooperativa -> traducción de eventos ->
# bytes -> enlace -> decodificar -> sanear_mensaje -> InterpoladorRemoto se prueba sin dormir.
#
#   reloj = RelojVirtual()
#   enlace = EnlaceSimulado(reloj, latencia=0.05, jitter=0.03, perdida=0.02, semilla=1)
#   enlace.enviar({"t": "snap", ...}, protocolo.DIR_H2C)       # codifica con el codec real
#   reloj.avanzar(0.05); for msg in enlace.recibir(): ...       # decodifica lo ya entregado
#
# Un mensaje que el codec rechaza (esquema) lanza ErrorProtocolo en enviar(): es una prueba de
# contrato gratis de todo lo que el anfitrión genera. NUNCA importa ursina ni panda3d.
import heapq
import random

from backend.red import protocolo


class RelojVirtual:
    """Reloj que solo avanza cuando se le ordena (callable, como time.monotonic)."""

    def __init__(self, t=0.0):
        self.t = float(t)

    def __call__(self):
        return self.t

    def avanzar(self, s):
        if s < 0:
            raise ValueError("El tiempo no retrocede.")
        self.t += s
        return self.t


class EnlaceSimulado:
    """Un sentido de la red. Entrega los bytes de cada línea tras latencia + jitter (uniforme en
    [0, jitter]); puede perder, duplicar y desordenar (si `ordenado=False`; con TCP real el orden
    se conserva, por eso el defecto es ordenado y la entrega nunca retrocede)."""

    def __init__(self, reloj, latencia=0.0, jitter=0.0, perdida=0.0, duplicado=0.0, ordenado=True,
                 semilla=0):
        self.reloj = reloj
        self.latencia = float(latencia)
        self.jitter = float(jitter)
        self.perdida = float(perdida)
        self.duplicado = float(duplicado)
        self.ordenado = bool(ordenado)
        self._azar = random.Random(semilla)
        self._cola = []                 # (entrega, secuencia, bytes)
        self._seq = 0
        self._ultima_entrega = 0.0
        self.cortado = False
        self.enviados = 0
        self.perdidos = 0
        self.entregados = 0

    def cortar(self):
        """Corte de red: lo que viaja se pierde y lo nuevo también, hasta restablecer()."""
        self.cortado = True
        self._cola.clear()

    def restablecer(self):
        self.cortado = False

    def enviar_bytes(self, datos):
        self.enviados += 1
        if self.cortado or self._azar.random() < self.perdida:
            self.perdidos += 1
            return
        copias = 2 if self._azar.random() < self.duplicado else 1
        for _ in range(copias):
            entrega = self.reloj() + self.latencia + (self._azar.uniform(0.0, self.jitter) if self.jitter else 0.0)
            if self.ordenado:
                entrega = max(entrega, self._ultima_entrega)
                self._ultima_entrega = entrega
            self._seq += 1
            heapq.heappush(self._cola, (entrega, self._seq, datos))

    def enviar(self, mensaje, direccion):
        """Codifica con el codec real (valida el esquema) y lo pone en vuelo."""
        datos = protocolo.codificar(mensaje, direccion)
        self.enviar_bytes(datos)
        return datos

    def pendientes(self):
        return len(self._cola)

    def entregar_bytes(self):
        """Líneas (bytes) cuya hora de entrega ya llegó, en orden de entrega."""
        salida = []
        ahora = self.reloj()
        while self._cola and self._cola[0][0] <= ahora:
            salida.append(heapq.heappop(self._cola)[2])
        self.entregados += len(salida)
        return salida

    def recibir(self, direccion):
        """Mensajes ya decodificados y validados. Las líneas inválidas se descartan (se cuentan
        en `rechazados`), como haría el receptor real."""
        mensajes = []
        for datos in self.entregar_bytes():
            try:
                mensajes.append(protocolo.decodificar(datos, direccion))
            except protocolo.ErrorProtocolo:
                self.rechazados = getattr(self, "rechazados", 0) + 1
        return mensajes
