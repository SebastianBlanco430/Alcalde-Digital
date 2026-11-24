# Final del caso de Fiscalía v2 (Ursina, en camera.ui), en dos pasos:
#   1. Tarjeta del final: resultado (Éxito / Parcial / Fracaso), título, texto y solidez final. Botón «Ver el recorrido».
#   2. Diagrama de flujo del caso (casos_v2_tipos.Diagrama, un grafo dirigido acíclico por capas): columnas de izquierda
#      a derecha; los momentos recorridos iluminados con su texto, los no vistos como siluetas con «?», las aristas
#      recorridas marcadas, y el porcentaje visto. Botón «Salir de la Fiscalía» -> al_cerrar().
# Aquí solo se dibuja: el diseño por capas (Sugiyama, sin solapes, dentro de pantalla, aristas que no pisan cajas) está
# en diagrama_flujo_calculos.disponer() y se explica en docs/DIAGRAMA_FLUJO.md.

from ursina import Entity, Mesh, Text, color

from frontend import estilo, tipografia
from frontend.componentes import BotonPrimario, a_unidades, escala_fuente, modelo_redondeado, panel_tinta, rgb
from frontend.fiscalia import diagrama_flujo_calculos as dc
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import ajustar

ALTO_BOTON = a_unidades(56)
TONO_TIPO = {"laboratorio": (46, 92, 110), "acusacion": (110, 92, 40)}
TONO_VISTO = estilo.COLOR_TARJETA
TONO_NO_VISTO = (22, 24, 34)
TONO_ARISTA = (92, 96, 118)            # aristas no recorridas: grises, opacas (sin solapes de transparencia)
GROSOR_GRIS, GROSOR_RECORRIDO = 0.0026, 0.0060
FLECHA, UNION = 0.016, 0.0075          # lado de la punta de flecha y semidiagonal del rombo de unión
PX_MIN = 10


