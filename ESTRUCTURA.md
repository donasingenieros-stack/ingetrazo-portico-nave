# Estructura del código — `portico_nave.py`

Índice de referencia para localizar y solicitar modificaciones. Los números de
línea son orientativos (versión 1.0).

## Índice por bloques

| Ámbito | Bloque | Líneas aprox. |
|---|---|---|
| Catálogo de perfiles (IPE, HEA, HEB) | `_IPE`, `_HEA`, `_HEB`, `PROFILES` | 62–100 |
| Parámetros y valores por defecto | `DEFAULTS` | 104–123 |
| Etiquetas y materiales | `LAYERS`, `MATS` | 125–129 |
| Saneado de parámetros | `normalize` | 140–155 |
| Geometría derivada, comprobaciones y avisos | clase `Geo` | 158–253 |
| Secciones 2D (I, C, Z, U) | `i_section` … `u_section` | 260–300 |
| Generación de sólidos | `prism`, `_group`, `_container` | 307–377 |
| Construcción de la nave | `build_nave` | 409–529 |
| Medición de acero | `measurement`, `summary` | 536–580 |
| Creación, edición y deshacer | `make_nave`, `rebuild_nave`, `_run` | 600–640 |
| Órdenes | `nueva`, `editar`, `medicion` | 663–706 |
| Cuadro de parámetros | `NaveDialog` | 722–905 |
| Tabla de medición | `MeasureDialog` | 908–947 |
| Registro de menús y Explorador | `setup`, `outliner_kind` | 954–1001 |

## Puntos afectados por un parámetro nuevo

Añadir un parámetro exige, por lo general, modificar:

1. `DEFAULTS` — clave y valor por defecto (el tipo del valor fija la conversión
   en `normalize`).
2. `Geo` — comprobaciones de coherencia, si proceden.
3. `build_nave` — geometría.
4. `measurement` — fila de medición, si genera acero.
5. `NaveDialog.ask` — campo en la pestaña correspondiente.

Las naves existentes reciben el valor por defecto de la nueva clave al
editarse, porque `normalize` completa los parámetros guardados.

## Convenios del modelo

- Coordenadas locales (m): X según la luz (0 = cara exterior del pilar
  izquierdo); Y según la nave (0 = primer pórtico); Z vertical (0 = arranque
  de pilares).
- Luz: entre caras exteriores de pilares.
- Altura de alero: cara superior del dintel en la cara exterior del pilar.
- Pendiente en %; el ángulo se obtiene como `atan(pendiente / 100)`.
- Ménsula: cota de su cara superior; vuelo desde la cara interior del pilar al
  eje de la viga carril.
- Lado derecho: giro de 180° del izquierdo (`R0` dentro del pórtico, `R` en
  piezas longitudinales).
- Pesos nominales de catálogo; acero 7 850 kg/m³.

## Versiones y publicación

- La versión figura en `__version__` (`portico_nave.py`) y en
  `extensions/portico_nave.toml` del repositorio `ingetrazo-extensions`
  (campos `version`, `download` y `sha256`).
- El catálogo descarga el fichero de la etiqueta `vX.Y` y verifica su
  `sha256`. Una modificación de `portico_nave.py` exige, para publicarse:
  nueva versión en `__version__`, nueva etiqueta y actualización de
  `version`, `download` y `sha256` en el `.toml`.
- Los cambios en documentación (README, este fichero) no alteran
  `portico_nave.py` ni requieren nueva versión.
