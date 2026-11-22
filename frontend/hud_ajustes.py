# Fila «HUD» (Completo / Mínimo) de Ajustes (M3.5). Entra por el registro público de la escena de Ajustes
# (escena_ajustes.registrar_seccion), sin editarla, igual que frontend/graficos_ajustes.py y movimiento_ajustes.py.
# La registra frontend/hud.py (HudMundo) la primera vez que se crea, solo si ALCALDE_HUD_MINIMO_AJUSTE no la apaga.
# El valor es el campo `hud_modo` de backend/logica/ajustes.py; el HUD lo sigue en vivo (GestorAjustes.suscribir).

from frontend import hud_modo_calculos as hm
from frontend import pase_final_calculos as pf
from frontend import pulseras_visibles_calculos as pv

NOMBRE_SECCION = "Interfaz"
ETIQUETA = "HUD"
DESCRIPCION = ("Mínimo deja solo la misión y el reloj. La franja de confianza, el minimapa, el dinero y el teléfono "
               "aparecen unos segundos cuando cambian o al pulsar su tecla (M/N el mapa, Tab el teléfono).")

# M5.3 (ALCALDE_PULSERAS_VISIBLES): «Pulseras en el HUD», campo `pulseras_hud` de backend/logica/ajustes.py.
ETIQUETA_PULSERAS = "Pulseras en el HUD"
DESCRIPCION_PULSERAS = ("Siempre: las dos pulseras pequeñas junto al reloj. Al cambiar: solo 30 s cuando sube o baja "
                        "una (con el HUD en Mínimo se portan así).")

# T3 (ALCALDE_TINTA_PANTALLA): «Tinta», campo `tinta_pantalla` de backend/logica/ajustes.py (frontend/pase_final.py).
ETIQUETA_TINTA = "Tinta"
DESCRIPCION_TINTA = "Contornos: solo el borde de cada figura. Cómic: además, líneas de tinta en siluetas y pliegues."

_registrada = False


# `s` = escena_ajustes.Seccion.
def construir_seccion(s):
    if hm.activo():
        s.anadir_selector(ETIQUETA, "hud_modo", hm.opciones_selector())
        s.anadir_texto(DESCRIPCION, alto=0.11)
    if pv.activo():
        s.anadir_selector(ETIQUETA_PULSERAS, pv.CLAVE_AJUSTE, pv.opciones_selector())
        s.anadir_texto(DESCRIPCION_PULSERAS, alto=0.11)
    if pf.tinta_activa():
        s.anadir_selector(ETIQUETA_TINTA, "tinta_pantalla", pf.opciones_selector())
        s.anadir_texto(DESCRIPCION_TINTA, alto=0.08)


def registrar():
    """Añade la pestaña una sola vez (registrar_seccion reconstruye la pantalla de Ajustes cada vez que se llama)."""
    global _registrada
    if _registrada or not (hm.activo() or pv.activo() or pf.tinta_activa()):
        return False
    from frontend.escenas import escena_ajustes
    escena_ajustes.registrar_seccion(NOMBRE_SECCION, construir_seccion)
    _registrada = True
    return True
