# Escritorio y cuarto de la familia PC (Ursina): lo que se añade a la oficina del lugar (sets.py, set «interior»), colgado
# de ella y registrado con set.nueva() para que se destruya al cerrar el minijuego. Nada de esto decide nada del juego.
#
#   - ratón CLARO que se mueve en la mesa con el puntero (y la mano encima) y cuyo botón se hunde al hacer clic;
#   - alfombrilla, teclado claro (tapa el oscuro de la oficina) con la tecla pulsada resaltada;
#   - un libro cerrado que tapa el ratón oscuro de la oficina (que va pegado en su malla combinada);
#   - cuarto: ventana en la pared del fondo a la derecha del monitor, estante con libros y afiche a la izquierda, taza y
#     planta en el escritorio. Todo con el shader del juego (sombra cel violeta) y la tinta del pase final.
# Coordenadas de MUNDO (= las de la oficina: está en el origen sin rotar). Medidas en metros.

from ursina import Entity
from ursina.shaders import lit_with_shadows_shader

from frontend.componentes import rgb
from frontend.minijuegos_3d import pc_calculos as calc
from frontend.piezas import pieza, silenciar

RATON_CLARO = (236, 238, 242)
RATON_BOTON = (214, 218, 226)
ALFOMBRILLA = (64, 120, 170)
TECLADO_CLARO = (226, 228, 234)
TECLA = (246, 247, 250)
TECLA_PULSADA = (255, 214, 102)              # amarillo del foco de los minijuegos
LIBRO = (170, 60, 64)
LIBRO_PAGINAS = (244, 238, 222)
MADERA = (150, 104, 66)
MADERA_OSCURA = (96, 66, 44)

Y_MESA = 0.755                               # tablero del escritorio de la oficina (EscenaInterior._escritorio)
RATON_CASA = (1.50, 1.685)                   # (x, z) del ratón claro con el puntero en el centro del monitor
TECLADO = (1.2, 1.78)                        # centro del teclado de la oficina (x, z)
Y_TECLA = Y_MESA + 0.0325                    # centro de la tecla resaltada: 1,5 mm por encima de las teclas (tapa 0,786)
HUNDIDO_TECLA = 0.0015                       # lo que baja al pulsarla: nunca se mete dentro de las teclas (se ocultaba)
DURACION_TECLA = 0.3
PARED_FONDO = 2.5                            # z de la pared norte (guion.SALA_FONDO / 2)


