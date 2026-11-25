# Trabajo «Mototaxi y entregas» jugado en el mundo (sustituye al minijuego de la barra). Lógica pura en
# backend/logica/entregas.py; este módulo solo pinta y conecta:
#   - preparar(jugador): al abrir el menú del puesto se eligen al azar los 2 pedidos y el tiempo límite, para que el
#     menú los explique antes de aceptar (frontend/trabajo_mundo.py: MenuTrabajo);
#   - iniciar(puesto): al aceptar se da una moto junto al jugador y se le monta en ella; en cada lugar de entrega espera
#     el destinatario (un NPC con su nombre), el pedido actual usa la baliza amarilla, la ruta azul del suelo y la ruta
#     del minimapa de las misiones (gancho `destino_trabajo` de EscenaMundo y del HUD), y los dos pedidos salen como
#     objetivos en el minimapa;
#   - entregar = pasar por encima del punto; al terminar (las dos entregas, tiempo agotado o cambio de turno) se cobra
#     con pago_trabajo.aplicar_resultado, como los demás turnos.
# La moto del trabajo se crea una vez y se reutiliza (se recoloca) en los turnos siguientes.
#
# BANDERA. ENTREGAS_EN_MUNDO = False (o ALCALDE_ENTREGAS_MUNDO=0): el puesto vuelve a abrir la escena de trabajo 2D.

import math
import os
import random
import sys

from ursina import Entity, Text, time

from backend.datos.entregas_semilla import PUNTOS_ENTREGA
from backend.datos.nombres_visibles import nombre_visible
from backend.logica import entregas as le
from backend.logica.trabajos import ENTREGAS
from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, rgb, panel_piel

ENTREGAS_EN_MUNDO = True
FUENTE_MINIMAPA = "entregas"
DISTANCIAS_MOTO = (2.5, 3.5, 5.0)       # m desde el jugador donde se busca sitio para la moto
LATERAL_DESTINATARIO = 1.6              # m al lado del punto de entrega donde espera el destinatario
INDICE_NPC_DESTINATARIO = 160           # caras distintas de las de los comercios (101 en adelante)
ANCHO_HUD, ALTO_HUD, Y_HUD = 1.12, 0.11, 0.33       # bajo la barra de confianza
SEGUNDOS_URGENTE = 15


def activo():
    valor = os.environ.get("ALCALDE_ENTREGAS_MUNDO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(ENTREGAS_EN_MUNDO)


def es_entregas(puesto):
    trabajo = getattr(puesto, "trabajo", puesto)
    return getattr(trabajo, "motor", None) == ENTREGAS


# Primera letra en mayúscula («una caja» -> «Una caja»).
def _mayuscula(texto):
    return texto[:1].upper() + texto[1:]


def texto_pedido(pedido):
    return f"{pedido.punto.paquete} para {pedido.punto.destinatario}, en {nombre_visible(pedido.punto.lugar, corto=True)}"


def texto_tiempo(segundos):
    segundos = max(0, int(math.ceil(segundos)))
    return f"{segundos // 60}:{segundos % 60:02d}"


# Explicación del menú (MenuTrabajo): corta y en pasos, con los pedidos concretos de este turno.
def explicacion(plan):
    lineas = ["CÓMO FUNCIONA",
              "1. Al aceptar te damos una moto y sales ya montado.",
              f"2. Lleva {len(plan['pedidos'])} pedidos, en este orden:"]
    lineas += [f"      {i}) {_mayuscula(texto_pedido(p))}" for i, p in enumerate(plan["pedidos"], 1)]
    lineas += ["3. Sigue la línea azul del suelo y el rombo amarillo (también en el minimapa).",
               "4. Para entregar, solo pasa por encima del punto. No hay que pulsar nada.",
               f"5. Tienes {texto_tiempo(plan['limite'])} min. Cuanto antes acabes, más cobras;",
               "    si se acaba el tiempo, solo cobras lo que entregaste.",
               "Moto: W acelera · S frena · A/D gira · Ctrl turbo · E bajar"]
    return "\n".join(lineas)


def texto_detalle(trabajo, plan):
    return f"Paga R$ {trabajo.pago_base} a {trabajo.pago_max} · Tiempo límite: {texto_tiempo(plan['limite'])} min"


# Metros de la ruta del GPS de (x, z) a la puerta de `lugar`; si el GPS falla, la recta por 1,4.
def _metros_ruta(mundo, x, z, lugar, fx, fz):
    try:
        from backend.logica import navegacion
        puntos = [(x, z)] + list(navegacion.ruta_gps_hasta_puerta(mundo, x, z, lugar))
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(puntos, puntos[1:]))
    except Exception:
        return math.hypot(fx - x, fz - z) * 1.4


