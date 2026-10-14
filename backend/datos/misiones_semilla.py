# Catálogo semilla de misiones (datos puros). Tono: notificación de Civitas.
# Cada rol tiene al menos una misión cuyo destino NO es su lugar de inicio
# (si no, el jugador ya estaría "llegado" al aparecer). rol=None = genérica.
# Las misiones de roles que nadie juega las reparte SistemaMisiones entre los presentes,
# por eso los textos son neutros (no hablan en segunda persona del rol).

from backend.logica.misiones import Mision

CATALOGO_MISIONES = (
    Mision(
        "ciudadano_plaza", "ciudadano", "Tendencia en la plaza",
        "Civitas: tendencia en Plaza Central. Ve y revísala.", "Plaza Central",
    ),
    Mision(
        "periodista_alcaldia", "periodista", "Rumor en la Alcaldía",
        "Civitas: rumor sin verificar en la Alcaldía. Contrástalo.", "Alcaldía",
    ),
    Mision(
        "influencer_parque", "influencer", "Publicación viral",
        "Civitas: una publicación se mueve en el Parque Municipal. Pásate.", "Parque Municipal",
    ),
    Mision(
        "candidato_barrio", "candidato", "Voces del barrio",
        "Civitas: los vecinos de Barrio Las Flores quieren ser escuchados.", "Barrio Las Flores",
    ),
    Mision(
        "generica_hospital", None, "Alerta sanitaria",
        "Civitas: circula una alerta en Hospital Las Flores. Verifícala.", "Hospital Las Flores",
    ),
    Mision(
        "generica_terminal", None, "Cadena de mensajes",
        "Civitas: cadena sospechosa en la Terminal de Buses. Revísala.", "Terminal de Buses",
    ),
    Mision(
        "generica_universidad", None, "Debate estudiantil",
        "Civitas: debate encendido en la Universidad de Ciudad Nova.", "Universidad de Ciudad Nova",
    ),
)
