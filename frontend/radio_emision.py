# Emisión de la Rádio Comunitária (Ursina, camera.ui): el globo con la línea va en el mismo componente de viñetas que las
# cinemáticas del periodista (cinematica_final.crear_vinetas); encima de la viñeta, una RADIO ANIMADA dibujada por código
# (RadioAnimada, cálculos en frontend/radio_animacion_calculos.py):
#   - cielo según el momento (vineta["radio_momento"]: noche estrellada con luna, amanecer con sol o atardecer del día 7)
#     y la silueta de la ladera con ventanas que se encienden;
#   - la radio respira, el altavoz late con la voz, la antena oscila con su luz, la aguja del dial busca la emisora y
#     salen ondas a los lados; arriba a la izquierda, el letrero «AO VIVO» parpadea;
#   - el texto aparece letra a letra (máquina de escribir).
# Con «reducir movimiento» (frontend/banderas_visuales.py) queda quieta y el texto sale entero. Paso intermedio: la idea
# es llevarla a 3D más adelante.
#
# Cada línea pasa sola a su tiempo de lectura (1,5 s + 0,06 s por carácter, mínimo 2,5 s); Espacio/clic adelantan y
# Escape (o «Saltar») salta la emisión entera. Solo dibuja: qué decir lo decide backend/logica/radio_guion.py y cuándo,
# frontend/radio_calculos.py. Bandera: ALCALDE_HILO_RADIO (ver radio_guion). Si la animación falla, queda la viñeta.
#
#   crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None) -> entidad (.terminada, .saltar())

import math
import sys

from frontend import radio_animacion_calculos as rac

ROTULOS = {"saltar": "Saltar", "continuar": "Seguir"}
TONO_RADIO = (196, 92, 60)
GRIS_ALTAVOZ = (40, 36, 40)
CENTRO_RADIO = (0.0, 0.07)              # respecto al centro de la viñeta
FRACCION_HABLANDO = 0.85                # parte del tiempo de la viñeta en que la locutora «habla»


def crear_emision(escena_mundo, vinetas, al_terminar, al_poner=None):
    from frontend.cinematica_final import crear_vinetas

    def guardia():
        # Escape pudo abrir la pausa debajo de la emisión: se cierra (como la cinemática del final).
        if getattr(escena_mundo, "en_pausa", False):
            escena_mundo.alternar_pausa(False)

    # La radio la dibuja RadioAnimada: las viñetas no llevan la figura fija.
    propias = [dict(v, figuras=[f for f in v.get("figuras", []) if f.get("tipo") != "radio"]) for v in vinetas]
    entidad = crear_vinetas(propias, al_terminar, segundos=None, guardia=guardia, rotulos=ROTULOS, al_poner=al_poner,
                            parent=escena_mundo.hud)
    try:
        RadioAnimada(entidad, propias)
    except Exception as error:                  # noqa: BLE001  sin animación: queda la radio fija de siempre
        print(f"[radio] animación omitida ({type(error).__name__}: {error})", file=sys.stderr)
        for v, original in zip(propias, vinetas):
            v["figuras"] = list(original.get("figuras", []))
    return entidad


def _malla_arco(desde, hasta, grosor=0.1, n=14):
    """Arco de radio 1 (de `desde` a `hasta` grados, 0 = derecha) con `grosor` relativo: se escala con la entidad."""
    from ursina import Mesh
    vertices, triangulos = [], []
    for k in range(n + 1):
        a = math.radians(desde + (hasta - desde) * k / n)
        c, s = math.cos(a), math.sin(a)
        vertices += [(c * (1 - grosor / 2), s * (1 - grosor / 2), 0), (c * (1 + grosor / 2), s * (1 + grosor / 2), 0)]
        if k:
            i = 2 * k
            triangulos += [i - 2, i - 1, i, i - 1, i + 1, i]
    return Mesh(vertices=vertices, triangles=triangulos, mode="triangle")


