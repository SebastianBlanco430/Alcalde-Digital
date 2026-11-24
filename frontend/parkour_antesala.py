# Antesala del PARKOUR (Ursina): el «terminal del servidor». Un cuartito oscuro con la estética del sector (paredes casi
# negras, zócalo cian y friso magenta de neón), una mesa con monitor encendido (rótulo del servidor + nombre del nivel),
# teclado, la silla de frontend/cinematica_silla.crear_silla y el protagonista del jugador activo. Ahí se reproduce
# cinematica_silla.entrar_a_pantalla (llega, saca la silla, se sienta y la cámara ENTRA en la pantalla con el glitch) antes
# del nivel, y salir_de_pantalla + levantarse_de al volver del servidor.
#
# La usa frontend/escenas/escena_parkour.py (dueña del estado: cámara, HUD, simulación). Esta clase solo dibuja y lanza
# las secuencias (auto=False: la escena las avanza en su update). Se construye UNA vez (bajo el fundido de la primera
# entrada) y se reutiliza; el personaje se rehace solo si cambia el jugador/rol. Geometría y tomas: parkour_antesala_calculos.
#
# Luces: una ambiental y una direccional PROPIAS (sin sombras), encendidas solo mientras se ve la antesala (el parkour es
# neón sin luz: no se le cambia nada). Nada de esto se ve con ALCALDE_ANIM_SILLA=0 (la escena ni la construye).

from ursina import Entity, Text, camera, color
from ursina.lights import AmbientLight, DirectionalLight
from ursina.shaders import lit_with_shadows_shader

from frontend import parkour_antesala_calculos as pa
from frontend import tipografia
from frontend.componentes import destruir_arbol, rgb
from frontend.piezas import encender_luz, pieza, silenciar

CLAVE = "parkour"                 # «ya la vio» (versión rápida desde la 2.ª vez; la salida recuerda «parkour_salida» sola)
FONDO_VENTANA = (6, 6, 14)        # color de la ventana mientras se ve la antesala (el cuarto es cerrado)


def _modulo():
    """(cinematica_silla, Silla, Mesa). Lanza si el módulo de la silla no está (la escena cae al camino de hoy)."""
    from frontend import cinematica_silla as cs
    from frontend.cinematica_silla_calculos import Mesa, Silla
    return cs, Silla, Mesa


def _personaje(jugador, parent):
    """Mismo criterio que minijuegos_3d/sets._personaje: el protagonista del rol, sin aro ni nombre, animado por código."""
    from backend.logica.roles import ROLES
    from frontend.personaje_modelo import crear_personaje
    rol = getattr(jugador, "rol", None) or "ciudadano"
    nombre = getattr(jugador, "nombre", None) or "Jugador"
    color_rol = ROLES[rol].color if rol in ROLES else (200, 200, 200)
    p = crear_personaje(nombre, rol, color_rol, parent=parent)
    p.automatico = False
    for parte in ("etiqueta", "aro"):
        if getattr(p, parte, None) is not None:
            getattr(p, parte).enabled = False
    return p


