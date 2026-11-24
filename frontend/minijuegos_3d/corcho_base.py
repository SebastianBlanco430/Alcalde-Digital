# Base común de la familia CORCHO (Rastrear y Cronología en 3D, Ursina). Sobre Minijuego3D (infra-3d) añade:
#   - el personaje en REPOSO a la izquierda del corcho, fuera de su marco (no tapa nada de lo que se lee); solo se acerca a
#     una pieza durante un gesto y vuelve (volver_al_reposo);
#   - la toma de juego: encuadra el corcho entero + el hueco del personaje + la franja de la ayuda (corcho ~78 % del alto
#     a 16:9: el texto mide más que con la toma de infra), de frente y un poco al costado;
#   - la tira del rumor con la etiqueta roja «RUMOR» (el texto sale de la misión, como en la cabecera de la vista 2D);
#   - el sello final (VERIFICADO / BULO) sobre el rumor si la vista 2D lo pone.
# Medidas en corcho_calculos (puro, con tests).

import math

from ursina import Entity

from frontend.minijuegos_3d import camaras_calculos as ccal
from frontend.minijuegos_3d import corcho_calculos as cc
from frontend.minijuegos_3d import corcho_piezas as cp
from frontend.minijuegos_3d import papel_3d, raton
from frontend.minijuegos_3d.base import Minijuego3D
from frontend.minijuegos_3d.camaras import aspecto_ventana


