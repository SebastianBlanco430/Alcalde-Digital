# Adaptadores de los tutoriales de los minijuegos de verificar (Ursina). Cada adaptador construye la vista REAL del minijuego (la
# visual si su bandera está encendida, la de siempre si no: la misma que pide EscenaMinijuego) con un CASO DE DEMO propio y
# pequeño del guion, y sabe decirle al reproductor (frontend/tutorial_mision_vista.py) qué elemento señalar, cómo mandar una
# tecla y cómo FRENAR la acción equivocada en «Ahora tú» sin tocar la partida.
#
# SIN CONSECUENCIAS: la vista de demo recibe un callback propio (no el `al_terminar` de la escena), un `mision` de mentira que no
# es ninguna misión real y `es_tutorial = True` (la capa de efectos no registra estrellas ni medallas). No pasa por
# EscenaMinijuego.usados, ni por cerrar_lote, ni por el GameState.
#
# Interfaz del adaptador: crear_vista(padre, al_terminar) · elemento(vista, foco) · elemento_tecla(vista, k) ·
# poner_foco(vista, foco) · enviar_tecla(vista, k) · avanzar_juego(vista, dt) · avanzar_visual(vista, dt) ·
# armar_turno(vista, paso, al_acertar, al_fallar) · camara(vista, paso) · cerrar(vista).

import random
from types import SimpleNamespace



class _AzarFijo(random.Random):
    """El minijuego mezcla la carta de la misión entre las del caso con `randrange`: en la demo va siempre al final."""

    def randrange(self, inicio, stop=None, step=1):
        return (inicio if stop is None else stop) - 1

    def shuffle(self, lista):
        """No baraja: en la demo la respuesta correcta es siempre la primera y el guion sabe dónde está."""


def mision_de_demo(rumor, es_verdadera=True):
    """Una «misión» que no existe en ninguna partida: solo lo que las vistas leen (texto del rumor y veracidad)."""
    return SimpleNamespace(id="tutorial", rumor=rumor, es_verdadera=bool(es_verdadera), titulo="Tutorial", destino="",
                           pista="", tipo="verificar")


class AdaptadorMinijuego:

    def __init__(self, id_, guion):
        self.id = id_
        self.guion = guion
        self._originales = []                    # (objeto, nombre, valor) que se pusieron a mano: se devuelven al cerrar

    # -- Vista --

    def crear_vista(self, padre, al_terminar):
        from frontend.minijuegos import clase_de
        clase = clase_de(self.id)
        try:
            from frontend.minijuegos_visual import clase_visual
            clase = clase_visual(self.id, clase)
        except Exception:                        # noqa: BLE001  sin capa visual: la vista de siempre
            pass
        caso = self.caso()
        mision = self.mision()
        vista = clase(parent=padre)
        vista.es_tutorial = True                 # ANTES de empezar: la capa de efectos no registra logros
        vista.empezar({"caso": caso, "mision": mision, "azar": _AzarFijo(0), "al_terminar": al_terminar})
        self.preparar(vista)
        return vista

    def caso(self):
        return dict(self.guion["caso_demo"])

    def mision(self):
        return mision_de_demo(self.guion["caso_demo"].get("intro", "Práctica"))

    def preparar(self, vista):
        """Gancho: ajustes de la vista de demo tras construirla."""

    # -- Señalar y mandar entradas --

    def elemento(self, vista, foco):
        for nombre in ("focables", "filas", "tarjetas"):
            piezas = getattr(vista, nombre, None)
            if piezas and foco < len(piezas):
                return piezas[foco]
        return vista

    def elemento_tecla(self, vista, k):
        return None

    def poner_foco(self, vista, foco):
        vista.poner_foco(foco)

    def enviar_tecla(self, vista, k):
        vista.tecla(k)

    def avanzar_juego(self, vista, dt):
        vista.avanzar(dt)

    def avanzar_visual(self, vista, dt):
        if hasattr(vista, "avanzar_visual"):
            vista.avanzar_visual(dt)

    def camara(self, vista, paso):
        """Solo los tipos en el mundo 3D mueven la cámara; los minijuegos no."""

    def error(self, vista, paso):
        """El error a propósito de «error_demo» cuando es una acción sobre la vista (si es por el tiempo, no hace nada)."""

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        raise NotImplementedError

    def cerrar(self, vista):
        for objeto, nombre, valor in reversed(self._originales):
            try:
                setattr(objeto, nombre, valor)
            except Exception:                    # noqa: BLE001
                pass
        self._originales.clear()
        # La vista cuelga del tutorial: lo destruye quien cierra el tutorial (destruir_arbol del padre).

    def _sustituir(self, objeto, nombre, nuevo):
        self._originales.append((objeto, nombre, getattr(objeto, nombre)))
        setattr(objeto, nombre, nuevo)


