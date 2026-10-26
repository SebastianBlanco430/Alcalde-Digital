# Casas del mapa grande, por chunk (el mundo chico sigue usando casas_decorativas.construir_casas_favela, sin cambios).
#
# LOD0 (casas completas, < ~110 m): el mismo pintado de la favela (casas_decorativas.pintar_modelo: paredes del color de
# su piso, techos de zinc/teja, ladrillo visto, relieve de ladrillo, puertas) pero con el color plano de cada geom
# PASADO A COLOR DE VÉRTICE (hornear_color_plano): así flatten_strong funde por TEXTURA y no por (textura, color). Un
# chunk de ~25 casas baja de ~55 a ~26 llamadas de dibujo (una por textura distinta; ver DRAWS_MAXIMOS_POR_CHUNK).
# El resultado se ve igual: el shader multiplica textura * color de vértice, igual que antes multiplicaba textura * color plano.
# También se quita el material de cada geom (el shader no lo lee y distinguía estados que son el mismo dibujo).
#
# Las fuentes pintadas (modelo x estilo) y las texturas corregidas se crean UNA vez y se comparten entre chunks
# (FabricaCasas); el relieve de ladrillo usa 3 brillos fijos (RELIEVES) en vez de uno por pared (antes 10+ texturas por chunk).
#
# LOD1 (cajas, 110-300 m): una caja de color por casa, con el techo de su color, en un Acumulador (frontend/geom_directa.py).
#
# Todo es generador cuando puede tardar: ceden el control cada pocas casas para que el gestor no pase de ~3 ms por frame.

from panda3d.core import (ColorAttrib, Geom, GeomVertexArrayFormat, GeomVertexFormat, GeomVertexWriter, InternalName,
                          MaterialAttrib, NodePath)
from ursina import Entity, load_model

from backend.datos.modelos_edificios import MODELOS, modelo_de
from frontend import casas_decorativas as cd
from frontend.componentes import rgb

# Brillos (0-255) a los que se llevan las texturas de relieve de ladrillo: el de cada pared se redondea al más cercano.
RELIEVES = (146, 162, 178)
DRAWS_MAXIMOS_POR_CHUNK = 35          # tope de geoms de las casas de un chunk (lo comprueba la prueba de humo)
CASAS_POR_TANDA = 4                   # pisos que se copian entre una cesión y otra
# LOD1: la pared pintada se ve con la textura de concreto (~0,66 de brillo en la esquina) y el zinc/teja ~0,8.
FACTOR_PARED_LOD1 = 0.68
FACTOR_TECHO_LOD1 = 0.82


class TexturasCompartidas(cd._Texturas):
    """_Texturas con el relieve de ladrillo en RELIEVES brillos fijos (menos texturas y menos estados distintos)."""

    def relieve_ladrillo(self, media=cd.BRILLO_PARED):
        cerca = min(RELIEVES, key=lambda r: abs(r - media))
        return super().relieve_ladrillo(cerca)

    # Igual que la de _Texturas, pero guardada por (textura, clase): recalcularla copiaba la imagen entera (~8 ms) por cada fuente nueva.
    def brillo_visible(self, tex, clase):
        clave = ("brillo", tex.get_name(), clase)
        if clave not in self._cache:
            self._cache[clave] = super().brillo_visible(tex, clase)
        return self._cache[clave]


def _formato_con_color(formato):
    """Formato igual al dado más una columna de color (uint8 x4) si no la tiene; registrado en Panda."""
    for k in range(formato.get_num_columns()):
        if formato.get_column(k).get_name() == InternalName.get_color():
            return formato
    base = GeomVertexArrayFormat(formato.get_array(0))
    base.add_column(InternalName.get_color(), 4, Geom.NT_uint8, Geom.C_color)
    nuevo = GeomVertexFormat()
    nuevo.add_array(base)
    return GeomVertexFormat.register_format(nuevo)


def hornear_color_plano(nodo):
    """Pasa el color plano de cada geom de `nodo` a color de vértice y le quita el material. Devuelve `nodo`."""
    for camino in nodo.find_all_matches("**/+GeomNode"):
        gn = camino.node()
        for i in range(gn.get_num_geoms()):
            estado = gn.get_geom_state(i)
            atributo = estado.get_attrib(ColorAttrib)
            if atributo is not None and atributo.get_color_type() == ColorAttrib.T_flat:
                c = atributo.get_color()
                rgba = (c[0], c[1], c[2], c[3])
            else:
                rgba = (1.0, 1.0, 1.0, 1.0)
            datos = gn.modify_geom(i).modify_vertex_data()
            datos.set_format(_formato_con_color(datos.get_format()))
            escritor = GeomVertexWriter(datos, "color")
            for _ in range(datos.get_num_rows()):
                escritor.add_data4(*rgba)
            estado = estado.set_attrib(ColorAttrib.make_vertex())
            if estado.has_attrib(MaterialAttrib):
                estado = estado.remove_attrib(MaterialAttrib)
            gn.set_geom_state(i, estado)
    return nodo