class Escritorio:
    """Piezas del escritorio y del cuarto. `padre` = la oficina (set.raiz); `nueva` = set.nueva (registro para destruir)."""

    def __init__(self, padre, nueva):
        self.padre = padre
        self._nueva = nueva
        self._t_clic = None
        self._t_tecla = None
        self._fijo()
        self._cuarto()
        self._moviles()

    # -- Construcción --

    def _grupo(self):
        return self._nueva(Entity(parent=self.padre, shader=lit_with_shadows_shader))

    def _fijo(self):
        """Alfombrilla, teclado claro con sus teclas y el libro que tapa el ratón oscuro: una sola malla."""
        g = self._grupo()
        x, z = RATON_CASA
        pieza(parent=g, model="cube", color=rgb(ALFOMBRILLA), position=(x, Y_MESA + 0.0015, z + 0.005),
              scale=(0.17, 0.003, 0.14))
        tx, tz = TECLADO
        pieza(parent=g, model="cube", color=rgb(TECLADO_CLARO), position=(tx, Y_MESA + 0.016, tz), scale=(0.475, 0.024, 0.16))
        for fila, zf in enumerate((0.05, 0.03, 0.01, -0.01)):
            pieza(parent=g, model="cube", color=rgb(TECLA), position=(tx - 0.02 + fila * 0.004, Y_MESA + 0.029, tz + zf),
                  scale=(0.36, 0.004, 0.015))
        pieza(parent=g, model="cube", color=rgb(TECLA), position=(tx - 0.06, Y_MESA + 0.029, tz - 0.04), scale=(0.16, 0.004, 0.016))
        pieza(parent=g, model="cube", color=rgb(TECLA), position=(tx + 0.185, Y_MESA + 0.029, tz - 0.035), scale=(0.06, 0.004, 0.04))
        # libro cerrado encima del ratón oscuro de la oficina (x 1,565-1,635; z 1,745-1,855; 2,5 cm de alto)
        pieza(parent=g, model="cube", color=rgb(LIBRO_PAGINAS), position=(1.65, Y_MESA + 0.02, 1.86), scale=(0.17, 0.036, 0.23))
        pieza(parent=g, model="cube", color=rgb(LIBRO), position=(1.65, Y_MESA + 0.039, 1.86), scale=(0.18, 0.006, 0.24))
        pieza(parent=g, model="cube", color=rgb(LIBRO), position=(1.65, Y_MESA + 0.0015, 1.86), scale=(0.18, 0.003, 0.24))
        pieza(parent=g, model="cube", color=rgb(LIBRO), position=(1.739, Y_MESA + 0.02, 1.86), scale=(0.006, 0.04, 0.24))
        g.combine()
        silenciar(g)

    def _cuarto(self):
        """Ventana a la derecha del monitor, estante con libros y afiche a la izquierda, taza y planta (una malla)."""
        g = self._grupo()
        z = PARED_FONDO
        # ventana (pared norte, a la derecha del monitor): marco, vidrio, cruz y alféizar
        wx, wy = 2.25, 1.6
        pieza(parent=g, model="cube", color=rgb((236, 236, 240)), position=(wx, wy, z - 0.03), scale=(0.9, 0.95, 0.06))
        pieza(parent=g, model="cube", color=rgb((150, 205, 235)), position=(wx, wy, z - 0.065), scale=(0.78, 0.83, 0.02))
        pieza(parent=g, model="cube", color=rgb((236, 236, 240)), position=(wx, wy, z - 0.08), scale=(0.04, 0.83, 0.02))
        pieza(parent=g, model="cube", color=rgb((236, 236, 240)), position=(wx, wy, z - 0.08), scale=(0.78, 0.04, 0.02))
        pieza(parent=g, model="cube", color=rgb((236, 236, 240)), position=(wx, wy - 0.5, z - 0.08), scale=(0.98, 0.05, 0.14))
        # nubes del cielo (dos manchas blancas) para que se lea como ventana
        pieza(parent=g, model="sphere", color=rgb((250, 252, 255)), position=(wx - 0.18, wy + 0.2, z - 0.06), scale=(0.22, 0.08, 0.01))
        pieza(parent=g, model="sphere", color=rgb((250, 252, 255)), position=(wx + 0.16, wy + 0.08, z - 0.06), scale=(0.18, 0.06, 0.01))
        # estante con libros (izquierda del monitor) y afiche encima
        sx, sy = 0.22, 1.42
        pieza(parent=g, model="cube", color=rgb(MADERA), position=(sx, sy, z - 0.11), scale=(0.62, 0.03, 0.2))
        for k, (ancho, alto, tono) in enumerate(((0.05, 0.2, (190, 70, 70)), (0.04, 0.17, (70, 110, 190)),
                                                 (0.06, 0.22, (230, 190, 80)), (0.045, 0.19, (90, 160, 100)),
                                                 (0.05, 0.16, (220, 60, 160)))):
            pieza(parent=g, model="cube", color=rgb(tono), position=(sx - 0.2 + k * 0.065, sy + 0.015 + alto / 2, z - 0.11),
                  scale=(ancho, alto, 0.15))
        pieza(parent=g, model="cube", color=rgb((246, 240, 226)), position=(sx + 0.05, 1.86, z - 0.012), scale=(0.42, 0.54, 0.01))
        pieza(parent=g, model="cube", color=rgb((234, 120, 90)), position=(sx + 0.05, 1.93, z - 0.018), scale=(0.34, 0.26, 0.004))
        pieza(parent=g, model="cube", color=rgb((40, 42, 52)), position=(sx + 0.05, 1.71, z - 0.018), scale=(0.3, 0.025, 0.004))
        pieza(parent=g, model="cube", color=rgb((40, 42, 52)), position=(sx + 0.02, 1.67, z - 0.018), scale=(0.24, 0.02, 0.004))
        # taza (izquierda del teclado) y planta (fondo derecho del escritorio)
        pieza(parent=g, model="cube", color=rgb((240, 240, 244)), position=(0.78, Y_MESA + 0.045, 1.82), scale=(0.075, 0.09, 0.075))
        pieza(parent=g, model="cube", color=rgb((120, 70, 40)), position=(0.78, Y_MESA + 0.086, 1.82), scale=(0.06, 0.006, 0.06))
        pieza(parent=g, model="cube", color=rgb((240, 240, 244)), position=(0.735, Y_MESA + 0.05, 1.82), scale=(0.02, 0.05, 0.012))
        pieza(parent=g, model="cube", color=rgb((176, 100, 70)), position=(1.88, Y_MESA + 0.07, 2.22), scale=(0.16, 0.14, 0.16))
        pieza(parent=g, model="sphere", color=rgb((70, 150, 80)), position=(1.88, Y_MESA + 0.25, 2.22), scale=(0.28, 0.26, 0.26))
        pieza(parent=g, model="sphere", color=rgb((90, 170, 90)), position=(1.95, Y_MESA + 0.36, 2.2), scale=(0.16, 0.16, 0.16))
        g.combine()
        silenciar(g)

    def _moviles(self):
        """Ratón claro (cuerpo + botón que se hunde) y la tecla resaltada: entidades sueltas que se mueven."""
        x, z = RATON_CASA
        self.raton = self._nueva(pieza(parent=self.padre, model="sphere", color=rgb(RATON_CLARO),
                                       position=(x, Y_MESA + 0.004, z), scale=(0.062, 0.052, 0.105)))
        self.boton = pieza(parent=self.padre, model="cube", color=rgb(RATON_BOTON),
                           position=(x - 0.012, Y_MESA + 0.027, z + 0.024), scale=(0.026, 0.006, 0.04))
        self._nueva(self.boton)
        self.linea = pieza(parent=self.padre, model="cube", color=rgb((120, 124, 136)),
                           position=(x, Y_MESA + 0.03, z + 0.026), scale=(0.002, 0.004, 0.04))
        self._nueva(self.linea)
        self.tecla = self._nueva(pieza(parent=self.padre, model="cube", color=rgb(TECLA_PULSADA),
                                       position=(TECLADO[0], Y_TECLA, TECLADO[1]),
                                       scale=(calc.ANCHO_TECLA, 0.004, calc.ANCHO_TECLA), enabled=False))
        for e in (self.raton, self.boton, self.linea, self.tecla):
            silenciar(e)
        self.centro = (x, Y_MESA + 0.004, z)

    # -- Cada frame --

    def colocar_raton(self, dx, dz):
        """Pone el ratón en la mesa desplazado (dx, dz) de su casa. Devuelve su centro (mundo)."""
        x, z = RATON_CASA[0] + dx, RATON_CASA[1] + dz
        hundido = calc.HUNDIDO_BOTON * calc.curva_pulso(self._t_clic or 0.0, calc.DURACION_CLIC_RATON) \
            if self._t_clic is not None else 0.0
        self.raton.position = (x, Y_MESA + 0.004, z)
        self.boton.position = (x - 0.012, Y_MESA + 0.027 - hundido, z + 0.024)
        self.linea.position = (x, Y_MESA + 0.03, z + 0.026)
        self.centro = (x, Y_MESA + 0.004, z)
        return self.centro

    def clic(self):
        self._t_clic = 0.0

    def pulsar_tecla(self, k):
        pos = calc.tecla_en_teclado(k)
        if pos is None:
            return False
        ancho = calc.ANCHO_TECLA * (3.0 if k in ("space",) else 1.6 if k in ("enter", "return", "backspace", "tab") else 1.0)
        self.tecla.scale = (ancho, 0.004, calc.ANCHO_TECLA)
        self.tecla.position = (TECLADO[0] + pos[0], Y_TECLA, TECLADO[1] + pos[1])
        self.tecla.enabled = True
        self._t_tecla = 0.0
        return True

    def hundido_clic(self):
        """Lo que baja la mano por el clic (m), además del gesto de poses_3d."""
        if self._t_clic is None:
            return 0.0
        return calc.HUNDIDO_MANO_CLIC * calc.curva_pulso(self._t_clic, calc.DURACION_CLIC_RATON)

    def avanzar(self, dt):
        if self._t_clic is not None:
            self._t_clic += dt
            if self._t_clic >= calc.DURACION_CLIC_RATON:
                self._t_clic = None
        if self._t_tecla is not None:
            self._t_tecla += dt
            k = self._t_tecla / DURACION_TECLA
            self.tecla.y = Y_TECLA - HUNDIDO_TECLA * calc.curva_pulso(self._t_tecla, DURACION_TECLA)
            if k >= 1.0:
                self._t_tecla = None
                self.tecla.enabled = False
