# Tarjeta de primera vez del teléfono en grande (Ursina, camera.ui): modal pequeño que explica en una o dos oraciones,
# con 1 a 3 dibujos sencillos (frontend/dibujos_avisos.py), en qué consiste un tipo de aviso de Civitas. Sale ANTES del
# teléfono la primera vez que llega cada tipo en la partida (frontend/registro_telefono_grande.py) y también sirve de
# carrusel de solo lectura para releerlas («?» del teléfono y «Avisos de Civitas» en la pausa).
#
#   TarjetaAviso(al_entender)
#     .mostrar(datos, carrusel=None)   datos: {"titulo", "texto", "dibujos"}; carrusel: (indice, total) o None
#     .ocultar() / .abierta()
#   Teclas: las maneja quien la abre (Espacio, Intro o clic = «Entendido»; en el carrusel, flechas para pasar).
# Entidades fijas (≈ 15): se crean una vez.

from ursina import Entity, Text, camera, color

from frontend import dibujos_avisos, diseno_adaptable, estilo, tipografia
from frontend.componentes import BotonPrimario, BotonSecundario, escala_fuente, panel_tinta, rgb
from frontend.texto import envolver_texto

ANCHO, ALTO = 0.86, 0.52
LADO_DIBUJO = 0.17
MAX_DIBUJOS = 3
PIE = "Espacio, Intro o clic: entendido"
PIE_CARRUSEL = "Flechas: pasar  ·  Esc o Intro: cerrar"


class TarjetaAviso(Entity):

    def __init__(self, al_entender, al_pasar=None, **opciones):
        opciones.setdefault("parent", camera.ui)
        super().__init__(enabled=False, **opciones)
        self.z = -0.09
        self.fondo = Entity(parent=self, model="quad", scale=(4, 2), color=color.rgba32(10, 11, 18, 200), z=0.02)
        self.marco = panel_tinta(self, ANCHO, ALTO, tono=estilo.COLOR_PANEL)
        x0 = -ANCHO / 2 + 0.05
        self.etiqueta = Text("Civitas  ·  Antes de abrir", parent=self, origin=(-0.5, 0.5),
                             position=(x0, ALTO / 2 - 0.035, -0.02), scale=escala_fuente(13),
                             color=rgb(estilo.ACENTO_SECUNDARIO), font=tipografia.FUENTE_TITULO)
        self.titulo = Text("", parent=self, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.065, -0.02),
                           scale=escala_fuente(26), color=rgb(estilo.COLOR_ACENTO), font=tipografia.FUENTE_TITULO)
        self._px_texto = 18
        self.texto = Text("", parent=self, origin=(-0.5, 0.5), position=(x0, ALTO / 2 - 0.13, -0.02),
                          scale=escala_fuente(self._px_texto), color=rgb(estilo.COLOR_TEXTO))
        self.dibujos = [Entity(parent=self, model="quad", scale=LADO_DIBUJO, position=(0, -0.05, -0.02), enabled=False)
                        for _ in range(MAX_DIBUJOS)]
        self.boton = BotonPrimario("Entendido", al_clic=al_entender, ancho=0.26, alto=0.06, tamano_fuente_px=18,
                                   parent=self, position=(ANCHO / 2 - 0.18, -ALTO / 2 + 0.06, -0.02))
        self.pie = Text("", parent=self, origin=(-0.5, 0), position=(x0, -ALTO / 2 + 0.06, -0.02),
                        scale=escala_fuente(13), color=rgb(estilo.COLOR_TEXTO_TENUE))
        self.pasar = []
        if al_pasar is not None:
            for i, (texto, paso) in enumerate((("Anterior", -1), ("Siguiente", 1))):
                boton = BotonSecundario(texto, al_clic=lambda p=paso: al_pasar(p), ancho=0.17, alto=0.05,
                                        tamano_fuente_px=15, parent=self,
                                        position=(-ANCHO / 2 + 0.14 + i * 0.19, -ALTO / 2 + 0.06, -0.02))
                boton.enabled = False
                self.pasar.append(boton)
        diseno_adaptable.ajustar_escala(self)

    def _medir(self, px):
        from frontend.telefono_pantallas import medidor
        return medidor().funcion(px)

    def mostrar(self, datos, carrusel=None):
        self.enabled = True
        self.titulo.text = datos["titulo"]
        lineas = envolver_texto(" ".join(datos["texto"].split()), self._medir(self._px_texto), ANCHO - 0.1)
        self.texto.text = "\n".join(lineas[:4])
        nombres = [n for n in datos.get("dibujos", []) if n in dibujos_avisos.NOMBRES][:MAX_DIBUJOS]
        separacion = LADO_DIBUJO + 0.06
        x_inicio = -(len(nombres) - 1) * separacion / 2
        for i, entidad in enumerate(self.dibujos):
            hay = i < len(nombres)
            entidad.enabled = hay
            if hay:
                entidad.texture = dibujos_avisos.textura(nombres[i])
                entidad.color = color.white
                entidad.x = x_inicio + i * separacion
                entidad.y = -0.05 - max(0, len(lineas) - 2) * 0.012
        en_carrusel = carrusel is not None
        self.etiqueta.text = f"Avisos de Civitas  ·  {carrusel[0] + 1} de {carrusel[1]}" if en_carrusel \
            else "Civitas  ·  Antes de abrir"
        self.boton.text = "Cerrar" if en_carrusel else "Entendido"
        for boton in self.pasar:
            boton.enabled = en_carrusel
        self.pie.enabled = not en_carrusel or not self.pasar
        self.pie.text = PIE_CARRUSEL if en_carrusel else PIE

    def ocultar(self):
        self.enabled = False

    def abierta(self):
        return bool(self.enabled)
