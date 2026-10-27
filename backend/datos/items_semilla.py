# Catálogo semilla de objetos del inventario (datos puros). Precio en R$ (None = no se vende).
# Bolsillo: celular y billetera son `fijo` (el jugador siempre los lleva). Los `sensible` (cuchillo pequeño,
# pistola) son objetos de cintura sin precio ni efecto; el juego los muestra solo tras una bandera.

from backend.logica.inventario import DefItem, PEQUENO, MEDIANO, GRANDE

_ITEMS = (
    # -- Pequeños (bolsillo) --
    DefItem("celular", "Celular", PEQUENO, 0.2, categoria="tecnologia", fijo=True,
            descripcion="Tu teléfono: mensajes de Civitas y misiones."),
    DefItem("billetera", "Billetera", PEQUENO, 0.1, categoria="dinero", fijo=True,
            descripcion="Guarda tu dinero en reales (R$)."),
    DefItem("llaves", "Llaves", PEQUENO, 0.1, categoria="llave", descripcion="Las llaves de casa."),
    DefItem("bolsita", "Bolsita vacía", PEQUENO, 0.01, apilable=5, categoria="cocina", precio=1,
            descripcion="Una bolsita de plástico vacía."),
    DefItem("bicarbonato", "Bolsita de bicarbonato", PEQUENO, 0.05, apilable=3, categoria="cocina", precio=5,
            efecto="info",
            descripcion="Es bicarbonato de sodio: sirve para cocinar y limpiar. No cura nada."),
    DefItem("audifonos", "Audífonos", PEQUENO, 0.05, categoria="tecnologia", precio=12),
    DefItem("pendrive", "Pendrive", PEQUENO, 0.02, categoria="tecnologia", precio=8),
    DefItem("recarga", "Recarga de celular", PEQUENO, 0.02, categoria="tecnologia", precio=10),
    DefItem("bala", "Bala (dulce)", PEQUENO, 0.01, apilable=10, categoria="comida", precio=1, efecto="comer",
            descripcion="Un dulce de los de la esquina."),
    # -- Medianos (cintura / mochila) --
    DefItem("linterna", "Linterna", MEDIANO, 0.3, categoria="herramienta", precio=15, cintura=True),
    DefItem("destornillador", "Destornillador", MEDIANO, 0.2, categoria="herramienta", precio=6, cintura=True),
    DefItem("libreta", "Libreta", MEDIANO, 0.15, categoria="papel", precio=4, cintura=True),
    DefItem("agua", "Botella de agua", MEDIANO, 0.5, categoria="bebida", precio=3, cintura=True, efecto="beber"),
    DefItem("cafe", "Café", MEDIANO, 0.3, categoria="bebida", precio=2, cintura=True, efecto="beber"),
    DefItem("pan", "Pan", MEDIANO, 0.1, apilable=4, categoria="comida", precio=1, cintura=True, efecto="comer"),
    DefItem("bolsa_feria", "Bolsa de feria", MEDIANO, 0.2, categoria="bolsa", precio=4, cintura=True),
    DefItem("periodico", "Periódico", MEDIANO, 0.2, categoria="papel"),
    # -- Grandes (manos) --
    DefItem("pelota", "Pelota de fútbol", GRANDE, 0.4, categoria="juego", precio=25),
    DefItem("caja_herramientas", "Caja de herramientas", GRANDE, 6.0, categoria="herramienta", precio=45),
    DefItem("botijon_gas", "Botijón de gas", GRANDE, 13.0, categoria="hogar", precio=100, dos_manos=True),
    # -- Equipo --
    DefItem("mochila", "Mochila", MEDIANO, 0.8, categoria="equipo", precio=60, ranuras=8, peso_extra=8.0,
            descripcion="Ocho ranuras más y 8 kg más de capacidad."),
    # -- Sensibles: sin precio ni efecto --
    DefItem("cuchillo_pequeno", "Cuchillo pequeño", MEDIANO, 0.2, categoria="sensible", cintura=True,
            sensible=True),
    DefItem("pistola", "Pistola", MEDIANO, 1.0, categoria="sensible", cintura=True, sensible=True),
)

CATALOGO_ITEMS = {item.id: item for item in _ITEMS}
