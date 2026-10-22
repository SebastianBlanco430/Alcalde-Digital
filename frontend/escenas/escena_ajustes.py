# Pantalla de AJUSTES (Ursina): accesibilidad (filtro de daltonismo con vista previa en vivo), audio (volúmenes,
# silenciar, dispositivo de salida) y un espacio para Online. Se usa de dos maneras con la misma pieza:
#   - EscenaAjustes: escena completa (desde el menú de inicio) con el fondo de los menús.
#   - PantallaAjustes dentro del menú de pausa (superposición); ver frontend/menu_pausa.py.
# Los cambios se aplican EN VIVO (el filtro de daltonismo se ve al instante en toda la pantalla, también en esta);
# «Guardar» los persiste en el JSON del usuario, «Atrás» (o Escape) los descarta y «Restablecer» vuelve a los
# valores por defecto (sin guardar hasta pulsar «Guardar»).
#
# Teclado: Arriba/Abajo cambian de fila, Izquierda/Derecha ajustan el control (deslizador/selector) o cambian de
# botón en la fila, Tab/Mayús+Tab recorren todo, Intro/Espacio activan, Escape = Atrás. El ratón y el teclado
# conviven: al pasar el ratón por un control, el foco se va con él. Se adapta a la ventana con diseno_adaptable.
#
# EXTENSIÓN (sin editar este archivo):
#   registrar_seccion(nombre, constructor)  añade (o reemplaza si el nombre existe) una pestaña. `constructor(seccion)`
#       recibe una `Seccion` vacía y la rellena con sus métodos: anadir_texto, anadir_deslizador, anadir_selector,
#       anadir_interruptor, anadir_boton, anadir_muestras. `seccion.gestor` es el GestorAjustes (backend.logica.ajustes).
#       El constructor puede devolver una función `al_mostrar()` que se llama cada vez que se abre la pestaña.
#   registrar_dispositivos(lista)           el módulo de audio entrega aquí los nombres de las salidas disponibles.
#   registrar_prueba_sonido(callback)       (opcional) muestra un botón «Probar sonido» en Audio.
#
# Bandera reversible: AJUSTES (backend.logica.ajustes) = False oculta los botones «Ajustes» de los menús.

from ursina import Entity, Text, Vec3, camera, color, mouse

from backend.logica import ajustes as modelo_ajustes
from frontend import ajustes_calculos as calc
from frontend import daltonismo_calculos as dalt
from frontend import diseno_adaptable, estilo, tipografia
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FondoMenu, anadir_filo

AJUSTES_ESCENA = "ajustes"            # nombre con que main.py registra la escena en el gestor

ANCHO_PANEL, ALTO_PANEL = 1.36, 0.90
X_ETIQUETA = -0.62                    # inicio del texto de cada fila
X_CONTROL = 0.30                      # centro de la zona del control
ANCHO_CONTROL = 0.64
ALTO_FILA = 0.09
Y_CONTENIDO = 0.215                   # borde superior del área de contenido
Z_TEXTO = -0.004


# --- Registro público (ver arriba) ---

_registro = calc.RegistroSecciones()
_dispositivos = []                    # nombres de salidas de audio entregados por el módulo de audio
_prueba_sonido = None
_pantallas_vivas = []                 # PantallaAjustes abiertas, para refrescar al llegar dispositivos


def registrar_seccion(nombre, constructor):
    _registro.registrar(nombre, constructor)


def registrar_dispositivos(lista):
    global _dispositivos
    _dispositivos = calc.sanear_dispositivos(lista)
    for pantalla in list(_pantallas_vivas):
        try:
            pantalla.refrescar_dispositivos()
        except Exception as error:     # pragma: no cover - pantalla ya destruida
            print(f"[ajustes] refrescar dispositivos: {error}")


def dispositivos_registrados():
    return list(_dispositivos)


def registrar_prueba_sonido(callback):
    global _prueba_sonido
    _prueba_sonido = callback


# --- Controles ---

def _texto(padre, contenido, x, y, px, tono=estilo.COLOR_TEXTO, origen=(-0.5, 0), titulo=False):
    opciones = {"font": tipografia.FUENTE_TITULO} if titulo else {}
    return Text(contenido, parent=padre, origin=origen, position=(x, y, Z_TEXTO), scale=escala_fuente(px),
                color=rgb(tono), **opciones)


