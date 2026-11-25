# Tutorial de los trabajos por motor (atender, secuencia, barra, ritmo) en la escena real de trabajo (EscenaTrabajo). Un solo
# adaptador para los cuatro: «atender» sale una sola vez para los cuatro puestos (panadería, súper, feria, bar).
#
# SIN CONSECUENCIAS Y ANTES DE EMPEZAR EL TURNO. El tutorial se abre en `EscenaTrabajo.al_entrar`, antes de la pantalla «Tu turno»:
# el turno real todavía no existe en pantalla ni corre su reloj. Durante la demo la escena trabaja con un trabajo de práctica
# (el mismo puesto, con pagos y fatiga a 0 y 1000 s de duración), `jugador=None` (no se lee ningún perfil) y `al_terminar=None`
# (no hay paga, ni fatiga, ni libro de cuentas, ni llamada a ConexionFlujo.terminar_trabajo). Al cerrar se devuelve a la escena su
# turno real y se enseña la pantalla «Tu turno» de siempre. Escape de la escena (abandonar el turno) no hace nada mientras dura.
#
# TIEMPO. En «Mira» la escena no avanza sola: el guion decide cuánto tiempo de juego pasa (`avanza`, o `hasta`: fuera/dentro de la
# zona de la barra, o «nota» = hasta que la siguiente nota del taller llega al recuadro). En «Ahora tú» sí corre (la barra se mueve,
# las notas viajan), pero con 1000 s: no hay presión.
#
# Pasos: «tecla» con k «auto» = la jugada correcta del momento; «error_demo» = una jugada equivocada a propósito.

import dataclasses

from backend.logica.taller_ritmo import Nota, TurnoRitmo
from backend.logica.trabajos import ATENDER, BARRA, RITMO, SECUENCIA, TurnoTrabajo

_AUSENTE = object()
SEMILLA_DEMO = 7
LLEGADA_LENTA_S = (3.0, 6.5)           # «2 flechas lentas»: segundos desde el inicio del turno de práctica


def _ritmo_flechas():
    """Las flechas de la demo del taller van tan rápidas y tan seguidas como en el turno de verdad
    (ALCALDE_TALLER3D_VELOCIDAD y ALCALDE_TALLER3D_CADENCIA); con el taller 3D apagado, como siempre."""
    from frontend import taller3d_calculos
    if not taller3d_calculos.activo():
        return {}
    return {"velocidad": taller3d_calculos.velocidad_flechas(), "cadencia": taller3d_calculos.cadencia_flechas()}


