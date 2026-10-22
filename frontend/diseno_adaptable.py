# Gestor del diseño adaptable de la interfaz (Ursina): reancla y reescala la UI cuando cambia el
# tamaño o la proporción de la ventana (pantalla completa con F11 o con el botón verde de macOS,
# arrastrar el borde, 4:3, ultra ancho...). La matemática vive en
# frontend/diseno_adaptable_calculos.py (pura, con tests); aquí solo se aplica a entidades.
#
# Causa raíz que corrige (ver nota de la bóveda «23 Ronda 3»):
#   1. El HUD calculaba sus anclajes a los bordes UNA vez con `window.aspect_ratio` al crearse
#      (minimapa, teléfono y panel de turno) y nadie los reubicaba: en 16:10 / 4:3 quedaban
#      fuera de la pantalla y en ultra ancho flotaban hacia dentro.
#   2. Las pantallas diseñadas a 16:9 (Civitas, resultado de la misión, marco de monitor) no se
#      reducían en ventanas más estrechas: se recortaban por los lados. Ursina solo reubica en x
#      los hijos directos de camera.ui, y no escala nada.
#   3. Los anchos de texto eran fijos (envoltura por medida, pero con anchos pensados para 16:9).
#
# Uso (todas las funciones de módulo son NO-OP si el gestor no está instalado o `UI_ADAPTABLE`
# es False, así los tests y los scripts sin app siguen igual que siempre):
#   anclar(entidad, "izquierda" | "derecha")   mueve la entidad en x al cambiar el aspecto.
#   ajustar_escala(entidad, escala_base=1)     escala = escala_base * factor «caber» (<= 1).
#   suscribir(callback)                        callback(aspecto, factor) ya y en cada cambio.
#   ajustar_texto(texto, ancho_max, ...)       encoge / parte un Text para que quepa en ancho_max.
# El gestor sondea el tamaño de la ventana cada frame (macOS no siempre emite 'aspectRatioChanged').
#
# Reversible: poner UI_ADAPTABLE = False (o no llamar a `instalar()`) deja la UI como estaba.

from panda3d.core import TextNode
from ursina import Entity, window

from frontend import diseno_adaptable_calculos as calc

UI_ADAPTABLE = True          # bandera reversible: False = sin gestor, todo como antes

_gestor = None


# Aspecto actual de la ventana (ancho/alto en píxeles); 16:9 si aún no hay ventana.
def aspecto_ventana():
    try:
        return calc.aspecto_de(window.size[0], window.size[1])
    except Exception:  # pragma: no cover - ventana aún sin abrir
        return calc.ASPECTO_DISENO


class GestorDisenoAdaptable(Entity):

    def __init__(self, **opciones):
        super().__init__(eternal=True, **opciones)
        self._aspecto = None
        self._anclas = []         # [entidad, lado, x_base, aspecto_base]
        self._escalas = []        # [entidad, escala_base (número o callable)]
        self._suscritos = []      # callbacks (aspecto, factor)
        self.aplicaciones = 0     # cuántas veces se reaplicó (los tests lo miran)

    # -- Estado --

    @property
    def aspecto(self):
        return self._aspecto if self._aspecto is not None else aspecto_ventana()

    @property
    def factor(self):
        return calc.factor_ajuste(self.aspecto)

    # -- Registro --

    # Ancla `entidad` a un borde (izquierda/derecha/centro). `aspecto_base` = el aspecto con el que
    # se calculó su `x` actual (por defecto el de la ventana ahora, que es con el que se construyó).
    def anclar(self, entidad, lado, aspecto_base=None):
        base = aspecto_ventana() if aspecto_base is None else aspecto_base
        registro = [entidad, lado, entidad.x, base]
        self._anclas.append(registro)
        self._aplicar_ancla(registro, self.aspecto)

    # `escala_base` puede ser un número o un callable sin argumentos (la escala «propia» de la entidad).
    def ajustar_escala(self, entidad, escala_base=1.0):
        registro = [entidad, escala_base]
        self._escalas.append(registro)
        self._aplicar_escala(registro, self.factor)

    # Llama `callback(aspecto, factor)` ahora y cada vez que cambie la proporción de la ventana.
    def suscribir(self, callback):
        self._suscritos.append(callback)
        callback(self.aspecto, self.factor)

    # Quita lo registrado de una entidad (para reutilizar un objeto o en pruebas).
    def olvidar(self, entidad):
        self._anclas = [r for r in self._anclas if r[0] is not entidad]
        self._escalas = [r for r in self._escalas if r[0] is not entidad]

    # -- Aplicación --

    def _viva(self, entidad):
        try:
            return not entidad.isEmpty()
        except Exception:
            return False

    def _aplicar_ancla(self, registro, aspecto):
        entidad, lado, x_base, base = registro
        if self._viva(entidad):
            entidad.x = x_base + calc.desplazamiento_borde(lado, aspecto, base)

    def _aplicar_escala(self, registro, factor):
        entidad, base = registro
        if self._viva(entidad):
            propia = base() if callable(base) else base
            entidad.scale = propia * factor

    # Reaplica TODO con el aspecto de la ventana (o `aspecto` si se da: pruebas). Devuelve el aspecto.
    def reaplicar(self, aspecto=None):
        if aspecto is None:
            aspecto = aspecto_ventana()
        self._aspecto = aspecto
        factor = calc.factor_ajuste(aspecto)
        self._anclas = [r for r in self._anclas if self._viva(r[0])]
        self._escalas = [r for r in self._escalas if self._viva(r[0])]
        for registro in self._anclas:
            self._aplicar_ancla(registro, aspecto)
        for registro in self._escalas:
            self._aplicar_escala(registro, factor)
        for callback in list(self._suscritos):
            callback(aspecto, factor)
        self.aplicaciones += 1
        return aspecto

    # Cada frame: si cambió el tamaño de la ventana, se reaplica.
    def update(self):
        actual = aspecto_ventana()
        if calc.aspecto_cambio(self._aspecto, actual):
            self.reaplicar(actual)


