# Sala de espera del modo ONLINE (Ursina). Muestra:
#   - las 4 tarjetas de rol (TarjetaRol de escena_seleccion_rol.py, reutilizada por IMPORTACIÓN): clic en un rol
#     libre lo pide al anfitrión; los tomados muestran «Elegido por <alias>»;
#   - 4 casillas de jugador: alias, rol, listo, conexión y ping, con TEXTO además de color (filtros de daltonismo);
#   - IP:puerto y código (ocultable, con «Copiar»; solo el anfitrión los tiene) y «Ayuda del cortafuegos de macOS»;
#   - «Listo», «Iniciar partida» (solo anfitrión, activo cuando todos están listos) y «Salir de la sala»;
#   - el aviso fijo «el tráfico no va cifrado: usa red local o VPN».
# Recibe `sesion` (online_servicios.SesionLobby) en al_entrar. Cuando llega «inicio» deja de drenar eventos (los
# siguientes quedan en la cola de ClienteRed) y llama `al_empezar(cliente, info)` (T6/T7 lo conectan; ver
# online_servicios). Si `al_empezar` es None muestra un aviso y se queda en la sala.
#   al_salir()            tras abandonar la sala (cierra cliente y, si aloja, el anfitrión)
#   al_fallo(motivo, p)   la conexión se perdió o fue rechazada

from ursina import Entity

from backend.logica.roles import ORDEN_ROLES
from frontend import diseno_adaptable, estilo, tipografia
from frontend import online_lobby_calculos as lobby
from frontend.campo_texto import copiar_al_portapapeles
from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, panel_tinta, rgb
from frontend.escenas.escena_base import Escena
from frontend.escenas.escena_seleccion_rol import ANCHO_TARJETA, TarjetaRol
from frontend.fondo_menu import FondoMenu, anadir_filo
from frontend.online_ui import FocoOnline, ajustar_ancho, crear_texto, fijar, texto_envuelto

ANCHO_PANEL, ALTO_PANEL = 1.70, 0.96
ESCALA_TARJETAS = 0.52
Y_TARJETAS = 0.18
Y_FILAS0 = -0.115
ALTO_FILA = 0.070
ANCHO_TABLA = 1.60
X_COL = {"alias": -0.77, "rol": -0.40, "listo": -0.08, "conexion": 0.22, "ping": 0.50}
X_DER = 0.46                       # centro de la columna derecha (código y cómo entrar)
COLOR_NIVEL = {lobby.NIVEL_BUENO: estilo.ESTADO_EXITO, lobby.NIVEL_ACEPTABLE: estilo.ESTADO_AVISO,
               lobby.NIVEL_ALTO: estilo.ESTADO_ERROR, lobby.NIVEL_SIN_DATO: estilo.COLOR_TEXTO_TENUE}
REFRESCO_S = 0.5


class FilaJugador(Entity):
    """Una casilla de jugador (fila de la tabla)."""

    def __init__(self, indice, **kw):
        super().__init__(**kw)
        self.panel = panel_tinta(self, ANCHO_TABLA, ALTO_FILA - 0.010, estilo.COLOR_TARJETA, estilo.RADIO_CHIP_PX,
                                 sombra=False, borde_px=2, position=(0, 0, 0))
        self.t_alias = crear_texto(self, " ", X_COL["alias"], 0.010, 20, z=-0.01)
        self.t_sub = crear_texto(self, " ", X_COL["alias"], -0.020, 14, estilo.COLOR_TEXTO_TENUE, z=-0.01)
        self.t_rol = crear_texto(self, " ", X_COL["rol"], 0, 19, z=-0.01)
        self.t_listo = crear_texto(self, " ", X_COL["listo"], 0, 19, z=-0.01)
        self.t_conexion = crear_texto(self, " ", X_COL["conexion"], 0, 19, z=-0.01)
        self.t_ping = crear_texto(self, " ", X_COL["ping"], 0, 19, z=-0.01)

    def pintar(self, c):
        if not c.ocupada:
            fijar(self.t_alias, f"Casilla {c.indice + 1} (libre)")
            self.t_alias.color = rgb(estilo.COLOR_TEXTO_TENUE)
            for t in (self.t_sub, self.t_rol, self.t_listo, self.t_conexion, self.t_ping):
                fijar(t, " ")
            fijar(self.t_conexion, "Libre")
            self.t_conexion.color = rgb(estilo.COLOR_TEXTO_TENUE)
            return
        fijar(self.t_alias, c.alias)
        ajustar_ancho(self.t_alias, 0.34, 20)
        self.t_alias.color = rgb(estilo.COLOR_TEXTO)
        etiquetas = [e for e, ok in (("Anfitrión", c.anfitrion), ("Tú", c.local)) if ok]
        fijar(self.t_sub, " · ".join(etiquetas))
        fijar(self.t_rol, c.nombre_rol)
        ajustar_ancho(self.t_rol, 0.30, 19)
        fijar(self.t_listo, c.texto_listo)
        self.t_listo.color = rgb(estilo.ESTADO_EXITO if c.listo else estilo.COLOR_TEXTO_TENUE)
        fijar(self.t_conexion, c.texto_conexion)
        self.t_conexion.color = rgb(estilo.ESTADO_EXITO if c.conectado else estilo.ESTADO_ERROR)
        fijar(self.t_ping, c.texto_ping)
        self.t_ping.color = rgb(COLOR_NIVEL[c.nivel_ping])


