# Menú del modo ONLINE (Ursina): Crear sala / Unirse / Atrás, formularios y pantalla «Conectando…».
#   Crear sala: alias, ámbito («Solo este equipo» / «Red local» (defecto) / «Abierto a internet» con explicación y
#       confirmación escribiendo ABRIR; el anfitrión genera un código de 12 caracteres) y puerto.
#   Unirse: alias, IP:puerto y código (con botones «Pegar»).
# Recuerda alias y último anfitrión en el almacén de ajustes (nombre_en_linea, ultimo_host).
# No conoce al gestor: recibe `servicios` (online_servicios.ServiciosOnline) y callbacks:
#   al_atras()                    vuelve al menú de inicio
#   al_conectado(sesion)          la conexión llegó a la sala (SesionLobby con su ModeloSala)
#   al_fallo(motivo, pagina)      error de red/rechazo (motivo = código de online_lobby_calculos.info_error)
# Teclado: Arriba/Abajo/Tab mueven el foco (los campos de texto se activan solos), Intro avanza o envía, Escape = atrás.
# Se adapta a la ventana con diseno_adaptable.ajustar_escala sobre la raíz de la escena.

import time

from ursina import Entity

from backend.logica import ajustes as modelo_ajustes
from frontend import campo_texto_calculos as calc_campo
from frontend import diseno_adaptable, estilo, tipografia
from frontend import online_lobby_calculos as lobby
from frontend.campo_texto import CampoTexto
from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, panel_tinta, rgb
from frontend.escenas.escena_base import Escena
from frontend.fondo_menu import FondoMenu, anadir_filo
from frontend.online_ui import FocoOnline, SelectorSimple, crear_texto, fijar, texto_envuelto

PAGINA_PRINCIPAL, PAGINA_CREAR, PAGINA_UNIRSE, PAGINA_CONECTANDO = "principal", "crear", "unirse", "conectando"
ANCHO_PANEL, ALTO_PANEL = 1.16, 0.86
X_ETIQUETA, X_CAMPO, ANCHO_CAMPO = -0.52, 0.12, 0.62
Z = -0.004


