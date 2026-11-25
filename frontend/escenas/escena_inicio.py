# Escena de inicio (Ursina): wordmark, subtítulo y botones "Empezar" y "Salir".
# No conoce al gestor de escenas: recibe los callbacks `al_comenzar` y `al_salir`.
# Visual (T7): fondo de menú en capas con deriva lenta, wordmark dibujado por código y botones
# de tinta (primario amarillo / secundario). Teclado: flechas o Tab mueven el foco, Enter activa.
# Menú BOTW (sesión G, ALCALDE_MENU_BOTW, encendido por defecto): frontend/menu_botw.py pone encima una piel con el fondo
# del póster, logo y opciones en cursiva; estos botones siguen siendo los controles (mismos callbacks y confirmaciones).
# Con =0, sin recursos o si la piel falla, este menú se ve tal cual.
# Hilo conductor (docs/MODO_FERIA.md, docs/HILO_CONDUCTOR.md): botón «Modo feria» tras «Empezar» (ALCALDE_FERIA_MENU=0 lo
# quita): deja ALCALDE_FERIA=1 en el entorno y empieza como «Empezar»; «Empezar» y «Continuar» lo dejan en 0. Antes de
# una partida nueva (normal o de feria) va a la selección de rol; el PRÓLOGO en 3D sale después, al entrar al mundo
# (frontend/prologo_cinematica.py, ALCALDE_PROLOGO=0 lo quita).

from ursina import Entity, Text, color, time

from backend.logica import modo_feria
from frontend import diseno_adaptable, estilo
from frontend import menu_botw_calculos as mbc
from frontend import menu_inicio_calculos as mic
from frontend.componentes import (
    BotonPrimario, BotonSecundario, a_unidades, escala_fuente, panel_tinta, rgb,
)
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FocoTeclado, FondoMenu
from frontend.logo import crear_wordmark

TITULO = "Alcalde Digital"
SUBTITULO = "Campaña electoral en Ciudad Nova · Civitas"


