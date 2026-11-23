# Estructura del código — `portico_nave.py`

Índice de referencia para localizar y solicitar modificaciones. Los números de
línea son orientativos (versión 1.1).

## Índice por bloques

| Ámbito | Bloque | Líneas aprox. |
|---|---|---|
| Idioma: textos en español e inglés | `_S`, `lang`, `set_lang`, `tr` | 75–318 |
| Catálogo de perfiles (IPE, HEA, HEB) | `_IPE`, `_HEA`, `_HEB`, `PROFILES` | 318–356 |
| Parámetros y valores por defecto | `DEFAULTS`, `LEGACY` | 358–388 |
| Etiquetas y materiales | `LAYER_KEYS`, `MAT_RGB`, `layer_name` | 390–397 |
| Saneado de parámetros | `normalize` | 408–433 |
| Geometría de cada faldón y fachada | clase `Side` | 436–467 |
| Geometría general, comprobaciones y avisos | clase `Geo` | 470–630 |
| Secciones 2D (I, C, Z, U) | `i_section` … `u_section` | 637–681 |
| Generación de sólidos (prismas, redondos) | `prism`, `rod`, `_group`, `_container` | 688–783 |
| Construcción de la nave | clase `_Builder`, `build_nave` | 811–1066 |
| Pórticos (interiores y extremos) | `_Builder.frame_parts`, `_Builder.frames` | 900–955 |
| Cruces de San Andrés | `_Builder.bracing` | 1011–1052 |
| Medición de acero | `measurement`, `summary` | 1071–1167 |
| Creación, edición y deshacer | `make_nave`, `rebuild_nave`, `_run` | 1184–1232 |
| Órdenes | `nueva`, `editar`, `medicion` | 1256–1300 |
| Cuadro de parámetros | `NaveDialog` | 1315–1558 |
| Tabla de medición | `MeasureDialog` | 1561–1600 |
| Registro de menús y Explorador | `setup`, `outliner_kind` | 1606–1656 |

## Puntos afectados por un parámetro nuevo

Añadir un parámetro exige, por lo general, modificar:

1. `DEFAULTS` — clave y valor por defecto (el tipo del valor fija la conversión
   en `normalize`). Si el valor por defecto añade piezas, indicar en `LEGACY`
   el valor que deben tomar las naves guardadas con versiones anteriores.
2. `Geo` / `Side` — comprobaciones de coherencia y magnitudes derivadas.
3. `_Builder` — geometría.
4. `measurement` — fila de medición, si genera acero.
5. `NaveDialog._ask_once` — campo en la pestaña correspondiente.
6. `_S` — textos del campo y de los avisos, en español e inglés.

## Convenios del modelo

- Coordenadas locales (m): X según la luz (0 = cara exterior del pilar
  izquierdo); Y según la nave (0 = primer pórtico); Z vertical (0 = arranque
  de pilares).
- Luz: entre caras exteriores de pilares.
- Altura de alero: cara superior del dintel en la cara exterior del pilar, en
  cada fachada (`alero` izquierda, `alero_der` derecha).
- Pendiente en %, común a ambos faldones. Con aleros distintos la cumbrera se
  sitúa en `xr = (L + (Hder − Hizq) / t) / 2`.
- Cada faldón se calcula en sus propias coordenadas (`Side`: x desde la cara
  exterior del pilar de esa fachada). El lado derecho se coloca con un giro de
  180° (`R0` dentro del pórtico, `R` en piezas longitudinales).
- Pórticos extremos (primero y último): dintel `dintel_ext` si
  `dintel_ext_on`; su pilar es más largo o más corto según el canto del
  dintel, porque la cota de alero se mantiene.
- Cruces de San Andrés: redondo macizo. Fachada: plano del eje de pilares,
  del arranque a la cabeza del pilar más corto del lado. Cubierta: plano
  paralelo al faldón, a un cuarto del canto del dintel más pequeño bajo la
  cara superior, del eje del pilar a la cumbrera.
- Ménsula: cota de su cara superior; vuelo desde la cara interior del pilar al
  eje de la viga carril.
- Pesos nominales de catálogo; acero 7 850 kg/m³.

## Idioma

- Todos los textos visibles están en `_S` como pares (español, inglés) y se
  obtienen con `tr(clave)`.
- El idioma se elige en el cuadro de parámetros y se guarda en la
  configuración del usuario (`QSettings`); sin preferencia guardada se toma
  el de la configuración regional del sistema.
- Los nombres de piezas, etiquetas y materiales se crean en el idioma activo
  al generar o editar la nave.

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
