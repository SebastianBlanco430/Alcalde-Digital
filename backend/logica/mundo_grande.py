# Mundo del mapa grande (modelo puro, sin ursina): MundoCiudad + lo que hace falta para trabajar POR CHUNKS de 64 m
# (los mismos del TerrenoGrande: origen = terreno.extension, nodos de la grilla global).
#
#   chunk_de(x, z)                 -> (ci, cj) del chunk que contiene el punto (sujeto a la rejilla de chunks).
#   limites_de_chunk(ci, cj)       -> (xmin, xmax, zmin, zmax).
#   contenido_de_chunk(ci, cj, h)  -> dict con lo que toca el chunk ensanchado `h` m (obstaculos, casas, edificios,
#                                     escaleras, callejones, zonas, segmentos, becos); ver VistaChunk (vista_chunk.py).
#   muros_de_chunk(ci, cj)         -> muros de contención del chunk (calculados al pedirlos y guardados); muros() los junta
#                                     TODOS (caro: recorre el terreno entero, solo para pruebas o herramientas).
#   firma_datos()                  -> huella estable (hex) del contenido generado; igual entre procesos y equipos.
#   firma_casas()                  -> crc32 de las casas redondeadas (la clave `casas` de la huella online).
#
# MundoCiudad no se modifica: esto es una subclase. La colisión, la altura y el GPS son los de siempre.

import hashlib
import math
import zlib

from backend.datos.indice_espacial import IndiceUniforme
from backend.datos.muros import muros_de_contencion
from backend.logica.mundo_ciudad import CasaDecorativa, MundoCiudad

LADO_CHUNK = 64.0
CELDA_INDICE = 32.0
PUNTOS_FIRMA = 96                 # alturas de muestra que entran en la firma


def _r(v, n=3):
    return round(float(v), n) + 0.0


def _caja_obstaculo(o):
    if o.es_circulo:
        return (o.cx - o.radio, o.cx + o.radio, o.cz - o.radio, o.cz + o.radio)
    return (o.cx - o.ancho / 2, o.cx + o.ancho / 2, o.cz - o.fondo / 2, o.cz + o.fondo / 2)


def _caja_segmento(ax, az, bx, bz, m=0.0):
    return (min(ax, bx) - m, max(ax, bx) + m, min(az, bz) - m, max(az, bz) + m)


def _se_tocan(c, v):
    return c[0] <= v[1] and v[0] <= c[1] and c[2] <= v[3] and v[2] <= c[3]


class _VentanaTerreno:
    """Un recorte rectangular de un terreno para muros_de_contencion: solo cambia `extension`."""

    def __init__(self, terreno, extension):
        self._t = terreno
        self.extension = extension

    def altura(self, x, z):
        return self._t.altura(x, z)

    def caminable(self, x, z):
        return self._t.caminable(x, z)


