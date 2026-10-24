# Pantalla «Resultado de la misión» (Ursina, en camera.ui): un velo oscuro sobre la escena y un
# panel grande centrado con el grafo social GRANDE coloreado por el estado final acumulado de
# todas las propagaciones de la misión, la leyenda, el resumen (decisiones, alcance, % de la
# red, aislados, influyentes), los cambios en los tres indicadores y un botón «Continuar».
#
# Todo lo que se calcula (estado acumulado, textos, colores por salto, tiempos) vive en
# frontend/resultado_grafo_calculos.py (Python puro, con tests); aquí solo se dibuja.
# Igual que PanelPropagacion, no tiene update(): EscenaJuego llama a avanzar(dt).
#
# «Continuar» llama a `al_continuar` UNA sola vez (clic o Enter/Espacio). Las teclas se anotan en
# input() y se atienden en avanzar() (después de que main.AtajosCinematica ya procesó la
# misma pulsación), así Espacio/Enter no saltan además el fundido que arranca al continuar.

from panda3d.core import TextNode
from ursina import Entity, Text, color

from frontend import estilo, grafo_social_vista as vista, hud_calculos, iconos, tipografia
from frontend import resultado_grafo_calculos as calc
from frontend.componentes import (
    BotonPrimario, a_unidades, destruir_arbol, escala_fuente, modelo_redondeado, panel_tinta, rgb,
)
from frontend.texto import envolver_texto


