# Enganches del audio con el juego, SIN tocar las escenas: este módulo OBSERVA el estado (escena activa, avatar,
# controlador, vehículos, teléfono, misiones, ratón) una vez por frame y dispara los sonidos. Así las escenas y
# el controlador no cambian (solo se leen atributos con getattr; ningún campo nuevo en ellos).
#
# Cableado (una línea en main.py, tras registrar las escenas):  audio_enganches.instalar(gestor)
#
# Qué suena y cuándo:
#   - Música por escena: inicio / selección = musica_ambiente (fuerte); mundo = musica_ambiente (baja) + ambiente_favela;
#     interior = musica_interior (la misma, apagada); minijuego = musica_interior. Cambia con fundido cruzado.
#   - Pasos: por DISTANCIA REAL recorrida (velocidad del avatar), cada ~0,8 m caminando o ~1,3 m corriendo; arena en
#     calles/laderas y concreto en plazas y escaleras. No suenan en el aire, parado, con pausa ni en cinemática.
#   - Salto / aterrizaje: el controlador solo se lee (estado vertical `en_aire`).
#   - Vehículos: moto = motor_moto con pitch y volumen por velocidad; bici = bici_cadena (solo rodando) y timbre al montar.
#   - Mensaje de Civitas: sube el número de mensajes sin leer del teléfono del jugador activo.
#   - Fin de misión: sube la lista de misiones completadas; éxito si los deltas del resultado no suman negativo.
#   - Interfaz: hover (al entrar el ratón en un botón) y clic (clic izquierdo sobre un botón habilitado).
#   - Ajustes: se suscribe al almacén backend.logica.ajustes y aplica volúmenes/silencio/dispositivo al instante.

from frontend import audio as audio_modulo
from frontend import audio_calculos as ac
from frontend.conexion_flujo import INICIO, INTERIOR, JUEGO, MUNDO, SELECCION_ROL

# escena -> (música, volumen, ambiente, volumen)
PERFIL_ESCENA = {
    INICIO: ("musica_ambiente", 0.9, None, 0.0),
    SELECCION_ROL: ("musica_ambiente", 0.7, None, 0.0),
    MUNDO: ("musica_ambiente", 0.45, "ambiente_favela", 0.8),
    INTERIOR: ("musica_interior", 0.7, None, 0.0),
    JUEGO: ("musica_interior", 0.6, None, 0.0),
}
VARIACION_PITCH = (1.0, 1.05, 0.96, 1.03, 0.93, 1.07)       # los pasos y clics no suenan idénticos
ESPERA_HOVER = 0.06          # s mínimos entre dos «hover»
FUNDIDO_MUSICA = 1.4
BICI_VMAX_DEFECTO = 8.0
MOTO_VMAX_DEFECTO = 16.0