class MundoGrande(MundoCiudad):

    def __init__(self, mapa, edificios, obstaculos, semilla=0, becos=(), lineas_libres=(), **kw):
        super().__init__(mapa, edificios, obstaculos, **kw)
        if self.terreno is None or not hasattr(self.terreno, "grilla_de_chunk"):
            raise ValueError("MundoGrande necesita un TerrenoGrande.")
        self.semilla = semilla
        self._becos = list(becos)
        self._lineas_libres = [tuple(map(tuple, l)) for l in lineas_libres]
        t = self.terreno
        self._x0, self._x1, self._z0, self._z1 = t.extension
        self.chunks_x, self.chunks_z = t.chunks_x, t.chunks_z
        self._indices = None
        self._muros_chunk = {}
        self._perfiles_idx = None

    # -- Comercios --

    @property
    def anclas_comercios(self):
        """{id de comercio: ancla} de este mundo (ANCLAS_COMERCIOS_GRANDE): ver backend.logica.comercios.ancla_de."""
        from backend.datos.ciudad_grande import ANCLAS_COMERCIOS_GRANDE
        return ANCLAS_COMERCIOS_GRANDE

    # -- Becos --

    def becos(self):
        return list(self._becos)

    # -- Chunks --

    def chunk_de(self, x, z):
        ci = int(math.floor((x - self._x0) / LADO_CHUNK))
        cj = int(math.floor((z - self._z0) / LADO_CHUNK))
        return min(max(ci, 0), self.chunks_x - 1), min(max(cj, 0), self.chunks_z - 1)

    def limites_de_chunk(self, ci, cj):
        if not (0 <= ci < self.chunks_x and 0 <= cj < self.chunks_z):
            raise IndexError(f"chunk ({ci}, {cj}) fuera de rango ({self.chunks_x} x {self.chunks_z})")
        x0, z0 = self._x0 + ci * LADO_CHUNK, self._z0 + cj * LADO_CHUNK
        return (x0, min(x0 + LADO_CHUNK, self._x1), z0, min(z0 + LADO_CHUNK, self._z1))

    def numero_de_chunks(self):
        return self.chunks_x * self.chunks_z

    def _indexar(self):
        if self._indices is not None:
            return self._indices
        idx = {k: IndiceUniforme(CELDA_INDICE) for k in
               ("obstaculos", "edificios", "escaleras", "callejones", "zonas", "segmentos", "becos")}
        for o in self._obstaculos:
            idx["obstaculos"].insertar(o, _caja_obstaculo(o))
        for e in self._edificios:
            idx["edificios"].insertar(e, e.caja())
        for e in self._escaleras:
            idx["escaleras"].insertar(e, _caja_segmento(e.ax, e.az, e.bx, e.bz, e.ancho / 2))
        for c in self._callejones:
            idx["callejones"].insertar(c, _caja_segmento(c.ax, c.az, c.bx, c.bz, c.ancho / 2))
        for z in self._zonas:
            idx["zonas"].insertar(z, z.caja())
        for a, b in self._mapa.segmentos():
            (ax, az), (bx, bz) = self._mapa.coordenada(a), self._mapa.coordenada(b)
            idx["segmentos"].insertar((a, b, (ax, az), (bx, bz)), _caja_segmento(ax, az, bx, bz, self.ancho_calle / 2))
        for b in self._becos:
            xs, zs = [p[0] for p in b.puntos], [p[1] for p in b.puntos]
            idx["becos"].insertar(b, (min(xs) - b.ancho / 2, max(xs) + b.ancho / 2, min(zs) - b.ancho / 2, max(zs) + b.ancho / 2))
        self._indices = idx
        return idx

    def _consulta(self, clase, caja, caja_de):
        cx, cz = (caja[0] + caja[1]) / 2, (caja[2] + caja[3]) / 2
        r = max(caja[1] - caja[0], caja[3] - caja[2]) / 2
        return [it for it in self._indexar()[clase].cerca(cx, cz, r) if _se_tocan(caja_de(it), caja)]

    def contenido_de_chunk(self, ci, cj, halo=0.0):
        """Lo que toca el rectángulo del chunk ensanchado `halo` m, en el orden de generación (por intersección de cajas)."""
        x0, x1, z0, z1 = self.limites_de_chunk(ci, cj)
        caja = (x0 - halo, x1 + halo, z0 - halo, z1 + halo)
        obstaculos = self._consulta("obstaculos", caja, _caja_obstaculo)
        return {
            "limites": (x0, x1, z0, z1),
            "obstaculos": obstaculos,
            "casas": [o for o in obstaculos if isinstance(o, CasaDecorativa)],
            "edificios": self._consulta("edificios", caja, lambda e: e.caja()),
            "escaleras": self._consulta("escaleras", caja, lambda e: _caja_segmento(e.ax, e.az, e.bx, e.bz, e.ancho / 2)),
            "callejones": self._consulta("callejones", caja, lambda c: _caja_segmento(c.ax, c.az, c.bx, c.bz, c.ancho / 2)),
            "zonas": self._consulta("zonas", caja, lambda z: z.caja()),
            "segmentos": self._consulta("segmentos", caja, lambda s: _caja_segmento(*s[2], *s[3], self.ancho_calle / 2)),
            "becos": self._consulta("becos", caja, lambda b: _caja_segmento(
                min(p[0] for p in b.puntos), min(p[1] for p in b.puntos),
                max(p[0] for p in b.puntos), max(p[1] for p in b.puntos), b.ancho / 2)),
        }

    # -- Muros --

    def muros_de_chunk(self, ci, cj):
        clave = (ci, cj)
        if clave not in self._muros_chunk:
            lim = self.limites_de_chunk(ci, cj)
            if lim[1] - lim[0] < 2 or lim[3] - lim[2] < 2:
                self._muros_chunk[clave] = []
            else:
                caja = (lim[0] - 4, lim[1] + 4, lim[2] - 4, lim[3] + 4)
                escaleras = self._consulta("escaleras", caja, lambda e: _caja_segmento(e.ax, e.az, e.bx, e.bz, e.ancho / 2))
                cajas = [e.caja() for e in self._consulta("edificios", caja, lambda e: e.caja())]
                cajas += [_caja_obstaculo(o) for o in self._consulta("obstaculos", caja, _caja_obstaculo)
                          if isinstance(o, CasaDecorativa)]
                lineas = [l for l in self._lineas_libres if _se_tocan(_caja_segmento(*l[0], *l[1]), caja)]
                self._muros_chunk[clave] = muros_de_contencion(
                    _VentanaTerreno(self.terreno, lim), escaleras, cajas, lineas_libres=lineas)
        return list(self._muros_chunk[clave])

    def muros(self):
        """Todos los muros (recorre todos los chunks: caro; el juego pide muros_de_chunk)."""
        return [m for cj in range(self.chunks_z) for ci in range(self.chunks_x) for m in self.muros_de_chunk(ci, cj)]

    # -- Escaleras indexadas --

    def perfil_escalera_en(self, x, z):
        if self.terreno is None:
            return None
        if self._perfiles_idx is None:
            idx = IndiceUniforme(CELDA_INDICE)
            for p in self.perfiles_escaleras():
                e = p.escalera
                idx.insertar(p, _caja_segmento(e.ax, e.az, e.bx, e.bz, e.ancho / 2))
            self._perfiles_idx = idx
        for perfil in self._perfiles_idx.cerca(x, z, 0.0):
            if perfil.escalera.contiene(x, z):
                return perfil
        return None

    # -- Firmas --

    def _filas_casas(self):
        return [(c.modelo, _r(c.cx, 2), _r(c.cz, 2), _r(c.ancho), _r(c.fondo), c.rumbo, _r(c.escala), c.pisos,
                 _r(c.estiramiento), c.variante) for c in self._obstaculos if isinstance(c, CasaDecorativa)]

    def firma_casas(self):
        return "%08x" % (zlib.crc32(repr(self._filas_casas()).encode("utf-8")) & 0xFFFFFFFF)

    def firma_datos(self):
        """sha256 (32 hex) de: semilla, lugares y calles, edificios, casas, resto de obstáculos, escaleras, becos, zonas,
        callejones y una muestra fija de alturas. Solo redondeos a 2-3 decimales: igual en cualquier proceso."""
        xmin, xmax, zmin, zmax = self._limites
        muestra = []
        for k in range(PUNTOS_FIRMA):          # rejilla fija, sin azar
            x = xmin + (xmax - xmin) * ((k * 37) % PUNTOS_FIRMA + 0.5) / PUNTOS_FIRMA
            z = zmin + (zmax - zmin) * ((k * 59) % PUNTOS_FIRMA + 0.5) / PUNTOS_FIRMA
            muestra.append(_r(self.altura(x, z), 2))
        datos = [
            self.semilla,
            [(l, _r(self.coordenada(l)[0], 2), _r(self.coordenada(l)[1], 2)) for l in self.lugares()],
            sorted(sorted(s) for s in self.segmentos()),
            [(e.lugar, _r(e.cx), _r(e.cz), _r(e.ancho), _r(e.fondo), _r(e.alto), e.lado_puerta, e.modelo, _r(e.y))
             for e in self._edificios],
            self._filas_casas(),
            [(o.tipo, _r(o.cx, 2), _r(o.cz, 2)) for o in self._obstaculos if not isinstance(o, CasaDecorativa)],
            [(_r(e.ax, 2), _r(e.az, 2), _r(e.bx, 2), _r(e.bz, 2), _r(e.ancho, 2)) for e in self._escaleras],
            [([(_r(x, 2), _r(z, 2)) for x, z in b.puntos], b.ancho, len(b.escaleras)) for b in self._becos],
            [(z.tipo, _r(z.cx, 2), _r(z.cz, 2), _r(z.ancho), _r(z.fondo), z.rumbo) for z in self._zonas],
            [(_r(c.ax, 2), _r(c.az, 2), _r(c.bx, 2), _r(c.bz, 2), _r(c.ancho, 2)) for c in self._callejones],
            muestra,
        ]
        return hashlib.sha256(repr(datos).encode("utf-8")).hexdigest()[:32]

    def __repr__(self):
        return (f"MundoGrande(lugares={len(self.lugares())}, edificios={len(self._edificios)}, "
                f"obstaculos={len(self._obstaculos)}, becos={len(self._becos)}, chunks={self.chunks_x}x{self.chunks_z})")
