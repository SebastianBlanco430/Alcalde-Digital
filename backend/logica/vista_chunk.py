# Vista de UN chunk del mapa grande (modelo puro, sin ursina): todo lo que el frontend necesita para construir o
# descartar un chunk, ya recortado. Se arma con MundoGrande.contenido_de_chunk(ci, cj, halo).
#
#   obstaculos / casas / edificios / escaleras / callejones / zonas / becos / segmentos  = los que TOCAN el chunk
#       ensanchado `halo` m (un objeto grande aparece en cada chunk que toca; obstaculos_propios() da solo los de centro
#       dentro del chunk, sin repetidos entre chunks).
#   segmentos = [(lugar_a, lugar_b, (ax, az), (bx, bz))] de las calles que cruzan el chunk.
#   muros     = muros de contención del chunk (se calculan al primer acceso).
#   terreno   = TerrenoDeChunk: grilla de alturas del chunk (65 x 65 nodos con borde compartido) + altura(x, z).

from dataclasses import dataclass


@dataclass(frozen=True)
class TerrenoDeChunk:
    origen: tuple          # (x, z) del primer nodo
    paso: float
    filas: list            # filas[j][i] = altura del nodo (i, j) del chunk
    altura: object         # callable (x, z) del terreno completo (para quien necesite ir más allá del chunk)


class VistaChunk:

    def __init__(self, mundo, ci, cj, halo=0.0):
        from backend.datos.terreno import PASO_GRILLA
        self.mundo = mundo
        self.ci, self.cj, self.halo = ci, cj, halo
        c = mundo.contenido_de_chunk(ci, cj, halo)
        self.limites = c["limites"]
        self.obstaculos = c["obstaculos"]
        self.casas = c["casas"]
        self.edificios = c["edificios"]
        self.escaleras = c["escaleras"]
        self.callejones = c["callejones"]
        self.zonas = c["zonas"]
        self.becos = c["becos"]
        self.segmentos = c["segmentos"]
        self._muros = None
        t = mundo.terreno
        self.terreno = TerrenoDeChunk(t.origen_chunk(ci, cj), PASO_GRILLA, t.grilla_de_chunk(ci, cj), t.altura)

    @property
    def clave(self):
        return (self.ci, self.cj)

    @property
    def muros(self):
        if self._muros is None:
            self._muros = self.mundo.muros_de_chunk(self.ci, self.cj)
        return self._muros

    def obstaculos_propios(self):
        return [o for o in self.mundo.contenido_de_chunk(self.ci, self.cj, 0.0)["obstaculos"]
                if self.mundo.chunk_de(o.cx, o.cz) == (self.ci, self.cj)]

    def __repr__(self):
        return (f"VistaChunk({self.ci}, {self.cj}, halo={self.halo}, casas={len(self.casas)}, "
                f"edificios={len(self.edificios)}, escaleras={len(self.escaleras)})")