# ¿El ratón está encima del control? (los botones usan `hovered`; los demás, su zona sensible)
def _bajo_el_raton(control):
    consulta = getattr(control, "bajo_el_raton", None)
    return consulta() if callable(consulta) else bool(getattr(control, "hovered", False))


# Fila de una sección: etiqueta a la izquierda y resaltado de foco detrás.
class Fila(Entity):

    def __init__(self, etiqueta, y, alto=ALTO_FILA, **opciones):
        super().__init__(position=(0, y, 0), **opciones)
        self.alto = alto
        self.resalte = Entity(parent=self, model="quad", color=rgb(estilo.COLOR_SUPERFICIE_ALTA),
                              scale=(ANCHO_PANEL - 0.12, alto - 0.012), z=0.002, enabled=False)
        self.barra = Entity(parent=self.resalte, model="quad", color=rgb(estilo.ACENTO_SECUNDARIO),
                            scale=(0.006 / (ANCHO_PANEL - 0.12), 1), x=-0.5, z=-0.01)
        self.etiqueta = _texto(self, etiqueta, X_ETIQUETA, 0, 22) if etiqueta else None

    def fijar_foco(self, valor):
        self.resalte.enabled = bool(valor)


# Deslizador 0..1 (ratón: clic y arrastre; teclado: izquierda/derecha).
class Deslizador(Entity):

    ANCHO_PISTA = 0.46
    ALTO_PISTA = 0.026

    def __init__(self, fila, valor, al_cambiar, formato=calc.formato_porcentaje, **opciones):
        super().__init__(parent=fila, **opciones)
        self.fila = fila
        self._al_cambiar = al_cambiar
        self._formato = formato
        self.valor = 0.0
        self._arrastrando = False
        self._habilitado = True
        x0 = X_CONTROL - ANCHO_CONTROL / 2 + 0.02
        self.x_centro = x0 + self.ANCHO_PISTA / 2
        self.pista = panel_tinta(self, self.ANCHO_PISTA, self.ALTO_PISTA, (96, 102, 138), 6,
                                 sombra=False, borde_px=2, position=(self.x_centro, 0, -0.003))
        self.relleno = Entity(parent=self, model="quad", color=rgb(estilo.ACENTO_SECUNDARIO), z=-0.006,
                              scale=(0.001, self.ALTO_PISTA * 0.8), position=(x0, 0, -0.006))
        self.nudo = panel_tinta(self, 0.034, 0.062, estilo.ACENTO_PRIMARIO, 6, sombra=False, borde_px=2,
                                position=(x0, 0, -0.009))
        self.zona = Entity(parent=self, model="quad", collider="box", color=color.clear,
                           scale=(self.ANCHO_PISTA + 0.05, 0.085), position=(self.x_centro, 0, -0.012))
        self.texto_valor = _texto(self, "0 %", x0 + self.ANCHO_PISTA + 0.04, 0, 22)
        self._x0 = x0
        self.fijar_valor(valor)

    def bajo_el_raton(self):
        return bool(self.zona.hovered) or self._arrastrando

    def esta_habilitado(self):
        return self._habilitado

    def fijar_foco(self, valor):
        self.fila.fijar_foco(valor)

    def manejar_clic(self):
        pass

    def ajustar(self, direccion):
        self.fijar_valor(calc.mover_valor(self.valor, calc.PASO_DESLIZADOR, direccion), avisar=True)

    def fijar_valor(self, valor, avisar=False):
        valor = max(0.0, min(1.0, float(valor)))
        self.valor = valor
        ancho = self.ANCHO_PISTA * valor
        self.relleno.scale_x = max(ancho, 0.0001)
        self.relleno.x = self._x0 + ancho / 2
        self.nudo.x = self._x0 + ancho
        self.texto_valor.text = self._formato(valor)
        if avisar and self._al_cambiar is not None:
            self._al_cambiar(valor)

    def _valor_del_raton(self):
        local = self.pista.getRelativePoint(camera.ui, Vec3(mouse.x, mouse.y, 0))
        return calc.valor_desde_posicion(local.x / self.ANCHO_PISTA)

    def input(self, key):
        if key == "left mouse down" and self.zona.hovered:
            self._arrastrando = True
            self.fijar_valor(self._valor_del_raton(), avisar=True)
        elif key == "left mouse up":
            self._arrastrando = False

    def update(self):
        if self._arrastrando:
            self.fijar_valor(self._valor_del_raton(), avisar=True)