class PantallaFinal(Entity):

    def __init__(self, vista, diagrama, al_cerrar, solidez=0, umbrales=None, titulo_caso="", semiancho=16 / 9 / 2,
                 **opciones):
        super().__init__(**opciones)
        self._al_cerrar = al_cerrar
        self._cerrado = False
        self.fase = "tarjeta"
        self.velo = Entity(parent=self, model="quad", color=color.rgba32(*estilo.COLOR_FONDO, 240), scale=(4, 4), z=0.05,
                           collider="box")
        self.tarjeta = Entity(parent=self)
        self._tarjeta(vista, solidez, umbrales, titulo_caso)
        self.diagrama = Entity(parent=self, enabled=False)
        self.diagrama_ok = False
        if diagrama is not None:
            try:
                self._diagrama(diagrama, getattr(vista, "id", None), semiancho)
                self.diagrama_ok = True
            except Exception as error:   # noqa: BLE001  sin diagrama: la tarjeta lleva directo a salir
                from frontend import banderas_visuales as bv
                bv.avisar_una_vez("fiscalia_diagrama", error)
        if not self.diagrama_ok:
            self.boton_ver.text = "Salir de la Fiscalía"

    # -- Tarjeta --

    def _tarjeta(self, vista, solidez, umbrales, titulo_caso):
        ancho, alto = 1.06, 0.70
        t = self.tarjeta
        panel_tinta(t, ancho, alto, tono=estilo.COLOR_PANEL, position=(0, 0.0, 0.01))
        cab = Text("", parent=t, origin=(0, 0), position=(0, 0.30, -0.01), scale=escala_fuente(16),
                   color=rgb(estilo.COLOR_TEXTO_TENUE))
        ajustar(cab, f"Caso cerrado · {titulo_caso}" if titulo_caso else "Caso cerrado", ancho - 0.1, 16)
        nombre, tono = uc.nombre_resultado(getattr(vista, "resultado", None))
        sello = panel_tinta(t, 0.22, 0.05, tono=tono, radio_px=estilo.RADIO_CHIP_PX, sombra=False,
                            position=(0, 0.245, -0.005))
        Text(nombre.upper(), parent=sello, origin=(0, 0), z=-0.01, scale=escala_fuente(uc.TAM["resultado"]),
             font=tipografia.FUENTE_TITULO, color=rgb(estilo.tono_legible(estilo.TINTA, tono)))
        self.titulo = Text("", parent=t, origin=(0, 0), position=(0, 0.17, -0.01), scale=escala_fuente(uc.TAM["titulo"]),
                           font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        ajustar(self.titulo, getattr(vista, "titulo", "") or "Final", ancho - 0.1, uc.TAM["titulo"])
        self.texto = Text("", parent=t, origin=(0, 0.5), position=(0, 0.115, -0.01),
                          scale=escala_fuente(uc.TAM["texto_final"]), color=rgb(estilo.COLOR_TEXTO))
        self.texto.line_height = 1.15
        ajustar(self.texto, getattr(vista, "texto", ""), ancho - 0.12, uc.TAM["texto_final"], max_lineas=6)
        # Solidez final con su barra y las marcas de los umbrales.
        y_barra, ancho_barra = -0.175, 0.56
        Text(f"Solidez final {int(solidez)} %", parent=t, origin=(0, 0), position=(0, -0.135, -0.01),
             scale=escala_fuente(uc.TAM["porcentaje"]), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        Entity(parent=t, model=modelo_redondeado(ancho_barra, 0.018, 4), scale=(ancho_barra, 0.018),
               position=(0, y_barra, -0.004), color=rgb(estilo.COLOR_BARRA_FONDO))
        lleno = max(0.001, ancho_barra * max(0, min(100, solidez)) / 100)
        Entity(parent=t, model="quad", scale=(lleno, 0.018), position=(-ancho_barra / 2 + lleno / 2, y_barra, -0.006),
               color=rgb(uc.tono_solidez(solidez, umbrales)))
        for x, _, _ in uc.marcas_umbrales(umbrales, ancho_barra):
            Entity(parent=t, model="quad", scale=(0.004, 0.03), position=(-ancho_barra / 2 + x, y_barra, -0.008),
                   color=rgb(estilo.PAPEL))
        self.boton_ver = BotonPrimario("Ver el recorrido", al_clic=self._pulsar, ancho=0.44, alto=ALTO_BOTON,
                                       tamano_fuente_px=uc.TAM["boton"], parent=t, position=(0, -0.265, -0.01))
        self.boton_ver.fijar_foco(True)

    # -- Diagrama --

    def _diagrama(self, d, id_final, semiancho):
        raiz = self.diagrama
        Text("Recorrido del caso", parent=raiz, origin=(0, 0), position=(0, 0.44, -0.01),
             scale=escala_fuente(uc.TAM["diagrama_titulo"]), font=tipografia.FUENTE_TITULO, color=rgb(estilo.COLOR_TEXTO))
        self.porcentaje = Text(uc.texto_porcentaje(d.vistos, d.total), parent=raiz, origin=(0, 0),
                               position=(0, 0.385, -0.01), scale=escala_fuente(uc.TAM["porcentaje"]),
                               color=rgb(estilo.COLOR_ACENTO))
        area = dc.area_para(semiancho)
        disp = dc.disponer(d, area)           # Sugiyama: toda la geometría sale de aquí (puro, con tests)
        self.disposicion = disp
        px = uc.TAM["diagrama"] if disp.escala >= 0.999 else max(PX_MIN, int(uc.TAM["diagrama"] * disp.escala))
        # Aristas detrás de las cajas, en DOS mallas: las grises finas y, encima, el recorrido grueso y amarillo.
        for recorrida, grosor, tono, z in ((False, GROSOR_GRIS, TONO_ARISTA, 0.02),
                                           (True, GROSOR_RECORRIDO, estilo.COLOR_ACENTO, 0.015)):
            trazos = [t for t in disp.trazos if t.recorrida == recorrida]
            uniones = [u for u in disp.uniones if u.recorrida == recorrida]
            vertices, triangulos = dc.malla(trazos, uniones, grosor, FLECHA * disp.escala, UNION * disp.escala)
            if vertices:
                Entity(parent=raiz, model=Mesh(vertices=vertices, triangles=triangulos, mode="triangle"),
                       color=rgb(tono), z=z, double_sided=True)
        self.cajas = {}
        for n in d.nodos:
            x, y, w, h = disp.cajas[n.id]
            self.cajas[n.id] = self._caja(raiz, n, x, y, w, h, px, n.id == id_final)

    def _caja(self, raiz, n, x, y, w, h, px, actual):
        visto = bool(n.visto)
        if visto:
            if n.tipo == "final":
                tono = uc.nombre_resultado(n.resultado)[1]
            else:
                tono = TONO_TIPO.get(n.tipo, TONO_VISTO)
        else:
            tono = TONO_NO_VISTO
        caja = panel_tinta(raiz, w, h, tono=tono, radio_px=estilo.RADIO_CHIP_PX, sombra=visto,
                           borde_px=3 if actual else 2, position=(x, y, 0))
        if actual:
            caja.borde.color = rgb(estilo.COLOR_ACENTO)
        txt = Text("", parent=caja, origin=(0, 0), z=-0.01, scale=escala_fuente(px), font=tipografia.FUENTE_TITULO,
                   color=rgb(estilo.COLOR_TEXTO))
        txt.line_height = 1.05
        if visto:
            claro = n.tipo == "final"
            txt.color = rgb(estilo.tono_legible(estilo.TINTA, tono) if claro else estilo.COLOR_TEXTO)
            ajustar(txt, n.etiqueta or "", w - 2 * dc.RELLENO, px, max_lineas=dc.lineas_que_caben(h, px))
        else:
            txt.text = "?"
            txt.scale = escala_fuente(px + 8)
            txt.color = rgb((110, 112, 130))
        return caja

    # -- Entrada --

    def _pulsar(self):
        if self.fase == "tarjeta" and self.diagrama_ok:
            self.fase = "diagrama"
            self.tarjeta.enabled = False
            self.diagrama.enabled = True
            self.boton_salir = BotonPrimario("Salir de la Fiscalía", al_clic=self._pulsar, ancho=0.46, alto=ALTO_BOTON,
                                             tamano_fuente_px=uc.TAM["boton"], parent=self.diagrama,
                                             position=(0, -0.425, -0.01))
            self.boton_salir.fijar_foco(True)
            return
        if self._cerrado:
            return
        self._cerrado = True
        if self._al_cerrar is not None:
            self._al_cerrar()

    def tecla(self, key):
        if key in ("enter", "space", "gamepad a"):
            self._pulsar()
        return True
