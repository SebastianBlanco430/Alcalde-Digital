# Mundo ONLINE: IntegracionOnline engancha el FlujoEnLinea (frontend/online_flujo.py) a la EscenaMundo, con el mismo
# patrón que IntegracionVehiculos (frontend/vehiculo_mundo.py): la escena la crea solo si hay un FlujoEnLinea y le
# llama a actualizar(dt) en su update(). Con ONLINE=False ni este módulo ni backend.red se importan.
#
# Qué hace cada frame:
#   - Jugadores REMOTOS: usan la misma clase de personaje que los locales (EscenaMundo ya crea un avatar por
#     jugador de la sesión). Su posición / rumbo / altura salen de la muestra interpolada (retardo 100 ms,
#     backend.red.interpolacion_calculos) que ya calcula FlujoEnLinea.avanzar(); la animación se DERIVA de la
#     velocidad (PersonajeModelo.update -> modelo_calculos.clip_para_velocidad) y de las banderas (en el aire,
#     escalera). Bandera «dentro»: se oculta. Desconectado: translúcido, quieto y con «(ausente)» en la etiqueta.
#     Sin colisión entre jugadores (no se añade ninguna).
#   - Altas y bajas en vivo: si cambia el roster (flujo.sesion es un objeto nuevo) se crean / destruyen los avatares
#     que faltan o sobran sin tocar al resto. Si el jugador local está dentro de un edificio, la escena está
#     desactivada y esto se hace al volver (hook en EscenaMundo.al_entrar): así no hay KeyError en refrescar().
#   - Corrección del anfitrión al jugador LOCAL: pequeña (<= 1 m) = se difumina en ~0,12 s; grande = salto brusco
#     (se reinicia el estado vertical del controlador). Con un vehículo montado todavía no se aplica (T9).
#   - HUD en línea (frontend/online_hud.py): ping con texto, avisos, saludos rápidos (G), fin de partida y sala cerrada.
#
# VEHÍCULOS (T9): con online_config.VEHICULOS_ONLINE se crea frontend/online_vehiculos.VehiculosOnline, que envuelve la
# IntegracionVehiculos local (montar pide permiso al anfitrión, remotos montados se dibujan como vehículo con piloto,
# corrección suave al que conduce). Sin la bandera, un remoto con la bandera «vehículo» se dibuja como peatón
# deslizándose a su velocidad, como antes.

import math
import time as time_real

from ursina import Entity, time

from backend.logica.roles import ROLES
from backend.red.saneado import sanear_texto_visible
from frontend import online_config
from frontend import online_mundo_calculos as omc
from frontend.componentes import destruir_arbol
from frontend.niebla import activar_niebla
from frontend.online_hud import HudOnline
from frontend.personaje_modelo import crear_personaje

TECLA_SALUDOS = "g"
TECLAS_SALUDO = {str(i + 1): i for i in range(len(omc.SALUDOS))}


# Estado de dibujo de un remoto entre frames.
class _Dibujo:

    def __init__(self):
        self.y_previa = None
        self.vy = 0.0
        self.ausente = None          # None = aún no aplicado
        self.visible = None


# Entidad auxiliar hija de la escena: se crea DESPUÉS del controlador, así que su update() corre tras el del
# controlador (Ursina recorre las entidades por orden de creación) y puede sumar el difuminado de la corrección
# sobre la posición que el controlador acaba de fijar. También recibe el teclado (saludos).
class _Auxiliar(Entity):

    def __init__(self, integracion, **opciones):
        super().__init__(**opciones)
        self._integracion = integracion

    def update(self):
        self._integracion.despues_del_controlador(time.dt)

    def input(self, key):
        self._integracion.tecla(key)


