# Límites de tasa del anfitrión: cubos de fichas (token bucket) por conexión y por tipo de
# mensaje, veto temporal por IP e infracciones acumuladas. Módulo PURO con reloj inyectable
# (`reloj` es un callable sin argumentos que devuelve segundos; por defecto time.monotonic).
import time

from backend.red import protocolo


class CuboFichas:
    """Cubo de fichas: `tasa` fichas/s, capacidad `rafaga`. Empieza lleno."""

    def __init__(self, tasa, rafaga, reloj=time.monotonic):
        self.tasa = float(tasa)
        self.rafaga = float(rafaga)
        self._reloj = reloj
        self._fichas = float(rafaga)
        self._ultimo = reloj()

    def _rellenar(self):
        ahora = self._reloj()
        dt = max(0.0, ahora - self._ultimo)    # un reloj que retrocede no resta fichas
        self._ultimo = ahora
        self._fichas = min(self.rafaga, self._fichas + dt * self.tasa)

    def tomar(self, n=1.0):
        """Consume `n` fichas; True si había suficientes (si no, no consume nada)."""
        self._rellenar()
        if self._fichas >= n:
            self._fichas -= n
            return True
        return False

    def disponibles(self):
        self._rellenar()
        return self._fichas


class LimiteConexion:
    """Control de una conexión: cubo global + un cubo por tipo + infracciones.

    `admitir(tipo)` -> True si el mensaje puede procesarse. Cuando devuelve False se cuenta
    una infracción; al llegar a `max_infracciones` `debe_cerrar()` pasa a True.
    """

    def __init__(self, reloj=time.monotonic,
                 sostenido=protocolo.LIMITE_MSG_SOSTENIDO, rafaga=protocolo.LIMITE_MSG_RAFAGA,
                 por_tipo=None, max_infracciones=20):
        self._reloj = reloj
        self._global = CuboFichas(sostenido, rafaga, reloj)
        tipos = protocolo.LIMITES_POR_TIPO if por_tipo is None else por_tipo
        # Cada tipo tiene tasa sostenida y una ráfaga igual a la tasa (mínimo 1)
        self._tipos = {t: CuboFichas(v, max(1, v), reloj) for t, v in tipos.items()}
        self.max_infracciones = int(max_infracciones)
        self.infracciones = 0

    def registrar_infraccion(self, n=1):
        self.infracciones += int(n)

    def admitir(self, tipo):
        if not self._global.tomar():
            self.registrar_infraccion()
            return False
        cubo = self._tipos.get(tipo)
        if cubo is not None and not cubo.tomar():
            self.registrar_infraccion()
            return False
        return True

    def debe_cerrar(self):
        return self.infracciones >= self.max_infracciones


class VetoPorIP:
    """Cuenta fallos de autenticación por IP en una ventana y veta temporalmente.

    5 fallos en 60 s -> veto de 60 s (valores por defecto del diseño). Todo en memoria.
    """

    def __init__(self, reloj=time.monotonic, max_fallos=5, ventana=60.0, duracion_veto=60.0):
        self._reloj = reloj
        self.max_fallos = int(max_fallos)
        self.ventana = float(ventana)
        self.duracion_veto = float(duracion_veto)
        self._fallos = {}      # ip -> lista de instantes
        self._vetos = {}       # ip -> instante en que termina el veto

    def registrar_fallo(self, ip):
        ahora = self._reloj()
        recientes = [t for t in self._fallos.get(ip, []) if ahora - t < self.ventana]
        recientes.append(ahora)
        if len(recientes) >= self.max_fallos:
            self._vetos[ip] = ahora + self.duracion_veto
            recientes = []
        self._fallos[ip] = recientes

    def registrar_exito(self, ip):
        self._fallos.pop(ip, None)

    def vetada(self, ip):
        fin = self._vetos.get(ip)
        if fin is None:
            return False
        if self._reloj() >= fin:
            del self._vetos[ip]
            return False
        return True

    def segundos_restantes(self, ip):
        fin = self._vetos.get(ip)
        return max(0.0, fin - self._reloj()) if fin is not None else 0.0

    def limpiar(self):
        """Olvida entradas caducadas (llamar de vez en cuando para acotar la memoria)."""
        ahora = self._reloj()
        self._vetos = {ip: f for ip, f in self._vetos.items() if f > ahora}
        self._fallos = {ip: [t for t in ts if ahora - t < self.ventana]
                        for ip, ts in self._fallos.items()}
        self._fallos = {ip: ts for ip, ts in self._fallos.items() if ts}


class ConteoConexiones:
    """Máximo de conexiones totales y por IP (8 y 2 por defecto)."""

    def __init__(self, maximo=protocolo.MAX_CONEXIONES, por_ip=protocolo.MAX_CONEXIONES_POR_IP):
        self.maximo = int(maximo)
        self.por_ip = int(por_ip)
        self._por_ip = {}

    def total(self):
        return sum(self._por_ip.values())

    def puede_entrar(self, ip):
        return self.total() < self.maximo and self._por_ip.get(ip, 0) < self.por_ip

    def entrar(self, ip):
        """Registra una conexión; False (sin registrar) si se superan los topes."""
        if not self.puede_entrar(ip):
            return False
        self._por_ip[ip] = self._por_ip.get(ip, 0) + 1
        return True

    def salir(self, ip):
        n = self._por_ip.get(ip, 0) - 1
        if n <= 0:
            self._por_ip.pop(ip, None)
        else:
            self._por_ip[ip] = n