class EntregasMundo(Entity):

    def __init__(self, economia, catalogo=PUNTOS_ENTREGA, rng=None):
        super().__init__(parent=economia)
        self.economia = economia
        self.catalogo = catalogo
        self.rng = rng or random.Random()
        self.turno = None
        self.jugador = None
        self.puesto = None
        self._plan = None
        self._moto = None
        self._destinatarios = []
        self.hud = None
        self._mostrado = None

    @property
    def escena(self):
        return self.economia.escena

    @property
    def en_curso(self):
        return self.turno is not None

    # -- Antes de aceptar --

    # Elige los pedidos y el tiempo límite para `jugador` (desde donde está). Devuelve el plan o None si no hay pedidos.
    def preparar(self, jugador):
        mundo = self.escena._mundo
        x0, z0 = float(jugador.x), float(jugador.z)
        pedidos = le.elegir_pedidos(le.pedidos_posibles(mundo, self.catalogo), x0, z0, self.rng)
        if not pedidos:
            self._plan = None
            return None
        metros, x, z = 0.0, x0, z0
        for pedido in pedidos:
            metros += _metros_ruta(mundo, x, z, pedido.punto.lugar, pedido.x, pedido.z)
            x, z = pedido.x, pedido.z
        self._plan = {"jugador": jugador, "pedidos": pedidos, "limite": le.tiempo_limite(metros)}
        return self._plan

    # -- Empezar --

    def _puede_empezar(self, jugador):
        escena = self.escena
        flujo = escena.flujo
        if self.en_curso or flujo is None or flujo.partida_terminada() or escena._cinematica:
            return False
        from backend.logica.misiones import COMPLETADA, EN_MINIJUEGO
        if flujo.estado_mision() in (EN_MINIJUEGO, COMPLETADA):
            return False
        from frontend import economia_config as cfg
        if cfg.CANSANCIO:
            from backend.logica.trabajos import puede_trabajar
            perfil = self.economia.perfil(jugador)
            if perfil is not None and not puede_trabajar(perfil):
                return False
        return jugador is flujo.jugador_activo()

    # Empieza el turno con el puesto aceptado. True si empezó.
    def iniciar(self, puesto):
        flujo = self.escena.flujo
        jugador = None if flujo is None else flujo.jugador_activo()
        if jugador is None or not self._puede_empezar(jugador):
            return False
        plan = self._plan if self._plan is not None and self._plan["jugador"] is jugador else self.preparar(jugador)
        self._plan = None
        if plan is None:
            self.economia.aviso_temporal("Hoy no hay pedidos que repartir.")
            return False
        # Tutorial de la primera vez (frontend/tutorial_mision_ruta.py, ALCALDE_TUTORIAL_MISION=0 lo apaga): el turno empieza al cerrarlo.
        try:
            from frontend import tutorial_mision_ruta
            if tutorial_mision_ruta.entregas_antes_de_iniciar(self, puesto, plan):
                return True
        except Exception:                # noqa: BLE001
            pass
        self.turno = le.TurnoEntregas(puesto.trabajo, plan["pedidos"], plan["limite"])
        self.jugador, self.puesto = jugador, puesto
        try:
            self._dar_moto(jugador, plan["pedidos"][0])
        except Exception as error:          # sin moto se puede repartir a pie: el turno sigue
            print(f"[entregas] no se pudo dar la moto ({error})", file=sys.stderr)
        self._poner_destinatarios(plan["pedidos"])
        self.escena.destino_trabajo = self.destino_actual
        self.escena.hud.destino_trabajo = self.destino_actual
        self._crear_hud()
        self._marcar_minimapa()
        self.economia.aviso_temporal("¡Moto lista! Sigue la línea azul hasta el primer pedido.")
        return True

    # Moto del trabajo junto al jugador, mirando hacia el primer pedido, y el jugador montado en ella.
    def _dar_moto(self, jugador, pedido):
        integracion = getattr(self.escena, "vehiculos", None)
        if integracion is None or integracion.conduciendo:
            return
        from frontend import vehiculo_calculos as vc
        mundo_v = integracion.mundo
        mundo = self.escena._mundo
        x, z = float(jugador.x), float(jugador.z)
        rumbo = math.degrees(math.atan2(pedido.x - x, pedido.z - z))
        sitio = (x, z)
        for distancia in DISTANCIAS_MOTO:
            libres = []
            for k in range(8):
                angulo = math.radians(rumbo + 90 + 45 * k)
                px, pz = x + math.sin(angulo) * distancia, z + math.cos(angulo) * distancia
                if vc.posicion_valida(mundo, px, pz, rumbo, vc.PERFIL_MOTO):
                    libres.append((px, pz))
            if libres:
                sitio = libres[0]
                break
        moto = self._moto if self._moto in mundo_v.vehiculos else None
        if moto is None:
            moto = mundo_v.colocar(vc.Aparcado(vc.MOTO, sitio[0], sitio[1], rumbo, 0))
            self._moto = moto
        else:
            moto.estado = vc.estado_inicial(sitio[0], sitio[1], rumbo)
            moto.modelo.aplicar_estado(moto.estado, 0.0, mundo.altura)
            moto.modelo.aparcar()
        integracion.montar(moto, jugador)
        self.escena.camara.yaw = rumbo

    # Un NPC con su nombre al lado de cada punto de entrega, mirando a la calle.
    def _poner_destinatarios(self, pedidos):
        self._quitar_destinatarios()
        from frontend.comercios_mundo import _crear_dependiente, es_dependienta, indice_vestido
        mundo = self.escena._mundo
        usados = set()
        for pedido in pedidos:
            try:
                try:
                    rumbo = (mundo.edificio_de(pedido.punto.lugar).rumbo_puerta() + 180.0) % 360.0
                except (ValueError, AttributeError):
                    rumbo = 0.0
                r = math.radians(rumbo)
                x = pedido.x + math.cos(r) * LATERAL_DESTINATARIO
                z = pedido.z - math.sin(r) * LATERAL_DESTINATARIO
                nombre = pedido.punto.destinatario
                indice = indice_vestido(INDICE_NPC_DESTINATARIO, usados, es_dependienta(nombre))
                usados.add(indice)
                self._destinatarios.append(_crear_dependiente(self.escena, indice, nombre, x, z, rumbo))
            except Exception as error:      # sin el NPC el punto sigue marcado: se puede entregar igual
                print(f"[entregas] destinatario no creado ({error})", file=sys.stderr)

    def _quitar_destinatarios(self):
        from frontend.componentes import destruir_arbol
        for npc in self._destinatarios:
            try:
                destruir_arbol(npc)
            except Exception:
                pass
        self._destinatarios = []

    # Lugar del pedido actual (lo leen EscenaMundo y el HUD para la baliza y las rutas) o None sin turno.
    def destino_actual(self):
        pedido = None if self.turno is None else self.turno.pedido_actual()
        return None if pedido is None else pedido.punto.lugar

    # -- HUD --

    def _crear_hud(self):
        if self.hud is None:
            hud = Entity(parent=self.escena.hud, y=Y_HUD, z=-0.04)
            panel_piel(hud, ANCHO_HUD, ALTO_HUD, z=-0.01)
            hud.titulo = Text("", parent=hud, origin=(0, 0), position=(0, 0.025, -0.02), scale=escala_fuente(20),
                              color=rgb(estilo.COLOR_ACENTO), font=tipografia.fuente_piel(titulo=True))
            hud.texto = Text("", parent=hud, origin=(0, 0), position=(0, -0.022, -0.02), scale=escala_fuente(16),
                             color=rgb(estilo.COLOR_TEXTO))
            self.hud = hud
        self.hud.enabled = True
        self._mostrado = None

    def _pintar_hud(self):
        if self.hud is None or self.turno is None:
            return
        pedido = self.turno.pedido_actual()
        restante = self.turno.tiempo_restante()
        hechas, total = self.turno.entregas_hechas(), len(self.turno.pedidos)
        titulo = f"ENTREGA {min(hechas + 1, total)} DE {total}   ·   {texto_tiempo(restante)}"
        texto = "" if pedido is None else f"Lleva {texto_pedido(pedido)}"
        if (titulo, texto) == self._mostrado:
            return
        self._mostrado = (titulo, texto)
        self.hud.titulo.text = titulo
        self.hud.titulo.color = rgb(estilo.ESTADO_ERROR if restante <= SEGUNDOS_URGENTE else estilo.COLOR_ACENTO)
        self.hud.texto.text = texto.replace("<", "(")

    def _marcar_minimapa(self):
        try:
            from frontend import minimapa_calculos as mm
            marcadores = []
            if self.turno is not None:
                for i, pedido in enumerate(self.turno.pedidos[self.turno.entregas_hechas():],
                                           self.turno.entregas_hechas() + 1):
                    marcadores.append(mm.MarcadorMinimapa("objetivo", pedido.x, pedido.z, id=f"entrega-{i}",
                                                          etiqueta=f"{i}. {pedido.punto.destinatario}"))
            mm.registro().reemplazar_fuente(FUENTE_MINIMAPA, marcadores)
        except Exception as error:
            print(f"[entregas] minimapa sin marcas ({error})", file=sys.stderr)

    # -- Cada frame --

    def update(self):
        if self.turno is None:
            return
        escena = self.escena
        flujo = escena.flujo
        if flujo is None or flujo.partida_terminada() or flujo.jugador_activo() is not self.jugador:
            self._terminar()          # cambió el turno o terminó la partida: se cobra lo entregado
            return
        if not escena.enabled or escena.en_pausa or escena._cinematica:
            return
        self.turno.avanzar(time.dt)
        pedido = self.turno.llegar(float(self.jugador.x), float(self.jugador.z))
        if pedido is not None:
            self._al_entregar(pedido)
        if self.turno.terminado():
            self._terminar()
            return
        self._pintar_hud()

    def _al_entregar(self, pedido):
        self._sonar("mision_exito")
        self._marcar_minimapa()
        siguiente = self.turno.pedido_actual()
        texto = f"¡Entregado a {pedido.punto.destinatario}!"
        if siguiente is not None:
            texto += f" Ahora: {nombre_visible(siguiente.punto.lugar, corto=True)}."
        self.economia.aviso_temporal(texto)

    @staticmethod
    def _sonar(nombre):
        try:
            from frontend import audio
            audio.obtener().efecto(nombre, 0.8)
        except Exception:
            pass

    # Cierra el turno: cobra, quita marcas, destinatarios y HUD, y avisa del resultado. El jugador sigue en la moto.
    def _terminar(self):
        turno, jugador, puesto = self.turno, self.jugador, self.puesto
        self.turno = self.jugador = self.puesto = None
        if self.escena.destino_trabajo == self.destino_actual:
            self.escena.destino_trabajo = None
        if getattr(self.escena.hud, "destino_trabajo", None) == self.destino_actual:
            self.escena.hud.destino_trabajo = None
        if self.hud is not None:
            self.hud.enabled = False
        self._quitar_destinatarios()
        self._marcar_minimapa()
        if turno is None:
            return
        turno.cancelar()
        resultado = turno.resultado()
        try:
            from backend.logica.pago_trabajo import aplicar_resultado
            from backend.logica.perfil_economia import perfil_de
            mensaje = aplicar_resultado(perfil_de(jugador), puesto.trabajo, resultado)["mensaje"]
        except Exception as error:
            print(f"[entregas] no se pudo cobrar ({error})", file=sys.stderr)
            return
        hechas, total = resultado["entregas"], len(turno.pedidos)
        if hechas >= total:
            texto = f"Entregas completas: {mensaje}"
        elif hechas > 0:
            texto = f"Se acabó el tiempo ({hechas} de {total} entregas): {mensaje}"
        else:
            texto = "Se acabó el tiempo y no entregaste nada: sin paga"
        if hechas < total:
            self._sonar("mision_fallo")
        self._avisar(texto, "exito" if hechas >= total else "aviso", jugador)

    def _avisar(self, texto, tono, jugador):
        try:
            from frontend import notificaciones
            if notificaciones.activo():
                notificaciones.notificar_evento(self.escena, texto, tono=tono, jugador=jugador)
                return
        except Exception:
            pass
        self.economia.aviso_temporal(texto)

    def destruir(self):
        self._terminar()
        try:
            from frontend import minimapa_calculos as mm
            mm.registro().limpiar_fuente(FUENTE_MINIMAPA)
        except Exception:
            pass


# Crea el EntregasMundo de la economía (lo llama trabajo_mundo.instalar). None con la bandera apagada.
def instalar(economia):
    if not activo():
        return None
    entregas = EntregasMundo(economia)
    economia.entregas = entregas
    return entregas
