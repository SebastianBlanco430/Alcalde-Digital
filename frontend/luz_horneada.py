# Luz horneada en el mundo (punto 4): aplica en los COLORES DE VÉRTICE, al construir, el factor de
# frontend/luz_horneada_calculos.py (cara al sol / a la sombra / techo + oclusión falsa en la base de las paredes).
# Costo cero en el loop: nada de esto corre por frame. El factor MULTIPLICA el color que ya había (pintura del piso,
# tinte, ruido), y el color de entidad / de las luces que pone ciudad_viva de noche se sigue multiplicando encima.
#
# Dónde se usa (frontend/ciudad_3d.py y frontend/casas_decorativas.py):
#   - grupos combinados con combine() de cubos («edificios»: bases, losas y pilotes de las casas; «muros»): después del
#     combine(), con las normales y los vértices de la malla combinada (ya en el marco del grupo). La base de cada pieza
#     se reconstruye con los conteos de vértices que combine() recorre (mismo filtro y orden: conteos_para_combine).
#   - casas de la favela (.glb copiados y aplanados): se hornea una VARIANTE por (fuente, giro, escala, ¿planta baja?)
#     antes de copiarla, en el marco ya girado y escalado; la AO solo en la planta baja (contacto con el suelo).
#   - edificios jugables (.glb pintados, una Entity cada uno): sus colores planos se pasan a color de vértice
#     (fusion_materiales.hornear_colores) y se hornean con la transformación de su Entity.
# NO se toca: suelo/ladera (ya lleva ruido por vértice), calles, plazas (suelo_favela), cascos de tinta, ventanas, luces.
#
# Límite conocido: el color de vértice se interpola entre vértices; en una pared de un solo quad (cubos) la franja de
# AO se estira a todo el alto (gradiente suave de abajo hacia arriba) en vez de quedar en los primeros 0.6 m.
#
# BANDERA: ALCALDE_LUZ_HORNEADA=0 (o luz_horneada_calculos.LUZ_HORNEADA = False): nada de esto corre.
# Nunca lanza: si algo falla, deja la geometría como estaba y avisa una vez por stderr.

import sys

from panda3d.core import ColorAttrib, Geom, LMatrix3f, LVecBase3f, NodePath

from frontend import luz_horneada_calculos as calc

PASO_ESCALA = 0.1        # agrupación de escalas de las variantes de las casas (ver VariantesHorneadas)
_AVISADO = []


def activa():
    return calc.luz_horneada_activa()


def _avisar(donde, error):
    if not _AVISADO:
        _AVISADO.append(True)
        print(f"[luz_horneada] {donde} sin hornear ({type(error).__name__}: {error})", file=sys.stderr)


# -- Núcleo: hornea un GeomVertexData en su lugar --

def _columna(formato, nombre):
    """(índice de arreglo, columna) o (None, None)."""
    indice = formato.get_array_with(nombre)
    if indice < 0:
        return None, None
    return indice, formato.get_column(nombre)