def _clase():
    from ursina import Entity, Text, color, time

    from frontend import banderas_visuales, estilo
    from frontend.componentes import escala_fuente, rgb
    from frontend.cinematica_final import Y_VINETA

    def rgba(tono, alfa):
        return color.rgba(tono[0] / 255, tono[1] / 255, tono[2] / 255, max(0.0, min(1.0, alfa)))

    class _RadioAnimada(Entity):

        def __init__(self, vinetas_entidad, vinetas):
            super().__init__(parent=vinetas_entidad, position=(0, Y_VINETA, -0.012))
            self.vinetas_entidad, self.vinetas = vinetas_entidad, vinetas
            self.reducir = bool(banderas_visuales.reducir_movimiento())
            self.t = 0.0
            self._indice = None
            self._momento = None
            self._texto_lleno, self._t_texto = "", 0.0
            self.fondo = Entity(parent=self)            # cielo, astro, estrellas y silueta: se rehace por momento
            self._estrellas, self._ventanas, self.sol = [], [], None
            self._sol_y0, self._t_momento = 0.0, 0.0
            self._crear_radio()
            self._crear_letrero()
            self._crear_ondas()

        # -- Construcción --

        def _quad(self, padre, tono, x, y, ancho, alto, z=0.0, borde=False, alfa=1.0):
            if borde:
                Entity(parent=padre, model="quad", color=rgb(estilo.TINTA), position=(x, y, z + 0.0004),
                       scale=(ancho + 0.012, alto + 0.012))
            return Entity(parent=padre, model="quad", color=rgba(tono, alfa), position=(x, y, z), scale=(ancho, alto))

        def _disco(self, padre, tono, x, y, diametro, z=0.0, borde=False):
            if borde:
                Entity(parent=padre, model="circle", color=rgb(estilo.TINTA), position=(x, y, z + 0.0004),
                       scale=diametro + 0.012)
            return Entity(parent=padre, model="circle", color=rgb(tono), position=(x, y, z), scale=diametro)

        def _crear_fondo(self, momento):
            for hijo in list(self.fondo.children):
                hijo.enabled = False
                from ursina import destroy
                destroy(hijo)
            self._estrellas, self._ventanas, self.sol = [], [], None
            bandas, astro, con_estrellas = rac.cielo(momento)
            for y, alto, tono in bandas:
                self._quad(self.fondo, tono, 0, y, rac.ANCHO, alto + 0.001, z=0.006)
            if con_estrellas:
                for x, y, tam, fase in rac.estrellas():
                    e = self._quad(self.fondo, (255, 248, 220), x, y, tam, tam, z=0.0045)
                    self._estrellas.append((e, fase))
            if astro["tipo"] == "luna":
                self._disco(self.fondo, astro["color"], astro["x"], astro["y"], astro["r"] * 2, z=0.004)
                # El «mordisco» de la luna, del color de la banda de cielo que tiene detrás
                detras = min(bandas, key=lambda banda: abs(banda[0] - astro["y"]))[2]
                self._disco(self.fondo, detras, astro["x"] + astro["r"] * 0.55,
                            astro["y"] + astro["r"] * 0.3, astro["r"] * 1.8, z=0.0038)
            else:
                self.sol = self._disco(self.fondo, astro["color"], astro["x"], astro["y"], astro["r"] * 2, z=0.004)
                self._sol_y0, self._t_momento = astro["y"], 0.0
            de_noche = momento in ("noche", "puente")
            casa = (16, 18, 38) if momento == "noche" else (60, 34, 64) if momento == "puente" else (122, 86, 96)
            base = -rac.ALTO / 2
            for k, (x, ancho, alto) in enumerate(rac.silueta()):
                self._quad(self.fondo, casa, x, base + alto / 2, ancho, alto, z=0.003)
                if de_noche and k % 2 == 0:
                    v = self._quad(self.fondo, (255, 214, 102), x, base + alto * 0.62, 0.014, 0.016, z=0.0028)
                    self._ventanas.append((v, k * 1.7))
            # La repisa donde está la radio
            self._quad(self.fondo, (92, 64, 44), 0, CENTRO_RADIO[1] - 0.105, 0.5, 0.022, z=0.002, borde=True)

        def _crear_radio(self):
            self.radio = Entity(parent=self, position=(CENTRO_RADIO[0], CENTRO_RADIO[1], 0))
            r = self.radio
            # Antena: pivote abajo, oscila; luz en la punta
            self.antena = Entity(parent=r, position=(0.08, 0.09, 0.001), rotation_z=28)
            Entity(parent=self.antena, model="quad", color=rgb((200, 200, 210)), position=(0, 0.05, 0),
                   scale=(0.007, 0.1))
            self.luz = Entity(parent=self.antena, model="circle", color=rgb(estilo.ESTADO_ERROR), position=(0, 0.1, -0.001),
                              scale=0.016)
            oscuro = tuple(int(c * 0.75) for c in TONO_RADIO)
            self._quad(r, oscuro, 0, 0.1, 0.16, 0.022, z=0.0005, borde=True)          # asa
            self.cuerpo = self._quad(r, TONO_RADIO, 0, 0, 0.34, 0.18, z=0.0, borde=True)
            self._disco(r, GRIS_ALTAVOZ, -0.07, -0.005, 0.12, z=-0.001, borde=True)
            self.cono = self._disco(r, (70, 64, 70), -0.07, -0.005, 0.085, z=-0.002)
            self.centro_cono = self._disco(r, (58, 52, 58), -0.07, -0.005, 0.045, z=-0.003)
            self._quad(r, estilo.PAPEL, 0.085, 0.03, 0.11, 0.05, z=-0.001, borde=True)  # dial
            self.aguja = self._quad(r, estilo.ESTADO_ERROR, 0.07, 0.03, 0.004, 0.04, z=-0.002)
            for dx in (0.06, 0.11):
                self._disco(r, GRIS_ALTAVOZ, dx, -0.04, 0.03, z=-0.001)

        def _crear_letrero(self):
            x, y = -rac.ANCHO / 2 + 0.13, rac.ALTO / 2 - 0.05
            self.letrero = Entity(parent=self, position=(x, y, -0.005))
            self._quad(self.letrero, estilo.ESTADO_ERROR, 0, 0, 0.19, 0.05, borde=True)
            self.punto = self._disco(self.letrero, estilo.PAPEL, -0.068, 0, 0.018, z=-0.001)
            Text("AO VIVO", parent=self.letrero, origin=(-0.5, 0), position=(-0.05, 0.001, -0.001),
                 scale=escala_fuente(15), color=rgb(estilo.PAPEL))

        def _crear_ondas(self):
            self.ondas = []
            for lado in (-1, 1):
                for _ in range(rac.ONDAS_POR_LADO):
                    desde, hasta = (130, 230) if lado < 0 else (-50, 50)
                    e = Entity(parent=self, model=_malla_arco(desde, hasta), color=rgba(estilo.PAPEL, 0.0),
                               position=(CENTRO_RADIO[0] + 0.17 * lado, CENTRO_RADIO[1], 0.001))
                    self.ondas.append(e)

        # -- Frame --

        def update(self):
            ent = self.vinetas_entidad
            if getattr(ent, "terminada", True):
                return
            dt = min(time.dt, 0.1)
            self.t += dt
            indice = getattr(ent, "indice", -1)
            if not (0 <= indice < len(self.vinetas)):
                return
            vineta = self.vinetas[indice]
            if indice != self._indice:
                self._indice = indice
                self._texto_lleno, self._t_texto = ent.texto.text, 0.0
                momento = vineta.get("radio_momento", "noche")
                if momento != self._momento:
                    self._momento = momento
                    self._crear_fondo(momento)
            self._escribir(ent, dt)
            hablando = getattr(ent, "_t", 0.0) < FRACCION_HABLANDO * float(vineta.get("segundos", 3.0))
            self._animar(rac.voz(self.t, hablando) if not self.reducir else 0.0)

        def _escribir(self, ent, dt):
            total = len(self._texto_lleno)
            if self.reducir:
                visibles = total
            else:
                self._t_texto += dt
                visibles = rac.letras_visibles(self._t_texto, total)
            if ent.texto.text != self._texto_lleno[:visibles]:
                ent.texto.text = self._texto_lleno[:visibles]

        def _animar(self, voz):
            t = self.t
            if self.reducir:
                for e in self.ondas:
                    e.color = rgba(estilo.PAPEL, 0.0)
                return
            self.radio.y = CENTRO_RADIO[1] + 0.004 * math.sin(t * 2.2)
            self.radio.scale = (1.0 - 0.012 * voz, 1.0 + 0.02 * voz)
            self.cono.scale = 0.085 * (1.0 + 0.12 * voz)
            self.centro_cono.scale = 0.045 * (1.0 - 0.15 * voz)
            self.antena.rotation_z = 28 + 5 * math.sin(t * 2.1)
            self.luz.enabled = (t % 0.9) < 0.55
            self.aguja.x = 0.085 + 0.03 * math.sin(t * 0.6) + 0.003 * math.sin(t * 7.0)
            self.punto.enabled = (t % 1.2) < 0.75
            ondas = rac.ondas(t, voz)
            for k, e in enumerate(self.ondas):
                radio, alfa = ondas[k % rac.ONDAS_POR_LADO]
                e.scale = radio
                e.color = rgba(estilo.PAPEL, alfa * 0.85)
            for e, fase in self._estrellas:
                e.color = rgba((255, 248, 220), rac.brillo_estrella(t, fase))
            for v, fase in self._ventanas:
                v.enabled = math.sin(t * 0.5 + fase) > -0.6
            if self.sol is not None:
                self._t_momento += min(time.dt, 0.1)
                self.sol.y = rac.altura_sol(self._momento, self._sol_y0, self._t_momento)

    return _RadioAnimada


_CLASE = {}


def RadioAnimada(vinetas_entidad, vinetas):    # noqa: N802  se usa como una clase
    if "clase" not in _CLASE:
        _CLASE["clase"] = _clase()
    return _CLASE["clase"](vinetas_entidad, vinetas)