# Crea el gestor (una sola vez) si UI_ADAPTABLE; devuelve None si está desactivado. Llamar tras
# crear la aplicación de Ursina.
def instalar():
    global _gestor
    if not UI_ADAPTABLE:
        return None
    if _gestor is None or not _vivo(_gestor):
        _gestor = GestorDisenoAdaptable()
        _gestor.reaplicar()
    return _gestor


def _vivo(gestor):
    try:
        return not gestor.isEmpty()
    except Exception:
        return False


# Gestor instalado o None (UI_ADAPTABLE apagada, o aún no se llamó a instalar()).
def obtener():
    if not UI_ADAPTABLE:
        return None
    return _gestor if _gestor is not None and _vivo(_gestor) else None


# Desinstala el gestor (pruebas y reversión en caliente).
def desinstalar():
    global _gestor
    if _gestor is not None and _vivo(_gestor):
        _gestor.disable()
        from ursina import destroy
        destroy(_gestor)
    _gestor = None


# -- Atajos de módulo: no hacen nada sin gestor --

def anclar(entidad, lado, aspecto_base=None):
    gestor = obtener()
    if gestor is not None:
        gestor.anclar(entidad, lado, aspecto_base)


def ajustar_escala(entidad, escala_base=1.0):
    gestor = obtener()
    if gestor is not None:
        gestor.ajustar_escala(entidad, escala_base)


def suscribir(callback):
    gestor = obtener()
    if gestor is not None:
        gestor.suscribir(callback)


# Aspecto y factor actuales (16:9 y 1.0 sin gestor): para quien calcula anchos al construir.
def aspecto():
    gestor = obtener()
    return gestor.aspecto if gestor is not None else calc.ASPECTO_DISENO


def factor():
    gestor = obtener()
    return gestor.factor if gestor is not None else 1.0


# Función cadena -> ancho (unidades de camera.ui) de un Text ya creado, a su escala ACTUAL.
def medidor(texto):
    nodo = TextNode("medida_adaptable")
    nodo.setFont(texto.font)
    factor_texto = texto.size * texto.scale_x
    return lambda cadena: nodo.calcWidth(cadena) * factor_texto


# Hace que el contenido de `texto` (un ursina.Text de una sola línea o ya con '\n') quepa en
# `ancho_max` (unidades de camera.ui): lo encoge hasta `escala_min` de `escala_base` (la escala
# con la que se creó), si no basta lo parte en líneas y solo con `max_lineas` lo recorta con
# elipsis. Devuelve el plan (dict de calc.plan_texto_en_ancho). `cadena` = texto a poner (por
# defecto el que ya tiene). No hace nada si UI_ADAPTABLE es False (devuelve None).
def ajustar_texto(texto, ancho_max, escala_base=None, escala_min=0.7, max_lineas=None, cadena=None):
    if not UI_ADAPTABLE:
        return None
    if escala_base is None:
        escala_base = texto.scale_x
    texto.scale = escala_base
    contenido = texto.text if cadena is None else cadena
    # Lo ya partido por el autor ('\n') se respeta: se ajusta línea a línea con el plan del más ancho.
    medir = medidor(texto)
    lineas_originales = [linea for linea in str(contenido).split("\n")]
    if len(lineas_originales) > 1:
        mas_ancha = max(lineas_originales, key=medir)
        plan = calc.plan_texto_en_ancho(mas_ancha, medir, ancho_max, escala_min, None)
        texto.scale = escala_base * plan["escala"]
        return plan
    plan = calc.plan_texto_en_ancho(contenido, medir, ancho_max, escala_min, max_lineas)
    texto.scale = escala_base * plan["escala"]
    if cadena is not None or len(plan["lineas"]) > 1 or plan["recortado"]:
        texto.text = "\n".join(plan["lineas"])
    return plan
