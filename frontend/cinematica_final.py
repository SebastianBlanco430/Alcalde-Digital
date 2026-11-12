# Cinemática del final (docs/PLAN_FINALES_HISTORIA.md §2.7): viñetas 2D como páginas de cómic, a pantalla completa en
# camera.ui. Cada viñeta (backend/datos/finales_historia.json, «cinematicas») trae un color de fondo, unas «figuras» hechas
# con quads y círculos planos con borde de tinta (edificios, gente, fuego, banderines, podio...), un título y un texto.
# Fundido a negro entre viñetas (frontend/fundido.py). Espacio, Enter o clic avanzan; Escape (o «Saltar») la salta entera.
# Cada viñeta pasa sola a los `segundos` s. Al terminar llama a `al_terminar()` UNA vez.
#
# Solo dibuja: qué final toca lo decide el backend (flujo.resumen_final()["final"]); la lanza frontend/registro_reloj.py.

from backend.logica import etapas_final
from frontend.azar_fijo import azar_de
from frontend.fundido import Fundido

SEGUNDOS_VINETA = 4.0
SEGUNDOS_FUNDIDO = 0.4           # total (mitad a negro, mitad de vuelta)
ANCHO_VINETA, ALTO_VINETA = 1.44, 0.56
Y_VINETA = 0.115                 # centro de la viñeta en camera.ui
Y_SUELO = -0.15                  # línea del suelo, relativa al centro de la viñeta
BORDE = 0.006                    # grosor de la tinta de las figuras
PALETA_FIESTA = ((222, 64, 64), (248, 206, 56), (44, 138, 214), (60, 170, 90), (250, 130, 50), (214, 70, 160))


