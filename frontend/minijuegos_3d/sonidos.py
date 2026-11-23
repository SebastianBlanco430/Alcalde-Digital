# Sonidos cortos de los minijuegos 3D. El juego NO trae «clavar», «colgar» ni «trazo»: se reutilizan los efectos que existen
# (assets/sonidos/clic_ui.wav y hover_ui.wav) con otro tono, por frontend/audio.py (respeta volúmenes, silencio y la bandera
# ALCALDE_AUDIO). Nunca lanza: sin audio, no suena nada.
#
#   sonidos.sonar("clavar" | "colgar" | "clic" | "trazo" | "papel", volumen=1.0)

# nombre -> (efecto de assets/sonidos sin .wav, volumen, tono)
SONIDOS = {
    "clic": ("clic_ui", 0.8, 1.0),
    "clavar": ("clic_ui", 1.0, 0.55),
    "colgar": ("hover_ui", 0.9, 0.7),
    "trazo": ("hover_ui", 0.35, 1.7),
    "papel": ("hover_ui", 0.6, 0.85),
}


def sonar(nombre, volumen=1.0):
    entrada = SONIDOS.get(nombre)
    if entrada is None:
        return False
    efecto, vol, tono = entrada
    try:
        from frontend import audio
        gestor = audio.obtener()
        if gestor is None:
            return False
        gestor.efecto(efecto, volumen=vol * volumen, pitch=tono)
        return True
    except Exception:                    # noqa: BLE001  sin audio: en silencio
        return False
