# Tipografía de la interfaz (T4, docs/DISENO.md sección 3).
# Fuente: Atkinson Hyperlegible (SIL OFL 1.1), estáticas Regular y Bold en
# assets/fuentes/ junto con su OFL.txt. Text.size no cambia, así que
# `escala_fuente` y `a_unidades` de componentes.py quedan idénticas.
from pathlib import Path

FUENTE_TEXTO = "AtkinsonHyperlegible-Regular.ttf"
FUENTE_TITULO = "AtkinsonHyperlegible-Bold.ttf"   # títulos: Text(..., font=FUENTE_TITULO)
CARPETA_FUENTES = Path(__file__).resolve().parent.parent / "assets" / "fuentes"


# Ruta absoluta de un archivo de fuente del proyecto.
def ruta_fuente(nombre):
    return CARPETA_FUENTES / nombre


# Fija la fuente por defecto de Text. Llamar tras fijar application.asset_folder
# (Ursina busca la fuente dentro de él) y antes de `preparar_fuente()`.
def aplicar():
    from ursina import Text
    Text.default_font = FUENTE_TEXTO
