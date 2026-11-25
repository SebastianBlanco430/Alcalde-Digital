# Modo feria (modelo puro, sin ursina): la semana avanza por MISIONES, no por reloj. Ver docs/MODO_FERIA.md.
#
# QUÉ HACE. Con el modo encendido, FlujoConTiempo (backend/logica/flujo_tiempo.py) no deja correr el reloj con el tiempo
# real: la hora del día la marca el progreso (08:00 al empezar; 08:00 + 12 h · hechas/por_dia tras cada misión cerrada,
# animada a VELOCIDAD_HORAS_POR_SEG para que el cielo cambie de verdad) y el día se cierra (reloj a las 20:00, noche
# pendiente) al cerrar `por_dia` misiones o cuando el jugador activo se queda sin misión del día. Pasar la noche usa la
# misma ruta que el modo normal (reloj.pasar_noche() -> fijar_dia_misiones(dia, hora)); la radio lo dispara por conteo.
# El día 7 cerrado = reloj en su fin = final de siempre.
#
# MISIONES POR DÍA. POR_DIA = 4 (feria del 26-nov: ≈ 28 misiones). Son las mismas 4 por día que sortea
# backend/logica/reparto_dias.py (quita 1 de las 5 de cada día): con menos, la que sobra caducaba cada noche sin verse y
# la radio decía «quedaron sin verificar». POR_DIA = None = el catálogo de verificar ÷ 7 (hoy 35 / 7 = 5).
# ALCALDE_FERIA_POR_DIA=<n> manda.
#
# GUARDADO. Una partida de feria NO se guarda ni se puede continuar (FlujoConTiempo oculta misiones_a_dict, así que
# guardado.se_puede_guardar dice que no). El modo no viaja en el guardado: no cambia el formato.
#
# BANDERA. FERIA = False; ALCALDE_FERIA=1 lo enciende (lo pone la opción «Modo feria» del menú de inicio antes de crear la
# partida, y lo quita «Partida nueva»). Es la bandera compartida de solo lectura del contrato §6: otros módulos la leen
# del entorno, nunca importando este archivo.
#
#   modo_feria.activo()                         -> ¿la partida que se crea ahora es de feria?
#   modo_feria.por_dia(catalogo=None)           -> misiones por día
#   ritmo = RitmoFeria(por_dia)
#   ritmo.registrar_cierre() / ritmo.nuevo_dia()
#   ritmo.observar(dt, hay_mision)              -> un frame con el mundo activo
#   ritmo.dia_completo()                        -> ¿se cierra el día?
#   ritmo.hora_objetivo(hora_inicio, hora_cierre)

import os

FERIA = False
VARIABLE = "ALCALDE_FERIA"
POR_DIA = 4                         # None = catálogo de verificar ÷ DIAS
DIAS = 7
VELOCIDAD_HORAS_POR_SEG = 1.5       # h de juego por s real al animar la hora tras una misión (el cielo se mueve)
ESPERA_SIN_MISION = 4.0             # s reales sin misión (mundo activo) para dar el día por agotado

_SI = ("1", "true", "si", "sí", "on")
_NO = ("0", "false", "no", "off")


def activo():
    """¿Modo feria? ALCALDE_FERIA=1/0 manda sobre FERIA (se lee en cada llamada)."""
    valor = os.environ.get(VARIABLE, "").strip().lower()
    if valor in _SI:
        return True
    if valor in _NO:
        return False
    return bool(FERIA)


def menu_activo():
    """¿Se ofrece «Modo feria» en el menú de inicio? ALCALDE_FERIA_MENU=0 lo quita (por defecto, sí)."""
    return os.environ.get("ALCALDE_FERIA_MENU", "").strip().lower() not in _NO


def encender(si=True):
    """Lo llama el menú de inicio: deja el modo en el entorno para la partida que se va a crear."""
    os.environ[VARIABLE] = "1" if si else "0"


# Misiones de verificar del catálogo ÷ DIAS (al menos 1). Duck typing: cualquier objeto con `tipo`.
def por_dia_de_catalogo(catalogo):
    verificar = [m for m in (catalogo or ()) if getattr(m, "tipo", "verificar") == "verificar"]
    return max(1, len(verificar) // DIAS)


def por_dia(catalogo=None):
    """Misiones por día: ALCALDE_FERIA_POR_DIA si es un entero >= 1; si no POR_DIA; si POR_DIA es None, el catálogo ÷ 7."""
    crudo = os.environ.get("ALCALDE_FERIA_POR_DIA", "").strip()
    if crudo.isdigit() and int(crudo) >= 1:
        return int(crudo)
    if POR_DIA is not None:
        return int(POR_DIA)
    return por_dia_de_catalogo(catalogo)


class RitmoFeria:

    def __init__(self, por_dia_feria=None):
        n = por_dia() if por_dia_feria is None else por_dia_feria
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"por_dia inválido: {n!r}; debe ser un entero >= 1.")
        self.por_dia = n
        self.hechas_hoy = 0
        self.hechas_total = 0
        # s reales seguidos con el mundo activo y sin misión: entre cerrar una y recibir la siguiente pasa un instante,
        # así que el día solo se da por agotado tras ESPERA_SIN_MISION s (no quedan del día para el rol activo).
        self._sin_mision_s = 0.0

    def registrar_cierre(self):
        self.hechas_hoy += 1
        self.hechas_total += 1

    def nuevo_dia(self):
        self.hechas_hoy = 0
        self._sin_mision_s = 0.0

    # Un frame con el mundo activo (lo llama FlujoConTiempo.avanzar_tiempo).
    def observar(self, dt, hay_mision):
        self._sin_mision_s = 0.0 if hay_mision else self._sin_mision_s + max(0.0, float(dt))

    def dia_completo(self):
        return self.hechas_hoy >= self.por_dia or self._sin_mision_s >= ESPERA_SIN_MISION

    def hora_objetivo(self, hora_inicio, hora_cierre):
        if self.dia_completo():
            return hora_cierre
        fraccion = min(1.0, self.hechas_hoy / self.por_dia)
        return hora_inicio + (hora_cierre - hora_inicio) * fraccion