# Selector cíclico con flechas: opciones = [(etiqueta, valor)].
class Selector(Entity):

    def __init__(self, fila, opciones, indice, al_cambiar, **kw):
        super().__init__(parent=fila, **kw)
        self.fila = fila
        self._al_cambiar = al_cambiar
        self._habilitado = True
        self.opciones = list(opciones) or [("—", None)]
        self.indice = 0
        ancho_flecha = 0.075
        ancho_centro = ANCHO_CONTROL - 2 * ancho_flecha - 0.03
        x_izq = X_CONTROL - ANCHO_CONTROL / 2 + ancho_flecha / 2
        x_der = X_CONTROL + ANCHO_CONTROL / 2 - ancho_flecha / 2
        self.flecha_izq = BotonSecundario("‹", al_clic=lambda: self.ajustar(-1), ancho=ancho_flecha,
                                          alto=a_unidades(46), tamano_fuente_px=26, parent=self,
                                          position=(x_izq, 0, -0.003))
        self.flecha_der = BotonSecundario("›", al_clic=lambda: self.ajustar(1), ancho=ancho_flecha,
                                          alto=a_unidades(46), tamano_fuente_px=26, parent=self,
                                          position=(x_der, 0, -0.003))
        self.centro = panel_tinta(self, ancho_centro, a_unidades(46), estilo.COLOR_TARJETA, 6, sombra=False,
                                  borde_px=2, position=(X_CONTROL, 0, -0.002))
        self.ancho_centro = ancho_centro
        self.texto = Text("-", parent=self.centro, origin=(0, 0), position=(0, 0, -0.001),
                          scale=escala_fuente(21), color=rgb(estilo.COLOR_TEXTO))
        self.zona = Entity(parent=self, model="quad", collider="box", color=color.clear,
                           scale=(ancho_centro, a_unidades(46)), position=(X_CONTROL, 0, -0.006))
        self.fijar_opciones(self.opciones, indice)

    def bajo_el_raton(self):
        return bool(self.zona.hovered or self.flecha_izq.hovered or self.flecha_der.hovered)

    def esta_habilitado(self):
        return self._habilitado

    def fijar_foco(self, valor):
        self.fila.fijar_foco(valor)

    def manejar_clic(self):
        self.ajustar(1)

    def valor(self):
        return self.opciones[self.indice][1]

    def etiqueta_actual(self):
        return self.opciones[self.indice][0]

    def fijar_opciones(self, opciones, indice=0):
        self.opciones = list(opciones) or [("—", None)]
        self.fijar_indice(indice)

    def fijar_indice(self, indice, avisar=False):
        self.indice = max(0, min(len(self.opciones) - 1, indice))
        etiqueta = self.opciones[self.indice][0]
        self.texto.text = etiqueta
        self.texto.scale = escala_fuente(21)
        # el texto largo se encoge para caber (nunca se sale del recuadro)
        diseno_adaptable.ajustar_texto(self.texto, self.ancho_centro - 0.03, escala_base=escala_fuente(21),
                                       escala_min=0.6)
        if avisar and self._al_cambiar is not None:
            self._al_cambiar(self.opciones[self.indice][1])

    def ajustar(self, direccion):
        self.fijar_indice(calc.ciclar(self.indice, direccion, len(self.opciones)), avisar=True)

    def update(self):
        # sin esperar al ratón del foco: nada que hacer por frame (las flechas son botones)
        pass


# Interruptor Sí/No como botón (un clic o Intro lo alterna).
class Interruptor(BotonSecundario):

    def __init__(self, fila, valor, al_cambiar, **opciones):
        self._valor = bool(valor)
        self._al_cambiar = al_cambiar
        self.fila = fila
        super().__init__(self._texto_de(self._valor), al_clic=self._alternar, ancho=0.30,
                         alto=a_unidades(46), tamano_fuente_px=21, parent=fila,
                         position=(X_CONTROL - ANCHO_CONTROL / 2 + 0.15, 0, -0.003), **opciones)

    @staticmethod
    def _texto_de(valor):
        return "Activado" if valor else "Desactivado"

    def valor(self):
        return self._valor

    def fijar_valor(self, valor):
        self._valor = bool(valor)
        self.text = self._texto_de(self._valor)

    def _alternar(self):
        self.fijar_valor(not self._valor)
        if self._al_cambiar is not None:
            self._al_cambiar(self._valor)

    def fijar_foco(self, valor):
        super().fijar_foco(valor)
        self.fila.fijar_foco(valor)

    def ajustar(self, direccion):
        self._alternar()


