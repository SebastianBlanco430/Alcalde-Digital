# Guía de assets

Cómo está organizada la carpeta `assets/` y cómo añadir o cambiar un modelo 3D (.glb) o una fuente.
Esta guía describe lo que el juego hace **hoy** en `main`; si algo cambia en el código, actualízala.

## 1. Carpetas

```
assets/
  fuentes/              AtkinsonHyperlegible-Regular.ttf, -Bold.ttf y OFL.txt (licencia)
  modelos/
    edificios/          casaN.glb y casaN_puerta.jpg (las genera buildings/exportar_edificios.py)
    personajes/         periodista.glb, smoking.glb (uno por rol con modelo)
    props/              reservada para árboles, farolas, bancos... (hoy son procedurales; sin cargador aún)
```

- Las **texturas van dentro del .glb** (edificios) o el modelo usa colores por material (personajes). No hay carpeta
  `texturas/`: la excepción es `casaN_puerta.jpg`, la hoja de la puerta, que va junto a su .glb.
- Las texturas fuente de Blender están en `buildings/textures/` (120 MB). **No se suben al repo**
  (`.gitignore`): se comparten aparte, por ejemplo por el grupo del equipo.
- Los `.blend` de las casas están en `buildings/`. Los de los personajes **no** están en el repo.

## 2. Convenciones para cualquier modelo (Blender)

| Tema | Regla |
|---|---|
| Formato | **.glb** (glTF binario): *File > Export > glTF 2.0*, "glTF Binary". |
| Unidades | **1 unidad = 1 metro**. |
| Ejes | **+Y arriba** en el .glb (el exportador convierte desde Z-up). |
| Escala y rotación | Aplicadas (`Ctrl+A`). Escala (1, 1, 1). |
| Frente | La fachada o el frente del modelo mira a **+Z** de Ursina. |
| Nombres | Minúsculas, sin espacios ni tildes, **únicos en todo `assets/`**. |
| Peso | Pocas caras: las 150 casas de la favela suman unos 75 000 vértices (~500 cada una) y el juego va a 60 FPS. |

## 3. Edificios (los 7 lugares y las casas de la favela)

Origen del modelo: **centro de la planta baja, a la altura del umbral de la puerta**. Lo que quede bajo el
umbral es el plinto de la casa (queda enterrado o sobre un zócalo).

1. **Exportar** (Blender en segundo plano), desde la raíz del repo:
   ```
   "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b buildings/casa1fav.blend --python buildings/exportar_edificios.py -- casa1
   ```
   El script reenlaza las texturas a `buildings/textures/` (a 1024 px), aplica las transformaciones, detecta la
   puerta y escribe `assets/modelos/edificios/casa1.glb` y `casa1_puerta.jpg`. Al final **imprime una línea
   `ModeloEdificio(...)`**.
2. **Registrar**: pega esa línea en `MODELOS` de `backend/datos/modelos_edificios.py` (Python puro, sin ursina).
   Agrega a mano `hondo` (cuánto baja el modelo bajo el umbral): se mide con
   `load_model(...).get_tight_bounds()` y es el `-y` mínimo.
3. **Asignar a un lugar**: en `_EDIFICIOS` de `backend/datos/ciudad_3d.py`, la última columna es el nombre del
   modelo (`"casa1"`). Con `""` el edificio vuelve a dibujarse con cubos.
4. **Tamaño**: el modelo se escala sin deformarse para caber en el lote del edificio y con la puerta de
   `ALTO_PUERTA_MAXIMO` = 3.2 m como tope.
5. **Ojo**: las casas decorativas de la favela eligen al azar entre **todos** los modelos de `MODELOS`
   (`sorted(MODELOS)`). Un modelo nuevo también aparecerá en la ladera y cambiará la favela.
6. Mira el resultado en una ventana real: `venv\Scripts\python main.py`. Con `ALCALDE_FPS=1` imprime los FPS.

Asignación actual: Plaza Central y Universidad = casa1; Terminal y Parque = casa2; Barrio Las Flores = casa3;
Alcaldía y Hospital = casa4.

## 4. Personajes

Origen en los **pies** (y = 0), frente a +Z, unos 2.0 m de alto sin escalar (el juego aplica 0.92).

- Dónde: `assets/modelos/personajes/<archivo>.glb`.
- Registrar: `MODELOS_POR_ROL` en `frontend/modelo_calculos.py` (`{"rol": "archivo.glb"}`). Hoy:
  `periodista` y `candidato` (`smoking.glb`). Ciudadano, influencer y peatones usan el muñeco procedural.
- **Clips** en el mismo .glb, con estos nombres exactos: `Idle`, `Caminar`, `Correr`, `Saludar`, `Hablar`.
  No existen clips de sentado ni de teclear.
- Rostro y pelo: el modelo puede venir con la cabeza lisa; `frontend/rostro_modelo.py` cuelga ojos, cejas,
  nariz, boca y pelo del hueso `DEF-spine.006` (si renombras ese hueso, hay que cambiarlo allí).
- Si el archivo falta o falla, el juego usa el muñeco procedural y avisa una vez por `stderr`.

## 5. Fuentes

`assets/fuentes/` guarda Atkinson Hyperlegible (Regular y Bold, licencia SIL OFL 1.1, con `OFL.txt`).
`frontend/tipografia.py` las aplica al arrancar. Si agregas otra fuente, copia también su licencia.

## 6. Pendientes y datos por completar

- Texturizar en Blender las caras de las casas que quedaron en gris liso y volver a exportar.
- Props (árboles, farolas, bancos): hoy los dibuja `frontend/props_mundo.py`; falta un cargador de .glb.
- Autoría y licencia de los modelos y de las texturas de `buildings/textures/` (p. ej. `Concrete-2767.jpg`,
  `Door-8850.jpg`, `janela01.jpg`): **por completar por el equipo** antes de publicar o redistribuir.
