# Estructura del código — `portico_nave.py`

Índice de referencia para localizar y solicitar modificaciones. Los números de
línea son orientativos (versión 1.2).

## Índice por bloques

| Ámbito | Bloque | Líneas aprox. |
|---|---|---|
| Idioma: textos en español e inglés | `_S`, `lang`, `set_lang`, `tr` | 85–395 |
| Catálogo de perfiles (IPE, HEA, HEB, UPE, UPN) | `_IPE` … `_UPN`, `PROFILES` | 399–450 |
| Parámetros, valores por defecto y fachadas | `FACADES`, `DEFAULTS`, `LEGACY` | 452–500 |
| Etiquetas y materiales | `LAYER_KEYS`, `MAT_RGB`, `layer_name` | 500–508 |
| Saneado de parámetros | `normalize` | 519–549 |
| Geometría de cada faldón y fachada | clase `Side` | 552–587 |
| Geometría general, avisos, arriostramiento | clase `Geo` | 590–905 |
| Fachadas: comprobaciones, perfiles y paneles | `Geo.facades_on` … `Geo.panel_summary` | 733–875 |
| Secciones 2D (I, C, Z, U) | `i_section` … `u_section` | 909–962 |
| Generación de sólidos (prismas, redondos) | `prism`, `rod`, `_group`, `_container` | 967–1062 |
| Construcción de la nave | clase `_Builder`, `build_nave` | 1090–1440 |
| Pórticos (interiores y extremos) | `_Builder.frame_parts`, `_Builder.frames` | 1181–1236 |
| Cruces de San Andrés | `_Builder.bracing` | 1292–1335 |
| Fachadas (perfiles de piñón y paneles) | `_Builder.facades`, `_frame_matrix` | 1337–1422 |
| Medición de acero y de paneles | `measurement`, `panel_rows`, `summary` | 1443–1563 |
| Creación, edición y deshacer | `make_nave`, `rebuild_nave`, `_run` | 1581–1630 |
| Órdenes | `nueva`, `editar`, `medicion` | 1653–1698 |
| Cuadro de parámetros | `NaveDialog` | 1712–2011 |
| Tablas de medición | `MeasureDialog` | 2014–2076 |
| Registro de menús y Explorador | `setup`, `outliner_kind` | 2079–2131 |

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
- Unión pilar–dintel: el pilar sube `pilar_sobre` (5 cm por defecto) sobre
  la cara superior del dintel en la cara interior del pilar; el dintel arranca
  en la cara interior del pilar (corte a plomo).
- Pórticos extremos (primero y último): dintel `dintel_ext` si
  `dintel_ext_on`; la cota de alero y la cabeza de pilar se mantienen.
- Cruces de San Andrés: redondo macizo. Fachada: plano del eje de pilares,
  del arranque a la cara inferior del dintel en el pilar. Cubierta: plano
  paralelo al faldón, a un cuarto del canto del dintel más pequeño bajo la
  cara superior, de la cara interior del pilar a la cumbrera.
- Fachadas: cuatro (`frontal`, `posterior`, `izq`, `der`), cada una con
  `fach_<clave>` (activa), `fach_h_<clave>` (altura de fachada) y
  `panel_h_<clave>` (altura de placa). Piñones por delante de los pórticos
  primero y último: perfil U de esquina con el alma enrasada con la cara
  exterior del pilar y perfiles intermedios a una separación máxima; los
  perfiles tienen la altura de su fachada. Laterales: paneles de alma a alma
  de pilar, dentro de la H del pilar, contra el ala exterior. Con paneles
  laterales, las cruces de fachada pasan al hueco entre panel y ala interior.
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
