# Alcalde Digital 🏛️

**Alcalde Digital** es un juego 3D educativo sobre la **desinformación** y el uso responsable de las redes sociales, ambientado en una favela brasileña. Recorre la ciudad, verifica rumores y decide qué compartir y qué reportar antes de que sus habitantes voten por su alcalde.


---

## 🎯 Descripción

El jugador vive una semana en **Ciudad Nova**, a pocos días de unas elecciones. Recibe rumores por **Civitas**, una red social ficticia, completa misiones, ve al lugar donde empezó cada uno, busca pistas y resuelve minijuegos para decidir si es verdad o mentira. Cada decisión cambia la **convivencia**, la **confianza** y la **desinformación** de la ciudad, y al terminar el séptimo día esos números definen cómo acaba la historia. Puede jugar solo, por turnos con otros jugadores o en cooperativo online.

---

## 👥 Integrantes

| Nombre |
|---|
| Amir Diago |
| Samuel Castañeda |
| Sebastián Blanco |
| Santiago Lobo |
| Sebastián Sánchez |

---

## ⚙️ Requisitos

- Windows, macOS o Linux
- Python 3.12 a 3.14
- Conexión a internet (solo para la instalación y el modo online)

---

## 🚀 Instalación

1. Clona el repositorio
2. Abre la carpeta del proyecto
3. Ejecuta el instalador:
   - **Windows:** haz doble clic en `setup.bat`
   - **macOS / Linux:** `./setup.sh`
4. El script crea un entorno virtual `venv` e instala las dependencias
5. Una vez termine, corre el juego con:

```bash
# Windows
venv\Scripts\python main.py

# macOS / Linux
./venv/bin/python main.py
```

> ⚠️ Si no tienes Python 3.12 a 3.14, el instalador te avisará. Instálalo y vuelve a ejecutarlo.

---

## 🕹️ Controles

| Tecla | Acción |
|---|---|
| `W` `A` `S` `D` / Ratón | Moverse y mover la cámara |
| `Shift` | Correr (en vehículo: caballito) |
| `Ctrl` | Turbo (en vehículo) |
| `Espacio` | Saltar (en vehículo: frenar) |
| `E` | Entrar, montar, comprar y trabajar |
| `Tab` | Teléfono (misiones y novedades) |
| `M` | Seguir la misión (mostrar u ocultar la ruta) |
| `N` | Mapa (el minimapa en grande; `N` o `Esc` lo cierran) |
| `L` | Bandeja de Civitas |
| `K` | Dilemas |
| `B` | Significado de las pulseras |
| `I` | Mochila |
| `Esc` | Pausa (ahí está también esta lista) |

También se puede jugar con **mando**.

---

## 📁 Estructura del proyecto

```
Alcalde-Digital/
├── backend/          # Lógica del juego, árboles, grafos y red
├── frontend/         # Escenas, interfaz y minijuegos (Ursina)
├── assets/           # Modelos 3D, sonidos y fuentes
├── buildings/        # Fuentes de Blender de las casas
├── docs/             # Diseño, modo online y avisos legales
├── empaquetado/      # Instaladores del juego
├── sitio_web/        # Página de descarga
├── main.py           # Archivo principal
├── setup.bat         # Instalador para Windows
├── setup.sh          # Instalador para macOS y Linux
└── requirements.txt  # Dependencias de Python
```

---

## 📦 Dependencias

- `ursina 8.3.0`
- `Panda3D 1.10.16`
- `panda3d-gltf 1.3.0`
- `panda3d-simplepbr 0.13.1`
- `pillow 13.0.0`
- `psutil 7.2.2`
- `pyperclip 1.11.0`
- `screeninfo 0.8.1`