def _hornear_datos(datos, matriz, m_normal, sol, base_y=None, bases=None):
    """Multiplica la columna «color» de `datos` (GeomVertexData escribible) por el factor de luz de cada fila. Normales
    llevadas al marco de referencia con `m_normal` (LMatrix3f) y alturas con `matriz` (LMatrix4f). AO con `base_y`
    (una base para todo) o `bases` (lista por fila); sin ninguna, solo la luz por orientación. Devuelve las filas."""
    formato = datos.get_format()
    iv, cv = _columna(formato, "vertex")
    inn, cn = _columna(formato, "normal")
    ic, cc = _columna(formato, "color")
    if cv is None or cn is None or cc is None:
        return 0
    filas = datos.get_num_rows()
    if bases is not None and len(bases) != filas:
        bases = None
    tipo_color = cc.get_numeric_type()
    rapido = (cv.get_numeric_type() == Geom.NT_float32 and cn.get_numeric_type() == Geom.NT_float32
              and cv.get_num_components() >= 3 and cn.get_num_components() == 3 and cc.get_num_components() == 4
              and tipo_color in (Geom.NT_uint8, Geom.NT_float32)
              and not (cv.get_start() % 4 or cn.get_start() % 4 or cc.get_start() % 4))
    if not rapido:
        return _hornear_datos_lento(datos, matriz, m_normal, sol, base_y, bases)
    entero = tipo_color == Geom.NT_uint8
    # Se trabaja sobre COPIAS en Python de los bytes (get_data/set_data del handle): una memoryview viva sobre un arreglo
    # de Panda lo deja bloqueado y el render se colgaba al dibujarlo.
    crudo_c = bytearray(datos.modify_array_handle(ic).get_data())
    if entero:
        col = memoryview(crudo_c)
        paso_c, ini_c, tope = formato.get_array(ic).get_stride(), cc.get_start(), 255
    else:
        col = memoryview(crudo_c).cast("f")
        paso_c, ini_c, tope = formato.get_array(ic).get_stride() // 4, cc.get_start() // 4, 1.0
    ver = memoryview(datos.get_array(iv).get_handle().get_data()).cast("f")
    nor = ver if inn == iv else memoryview(datos.get_array(inn).get_handle().get_data()).cast("f")
    paso_v, ini_v = formato.get_array(iv).get_stride() // 4, cv.get_start() // 4
    paso_n, ini_n = formato.get_array(inn).get_stride() // 4, cn.get_start() // 4
    m01, m11, m21, m31 = matriz.get_cell(0, 1), matriz.get_cell(1, 1), matriz.get_cell(2, 1), matriz.get_cell(3, 1)
    usar_ao = base_y is not None or bases is not None
    alto_ao = calc.ALTO_AO
    memo = {}
    for fila in range(filas):
        b = fila * paso_n + ini_n
        clave = (nor[b], nor[b + 1], nor[b + 2])
        dato = memo.get(clave)
        if dato is None:
            n = m_normal.xform(LVecBase3f(*clave))
            f = calc.factor_direccional((n[0], n[1], n[2]), sol)
            largo = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) ** 0.5
            arriba = n[1] / largo if largo > 1e-6 and largo == largo else 0.0
            dato = memo[clave] = (f[0], f[1], f[2], max(0.0, arriba))
        f0, f1, f2, arriba = dato
        if usar_ao:
            a = fila * paso_v + ini_v
            y = ver[a] * m01 + ver[a + 1] * m11 + ver[a + 2] * m21 + m31
            altura = y - (bases[fila] if bases is not None else base_y)
            if altura < alto_ao or altura != altura:
                ao = calc.factor_ao(altura)
                if arriba > 0.0:
                    ao = ao + (1.0 - ao) * arriba
                f0, f1, f2 = f0 * ao, f1 * ao, f2 * ao
        if f0 == 1.0 and f1 == 1.0 and f2 == 1.0:
            continue
        c = fila * paso_c + ini_c
        if entero:
            col[c] = min(tope, int(col[c] * f0 + 0.5))
            col[c + 1] = min(tope, int(col[c + 1] * f1 + 0.5))
            col[c + 2] = min(tope, int(col[c + 2] * f2 + 0.5))
        else:
            col[c] = min(tope, col[c] * f0)
            col[c + 1] = min(tope, col[c + 1] * f1)
            col[c + 2] = min(tope, col[c + 2] * f2)
    col.release()
    datos.modify_array_handle(ic).set_data(bytes(crudo_c))
    return filas


def _hornear_datos_lento(datos, matriz, m_normal, sol, base_y=None, bases=None):
    """Lo mismo con lectores de Panda (formatos raros: normales empaquetadas, colores de 16 bits...)."""
    from panda3d.core import GeomVertexReader, GeomVertexRewriter
    lector_v = GeomVertexReader(datos, "vertex")
    lector_n = GeomVertexReader(datos, "normal")
    color = GeomVertexRewriter(datos, "color")
    fila = 0
    while not color.is_at_end():
        n = m_normal.xform(lector_n.get_data3())
        v = lector_v.get_data3()
        altura = None
        if bases is not None or base_y is not None:
            altura = matriz.xform_point(v).y - (bases[fila] if bases is not None else base_y)
        c = color.get_data4()
        color.set_data4(calc.aplicar((c[0], c[1], c[2], c[3]), calc.factor_vertice((n[0], n[1], n[2]), altura, sol)))
        fila += 1
    return fila


# -- Mallas combinadas de Ursina (combine()) --

def conteos_para_combine(grupo):
    """Vértices de cada pieza que combine() fundirá, en su mismo orden (recorre scene.entities con su mismo filtro).
    None si alguna pieza no trae vértices a mano (entonces no se hace AO, solo la luz por orientación)."""
    from ursina import scene
    conteos = []
    for e in scene.entities:
        if not e.enabled or not (e == grupo or e.has_ancestor(grupo)):
            continue
        if not hasattr(e, "model") or e.model is None or e.scripts or e.eternal:
            continue
        vertices = getattr(e.model, "vertices", None)
        if not vertices:
            return None
        conteos.append(len(vertices))
    return conteos


