# Lógica pura (sin ursina) de la pantalla de Ajustes: registro de secciones ampliable, lista de dispositivos de
# audio, formato de valores, posición del deslizador y navegación de foco por filas/columnas.
# La pantalla (frontend/escenas/escena_ajustes.py) solo dibuja y conecta; todo lo que se puede probar sin
# ventana vive aquí.

MAX_DISPOSITIVOS = 40
LARGO_MAX_DISPOSITIVO = 120
ETIQUETA_PREDETERMINADO = "Predeterminado del sistema"
ETIQUETA_NO_CONECTADO = " (no conectado)"
PASO_DESLIZADOR = 0.05            # lo que mueven las flechas izquierda/derecha


# Registro ordenado de secciones: (nombre, constructor). Registrar un nombre que ya existe lo REEMPLAZA
# (así el agente de audio/online sustituye el marcador de posición sin editar el archivo de la pantalla).
# `version` sube con cada cambio para que la pantalla sepa que debe reconstruir sus pestañas.
class RegistroSecciones:

    def __init__(self):
        self._items = []
        self.version = 0

    def registrar(self, nombre, constructor):
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError("el nombre de la sección debe ser un texto no vacío")
        if not callable(constructor):
            raise TypeError("el constructor de la sección debe ser invocable")
        nombre = nombre.strip()[:30]
        for i, (existente, _) in enumerate(self._items):
            if existente == nombre:
                self._items[i] = (nombre, constructor)
                break
        else:
            self._items.append((nombre, constructor))
        self.version += 1

    def quitar(self, nombre):
        antes = len(self._items)
        self._items = [(n, c) for n, c in self._items if n != nombre]
        if len(self._items) != antes:
            self.version += 1

    def nombres(self):
        return [n for n, _ in self._items]

    def constructor(self, nombre):
        for n, c in self._items:
            if n == nombre:
                return c
        return None

    def items(self):
        return list(self._items)


# Lista de dispositivos de salida sanea: solo textos imprimibles no vacíos, sin duplicados, acotada.
def sanear_dispositivos(lista):
    limpia = []
    if not isinstance(lista, (list, tuple)):
        return limpia
    for nombre in lista:
        if not isinstance(nombre, str):
            continue
        texto = "".join(c for c in nombre if c.isprintable()).strip()[:LARGO_MAX_DISPOSITIVO]
        if texto and texto not in limpia:
            limpia.append(texto)
        if len(limpia) >= MAX_DISPOSITIVOS:
            break
    return limpia


# Opciones del selector de dispositivo: [(etiqueta, valor)] con valor None = predeterminado. Si el guardado ya
# no está en la lista se añade como «(no conectado)» para no perder el ajuste sin avisar.
def opciones_dispositivo(dispositivos, guardado=None):
    opciones = [(ETIQUETA_PREDETERMINADO, None)]
    opciones += [(nombre, nombre) for nombre in dispositivos]
    if guardado and guardado not in dispositivos:
        opciones.append((guardado + ETIQUETA_NO_CONECTADO, guardado))
    return opciones


# Índice de `valor` en una lista de opciones [(etiqueta, valor)]; 0 si no está.
def indice_de_valor(opciones, valor):
    for i, (_, v) in enumerate(opciones):
        if v == valor:
            return i
    return 0


# Siguiente índice cíclico.
def ciclar(indice, paso, total):
    return (indice + paso) % total if total > 0 else 0


# Porcentaje entero para mostrar: 0.756 -> «76 %».
def formato_porcentaje(valor):
    return f"{int(round(max(0.0, min(1.0, valor)) * 100))} %"


# Valor 0..1 que corresponde a una posición local x en una pista centrada de ancho 1 (x en [-0.5, 0.5]).
def valor_desde_posicion(x_local):
    return max(0.0, min(1.0, x_local + 0.5))


# Mueve el valor un paso (con redondeo para que no se acumule error de coma flotante).
def mover_valor(valor, paso=PASO_DESLIZADOR, direccion=1):
    return round(max(0.0, min(1.0, valor + paso * direccion)), 4)


# Navegación de foco en una rejilla irregular: `tamanos` = cantidad de controles de cada fila.
# Devuelve (fila, columna) tras moverse arriba/abajo (cíclico, conserva la columna recortada) o
# izquierda/derecha (dentro de la fila, sin dar la vuelta).
def mover_foco(tamanos, fila, columna, direccion):
    filas = [i for i, n in enumerate(tamanos) if n > 0]
    if not filas:
        return 0, 0
    if fila not in filas:
        fila = filas[0]
    if direccion in ("arriba", "abajo"):
        pos = filas.index(fila)
        pos = (pos + (1 if direccion == "abajo" else -1)) % len(filas)
        nueva = filas[pos]
        return nueva, min(columna, tamanos[nueva] - 1)
    paso = 1 if direccion == "derecha" else -1
    return fila, max(0, min(tamanos[fila] - 1, columna + paso))


# Orden lineal Tab / Shift+Tab sobre la misma rejilla (cíclico).
def mover_foco_lineal(tamanos, fila, columna, paso):
    lineal = [(f, c) for f, n in enumerate(tamanos) for c in range(n)]
    if not lineal:
        return 0, 0
    actual = (fila, columna)
    pos = lineal.index(actual) if actual in lineal else 0
    return lineal[(pos + paso) % len(lineal)]
