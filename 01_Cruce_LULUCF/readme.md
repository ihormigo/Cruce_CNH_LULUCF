# Cruce_CNH_LULUCF

Cruce de la preCNH24 con la cartografía de LULUCF y revisión de casuísticas para la mejora del nivel de detalle de los códigos de hábitats LPEH, diferenciando flujos de procesamiento por grupos (`7s` y `8s`) y zonas (`PB` y `C`).

## Índice
* [A) Instalación de librerías y ejecución de los scripts de la metodología](#a-instalación-de-librerías-y-ejecución-de-los-scripts-de-la-metodología)
* [B) Esquema de los scripts para la metodología de cruce preCNH24-LULUCF](#b-esquema-de-los-scripts-para-la-metodología-de-cruce-precnh24-lulucf)
  * [1º) Procesado espacial: `procesado_espacial_cruce_preCNH_LULUCF_separacionVsJs.py`](#1º-procesado-espacial-procesado_espacial_cruce_precnh_lulucf_separacionvsjspy)
  * [2º) Depuración y clasificación inicial: `sel_mas_detalle_parte_1_separacionVsJs.py`](#2º-depuración-y-clasificación-inicial-sel_mas_detalle_parte_1_separacionvsjspy)
  * [3º) Pasarela secundaria y análisis 1:1: `sel_mas_detalle_parte_2_relacion_1_1_CNH_LULUCFs.py`](#3º-pasarela-secundaria-y-análisis-11-sel_mas_detalle_parte_2_relacion_1_1_cnh_lulucfspy)
  * [4º) Volcado final: `volcado_AAF_preCNH24.py`](#4º-volcado-final-volcado_aaf_precnh24py)
* [C) Consejos para la correcta ejecución de los scripts](#c-consejos-para-la-correcta-ejecución-de-los-scripts)

---

## A) Instalación de librerías y ejecución de los scripts de la metodología

### Requisitos de software
* ArcGIS Pro
* Python (entorno de ArcGIS Pro)

### Librerías Python a instalar
* `arcpy` (se clona desde ArcGIS Pro)
* `geopandas`
* `pandas` y `numpy` (se instalan automáticamente como dependencias de `geopandas`)
* El resto son librerías nativas de Python (`os`, `sys`, `time`, `glob`, `datetime`)

### 1) Clonado e instalación de la librería `arcpy`
1. Abrimos ArcGIS Pro (sin abrir proyecto), nos dirigimos a **Settings > Package Manager**, hacemos clic en el botón de configuración ⚙️ y luego en **Clone arcgispro-py3** (a la izquierda del icono de la carpeta) e indicamos dónde se realizará el clonado (este será el entorno virtual desde el que ejecutaremos `arcpy`).
2. Si lo hacemos desde un proyecto abierto, accedemos desde la pestaña **Project > Package Manager**.

### 2) Activamos el entorno virtual clonado
En consola ejecutamos:
```bash
conda activate nombre_clon_arcpy
```

### 3) Instalación de las librerías adicionales
En consola ejecutamos:
```bash
pip install geopandas
```

### 4) Enlace a la carpeta que contiene los scripts
```bash
cd ruta/a/la/carpeta/con/los/scripts
```

### 5) Ejecución de los scripts
```bash
python nombre_del_script.py
```

---

## B) Esquema de los scripts para la metodología de cruce preCNH24-LULUCF

El flujo de trabajo está automatizado para ejecutarse de forma secuencial y en lote (*batch*) por zonas (`PB` y `C`) y grupos de tipologías (`7s` y `8s`).

---

### 1º) Procesado espacial: `procesado_espacial_cruce_preCNH_LULUCF_separacionVsJs.py`

Ejecuta un procesamiento por lotes iterando automáticamente sobre todas las combinaciones de zona (`c`, `pb`) y grupo (`7s`, `8s`):

* Carga las geodatabases de la preCNH24 y LULUCF como inputs y crea una GDB temporal propia (`Temp_Procesos.gdb`) para evitar bloqueos y errores en disco.
* Filtra la preCNH24 en disco mediante ArcPy según el grupo activo:
  * **Grupo `7s`:** `id_tipestr IN (7, 71, 72, 75, 76, 77)`
  * **Grupo `8s`:** `id_tipestr IN (8, 811, 812, 82, 83, 84, 85, 861, 862, 863, 864, 865, 87, 88, 89)`
  * **Condiciones comunes:** `id_gh IS NULL AND identico_mfeff = 'ESI_TSI' AND (obs_tipo NOT LIKE '%56%' OR obs_tipo IS NULL) AND asigna_eq <> 'C'`
* Recorta el ráster LULUCF por *Bounding Box* de la selección, lo vectoriza y elimina el valor NoData (`65535`). Está configurado por defecto para ejecutarse **sin filtro previo de gridcodes** (`filtro=False`).
* **Identity:** Cruza la preCNH24 filtrada con los polígonos de LULUCF, calcula áreas (`a_cnh24`, `A_LULUCF`) y porcentajes (`PER`, `PER_R`), y guarda la capa resultante en geodatabases separadas por grupo.
* Extrae la tabla en formato `.csv` sin geometrías para agilizar el resto del procesado y limpia los archivos temporales.

#### 1.1) Inputs
* Ruta de la GDB vectorial original de la preCNH24 (`.gdb`).
* Ruta de la GDB de LULUCF (`.gdb`).
* Ruta de la carpeta de salida.

#### 1.2) Outputs
* `Cruce_CBP_LULUCF_{grupo}.gdb` (`7s` y `8s`) --> Geodatabases con las capas resultantes del `Identity` organizadas por *Feature Dataset* (`etrs89` para PB, `wgs84` para C).
* `cbp_lulucf_{zona}_{grupo}.csv` (`cbp_lulucf_pb_7s.csv`, `cbp_lulucf_pb_8s.csv`, `cbp_lulucf_c_7s.csv`, `cbp_lulucf_c_8s.csv`) --> Tablas alfanuméricas limpias para continuar en la Parte 1.

---

### 2º) Depuración y clasificación inicial: `sel_mas_detalle_parte_1_separacionVsJs.py`

Lee automáticamente todos los CSV de entrada de la carpeta indicada detectando de forma dinámica la zona (`pb`/`c`) y el grupo (`7s`/`8s`):

* **Pasarela y pivotado:** Traduce los `gridcode` de LULUCF a códigos `LPEH` (en mayúsculas para distinguirlos de los `lpeh` originales), agrupa porcentajes, aplica reglas de redondeo (<5% a 0%, >95% a 100%, asignando remanentes al mayor) y pivota los resultados en columnas dinámicas (`LPEH_1`, `PER_1`, `LPEH_2`, `PER_2`, etc.).
* **Cruce y filtrado de asignaciones previas:** Cruza los datos pivotados con la tabla de atributos de la capa filtrada y descarta los registros donde `asigna_lpeh1` contiene `'5'` o es igual a `'2aa'` o `'2bb'` (ya fotointerpretados).
* **Eliminación de duplicados:** Separa los registros donde todos los binomios origen (`lpehx`, `px`) y destino (`LPEH_X`, `PER_X`) coinciden exactamente con diferencias de porcentaje menores al 5%.
* **Clasificación parametrizada (`Vs` para `7s` / `Js` para `8s`):** Evalúa la presencia de coberturas objetivo (`V` si el archivo es `7s`, o `J` si es `8s`) en `LPEH_1` y el resto de posiciones, subdividiendo por umbrales de porcentaje (`<= 70%`, `70% - 85%`, `>= 85%`) con control matemático de cuadre de registros.

#### 2.1) Inputs
* Ruta de la carpeta con los CSV de entrada generados en el procesado espacial.
* Ruta de la GDB de la preCNH24 (`.gdb`).
* Ruta de la carpeta de salida.

#### 2.2) Outputs (etiquetados dinámicamente por `{zona}` y `{grupo}`)
* **Pasarela y pivotado (Excel de control):**
  * `cbp_lulucf_mapeado_{zona}_{grupo}.xlsx`
  * `cbp_lulucf_final_{zona}_{grupo}_pivotado.xlsx`
* **Filtrado y depuración:**
  * `revisar_descartes_filtros_asigna1_{zona}_{grupo}.csv`
  * `continuar_dep_filtros_asigna1_{zona}_{grupo}.csv`
  * `revision_INTERNA_duplicados_lpehx_LPEHX_px_PERX_{zona}_{grupo}.csv`
  * `continuar_SIN_duplicados_lpehx_LPEHX_px_PERX_{zona}_{grupo}.csv`
* **Casuísticas clasificadas (donde `{patron}` es `Vs` para `7s` y `Js` para `8s`):**
  * `registros_LPEH_1_SIN_{patron}_{zona}_{grupo}.csv`
  * `revision_cruce_LPEH_2_X_SI_{patron}_{zona}_{grupo}.csv`
  * `revision_cruce_LPEH_2_X_NO_{patron}_{zona}_{grupo}.csv`
  * `registros_LPEH_1_CON_{patron}_{zona}_{grupo}.csv`
  * `revision_cruce_suma_PERs_X_CON_{patron}_menor_igual_70_{zona}_{grupo}.csv`
  * `revision_cruce_suma_PERs_X_CON_{patron}_70_85_{zona}_{grupo}.csv`
  * `revision_mejorar_detalle_cruce_suma_PERs_X_CON_{patron}_mayor_igual_85_{zona}_{grupo}.csv` *(Caso 3: pasa a muestreo / Parte 2)*

---

### 3º) Pasarela secundaria y análisis 1:1: `sel_mas_detalle_parte_2_relacion_1_1_CNH_LULUCFs.py`

Procesa de forma **recursiva** todos los CSV ubicados bajo la carpeta raíz de entrada (registros no muestreados del Caso 3 con suma `>= 85%`), organizando automáticamente las salidas en subcarpetas por grupo (`7s` y `8s`):

* **Pasarela secundaria (`PASARELA_TIPESTR`):** Para los porcentajes que no correspondan a códigos `V` o `J`, aplica una tabla de conversión según `id_tipestr` (incluyendo la regla actualizada `89: [('J', 51), ('V', 49)]`). Si el `id_tipestr` no está en la pasarela, **conserva intactas las coberturas secundarias originales**.
* **Reagrupación y limpieza:** Fusiona porcentajes de códigos coincidentes, absorbe coberturas residuales menores al 5% sumándolas al código mayoritario y elimina los nuevos duplicados donde origen (`lpehx`, `px`) y destino (`LPEH_X`, `PER_X`) resulten idénticos tras la pasarela.
* **Separación por cardinalidad:** Divide los registros en relaciones `1:1`, `1:N` y `M:N` verificando que no haya pérdida de registros.
* **Evaluación de mejora de detalle (`1:1`) y bifurcación por prefijos:** En los casos `1:1`, mide la longitud efectiva de `lpeh1` frente a `LPEH_1` (eliminando puntos y contando `ES` como un único carácter). Cuando `LPEH_1` aporta mayor detalle, separa los registros según si mantienen el **mismo prefijo** (`lpeh1` contenido en `LPEH_1`) o presentan **distinto prefijo** (para revisión).

#### 3.1) Inputs
* Ruta de la carpeta raíz de entrada (`datos_entrada_2a_parte`) con los CSV estructurados por grupo/zona. *(Las carpetas de salida `7s` y `8s` se generan automáticamente en el directorio padre).*

#### 3.2) Outputs (generados dentro de cada subcarpeta `7s` y `8s`)
* `{zona_codigo}_caso3_no_muestreado_2a_parte_MAPEADO_tipestr.csv` --> Tabla completa tras aplicar la pasarela `id_tipestr` (estandarizada a CSV).
* `REVISION_duplicados_lpehx_LPEH_X_{ZONA}.csv` --> Nuevos duplicados detectados tras la pasarela.
* `registros_lpeh1_LPEH_1_{ZONA}.csv` --> Filas con relación `1:1`.
* `registros_lpeh1_varios_LPEH_X_{ZONA}.csv` --> Filas con relación `1:N`.
* `registros_varios_binomios_lpehx_{ZONA}.csv` --> Filas con relación `M:N`.
* `mejora_detalle_LPEH_1_lpeh1_{ZONA}_mismo_prefijo.csv` --> Casos `1:1` con aumento de detalle que conservan la jerarquía del código origen.
* `revision_mejora_detalle_LPEH_1_lpeh1_{ZONA}_distinto_prefijo.csv` --> Casos `1:1` con aumento de longitud pero cambio de raíz/prefijo (para revisión).
* `revision_detalle_lpeh1_LPEH_1_{ZONA}.csv` --> Casos `1:1` donde `LPEH_1` tiene igual o menor longitud que `lpeh1`.

---

### 4º) Volcado final: `volcado_AAF_preCNH24.py`

Vuelca los campos actualizados sobre la geodatabase de la preCNH24 a partir de los CSV revisados y validados según el árbol de decisión:

* **Actualización de hábitats (`fte_lpehx`, `asigna_lpehx`, `hicx`, `fte_hicx`, `asigna_hicx`):**
  * **Si `Accion = 2`** *(mejora de detalle derivada del cruce LULUCF)*:
    * Parte de los campos `LPEH_X` y porcentajes `PER_X`.
    * `fte_lpehx = 628` y `asigna_lpehx = '2bb'`.
    * `hicx = fte_hicx = asigna_hicx = x`.
  * **Si `Accion = 3`** *(mejora de detalle por fotointerpretación)*:
    * Parte de los campos `lpehx_3` y porcentajes `px_3` (creados en revisión manual).
    * `fte_lpehx = x` y `asigna_lpehx = '5a'`.
    * `hicx = 'nc'`; `fte_hicx = asigna_hicx = x`.
* **Campos generales de asignación:**
  * `mc_asig = 'ma'`
  * `rev = 'NO'` --> `rev_gh = null`
  * `asigna_eq = 'AAF'`
  * `fc_asig` --> Se actualiza automáticamente con el mes/año de ejecución (`mm-yyyy`).
  * `masc_gh = 'DM_GH'`
* **Actualización de situación (`sit_gh`):**
  * `1` --> pasa a `2` (sin modificar el resto de campos asociados según el DD).
  * `6` --> pasa a `14` (`id_gh = null`, `geo_mod = 'SI'`, `fus = 'NO'`, `rev = 'NO'`).
  * `8` --> pasa a `16` (`id_gh = null`, `geo_mod = 'SI'`, `fus = 'SI'`, `rev = 'NO'`).

#### 4.1) Inputs
* Ruta de la preCNH24 (`.gdb`).
* Carpeta de salida.
* Carpeta con los CSVs para PB y C a volcar (cada zona debe estar en una subcarpeta con estos nombres).

#### 4.2) Outputs
* Geodatabase `preCNH24` actualizada con el volcado y la fecha de ejecución (en el nombre de la GDB, capas y alias).
* Archivos `{nombre_csv_input}_volcado_REVISAR.csv` --> Contienen todos los campos originales de la preCNH24, los derivados del cruce LULUCF (`LPEH_X`, `PER_X`), los de revisión manual (`Accion`, `lpehx_3`, `px_3`) y los campos finales volcados tras aplicar el árbol de decisiones.

---

## C) Consejos para la correcta ejecución de los scripts

* **Bloqueos de geodatabase (`ERROR 000210: Cannot create output`):** Si aparece este error al ejecutar cualquiera de los scripts con `arcpy`, cierra **ArcGIS Pro** y cualquier consola de Python abierta que esté apuntando a la geodatabase para liberar los archivos `.lock`.
* **Nomenclatura de entrada en Parte 1 y Parte 2:** Asegúrate de que los nombres de los archivos CSV (o las subcarpetas que los contienen en la Parte 2) conserven las etiquetas de zona (`pb` / `c`) y grupo (`7s` / `8s`), ya que los scripts las utilizan para enrutar las reglas de selección y nombrar las salidas automáticamente.
* **Estructura de carpetas para el volcado (Script 4º):** Los CSVs a volcar deben estar separados en subcarpetas llamadas exactamente `PB` y `C`. De no ser así, el volcado se ejecutará sobre una única zona sin mostrar error en consola.