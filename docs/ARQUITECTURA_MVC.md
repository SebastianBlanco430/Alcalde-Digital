# Arquitectura MVC de Alcalde Digital

MVC por contrato y por test, sin mover archivos. El test `tests/test_arquitectura_mvc.py` (con los datos de
`tests/arquitectura_lista_blanca.py`) lo hace cumplir con `ast`, sin importar el proyecto ni Ursina.
Cifras reales: `venv/bin/python tests/test_arquitectura_mvc.py`.

## Mapa de capas (se decide por nombre)

| Capa | Qué es | Reconocimiento |
|---|---|---|
| Modelo | reglas del juego, datos, persistencia | `backend/**` |
| Modelo de vista (puro) | cálculos sin Ursina | `frontend/**/*_calculos.py` y `banderas_visuales`, `cinematica`, `estilo`, `geometria_mundo`, `azar_fijo`, `grafo_social_vista`, `trabajo_constantes`, `flujo_constantes`, `reloj_constantes` |
| Controlador | cablea modelo y vista, decide el flujo | `frontend/escenas/*`, `registro_*`, `controlador_*`, `*_enganches`, `conexion_flujo`, `extensiones`, `online_flujo`, `online_registro`, `gestor_escenas` |
| Vista | dibuja y lee entrada | el resto de `frontend/**` que importa `ursina` |

Flecha permitida: Vista -> Modelo de vista -> Modelo; Controlador -> todo. Nunca al revés.

## Reglas que vigila el test

- R1: `backend` no importa `ursina` ni `frontend`.
- R2: ningún módulo puro importa `ursina`, directa o transitivamente (por imports de nivel módulo).
- R3: ninguna vista importa un controlador (cuenta también el import dentro de función).
- R4: sin ciclos de nivel módulo entre módulos de `frontend`.
- R5 (aviso): una vista llama a una escritura del modelo (`registrar`, `guardar`, `otorgar`...).
- R6: las tablas de importación por texto resuelven con `importlib.util.find_spec`
  (`minijuegos.REGISTRO`, `minijuegos_visual.VISTAS`, `extensiones.MODULOS`, y las de `economia_mundo`,
  `tutorial_mision_bandeja`, `registro_tutorial_mision`).
- R7 (trinquete): si una entrada de la lista blanca ya no se viola, el test falla y pide borrarla.

## Convenciones para código nuevo

- `<x>_calculos.py`: la lógica y los números de la pantalla, sin Ursina, testeable sin ventana.
- `<x>_visual.py` / `<x>_vista.py`: solo dibujo y lectura de teclas; lee de un `_calculos`, no de una escena.
- `registro_<x>.py`: el cableado (instalar enganches, crear la vista, conectar el modelo).
- Constantes que comparten vista y controlador (nombres de escena, fases, medidas): módulo puro aparte
  (ejemplos: `flujo_constantes.py`, `trabajo_constantes.py`, `reloj_constantes.py`); el controlador las reexporta.
- Dibujo compartido por varias vistas: módulo de vista propio (ejemplo: `trabajo_dibujos.py`); la escena lo reexporta.
- La vista no escribe en el modelo: pide al controlador que lo haga.

## Qué NO mover y por qué

- Imports por texto (`importlib.import_module`, `__import__` con f-strings): cambiar una ruta rompe en tiempo de
  ejecución sin error de import; por eso R6 las verifica.
- PyInstaller: el empaquetado descubre módulos por imports y por lo que se lista en el spec; mover archivos puede
  dejar módulos fuera del binario.
- `mock.patch` / `monkeypatch` en los tests apuntan a rutas `modulo.nombre`: mover o renombrar los rompe.
  Por eso, al extraer algo, el módulo original REEXPORTA los mismos nombres.
- Archivos protegidos (los que el preservador marca como en uso): se extiende con módulos nuevos, no se reescribe.

## Cómo acortar la lista blanca

1. Mira la entrada (por ejemplo `vista -> controlador (perezosa)`) y qué nombre toma la vista del controlador.
2. Si es una constante o un nombre: llévalo a un módulo puro nuevo; el controlador lo importa de allí y lo reexporta.
3. Si es dibujo: llévalo a un módulo de vista; la escena lo reexporta.
4. Si es una llamada hacia el controlador: inyecta un callback o recibe el valor como argumento.
5. Corre `pytest -q -p no:cacheprovider tests/test_arquitectura_mvc.py`; el trinquete (R7) te dirá qué líneas
   borrar de `tests/arquitectura_lista_blanca.py`. Nunca se añaden entradas.
