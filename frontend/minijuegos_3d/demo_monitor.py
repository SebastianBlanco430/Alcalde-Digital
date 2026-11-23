# DEMOSTRACIÓN de la infraestructura 3D (bandera ALCALDE_3D_DEMO, apagada por defecto): el minijuego de hoy, SIN rediseñar,
# dibujado en el monitor de la oficina del lugar, con el protagonista sentado imitando el mouse y el teclado. Prueba que la
# textura de la interfaz, el mouse sobre el monitor (hover y clic) y el respaldo funcionan antes de la Fase 2.
# No ocupa los nombres de archivo de las familias (pc_*, chat_3d, ...).

from frontend.minijuegos_3d.base import Minijuego3D


class DemoMonitor(Minijuego3D):

    FAMILIA = "pc"


CLASE_3D = DemoMonitor