class FabricaCasas:
    """Fuentes pintadas (con el color ya en los vértices), cascos de tinta y texturas, creados una vez y compartidos."""

    def __init__(self):
        self.texturas = TexturasCompartidas()
        self._fuentes = {}
        self._cascos = {}

    # Fuente de `modelo` pintada con el estilo (pintura, ladrillo, techo) y el relieve dados, lista para copiar.
    def fuente(self, modelo, estilo, relieve):
        clave = (modelo,) + tuple(estilo) + (bool(relieve),)
        f = self._fuentes.get(clave)
        if f is None:
            pintura, ladrillo, techo = estilo
            f = cd._fuente_viva(modelo, pintura, ladrillo, techo, self.texturas, relieve)
            hornear_color_plano(f)
            self._fuentes[clave] = f
        return f

    def casco(self, modelo):
        c = self._cascos.get(modelo)
        if c is None:
            c = self._cascos[modelo] = cd._casco(modelo)
        return c

    @property
    def fuentes_creadas(self):
        return len(self._fuentes)

    def precalentar(self):
        """Generador: crea ya todas las texturas corregidas (las de cada clase de cada modelo) y el relieve de ladrillo,
        para que ningún chunk pague su creación ni su subida a la GPU en pleno juego. Cede tras cada textura."""
        from panda3d.core import TextureAttrib
        for nombre in MODELOS:
            modelo = load_model(modelo_de(nombre).archivo)
            for camino in modelo.find_all_matches("**/+GeomNode"):
                nodo = camino.node()
                for i in range(nodo.get_num_geoms()):
                    atributo = nodo.get_geom_state(i).get_attrib(TextureAttrib)
                    tex = atributo.get_texture() if atributo else None
                    if tex is None:
                        continue
                    clase = cd.clase_de_textura(tex.get_name())
                    self.texturas.de(tex, clase)
                    yield
        self.texturas.ladrillo_vivo()
        yield
        for r in RELIEVES:
            self.texturas.relieve_ladrillo(r)
            yield


def pisos_de(casas):
    """[(casa, piso)] de todas las casas, en orden."""
    return [(c, p) for c in casas for p in range(getattr(c, "pisos", 1))]


def lote_de_casas(fabrica, casas, alturas, contorno=True, tanda=CASAS_POR_TANDA):
    """Generador: copia cada piso de cada casa (con su pintura) bajo una raíz y la funde con flatten_strong. Su valor de
    retorno es (lote, tinta): NodePath de las casas y NodePath del casco de tinta (None si contorno=False)."""
    raiz = NodePath("casas_chunk")
    raiz_tinta = NodePath("contorno_chunk") if contorno else None
    hechos = 0
    for casa, y in zip(casas, alturas):
        m = modelo_de(casa.modelo)
        alto_piso = m.alto * casa.escala
        est = getattr(casa, "estiramiento", 1.0)
        for piso in range(getattr(casa, "pisos", 1)):
            estilo = cd.estilo_del_piso(casa, piso)
            relieve = cd.relieve_del_piso(casa, piso, estilo[1])
            copia = fabrica.fuente(casa.modelo, estilo, relieve).copy_to(raiz)
            copia.set_pos(casa.cx, y + piso * alto_piso, casa.cz)
            copia.set_hpr(-casa.rumbo, 0, 0)
            copia.set_scale(casa.escala, casa.escala, casa.escala * est)
            if raiz_tinta is not None:
                casco = fabrica.casco(casa.modelo).copy_to(raiz_tinta)
                inferior = cd.SUBE_CONTORNO_PISO if piso else -cd.BAJA_CONTORNO_SUELO
                cd._colocar_casco(casco, m, casa, est, (casa.cx, y + piso * alto_piso, casa.cz), alto_piso, inferior)
            hechos += 1
            if hechos % tanda == 0:
                yield
    yield
    raiz.clear_model_nodes()
    raiz.flatten_strong()
    yield
    if raiz_tinta is not None:
        raiz_tinta.clear_model_nodes()
        raiz_tinta.flatten_strong()
        raiz_tinta.set_light_off()
        yield
    return raiz, raiz_tinta


def cajas_lod1(acum, casas, apoyos):
    """LOD1: una caja por casa (pared del color de su piso de abajo, techo del suyo) en el Acumulador. `apoyos` = lista
    de (bajo, alto) alineada con `casas` (frontend/geometria_mundo.apoyo_de_caja)."""
    for casa, (bajo, alto) in zip(casas, apoyos):
        pintura, ladrillo, techo = cd.estilo_del_piso(casa, 0)
        pared = cd.TINTE_LADRILLO_VIVO if ladrillo else cd.PINTURAS[pintura]
        pared = tuple(int(c * FACTOR_PARED_LOD1) for c in pared)
        tapa = tuple(int(c * FACTOR_TECHO_LOD1) for c in cd.TECHOS[techo][0])
        piso_total = alto + casa.alto_total
        # la caja baja hasta el suelo más bajo de la huella (el zócalo de las casas en pendiente)
        y0 = bajo - 0.3
        acum.caja(casa.cx, (y0 + piso_total) / 2, casa.cz, casa.ancho, piso_total - y0, casa.fondo, 0.0,
                  color=pared, tapa=tapa, degradado=(0.9, 1.0))
