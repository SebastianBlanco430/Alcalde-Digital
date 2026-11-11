# Azar determinista del frontend (sin ursina): el mismo (a, b) da siempre el mismo número, así los
# detalles de la favela (tanques, antenas, ropa) no cambian entre ejecuciones ni tocan el
# random.Random del backend (que alteraría la disposición de las casas).

import math


# Número en [0, 1) que depende solo de (a, b): decide detalles siempre igual. Cada detalle usa
# argumentos distintos para que no coincidan entre sí.
def azar_de(a, b):
    return (math.sin(a * 12.9898 + b * 78.233) * 43758.5453) % 1.0


# Ruido de valor suave en [0, 1) que depende solo de (x, z): interpola con azar_de los números de
# las esquinas de una malla de `escala` m. Sirve para variar el color del suelo en manchas amplias
# sin saltos bruscos entre vértices vecinos (y siempre igual en cada ejecución).
def ruido_suave(x, z, escala=1.0):
    gx, gz = x / escala, z / escala
    ix, iz = math.floor(gx), math.floor(gz)
    fx, fz = gx - ix, gz - iz
    fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)       # suaviza la curva entre esquinas
    a, b = azar_de(ix + 0.37, iz + 0.71), azar_de(ix + 1.37, iz + 0.71)
    c, d = azar_de(ix + 0.37, iz + 1.71), azar_de(ix + 1.37, iz + 1.71)
    return (a + (b - a) * fx) * (1 - fz) + (c + (d - c) * fx) * fz