class EnganchesAudio:

    # gestor: GestorEscenas (nombre_actual / escena_actual). audio: GestorAudio. raton: objeto con
    # `hovered_entity` (ursina.mouse); None = sin hover/clic de interfaz (pruebas).
    def __init__(self, gestor, audio=None, raton=None):
        self.gestor = gestor
        self.audio = audio if audio is not None else audio_modulo.obtener()
        self.raton = raton
        self._escena = None
        self._pasos = ac.ContadorPasos()
        self._salto = ac.DetectorSalto()
        self._sesion = None
        self._no_leidos = {}
        self._completadas = None
        self._conduciendo = None          # tipo de vehículo que se conduce (o None)
        self._hover = None
        self._tiempo = 0.0
        self._ultimo_hover = -1.0
        self._indice_pitch = 0
        self._ajustes = None
        self._reloj = None

    # -- Un frame --

    def actualizar(self, dt):
        try:
            self._tiempo += dt
            self.audio.actualizar(dt)
            nombre = self.gestor.nombre_actual()
            if nombre != self._escena:
                self._cambio_de_escena(nombre)
            self._interfaz()
            if nombre == MUNDO:
                self._mundo(dt)
        except Exception as error:         # el audio nunca debe tirar el juego
            audio_modulo._avisar_una_vez("enganches", f"error en los enganches de audio ({error}).")

    # -- Música y ambiente --

    def _cambio_de_escena(self, nombre):
        anterior = self._escena
        self._escena = nombre
        musica, vol_musica, ambiente, vol_ambiente = PERFIL_ESCENA.get(nombre, (None, 0.0, None, 0.0))
        self.audio.musica(musica, volumen=vol_musica, fundido=FUNDIDO_MUSICA)
        for bucle in ("ambiente_favela",):
            if bucle == ambiente:
                self.audio.bucle(bucle, vol_ambiente, 1.0, fundido=2.0)
            else:
                self.audio.parar_bucle(bucle, fundido=1.0)
        if anterior == MUNDO:
            self._soltar_movimiento()

    def _soltar_movimiento(self):
        self.audio.parar_bucle("motor_moto", 0.3)
        self.audio.parar_bucle("bici_cadena", 0.3)
        self._conduciendo = None
        self._pasos.reiniciar()
        self._salto = ac.DetectorSalto()

    # -- Interfaz --

    @staticmethod
    def es_boton(entidad):
        # Botón de interfaz: tiene on_click invocable y no está inhabilitado.
        if entidad is None or not callable(getattr(entidad, "on_click", None)):
            return False
        habilitado = getattr(entidad, "esta_habilitado", None)
        if callable(habilitado):
            try:
                return bool(habilitado())
            except Exception:
                return True
        return True

    def _interfaz(self):
        if self.raton is None:
            return
        actual = getattr(self.raton, "hovered_entity", None)
        if actual is not self._hover:
            self._hover = actual
            if self.es_boton(actual) and self._tiempo - self._ultimo_hover > ESPERA_HOVER:
                self._ultimo_hover = self._tiempo
                self.audio.efecto("hover_ui", 0.8, self._variar())

    # Llamado con cada tecla/botón de Ursina (input global): el clic izquierdo sobre un botón suena.
    def tecla(self, tecla):
        if tecla == "left mouse down" and self.raton is not None:
            if self.es_boton(getattr(self.raton, "hovered_entity", None)):
                self.audio.efecto("clic_ui", 1.0, self._variar())

    def _variar(self):
        self._indice_pitch = (self._indice_pitch + 1) % len(VARIACION_PITCH)
        return VARIACION_PITCH[self._indice_pitch]

    # -- Mundo --

    def _mundo(self, dt):
        escena = self.gestor.escena_actual()
        flujo = getattr(escena, "flujo", None)
        if flujo is None:
            return
        if flujo.sesion is not self._sesion:            # partida nueva: se reinician los contadores
            self._sesion = flujo.sesion
            self._no_leidos = {}
            self._completadas = None
        jugador = flujo.jugador_activo()
        if jugador is None:
            return
        self._mensajes(jugador)
        self._misiones(flujo)
        controlador = getattr(escena, "controlador", None)
        if controlador is None:
            return
        pausa = bool(getattr(escena, "en_pausa", False))
        if getattr(controlador, "modo_vehiculo", None) is not None:
            self._pasos.reiniciar()
            self._vehiculo(escena, pausa)
        else:
            if self._conduciendo is not None:
                self._soltar_movimiento()
            self._a_pie(escena, controlador, jugador, dt)

    def _mensajes(self, jugador):
        telefono = getattr(jugador, "telefono", None)
        if telefono is None:
            return
        no_leidos = telefono.no_leidos()
        antes = self._no_leidos.get(jugador.nombre, 0)
        self._no_leidos[jugador.nombre] = no_leidos
        if no_leidos > antes:
            self.audio.efecto("mensaje_civitas", 0.9)

    def _misiones(self, flujo):
        sistema = getattr(flujo, "_sistema", None)
        if sistema is None:
            return
        cantidad = len(sistema.completadas())
        if self._completadas is None:
            self._completadas = cantidad
            return
        if cantidad > self._completadas:
            self._completadas = cantidad
            self.audio.efecto("mision_exito" if self._fue_exito(sistema.resultado_ultimo()) else "mision_fallo", 0.9)

    # Heurística: éxito si los deltas de los indicadores no suman negativo (sin deltas = éxito).
    @staticmethod
    def _fue_exito(resultado):
        try:
            deltas = resultado.get("deltas", {}) if isinstance(resultado, dict) else {}
            return sum(float(v) for v in deltas.values()) >= 0
        except (TypeError, ValueError):
            return True

    def _a_pie(self, escena, controlador, jugador, dt):
        avatar = escena.avatar_de(jugador)
        if avatar is None:
            return
        velocidad = float(getattr(avatar, "velocidad", 0.0) or 0.0)
        estado = getattr(controlador, "_verticales", {}).get(jugador.nombre)
        en_aire = bool(getattr(estado, "en_aire", False))
        evento = self._salto.actualizar(en_aire, dt)
        if evento == "salto":
            self.audio.efecto("salto", 0.8, self._variar())
        elif evento == "aterrizaje":
            self.audio.efecto("aterrizaje", 0.9)
        if getattr(escena, "en_pausa", False):
            return
        if self._pasos.avanzar(velocidad, dt, en_aire):
            superficie = self._superficie(escena, jugador)
            variante = 1 + self._pasos.lado
            self.audio.efecto(f"paso_{superficie}_{variante}", ac.volumen_paso(velocidad), self._variar())

    @staticmethod
    def _superficie(escena, jugador):
        # concreto en plazas y escaleras; arena en el resto (calles de tierra y laderas)
        mundo = getattr(escena, "_mundo", None)
        try:
            if mundo is not None:
                perfil = getattr(mundo, "perfil_escalera_en", None)
                if perfil is not None and perfil(jugador.x, jugador.z) is not None:
                    return "concreto"
                if mundo.lugar_en_plaza(jugador.x, jugador.z):
                    return "concreto"
        except Exception:
            pass
        return "arena"

    def _vehiculo(self, escena, pausa):
        integracion = getattr(escena, "vehiculos", None)
        mundo_v = getattr(integracion, "mundo", None)
        conducido = getattr(mundo_v, "conducido", None)
        if conducido is None:
            return
        tipo = getattr(getattr(conducido, "perfil", None), "tipo", None) or getattr(conducido, "tipo", "moto")
        velocidad = abs(float(mundo_v.velocidad()))
        vmax = float(getattr(getattr(conducido, "perfil", None), "vturbo", 0.0) or 0.0)
        if tipo == "bicicleta":
            vmax = vmax or BICI_VMAX_DEFECTO
            if self._conduciendo != tipo:
                self.audio.efecto("bici_timbre", 0.7)
            volumen = 0.0 if pausa else ac.volumen_cadena(velocidad, vmax)
            self.audio.bucle("bici_cadena", volumen, ac.pitch_cadena(velocidad, vmax), fundido=0.3)
            self.audio.ajustar_bucle("bici_cadena", volumen, ac.pitch_cadena(velocidad, vmax))
        else:
            vmax = vmax or MOTO_VMAX_DEFECTO
            volumen = 0.0 if pausa else ac.volumen_motor(velocidad, vmax)
            self.audio.bucle("motor_moto", volumen, ac.pitch_motor(velocidad, vmax), fundido=0.4)
            self.audio.ajustar_bucle("motor_moto", volumen, ac.pitch_motor(velocidad, vmax))
        self._conduciendo = tipo

    # -- Ajustes --

    def suscribir_ajustes(self, almacen=None):
        # Aplica los ajustes guardados ya y cada cambio posterior. Nunca lanza.
        try:
            if almacen is None:
                from backend.logica import ajustes as modulo_ajustes
                almacen = modulo_ajustes.obtener()
            almacen.suscribir(lambda actuales, claves: self.audio.aplicar_ajustes(actuales))
            self._ajustes = almacen
        except Exception as error:
            audio_modulo._avisar_una_vez("ajustes_enganche", f"sin enlace con los ajustes ({error}).")


