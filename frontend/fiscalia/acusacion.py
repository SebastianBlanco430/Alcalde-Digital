# Acusación del caso de Fiscalía v2 (Ursina): la misma rueda de cuatro huecos, pero cada hueco es una FICHA de
# sospechoso: retrato pequeño dibujado con los colores del personaje (piel, pelo, ropa del JSON del caso), su nombre y la
# etiqueta de la acusación («Acusar a Marcos»). Una opción sin `personaje` («No acusar») sale sin retrato.
# Se usa con Rueda(fabrica=Ficha, ancho=ANCHO_FICHA, alto=ALTO_FICHA); los datos de los personajes van en `rueda.datos`.

from ursina import Entity, Text, color

from frontend import estilo, tipografia
from frontend.componentes import escala_fuente, modelo_redondeado, rgb
from frontend.fiscalia import ui_calculos as uc
from frontend.fiscalia.rueda import Hueco, ajustar

DIAMETRO = 0.074


def _rgb(valor, defecto):
    try:
        r, g, b = (max(0, min(255, int(v))) for v in list(valor)[:3])
        return r, g, b
    except Exception:                    # noqa: BLE001  retrato incompleto: un color neutro
        return defecto


def retrato_mini(padre, retrato, diametro=DIAMETRO, **opciones):
    """Busto plano: fondo redondo, hombros con el color de la ropa, cara con el de la piel y pelo encima."""
    retrato = retrato or {}
    piel = _rgb(retrato.get("piel"), (200, 160, 130))
    pelo = _rgb(retrato.get("pelo"), (60, 50, 50))
    ropa = _rgb(retrato.get("ropa"), (80, 90, 120))
    estilo_pelo = retrato.get("pelo_estilo", "corto")
    raiz = Entity(parent=padre, scale=diametro, **opciones)
    Entity(parent=raiz, model=modelo_redondeado(1, 1, 1000), scale=1.0, color=rgb(estilo.COLOR_FONDO), z=0.004)
    Entity(parent=raiz, model=modelo_redondeado(0.74, 0.40, 1000), position=(0, -0.33), scale=(0.74, 0.40),
           color=rgb(ropa), z=0.003)
    if estilo_pelo == "largo":
        Entity(parent=raiz, model=modelo_redondeado(0.50, 0.56, 1000), position=(0, 0.06), scale=(0.50, 0.56),
               color=rgb(pelo), z=0.0025)
    Entity(parent=raiz, model=modelo_redondeado(0.40, 0.46, 1000), position=(0, 0.07), scale=(0.40, 0.46),
           color=rgb(piel), z=0.002)
    if estilo_pelo != "calvo":
        Entity(parent=raiz, model=modelo_redondeado(0.42, 0.16, 1000), position=(0, 0.27), scale=(0.42, 0.16),
               color=rgb(pelo), z=0.001)
    if retrato.get("accesorio") == "gafas":
        Entity(parent=raiz, model="quad", position=(0, 0.10), scale=(0.34, 0.05), color=rgb(estilo.TINTA), z=0.0005)
    elif retrato.get("accesorio") == "barba":
        Entity(parent=raiz, model=modelo_redondeado(0.34, 0.14, 1000), position=(0, -0.08), scale=(0.34, 0.14),
               color=rgb(pelo), z=0.0005)
    return raiz


class Ficha(Hueco):
    """Hueco de la acusación: retrato + nombre + etiqueta."""

    def _contenido(self):
        x_texto = -self.ancho / 2 + 0.035 + DIAMETRO + 0.01
        self._x_texto = x_texto
        self.retrato = None
        self.vacio = Entity(parent=self.panel, model=modelo_redondeado(DIAMETRO, DIAMETRO, 1000),
                            scale=(DIAMETRO, DIAMETRO), position=(-self.ancho / 2 + 0.035 + DIAMETRO / 2, 0, -0.005),
                            color=color.rgba32(*estilo.PAPEL, 40))
        self.nombre = Text("", parent=self.panel, origin=(-0.5, 0), position=(x_texto, 0.018, -0.01),
                           scale=escala_fuente(uc.TAM["ficha_nombre"]), font=tipografia.fuente_piel(titulo=True),
                           color=rgb(estilo.COLOR_TEXTO))
        self.texto = Text("", parent=self.panel, origin=(-0.5, 0), position=(x_texto, -0.02, -0.01),
                          scale=escala_fuente(uc.TAM["ficha_etiqueta"]), color=rgb(estilo.COLOR_TEXTO))

    def _rellenar(self):
        o = self.opcion
        if self.retrato is not None:
            from frontend.componentes import destruir_arbol
            destruir_arbol(self.retrato)
            self.retrato = None
        if o is None:
            self.nombre.text = self.texto.text = ""
            return
        ancho_texto = self.ancho / 2 - self._x_texto - 0.012
        datos = getattr(self.parent, "datos", None) or {}
        pj = datos.get(getattr(o, "personaje", None)) if getattr(o, "personaje", None) else None
        self.vacio.enabled = pj is None
        if pj is not None:
            self.retrato = retrato_mini(self.panel, pj.get("retrato"),
                                        position=(-self.ancho / 2 + 0.035 + DIAMETRO / 2, 0, -0.005))
            self._poner_nombre(pj.get("nombre", o.personaje), ancho_texto)
            ajustar(self.texto, o.etiqueta, ancho_texto, uc.TAM["ficha_etiqueta"])
            self.texto.y = -0.02
        else:
            self.nombre.text = ""
            ajustar(self.texto, o.etiqueta if self.estado != "bloqueada" else (o.pista or "[Falta una prueba]"),
                    ancho_texto, uc.TAM["ficha_nombre"])
            self.texto.y = 0
        self.numero.x = -self.ancho / 2 + 0.017

    def _poner_nombre(self, nombre, ancho_texto):
        """El nombre entero si cabe a tamaño completo; si no, la primera forma más corta que quepa a tamaño completo
        («Profesor Eurico Matos» → «Eurico Matos»), y si ninguna, la primera que quepa encogida sin recortarse. Antes
        se encogía hasta el piso y se cortaba con «…» («Profesor Eurico…», S9)."""
        variantes = uc.variantes_nombre(nombre) or [str(nombre)]
        planes = []
        for v in variantes:
            plan = ajustar(self.nombre, v, ancho_texto, uc.TAM["ficha_nombre"])
            if not isinstance(plan, dict):
                return                                   # sin UI adaptable: el texto ya quedó puesto
            planes.append((v, plan))
            if not plan.get("recortado") and plan.get("escala", 1.0) >= 0.999:
                return
        elegido = next((v for v, p in planes if not p.get("recortado")), variantes[-1])
        ajustar(self.nombre, elegido, ancho_texto, uc.TAM["ficha_nombre"])

    def _colorear_texto(self, tono):
        self.texto.color = rgb(tono)
        self.nombre.color = rgb(tono)

    def _aplicar(self):
        super()._aplicar()
        if self.estado == "bloqueada":
            self.candado.x = self._x_texto - 0.03