# Una sección (pestaña): contenedor con diseño vertical automático y las filas de controles para el foco.
class Seccion(Entity):

    def __init__(self, nombre, gestor, pantalla=None, **opciones):
        super().__init__(**opciones)
        self.nombre = nombre
        self.gestor = gestor
        self.pantalla = pantalla
        self.filas_foco = []          # cada elemento: lista de controles de una fila
        self._y = Y_CONTENIDO
        self._al_mostrar = []         # callbacks sin argumentos al abrir la pestaña
        self.controles = {}           # clave -> control (para refrescar valores desde el gestor)

    def _nueva_fila(self, etiqueta, alto=ALTO_FILA):
        fila = Fila(etiqueta, self._y - alto / 2, alto=alto, parent=self)
        self._y -= alto
        return fila

    def en_mostrar(self, callback):
        self._al_mostrar.append(callback)

    def mostrado(self):
        for callback in self._al_mostrar:
            callback()

    def anadir_texto(self, contenido, tenue=True, px=19, alto=0.075):
        fila = self._nueva_fila(None, alto)
        texto = _texto(fila, contenido, X_ETIQUETA, 0, px,
                       estilo.COLOR_TEXTO_TENUE if tenue else estilo.COLOR_TEXTO)
        diseno_adaptable.ajustar_texto(texto, ANCHO_PANEL - 0.2, escala_base=escala_fuente(px), escala_min=0.7,
                                       max_lineas=2)
        return texto

    # Deslizador ligado a `clave` de los ajustes (0..1). Devuelve el control.
    def anadir_deslizador(self, etiqueta, clave, formato=calc.formato_porcentaje):
        fila = self._nueva_fila(etiqueta)
        control = Deslizador(fila, getattr(self.gestor.actual, clave),
                             lambda v: self.gestor.cambiar(**{clave: v}), formato)
        self.controles[clave] = control
        self.filas_foco.append([control])
        return control

    # Selector con opciones [(etiqueta, valor)] ligado a `clave`.
    def anadir_selector(self, etiqueta, clave, opciones):
        fila = self._nueva_fila(etiqueta)
        actual = getattr(self.gestor.actual, clave)
        control = Selector(fila, opciones, calc.indice_de_valor(opciones, actual),
                           lambda v: self.gestor.cambiar(**{clave: v}))
        self.controles[clave] = control
        self.filas_foco.append([control])
        return control

    # Interruptor ligado a `clave` (booleano).
    def anadir_interruptor(self, etiqueta, clave):
        fila = self._nueva_fila(etiqueta)
        control = Interruptor(fila, getattr(self.gestor.actual, clave),
                              lambda v: self.gestor.cambiar(**{clave: v}))
        self.controles[clave] = control
        self.filas_foco.append([control])
        return control

    # Botón suelto en su propia fila (acción propia de la sección).
    def anadir_boton(self, etiqueta, texto, accion):
        fila = self._nueva_fila(etiqueta)
        boton = BotonSecundario(texto, al_clic=accion, ancho=0.34, alto=a_unidades(46), tamano_fuente_px=21,
                                parent=fila, position=(X_CONTROL - ANCHO_CONTROL / 2 + 0.17, 0, -0.003))
        original = boton.fijar_foco

        def con_fila(valor, original=original, fila=fila):
            original(valor)
            fila.fijar_foco(valor)
        boton.fijar_foco = con_fila
        self.filas_foco.append([boton])
        return boton

    # Fila de muestras de color con su nombre (los colores del propio juego), para ver cómo cambia cada uno
    # con el filtro activo: el filtro afecta a toda la pantalla, también a estas muestras.
    def anadir_muestras(self, muestras, alto=0.15):
        fila = self._nueva_fila(None, alto)
        n = len(muestras)
        ancho_total = ANCHO_PANEL - 0.24
        paso = ancho_total / n
        lado = min(paso - 0.03, 0.115)
        for i, (nombre, rgb_muestra) in enumerate(muestras):
            x = -ancho_total / 2 + paso * (i + 0.5)
            panel_tinta(fila, lado, lado * 0.8, rgb_muestra, 6, sombra=False, borde_px=2, position=(x, 0.016, -0.002))
            _texto(fila, nombre, x, -0.058, 17, estilo.COLOR_TEXTO_TENUE, origen=(0, 0))
        return fila