class PanelResultadoGrafo(Entity):

    ANCHO, ALTO = 1.62, 0.94
    ASPECTO_VELO = 16 / 9                     # el velo cubre exactamente la escena (16:9)
    ALFA_VELO = 232

    # Tarjeta del grafo (izquierda) y columna de resumen (derecha), en coordenadas del panel.
    TARJETA_GRAFO = (-0.335, 0.07, 0.87, 0.52)        # (x, y, ancho, alto) del centro
    MEDIO_ANCHO_GRAFO = 0.355
    MEDIO_ALTO_GRAFO = 0.185
    X_COLUMNA, ANCHO_COLUMNA = 0.15, 0.63              # borde izquierdo y ancho útil
    DIAMETRO_NODO = 0.066
    FACTOR_NODO_MAX = 1.4
    TINTA_NODO = 0.0035                                # grosor del contorno de tinta
    GROSOR_ARO = 0.0065
    GROSOR_ARISTA = 0.006
    EXTRA_ARISTA = 0.002
    CONTORNO_ARISTA = 0.0035

    RETARDO_ANIMACION = 0.3          # s antes de empezar a encender saltos
    DURACION_APARICION = 0.2         # s del «pop» del panel
    DEMORA_TECLA = 0.4               # s antes de aceptar Enter/Espacio (evita pulsaciones sueltas)

    def __init__(self, **opciones):
        opciones.setdefault("enabled", False)
        super().__init__(**opciones)
        # Velo oscuro: cubre exactamente la escena (dentro del marco de monitor no se sale).
        self.velo = Entity(parent=self, model="quad", scale=(self.ASPECTO_VELO, 1),
                           color=color.rgba32(*estilo.TINTA, self.ALFA_VELO), z=-0.05)
        # Contenedor que hace el «pop»; todo lo del panel cuelga de él.
        self.contenedor = Entity(parent=self, z=-0.06)
        self.panel = panel_tinta(self.contenedor, self.ANCHO, self.ALTO, tono=estilo.COLOR_PANEL)

        self.titulo = Text("Resultado de la misión", parent=self.contenedor, origin=(0, 0),
                           position=(0, 0.418, -0.01), scale=escala_fuente(30),
                           font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self.subtitulo = Text("", parent=self.contenedor, origin=(0, 0), position=(0, 0.372, -0.01),
                              scale=escala_fuente(15), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._fuente_texto = self.subtitulo.font
        self._fuente_titulo = self.titulo.font

        x, y, ancho, alto = self.TARJETA_GRAFO
        self.tarjeta = panel_tinta(self.contenedor, ancho, alto, tono=estilo.COLOR_FONDO,
                                   radio_px=estilo.RADIO_TARJETA_PX, sombra=False,
                                   position=(x, y, -0.005), borde_px=2)
        self.etiqueta_grafo = Text("Red social de Civitas", parent=self.contenedor, origin=(-0.5, 0),
                                   position=(x - ancho / 2 + 0.02, y + alto / 2 - 0.022, -0.012),
                                   scale=escala_fuente(12), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._construir_leyenda()
        self._construir_indicadores()

        self.boton = BotonPrimario("Continuar", al_clic=self.continuar, ancho=0.30, alto=0.075,
                                   parent=self.contenedor, position=(0, -0.41, -0.01),
                                   tamano_fuente_px=22)
        self.pista = Text("Enter o Espacio", parent=self.contenedor, origin=(-0.5, 0),
                          position=(0.19, -0.41, -0.01), scale=escala_fuente(13),
                          color=rgb(estilo.COLOR_TEXTO_TENUE))
        self._dinamico = Entity(parent=self.contenedor, z=-0.01)

        self._al_continuar = None
        self._reiniciar_estado()

    def _reiniciar_estado(self):
        self.estado = None
        self.deltas = {}
        self.indicadores_finales = None
        self.mensaje = ""
        self.lineas_mensaje = []
        self.tiempo = 0.0
        self.continuado = False
        self._tecla_pendiente = False
        self._firma = None
        self._nodos = {}            # nombre -> dict de capas del nodo
        self._cuadros = {}          # (a, b) -> (contorno, línea)
        self._aristas = []
        self._puntos = {}

    # -- Medición de texto (misma técnica que PanelPropagacion) --

    def _medir(self, cadena, px, negrita=False):
        nodo = TextNode("medida_resultado")
        nodo.setFont(self._fuente_titulo if negrita else self._fuente_texto)
        return nodo.calcWidth(cadena) * a_unidades(px)

    # Reduce la escala de un Text hasta que su texto quepa en `ancho_max` (mínimo 70 %).
    def _ajustar(self, texto, px, ancho_max, negrita=False):
        ancho = self._medir(texto.text, px, negrita)
        if ancho > ancho_max > 0:
            texto.scale = escala_fuente(px) * max(0.7, ancho_max / ancho)

    # -- Piezas fijas --

    # Fila de leyenda centrada bajo las dos columnas: color/aro + texto, y la insignia «×N».
    def _construir_leyenda(self):
        y = -0.243
        items = [(texto, tono, tipo) for _clave, texto, tono, tipo in calc.leyenda()]
        items.append(("×N = veces que le llegó", None, "insignia"))
        px = 12
        d, hueco_texto, separacion = 0.022, 0.008, 0.028
        anchos = [d + hueco_texto + self._medir(t, px) for t, _c, _k in items]
        total = sum(anchos) + separacion * (len(items) - 1)
        x = -total / 2
        self.leyenda_total = total
        for (texto, tono, tipo), ancho in zip(items, anchos):
            centro = x + d / 2
            if tipo == "relleno":
                Entity(parent=self.contenedor, model="circle", scale=d + 0.006,
                       color=rgb(estilo.TINTA), position=(centro, y, -0.009))
                Entity(parent=self.contenedor, model="circle", scale=d, color=rgb(tono),
                       position=(centro, y, -0.01))
            elif tipo == "aro":
                Entity(parent=self.contenedor, model="circle", scale=d + 0.004,
                       color=rgb(estilo.TINTA), position=(centro, y, -0.009))
                Entity(parent=self.contenedor, model="circle", scale=d, color=rgb(tono),
                       position=(centro, y, -0.01))
                Entity(parent=self.contenedor, model="circle", scale=d * 0.5,
                       color=rgb(estilo.COLOR_FONDO), position=(centro, y, -0.011))
            else:
                Entity(parent=self.contenedor, model=modelo_redondeado(d + 0.006, d, 5),
                       scale=(d + 0.006, d), color=rgb(estilo.TINTA), position=(centro, y, -0.01))
                Text("×2", parent=self.contenedor, origin=(0, 0), position=(centro, y, -0.012),
                     scale=escala_fuente(10), color=rgb(estilo.COLOR_TEXTO))
            Text(texto, parent=self.contenedor, origin=(-0.5, 0),
                 position=(x + d + hueco_texto, y, -0.01), scale=escala_fuente(px),
                 color=rgb(estilo.COLOR_TEXTO_TENUE))
            x += ancho + separacion

    # Tres filas de indicadores (icono + etiqueta); los números se ponen en mostrar().
    def _construir_indicadores(self):
        x0, ancho = self.X_COLUMNA, self.ANCHO_COLUMNA
        self.titulo_resumen = Text("Resumen", parent=self.contenedor, origin=(-0.5, 0),
                                   position=(x0, 0.305, -0.01), scale=escala_fuente(15),
                                   font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self.titulo_indicadores = Text("Cambio en los indicadores", parent=self.contenedor,
                                       origin=(-0.5, 0), position=(x0, 0.0, -0.01),
                                       scale=escala_fuente(15), font=tipografia.FUENTE_TITULO,
                                       color=rgb(estilo.COLOR_TEXTO))
        self.filas_indicadores = {}
        for i, nombre in enumerate(("convivencia", "confianza", "desinformacion")):
            y = -0.065 - i * 0.06
            Entity(parent=self.contenedor, model=modelo_redondeado(ancho, 0.05, 8),
                   scale=(ancho, 0.05), color=rgb(estilo.COLOR_TARJETA),
                   position=(x0 + ancho / 2, y, -0.005))
            Entity(parent=self.contenedor, model="quad", texture=iconos.textura_icono(nombre),
                   scale=0.036, position=(x0 + 0.028, y, -0.01))
            Text(estilo.ETIQUETAS_INDICADORES[nombre], parent=self.contenedor, origin=(-0.5, 0),
                 position=(x0 + 0.058, y, -0.01), scale=escala_fuente(16),
                 color=rgb(estilo.COLOR_TEXTO))
            delta = Text("", parent=self.contenedor, origin=(0.5, 0),
                         position=(x0 + ancho - 0.14, y, -0.01), scale=escala_fuente(24),
                         font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO_TENUE))
            ahora = Text("", parent=self.contenedor, origin=(0.5, 0),
                         position=(x0 + ancho - 0.012, y, -0.01), scale=escala_fuente(13),
                         color=rgb(estilo.COLOR_TEXTO_TENUE))
            self.filas_indicadores[nombre] = (delta, ahora)

    # -- Control --

    # Muestra el resultado: `propagaciones` completas (con niveles), `deltas` acumulados del lote,
    # `titulo` de la misión e `indicadores` finales opcionales ({nombre: valor}). `al_continuar`
    # se llama una sola vez al pulsar «Continuar».
    def mostrar(self, grafo_social, propagaciones, deltas, titulo="", indicadores=None,
                al_continuar=None):
        self._reiniciar_estado()
        self._grafo = grafo_social
        self._al_continuar = al_continuar
        self.estado = calc.estado_acumulado(grafo_social, propagaciones)
        self.deltas = dict(deltas)
        self.indicadores_finales = None if indicadores is None else dict(indicadores)
        self.mensaje = calc.mensaje_cierre(self.estado, self.deltas)
        self.subtitulo.text = titulo
        self.boton.fijar_habilitado(True)
        self._construir_dinamico()
        self.enabled = True
        self._aplicar_aparicion(0.0)
        self._dibujar()

    def ocultar(self):
        self.enabled = False
        self.estado = None
        self._al_continuar = None
        self._tecla_pendiente = False

    # Un paso de `dt`: avanza el reloj, hace el «pop», enciende saltos y atiende una tecla pendiente.
    def avanzar(self, dt):
        if self.estado is None or not self.enabled:
            return
        self.tiempo += dt
        self._aplicar_aparicion(self.tiempo)
        self._dibujar()
        if self._tecla_pendiente:
            self._tecla_pendiente = False
            if self.tiempo >= self.DEMORA_TECLA:
                self.continuar()

    # Entity.input: solo anota Enter/Espacio (se atienden en avanzar).
    def input(self, key):
        if self.enabled and self.estado is not None and not self.continuado and key in ("space", "enter"):
            self._tecla_pendiente = True

    # Pulsar «Continuar»: llama al callback UNA sola vez, aunque se repita el clic o la tecla.
    def continuar(self):
        if self.continuado or self.estado is None:
            return False
        self.continuado = True
        self.boton.fijar_habilitado(False)
        if self._al_continuar is not None:
            self._al_continuar()
        return True

    # -- Consultas (las usan las pruebas) --

    def salto(self):
        if self.estado is None:
            return 0
        return calc.salto_en(self.estado, self.tiempo - self.RETARDO_ANIMACION)

    def animacion_terminada(self):
        return self.estado is not None and calc.animacion_terminada(
            self.estado, self.tiempo - self.RETARDO_ANIMACION)

    def color_de_nodo(self, nombre):
        c = self._nodos[nombre]["relleno"].color
        return (round(c.r * 255), round(c.g * 255), round(c.b * 255))

    def textos_visibles(self):
        return [t.text for t in self._dinamico.children if isinstance(t, Text)]

    # -- Construcción de lo que depende del resultado --

    def _construir_dinamico(self):
        for hijo in list(self._dinamico.children):
            destruir_arbol(hijo)
        grafo, estado = self._grafo, self.estado
        gx, gy = self.TARJETA_GRAFO[0], self.TARJETA_GRAFO[1]
        normalizadas = vista.posiciones(grafo)
        self._puntos = calc.puntos_en_rectangulo(
            normalizadas, self.MEDIO_ANCHO_GRAFO, self.MEDIO_ALTO_GRAFO, (gx, gy))
        grado_maximo = max((grafo.grado(c) for c in grafo.ciudadanos()), default=0)
        diametro_base = self.DIAMETRO_NODO * vista.escala_nodos(len(grafo.ciudadanos()))   # más ciudadanos: más chicos

        # Aristas: contorno de tinta + línea de color encima.
        self._aristas = vista.aristas(grafo)
        for a, b in self._aristas:
            cu, cv, largo, rotacion = _segmento(self._puntos[a], self._puntos[b])
            contorno = Entity(parent=self._dinamico, model="quad", position=(cu, cv, 0.002),
                              rotation_z=rotacion, scale=(largo, self.GROSOR_ARISTA + 2 * self.CONTORNO_ARISTA),
                              color=rgb(estilo.TINTA))
            linea = Entity(parent=self._dinamico, model="quad", position=(cu, cv, 0.0015),
                           rotation_z=rotacion, scale=(largo, self.GROSOR_ARISTA),
                           color=rgb(calc.COLOR_ARISTA_INACTIVA))
            self._cuadros[(a, b)] = (contorno, linea)

        # Nodos: contorno de tinta, aro (dorado/rojo), contorno interior, relleno e inicial.
        for nombre, (px, py) in self._puntos.items():
            grado = grafo.grado(nombre)
            d = vista.diametro_nodo(grado, grado_maximo, diametro_base, self.FACTOR_NODO_MAX)
            aislado = nombre in estado["aislados"]
            influyente = nombre in estado["influyentes"]
            con_aro = aislado or influyente
            tono_aro = calc.COLOR_AISLADO if aislado else calc.COLOR_INFLUYENTE
            k, r = self.TINTA_NODO, self.GROSOR_ARO
            cont = Entity(parent=self._dinamico, position=(px, py, -0.002))
            exterior = Entity(parent=cont, model="circle", scale=d + 2 * (2 * k + r),
                              color=rgb(estilo.TINTA), z=0.0004, enabled=con_aro)
            aro = Entity(parent=cont, model="circle", scale=d + 2 * (k + r),
                         color=rgb(tono_aro), z=0.0003, enabled=con_aro)
            interior = Entity(parent=cont, model="circle", scale=d + 2 * k,
                              color=rgb(estilo.TINTA), z=0.0002)
            relleno = Entity(parent=cont, model="circle", scale=d, color=rgb(calc.COLOR_SIN_RECIBIR))
            letra = Text(nombre[0], parent=cont, origin=(0, 0), position=(0, 0, -0.001),
                         scale=escala_fuente(22 if d > 0.07 else 19), font=tipografia.FUENTE_TITULO,
                         color=rgb(estilo.COLOR_TEXTO_TENUE))
            self._etiqueta_de_nombre(nombre, px, py, d, normalizadas[nombre])
            insignia = self._insignia_veces(cont, d, estado["veces"].get(nombre, 0), nombre)
            self._nodos[nombre] = {"relleno": relleno, "letra": letra, "aro": aro,
                                   "exterior": exterior, "interior": interior, "d": d,
                                   "insignia": insignia}

        self._construir_resumen()
        self._construir_indicadores_valores()
        self._construir_mensaje()

    # Nombre del ciudadano en una pastilla de tinta, al lado o bajo el nodo.
    def _etiqueta_de_nombre(self, nombre, px, py, d, normalizada):
        px_fuente = 14
        ancho = self._medir(nombre, px_fuente) + 0.018
        alto = 0.03
        lado = calc.lado_etiqueta(*normalizada)
        margen = d / 2 + 2 * self.TINTA_NODO + self.GROSOR_ARO + 0.004
        if lado == "abajo":
            cx, cy = px, py - margen - alto / 2
        elif lado == "izquierda":
            cx, cy = px - margen - ancho / 2, py
        else:
            cx, cy = px + margen + ancho / 2, py
        Entity(parent=self._dinamico, model=modelo_redondeado(ancho, alto, 7), scale=(ancho, alto),
               color=color.rgba32(*estilo.TINTA, 225), position=(cx, cy, -0.003))
        Text(nombre, parent=self._dinamico, origin=(0, 0), position=(cx, cy, -0.004),
             scale=escala_fuente(px_fuente), color=rgb(estilo.COLOR_TEXTO))

    # Insignia «×N» arriba a la derecha del nodo si lo alcanzaron 2 o más publicaciones.
    def _insignia_veces(self, contenedor, d, veces, nombre):
        if veces < 2 or nombre == self.estado["origen"]:
            return None
        ancho = self._medir(f"×{veces}", 11, True) + 0.014
        insignia = Entity(parent=contenedor, position=(d * 0.62, d * 0.62, -0.003), enabled=False)
        Entity(parent=insignia, model=modelo_redondeado(ancho, 0.024, 6), scale=(ancho, 0.024),
               color=rgb(estilo.TINTA))
        Text(f"×{veces}", parent=insignia, origin=(0, 0), position=(0, 0, -0.001),
             scale=escala_fuente(11), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        return insignia

    # Líneas «Etiqueta: valor» de la columna derecha.
    def _construir_resumen(self):
        x0, ancho = self.X_COLUMNA, self.ANCHO_COLUMNA
        for i, (etiqueta, valor) in enumerate(calc.lineas_resumen(self.estado)):
            y = 0.258 - i * 0.047
            Entity(parent=self._dinamico, model=modelo_redondeado(ancho, 0.04, 7),
                   scale=(ancho, 0.04), color=rgb(estilo.COLOR_TARJETA), position=(x0 + ancho / 2, y, 0.004))
            Text(etiqueta, parent=self._dinamico, origin=(-0.5, 0), position=(x0 + 0.012, y, -0.001),
                 scale=escala_fuente(14), color=rgb(estilo.COLOR_TEXTO_TENUE))
            x_valor = x0 + 0.012 + self._medir(etiqueta, 14) + 0.016
            texto = Text(valor, parent=self._dinamico, origin=(-0.5, 0), position=(x_valor, y, -0.001),
                         scale=escala_fuente(14), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
            self._ajustar(texto, 14, x0 + ancho - 0.01 - x_valor, negrita=True)

    # Cambios con signo y color; si hay valores finales, «ahora N».
    def _construir_indicadores_valores(self):
        for nombre, (delta, ahora) in self.filas_indicadores.items():
            valor = self.deltas.get(nombre, 0)
            delta.text = calc.texto_delta(valor) if valor != 0 else "sin cambio"
            delta.scale = escala_fuente(24 if valor != 0 else 15)
            delta.color = rgb(calc.color_delta(nombre, valor))
            if self.indicadores_finales is not None and nombre in self.indicadores_finales:
                ahora.text = f"ahora {self.indicadores_finales[nombre]}"
            else:
                ahora.text = ""

    # Mensaje de cierre en una tarjeta con barra de acento (verde/rojo/gris según la desinformación).
    def _construir_mensaje(self):
        y, ancho, alto = -0.322, 1.50, 0.088
        Entity(parent=self._dinamico, model=modelo_redondeado(ancho, alto, 9), scale=(ancho, alto),
               color=rgb(estilo.COLOR_TARJETA), position=(0, y, 0.004))
        tono = calc.color_delta("desinformacion", self.deltas.get("desinformacion", 0))
        Entity(parent=self._dinamico, model="quad", scale=(0.008, alto - 0.03), color=rgb(tono),
               position=(-ancho / 2 + 0.02, y, -0.001))
        lineas = envolver_texto(self.mensaje, lambda c: self._medir(c, 17), ancho - 0.09) or [""]
        texto = Text("\n".join(lineas), parent=self._dinamico, origin=(-0.5, 0),
                     position=(-ancho / 2 + 0.045, y, -0.002), scale=escala_fuente(17),
                     color=rgb(estilo.COLOR_TEXTO))
        texto.line_height = 1.3
        self.lineas_mensaje = lineas

    # -- Animación --

    # «Pop» del panel y fundido del velo durante DURACION_APARICION.
    def _aplicar_aparicion(self, t):
        p = max(0.0, min(1.0, t / self.DURACION_APARICION))
        suave = 1 - (1 - p) ** 2
        self.contenedor.scale = 0.94 + 0.06 * suave
        self.velo.color = color.rgba32(*estilo.TINTA, int(self.ALFA_VELO * suave))

    # Pinta nodos y aristas según el salto encendido; solo redibuja si cambió algo.
    def _dibujar(self):
        salto = self.salto()
        terminada = self.animacion_terminada()
        if (salto, terminada) == self._firma:
            return
        self._firma = (salto, terminada)
        estado = self.estado
        for nombre, capas in self._nodos.items():
            tono = calc.color_nodo(estado, nombre, salto)
            capas["relleno"].color = rgb(tono)
            pendiente = calc.estado_nodo(estado, nombre, salto) == calc.NODO_PENDIENTE
            frenado = calc.estado_nodo(estado, nombre, salto) == calc.NODO_FRENADO
            capas["letra"].color = rgb(estilo.COLOR_TEXTO if frenado else
                                       estilo.COLOR_TEXTO_TENUE if pendiente else estilo.TINTA)
            if capas["insignia"] is not None:
                capas["insignia"].enabled = not pendiente
        for (a, b), (_contorno, linea) in self._cuadros.items():
            encendida = calc.salto_de_arista(estado, a, b, salto)
            if encendida is None:
                linea.color = rgb(calc.COLOR_ARISTA_INACTIVA)
                linea.scale_y = self.GROSOR_ARISTA
            else:
                linea.color = rgb(calc.color_del_salto(encendida))
                linea.scale_y = calc.grosor_arista(
                    calc.veces_de_arista(estado, a, b), self.GROSOR_ARISTA, self.EXTRA_ARISTA)
            _contorno.scale_y = linea.scale_y + 2 * self.CONTORNO_ARISTA


# (centro_x, centro_y, largo, rotación en grados) del rectángulo que une dos puntos.
def _segmento(p, q):
    return hud_calculos.segmento_a_cuadro(p, q)