class EscenaOnlineMenu(Escena):

    def __init__(self, servicios, al_atras=None, al_conectado=None, al_fallo=None, gestor_ajustes=None, **opciones):
        super().__init__(**opciones)
        self.servicios = servicios
        self._al_atras = al_atras
        self._al_conectado = al_conectado
        self._al_fallo = al_fallo
        self._gestor_ajustes = gestor_ajustes
        self._construido = False      # los campos avisan al escribir: no validar a medio construir
        self.pagina = PAGINA_PRINCIPAL
        self.sesion = None
        self._t_conexion = 0.0
        self._pagina_origen = PAGINA_CREAR
        self.fondo = FondoMenu(parent=self)
        self.raiz = Entity(parent=self)
        diseno_adaptable.ajustar_escala(self.raiz)
        self.panel = panel_tinta(self.raiz, ANCHO_PANEL, ALTO_PANEL, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO_PANEL, ALTO_PANEL, estilo.RADIO_PANEL_PX)
        self.titulo = crear_texto(self.raiz, "En línea", 0, 0.375, 38, origen=(0, 0), font=tipografia.FUENTE_TITULO)
        self.paginas = {}
        self.controles = {}
        self._construir_principal()
        self._construir_crear()
        self._construir_unirse()
        self._construir_conectando()
        self.foco = FocoOnline(self._controles_activos, al_escape=self.atras, parent=self)
        self._construido = True
        self._mostrar(PAGINA_PRINCIPAL)

    # ------------------------------------------------------------------ construcción
    def _grupo(self, nombre):
        g = Entity(parent=self.raiz, enabled=False)
        self.paginas[nombre] = g
        return g

    def _boton(self, g, texto, accion, x, y, ancho=0.40, primario=False, px=22):
        clase = BotonPrimario if primario else BotonSecundario
        return clase(texto, al_clic=accion, ancho=ancho, alto=a_unidades(52), tamano_fuente_px=px + (2 if primario else 0),
                     parent=g, position=(x, y, -0.003))

    def _fila_campo(self, g, etiqueta, y, tipo, valor="", marcador="", ancho=ANCHO_CAMPO, x=X_CAMPO, **kw):
        crear_texto(g, etiqueta, X_ETIQUETA, y, 21)
        campo = CampoTexto(tipo, valor, ancho=ancho, marcador=marcador, parent=g, position=(x, y, -0.003), **kw)
        return campo

    def _construir_principal(self):
        g = self._grupo(PAGINA_PRINCIPAL)
        t = crear_texto(g, " ", 0, 0.275, 19, estilo.COLOR_TEXTO_TENUE, origen=(0, 0.5))
        texto_envuelto(t, "Juega en cooperativo con hasta 4 personas: una aloja la partida y las demás entran con su "
                          "dirección y un código.", 0.95, 19)
        t.origin = (0, 0.5)
        self.btn_crear = self._boton(g, "Crear sala", self.ir_crear, 0, 0.08, primario=True)
        self.btn_unirse = self._boton(g, "Unirse a una sala", self.ir_unirse, 0, -0.03)
        self.btn_atras_p = self._boton(g, "Atrás", self.atras, 0, -0.14)
        self.nota_cifrado = crear_texto(g, " ", 0, -0.30, 17, estilo.ESTADO_AVISO, origen=(0, 0.5))
        texto_envuelto(self.nota_cifrado, lobby.AVISO_SIN_CIFRAR, 0.95, 17)
        self.nota_cifrado.origin = (0, 0.5)
        self.nota_privacidad = crear_texto(g, " ", 0, -0.39, 16, estilo.COLOR_TEXTO_TENUE, origen=(0, 0.5))
        texto_envuelto(self.nota_privacidad, lobby.AVISO_PRIVACIDAD, 0.95, 16)
        self.nota_privacidad.origin = (0, 0.5)
        self.controles[PAGINA_PRINCIPAL] = [self.btn_crear, self.btn_unirse, self.btn_atras_p]

    def _construir_crear(self):
        g = self._grupo(PAGINA_CREAR)
        crear_texto(g, "Crear sala", -ANCHO_PANEL / 2 + 0.05, 0.31, 24, estilo.ACENTO_PRIMARIO, font=tipografia.FUENTE_TITULO)
        self.c_alias = self._fila_campo(g, "Alias", 0.235, calc_campo.TIPO_ALIAS, marcador="Tu nombre en la sala",
                                        al_cambiar=lambda _t: self._validar_crear())
        crear_texto(g, "Dónde abrirla", X_ETIQUETA, 0.14, 21)
        opciones = [(a, n) for a, n in lobby.AMBITOS_UI]
        self.c_ambito = SelectorSimple(opciones, [a for a, _ in opciones].index(lobby.AMBITO_DEFECTO),
                                       al_cambiar=lambda _v: self._validar_crear(), ancho=ANCHO_CAMPO, parent=g,
                                       position=(X_CAMPO, 0.14, 0))
        self.c_explica = crear_texto(g, " ", X_ETIQUETA, 0.085, 17, estilo.COLOR_TEXTO_TENUE, origen=(-0.5, 0.5))
        self.c_puerto = self._fila_campo(g, "Puerto", -0.065, calc_campo.TIPO_PUERTO, str(lobby.PUERTO_DEFECTO),
                                         ancho=0.22, x=X_CAMPO - ANCHO_CAMPO / 2 + 0.11,
                                         al_cambiar=lambda _t: self._validar_crear())
        self.c_aviso_abierto = crear_texto(g, " ", X_ETIQUETA, -0.115, 17, estilo.ESTADO_AVISO, origen=(-0.5, 0.5))
        self.c_confirma_etq = crear_texto(g, "Confirmar", X_ETIQUETA, -0.225, 21)
        self.c_confirma = CampoTexto(calc_campo.TIPO_CONFIRMAR, "", ancho=0.30, marcador="Escribe ABRIR", parent=g,
                                     position=(X_CAMPO - ANCHO_CAMPO / 2 + 0.15, -0.225, -0.003),
                                     al_cambiar=lambda _t: self._validar_crear())
        self.c_error = crear_texto(g, " ", X_ETIQUETA, -0.30, 18, estilo.ESTADO_AVISO, origen=(-0.5, 0))
        self.c_atras = self._boton(g, "Atrás", lambda: self._mostrar(PAGINA_PRINCIPAL), -0.27, -0.375, ancho=0.34)
        self.c_crear = self._boton(g, "Crear sala", self.crear_sala, 0.22, -0.375, ancho=0.44, primario=True)
        self.c_alias.al_enviar = lambda: self.foco.mover(1)
        self.c_puerto.al_enviar = lambda: self.foco.mover(1)
        self.c_confirma.al_enviar = self.crear_sala
        self.controles[PAGINA_CREAR] = [self.c_alias, self.c_ambito, self.c_puerto, self.c_confirma, self.c_atras,
                                        self.c_crear]

    def _construir_unirse(self):
        g = self._grupo(PAGINA_UNIRSE)
        crear_texto(g, "Unirse a una sala", -ANCHO_PANEL / 2 + 0.05, 0.31, 24, estilo.ACENTO_PRIMARIO,
                    font=tipografia.FUENTE_TITULO)
        self.u_alias = self._fila_campo(g, "Alias", 0.215, calc_campo.TIPO_ALIAS, marcador="Tu nombre en la sala",
                                        al_cambiar=lambda _t: self._validar_unirse())
        self.u_destino = self._fila_campo(g, "IP:puerto", 0.105, calc_campo.TIPO_HOST, marcador="192.168.1.5:7777",
                                          ancho=0.50, x=X_CAMPO - 0.06, al_cambiar=lambda _t: self._validar_unirse())
        self.u_codigo = self._fila_campo(g, "Código", -0.005, calc_campo.TIPO_CODIGO, marcador="ABCD-EFGH",
                                         ancho=0.50, x=X_CAMPO - 0.06, al_cambiar=lambda _t: self._validar_unirse())
        self.u_pegar_destino = self._boton(g, "Pegar", lambda: self.u_destino.pegar(), 0.405, 0.105, ancho=0.16, px=18)
        self.u_pegar_codigo = self._boton(g, "Pegar", lambda: self.u_codigo.pegar(), 0.405, -0.005, ancho=0.16, px=18)
        self.u_ayuda = crear_texto(g, " ", X_ETIQUETA, -0.085, 17, estilo.COLOR_TEXTO_TENUE, origen=(-0.5, 0.5))
        texto_envuelto(self.u_ayuda, "Pídele al anfitrión la dirección (IP:puerto) y el código que ve en su sala. "
                       + lobby.AVISO_SIN_CIFRAR, 1.0, 17)
        self.u_ayuda.origin = (-0.5, 0.5)
        self.u_error = crear_texto(g, " ", X_ETIQUETA, -0.255, 18, estilo.ESTADO_AVISO, origen=(-0.5, 0))
        self.u_atras = self._boton(g, "Atrás", lambda: self._mostrar(PAGINA_PRINCIPAL), -0.27, -0.375, ancho=0.34)
        self.u_unirse = self._boton(g, "Unirse", self.unirse, 0.22, -0.375, ancho=0.44, primario=True)
        self.u_alias.al_enviar = lambda: self.foco.ir_a(self.u_destino)
        self.u_destino.al_enviar = lambda: self.foco.ir_a(self.u_codigo)
        self.u_codigo.al_enviar = self.unirse
        self.controles[PAGINA_UNIRSE] = [self.u_alias, self.u_destino, self.u_pegar_destino, self.u_codigo,
                                         self.u_pegar_codigo, self.u_atras, self.u_unirse]

    def _construir_conectando(self):
        g = self._grupo(PAGINA_CONECTANDO)
        self.k_texto = crear_texto(g, "Conectando…", 0, 0.08, 28, origen=(0, 0), font=tipografia.FUENTE_TITULO)
        self.k_detalle = crear_texto(g, " ", 0, -0.02, 19, estilo.COLOR_TEXTO_TENUE, origen=(0, 0.5))
        self.k_cancelar = self._boton(g, "Cancelar", self.cancelar_conexion, 0, -0.2)
        self.controles[PAGINA_CONECTANDO] = [self.k_cancelar]

    # ------------------------------------------------------------------ páginas
    def _controles_activos(self):
        return self.controles.get(self.pagina, [])

    def _mostrar(self, pagina):
        self.pagina = pagina
        for nombre, g in self.paginas.items():
            g.enabled = nombre == pagina
        fijar(self.titulo, {PAGINA_CONECTANDO: "Conectando"}.get(pagina, "En línea"))
        if pagina == PAGINA_CREAR:
            self._validar_crear()
        elif pagina == PAGINA_UNIRSE:
            self._validar_unirse()
        self.foco.reiniciar()
        for lista in self.controles.values():
            for c in lista:
                if isinstance(c, CampoTexto) and c.activo:
                    c.desactivar()

    def ir_crear(self):
        self._pagina_origen = PAGINA_CREAR
        self._mostrar(PAGINA_CREAR)

    def ir_unirse(self):
        self._pagina_origen = PAGINA_UNIRSE
        self._mostrar(PAGINA_UNIRSE)

    def atras(self):
        if self.pagina == PAGINA_PRINCIPAL:
            if self._al_atras is not None:
                self._al_atras()
        elif self.pagina == PAGINA_CONECTANDO:
            self.cancelar_conexion()
        else:
            self._mostrar(PAGINA_PRINCIPAL)

    # ------------------------------------------------------------------ validación viva
    def formulario_crear(self):
        return lobby.validar_crear(self.c_alias.texto, self.c_ambito.valor(), self.c_puerto.texto,
                                   self.c_confirma.texto)

    def formulario_unirse(self):
        return lobby.validar_unirse(self.u_alias.texto, self.u_destino.texto, self.u_codigo.texto)

    def _validar_crear(self):
        if not self._construido:
            return None
        f = self.formulario_crear()
        ambito = self.c_ambito.valor()
        abierto = ambito == lobby.AMBITO_ABIERTO
        texto_envuelto(self.c_explica, lobby.EXPLICACION_AMBITO.get(ambito, ""), 1.0, 17, max_lineas=3)
        self.c_explica.origin = (-0.5, 0.5)
        texto_envuelto(self.c_aviso_abierto, lobby.AVISO_ABIERTO if abierto else lobby.AVISO_SIN_CIFRAR, 1.0, 17,
                       max_lineas=2)
        self.c_aviso_abierto.origin = (-0.5, 0.5)
        self.c_aviso_abierto.color = rgb(estilo.ESTADO_AVISO if abierto else estilo.COLOR_TEXTO_TENUE)
        self.c_confirma_etq.enabled = abierto
        self.c_confirma.enabled = abierto
        self.controles[PAGINA_CREAR] = [self.c_alias, self.c_ambito, self.c_puerto] + (
            [self.c_confirma] if abierto else []) + [self.c_atras, self.c_crear]
        primero = next(iter(f.errores.values()), "")
        fijar(self.c_error, primero)
        self.c_alias.marcar_error("alias" in f.errores and bool(self.c_alias.texto))
        self.c_puerto.marcar_error("puerto" in f.errores)
        self.c_crear.fijar_habilitado(f.valido)
        return f

    def _validar_unirse(self):
        if not self._construido:
            return None
        f = self.formulario_unirse()
        fijar(self.u_error, next(iter(f.errores.values()), ""))
        self.u_alias.marcar_error("alias" in f.errores and bool(self.u_alias.texto))
        self.u_destino.marcar_error("destino" in f.errores and bool(self.u_destino.texto))
        self.u_codigo.marcar_error("codigo" in f.errores and bool(self.u_codigo.texto))
        self.u_unirse.fijar_habilitado(f.valido)
        return f

    # ------------------------------------------------------------------ acciones
    def _ajustes(self):
        return self._gestor_ajustes if self._gestor_ajustes is not None else modelo_ajustes.obtener()

    def _recordar(self, alias, destino):
        try:
            gestor = self._ajustes()
            gestor.cambiar(nombre_en_linea=alias, ultimo_host=destino or "")
            gestor.guardar()
        except Exception as error:      # el almacén nunca debe impedir jugar
            print(f"[online] no se pudo guardar el alias: {error}")

    def crear_sala(self):
        f = self._validar_crear()
        if not f.valido:
            return None
        v = f.valores
        try:
            sesion = self.servicios.abrir_como_anfitrion(v["alias"], v["ambito"], v["puerto"], v["abierto"])
        except (OSError, ValueError, RuntimeError, TimeoutError) as error:
            fijar(self.c_error, f"No se pudo abrir la sala: {error}")
            return None
        self._recordar(v["alias"], None)
        self._empezar_conexion(sesion, "tu sala")
        return sesion

    def unirse(self):
        f = self._validar_unirse()
        if not f.valido:
            return None
        v = f.valores
        try:
            sesion = self.servicios.abrir_como_cliente(v["alias"], v["host"], v["puerto"], v["codigo"])
        except (OSError, ValueError, RuntimeError) as error:
            fijar(self.u_error, f"No se pudo conectar: {error}")
            return None
        self._recordar(v["alias"], lobby.formatear_destino(v["host"], v["puerto"]))
        self._empezar_conexion(sesion, sesion.destino)
        return sesion

    def _empezar_conexion(self, sesion, destino):
        self.sesion = sesion
        self._t_conexion = time.monotonic()
        fijar(self.k_texto, "Conectando…")
        fijar(self.k_detalle, f"Esperando respuesta de {destino}")
        self._mostrar(PAGINA_CONECTANDO)

    def cancelar_conexion(self):
        self._cerrar_sesion()
        self._mostrar(self._pagina_origen)

    def _cerrar_sesion(self):
        if self.sesion is not None:
            self.sesion.cerrar()
            self.sesion = None

    # ------------------------------------------------------------------ ciclo de vida
    def al_entrar(self, **datos):
        self.fondo.t = 0.0
        pagina = datos.get("pagina")
        self._cargar_recordados()
        self._mostrar(pagina if pagina in (PAGINA_CREAR, PAGINA_UNIRSE) else PAGINA_PRINCIPAL)
        if pagina in (PAGINA_CREAR, PAGINA_UNIRSE):
            self._pagina_origen = pagina

    def _cargar_recordados(self):
        actual = self._ajustes().actual
        alias = actual.nombre_en_linea
        for campo in (self.c_alias, self.u_alias):
            if not campo.texto and alias:
                campo.fijar_texto(alias)
        if not self.u_destino.texto and actual.ultimo_host:
            self.u_destino.fijar_texto(actual.ultimo_host)

    def al_salir(self):
        for lista in self.controles.values():
            for c in lista:
                if isinstance(c, CampoTexto):
                    c.desactivar()

    def update(self):
        if self.pagina != PAGINA_CONECTANDO or self.sesion is None:
            return
        self.sondear()

    # Drena los eventos de uno en uno hasta llegar a la sala (lo posterior queda en la cola para la sala).
    def sondear(self):
        sesion = self.sesion
        modelo = sesion.modelo
        for _ in range(64):
            eventos = sesion.cliente.sacar_eventos(1)
            if not eventos:
                break
            resultado = modelo.aplicar(eventos[0])
            if resultado in ("rechazo", "cerrado"):
                motivo = (modelo.rechazo or {}).get("codigo") or modelo.motivo_cierre
                self._fallar(motivo)
                return
            if eventos[0].get("t") == "estado" and eventos[0].get("estado") == "en_sala":
                self.sesion = None
                if self._al_conectado is not None:
                    self._al_conectado(sesion)
                return
        if time.monotonic() - self._t_conexion > lobby.TIEMPO_CONEXION_S:
            self._fallar("tiempo_agotado")

    def _fallar(self, motivo):
        self._cerrar_sesion()
        if self._al_fallo is not None:
            self._al_fallo(motivo, self._pagina_origen)