# --- Secciones incluidas ---

def _seccion_accesibilidad(s):
    modos = [(dalt_nombre, m) for m, dalt_nombre in
             ((m, modelo_ajustes.NOMBRES_MODO[m]) for m in modelo_ajustes.MODOS_DALTONISMO)]
    s.anadir_selector("Filtro de color", "modo_daltonismo", modos)
    s.anadir_deslizador("Intensidad", "intensidad")
    s.anadir_interruptor("Simular la visión", "simular_daltonismo")
    s.anadir_muestras(dalt.MUESTRAS)
    s.anadir_texto("El filtro cambia los colores de TODA la pantalla (mundo e interfaz) en vivo. "
                   "Corrige para distinguir mejor rojos, verdes y azules; «Simular» muestra cómo lo ve "
                   "alguien con ese tipo de daltonismo.")


def _seccion_audio(s):
    s.anadir_deslizador("Volumen general", "volumen_maestro")
    s.anadir_deslizador("Música", "volumen_musica")
    s.anadir_deslizador("Efectos", "volumen_efectos")
    s.anadir_interruptor("Silenciar todo", "silenciado")
    control = s.anadir_selector("Salida de audio", "dispositivo_audio", calc.opciones_dispositivo(_dispositivos))
    if _prueba_sonido is not None:
        s.anadir_boton("Comprobar", "Probar sonido", _prueba_sonido)
    aviso = s.anadir_texto("La lista de salidas aparece cuando el motor de audio está disponible.")

    # Rellena el selector con la lista que dio el módulo de audio (y conserva el dispositivo guardado).
    def actualizar_dispositivos():
        opciones = calc.opciones_dispositivo(_dispositivos, s.gestor.actual.dispositivo_audio)
        control.fijar_opciones(opciones, calc.indice_de_valor(opciones, s.gestor.actual.dispositivo_audio))
        aviso.enabled = not _dispositivos
    s.en_mostrar(actualizar_dispositivos)
    s.refrescar_dispositivos = actualizar_dispositivos


def _seccion_online(s):
    s.anadir_texto("El modo en línea (cooperativo, hasta 4 jugadores) se configurará aquí: "
                   "nombre en línea y último anfitrión.", tenue=True, alto=0.09)
    s.anadir_texto("Todavía no está disponible en esta versión.", tenue=True)


registrar_seccion("Accesibilidad", _seccion_accesibilidad)
registrar_seccion("Audio", _seccion_audio)
registrar_seccion("Online", _seccion_online)


# --- Pantalla ---