class IntegracionOnline:

    # escena: EscenaMundo. obtener_bucle: callable() -> BucleRed | None (por defecto, el bucle global).
    # avanzar_flujo: llamar a flujo.avanzar() desde aquí (solo si no hay BucleRed; los scripts / tests).
    def __init__(self, escena, obtener_bucle=None, reloj=None, avanzar_flujo=False):
        self.escena = escena
        self.flujo = escena.flujo
        if obtener_bucle is None:
            from frontend import online_bucle
            obtener_bucle = online_bucle.bucle_actual
        self._obtener_bucle = obtener_bucle
        self._avanzar_flujo = avanzar_flujo
        self._reloj = reloj if reloj is not None else time_real.monotonic
        self.avisos = omc.PlanificadorAvisos(self._reloj)
        self.hud = HudOnline(escena.hud, al_menu=escena._ir_al_menu)
        self.suavizado = omc.SuavizadoCorreccion()
        self._dibujos = {}                 # id remoto -> _Dibujo
        self._conectados = {}              # id remoto -> bool (para avisar de cortes y regresos)
        self._nombres = None               # nombres vistos en el último roster
        self._n_ind_visto = None
        self._saludo_visto = None
        self._ultimo_saludo_propio = -1e9
        self._reconectando_desde = None
        self._terminada_vista = False
        self._perdida = False
        self._activa = True
        self._visual_local = None          # (x, z) con que se dibujó el avatar local en el frame anterior
        # Ganchos en la escena (se quitan en cerrar()).
        escena.sanear_nombre = sanear_texto_visible
        escena.texto_turno_fn = self.texto_turno
        self._aux = _Auxiliar(self, parent=escena)
        self.vehiculos_online = None       # T9: VehiculosOnline (solo con VEHICULOS_ONLINE y vehículos en la escena)
        if online_config.VEHICULOS_ONLINE and getattr(escena, "vehiculos", None) is not None:
            from frontend.online_vehiculos import VehiculosOnline
            self.vehiculos_online = VehiculosOnline(escena, self.flujo, avisar=self.avisos.empujar,
                                                    obtener_bucle=self._obtener_bucle)

    # -- Ganchos de la escena --

    # Texto del panel de turno: no hay turnos en línea.
    def texto_turno(self, activo):
        sesion = self.flujo.sesion
        n = len(sesion.jugadores()) if sesion is not None else 1
        return omc.texto_turno_online(activo.nombre, ROLES[activo.rol].nombre, n)

    # ¿Hay que soltar el ratón / congelar los controles? (sala cerrada: se muestra la pantalla de error).
    def bloquea_controles(self):
        return self._perdida

    # Quita los ganchos y el HUD en línea (cambio de partida o vuelta al hot-seat).
    def cerrar(self):
        if not self._activa:
            return
        self._activa = False
        escena = self.escena
        if escena.sanear_nombre is sanear_texto_visible:
            escena.sanear_nombre = None
        if escena.texto_turno_fn == self.texto_turno:
            escena.texto_turno_fn = None
        self.suavizado.cancelar()
        if self.vehiculos_online is not None:
            self.vehiculos_online.cerrar()
            self.vehiculos_online = None
        from ursina import destroy
        destroy(self._aux)
        destroy(self.hud)

    def al_salir(self):
        self.hud.mostrar_saludos(False)

    # -- Altas y bajas --

    # Si el roster cambió (flujo.sesion nueva), crea / destruye los avatares que faltan o sobran. Devuelve True si hubo
    # cambios. No hace nada antes de la primera construcción de la escena (esa la hace _reconstruir_personajes).
    def sincronizar_roster(self):
        escena, flujo = self.escena, self.flujo
        sesion = flujo.sesion
        if sesion is None or escena._sesion is None or sesion is escena._sesion:
            return False
        actuales = {j.nombre: j for j in sesion.jugadores()}
        anteriores = set(escena.avatares)
        for nombre in [n for n in escena.avatares if n not in actuales]:
            destruir_arbol(escena.avatares.pop(nombre))
            self.avisos.empujar(f"{sanear_texto_visible(nombre)} salió de la sala")
        for nombre, jugador in actuales.items():
            if nombre in escena.avatares:
                continue
            avatar = crear_personaje(sanear_texto_visible(nombre), jugador.rol, ROLES[jugador.rol].color, parent=escena)
            avatar.suelo = escena._mundo.altura
            escena.avatares[nombre] = avatar
            if anteriores:
                self.avisos.empujar(f"{sanear_texto_visible(nombre)} se unió a la sala")
        escena._sesion = sesion
        escena.camara.ignorar = list(escena.avatares.values())
        activar_niebla()                       # los Personaje recién creados no la tenían
        self._dibujos = {i: d for i, d in self._dibujos.items() if flujo.jugador_por_id(i) is not None}
        if not escena._cinematica:
            escena.refrescar()
        return True

    # -- Frame --

    def actualizar(self, dt):
        flujo, escena = self.flujo, self.escena
        if flujo is None or escena._sesion is None or not self._activa:
            return
        if self._avanzar_flujo or self._obtener_bucle() is None:
            flujo.avanzar()          # sin BucleRed (scripts / pruebas) alguien tiene que interpolar
        self.sincronizar_roster()
        if self.vehiculos_online is not None:
            self.vehiculos_online.actualizar(dt)
        self._dibujar_remotos(dt)
        self._aplicar_correccion()
        self._estado_de_red(dt)

    # Tras el controlador y la escena (la entidad auxiliar se actualiza la última): suma el difuminado de la corrección
    # sobre la posición del avatar local y recuerda dónde se vio por última vez (base para medir la próxima corrección:
    # al llegar a escena.update() el controlador ya colocó el avatar en la posición corregida).
    def despues_del_controlador(self, dt):
        avatar = self.escena.avatar_de(self.flujo.jugador) if self.flujo is not None else None
        if avatar is None:
            return
        if self.suavizado.activo:
            ox, oz = self.suavizado.avanzar(dt)
            avatar.x += ox
            avatar.z += oz
        self._visual_local = (avatar.x, avatar.z)

    # -- Remotos --

    def _suelo(self, x, z):
        mundo = self.escena._mundo
        funcion = getattr(mundo, "altura_con_escaleras", None) or getattr(mundo, "altura", None)
        return funcion(x, z) if funcion is not None else None

    def _dibujar_remotos(self, dt):
        flujo, escena = self.flujo, self.escena
        for remoto in flujo.jugadores_remotos():
            avatar = escena.avatares.get(remoto.nombre)
            if avatar is None:
                continue
            if self.vehiculos_online is not None and self.vehiculos_online.dibuja_a(remoto.id):
                self._avisar_conexion(remoto)      # va montado: lo dibuja VehiculosOnline (vehículo con piloto)
                continue
            muestra = flujo.muestra_de(remoto.id)
            hubo_tp = flujo.tomar_teletransporte(remoto.id)
            dibujo = self._dibujos.setdefault(remoto.id, _Dibujo())
            self._avisar_conexion(remoto)
            if muestra is None:                 # aún sin snapshots: en su punto de salida
                avatar.colocar(remoto.x, remoto.z)
                self._ausente(avatar, remoto, dibujo, not remoto.conectado)
                continue
            if hubo_tp:
                dibujo.y_previa, dibujo.vy = None, 0.0
            self._dibujar(avatar, remoto, omc.estado_visual(muestra, remoto.conectado), dibujo, dt)

    def _dibujar(self, avatar, remoto, v, dibujo, dt):
        if dibujo.visible != v.visible:
            dibujo.visible = v.visible
            avatar.enabled = v.visible          # «dentro» de un edificio: no se ve en la calle
        if not v.visible:
            dibujo.y_previa = None
            return
        avatar.colocar(v.x, v.z)
        if abs(v.y - avatar.y) > 1e-6:
            avatar.y = v.y                      # como el salto / los peldaños del controlador local
        fijar_rumbo = getattr(avatar, "fijar_rumbo", None)
        if callable(fijar_rumbo):
            fijar_rumbo(v.rumbo)
        fijar_velocidad = getattr(avatar, "fijar_velocidad", None)
        if callable(fijar_velocidad):
            fijar_velocidad(v.velocidad)
        dibujo.vy = omc.velocidad_vertical(dibujo.y_previa, v.y, dt, anterior=dibujo.vy)
        dibujo.y_previa = v.y
        informar_aire = getattr(avatar, "fijar_estado_aire", None)
        if callable(informar_aire):
            informar_aire(v.en_aire, dibujo.vy if v.en_aire else 0.0)
        informar_escalera = getattr(avatar, "fijar_subiendo_escalera", None)
        if callable(informar_escalera):
            informar_escalera(v.escalera)
        # Sombra y aro se quedan en el suelo mientras vuela (mismo criterio que el controlador local).
        poner_sombra = getattr(self.escena.controlador, "_poner_sombra_en_el_suelo", None)
        if callable(poner_sombra):
            poner_sombra(avatar, omc.elevacion_sobre_suelo(v.y, self._suelo(v.x, v.z), v.en_aire))
        self._ausente(avatar, remoto, dibujo, v.ausente)

    # Aspecto «ausente»: translúcido + «(ausente)» en la etiqueta; al volver se restaura.
    def _ausente(self, avatar, remoto, dibujo, ausente):
        if dibujo.ausente == ausente:
            return
        dibujo.ausente = ausente
        cuerpo = getattr(avatar, "cuerpo", None)
        if cuerpo is not None:
            if ausente:
                cuerpo.setTransparency(1)                          # TransparencyAttrib.M_alpha
                cuerpo.setColorScale(1, 1, 1, omc.ALFA_AUSENTE)
            else:
                cuerpo.clearColorScale()
                cuerpo.clearTransparency()
        etiqueta = getattr(avatar, "etiqueta", None)
        if etiqueta is not None:
            etiqueta.text = omc.texto_etiqueta(remoto.nombre, ausente)
        if ausente:
            fijar_velocidad = getattr(avatar, "fijar_velocidad", None)
            if callable(fijar_velocidad):
                fijar_velocidad(0.0)

    def _avisar_conexion(self, remoto):
        antes = self._conectados.get(remoto.id)
        self._conectados[remoto.id] = remoto.conectado
        if antes is None or antes == remoto.conectado:
            return
        nombre = sanear_texto_visible(remoto.nombre)
        self.avisos.empujar(f"{nombre} volvió" if remoto.conectado else f"{nombre} perdió la conexión")

    # -- Corrección al jugador local --

    def _aplicar_correccion(self):
        flujo, escena = self.flujo, self.escena
        correccion = flujo.tomar_correccion()
        if correccion is None:
            return
        x, z, y = correccion
        vehiculos = getattr(escena, "vehiculos", None)
        if vehiculos is not None and getattr(vehiculos, "conduciendo", False):
            if self.vehiculos_online is not None:
                self.vehiculos_online.recibir_correccion(x, z)   # T9: se difumina, sin bajarlo del vehículo
            return
        jugador = flujo.jugador
        avatar = escena.avatar_de(jugador)
        if avatar is None:
            return
        vx, vz = self._visual_local if self._visual_local is not None else (avatar.x, avatar.z)
        distancia = math.hypot(vx - x, vz - z)
        clase = omc.clasificar_correccion(distancia)
        if clase == omc.CORRECCION_NULA:
            return
        if clase == omc.CORRECCION_SUAVE:
            self.suavizado.iniciar(vx - x, vz - z)   # el controlador ya trabaja con la posición buena
            return
        self.suavizado.cancelar()
        reiniciar = getattr(escena.controlador, "_reiniciar_vertical", None)
        if callable(reiniciar):
            reiniciar(jugador)
        avatar.colocar(x, z)
        avatar.y = y
        colocar_ya = getattr(escena.camara, "colocar_ya", None)
        if callable(colocar_ya):
            colocar_ya()

    # -- Red, avisos y HUD --

    def _estado_de_red(self, dt):
        flujo, escena, hud = self.flujo, self.escena, self.hud
        ahora = self._reloj()
        terminada = flujo.partida_terminada()

        # Sala cerrada / conexión perdida (si la partida ya terminó, el panel de fin manda).
        cerrada = bool(flujo.sala_cerrada or flujo.cerrado_motivo) and not terminada
        if cerrada and not self._perdida:
            self._perdida = True
            hud.mostrar_cierre(flujo.cerrado_motivo or "sala_cerrada")
            escena._sincronizar_raton()
        elif not cerrada and self._perdida:
            self._perdida = False
            hud.ocultar_cierre()
            escena._sincronizar_raton()

        # Condición de red: «Reconectando… (n s)» o «Conexión inestable».
        if flujo.reconectando:
            if self._reconectando_desde is None:
                self._reconectando_desde = ahora
            self.avisos.condicion(omc.texto_reconectando(ahora - self._reconectando_desde))
        else:
            if self._reconectando_desde is not None:
                self._reconectando_desde = None
                self.avisos.empujar("Reconectado")
            self.avisos.condicion(omc.TEXTO_INESTABLE if self._inestable() else None)

        # Lo que decidieron los demás.
        ind = flujo.ultimo_ind
        if ind is not None and ind["n"] != self._n_ind_visto:
            if self._n_ind_visto is not None and not ind["propio"]:
                autor = flujo.jugador_por_id(ind["autor"])
                self.avisos.empujar(omc.texto_decision(autor.nombre if autor else "Alguien", ind["deltas"]))
            self._n_ind_visto = ind["n"]
        saludo = flujo.ultimo_saludo
        if saludo is not None and saludo is not self._saludo_visto:
            self._saludo_visto = saludo
            emisor = flujo.jugador_por_id(saludo[0])
            if emisor is not None and saludo[0] != flujo.tu_id:
                self.avisos.empujar(omc.texto_saludo(emisor.nombre, saludo[1]), omc.DURACION_SALUDO)

        # Fin de partida: se refresca la escena (panel de indicadores) y se muestra el resumen del anfitrión.
        if terminada != self._terminada_vista:
            self._terminada_vista = terminada
            hud.fijar_resumen(flujo.resumen_fin if terminada else None)
            if not escena._cinematica:
                escena.refrescar()
            escena._sincronizar_raton()

        self.avisos.persistente(
            omc.TEXTO_ESPERANDO if omc.esperando_companeros(flujo.hay_mision_activa(), terminada, self._perdida) else None)

        hud.fijar_ping(flujo.latencia_ms, visible=not self._perdida)
        hud.fijar_aviso(self.avisos.actual())
        hud.avanzar(dt)

    def _inestable(self):
        bucle = self._obtener_bucle()
        if bucle is not None:
            return bucle.aviso() == omc.TEXTO_INESTABLE
        silencio = getattr(self.flujo.cliente, "silencio", None)
        return bool(callable(silencio) and silencio() > 0.5)

    # -- Teclado: saludos rápidos --

    def tecla(self, key):
        flujo, escena = self.flujo, self.escena
        if flujo is None or not self._activa or escena.controles_bloqueados() or flujo.partida_terminada():
            if self.hud.saludos_abierto:
                self.hud.mostrar_saludos(False)
            return
        if key == TECLA_SALUDOS:
            self.hud.mostrar_saludos(not self.hud.saludos_abierto)
        elif self.hud.saludos_abierto:
            if key == "escape":
                self.hud.mostrar_saludos(False)
            elif key in TECLAS_SALUDO:
                self.enviar_saludo(TECLAS_SALUDO[key])
                self.hud.mostrar_saludos(False)

    def enviar_saludo(self, indice):
        ahora = self._reloj()
        if ahora - self._ultimo_saludo_propio < omc.COOLDOWN_SALUDO:
            return False
        self._ultimo_saludo_propio = ahora
        enviado = self.flujo.cliente.enviar_saludo(indice)
        if enviado:
            self.avisos.empujar(omc.texto_saludo("Tú", indice), omc.DURACION_SALUDO)
        return bool(enviado)