class Antesala(Entity):

    def __init__(self, **opciones):
        super().__init__(**opciones)           # cuelga de la escena del parkour (en el origen, sin rotar)
        cs, Silla, Mesa = _modulo()
        self.silla = Silla(**pa.datos_silla())
        self.mesa = Mesa(**pa.datos_mesa())
        self.pantalla = pa.pantalla()
        self.sec = None                        # Secuencia en curso (o la última, que sostiene la pose sentada)
        self.personaje = None
        self._clave_personaje = None
        self._al_terminar_salida = None
        self.cuarto = Entity(parent=self, position=pa.ORIGEN)
        self._construir_cuarto()
        self._construir_monitor()
        self.ent_silla = cs.crear_silla(self, self.silla)
        self.luces = self._construir_luces()
        self.enabled = False

    # -- Construcción (una vez) --

    def _construir_cuarto(self):
        con_luz = Entity(parent=self.cuarto, shader=lit_with_shadows_shader)
        neon = Entity(parent=self.cuarto)
        for nombre, centro, escala, tono, propia_luz in pa.piezas_cuarto() + pa.piezas_mesa():
            if propia_luz:
                Entity(parent=neon, model="cube", position=centro, scale=escala, color=rgb(tono))
            else:
                pieza(parent=con_luz, model="cube", position=centro, scale=escala, color=rgb(tono))
        con_luz.combine()
        neon.combine()
        neon.setLightOff()
        silenciar(con_luz)
        silenciar(neon)

    def _construir_monitor(self):
        cx, cy, cz = pa.PANTALLA_CENTRO
        self.pantalla_quad = Entity(parent=self.cuarto, model="quad", position=(cx, cy, cz - 0.001),
                                    scale=(pa.PANTALLA_ANCHO, pa.PANTALLA_ALTO), color=rgb(pa.PANTALLA_FONDO))
        self.pantalla_quad.setLightOff()
        # Contenido de la pantalla (sin escala no uniforme: los textos cuelgan de un nodo propio).
        contenido = Entity(parent=self.cuarto, position=(cx, cy, cz - 0.004))
        mx, my = pa.PANTALLA_ANCHO / 2, pa.PANTALLA_ALTO / 2       # medio ancho y medio alto: todo queda dentro
        for k in range(5):                     # líneas de «código» tenues, alineadas a la izquierda
            ancho = 0.07 + 0.035 * ((k * 7) % 4)
            Entity(parent=contenido, model="quad", position=(-mx + 0.03 + 0.012 * (k % 2) + ancho / 2, -0.035 - 0.015 * k, 0),
                   scale=(ancho, 0.005), color=rgb((30, 90, 120)))
        Entity(parent=contenido, model="quad", position=(0, my - 0.042, 0), scale=(pa.PANTALLA_ANCHO * 0.9, 0.003),
               color=rgb(pa.CIAN))
        self.texto_cabecera = Text("SERVIDOR CIVITAS · ACCESO", parent=contenido, origin=(0, 0),
                                   position=(0, my - 0.024, -0.001), scale=0.3, color=rgb(pa.CIAN),
                                   font=tipografia.FUENTE_TITULO)
        self.texto_nivel = Text("", parent=contenido, origin=(0, 0), position=(0, 0.035, -0.001), scale=0.4,
                                color=rgb((255, 225, 110)), font=tipografia.FUENTE_TITULO)
        self.texto_estado = Text("Conectando…", parent=contenido, origin=(0, 0), position=(0, -my + 0.02, -0.001),
                                 scale=0.3, color=rgb(pa.MAGENTA))
        for e in [contenido, *contenido.children]:
            e.setLightOff()
        silenciar(contenido)
        silenciar(self.pantalla_quad)

    def _construir_luces(self):
        x, y, z = pa.ORIGEN
        ambiente = AmbientLight(parent=self, color=color.rgba32(96, 98, 128, 255))
        sol = DirectionalLight(parent=self, shadows=False)
        sol.position = (x + 1.0, y + 2.5, z - 1.5)
        sol.look_at((x - 0.3, y, z + 1.2))
        sol.color = color.rgba32(210, 215, 255, 255)
        for luz in (ambiente, sol):
            encender_luz(luz, False)
        return (sol, ambiente)

    # -- Personaje --

    def _preparar_personaje(self, jugador):
        clave = (getattr(jugador, "nombre", None), getattr(jugador, "rol", None))
        if self.personaje is not None and clave == self._clave_personaje:
            return
        self._soltar()
        if self.personaje is not None:
            destruir_arbol(self.personaje)
            self.personaje = None
        self.personaje = _personaje(jugador, self)
        self._clave_personaje = clave

    def _colocar_al_inicio(self):
        cs, _, _ = _modulo()
        try:
            x, z, rumbo = cs.punto_de_partida(self.silla)
        except Exception:                      # noqa: BLE001
            x, z, rumbo = pa.punto_de_partida()
        self.personaje.y = pa.suelo_y()
        self.personaje.colocar(x, z)
        self.personaje.fijar_rumbo(rumbo)
        sx, sz = self.silla.posicion
        self.ent_silla.world_x, self.ent_silla.world_z = sx, sz

    # -- Mostrar / ocultar --

    def mostrar(self, visible):
        from ursina import window
        self.enabled = bool(visible)
        for luz in self.luces:
            encender_luz(luz, bool(visible))
        if visible:
            window.color = rgb(FONDO_VENTANA)

    @staticmethod
    def poner_camara(toma):
        from frontend.minijuegos_3d.camaras_calculos import rotacion_mirando
        camera.position = toma["position"]
        pitch, yaw = rotacion_mirando(toma["position"], toma["target"])
        camera.rotation = (pitch, yaw, 0)
        camera.fov = toma["fov"]

    # -- Secuencias --

    def entrar(self, jugador, texto_nivel, al_terminar, aspecto):
        """Pone la sala (personaje en el punto de partida, cámara en la toma de la sala) y lanza entrar_a_pantalla.
        `al_terminar` se llama una vez con la pantalla llena (o al saltar, o si la secuencia falla por dentro)."""
        cs, _, _ = _modulo()
        self._preparar_personaje(jugador)
        self.texto_nivel.text = pa.partir_lineas(texto_nivel or "", pa.LETRAS_POR_LINEA)
        self.texto_estado.text = "Conectando…"
        self._soltar()
        self._colocar_al_inicio()
        self.mostrar(True)
        toma_inicial = pa.toma_sala()
        self.poner_camara(toma_inicial)
        previa = self.sec
        sec = cs.entrar_a_pantalla(self.personaje, self.silla, self.mesa, self.pantalla, entidad_silla=self.ent_silla,
                                   toma_inicial=toma_inicial, clave=CLAVE, auto=False, limites=pa.limites(),
                                   aspecto=aspecto, al_terminar=al_terminar)
        if self.sec is previa:               # (si al_terminar corrió dentro de la llamada no se pisa nada)
            self.sec = sec
        return sec

    def salir(self, al_terminar, aspecto):
        """Vuelta del servidor: la cámara sale de la pantalla (sigue sentado), se levanta, empuja la silla y se aparta.
        `al_terminar` se llama una vez al final (o al saltar / si algo falla por dentro)."""
        cs, _, _ = _modulo()
        if self.personaje is None:
            raise RuntimeError("antesala sin personaje")
        self.texto_estado.text = "Desconectado"
        self.mostrar(True)
        poses = getattr(self.sec, "poses", None)
        self._al_terminar_salida = al_terminar
        previa = self.sec
        # Parte de la pantalla llena (la calcula el módulo, como al entrar) y termina sobre el hombro, aún sentado.
        sec = cs.salir_de_pantalla(self.personaje, self.silla, self.mesa, self.pantalla, entidad_silla=self.ent_silla,
                                   toma_final=pa.toma_hombro(getattr(self.personaje, "rol", None)), poses=poses, clave=CLAVE, auto=False,
                                   limites=pa.limites(), aspecto=aspecto, al_terminar=self._levantarse)
        if self.sec is previa:               # si terminó dentro de la llamada, self.sec ya es la de levantarse
            self.sec = sec
        return self.sec

    def _levantarse(self):
        cs, _, _ = _modulo()
        poses = getattr(self.sec, "poses", None)
        al_terminar, self._al_terminar_salida = self._al_terminar_salida, None
        self.sec = cs.levantarse_de(self.personaje, self.silla, self.mesa, entidad_silla=self.ent_silla,
                                    toma_final=pa.toma_sala(), poses=poses, clave=CLAVE, auto=False,
                                    limites=pa.limites(), al_terminar=al_terminar)

    def avanzar(self, dt):
        if self.sec is not None:
            self.sec.avanzar(dt)

    def activa(self):
        return self.sec is not None and bool(getattr(self.sec, "activa", False))

    def saltar(self):
        """Termina TODA la secuencia en curso (la salida encadena dos: las salta ambas). True si había algo."""
        hubo = False
        for _ in range(3):
            sec = self.sec
            if sec is None or not getattr(sec, "activa", False):
                break
            hubo = bool(sec.saltar()) or hubo
            if self.sec is sec:
                break
        return hubo

    def _soltar(self):
        sec, self.sec = self.sec, None
        if sec is None:
            return
        try:
            sec.cancelar()
        except Exception:                      # noqa: BLE001
            pass
        try:
            sec.soltar()
        except Exception:                      # noqa: BLE001
            pass

    def ocultar(self, soltar=False):
        """Oculta la sala y apaga sus luces. `soltar`: además devuelve el personaje a su animación normal (al salir del
        parkour; entre la entrada y la salida la pose sentada se conserva para salir_de_pantalla)."""
        if soltar:
            self._al_terminar_salida = None
            self._soltar()
        self.mostrar(False)