class AdaptadorContrarreloj(AdaptadorMinijuego):
    """Tres noticias: una falsa (se frena), una cierta que se deja llenar (error a propósito) y una cierta para el turno."""

    def caso(self):
        demo = self.guion["caso_demo"]
        return {"intro": demo.get("intro", ""), "cartas": [dict(c) for c in demo["cartas"]], "es_verdadera": True}

    def mision(self):
        demo = self.guion["caso_demo"]
        return mision_de_demo(demo["mision"]["texto"], demo["mision"].get("veraz", True))

    def preparar(self, vista):
        """Tiempos de la demo (cortos y fijos) tomados del guion; la última noticia no se llena sola: sin presión de tiempo."""
        demo = self.guion["caso_demo"]
        tiempos = [c for c in demo["cartas"]] + [demo["mision"]]
        for carta, tiempo in zip(vista.partida.cartas, tiempos):
            carta["aparece"] = float(tiempo.get("aparece", carta["aparece"]))
            carta["ritmo"] = float(tiempo.get("ritmo", carta["ritmo"]))

    def elemento_tecla(self, vista, k):
        return {"f": vista.boton_frenar, "left arrow": vista.boton_frenar,
                "d": vista.boton_pasar, "right arrow": vista.boton_pasar}.get(k)

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        """Solo vale DEJAR PASAR la noticia señalada; FRENAR (o dejar pasar otra) no cambia la partida y se explica."""
        partida, foco = vista.partida, paso["foco"]
        dejar = partida.dejar_pasar

        def frenar(i):
            al_fallar()
            return False

        def dejar_pasar(i):
            if i != foco:
                al_fallar()
                return False
            hecho = dejar(i)
            if hecho:
                al_acertar()
            return hecho

        self._sustituir(partida, "frenar", frenar)
        self._sustituir(partida, "dejar_pasar", dejar_pasar)


class AdaptadorRastrear(AdaptadorMinijuego):
    """Tres saltos: el primero con un error a propósito («reenviado»), el segundo bien y el tercero lo hace el jugador."""

    def error(self, vista, paso):
        vista.elegir(paso["foco"])

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        """Solo vale la opción correcta del salto; las demás no cambian la partida (ni suman rodeos) y se explican."""
        partida = vista.partida
        elegir = partida.elegir

        def elegir_puerta(i):
            salto = partida.salto_actual()
            if salto is None or i != salto["correcta"]:
                al_fallar()
                return None
            resultado = elegir(i)
            if resultado == "bien":
                al_acertar()
            return resultado

        self._sustituir(partida, "elegir", elegir_puerta)


class _AdaptadorDeMarcas(AdaptadorMinijuego):
    """Comparar y Señales: se marcan zonas y se confirma. En «Ahora tú» solo vale confirmar con EXACTAMENTE las marcas correctas."""

    BOTON_CONFIRMAR, BOTON_NINGUNA = "boton_confirmar", "boton_igual"
    DECLARAR = "declarar_sin_diferencias"
    CORRECTAS = "alteradas"

    def error(self, vista, paso):
        vista.alternar(paso["foco"])

    def elemento_tecla(self, vista, k):
        nombre = {"c": self.BOTON_CONFIRMAR, "n": self.BOTON_NINGUNA}.get(k)
        return getattr(vista, nombre, None) if nombre else None

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        partida = vista.partida
        terminar = vista.terminar
        correctas = getattr(partida, self.CORRECTAS)

        def declarar():                                  # «no veo nada»: aquí sí hay pistas, así que no vale
            al_fallar()

        def terminar_puerta(resultado):
            if partida.confirmada and partida.marcadas == correctas():
                terminar(resultado)
                al_acertar()
                return
            partida.confirmada = False                   # se deshace la confirmación: la partida sigue abierta
            al_fallar()

        self._sustituir(partida, self.DECLARAR, declarar)
        self._sustituir(vista, "terminar", terminar_puerta)


class AdaptadorComparar(_AdaptadorDeMarcas):
    pass


class AdaptadorSenales(_AdaptadorDeMarcas):
    BOTON_NINGUNA = "boton_nada"
    DECLARAR = "declarar_sin_senales"
    CORRECTAS = "fallas"


class AdaptadorCronologia(AdaptadorMinijuego):
    """Tres mensajes que empiezan al revés (`orden_inicial` del guion). La mano mueve uno mal y luego bien; el jugador, el último."""

    def preparar(self, vista):
        orden = self.guion["caso_demo"].get("orden_inicial")
        if orden:
            vista.partida.orden[:] = list(orden)
            vista._pintar_filas()

    def elemento_tecla(self, vista, k):
        return vista.boton_comprobar if k == "c" else None

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        """«Comprobar» solo vale con todo en su puesto; si no, se deshace y se explica."""
        partida = vista.partida
        terminar = vista.terminar

        def terminar_puerta(resultado):
            if all(partida.en_su_puesto()):
                terminar(resultado)
                al_acertar()
                return
            partida.comprobado = False
            al_fallar()

        self._sustituir(vista, "terminar", terminar_puerta)


class AdaptadorChat(AdaptadorMinijuego):
    """Dos turnos del grupo. Sin presión de tiempo salvo la que se ve subir en «Mira»; la respuesta buena es la de valor 2."""

    def error(self, vista, paso):
        """Resalta en rojo la respuesta que entregaría el dato (sin responderla)."""
        try:
            vista.opciones[paso["foco"]].fijar_estado("incorrecta", "ENTREGA ESE DATO")
        except Exception:                        # noqa: BLE001  sin resaltado: el bocadillo ya lo explica
            pass

    def armar_turno(self, vista, paso, al_acertar, al_fallar):
        responder = vista.responder

        def responder_puerta(i):
            turno = vista.partida.turno_actual()
            if turno is None or not 0 <= i < len(turno["opciones"]) or turno["opciones"][i]["valor"] != 2:
                al_fallar()
                return
            responder(i)
            al_acertar()

        self._sustituir(vista, "responder", responder_puerta)


ADAPTADORES = {"contrarreloj": AdaptadorContrarreloj, "rastrear": AdaptadorRastrear, "comparar": AdaptadorComparar,
               "senales": AdaptadorSenales, "cronologia": AdaptadorCronologia, "chat": AdaptadorChat}
