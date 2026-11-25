# TRABAJOS visuales (Ursina). Los turnos se juegan igual (backend/logica/trabajos.py, entregas.py, taller_ritmo.py no
# cambian, ni el pago ni el resultado); solo se decora lo que ya pasa:
#   - ATENDER (panadería, súper, feria, bar): una FILA de clientes esperando detrás del que pide, una BARRA DE PACIENCIA
#     sobre su cabeza, el producto VUELA de la bandeja al cliente al acertar y saltan MONEDAS al completar el pedido;
#   - SECUENCIA (lan house): las flechas son los bloques en la pantalla de un PC que se repara; al fallar, PANTALLA AZUL
#     falsa; al completar la secuencia, «PC reparado»;
#   - BARRA (lanchonete): la comida sobre la plancha CAMBIA DE COLOR según la marca (cruda, dorada, quemada) y HUMEA; cada
#     parada deja un PLATO en la fila (crudo, perfecto o quemado);
#   - RITMO (taller): ya tenía martillazo, chispas y la pieza que se arma (frontend/taller_vista.py): no se toca;
#   - ENTREGAS: el destinatario SALUDA con un «¡Gracias!», suena el CLAXON, flota un «+R$» y la moto deja ESTELA.
# Entra envolviendo métodos de LA INSTANCIA de EscenaTrabajo (la del gestor) y de EntregasMundo (economia.entregas), sin
# tocar escena_trabajo.py ni entregas_mundo.py.
# APAGADO: ALCALDE_TRABAJOS_VISUAL=0. REDUCIR MOVIMIENTO: sin vuelos ni humo que se mueve ni estela; lo demás, quieto.
# GUARDIÁN: un fallo avisa una vez por stderr, esconde lo añadido y el turno sigue exactamente igual.

import math

from ursina import Entity, Text, camera, color, scene, time

from frontend import banderas_visuales as bv
from frontend import estilo, tipografia
from frontend import trabajos_visual_calculos as calc
from frontend.componentes import destruir_arbol, escala_fuente, panel_piel

TRABAJOS_VISUAL = True
VARIABLE = "ALCALDE_TRABAJOS_VISUAL"

CLIENTE = (-0.4, 0.045)
DORADO = (255, 205, 64)
AZUL_ERROR = (30, 90, 200)
VERDE_OK = (60, 170, 90)
SEGUNDOS_PANTALLA = 0.45
MAX_PLATOS = 8


def activo():
    return bv.activa(TRABAJOS_VISUAL, VARIABLE)


def _rgba(tono, alfa=1.0):
    return color.rgba32(int(tono[0]), int(tono[1]), int(tono[2]), int(max(0.0, min(1.0, alfa)) * 255))


def _moneda(padre, lado=0.035):
    m = Entity(parent=padre, enabled=False)
    Entity(parent=m, model="circle", scale=lado, color=_rgba((150, 110, 20)))
    Entity(parent=m, model="circle", scale=lado * 0.8, color=_rgba(DORADO), z=-0.001)
    return m