class PantallaAjustes(Entity):

    def __init__(self, al_cerrar=None, gestor=None, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(**opciones)
        self.gestor = gestor if gestor is not None else modelo_ajustes.obtener()
        self._al_cerrar = al_cerrar
        self.secciones = {}            # nombre -> Seccion
        self.pestanas = []             # botones de pestaña
        self.seccion_actual = None
        self._version_registro = None
        self._foco = (0, 0)
        self._foco_visible = False
        self._hover_previo = None
        self._cerrando = False

        self.raiz = Entity(parent=self)
        diseno_adaptable.ajustar_escala(self.raiz)
        self.panel = panel_tinta(self.raiz, ANCHO_PANEL, ALTO_PANEL, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO_PANEL, ALTO_PANEL, estilo.RADIO_PANEL_PX)
        self.titulo = _texto(self.raiz, "Ajustes", 0, 0.385, 38, estilo.COLOR_TEXTO, origen=(0, 0), titulo=True)
        self.nota = _texto(self.raiz, "Atrás descarta los cambios sin guardar.", -ANCHO_PANEL / 2 + 0.05, -0.322,
                           17, estilo.COLOR_TEXTO_TENUE)

        alto_boton = a_unidades(52)
        self.boton_restablecer = BotonSecundario(
            "Restablecer", al_clic=self.restablecer, ancho=0.34, alto=alto_boton, tamano_fuente_px=22,
            parent=self.raiz, position=(-0.45, -0.385, -0.003))
        self.boton_atras = BotonSecundario(
            "Atrás", al_clic=self.atras, ancho=0.30, alto=alto_boton, tamano_fuente_px=22,
            parent=self.raiz, position=(0.20, -0.385, -0.003))
        self.boton_guardar = BotonPrimario(
            "Guardar", al_clic=self.guardar_y_cerrar, ancho=0.30, alto=alto_boton, tamano_fuente_px=24,
            parent=self.raiz, position=(0.52, -0.385, -0.003))
        self.botones_pie = [self.boton_restablecer, self.boton_atras, self.boton_guardar]
        _pantallas_vivas.append(self)
        self._reconstruir()

    # -- Construcción --

    def _reconstruir(self):
        for pestana in self.pestanas:
            pestana.parent = None
            pestana.enabled = False
        for seccion in self.secciones.values():
            seccion.parent = None
            seccion.enabled = False
        self.pestanas, self.secciones = [], {}
        nombres = _registro.nombres()
        ancho_total = ANCHO_PANEL - 0.2
        ancho_pestana = min(0.34, ancho_total / max(1, len(nombres)) - 0.02)
        x0 = -(ancho_pestana + 0.02) * (len(nombres) - 1) / 2
        for i, nombre in enumerate(nombres):
            boton = BotonSecundario(
                nombre, al_clic=lambda n=nombre: self.mostrar_seccion(n), ancho=ancho_pestana,
                alto=a_unidades(44), tamano_fuente_px=20, parent=self.raiz,
                position=(x0 + i * (ancho_pestana + 0.02), 0.295, -0.003))
            self.pestanas.append(boton)
            seccion = Seccion(nombre, self.gestor, self, parent=self.raiz, enabled=False)
            try:
                resultado = _registro.constructor(nombre)(seccion)
                if callable(resultado):
                    seccion.en_mostrar(resultado)
            except Exception as error:     # una sección rota no debe tumbar la pantalla
                print(f"[ajustes] la sección {nombre!r} falló: {error}")
                seccion.anadir_texto("Esta sección no se pudo cargar.")
            self.secciones[nombre] = seccion
        self._version_registro = _registro.version
        self.seccion_actual = None

    # -- API --

    # Abre la pantalla: sincroniza controles con los ajustes, vuelve a la primera pestaña y quita el foco visible.
    def abrir(self, seccion=None):
        if self._version_registro != _registro.version:
            self._reconstruir()
        self._cerrando = False
        self.enabled = True
        self.mostrar_seccion(seccion if seccion in self.secciones else (_registro.nombres() or [None])[0])
        self._foco = (0, 0)
        self._foco_visible = False
        self._aplicar_foco()

    def mostrar_seccion(self, nombre):
        if nombre not in self.secciones:
            return
        for n, seccion in self.secciones.items():
            seccion.enabled = n == nombre
        self.seccion_actual = self.secciones[nombre]
        self.refrescar_controles()
        self.seccion_actual.mostrado()
        # la pestaña activa se marca con el anillo de foco propio; el foco del teclado vuelve a las pestañas
        self._marcar_pestanas()
        self._aplicar_foco()

    def refrescar_controles(self):
        seccion = self.seccion_actual
        if seccion is None:
            return
        for clave, control in seccion.controles.items():
            valor = getattr(self.gestor.actual, clave, None)
            if isinstance(control, Deslizador):
                control.fijar_valor(valor)
            elif isinstance(control, Interruptor):
                control.fijar_valor(valor)
            elif isinstance(control, Selector):
                control.fijar_indice(calc.indice_de_valor(control.opciones, valor))

    def refrescar_dispositivos(self):
        for seccion in self.secciones.values():
            if hasattr(seccion, "refrescar_dispositivos"):
                seccion.refrescar_dispositivos()

    def _marcar_pestanas(self):
        for boton, nombre in zip(self.pestanas, self.secciones):
            activa = self.secciones[nombre] is self.seccion_actual
            boton.color = rgb(estilo.ACENTO_PRIMARIO if activa else estilo.COLOR_BOTON)
            boton.text_color = rgb(estilo.COLOR_ACENTO_TEXTO if activa else estilo.COLOR_BOTON_TEXTO)

    def restablecer(self):
        self.gestor.restablecer()
        self.refrescar_controles()
        self.nota.text = "Valores por defecto (pulsa Guardar para conservarlos)."

    def guardar_y_cerrar(self):
        ok = self.gestor.guardar()
        self._cerrar(guardado=ok)

    def atras(self):
        self.gestor.descartar()
        self._cerrar(guardado=False)

    def _cerrar(self, guardado):
        if self._cerrando:
            return
        self._cerrando = True
        self.nota.text = "Atrás descarta los cambios sin guardar."
        if self._al_cerrar is not None:
            self._al_cerrar(guardado)

    # Si la pantalla se oculta por fuera (p. ej. se cierra la pausa), lo no guardado se descarta.
    def on_disable(self):
        if getattr(self, "gestor", None) is not None and not self._cerrando and self.gestor.hay_cambios_sin_guardar():
            self.gestor.descartar()
            if self.seccion_actual is not None:
                self.refrescar_controles()

    def on_destroy(self):
        if self in _pantallas_vivas:
            _pantallas_vivas.remove(self)

    # -- Foco --

    def _filas(self):
        filas = [list(self.pestanas)]
        if self.seccion_actual is not None:
            filas += [f for f in self.seccion_actual.filas_foco if any(c.esta_habilitado() for c in f)]
        filas.append(list(self.botones_pie))
        return filas

    def _aplicar_foco(self):
        filas = self._filas()
        fila = max(0, min(self._foco[0], len(filas) - 1))
        columna = max(0, min(self._foco[1], len(filas[fila]) - 1))
        self._foco = (fila, columna)
        actual = filas[fila][columna]
        for lista in filas:
            for control in lista:
                control.fijar_foco(self._foco_visible and control is actual)
        # controles de otras secciones ocultas no necesitan limpieza (su fila está desactivada)

    def _mover(self, direccion):
        filas = self._filas()
        tamanos = [len(f) for f in filas]
        self._foco_visible = True
        self._foco = calc.mover_foco(tamanos, self._foco[0], self._foco[1], direccion)
        self._aplicar_foco()

    def _control_enfocado(self):
        filas = self._filas()
        fila, columna = self._foco
        if 0 <= fila < len(filas) and 0 <= columna < len(filas[fila]):
            return filas[fila][columna]
        return None

    def input(self, key):
        if not self.enabled or self._cerrando:
            return
        if key == "escape":
            self.atras()
        elif key in ("up arrow", "down arrow"):
            self._mover("arriba" if key == "up arrow" else "abajo")
        elif key in ("left arrow", "right arrow"):
            direccion = -1 if key == "left arrow" else 1
            control = self._control_enfocado()
            self._foco_visible = True
            if control is not None and hasattr(control, "ajustar") and self._foco[0] != 0 \
                    and control not in self.botones_pie:
                control.ajustar(direccion)
                self._aplicar_foco()
            else:
                self._mover("izquierda" if direccion < 0 else "derecha")
                if self._foco[0] == 0:                   # en la fila de pestañas, moverse la abre
                    self._abrir_pestana_enfocada()
        elif key in ("tab", "shift tab"):
            filas = self._filas()
            self._foco_visible = True
            self._foco = calc.mover_foco_lineal([len(f) for f in filas], self._foco[0], self._foco[1],
                                                -1 if key == "shift tab" else 1)
            self._aplicar_foco()
        elif key in ("enter", "space"):
            control = self._control_enfocado()
            if control is not None:
                control.manejar_clic()

    def _abrir_pestana_enfocada(self):
        if self._foco[0] == 0 and self._foco[1] < len(self.pestanas):
            nombre = list(self.secciones)[self._foco[1]]
            self.mostrar_seccion(nombre)

    # El ratón gana foco al pasar por un control (y oculta el anillo del teclado).
    def update(self):
        if not self.enabled:
            return
        filas = self._filas()
        golpeado = None
        for f, lista in enumerate(filas):
            for c, control in enumerate(lista):
                if control.esta_habilitado() and _bajo_el_raton(control):
                    golpeado = (f, c)
        if golpeado != self._hover_previo:
            self._hover_previo = golpeado
            if golpeado is not None:
                self._foco = golpeado
                self._foco_visible = False
                self._aplicar_foco()


# Escena completa (menú de inicio -> Ajustes). `al_volver()` lo pone main.py (vuelve al inicio).
class EscenaAjustes(Escena):

    def __init__(self, al_volver=None, **opciones):
        super().__init__(**opciones)
        self._al_volver = al_volver
        self.fondo = FondoMenu(parent=self)
        self.pantalla = PantallaAjustes(al_cerrar=self._cerrar, parent=self)

    def _cerrar(self, guardado):
        if self._al_volver is not None:
            self._al_volver()

    def al_entrar(self, **datos):
        self.fondo.t = 0.0
        self.pantalla.abrir(datos.get("seccion"))

    def al_salir(self):
        pass
