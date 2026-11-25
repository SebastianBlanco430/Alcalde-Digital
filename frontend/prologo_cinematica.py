# Prólogo de Alcalde Digital (Ursina, camera.ui): se ve al empezar una partida nueva (Empezar o Modo feria), ANTES de la
# selección de rol y de la intro de siempre (frontend/intro_cinematica.py, que no cambia). Contexto de Ciudad Nova y de
# la elección, fragmentos de los dos finales posibles y una pantalla negra: «La decisión depende de ti y de tus
# acciones.». Usa el componente de viñetas de las cinemáticas (cinematica_final.crear_vinetas); qué se ve lo arma
# frontend/prologo_calculos.py con backend/datos/prologo_cinematica.json y las cinemáticas de finales_historia.json.
# Espacio/clic adelantan, Escape (o «Saltar») salta todo. Tras la última viñeta queda un negro (escena.negro_prologo)
# hasta que la escena cambia (el fundido de siempre lleva a la selección de rol; la escena lo quita al salir).
#
# BANDERA. PROLOGO = True; ALCALDE_PROLOGO=0 lo quita (se empieza como antes). Lo engancha
# frontend/escenas/escena_inicio.py (_empezar).
#
#   activo()
#   crear_prologo(escena, al_terminar) -> entidad (.saltar())

import os

PROLOGO = True
ROTULOS = {"saltar": "Saltar", "continuar": "Seguir"}


def activo():
    """¿Hay prólogo? ALCALDE_PROLOGO=1/0 manda sobre PROLOGO."""
    valor = os.environ.get("ALCALDE_PROLOGO", "").strip().lower()
    if valor in ("1", "true", "si", "sí", "on"):
        return True
    if valor in ("0", "false", "no", "off"):
        return False
    return bool(PROLOGO)


def crear_prologo(escena, al_terminar):
    from backend.logica import etapas_final
    from frontend import prologo_calculos
    from frontend.cinematica_final import crear_vinetas

    cinematicas = etapas_final.cargar_textos()["cinematicas"]
    vinetas = prologo_calculos.armar_vinetas(prologo_calculos.cargar_guion(), cinematicas)
    if not vinetas:
        al_terminar()
        return None

    def terminar():
        # El negro del cierre se queda (por delante del menú) hasta que la escena cambia: la escena lo apaga al salir.
        from ursina import Entity, color
        escena.negro_prologo = Entity(parent=escena, model="quad", scale=(4.0, 2.0), z=-0.95, color=color.black)
        al_terminar()

    return crear_vinetas(vinetas, terminar, segundos=None, rotulos=ROTULOS, parent=escena)
