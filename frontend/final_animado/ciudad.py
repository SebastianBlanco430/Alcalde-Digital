# Estado de la ciudad durante el final animado (Ursina): etapa y hora del final, y fuera de escena lo que es del juego
# (peatones, NPC de ambiente y de etapa, avatares, vehículos, baliza, ruta del GPS, carteles y props de misión).
# Las capas de ciudad_viva (fuego, humo, banderines, confeti, flores, basura) se quedan: son el decorado base.
#
#   preparar(final)  fija etapa y hora y esconde; guarda lo que había
#   mantener()       cada frame: vuelve a esconder lo que otro módulo haya vuelto a mostrar (barato: NodePath.hide)
#   soltar()         devuelve etapa, hora y todo lo escondido. Idempotente, nunca lanza.
#
# Se esconde con NodePath.hide() y no con `enabled`: los vigías del juego encienden y apagan `enabled` (densidad de
# peatones, NPC de etapa, baliza...) y no tocan hide/show, así que nadie «se cuela» y al soltar todo queda como estaba.

import sys

from frontend import ambiente_vivo

TIPOS_FUERA = frozenset({"PersonajeNPC", "PersonajeModelo", "Personaje", "Peatones", "Baliza", "RutaPiso",
                         "MundoVehiculos", "Text", "MarcadorAviso", "MarcadorMision"})
NOMBRES_FUERA = frozenset({"bolsita_traspaso", "cartel_bicarbonato", "computador_caso"})


def _aviso(texto):
    print(f"[final_animado] {texto}", file=sys.stderr)


def estado_del_final(final):
    """{"etapa", "hora"} del final: de _calculos.estado_ciudad (director-final) o, sin él, del JSON del juego."""
    try:
        from frontend.final_animado import _calculos
        datos = _calculos.estado_ciudad(final)
        return {"etapa": int(datos["etapa"]), "hora": float(datos["hora"])}
    except Exception:
        from backend.logica import etapas_final
        datos = etapas_final.cargar_textos()["animacion"][final]
        return {"etapa": int(datos["etapa"]), "hora": float(datos["hora"])}


class EstadoCiudad:

    def __init__(self, escena, conexion=None):
        self.escena = escena
        self.conexion = conexion
        self.ocultos = []
        self._hora_antes = None
        self._etapa_antes = None
        self._controlador = None
        self._activo = False

    def controlador_etapas(self):
        ctrl = getattr(self.conexion, "etapas_final", None)
        if ctrl is None:
            ctrl = getattr(getattr(self.escena, "_conexion_globos", None), "etapas_final", None)
        if ctrl is None:
            for hijo in getattr(getattr(self.escena, "hud", None), "children", ()):
                if type(hijo).__name__ == "ControladorEtapas":
                    ctrl = hijo
                    break
        return ctrl

    def preparar(self, final):
        estado = estado_del_final(final)
        self._activo = True
        self._hora_antes = getattr(ambiente_vivo, "_hora_forzada", None)
        ambiente_vivo.fijar_hora_forzada(estado["hora"])
        ctrl = self.controlador_etapas()
        if ctrl is not None and callable(getattr(ctrl, "forzar_para_final", None)):
            ctrl.forzar_para_final(estado["etapa"])
            self._controlador = ctrl
        else:
            self._etapa_antes = ambiente_vivo.etapa()
            ambiente_vivo.fijar_etapa(estado["etapa"])
        self._repintar_cielo(estado["hora"])
        self.ocultos = []
        for np_ in self._candidatos():
            try:
                if not np_.isEmpty() and not np_.isHidden():
                    np_.hide()
                    self.ocultos.append(np_)
            except Exception:
                pass
        return estado

    def _candidatos(self):
        e = self.escena
        vistos = set()
        out = []

        def poner(x):
            if x is not None and id(x) not in vistos:
                vistos.add(id(x))
                out.append(x)

        poner(getattr(e, "peatones", None))
        poner(getattr(e, "baliza", None))
        poner(getattr(e, "ruta_piso", None))
        for avatar in getattr(e, "avatares", {}).values():
            poner(avatar)
        for hijo in list(getattr(e, "children", ())):
            if self._fuera(hijo):
                poner(hijo)
            elif type(hijo).__name__ == "ControladorCiudadViva":
                for npc in self._npc_de_capas(getattr(hijo, "raiz", None)):
                    poner(npc)
        return out

    @staticmethod
    def _npc_de_capas(raiz, hondo=4):
        """ALCALDE_FINALES_PULIDOS: los NPC sentados en los bancos y los corros (frontend/bancos_sentados.py) cuelgan de
        las capas de ciudad_viva, no de la escena: se colaban en los planos de la plaza mirando la fiesta."""
        from frontend.final_animado import final_pulido_calculos as pulido
        if raiz is None or not pulido.activo():
            return []
        out, pila = [], [(raiz, 0)]
        while pila:
            nodo, nivel = pila.pop()
            for hijo in list(getattr(nodo, "children", ())):
                if type(hijo).__name__ == "PersonajeNPC":
                    out.append(hijo)
                elif nivel < hondo:
                    pila.append((hijo, nivel + 1))
        return out

    @staticmethod
    def _fuera(hijo):
        """¿Es del juego y no del decorado? NPC, carteles, vehículos, props de misión y la columna de luz de la llegada
        a la misión (frontend/llegada_visual.py: un cilindro hijo directo de la escena, creado cuando hace falta)."""
        if type(hijo).__name__ in TIPOS_FUERA or getattr(hijo, "name", "") in NOMBRES_FUERA:
            return True
        return type(getattr(hijo, "model", None)).__name__ == "Cylinder"

    def _repintar_cielo(self, hora):
        cielo = getattr(getattr(self.escena, "ciudad", None), "cielo", None)
        try:
            if cielo is not None and hasattr(cielo, "aplicar_hora"):
                cielo.aplicar_hora(type(cielo)._hora() if hasattr(type(cielo), "_hora") else hora)
                cielo._t_ciclo = 0.0
        except Exception as error:
            _aviso(f"cielo sin repintar ({type(error).__name__}: {error})")

    def mantener(self):
        self._vueltas = getattr(self, "_vueltas", 0) + 1
        if self._vueltas % 20 == 0:                    # lo que el juego cree a mitad del final (la columna de luz)
            conocidos = {id(x) for x in self.ocultos}
            for np_ in self._candidatos():
                try:
                    if id(np_) not in conocidos and not np_.isEmpty() and not np_.isHidden():
                        np_.hide()
                        self.ocultos.append(np_)
                except Exception:
                    pass
        for np_ in self.ocultos:
            try:
                if not np_.isEmpty() and not np_.isHidden():
                    np_.hide()
            except Exception:
                pass

    def soltar(self):
        if not self._activo:
            return
        self._activo = False
        for np_ in self.ocultos:
            try:
                if not np_.isEmpty():
                    np_.show()
            except Exception:
                pass
        self.ocultos = []
        try:
            ambiente_vivo.fijar_hora_forzada(self._hora_antes)
        except Exception as error:
            _aviso(f"hora sin devolver ({type(error).__name__}: {error})")
        try:
            if self._controlador is not None:
                self._controlador.soltar_final()
            elif self._etapa_antes is not None:
                ambiente_vivo.fijar_etapa(self._etapa_antes)
        except Exception as error:
            _aviso(f"etapa sin devolver ({type(error).__name__}: {error})")
        self._controlador = None
        self._etapa_antes = None
        self._repintar_cielo(None)
