# Azar determinista del frontend (sin ursina): el mismo (a, b) da siempre el mismo número, así los
# detalles de la favela (tanques, antenas, ropa) no cambian entre ejecuciones ni tocan el
# random.Random del backend (que alteraría la disposición de las casas).

import math


# Número en [0, 1) que depende solo de (a, b): decide detalles siempre igual. Cada detalle usa
# argumentos distintos para que no coincidan entre sí.
def azar_de(a, b):
    return (math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1.0