class DecoracionTrabajo:
    """Decora una EscenaTrabajo. Capas propias bajo escena.raiz (no las borra el redibujado del juego)."""

    def __init__(self, escena):
        self.escena = escena
        self.roto = False
        self.fondo = Entity(parent=escena.raiz, z=-0.035)       # detrás del juego (fila, monitor)
        self.frente = Entity(parent=escena.raiz, z=-0.065)      # delante del juego, debajo de intro/resultado
        self._construir_atender()
        self._construir_secuencia()
        self._construir_barra()
        self._reiniciar()

    # -- Construcción (una vez; luego solo se mueve / enciende) --

    def _construir_atender(self):
        self.at_fondo = Entity(parent=self.fondo, enabled=False)
        self.at_frente = Entity(parent=self.frente, enabled=False)
        self.fila = Entity(parent=self.at_fondo)
        self.pac_marco = Entity(parent=self.at_frente, model="quad", scale=(0.15, 0.022), color=_rgba(estilo.TINTA),
                                position=(CLIENTE[0], CLIENTE[1] - 0.112, 0))
        self.pac_barra = Entity(parent=self.at_frente, model="quad", origin=(-0.5, 0), scale=(0.14, 0.014),
                                position=(CLIENTE[0] - 0.07, CLIENTE[1] - 0.112, -0.001))
        self.vuelos = {}                 # índice de producto -> icono (uno por producto, reutilizado)
        self.propina = [_moneda(self.at_frente) for _ in range(3)]

    def _construir_secuencia(self):
        self.sq_fondo = Entity(parent=self.fondo, enabled=False)
        self.sq_frente = Entity(parent=self.frente, enabled=False)
        self.monitor = panel_piel(self.sq_fondo, 0.9, 0.19, tono=(40, 42, 50), radio_px=10, sombra=False, borde_px=2,
                                   position=(0, 0.08, 0))
        self.pantalla = panel_piel(self.sq_fondo, 0.86, 0.16, tono=(16, 24, 48), radio_px=6, sombra=False, borde_px=0,
                                    position=(0, 0.08, -0.001))
        self.led = Entity(parent=self.sq_fondo, model="circle", scale=0.012, color=_rgba(VERDE_OK), position=(0, 0, -0.002))
        self.azul = Entity(parent=self.sq_frente, enabled=False)
        self.azul.fondo = Entity(parent=self.azul, model="quad", color=_rgba(AZUL_ERROR))
        self.azul.texto = Text(":(  Algo salió mal. Reiniciando la secuencia...", parent=self.azul, origin=(0, 0),
                               z=-0.001, scale=escala_fuente(18), color=_rgba((255, 255, 255)))
        self.reparado = Entity(parent=self.sq_frente, enabled=False)
        self.reparado.fondo = Entity(parent=self.reparado, model="quad", color=_rgba(VERDE_OK, 0.92))
        self.reparado.texto = Text("", parent=self.reparado, origin=(0, 0), z=-0.001, scale=escala_fuente(24),
                                   font=tipografia.FUENTE_TITULO, color=_rgba((255, 255, 255)))

    def _construir_barra(self):
        self.br_frente = Entity(parent=self.frente, enabled=False)
        self.plancha = Entity(parent=self.br_frente, model="quad", scale=(0.1, 0.012), color=_rgba((70, 70, 78)))
        self.comida = Entity(parent=self.br_frente, model="circle", scale=(0.07, 0.034))
        self.humos = [Entity(parent=self.br_frente, model="circle", color=_rgba((220, 220, 225), 0.5)) for _ in range(4)]
        self.platos = []
        for _ in range(MAX_PLATOS):
            p = Entity(parent=self.br_frente, enabled=False)
            Entity(parent=p, model="circle", scale=0.05, color=_rgba((236, 236, 240)))
            p.comida = Entity(parent=p, model="circle", scale=(0.032, 0.018), z=-0.001)
            self.platos.append(p)

    # -- Estado --

    def _reiniciar(self):
        self._n_cliente = None
        self._t_espera = 0.0
        self._vuelo = None            # (icono, t)
        self._t_propina = None
        self._t_azul = 0.0
        self._t_reparado = 0.0
        self._pcs = 0
        self._resultados_platos = []
        self._t = 0.0
        for capa in (self.at_fondo, self.at_frente, self.sq_fondo, self.sq_frente, self.br_frente):
            capa.enabled = False
        for hijo in list(self.fila.children):
            destruir_arbol(hijo)

    def _motor(self):
        t = getattr(self.escena, "trabajo", None)
        return None if t is None else t.motor

    def _jugando(self):
        from frontend.trabajo_constantes import JUGANDO
        e = self.escena
        return e.fase == JUGANDO and e.turno is not None and not e.turno.terminado()

    # -- Envolturas (las llama la instancia envuelta) --

    def antes_de_accion(self):
        if self.roto or not self._jugando():
            return None
        e, motor = self.escena, self._motor()
        from backend.logica.trabajos import BARRA, SECUENCIA
        antes = {"motor": motor, "n": e._n_pedido}
        if motor == BARRA:
            antes["pos"], antes["zona"] = e.turno.posicion_barra(), e.turno.zona_barra()
        elif motor == SECUENCIA:
            antes["prog"], antes["largo"] = e.turno.progreso(), len(e.turno.secuencia())
        return antes

    def tras_accion(self, entrada, acierto, antes):
        if antes is None:
            return
        self._vigilar(self._tras_accion, entrada, acierto, antes)

    def frame(self, dt):
        self._vigilar(self._frame, dt)

    def limpiar(self):
        self._vigilar(self._reiniciar)

    # -- Lo nuevo --

    def _tras_accion(self, entrada, acierto, antes):
        from backend.logica.trabajos import ATENDER, BARRA, SECUENCIA
        e, motor = self.escena, antes["motor"]
        reducir = bv.reducir_movimiento()
        if motor == ATENDER and acierto and isinstance(entrada, int):
            if self._vuelo is not None:          # un vuelo a medias se termina al empezar otro
                self._vuelo[0].enabled = False
            icono = self._icono(entrada - 1)
            icono.enabled = True
            desde = (-0.39 + 0.26 * (entrada - 1), -0.165)
            icono.position = (*(CLIENTE if reducir else desde), 0)
            self._vuelo = (icono, desde, 0.0)
            if e._n_pedido > antes["n"]:
                self._t_propina = 0.0
        elif motor == SECUENCIA:
            if not acierto:
                self._t_azul = SEGUNDOS_PANTALLA
            elif calc.pc_reparado(antes["prog"], e.turno.progreso(), antes["largo"], acierto):
                self._pcs += 1
                self._t_reparado = 0.7
                self.reparado.texto.text = f"PC reparado ({self._pcs})"
        elif motor == BARRA:
            self._resultados_platos.append(calc.plato_de(antes["pos"], antes["zona"], acierto))
            self._resultados_platos = self._resultados_platos[-MAX_PLATOS:]
            self._pintar_platos()
        if e.turno.terminado():
            self._esconder()

    def _icono(self, i):
        if i not in self.vuelos:
            from frontend.trabajo_dibujos import dibujar_icono
            productos = self.escena.trabajo.opciones
            self.vuelos[i] = dibujar_icono(self.at_frente, productos[i] if i < len(productos) else "", (0, 0), 0.06, z=0)
        return self.vuelos[i]

    def _esconder(self):
        for capa in (self.at_fondo, self.at_frente, self.sq_fondo, self.sq_frente, self.br_frente):
            capa.enabled = False

    def _frame(self, dt):
        if not self._jugando():
            self._esconder()
            return
        from backend.logica.trabajos import ATENDER, BARRA, SECUENCIA
        self._t += dt
        motor = self._motor()
        self.at_fondo.enabled = self.at_frente.enabled = motor == ATENDER
        self.sq_fondo.enabled = self.sq_frente.enabled = motor == SECUENCIA
        self.br_frente.enabled = motor == BARRA
        if motor == ATENDER:
            self._frame_atender(dt)
        elif motor == SECUENCIA:
            self._frame_secuencia(dt)
        elif motor == BARRA:
            self._frame_barra()

    def _frame_atender(self, dt):
        from frontend.trabajo_dibujos import dibujar_cliente
        e = self.escena
        reducir = bv.reducir_movimiento()
        if self._n_cliente != e._n_pedido:          # cliente nuevo: la fila avanza y la paciencia se rellena
            self._n_cliente = e._n_pedido
            self._t_espera = 0.0
            for hijo in list(self.fila.children):
                destruir_arbol(hijo)
            dibujar_cliente(self.fila, e._n_pedido + 2, (-0.53, 0.0), 0.55)
            dibujar_cliente(self.fila, e._n_pedido + 1, (-0.49, 0.015), 0.7).z = -0.002
        self._t_espera += dt
        f = calc.paciencia(self._t_espera, sum(e.turno.pedido().values()))
        self.pac_barra.scale_x = max(0.0001, 0.14 * f)
        self.pac_barra.color = _rgba(calc.color_paciencia(f))
        if self._vuelo is not None:
            icono, desde, t = self._vuelo
            t += dt
            x, y, fin = calc.arco(t, desde, (CLIENTE[0] + 0.05, CLIENTE[1]))
            if not reducir:
                icono.position = (x, y, 0)
            self._vuelo = None if fin else (icono, desde, t)
            if fin:
                icono.enabled = False
        if self._t_propina is not None:
            self._t_propina += dt
            for i, m in enumerate(self.propina):
                dx, dy, alfa = calc.moneda_propina(0.4 if reducir else self._t_propina, i)
                m.enabled = alfa > 0
                m.position = (CLIENTE[0] + dx, CLIENTE[1] - 0.01 + dy, -0.002)
            if self._t_propina > 0.8:
                self._t_propina = None
                for m in self.propina:
                    m.enabled = False

    def _frame_secuencia(self, dt):
        n = len(self.escena.turno.secuencia())
        ancho = calc.ancho_monitor(n)
        self.monitor.scale_x = ancho / 0.9
        self.pantalla.scale_x = (ancho - 0.04) / 0.86
        self.led.position = (ancho / 2 - 0.03, 0.08 - 0.087, -0.002)
        self.azul.fondo.scale = (ancho - 0.04, 0.16)
        self.azul.position = (0, 0.08, -0.01)
        self.reparado.fondo.scale = (ancho - 0.04, 0.16)
        self.reparado.position = (0, 0.08, -0.012)
        self._t_azul = max(0.0, self._t_azul - dt)
        self._t_reparado = max(0.0, self._t_reparado - dt)
        self.azul.enabled = self._t_azul > 0
        self.reparado.enabled = self._t_reparado > 0 and not self.azul.enabled

    def _frame_barra(self):
        from frontend.trabajo_constantes import ANCHO_BARRA
        t = self.escena.turno
        pos, zona = t.posicion_barra(), t.zona_barra()
        x = -ANCHO_BARRA / 2 + pos * ANCHO_BARRA
        self.plancha.position = (x, 0.128, 0)
        self.comida.position = (x, 0.148, -0.001)
        self.comida.color = _rgba(calc.tono_coccion(pos, zona))
        tiempo = 0.0 if bv.reducir_movimiento() else self._t
        intensidad = 0.4 + 0.6 * calc.cercania(pos, zona)
        for i, h in enumerate(self.humos):
            dx, dy, alfa, escala = calc.humo(tiempo + i * 0.07, i)
            h.position = (x + dx + (i - 1.5) * 0.012, 0.155 + dy, -0.002)
            h.scale = escala
            h.color = _rgba((220, 220, 225), alfa * intensidad)

    def _pintar_platos(self):
        tonos = {"crudo": calc.CRUDO, "perfecto": calc.PERFECTO, "quemado": calc.QUEMADO}
        for i, p in enumerate(self.platos):
            hay = i < len(self._resultados_platos)
            p.enabled = hay
            if hay:
                p.position = (-0.5 + 0.06 * i, -0.24, 0)
                p.comida.color = _rgba(tonos[self._resultados_platos[i]])

    # -- Guardián --

    def _vigilar(self, funcion, *args):
        if self.roto:
            return None
        try:
            return funcion(*args)
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("trabajos_visual", error)
            self.roto = True
            try:
                self._esconder()
            except Exception:            # noqa: BLE001
                pass
            return None


