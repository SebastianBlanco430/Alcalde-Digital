# Cinemática del final (docs/PLAN_FINALES_HISTORIA.md §2.7): viñetas 2D como páginas de cómic, a pantalla completa en
# camera.ui. Cada viñeta (backend/datos/finales_historia.json, «cinematicas») trae un color de fondo, unas «figuras» hechas
# con quads y círculos planos con borde de tinta (edificios, gente, fuego, banderines, podio...), un título y un texto.
# Fundido a negro entre viñetas (frontend/fundido.py). Espacio, Enter o clic avanzan; Escape (o «Saltar») la salta entera.
# Cada viñeta pasa sola a los `segundos` s. Al terminar llama a `al_terminar()` UNA vez.
#
# El componente es genérico (docs/PLAN_CLARIDAD_JUEGO.md §2.3): `crear_vinetas(vinetas, ...)` pinta cualquier lista de
# viñetas ya cargada (el tutorial usa backend/datos/tutorial_vinetas.json). Con `segundos=None` no avanzan solas. Además
# de las de cómic admite viñetas «foco» ({"tipo": "foco", "elemento", "titulo", "texto"}): la pantalla se oscurece salvo
# un recuadro (tinta + amarillo) alrededor de un elemento real del HUD, con un bocadillo al lado. El rectángulo lo da
# `foco_de(elemento)` -> (x, y, ancho, alto) en camera.ui, o None (entonces solo el bocadillo, centrado).
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
ALFA_VELO_FOCO = 0.6             # oscurecido de la pantalla en una viñeta «foco»
MARGEN_FOCO = 0.012              # aire entre el elemento señalado y su recuadro
GROSOR_ACENTO, GROSOR_TINTA_FOCO = 0.005, 0.004
ANCHO_BOCADILLO, ALTO_BOCADILLO = 0.56, 0.30     # el alto es el de partida: crece o encoge con las líneas del texto
RELLENO_BOCADILLO = 0.03
SEPARACION_BOCADILLO = 0.03
AYUDA_FOCO = "Espacio: seguir · Esc: saltar"
PALETA_FIESTA = ((222, 64, 64), (248, 206, 56), (44, 138, 214), (60, 170, 90), (250, 130, 50), (214, 70, 160))


def crear_cinematica(tipo, al_terminar, segundos=SEGUNDOS_VINETA, guardia=None, **opciones):
    """Crea y arranca la cinemática del final `tipo` ("bueno" | "malo"). `guardia()` (opcional) se llama cada frame
    mientras dura (el registro la usa para que Escape no deje abierta la pausa debajo)."""
    datos = etapas_final.cargar_textos()["cinematicas"]
    cinematica = crear_vinetas(list(datos[tipo]), al_terminar, segundos=segundos, guardia=guardia, rotulos=datos, **opciones)
    cinematica.tipo = tipo
    return cinematica