class Corcho3D(Minijuego3D):

    FAMILIA = "corcho"

    def _corcho(self):
        return self.set.anclas["corcho"]

    # -- Personaje --

    def _colocar_personaje(self):
        corcho = self.set.anclas.get("corcho")
        if corcho is not None:
            self.set.pie = self.punto_reposo(corcho)
        super()._colocar_personaje()

    def al_terminar_entrada(self):
        """Entrada animada (sesión B): tocó la nota junto al borde izquierdo; suelta la mano y va a su reposo (como hoy
        tras un gesto)."""
        if self._corcho() is not None:
            self.volver_al_reposo()

    @staticmethod
    def punto_reposo(corcho, atras=0.0):
        x, dist = cc.reposo(corcho.ancho, corcho.alto)
        pie = corcho.mundo(x, 0, -dist - atras)
        frente = corcho.mundo(x, 0, 0)
        return (pie[0], pie[2], math.degrees(math.atan2(frente[0] - pie[0], frente[2] - pie[2])))

    # Los pasos frente al corcho se dan SIN girar el cuerpo (de lado, mirando siempre al corcho): con el giro de
    # poses_3d.caminar_a (rumbo de la marcha y, al llegar, de golpe el rumbo final) el brazo que sostiene una pieza
    # barría el corcho en el frame del giro (medido: la muñeca 2,8 cm DETRÁS del plano durante un frame).

    def _rumbo_al_corcho(self):
        n = self.normal
        return math.degrees(math.atan2(-n[0], -n[2]))

    def _paso_de_lado(self, x, z, duracion):
        self.poses.caminar_a(x, z, self._rumbo_al_corcho(), duracion=duracion, girar=False)

    def volver_al_reposo(self, atras=0.0):
        """Suelta la mano y vuelve al reposo (de lado, mirando al corcho). Devuelve la duración del paseo."""
        p = self.poses
        p.soltar_mano("d")
        x, z, _ = self.punto_reposo(self._corcho(), atras)
        base = self.set.personaje.world_position
        dur = min(1.0, 0.35 + math.hypot(x - base[0], z - base[2]) * 0.45)
        self._paso_de_lado(x, z, dur)
        return dur

    DURACION_RETIRADA = 0.45       # s: al salir el resultado se aparta deprisa (nada suyo tapa lo que hay que leer)

    def retirarse_ya(self, atras=0.0):
        """Al salir el resultado: suelta las dos manos y vuelve al reposo en DURACION_RETIRADA s (si ya está ahí, no se
        mueve). Antes terminaba los gestos con calma y durante 2-3 s tapaba «Origen: …» y el banner (retoques 23-nov, D1).
        Devuelve la duración del paso (0 si no se movió)."""
        p = self.poses
        p.soltar_mano("d")
        p.soltar_mano("i")
        x, z, _ = self.punto_reposo(self._corcho(), atras)
        base = self.set.personaje.world_position
        if math.hypot(x - base[0], z - base[2]) < 0.03 and getattr(p, "_camino", None) is None:
            return 0.0
        self._paso_de_lado(x, z, self.DURACION_RETIRADA)
        return self.DURACION_RETIRADA

    def caminar_cerca(self, punto, duracion_max=0.9, duracion=None):
        """Pasos de lado hasta quedar frente a `punto` (mundo) del corcho, con la mano derecha delante de él (como
        poses_3d.acercarse_a, sin girar). Devuelve la duración."""
        n = self.normal
        largo = math.hypot(n[0], n[2]) or 1.0
        nx, nz = n[0] / largo, n[2] / largo
        derecha = (-nz, nx)                       # derecha de quien mira al corcho (f = -n; derecha = (f.z, -f.x))
        x = punto[0] + nx * cc.ACERCARSE_DISTANCIA - derecha[0] * 0.18
        z = punto[2] + nz * cc.ACERCARSE_DISTANCIA - derecha[1] * 0.18
        base = self.set.personaje.world_position
        dur = duracion if duracion is not None else min(duracion_max, 0.3 + math.hypot(x - base[0], z - base[2]) * 0.4)
        self._paso_de_lado(x, z, dur)
        return dur

    # -- Cámara --

    def toma_juego(self):
        corcho = self._corcho()
        e = cc.encuadre(corcho.ancho, corcho.alto)
        d = cc.distancia_camara(e["ancho"], e["alto"], ccal.FOV_JUEGO, aspecto_ventana())
        s = cc.escala(corcho.alto)
        dx, dy = e["centro"]
        return {"position": corcho.mundo(dx + 0.12 * s, dy + 0.05 * s, -d), "target": corcho.mundo(dx, dy, 0),
                "fov": ccal.FOV_JUEGO}

    # -- Piezas comunes --

    def preparar_corcho(self):
        corcho = self._corcho()
        self.raiz = Entity(parent=corcho.entidad, ignore=True)
        d = corcho.datos_toma()
        self.normal = d["normal"]
        self.poses.limitar(d["centro"], self.normal)
        self.reposo = self.set.pie
        self.sello_final = None
        self.hueco_sello = None
        if self.set.nombre == "sala_investigacion":
            self._tapar_zocalo(corcho)
        return corcho

    def _tapar_zocalo(self, corcho):
        """En la sala de investigación el zócalo de la pared (sets._habitacion: y 0,96-1,04, 1,25 cm delante del corcho)
        cruza la franja de abajo del corcho por DELANTE. Se tapa con una tira del mismo corcho 1 mm delante del zócalo
        (petición a infra en el informe). Ningún papel de la familia baja a esa franja."""
        alto_mundo = corcho.mundo(0, 0, 0)[1]
        y0, y1 = 0.955 - alto_mundo, 1.045 - alto_mundo
        abajo = -corcho.alto / 2
        if y0 > abajo + 0.25 or y1 < abajo:
            return
        y0 = max(y0, abajo)
        from frontend.minijuegos_3d.sets import CORCHO
        cp.rect(self.raiz, (0, (y0 + y1) / 2), (corcho.ancho, y1 - y0), CORCHO, z=-0.0137, iluminado=False)

    def tira_rumor(self, rect, ancho_etiqueta, alto_linea):
        """Tira del rumor (arriba) con la etiqueta roja «RUMOR». Devuelve el papel; el texto queda en .texto."""
        s = cc.escala(self._corcho().alto)
        cx, cy, w, h = rect
        mj = self.minijuego
        rumor = getattr(mj.mision, "rumor", "") or (mj.caso or {}).get("intro", "")
        cadena = f"«{rumor}»"
        ancho_txt = w - ancho_etiqueta - 0.06 * s
        n = cp.lineas(cadena, alto_linea, ancho_txt, True)
        alto = max(h, cp.alto_texto(n, alto_linea) + 0.03 * s)
        tira = papel_3d.papel(self.raiz, w, alto, posicion=(cx, cy + (h - alto) / 2), giro=-0.3)
        etiqueta = papel_3d.papel(tira, ancho_etiqueta, alto - 0.018 * s,
                                  posicion=(-w / 2 + ancho_etiqueta / 2 + 0.01 * s, 0), tono=cp.ROJO_OSCURO)
        cp.texto_centrado(etiqueta, "RUMOR", cc.LINEA_TITULO * s, ancho_etiqueta, 0.0, cp.BLANCO, negrita=True)
        x0 = -w / 2 + ancho_etiqueta + 0.03 * s
        tira.texto = cp.texto(tira, cadena, alto_linea, ancho_txt, cp.TINTA, (x0, cp.alto_texto(n, alto_linea) / 2),
                              negrita=True)
        tira.fin_texto = x0 + cp.ancho_texto(cadena, alto_linea, ancho_txt, True)
        self.tira = tira
        return tira

    def sellar_rumor(self, resultado):
        """El sello del veredicto (el texto lo decide la vista 2D: texto_sello_final) sobre la tira del rumor."""
        try:
            texto = self.minijuego.texto_sello_final(resultado)
        except Exception:                # noqa: BLE001  (vista 2D sin capa visual: sin sello)
            texto = None
        tira = getattr(self, "tira", None)
        if not texto or tira is None or self.sello_final is not None:
            return
        s = cc.escala(self._corcho().alto)
        tono = cp.VERDE if "VERIF" in str(texto).upper() else cp.ROJO
        linea = 0.034 * s
        ancho = cp.ancho_sello(str(texto), linea)
        x = getattr(tira, "fin_texto", tira.ancho / 2) + 0.03 * s + ancho / 2
        if x + ancho / 2 <= tira.ancho / 2 - 0.01 * s:              # cabe en la tira, después del texto: no lo tapa
            self.sello_final = cp.sello(tira, str(texto), (x, 0.0), tono, linea, giro=-6, capa=4)
        elif self.hueco_sello is not None:                          # en el hueco reservado del corcho
            self.sello_final = cp.sello(self.raiz, str(texto), self.hueco_sello, tono, linea, giro=-8, capa=4)
        else:                                                       # sobre la etiqueta «RUMOR» (el texto queda libre)
            self.sello_final = cp.sello(tira, str(texto), (-tira.ancho / 2 + 0.12 * s, -0.01 * s), tono, linea,
                                        giro=-8, capa=4)

    def al_resultado(self, resultado):
        # unos frames después: el frame del resultado ya es el más pesado de la vista 2D (terminar, banner de la escena)
        self._sello_pendiente = [resultado, 3]

    def avanzar_sello(self):
        """Lo llaman las subclases en avanzar_3d: pone el sello final cuando toca."""
        pendiente = getattr(self, "_sello_pendiente", None)
        if pendiente is None:
            return
        pendiente[1] -= 1
        if pendiente[1] <= 0:
            self._sello_pendiente = None
            self.sellar_rumor(pendiente[0])

    def destruir(self):
        raton.desvincular()
        cp.destruir(getattr(self, "raiz", None))
