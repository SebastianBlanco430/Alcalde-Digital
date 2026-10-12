# Fundido a negro (lógica pura, sin Ursina): máquina de dos fases que sube el alfa de 0 a 1
# (SALIENDO), ejecuta una acción con la pantalla ya negra (el cambio de escena) y baja el
# alfa de 1 a 0 (ENTRANDO). Se avanza a mano con avanzar(dt): el Entity de Ursina
# (frontend/transicion.py) lo llama cada frame con time.dt y los tests con dt fijos, así
# es determinista y se prueba sin ventana. Con duraciones 0 la acción corre al instante.
#
# Robustez: si la acción lanza una excepción el fundido se libera (alfa 0, no ocupado)
# antes de propagarla, para no dejar nunca la pantalla negra.

SALIENDO = "saliendo"
ENTRANDO = "entrando"


class Fundido:

    # duracion_salida / duracion_entrada en segundos (>= 0).
    def __init__(self, duracion_salida=0.25, duracion_entrada=0.25):
        if duracion_salida < 0 or duracion_entrada < 0:
            raise ValueError("Las duraciones del fundido no pueden ser negativas.")
        self.duracion_salida = duracion_salida
        self.duracion_entrada = duracion_entrada
        self._fase = None
        self._tiempo = 0.0
        self._accion = None

    # -- Consulta --

    # True mientras haya un fundido en curso (la pantalla puede estar parcial o totalmente negra).
    @property
    def ocupada(self):
        return self._fase is not None

    # Opacidad del negro: 0 = transparente, 1 = pantalla negra.
    @property
    def alfa(self):
        # Una fase de duración 0 no se puede dividir: salida 0 = ya negro, entrada 0 = ya claro.
        if self._fase == SALIENDO:
            if self.duracion_salida == 0:
                return 1.0
            return min(1.0, self._tiempo / self.duracion_salida)
        if self._fase == ENTRANDO:
            if self.duracion_entrada == 0:
                return 0.0
            return max(0.0, 1.0 - self._tiempo / self.duracion_entrada)
        return 0.0

    # -- Acciones --

    # Inicia un fundido que ejecutará `accion` con la pantalla en negro. Si ya había uno
    # en su fase de salida, su acción pendiente se ejecuta antes (no se pierde); si estaba
    # en la entrada, la nueva salida arranca desde el alfa actual (sin saltos).
    def ejecutar(self, accion):
        if self.duracion_salida == 0 and self.duracion_entrada == 0 and not self.ocupada:
            accion()
            return
        if self._fase == SALIENDO:
            self._cerrar_salida()
        alfa_actual = self.alfa
        self._accion = accion
        self._fase = SALIENDO
        if self.duracion_salida == 0:
            self._tiempo = 0.0
            self._cerrar_salida()
            if self.duracion_entrada == 0:
                self._liberar()
        else:
            self._tiempo = alfa_actual * self.duracion_salida

    # Avanza `dt` segundos. dt <= 0 o sin fundido en curso: no hace nada. Un dt grande
    # recorre ambas fases (la acción corre una sola vez).
    def avanzar(self, dt):
        if dt <= 0 or self._fase is None:
            return
        restante = dt
        if self._fase == SALIENDO:
            falta = self.duracion_salida - self._tiempo
            if restante < falta:
                self._tiempo += restante
                return
            restante -= falta
            self._cerrar_salida()
        if self._fase == ENTRANDO:
            falta = self.duracion_entrada - self._tiempo
            if restante < falta:
                self._tiempo += restante
                return
            self._liberar()

    # -- Internos --

    # Pantalla negra: corre la acción pendiente y pasa a la entrada.
    def _cerrar_salida(self):
        accion, self._accion = self._accion, None
        self._tiempo = self.duracion_salida
        try:
            if accion is not None:
                accion()
        except BaseException:
            self._liberar()
            raise
        self._fase = ENTRANDO
        self._tiempo = 0.0

    def _liberar(self):
        self._fase = None
        self._tiempo = 0.0
        self._accion = None