class EscenaSala(Escena):

    def __init__(self, al_empezar=None, al_salir=None, al_fallo=None, copiar=None, **opciones):
        super().__init__(**opciones)
        self._al_empezar = al_empezar
        self._al_salir = al_salir
        self._al_fallo = al_fallo
        self._copiar = copiar if copiar is not None else copiar_al_portapapeles
        self.sesion = None
        self.empezo = False
        self.codigo_visible = False
        self.ayuda_visible = False
        self._t_refresco = 0.0
        self._aviso_local = ""
        self.fondo = FondoMenu(velo=140, parent=self)
        self.raiz = Entity(parent=self)
        diseno_adaptable.ajustar_escala(self.raiz)
        self.panel = panel_tinta(self.raiz, ANCHO_PANEL, ALTO_PANEL, estilo.COLOR_PANEL, estilo.RADIO_PANEL_PX)
        anadir_filo(self.panel, ANCHO_PANEL, ALTO_PANEL, estilo.RADIO_PANEL_PX)
        self.titulo = crear_texto(self.raiz, "Sala de espera", -ANCHO_PANEL / 2 + 0.05, 0.43, 30,
                                  font=tipografia.FUENTE_TITULO)
        self.t_estado = crear_texto(self.raiz, " ", -0.20, 0.43, 20, estilo.ACENTO_SECUNDARIO,
                                    origen=(-0.5, 0))
        crear_texto(self.raiz, "Elige tu rol (clic en una tarjeta libre)", -0.80, 0.37, 18, estilo.COLOR_TEXTO_TENUE)

        # Tarjetas de rol (reutilizadas): una por rol, fila a la izquierda.
        self.grupo_roles = Entity(parent=self.raiz, scale=ESCALA_TARJETAS, position=(-0.385, Y_TARJETAS, 0))
        self.tarjetas = {}
        paso = ANCHO_TARJETA + 0.045
        total = len(ORDEN_ROLES)
        for i, rol in enumerate(ORDEN_ROLES):
            self.tarjetas[rol] = TarjetaRol(rol, al_clic=lambda r=rol: self.elegir_rol(r), parent=self.grupo_roles,
                                            position=((i - (total - 1) / 2) * paso, 0))

        # Cabecera de la tabla y casillas
        for clave, etq in (("alias", "Jugador"), ("rol", "Rol"), ("listo", "Estado"), ("conexion", "Conexión"),
                           ("ping", "Ping")):
            crear_texto(self.raiz, etq, X_COL[clave], Y_FILAS0 + 0.058, 16,
                        estilo.COLOR_TEXTO_TENUE)
        self.filas = [FilaJugador(i, parent=self.raiz, position=(0, Y_FILAS0 - i * ALTO_FILA, -0.01)) for i in range(4)]

        # Columna derecha: cómo entrar (solo el anfitrión) + aviso de cifrado
        self.caja_codigo = Entity(parent=self.raiz)
        panel_tinta(self.caja_codigo, 0.74, 0.31, estilo.COLOR_TARJETA, estilo.RADIO_TARJETA_PX, sombra=False,
                    borde_px=2, position=(X_DER, 0.205, 0))
        xi = X_DER - 0.34
        crear_texto(self.caja_codigo, "Cómo entrar", xi, 0.335, 16, estilo.COLOR_TEXTO_TENUE)
        self.t_destino = crear_texto(self.caja_codigo, " ", xi, 0.295, 22)
        self.t_codigo = crear_texto(self.caja_codigo, " ", xi, 0.245, 22, estilo.ACENTO_PRIMARIO)
        self.btn_ver = BotonSecundario("Mostrar código", al_clic=self.alternar_codigo, ancho=0.34,
                                       alto=a_unidades(38), tamano_fuente_px=17, parent=self.caja_codigo,
                                       position=(X_DER - 0.18, 0.17, -0.003))
        self.btn_copiar = BotonSecundario("Copiar", al_clic=self.copiar_acceso, ancho=0.34, alto=a_unidades(38),
                                          tamano_fuente_px=17, parent=self.caja_codigo,
                                          position=(X_DER + 0.18, 0.17, -0.003))
        self.t_copiado = crear_texto(self.caja_codigo, " ", xi, 0.115, 15, estilo.ESTADO_EXITO)
        self.t_cifrado = crear_texto(self.raiz, " ", X_DER - 0.37, 0.04, 16, estilo.ESTADO_AVISO, origen=(-0.5, 0.5))
        texto_envuelto(self.t_cifrado, "Aviso: " + lobby.AVISO_SIN_CIFRAR, 0.74, 16, max_lineas=2)
        self.t_cifrado.origin = (-0.5, 0.5)
        self.btn_ayuda = BotonSecundario("Ayuda: cortafuegos de macOS", al_clic=self.alternar_ayuda, ancho=0.44,
                                         alto=a_unidades(34), tamano_fuente_px=15, parent=self.raiz,
                                         position=(0.60, 0.395, -0.003))
        # La ayuda se abre como un cuadro sobre la tabla (no empuja nada)
        self.caja_ayuda = Entity(parent=self.raiz, enabled=False, z=-0.02)
        panel_tinta(self.caja_ayuda, 1.5, 0.17, estilo.COLOR_PANEL, estilo.RADIO_TARJETA_PX, position=(0, -0.145, 0))
        self.t_ayuda = crear_texto(self.caja_ayuda, " ", -0.70, -0.085, 18, estilo.COLOR_TEXTO, origen=(-0.5, 0.5))
        self.t_aviso = crear_texto(self.raiz, " ", -0.80, -0.365, 17, estilo.ESTADO_AVISO)
        self.btn_salir = BotonSecundario("Salir de la sala", al_clic=self.salir, ancho=0.40, alto=a_unidades(52),
                                         tamano_fuente_px=20, parent=self.raiz, position=(-0.55, -0.425, -0.003))
        self.btn_listo = BotonSecundario("Estoy listo", al_clic=self.alternar_listo, ancho=0.40, alto=a_unidades(52),
                                         tamano_fuente_px=22, parent=self.raiz, position=(0.0, -0.425, -0.003))
        self.btn_iniciar = BotonPrimario("Iniciar partida", al_clic=self.iniciar, ancho=0.56, alto=a_unidades(52),
                                         tamano_fuente_px=22, parent=self.raiz, position=(0.52, -0.425, -0.003))
        self.foco = FocoOnline(self._controles_activos, al_escape=self.salir, parent=self)

    # ------------------------------------------------------------------ foco
    def _controles_activos(self):
        lista = list(self.tarjetas.values())
        host = self.sesion is not None and self.sesion.es_anfitrion
        if host:
            lista += [self.btn_ver, self.btn_copiar, self.btn_ayuda]
        lista.append(self.btn_listo)
        if host:
            lista.append(self.btn_iniciar)
        lista.append(self.btn_salir)
        return lista

    # ------------------------------------------------------------------ ciclo de vida
    def al_entrar(self, **datos):
        self.sesion = datos.get("sesion")
        self.empezo = False
        self.codigo_visible = False
        self.ayuda_visible = False
        self._aviso_local = ""
        self.fondo.t = 0.0
        self.caja_ayuda.enabled = False
        host = bool(self.sesion and self.sesion.es_anfitrion)
        self.caja_codigo.enabled = True
        self.btn_ver.enabled = host
        self.btn_copiar.enabled = host
        self.btn_ayuda.enabled = host
        self.foco.reiniciar()
        self.refrescar()

    def al_salir(self):
        pass

    def update(self):
        if self.sesion is None or self.empezo:
            return
        cambio = self.sondear()
        self._t_refresco += 1 / 60
        if cambio or self._t_refresco >= REFRESCO_S:
            self._t_refresco = 0.0
            self.refrescar()

    # Drena de uno en uno: tras «inicio» no se toca nada más (es del juego). Devuelve True si algo cambió.
    def sondear(self):
        sesion = self.sesion
        modelo = sesion.modelo
        cambio = False
        for _ in range(64):
            eventos = sesion.cliente.sacar_eventos(1)
            if not eventos:
                break
            cambio = True
            resultado = modelo.aplicar(eventos[0])
            if resultado == "inicio":
                self._empezar()
                return True
            if resultado in ("cerrado", "rechazo"):
                motivo = (modelo.rechazo or {}).get("codigo") or modelo.motivo_cierre
                self._fallar(motivo)
                return True
        return cambio

    def _empezar(self):
        sesion = self.sesion
        modelo = sesion.modelo
        self.empezo = True
        info = {"tu_id": modelo.tu_id, "semilla": modelo.semilla, "sala": modelo.sala,
                "es_anfitrion": sesion.es_anfitrion, "anfitrion": sesion.anfitrion,
                "jugadores": [dict(j) for j in modelo.jugadores], "inicio": dict(modelo.inicio),
                "alias": sesion.alias, "destino": sesion.destino, "sesion": sesion}
        if self._al_empezar is not None:
            self._al_empezar(sesion.cliente, info)
        else:
            self._aviso_local = "¡Partida iniciada! (el cliente de juego aún no está conectado a esta sala)"
            self.refrescar()

    def _fallar(self, motivo):
        sesion, self.sesion = self.sesion, None
        if sesion is not None:
            sesion.cerrar()
        if self._al_fallo is not None:
            self._al_fallo(motivo, "unirse")

    # ------------------------------------------------------------------ acciones
    def elegir_rol(self, rol):
        modelo = self.sesion.modelo if self.sesion else None
        if modelo is None or not modelo.puede_elegir_rol(rol):
            return False
        return self.sesion.cliente.enviar_rol(rol)

    def alternar_listo(self):
        modelo = self.sesion.modelo if self.sesion else None
        if modelo is None or not modelo.puede_marcar_listo:
            return False
        return self.sesion.cliente.enviar_listo(not modelo.estoy_listo)

    def iniciar(self):
        modelo = self.sesion.modelo if self.sesion else None
        if modelo is None or not modelo.puede_iniciar:
            return False
        return self.sesion.cliente.enviar_iniciar()

    def alternar_codigo(self):
        self.codigo_visible = not self.codigo_visible
        self.refrescar()

    def alternar_ayuda(self):
        self.ayuda_visible = not self.ayuda_visible
        self.caja_ayuda.enabled = self.ayuda_visible
        if self.ayuda_visible:
            texto_envuelto(self.t_ayuda, lobby.AYUDA_CORTAFUEGOS, 1.40, 18)
            self.t_ayuda.origin = (-0.5, 0.5)

    def copiar_acceso(self):
        if self.sesion is None or not self.sesion.es_anfitrion:
            return False
        ok = self._copiar(f"{self.sesion.destino}  código {lobby.agrupar_codigo(self.sesion.codigo)}")
        fijar(self.t_copiado, "Copiado al portapapeles" if ok else "No se pudo copiar")
        return ok

    def salir(self):
        sesion, self.sesion = self.sesion, None
        if sesion is not None:
            sesion.cerrar()
        if self._al_salir is not None:
            self._al_salir()

    # ------------------------------------------------------------------ vista
    def refrescar(self):
        sesion = self.sesion
        if sesion is None:
            return
        m = sesion.modelo
        latencia = sesion.cliente.latencia_ms
        m.latencia_ms = latencia
        fijar(self.t_estado, m.texto_estado)
        for rol, tarjeta in self.tarjetas.items():
            dueno = m.rol_de(rol)
            tarjeta.marcar_tomado(None if dueno is None else dueno[:11].rstrip())
            tarjeta.fijar_habilitado(m.puede_elegir_rol(rol))
        for fila, casilla in zip(self.filas, m.casillas(latencia)):
            fila.pintar(casilla)
        host = sesion.es_anfitrion
        if host:
            fijar(self.t_destino, sesion.destino)
            ajustar_ancho(self.t_destino, 0.56, 23)
            fijar(self.t_codigo, "Código " + lobby.codigo_visible(sesion.codigo, self.codigo_visible))
            self.btn_ver.text = "Ocultar código" if self.codigo_visible else "Mostrar código"
        else:
            fijar(self.t_destino, f"Conectado a {sesion.destino}")
            ajustar_ancho(self.t_destino, 0.56, 23)
            fijar(self.t_codigo, "El anfitrión tiene el código")
        self.btn_listo.text = "No estoy listo" if m.estoy_listo else "Estoy listo"
        self.btn_listo.fijar_habilitado(m.puede_marcar_listo)
        self.btn_iniciar.enabled = host
        self.btn_iniciar.text = m.texto_iniciar
        self.btn_iniciar.fijar_habilitado(m.puede_iniciar)
        aviso = self._aviso_local or m.aviso
        fijar(self.t_aviso, aviso)