def crear_cinematica(tipo, al_terminar, segundos=SEGUNDOS_VINETA, guardia=None, **opciones):
    """Crea y arranca la cinemática del final `tipo` ("bueno" | "malo"). `guardia()` (opcional) se llama cada frame
    mientras dura (el registro la usa para que Escape no deje abierta la pausa debajo)."""
    from ursina import Circle, Entity, Text, color

    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb

    datos = etapas_final.cargar_textos()["cinematicas"]
    vinetas = list(datos[tipo])
    TINTA = estilo.TINTA

    class CinematicaFinal(Entity):

        def __init__(self, **kw):
            super().__init__(**kw)
            self.z = -0.9                                    # por delante de todo el HUD (el panel final está en -0.5)
            self.tipo = tipo
            self.indice = -1
            self.terminada = False
            self._t = 0.0
            self._segundos = max(0.05, float(segundos))
            self._fundido = Fundido(SEGUNDOS_FUNDIDO / 2, SEGUNDOS_FUNDIDO / 2)
            self._cola_guardia = 0
            self.telon = Entity(parent=self, model="quad", scale=(4.0, 2.0), z=0.02, color=rgb(TINTA), collider="box")
            self.marco = panel_tinta(self, ANCHO_VINETA, ALTO_VINETA, tono=estilo.PAPEL, position=(0, Y_VINETA, 0.01))
            self.fondo = Entity(parent=self, model="quad", scale=(ANCHO_VINETA - 0.02, ALTO_VINETA - 0.02),
                                position=(0, Y_VINETA, 0.005), color=rgb(estilo.PAPEL))
            self.lienzo = Entity(parent=self, position=(0, Y_VINETA, 0))
            y_cartela = Y_VINETA - ALTO_VINETA / 2 - 0.105
            self.cartela = panel_tinta(self, ANCHO_VINETA, 0.15, tono=estilo.PAPEL, position=(0, y_cartela, 0.01),
                                       radio_px=estilo.RADIO_TARJETA_PX)
            self.titulo = Text("", parent=self, origin=(-0.5, 0), position=(-ANCHO_VINETA / 2 + 0.04, y_cartela + 0.042, -0.01),
                               scale=escala_fuente(27), color=rgb(TINTA), font=tipografia.FUENTE_TITULO)
            self.texto = Text("…", parent=self, origin=(-0.5, 0.5), position=(-ANCHO_VINETA / 2 + 0.04, y_cartela + 0.012, -0.01),
                              scale=escala_fuente(16), color=rgb(TINTA), wordwrap=112)
            self.texto.line_height = 1.25
            self.paso = Text("", parent=self, origin=(0.5, 0), position=(ANCHO_VINETA / 2 - 0.04, y_cartela + 0.045, -0.01),
                             scale=escala_fuente(14), color=rgb((96, 92, 84)))
            y_botones = -0.5 + 0.055
            self.boton_saltar = BotonSecundario(datos.get("saltar", "Saltar"), al_clic=self.saltar, ancho=0.24, alto=a_unidades(44),
                                                tamano_fuente_px=18, parent=self,
                                                position=(-ANCHO_VINETA / 2 + 0.12, y_botones, -0.02))
            self.boton_seguir = BotonPrimario(datos.get("continuar", "Continuar"), al_clic=self.siguiente, ancho=0.28,
                                              alto=a_unidades(44), tamano_fuente_px=18, parent=self,
                                              position=(ANCHO_VINETA / 2 - 0.14, y_botones, -0.02))
            self.negro = Entity(parent=self, model="quad", scale=(4.0, 2.0), z=-0.05, color=color.rgba(0, 0, 0, 0))
            diseno_adaptable.ajustar_escala(self)
            self._poner(0)

        # -- Figuras: quads y círculos planos; cada una con su borde de tinta detrás -------------------------------

        def _quad(self, x, y, ancho, alto, tono, z=0.0, giro=0.0, borde=True):
            if borde:
                Entity(parent=self.lienzo, model="quad", position=(x, y, z + 0.0005), scale=(ancho + 2 * BORDE, alto + 2 * BORDE),
                       rotation_z=giro, color=rgb(TINTA))
            return Entity(parent=self.lienzo, model="quad", position=(x, y, z), scale=(ancho, alto), rotation_z=giro, color=rgb(tono))

        def _disco(self, x, y, diametro, tono, z=0.0, lados=16, giro=0.0, borde=True, alto=None):
            escala = (diametro, alto if alto is not None else diametro)
            if borde:
                Entity(parent=self.lienzo, model=Circle(lados), position=(x, y, z + 0.0005),
                       scale=(escala[0] + 2 * BORDE, escala[1] + 2 * BORDE), rotation_z=giro, color=rgb(TINTA))
            return Entity(parent=self.lienzo, model=Circle(lados), position=(x, y, z), scale=escala, rotation_z=giro, color=rgb(tono))

        def _figura(self, f, k):
            tipo_f = f["tipo"]
            x, y = float(f.get("x", 0.0)), Y_SUELO + float(f.get("y", 0.0))
            z = -0.001 * (k + 1)                              # las últimas figuras del JSON quedan delante
            if tipo_f == "suelo":
                alto = ALTO_VINETA / 2 + Y_SUELO - 0.01
                self._quad(0, -ALTO_VINETA / 2 + 0.01 + alto / 2, ANCHO_VINETA - 0.02, alto, f.get("color", (60, 60, 70)), z, borde=False)
                self._quad(0, Y_SUELO, ANCHO_VINETA - 0.02, 0.006, TINTA, z - 0.0002, borde=False)
            elif tipo_f == "edificio":
                ancho, alto, tono = float(f["ancho"]), float(f["alto"]), f.get("color", (80, 80, 90))
                self._quad(x, y + alto / 2, ancho, alto, tono, z)
                self._quad(x, y + alto + 0.012, ancho + 0.024, 0.024, tuple(int(c * 0.8) for c in tono), z - 0.0002)
                luz = (250, 214, 110) if f.get("luz") else (30, 32, 44)
                columnas = max(2, int(ancho / 0.055))
                filas = max(1, int((alto - (0.05 if f.get("rotulo") else 0.0)) / 0.075))
                for c in range(columnas):
                    for r in range(filas):
                        vx = x - ancho / 2 + ancho * (c + 0.5) / columnas
                        vy = y + 0.045 + (alto - 0.07 - (0.05 if f.get("rotulo") else 0.0)) * r / max(1, filas - 1 if filas > 1 else 1)
                        encendida = luz if (f.get("luz") and azar_de(c + x * 7, r + ancho * 3) > 0.25) or not f.get("luz") else (60, 62, 80)
                        self._quad(vx, vy, 0.022, 0.03, encendida, z - 0.0004, borde=False)
                if f.get("rotulo"):
                    self._quad(x, y + alto - 0.032, ancho - 0.03, 0.04, (36, 36, 48), z - 0.0005)
                    Text(f["rotulo"], parent=self.lienzo, origin=(0, 0), position=(x, y + alto - 0.032, z - 0.001),
                         scale=escala_fuente(11), color=rgb((120, 120, 136)), font=tipografia.FUENTE_TITULO)
            elif tipo_f == "persona":
                alto, tono = float(f.get("alto", 0.2)), f.get("color", (40, 40, 52))
                cabeza = alto * 0.26
                self._quad(x, y + alto * 0.36, alto * 0.34, alto * 0.72, tono, z)
                self._quad(x, y + alto * 0.12, alto * 0.05, alto * 0.24, TINTA, z - 0.0002, borde=False)       # piernas separadas
                self._disco(x, y + alto * 0.72 + cabeza * 0.45, cabeza, tuple(min(255, int(c * 1.15) + 12) for c in tono), z - 0.0003)
            elif tipo_f == "fuego":
                alto = float(f.get("alto", 0.16))
                for dx, escala, tono, dz in ((0.0, 1.0, estilo.ESTADO_ERROR, 0.0), (-alto * 0.22, 0.62, (240, 130, 40), -0.0003),
                                             (alto * 0.2, 0.7, (240, 130, 40), -0.0003), (0.0, 0.45, estilo.ACENTO_PRIMARIO, -0.0006)):
                    self._disco(x + dx, y + alto * escala * 0.42, alto * escala * 0.62, tono, z + dz, lados=3, giro=0,
                                alto=alto * escala * 1.1)
            elif tipo_f == "humo":
                e = float(f.get("escala", 0.1))
                for dx, dy, r in ((0.0, 0.0, 1.0), (e * 0.55, e * 0.5, 0.8), (-e * 0.2, e * 0.95, 0.6)):
                    self._disco(x + dx, y + dy, e * r, (86, 84, 92), z, lados=10)
            elif tipo_f == "pancarta":
                giro = float(f.get("giro", 0.0))
                if f.get("caida"):
                    self._quad(x, y, 0.012, 0.16, (110, 84, 58), z, giro)
                    self._quad(x + 0.05, y + 0.004, 0.11, 0.07, estilo.PAPEL, z - 0.0002, giro - 90)
                else:
                    self._quad(x, y - 0.05, 0.012, 0.16, (110, 84, 58), z, giro)
                    self._quad(x, y + 0.045, 0.13, 0.08, estilo.PAPEL, z - 0.0002, giro)
                    for dy in (0.012, -0.012):
                        self._quad(x, y + 0.045 + dy, 0.09, 0.008, TINTA, z - 0.0004, giro, borde=False)
            elif tipo_f in ("sol", "luna"):
                self._disco(x, y, 0.11, f.get("color", (245, 196, 40)), z, lados=20)
                if tipo_f == "luna":
                    self._disco(x + 0.03, y + 0.02, 0.085, self._tono_fondo, z - 0.0002, lados=20, borde=False)
            elif tipo_f == "periodico":
                self._quad(x, y + 0.17, 0.72, 0.30, estilo.PAPEL, z, giro=-2)
                Text(f.get("titular", ""), parent=self.lienzo, origin=(0, 0), position=(x, y + 0.235, z - 0.001), rotation_z=-2,
                     scale=escala_fuente(30), color=rgb(TINTA), font=tipografia.FUENTE_TITULO)
                self._quad(x, y + 0.19, 0.62, 0.006, TINTA, z - 0.0005, giro=-2, borde=False)
                Text(f.get("bajada", ""), parent=self.lienzo, origin=(0, 0), position=(x, y + 0.16, z - 0.001), rotation_z=-2,
                     scale=escala_fuente(15), color=rgb((70, 66, 60)))
                for k2 in range(3):
                    self._quad(x, y + 0.115 - 0.024 * k2, 0.58 - 0.08 * (k2 == 2), 0.008, (168, 160, 144), z - 0.0005, giro=-2, borde=False)
            elif tipo_f == "banderines":
                x1 = float(f.get("x1", -x))
                n = 13
                for j in range(n):
                    t = (j + 0.5) / n
                    bx = x + (x1 - x) * t
                    by = y - 0.05 * 4 * t * (1 - t)
                    self._disco(bx, by - 0.022, 0.05, PALETA_FIESTA[j % len(PALETA_FIESTA)], z, lados=3, giro=180, alto=0.06)
                self._quad((x + x1) / 2, y - 0.004, abs(x1 - x), 0.005, TINTA, z + 0.0002, borde=False)
            elif tipo_f == "confeti":
                for j in range(46):
                    cx = (azar_de(j, 1.5) - 0.5) * (ANCHO_VINETA - 0.12)
                    cy = Y_SUELO + 0.03 + azar_de(j + 4.0, 2.5) * (ALTO_VINETA / 2 - Y_SUELO - 0.06)
                    self._quad(cx, cy, 0.014, 0.008, PALETA_FIESTA[j % len(PALETA_FIESTA)], z, giro=360 * azar_de(j, 9.1), borde=False)
            elif tipo_f == "podio":
                self._quad(x, y + 0.035, 0.20, 0.07, (150, 104, 62), z)
                self._quad(x, y + 0.035, 0.05, 0.03, estilo.ACENTO_PRIMARIO, z - 0.0003)
            elif tipo_f == "flor":
                self._quad(x, y + 0.03, 0.006, 0.06, (58, 128, 56), z, borde=False)
                self._disco(x, y + 0.065, 0.03, PALETA_FIESTA[int(abs(x) * 100) % len(PALETA_FIESTA)], z - 0.0002, lados=8)
            elif tipo_f == "nota":
                self._disco(x, y, 0.026, TINTA, z, lados=10, borde=False, alto=0.02)
                self._quad(x + 0.011, y + 0.03, 0.005, 0.06, TINTA, z, borde=False)
                self._quad(x + 0.022, y + 0.055, 0.024, 0.008, TINTA, z, giro=20, borde=False)

        # -- Viñetas ------------------------------------------------------------------------------------------------

        def _poner(self, i):
            self.indice = i
            self._t = 0.0
            v = vinetas[i]
            for hijo in list(self.lienzo.children):
                destruir_arbol(hijo)
            self._tono_fondo = tuple(v.get("fondo", estilo.PAPEL))
            self.fondo.color = rgb(self._tono_fondo)
            for k, f in enumerate(v.get("figuras", [])):
                try:
                    self._figura(f, k)
                except Exception as error:                    # una figura mal escrita en el JSON no tira la cinemática
                    print(f"[cinematica_final] figura «{f.get('tipo')}» omitida ({type(error).__name__}: {error})")
            self.titulo.text = v.get("titulo", "")
            self.texto.text = v.get("texto", "")
            self.paso.text = f"{i + 1} / {len(vinetas)}"
            if v.get("sonido"):
                try:
                    from frontend import audio
                    audio.obtener().efecto(v["sonido"], 0.7)
                except Exception:
                    pass

        def siguiente(self):
            if self.terminada or self._fundido.ocupada:
                return
            if self.indice + 1 >= len(vinetas):
                self._fundido.ejecutar(self._terminar)
            else:
                self._fundido.ejecutar(lambda: self._poner(self.indice + 1))

        def saltar(self):
            if not self.terminada:
                self._terminar()

        def _terminar(self):
            if self.terminada:
                return
            self.terminada = True
            self._cola_guardia = 3                            # unos frames más de guardia (Escape pudo abrir la pausa)
            for hijo in (self.telon, self.marco, self.fondo, self.lienzo, self.cartela, self.titulo, self.texto, self.paso,
                         self.boton_saltar, self.boton_seguir, self.negro):
                hijo.enabled = False
            al_terminar()

        def input(self, key):
            if self.terminada:
                return
            if key in ("space", "enter", "left mouse down"):
                if key == "left mouse down" and (self.boton_saltar.hovered or self.boton_seguir.hovered):
                    return                                    # el botón ya hace lo suyo
                self.siguiente()
            elif key == "escape":
                self.saltar()

        def update(self):
            from ursina import time
            if guardia is not None:
                try:
                    guardia()
                except Exception:
                    pass
            if self.terminada:
                self._cola_guardia -= 1
                if self._cola_guardia <= 0:
                    self.enabled = False
                return
            dt = min(time.dt, 0.1)
            self._fundido.avanzar(dt)
            self.negro.color = color.rgba(0, 0, 0, self._fundido.alfa)
            if not self._fundido.ocupada:
                self._t += dt
                if self._t >= self._segundos:
                    self.siguiente()

    return CinematicaFinal(**opciones)