# Pantalla de bienvenida; `al_comenzar` se invoca al pulsar "Empezar" y `al_salir`
# (opcional) al pulsar "Salir".
class EscenaInicio(Escena):

    # Posiciones verticales (camera.ui: 0 = centro, positivo = arriba).
    Y_TITULO = a_unidades(300 - 150)
    Y_SUBTITULO = a_unidades(300 - 262)
    Y_BOTON = a_unidades(300 - 360)
    Y_BOTON_SALIR = Y_BOTON - a_unidades(80)
    ANCHO_BOTON = a_unidades(260)
    ALTO_BOTON = a_unidades(60)

    def __init__(self, al_comenzar, al_salir=None, al_ajustes=None, al_online=None, al_local=None, **opciones):
        super().__init__(**opciones)
        self._al_comenzar = al_comenzar
        self._salir_del_juego = al_salir
        # Submenú «Multijugador» (ALCALDE_MENU_MULTIJUGADOR): `al_local(n)` lleva a elegir rol con n jugadores por
        # turnos; «En línea» queda dentro y solo si main.py pasa `al_online`.
        self._al_online = al_online
        self._al_local = al_local
        self._nivel = mic.PRINCIPAL
        self.con_multijugador = mic.multijugador_activo() and (al_local is not None or al_online is not None)
        self.confirmacion = mic.Confirmacion()
        self.fondo = FondoMenu(parent=self)
        self.wordmark = crear_wordmark(self, position=(0, self.Y_TITULO))
        self.texto_titulo = self.wordmark.texto_principal

        # Subtítulo sobre una placa de tinta: se lee igual sobre cualquier parte del cielo.
        ancho_sub = 0.80
        alto_sub = a_unidades(40)
        self.placa_subtitulo = panel_tinta(
            self, ancho_sub, alto_sub, estilo.TINTA, estilo.RADIO_CHIP_PX,
            position=(0, self.Y_SUBTITULO), sombra=False)
        self.texto_subtitulo = Text(
            SUBTITULO, parent=self.placa_subtitulo, origin=(0, 0), position=(0, 0, -0.001),
            scale=escala_fuente(21), color=rgb(estilo.COLOR_TEXTO))
        # el subtítulo casi llena la placa: con otra fuente o escala no debe salirse de ella
        diseno_adaptable.ajustar_texto(self.texto_subtitulo, ancho_sub - 0.04, escala_base=escala_fuente(21),
                                       escala_min=0.8, max_lineas=1)

        # Con «En línea» hay un botón más: se compacta la columna (alto y paso menores) para que Salir quepa. Con
        # «Modo feria» y «En línea» a la vez, más compacta aún.
        con_feria = modo_feria.menu_activo()
        con_online = al_online is not None or self.con_multijugador
        alto_b = self.ALTO_BOTON if not con_online and not con_feria else a_unidades(50)
        paso = a_unidades(80) if not con_online and not con_feria else a_unidades(62)
        if con_feria and con_online:
            alto_b, paso = a_unidades(44), a_unidades(54)
        self.boton_comenzar = BotonPrimario(
            "Empezar", al_clic=self._clic_comenzar, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=26, parent=self, position=(0, self.Y_BOTON),
        )
        y_salir = self.Y_BOTON - paso
        # Botón «Modo feria» (hilo conductor): partida corta que avanza por misiones, sin guardado.
        self.boton_feria = None
        if con_feria:
            self.boton_feria = BotonSecundario(
                "Modo feria", al_clic=self._clic_feria, ancho=self.ANCHO_BOTON, alto=alto_b,
                tamano_fuente_px=24, parent=self, position=(0, y_salir),
            )
            y_salir = y_salir - paso
        # Botón «Ajustes» (opcional: solo si main.py pasa `al_ajustes`): va entre Empezar y Salir y Salir baja
        # un puesto. Sin `al_ajustes` el menú queda exactamente como siempre.
        self.boton_ajustes = None
        if al_ajustes is not None:
            self.boton_ajustes = BotonSecundario(
                "Ajustes", al_clic=al_ajustes, ancho=self.ANCHO_BOTON, alto=alto_b,
                tamano_fuente_px=24, parent=self, position=(0, y_salir),
            )
            y_salir = y_salir - paso
        # Botón «En línea» (opcional: solo si main.py pasa `al_online`, es decir con ONLINE=True): va tras Empezar.
        # Con el submenú, este mismo botón se llama «Multijugador», sale siempre y abre el submenú.
        self.boton_online = None
        if al_online is not None or self.con_multijugador:
            texto, al_clic = ("En línea", al_online) if not self.con_multijugador else (
                mic.TEXTO_MULTIJUGADOR, lambda: self._ir_a_nivel(mic.MULTIJUGADOR))
            self.boton_online = BotonSecundario(
                texto, al_clic=al_clic, ancho=self.ANCHO_BOTON, alto=alto_b,
                tamano_fuente_px=24, parent=self, position=(0, y_salir),
            )
            y_salir = y_salir - paso
        self.boton_salir = BotonSecundario(
            "Salir", al_clic=self._clic_salir, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=24, parent=self, position=(0, y_salir),
        )
        self.botones = (self.boton_comenzar, self.boton_salir)
        if self.boton_ajustes is not None:
            self.botones = (self.boton_comenzar, self.boton_ajustes, self.boton_salir)
        if self.boton_online is not None:
            self.botones = tuple(b for b in self.botones if b is not self.boton_salir) + (
                self.boton_online, self.boton_salir)
        if self.boton_feria is not None:
            self.botones = (self.boton_comenzar, self.boton_feria) + self.botones[1:]
        self.foco = FocoTeclado(lambda: self.botones, parent=self)
        # «Continuar» (guardado de partida): oculto hasta que frontend/registro_guardado.py lo ofrece y hay un guardado.
        self.boton_continuar = BotonPrimario(
            "Continuar", al_clic=self._clic_continuar, ancho=self.ANCHO_BOTON, alto=alto_b,
            tamano_fuente_px=26, parent=self, position=(-self.X_PAREJA, self.Y_BOTON), enabled=False)
        self.texto_continuar = Text(
            "", parent=self, origin=(0, 0), position=(-self.X_PAREJA, self.Y_BOTON + alto_b / 2 + a_unidades(16), -0.001),
            scale=escala_fuente(16), color=rgb(estilo.COLOR_TEXTO), enabled=False)
        self._botones_base = self.botones
        self._al_continuar = None
        self._resumen_guardado = None
        self._crear_confirmacion(alto_b)
        self._crear_submenus(alto_b, paso)
        self.botw = None
        if mbc.activo():
            from frontend import menu_botw
            self.botw = menu_botw.crear(self)      # None si faltan recursos o falla: queda el menú de siempre

    X_PAREJA = a_unidades(140)          # con «Continuar» a la vista, él y «Partida nueva» van uno al lado del otro

    # Lo llama frontend/registro_guardado.py: `al_continuar()` carga la partida guardada y `resumen()` devuelve su texto
    # corto («2 jugadores · 5 misiones hechas») o "" si no hay guardado de este mundo.
    def ofrecer_continuar(self, al_continuar, resumen):
        self._al_continuar, self._resumen_guardado = al_continuar, resumen
        self._refrescar_continuar()

    def _clic_continuar(self):
        if self._al_continuar is not None:
            modo_feria.encender(False)
            self._al_continuar()

    def _refrescar_continuar(self):
        texto = ""
        if self._resumen_guardado is not None:
            try:
                texto = self._resumen_guardado() or ""
            except Exception:
                texto = ""
        hay = bool(texto)
        self.boton_continuar.enabled = hay
        self.texto_continuar.enabled = hay
        self.texto_continuar.text = f"Partida guardada: {texto}" if hay else ""
        if hay:
            # cabe sobre la pareja de botones (de «Continuar» al centro de «Partida nueva»)
            diseno_adaptable.ajustar_texto(self.texto_continuar, 2 * self.X_PAREJA, escala_base=escala_fuente(16),
                                           escala_min=0.8, max_lineas=1)
        self.boton_comenzar.x = self.X_PAREJA if hay else 0
        self.boton_comenzar.text = "Partida nueva" if hay else "Empezar"
        # Dentro de un submenú la lista de controles es la suya: el menú principal se recompone al volver.
        if self._nivel == mic.PRINCIPAL:
            self.botones = ((self.boton_continuar,) + self._botones_base) if hay else self._botones_base
        self._aplicar_nivel()

    # -- Submenú «Multijugador» (ALCALDE_MENU_MULTIJUGADOR, docs/MENU_MULTIJUGADOR.md) --

    # Un botón por opción de cada submenú (menu_inicio_calculos.opciones_de). En el menú de siempre se ven en una placa
    # sobre un velo, como la confirmación; con la piel BOTW (frontend/menu_botw.py) se dibujan como sus opciones.
    def _crear_submenus(self, alto_b, paso):
        self._submenus = {}
        self.botones_submenu = ()
        if not self.con_multijugador:
            return
        self.velo_sub = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.55), z=-0.2,
                               collider="box", enabled=False)
        filas = max(len(mic.opciones_de(n, self._al_online is not None)) for n in (mic.MULTIJUGADOR, mic.LOCAL))
        alto_placa = a_unidades(90) + filas * paso
        y_titulo = alto_placa / 2 - a_unidades(40)
        self.placa_sub = panel_tinta(self, self.ANCHO_BOTON + a_unidades(80), alto_placa, estilo.COLOR_PANEL,
                                     position=(0, 0, -0.21), enabled=False)
        self.texto_sub = Text("", parent=self.placa_sub, origin=(0, 0), position=(0, y_titulo, -0.01),
                              scale=escala_fuente(26), color=rgb(estilo.COLOR_TEXTO))
        acciones = {mic.LOCAL_TURNOS: lambda: self._ir_a_nivel(mic.LOCAL), mic.EN_LINEA: self._al_online,
                    mic.ATRAS: self._volver_nivel}
        for n in mic.CANTIDADES_LOCALES:
            acciones[mic.id_cantidad(n)] = lambda n=n: self._clic_local(n)
        for nivel in (mic.MULTIJUGADOR, mic.LOCAL):
            botones = []
            for i, (id_opcion, texto) in enumerate(mic.opciones_de(nivel, self._al_online is not None)):
                clase = BotonSecundario if id_opcion == mic.ATRAS else BotonPrimario
                botones.append(clase(texto, al_clic=acciones[id_opcion], ancho=self.ANCHO_BOTON, alto=alto_b,
                                     tamano_fuente_px=24, parent=self, enabled=False,
                                     position=(0, y_titulo - a_unidades(60) - i * paso, -0.22)))
            self._submenus[nivel] = tuple(botones)
        self.botones_submenu = self._submenus[mic.MULTIJUGADOR] + self._submenus[mic.LOCAL]

    def _ir_a_nivel(self, nivel):
        self._nivel = nivel
        if nivel == mic.PRINCIPAL:
            self._refrescar_continuar()
        else:
            self.botones = self._submenus[nivel]
            self._aplicar_nivel()
        self.foco.reiniciar()

    def _volver_nivel(self):
        self._ir_a_nivel(mic.nivel_anterior(self._nivel))

    # Muestra los botones del nivel actual. La placa solo se ve en el menú de siempre: con la piel BOTW los botones
    # cuelgan de su contenedor oculto y las opciones dibujadas siguen a `self.botones`.
    def _aplicar_nivel(self):
        if not self._submenus:
            return
        clasico = self.boton_salir.parent is self
        actuales = self._submenus.get(self._nivel, ())
        for boton in self.botones_submenu:
            boton.enabled = boton in actuales
        self.velo_sub.enabled = self.placa_sub.enabled = bool(actuales) and clasico
        self.texto_sub.text = mic.TITULOS.get(self._nivel, "")

    # «2 / 3 / 4 jugadores»: partida nueva por turnos (pisa el guardado: pide confirmación como «Partida nueva»).
    def _clic_local(self, n):
        if self._al_local is None:
            return
        empezar = lambda: self._empezar_local(n)     # noqa: E731
        if mic.necesita_confirmar_nueva(self.boton_continuar.enabled):
            self._pedir(mic.NUEVA, empezar)
        else:
            empezar()

    def _empezar_local(self, n):
        modo_feria.encender(False)
        self._al_local(n)

    # -- Confirmaciones (EST-011 «Salir», BUG-005 «Partida nueva» con guardado): foco en «No», Esc/B = No --

    def _crear_confirmacion(self, alto_b):
        self.velo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba(0, 0, 0, 0.55), z=-0.3,
                           collider="box", enabled=False)          # tapa el menú: el ratón no llega a lo de detrás
        self.dialogo = panel_tinta(self, 0.78, 0.3, estilo.COLOR_PANEL, position=(0, 0.02, -0.31), enabled=False)
        self.texto_dialogo = Text("", parent=self.dialogo, origin=(0, 0), position=(0, 0.06, -0.01),
                                  scale=escala_fuente(24), color=rgb(estilo.COLOR_TEXTO))
        self.boton_no = BotonPrimario(mic.TEXTO_NO, al_clic=lambda: self._responder(False), ancho=a_unidades(180),
                                      alto=alto_b, tamano_fuente_px=24, parent=self.dialogo,
                                      position=(-0.16, -0.07, -0.01))
        self.boton_si = BotonSecundario("Sí", al_clic=lambda: self._responder(True), ancho=a_unidades(180),
                                        alto=alto_b, tamano_fuente_px=24, parent=self.dialogo,
                                        position=(0.16, -0.07, -0.01))
        self._botones_menu = None

    def _pedir(self, contenido, al_si):
        if self.confirmacion.abierta:
            return
        self.confirmacion.pedir(contenido, al_si)
        self.texto_dialogo.text = self.confirmacion.pregunta
        self.boton_si.text = self.confirmacion.texto_si
        self.velo.enabled = self.dialogo.enabled = True
        self._botones_menu, self._indice_menu = self.botones, self.foco.indice
        self.botones = (self.boton_no, self.boton_si)
        self.foco.indice = 0                    # «No» con el anillo de foco a la vista
        self.foco.visible = True
        self.foco._hover_previo = None
        self.foco._aplicar()

    def _responder(self, si):
        if not self.confirmacion.abierta:
            return
        if si and not self.confirmacion.puede_si(por_teclado=self.foco.visible):
            return                                  # «Sí» demasiado pronto (aporreando el mando): no pasa nada
        accion = self.confirmacion.responder(si)
        self._cerrar_confirmacion()
        if accion is not None:
            accion()

    def _cerrar_confirmacion(self):
        self.confirmacion.responder(False)
        self.velo.enabled = self.dialogo.enabled = False
        if self._botones_menu is not None:
            self.botones, self.foco.indice = self._botones_menu, self._indice_menu
            self._botones_menu = None
            self.foco._aplicar()

    def _clic_salir(self):
        if self._salir_del_juego is not None:
            self._pedir(mic.SALIR, self._salir_del_juego)

    def _clic_comenzar(self):
        if self._al_comenzar is None:
            return
        empezar = lambda: self._empezar(feria=False)     # noqa: E731
        if mic.necesita_confirmar_nueva(self.boton_continuar.enabled):
            self._pedir(mic.NUEVA, empezar)
        else:
            empezar()

    # La partida de feria no se guarda ni pisa el guardado al empezar: no pide confirmación.
    def _clic_feria(self):
        if self._al_comenzar is not None:
            self._empezar(feria=True)

    # Partida nueva: fija el modo (ALCALDE_FERIA, lo lee crear_flujo) y va a la selección de rol. El prólogo en 3D sale
    # al entrar al mundo, después de elegir personaje (frontend/prologo_cinematica.py).
    def _empezar(self, feria):
        modo_feria.encender(feria)
        self._al_comenzar()

    def input(self, key):
        if self.confirmacion.tecla(key):
            self._cerrar_confirmacion()
        elif key in mic.TECLAS_NO and self._nivel != mic.PRINCIPAL:
            self._volver_nivel()

    def update(self):
        if self.confirmacion.abierta:
            self.confirmacion.avanzar(time.dt, self.foco.enfocado() is self.boton_si)

    def al_salir(self):
        self._cerrar_confirmacion()
        if self.botw is not None:
            self.botw.al_salir()

    def al_entrar(self, **datos):
        self._cerrar_confirmacion()
        self._nivel = mic.PRINCIPAL
        self._refrescar_continuar()
        self.foco.reiniciar()
        self.fondo.t = 0.0
        if self.botw is not None:
            self.botw.al_entrar()