# Crea el observador, lo engancha al bucle de Ursina (una Entity que llama a actualizar() cada frame y recibe
# las teclas) y suscribe los ajustes. Devuelve el EnganchesAudio (con `.reloj` = la Entity). Nunca lanza.
# Entrega a la pantalla de Ajustes la lista de salidas de audio y el botón «Probar sonido».
# Falla en silencio: sin pantalla de Ajustes o sin dispositivos, el audio sigue funcionando.
def _conectar_ajustes(audio):
    try:
        from frontend.escenas import escena_ajustes
        escena_ajustes.registrar_dispositivos(list(audio.listar_dispositivos()))
        escena_ajustes.registrar_prueba_sonido(lambda: audio.efecto("mision_exito", 0.8))
    except Exception as error:
        audio_modulo._avisar_una_vez("ajustes", f"no se pudo conectar Ajustes con el audio ({error}).")


def instalar(gestor, audio=None, suscribir_ajustes=True):
    from ursina import Entity, mouse, time

    motor = EnganchesAudio(gestor, audio=audio, raton=mouse)

    class _Reloj(Entity):
        def update(self):
            motor.actualizar(time.dt)

        def input(self, key):
            motor.tecla(key)

    try:
        motor.reloj = _Reloj()
        if suscribir_ajustes:
            motor.suscribir_ajustes()
        motor.audio.precargar()
        _conectar_ajustes(motor.audio)
    except Exception as error:
        audio_modulo._avisar_una_vez("instalar", f"no se pudo instalar el audio ({error}).")
    return motor
