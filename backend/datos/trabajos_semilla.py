# Catálogo semilla de trabajos (datos puros): un puesto por comercio con `trabajo_id`. Turnos de 60-90 s,
# pago de R$ 12 a 25 según el rendimiento. `opciones` = productos (teclas 1-4) o direcciones de la secuencia.

from backend.logica.trabajos import Trabajo, ATENDER, SECUENCIA, BARRA

_FLECHAS = ("arriba", "abajo", "izquierda", "derecha")

CATALOGO_TRABAJOS = {t.id: t for t in (
    Trabajo("panaderia", "Atender en la panadería", ATENDER, 60, 12, 18, 20,
            ("pan", "café", "bollo", "leche")),
    Trabajo("supermercado", "Cajero del supermercado", ATENDER, 75, 14, 22, 25,
            ("arroz", "feijão", "leche", "jabón")),
    Trabajo("feirante", "Ayudar en la feria", ATENDER, 60, 12, 20, 25,
            ("mango", "banana", "tomate", "yuca")),
    Trabajo("bar", "Atender el bar", ATENDER, 75, 13, 21, 20,
            ("agua", "café", "refresco", "salgado")),
    Trabajo("taller", "Ayudante de taller", SECUENCIA, 90, 15, 25, 30, _FLECHAS),
    Trabajo("lan_house", "Soporte en la lan house", SECUENCIA, 60, 12, 19, 15, _FLECHAS),
    Trabajo("lanchonete", "Cocinar en la lanchonete", BARRA, 60, 12, 20, 25),
    Trabajo("entregas", "Mototaxi y entregas", BARRA, 90, 16, 25, 30),
)}