def hornear_malla_combinada(entidad, conteos=None, direccion_sol=calc.DIRECCION_SOL_POR_DEFECTO):
    """Multiplica los colores de la malla combinada de `entidad` por el factor de luz de cada vértice: normales de la
    malla (ya en el marco del grupo) y AO por la base de cada pieza si `conteos` cuadra. Usa la vía de Ursina (lista
    `colors` + generate()): escribir directo en el geom que generó Mesh colgaba el primer render_frame (2026-11-21, sin
    causa raíz aislada; la vía de Ursina no lo hace). Devuelve cuántos vértices horneó."""
    try:
        malla = entidad.model
        vertices, normales, colores = malla.vertices, malla.normals, malla.colors
        if not vertices or not normales or not colores or not (len(normales) == len(colores) == len(vertices)):
            return 0
        bases = calc.bases_por_pieza([v[1] for v in vertices], conteos) if conteos is not None else None
        memo = {}
        alto_ao = calc.ALTO_AO
        nuevos = []
        for i, (v, n, c) in enumerate(zip(vertices, normales, colores)):
            clave = (n[0], n[1], n[2])
            dato = memo.get(clave)
            if dato is None:
                f = calc.factor_direccional(clave, direccion_sol)
                largo = (n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) ** 0.5
                arriba = n[1] / largo if largo > 1e-6 and largo == largo else 0.0
                dato = memo[clave] = (f, max(0.0, arriba))
            f, arriba = dato
            if bases is not None:
                altura = v[1] - bases[i]
                if altura < alto_ao or altura != altura:
                    ao = calc.factor_ao(altura)
                    if arriba > 0.0:
                        ao = ao + (1.0 - ao) * arriba
                    f = (f[0] * ao, f[1] * ao, f[2] * ao)
            nuevos.append(calc.aplicar((c[0], c[1], c[2], c[3]), f))
        from ursina import Color
        malla.colors = [Color(*c) for c in nuevos]
        malla.generate()
        return len(nuevos)
    except Exception as error:      # noqa: BLE001
        _avisar(getattr(entidad, "name", "malla"), error)
        return 0


# -- Nodos de Panda (.glb) --

def _matriz_normal(matriz):
    m3 = LMatrix3f(matriz.get_upper_3())
    if not m3.invert_in_place():
        return None
    m3.transpose_in_place()
    return m3


def hornear_nodo(raiz, referencia, base_y=None, direccion_sol=calc.DIRECCION_SOL_POR_DEFECTO):
    """Hornea la luz en los colores de vértice de todos los geoms de `raiz` (NodePath) que USAN color de vértice
    (ColorAttrib de vértice y columna «color»), con normales y alturas en el marco de `referencia` (NodePath). `base_y`
    (en ese marco) activa la AO; None = sin AO. Modifica copias propias de los geoms (copy-on-write: las fuentes que
    compartían datos no se tocan). Devuelve cuántos vértices horneó; nunca lanza."""
    total = 0
    try:
        caminos = list(raiz.find_all_matches("**/+GeomNode"))
        if raiz.node().is_geom_node():           # find_all_matches no incluye la raíz misma
            caminos.insert(0, raiz)
        for camino in caminos:
            nodo = camino.node()
            matriz = camino.get_mat(referencia)
            m_normal = _matriz_normal(matriz)
            if m_normal is None:
                continue
            for i in range(nodo.get_num_geoms()):
                atributo = nodo.get_geom_state(i).get_attrib(ColorAttrib)
                if atributo is None or atributo.get_color_type() != ColorAttrib.T_vertex:
                    continue
                datos_ro = nodo.get_geom(i).get_vertex_data()
                if not (datos_ro.has_column("color") and datos_ro.has_column("normal")):
                    continue
                datos = nodo.modify_geom(i).modify_vertex_data()
                total += _hornear_datos(datos, matriz, m_normal, direccion_sol, base_y=base_y)
    except Exception as error:      # noqa: BLE001
        _avisar(raiz.get_name() if hasattr(raiz, "get_name") else "nodo", error)
    return total


class VariantesHorneadas:
    """Caché de fuentes horneadas para las casas de la favela: una variante por (clave de la fuente, giro, escala,
    estiramiento, ¿con AO?). La variante es una copia de la fuente con los colores ya horneados en el marco girado y
    escalado; luego se copia y se coloca como la fuente (su propia transformación queda en identidad)."""

    def __init__(self, direccion_sol=calc.DIRECCION_SOL_POR_DEFECTO):
        self.sol = direccion_sol
        self._variantes = {}
        self.vertices = 0

    def de(self, clave, fuente, rumbo, escala, estiramiento, con_ao):
        # La escala solo cambia la AO (alto en m de la franja) y el estiramiento, levemente, las normales: se agrupan de
        # a PASO_ESCALA (con escala ~2.5 el error en la franja de 0.6 m es de ~1 cm) para que las variantes se repitan.
        escala_q = max(PASO_ESCALA, round(escala / PASO_ESCALA) * PASO_ESCALA)
        est_q = max(PASO_ESCALA, round(estiramiento / PASO_ESCALA) * PASO_ESCALA)
        llave = (clave, round(rumbo % 360.0, 3), escala_q, est_q, bool(con_ao))
        variante = self._variantes.get(llave)
        if variante is None:
            soporte = NodePath("variante_luz")
            colocada = fuente.copy_to(soporte)
            colocada.set_pos(0, 0, 0)          # la copia final pone su propia posición (como la fuente)
            colocada.set_hpr(-rumbo, 0, 0)
            colocada.set_scale(escala_q, escala_q, escala_q * est_q)
            self.vertices += hornear_nodo(colocada, soporte, base_y=0.0 if con_ao else None, direccion_sol=self.sol)
            colocada.clear_transform()
            variante = self._variantes[llave] = colocada
        return variante
