# Cálculos puros del suavizado de bordes (MSAA). Sin Ursina ni Panda: se prueban con pytest.
# El cableado con la ventana y los búferes de pantalla vive en frontend/suavizado.py.
#
# De dónde sale el número de muestras:
#   ALCALDE_MSAA=0      -> 0 (apagado del todo: ni prc ni setAntialias, exactamente como antes)
#   ALCALDE_MSAA=2 / 4  -> fuerza ese valor (para medir), ignorando el ajuste
#   sin la variable     -> el ajuste del jugador «Suavizado» (backend/logica/ajustes.py: suavizado)
# Un valor de la variable que no sea entero se ignora (se usa el ajuste); uno entero se lleva al escalón válido más cercano.

MUESTRAS_VALIDAS = (0, 2, 4)


def _escalon(valor):
    return min(MUESTRAS_VALIDAS, key=lambda m: abs(m - valor))


# Muestras pedidas a partir del valor crudo de ALCALDE_MSAA (str o None) y del ajuste guardado.
def muestras_pedidas(variable, ajuste):
    if variable is not None and str(variable).strip() != "":
        try:
            return _escalon(int(str(variable).strip()))
        except ValueError:
            pass
    if isinstance(ajuste, bool) or not isinstance(ajuste, int):
        return 0
    return _escalon(ajuste)


# Líneas de configuración de Panda (loadPrcFileData) que piden una ventana con MSAA; [] = no tocar nada.
def lineas_prc(muestras):
    if muestras <= 0:
        return []
    return ["framebuffer-multisample 1", f"multisamples {int(muestras)}"]


# ¿La ventana obtuvo lo pedido? `obtenidas` = getFbProperties().getMultisamples() (0 o 1 = sin MSAA).
def ventana_tiene_msaa(obtenidas):
    return isinstance(obtenidas, int) and obtenidas > 1


# VIS-009: muestras con las que se dibuja el MUNDO: las del búfer del pase final si lo hay (FBO: lo pedido exacto, o 0
# con el pixelado), si no las de la ventana. 0 o 1 = sin MSAA.
def muestras_del_mundo(ventana, filtro):
    valor = ventana if filtro is None else filtro
    return int(valor) if isinstance(valor, int) and valor > 1 else 0


# Opciones del selector de Ajustes (etiqueta, valor).
def opciones():
    return [("No", 0), ("2×", 2), ("4×", 4)]