class AdaptadorTrabajo:

    def __init__(self, id_, guion, contexto=None):
        self.id = id_
        self.guion = guion
        ctx = contexto or {}
        self.escena = ctx["escena"]
        self.real = ctx["trabajo"]
        self._guardado = None
        self._sobrescritos = {}
        self._practica = False
        self._al_acertar = self._al_fallar = None
        self._hechos = 0
        self._pendientes = 0

    # -- Vista: la escena real, con un trabajo de práctica --

    def crear_vista(self, padre, al_terminar):
        from frontend.escenas import escena_trabajo as et
        escena = self.escena
        self._et = et
        self._guardado = {"jugador": escena.jugador, "trabajo": escena.trabajo, "turno": escena.turno,
                          "al_terminar": escena._al_terminar, "feedback": escena._feedback, "n_pedido": escena._n_pedido}
        demo = dataclasses.replace(self.real, duracion_s=1000.0, pago_base=0, pago_max=0, fatiga=0)
        escena._limpiar()
        escena.jugador, escena.trabajo, escena._al_terminar = None, demo, None
        escena.turno = (TurnoRitmo(demo, SEMILLA_DEMO, **_ritmo_flechas()) if demo.motor == RITMO
                        else TurnoTrabajo(demo, SEMILLA_DEMO))
        escena._n_pedido, escena._feedback = 0, ("", True, 0.0)
        self._preparar_turno(escena.turno)
        escena._construir_estatico()
        escena.fase = et.JUGANDO
        self._sobrescribir("avanzar", lambda dt: None)          # en «Mira» el tiempo lo pone el guion
        self._sobrescribir("entrada", lambda key: False)        # Escape (abandonar) y demás: nada
        escena._refrescar()
        return escena

    def _sobrescribir(self, nombre, nuevo):
        """Pone `nuevo` como atributo de la instancia guardando lo que hubiera (la decoración visual envuelve estos métodos)."""
        escena = self.escena
        self._sobrescritos.setdefault(nombre, escena.__dict__.get(nombre, _AUSENTE))
        setattr(escena, nombre, nuevo)

    def _restaurar(self, nombre):
        if nombre not in self._sobrescritos:
            return
        previo = self._sobrescritos.pop(nombre)
        if previo is _AUSENTE:
            self.escena.__dict__.pop(nombre, None)
        else:
            setattr(self.escena, nombre, previo)

    def _preparar_turno(self, turno):
        o = self.real.opciones
        if self.real.motor == ATENDER:
            turno._pedido, turno._entregado = {o[0]: 2, o[1]: 1}, {}       # «2 pan + 1 café»
        elif self.real.motor == SECUENCIA:
            turno._secuencia, turno._indice = [o[0], o[-1], o[1]], 0
        elif self.real.motor == BARRA:
            turno._centro = 0.5
        else:
            turno.notas = turno.notas[:4]                                  # 4 notas: 3 bien y un error a propósito

    # -- La jugada correcta, la equivocada y su tecla --

    def _jugada_correcta(self):
        t, motor = self.escena.turno, self.real.motor
        if motor == ATENDER:
            producto = next(p for p, n in t.pedido().items() if t.entregado().get(p, 0) < n)
            return self.real.opciones.index(producto) + 1
        if motor == SECUENCIA:
            return t.secuencia()[t.progreso()]
        if motor == RITMO:
            return t.siguiente().direccion
        return None                                                        # BARRA: Espacio

    def _jugada_equivocada(self):
        t, motor = self.escena.turno, self.real.motor
        if motor == ATENDER:
            fuera = [i + 1 for i, p in enumerate(self.real.opciones) if p not in t.pedido()]
            return fuera[0] if fuera else 1
        if motor in (SECUENCIA, RITMO):
            esperada = self._jugada_correcta()
            return next(d for d in self.real.opciones if d != esperada)
        return None

    def _de_la_tecla(self, k):
        et = self._et
        if self.real.motor == ATENDER:
            return et.TECLAS_PRODUCTO.get(k)
        if self.real.motor in (SECUENCIA, RITMO):
            return et.TECLAS_DIRECCION.get(k)
        return None if k == "space" else False

    # -- Tiempo de juego del paso --

    def al_paso(self, vista, paso):
        """Cuánto tiempo de juego hay que avanzar en este paso si el guion dice «hasta»; None = lo que diga «avanza»."""
        hasta = paso.get("hasta")
        if hasta is None or self._practica:
            return None
        t = self.escena.turno
        if self.real.motor == BARRA and hasta in ("fuera", "dentro"):
            return self._tiempo_hasta_barra(t, hasta == "dentro")
        if self.real.motor == RITMO and hasta == "nota":
            nota = t.siguiente()
            return 0.0 if nota is None else max(0.0, nota.llegada - t.tiempo())
        return None

    @staticmethod
    def _tiempo_hasta_barra(turno, dentro):
        """Segundos que faltan para que la marca esté dentro (o fuera) de la zona verde (se simula sin tocar el turno)."""
        ini, fin = turno.zona_barra()
        t0 = turno.tiempo()
        for i in range(1, 2000):
            turno._t = t0 + i * 0.01
            esta = ini <= turno.posicion_barra() <= fin
            if esta == dentro:
                turno._t = t0
                return i * 0.01 + (0.05 if dentro else 0.0)
        turno._t = t0
        return 0.0

    def avanzar_juego(self, vista, dt):
        escena = self.escena
        escena.turno.avanzar(dt)
        escena._refrescar()
        # la animación de la vista (martillazo, flechas que se encogen o caen y se borran) avanza con el juego; sin esto
        # las flechas ya resueltas se quedaban congeladas en el carril y se solapaban con las siguientes
        animar = getattr(escena._vista, "animar", None)
        if animar is not None:
            animar(dt)

    def avanzar_visual(self, vista, dt):
        """En la práctica de ritmo: si una nota se pasó, llega otra (el jugador no se queda sin intentos)."""
        if not self._practica or self.real.motor != RITMO or self._hechos >= self._pendientes:
            return
        t = self.escena.turno
        if t.siguiente() is None:
            t.notas.append(Nota(len(t.notas), self.real.opciones[len(t.notas) % len(self.real.opciones)], t.tiempo() + 3.0))

    # -- Señalar y entradas --

    def elemento(self, vista, foco):
        escena = self.escena
        if self.real.motor == ATENDER and foco < len(escena._tiles):
            return escena._tiles[foco]
        if self.real.motor == BARRA and escena._barra:
            return escena._barra.get("zona")
        return escena.juego

    def elemento_tecla(self, vista, k):
        return None

    def poner_foco(self, vista, foco):
        """Sin foco de teclado."""

    def enviar_tecla(self, vista, k):
        escena = self.escena
        if self._practica:
            entrada = self._de_la_tecla(k)
            if entrada is False or (entrada is None and self.real.motor != BARRA):
                return
            self._jugada_de_practica(entrada)
            return
        entrada = self._jugada_correcta() if k == "auto" else self._de_la_tecla(k)
        if entrada is False:
            return
        escena.accion(entrada)

    def error(self, vista, paso):
        if self.real.motor == BARRA:
            self.escena.accion(None)                      # la marca está fuera de la zona (el guion esperó «hasta fuera»)
        else:
            self.escena.accion(self._jugada_equivocada())

    def camara(self, vista, paso):
        """Sin cámara."""

    # -- «Ahora tú» --

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        escena, o, t = self.escena, self.real.opciones, self.escena.turno
        self._al_acertar, self._al_fallar = al_acertar, al_fallar
        self._hechos = 0
        if self.real.motor == ATENDER:
            t._pedido, t._entregado = {o[3]: 1}, {}                       # un pedido de 1 producto
            self._pendientes = 1
        elif self.real.motor == SECUENCIA:
            t._secuencia, t._indice = [o[2], o[1]], 0                      # una secuencia de 2
            self._pendientes = 2
        elif self.real.motor == BARRA:
            self._pendientes = 1
        else:
            ahora = t.tiempo()
            t.notas = [Nota(i, o[(i + 1) % len(o)], ahora + llegada) for i, llegada in enumerate(LLEGADA_LENTA_S)]
            self._pendientes = len(t.notas)
        escena._firma_juego = None
        self._restaurar("avanzar")                                         # ahora el tiempo corre (hay 1000 s: sin presión)
        self._practica = True
        escena._refrescar()

    def _jugada_de_practica(self, entrada):
        """Solo vale la jugada correcta; la otra no cambia el turno y se explica."""
        escena, t, motor = self.escena, self.escena.turno, self.real.motor
        if motor == BARRA:
            ini, fin = t.zona_barra()
            if not ini <= t.posicion_barra() <= fin:
                self._al_fallar()
                return
        elif motor == RITMO:
            nota = t.siguiente()
            if nota is None or not t.en_ventana(nota):
                return                                                     # fuera del recuadro no cuenta: se espera la nota
            if entrada != nota.direccion:
                self._al_fallar()
                return
        elif entrada != self._jugada_correcta():
            self._al_fallar()
            return
        if escena.accion(entrada):
            self._hechos += 1
            if self._hechos >= self._pendientes:
                self._al_acertar()
            elif motor != RITMO:
                self._al_fallar("Muy bien: sigue con el resto.", True)

    # -- Cierre: la escena vuelve a su turno real y enseña «Tu turno» --

    def cerrar(self, vista):
        escena, g = self.escena, self._guardado
        if g is None:
            return
        self._guardado = None
        self._practica = False
        for nombre in list(self._sobrescritos):
            self._restaurar(nombre)
        escena._limpiar()
        escena.jugador, escena.trabajo, escena.turno = g["jugador"], g["trabajo"], g["turno"]
        escena._al_terminar, escena._feedback, escena._n_pedido = g["al_terminar"], g["feedback"], g["n_pedido"]
        escena._flash, escena._firma_juego = {}, None
        escena._construir_estatico()


ADAPTADORES = {"trabajo_atender": AdaptadorTrabajo, "trabajo_secuencia": AdaptadorTrabajo, "trabajo_barra": AdaptadorTrabajo,
               "trabajo_ritmo": AdaptadorTrabajo}