def crear_vinetas(vinetas, al_terminar, segundos=None, guardia=None, rotulos=None, foco_de=None, al_poner=None, **opciones):
    """Crea y arranca una secuencia de viñetas ya cargada (lista de dicts). `segundos=None`: no avanzan solas (decide el
    jugador). `rotulos`: {"saltar", "continuar"} de los botones. `foco_de(elemento)`: rectángulo en camera.ui del elemento
    del HUD de una viñeta «foco» (o None). `al_poner(vineta, indice)`: aviso cada vez que cambia la viñeta."""
    from ursina import Circle, Entity, Text, color

    from frontend import diseno_adaptable, estilo, tipografia
    from frontend.componentes import BotonPrimario, BotonSecundario, a_unidades, destruir_arbol, escala_fuente, panel_tinta, rgb

    vinetas = list(vinetas)
    datos = rotulos or {}
    tipo = None
    TINTA = estilo.TINTA

    class CinematicaFinal(Entity):

        def __init__(self, **kw):
            super().__init__(**kw)
            self.z = -0.9                                    # por delante de todo el HUD (el panel final está en -0.5)
            self.tipo = tipo
            self.indice = -1
            self.terminada = False
            self._t = 0.0
            self._segundos = None if segundos is None else max(0.05, float(segundos))
            self.capa_foco = None                            # se crea con la primera viñeta «foco»
            self._rect_foco = False                          # último rectángulo pintado (False = ninguno aún)
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
                              scale=escala_fuente(16), color=rgb(TINTA))
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
            self._comic = (self.telon, self.marco, self.fondo, self.lienzo, self.cartela, self.titulo, self.texto, self.paso,
                           self.boton_saltar, self.boton_seguir)
            diseno_adaptable.ajustar_escala(self)
            self._poner(0)

        # -- Texto que no se sale: se parte midiendo el ancho real con la fuente (no por número de caracteres) --------

        @staticmethod
        def _envolver(texto, cadena, ancho, max_lineas=None):
            """Pone `cadena` en el Text partida para caber en `ancho`; devuelve cuántas líneas quedaron."""
            from frontend import hud as hud_mod
            from frontend.texto import envolver_texto
            lineas = envolver_texto(hud_mod._seguro(str(cadena or "")), hud_mod._medidor(texto), ancho) or [""]
            if max_lineas is not None and len(lineas) > max_lineas:
                lineas = lineas[:max_lineas]
                lineas[-1] = lineas[-1].rstrip()[:-1].rstrip() + "…"
            texto.text = "\n".join(lineas)
            return len(lineas)

        # -- Viñeta «foco»: velo con un hueco sobre un elemento real del HUD y un bocadillo al lado ------------------

        def _crear_capa_foco(self):
            # Cuelga del padre (el HUD, sin escala) y no de la cinemática: el hueco se mide en camera.ui tal cual.
            capa = Entity(parent=self.parent, z=self.z)
            velo = color.rgba(0, 0, 0, ALFA_VELO_FOCO)
            capa.velos = [Entity(parent=capa, model="quad", color=velo, z=0.02) for _ in range(4)]
            capa.tintas = [Entity(parent=capa, model="quad", color=rgb(TINTA), z=0.012) for _ in range(4)]
            capa.acentos = [Entity(parent=capa, model="quad", color=rgb(estilo.ACENTO_PRIMARIO), z=0.01) for _ in range(4)]
            capa.bocadillo = Entity(parent=capa)
            capa.fondo = None                       # el panel se rehace por viñeta: su alto depende de las líneas
            capa.alto = ALTO_BOCADILLO
            capa.titulo = Text("", parent=capa.bocadillo, origin=(-0.5, 0.5), z=-0.01,
                               scale=escala_fuente(20), color=rgb(TINTA), font=tipografia.FUENTE_TITULO)
            capa.titulo.line_height = 1.15
            capa.texto = Text("…", parent=capa.bocadillo, origin=(-0.5, 0.5), z=-0.01, scale=escala_fuente(15), color=rgb(TINTA))
            capa.texto.line_height = 1.25
            capa.ayuda = Text(AYUDA_FOCO, parent=capa.bocadillo, origin=(-0.5, 0), z=-0.01,
                              scale=escala_fuente(13), color=rgb((96, 92, 84)))
            capa.paso = Text("", parent=capa.bocadillo, origin=(0.5, 0), z=-0.01,
                             scale=escala_fuente(13), color=rgb((96, 92, 84)))
            return capa

        def _armar_bocadillo(self, titulo, cuerpo, paso):
            """Escribe el bocadillo partiendo título y texto a su ancho y le da el alto que pidan las líneas."""
            capa = self.capa_foco
            ancho_texto = ANCHO_BOCADILLO - 2 * RELLENO_BOCADILLO
            n_titulo = self._envolver(capa.titulo, titulo, ancho_texto, 2)
            n_texto = self._envolver(capa.texto, cuerpo, ancho_texto, 9)
            alto_titulo = n_titulo * a_unidades(20) * 1.15
            alto_texto = n_texto * a_unidades(15) * 1.25
            capa.alto = RELLENO_BOCADILLO + alto_titulo + 0.012 + alto_texto + 0.02 + a_unidades(13) + RELLENO_BOCADILLO
            if capa.fondo is not None:
                destruir_arbol(capa.fondo)
            capa.fondo = panel_tinta(capa.bocadillo, ANCHO_BOCADILLO, capa.alto, tono=estilo.PAPEL,
                                     radio_px=estilo.RADIO_TARJETA_PX, z=0.005)
            izquierda, arriba = -ANCHO_BOCADILLO / 2 + RELLENO_BOCADILLO, capa.alto / 2 - RELLENO_BOCADILLO
            capa.titulo.position = (izquierda, arriba, -0.01)
            capa.texto.position = (izquierda, arriba - alto_titulo - 0.012, -0.01)
            y_pie = -capa.alto / 2 + RELLENO_BOCADILLO + a_unidades(13) / 2
            capa.ayuda.position = (izquierda, y_pie, -0.01)
            capa.paso.position = (-izquierda, y_pie, -0.01)
            capa.paso.text = paso

        @staticmethod
        def _barras(entidades, x0, y0, x1, y1, grosor):
            """Coloca 4 quads como marco hueco de `grosor` por FUERA del rectángulo (x0, y0)-(x1, y1)."""
            cx, cy, ancho, alto = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
            for e, (x, y, w, h) in zip(entidades, ((cx, y1 + grosor / 2, ancho + 2 * grosor, grosor),
                                                   (cx, y0 - grosor / 2, ancho + 2 * grosor, grosor),
                                                   (x0 - grosor / 2, cy, grosor, alto), (x1 + grosor / 2, cy, grosor, alto))):
                e.x, e.y, e.scale_x, e.scale_y = x, y, w, h

        def _colocar_foco(self, rect):
            """`rect`: (x, y, ancho, alto) del elemento en camera.ui, o None (velo entero y bocadillo centrado)."""
            capa = self.capa_foco
            self._rect_foco = rect
            con_hueco = rect is not None
            for e in capa.velos[1:] + capa.tintas + capa.acentos:
                e.enabled = con_hueco
            if not con_hueco:
                capa.velos[0].x, capa.velos[0].y, capa.velos[0].scale_x, capa.velos[0].scale_y = 0, 0, 4.0, 4.0
                capa.bocadillo.position = (0, 0)
                return
            cx, cy, ancho, alto = rect
            x0, x1 = cx - ancho / 2 - MARGEN_FOCO, cx + ancho / 2 + MARGEN_FOCO
            y0, y1 = cy - alto / 2 - MARGEN_FOCO, cy + alto / 2 + MARGEN_FOCO
            for e, (x, y, w, h) in zip(capa.velos, (((x0 - 2.0) / 2, 0, x0 + 2.0, 4.0), ((x1 + 2.0) / 2, 0, 2.0 - x1, 4.0),
                                                    ((x0 + x1) / 2, (y1 + 2.0) / 2, x1 - x0, 2.0 - y1),
                                                    ((x0 + x1) / 2, (y0 - 2.0) / 2, x1 - x0, y0 + 2.0))):
                e.x, e.y, e.scale_x, e.scale_y = x, y, max(0.0001, w), max(0.0001, h)
            self._barras(capa.acentos, x0, y0, x1, y1, GROSOR_ACENTO)
            self._barras(capa.tintas, x0 - GROSOR_ACENTO, y0 - GROSOR_ACENTO, x1 + GROSOR_ACENTO, y1 + GROSOR_ACENTO,
                         GROSOR_TINTA_FOCO)
            # Bocadillo: al lado (hacia el centro de la pantalla); si no cabe, debajo o encima.
            medio = diseno_adaptable.aspecto() / 2 - 0.02
            alto_boc = capa.alto
            tope_y = 0.5 - 0.02 - alto_boc / 2
            bx = x0 - SEPARACION_BOCADILLO - ANCHO_BOCADILLO / 2 if cx >= 0 else x1 + SEPARACION_BOCADILLO + ANCHO_BOCADILLO / 2
            by = max(-tope_y, min(tope_y, cy))
            if abs(bx) + ANCHO_BOCADILLO / 2 > medio:
                tope_x = max(0.0, medio - ANCHO_BOCADILLO / 2)
                bx = max(-tope_x, min(tope_x, cx))
                by = y0 - SEPARACION_BOCADILLO - alto_boc / 2 if cy >= 0 else y1 + SEPARACION_BOCADILLO + alto_boc / 2
            capa.bocadillo.position = (bx, by)

        def _rect_de(self, vineta):
            if foco_de is None:
                return None
            try:
                rect = foco_de(vineta.get("elemento"))
                return None if rect is None else tuple(round(float(v), 4) for v in rect)
            except Exception:
                return None

        def _poner_foco(self, i, v):
            if self.capa_foco is None:
                self.capa_foco = self._crear_capa_foco()
            capa = self.capa_foco
            capa.enabled = True
            self._armar_bocadillo(v.get("titulo", ""), v.get("texto", ""), f"{i + 1} / {len(vinetas)}")
            self._colocar_foco(self._rect_de(v))

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
            es_foco = v.get("tipo") == "foco"
            for pieza in self._comic:
                pieza.enabled = not es_foco
            if self.capa_foco is not None:
                self.capa_foco.enabled = es_foco
            if al_poner is not None:
                try:
                    al_poner(v, i)
                except Exception:
                    pass
            if es_foco:
                self._poner_foco(i, v)
                return
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
            self._envolver(self.texto, v.get("texto", ""), ANCHO_VINETA - 0.08, 3)       # la cartela da para 3 líneas
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
            if self.capa_foco is not None:
                destruir_arbol(self.capa_foco)
                self.capa_foco = None
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
            if self.capa_foco is not None and self.capa_foco.enabled:       # el HUD puede moverse o tardar un frame en salir
                rect = self._rect_de(vinetas[self.indice])
                if rect != self._rect_foco:
                    self._colocar_foco(rect)
            if not self._fundido.ocupada:
                self._t += dt
                if self._segundos is not None and self._t >= self._segundos:
                    self.siguiente()

    return CinematicaFinal(**opciones)