def envolver_escena(escena):
    """Envuelve accion/avanzar/_limpiar de ESTA instancia de EscenaTrabajo. Devuelve la decoración (o None)."""
    if escena is None or getattr(escena, "_trabajos_visual", None) is not None:
        return None
    deco = DecoracionTrabajo(escena)
    escena._trabajos_visual = deco
    accion, avanzar, limpiar = escena.accion, escena.avanzar, escena._limpiar

    def accion_visual(entrada):
        antes = deco.antes_de_accion() if not deco.roto else None
        acierto = accion(entrada)
        deco.tras_accion(entrada, acierto, antes)
        return acierto

    def avanzar_visual(dt):
        avanzar(dt)
        deco.frame(dt)

    def limpiar_visual():
        limpiar()
        deco.limpiar()

    escena.accion, escena.avanzar, escena._limpiar = accion_visual, avanzar_visual, limpiar_visual
    return deco


# -- Entregas en el mundo --

class VigiaEntregas(Entity):
    """Busca economia.entregas (se crea al empezar la partida), envuelve su _al_entregar y anima estela y «+R$»."""

    def __init__(self, escena_mundo):
        super().__init__(parent=camera.ui)
        self.escena_mundo = escena_mundo
        self.roto = False
        self._envuelto = None
        self._turno = None
        self._pago = 0
        self.flotante = Text("", parent=self, origin=(0, 0), position=(0, 0.18, -0.3), scale=escala_fuente(40),
                             font=tipografia.fuente_piel(titulo=True), color=_rgba(DORADO), enabled=False)
        self._t_flotante = None
        self._saludos = []            # [npc, globo, t]
        self._estela = []
        self._t_estela = 0.0
        self._ultima = None

    def _entregas(self):
        return getattr(getattr(self.escena_mundo, "economia", None), "entregas", None)

    def update(self):
        if self.roto:
            return
        try:
            self._update(min(time.dt, 0.1))
        except Exception as error:      # noqa: BLE001
            bv.avisar_una_vez("trabajos_visual_entregas", error)
            self.roto = True
            self.flotante.enabled = False
            for t in self._estela:
                t[0].enabled = False

    def _update(self, dt):
        ent = self._entregas()
        if ent is not None and ent is not self._envuelto:
            self._envolver(ent)
        if ent is not None and ent.turno is not self._turno:
            self._turno, self._pago = ent.turno, 0
        if self._t_flotante is not None:
            self._t_flotante += dt
            dy, alfa = calc.flotar(0.8 if bv.reducir_movimiento() else self._t_flotante)
            self.flotante.y = 0.18 + dy
            self.flotante.color = _rgba(DORADO, alfa)
            if self._t_flotante > 1.6:
                self._t_flotante = None
                self.flotante.enabled = False
        for s in list(self._saludos):
            s[2] -= dt
            if s[2] <= 0:
                self._fin_saludo(s)
        self._estela_frame(ent, dt)

    def _envolver(self, ent):
        self._envuelto = ent
        original = ent._al_entregar

        def al_entregar_visual(pedido):
            original(pedido)
            if not self.roto:
                try:
                    self._celebrar(ent, pedido)
                except Exception as error:      # noqa: BLE001
                    bv.avisar_una_vez("trabajos_visual_entregas", error)
                    self.roto = True
        ent._al_entregar = al_entregar_visual

    def _celebrar(self, ent, pedido):
        pago = ent.turno.resultado()["pago"] if ent.turno is not None else self._pago
        monto = calc.monto_entrega(self._pago, pago)
        self._pago = pago
        if monto > 0:
            self.flotante.text = f"+R$ {monto}"
            self.flotante.enabled = True
            self._t_flotante = 0.0
        try:
            from frontend import audio
            audio.obtener().efecto("bici_timbre", 0.8, 0.5)          # claxon (timbre grave)
        except Exception:                # noqa: BLE001
            pass
        hechas = ent.turno.entregas_hechas() if ent.turno is not None else 0
        if 0 < hechas <= len(ent._destinatarios):
            self._saludar(ent._destinatarios[hechas - 1])

    def _saludar(self, npc):
        try:
            if npc.actor.getAnimControl("Saludar") is not None:
                npc.actor.loop("Saludar")
        except Exception:                # noqa: BLE001  sin clip: solo el globo
            pass
        from frontend import npc_postura
        from frontend.piezas import etiqueta
        globo = etiqueta("¡Gracias!", parent=npc_postura.ancla_cabeza(npc))
        self._saludos.append([npc, globo, 2.5])

    def _fin_saludo(self, s):
        self._saludos.remove(s)
        npc, globo, _ = s
        try:
            destruir_arbol(globo)
            if npc.actor.getAnimControl("Idle") is not None:
                npc.actor.loop("Idle")
        except Exception:                # noqa: BLE001  el destinatario ya no está (turno cerrado)
            pass

    def _estela_frame(self, ent, dt):
        for t in self._estela:
            if t[0].enabled:
                t[1] -= dt
                t[0].alpha = max(0.0, t[1] / 0.5) * 0.45
                if t[1] <= 0:
                    t[0].enabled = False
        jugador = None if ent is None or ent.turno is None else ent.jugador
        if jugador is None or bv.reducir_movimiento() or dt <= 0:
            self._ultima = None
            return
        pos = (float(jugador.x), float(getattr(jugador, "y", 0.0)), float(jugador.z))      # el Jugador del backend no tiene y
        if self._ultima is not None:
            v = math.hypot(pos[0] - self._ultima[0], pos[2] - self._ultima[2]) / dt
            self._t_estela += dt
            if calc.deja_estela(v) and self._t_estela >= 0.04:
                self._t_estela = 0.0
                rumbo = math.degrees(math.atan2(pos[0] - self._ultima[0], pos[2] - self._ultima[2]))
                trazo = next((t for t in self._estela if not t[0].enabled), None)
                if trazo is None and len(self._estela) < 16:
                    e = Entity(parent=scene, model="quad", rotation_x=90, scale=(0.35, 0.9),
                               color=_rgba(estilo.COLOR_ACENTO, 0.45), double_sided=True)
                    trazo = [e, 0.0]
                    self._estela.append(trazo)
                if trazo is not None:
                    trazo[0].enabled = True
                    trazo[0].position = (self._ultima[0], self._ultima[1] + 0.06, self._ultima[2])
                    trazo[0].rotation_y = rumbo
                    trazo[1] = 0.5
        self._ultima = pos


def registrar(gestor, conexion, escena_mundo):
    if not activo():
        return None
    from frontend.flujo_constantes import TRABAJO
    escena = getattr(gestor, "_escenas", {}).get(TRABAJO)
    deco = envolver_escena(escena)
    vigia = VigiaEntregas(escena_mundo) if escena_mundo is not None else None
    return deco, vigia
