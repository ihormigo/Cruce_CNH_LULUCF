import pandas as pd
import geopandas as gpd
import arcpy
import os
import sys
import time
from datetime import datetime
import glob

class mejora_nivel_detalle:
    def __init__(self, ruta_input, folder_output, zona, path_gdb_vectorial):
        self.ruta_input = ruta_input
        self.folder_output = folder_output
        self.zona = zona.lower()
        self.path_gdb_vectorial = path_gdb_vectorial

        # Configuración automática del filtro de zona
        if self.zona in ['península', 'peninsula', 'p', 'pb']:
            self.filtro_zona = '_PB_'
        elif self.zona in ['c', 'canarias']:
            self.filtro_zona = '_C_'
        else:
            self.filtro_zona = f'_{zona.upper()}_'

        # Atributos internos de la clase
        self.capa_objetivo = None
        self.cbp_sel_fc = None
        self.cbp_sel = None
        self.df_mapeado = None
        self.redondeo = None
        self.df_pivotado = None
        self.cbp_final_join = None
        self.csv_limpio = None
        self.df_1binomio = None
        self.df_descartados_detalle = None
        self.df_varios_binomios = None
        self.df_LPEH1_mas = None
        self.df_resto = None
        self.input_excel = None
        self.mapa_lpeh_cultivos = None
        self.mapa_lpeh_artificiales = None
        self.mapa_lpeh_gridcodes = None

        # Detección del grupo (7s u 8s) a partir del nombre del archivo de entrada
        nombre_input = os.path.basename(self.ruta_input).lower()
        if '7s' in nombre_input:
            self.grupo = '7s'
        elif '8s' in nombre_input:
            self.grupo = '8s'
        else:
            self.grupo = '7s'

        os.makedirs(self.folder_output, exist_ok=True)


    def cargar_vectorial(self):
        walker = arcpy.da.Walk(self.path_gdb_vectorial, datatype="FeatureClass", type='Polygon')

        for root, dirnames, filenames in walker:
            for nombre in filenames:
                if self.filtro_zona in nombre:
                    self.capa_objetivo = nombre
                    break
            if self.capa_objetivo:
                break

        if self.capa_objetivo:
            print(f"Capa poligonal identificada en la GDB: {self.capa_objetivo} (Se filtrará antes de cargar en RAM)")
        else:
            print("❌ Error: No se encontró ninguna capa de polígonos que coincida en la GDB.")
            sys.exit()

    def sel_vectorial(self):
        # 1. Por seguridad, forzamos la sobrescritura en ArcPy
        arcpy.env.overwriteOutput = True

        if self.grupo == '7s':
            seleccion = [71, 72, 75, 76, 77]
        else:  # self.grupo == '8s'
            seleccion = [8, 811, 812, 82, 83, 84, 85, 861, 862, 863, 864, 865, 87, 88, 89]

        lista_ids = ", ".join(map(str, seleccion))
        where_clause = (f"id_tipestr IN ({lista_ids}) AND id_gh IS NULL AND identico_mfeff = 'ESI_TSI' and "
                        f"(obs_tipo not like '%56%' or obs_tipo is null) and asigna_eq <> 'C'")

        try:
            print(f"Filtrando capa en disco con ArcPy para el grupo {self.grupo}...")
            ruta_entrada = os.path.join(self.path_gdb_vectorial, self.capa_objetivo)

            gdb_temporal = arcpy.env.scratchGDB

            # 2. Creamos un nombre único basado en el momento exacto para evitar conflictos de .locks
            nombre_capa_temp = f"temp_sel_{self.grupo}_{int(time.time())}"
            self.cbp_sel_fc = os.path.join(gdb_temporal, nombre_capa_temp)

            # ArcPy filtra en disco de forma ultra rápida
            arcpy.analysis.Select(ruta_entrada, self.cbp_sel_fc, where_clause)

            print("Cargando la selección en GeoPandas (para uso tabular)...")
            self.cbp_sel = gpd.read_file(gdb_temporal, layer=nombre_capa_temp)
            self.cbp_sel['a_cnh24'] = self.cbp_sel.geometry.area
            print(f'✅ Tras la selección quedan {len(self.cbp_sel)} registros extraídos de la GDB.')

        except Exception as e:
            print(f"❌ Error crítico al hacer la selección con ArcPy/GeoPandas: {e}")
            sys.exit()

    def cargar_tabla(self, ruta_tabla, nombre_log="datos"):
        if not os.path.exists(ruta_tabla):
            print(f"❌ Error: No se encontró el archivo en: {ruta_tabla}")
            sys.exit()

        print(f"Cargando {nombre_log}...")
        _, extension = os.path.splitext(ruta_tabla)

        if extension.lower() == '.csv':
            return pd.read_csv(ruta_tabla, sep=';', encoding='utf-8-sig', low_memory=False)
        elif extension.lower() in ['.xlsx', '.xls']:
            return pd.read_excel(ruta_tabla)
        else:
            print(f"❌ Error: Formato no soportado para {ruta_tabla}. Usa .csv o .xlsx")
            sys.exit()

    def mapeo(self):
        print("Iniciando pasarela...")
        input_excel = self.cargar_tabla(self.ruta_input, "datos a mapear")
        self.input_excel = input_excel

        self.mapa_lpeh_cultivos = {
            700: 'V', 710: 'V', 711: 'V621', 712: 'V54', 713: 'V622', 714: 'V6', 715: 'V6',
            719: 'V', 720: 'V1', 721: 'V14', 722: 'J2.43', 729: 'V1',
        }
        self.mapa_lpeh_artificiales = {
            800: 'J', 810: 'J', 820: 'J', 821: 'J', 822: 'J', 823: 'J', 824: 'J', 830: 'J4',
            831: 'J4.5', 832: 'J4.4', 840: 'J4', 841: 'J4.2', 842: 'J4.3', 850: 'J3', 860: 'J6',
            870: 'J', 880: 'V2', 881: 'V2', 883: 'V2',
        }
        self.mapa_lpeh_gridcodes = {
            100: 'T', 111: 'T', 112: 'T', 121: 'T3', 122: 'T3', 131: 'T', 132: 'T', 141: 'T', 142: 'T',
            200: 'R', 210: 'R7', 220: 'S', 230: 'R', 240: 'U54.ES',
            400: 'U',
            500: 'Q', 511: 'Q', 512: 'Q', 520: 'J5' , 521: 'J5.35.ES', 522: 'J5.41', 523: 'J5.413.ES', 524: 'J5.31', 526: 'J5.3',
            527: 'J5.12', 531: 'P2', 532: 'P1', 533: 'X' , 536: 'MA2', 537: 'M',
            65535: '65535',
        }

        mapa_lpeh = {**self.mapa_lpeh_cultivos, **self.mapa_lpeh_artificiales, **self.mapa_lpeh_gridcodes}

        input_excel['LPEH'] = input_excel['gridcode'].map(mapa_lpeh).fillna(input_excel['gridcode'].astype(str))

        df_agrupado = input_excel.groupby(['id_cnhv2', 'LPEH'], as_index=False)['PER'].sum()
        df_agrupado = df_agrupado.rename(columns={'PER': 'PER_LPEH'})
        df_agrupado['PER_R'] = df_agrupado['PER_LPEH'].round(0).astype(int)

        self.df_mapeado = df_agrupado[['id_cnhv2', 'LPEH', 'PER_LPEH', 'PER_R']]

        path_excel2 = os.path.normpath(
            os.path.join(self.folder_output, f'cbp_lulucf_mapeado_{self.zona}_{self.grupo}.xlsx'))
        self.df_mapeado.to_excel(path_excel2, index=False, sheet_name='resultados')

    def redondeo_mapeo(self):
        print("Aplicando redondeo...")
        self.df_mapeado.loc[self.df_mapeado['PER_LPEH'] < 5, 'PER_LPEH'] = 0
        self.df_mapeado.loc[self.df_mapeado['PER_LPEH'] > 95, 'PER_LPEH'] = 100
        self.df_mapeado['PER_LPEH'] = self.df_mapeado['PER_LPEH'].round(0).astype(int)

        mapeo_ordenado = self.df_mapeado.sort_values(['id_cnhv2', 'PER_LPEH'], ascending=[False, False]).copy()
        mapeo_ordenado['sum_per'] = mapeo_ordenado.groupby('id_cnhv2')['PER_LPEH'].transform('sum')
        mapeo_ordenado['diferencia'] = 100 - mapeo_ordenado['sum_per']
        mapeo_ordenado['es_maximo'] = ~mapeo_ordenado.duplicated(subset=['id_cnhv2'])

        mapeo_ordenado['PER_R_new'] = mapeo_ordenado['PER_LPEH']
        mapeo_ordenado.loc[mapeo_ordenado['es_maximo'], 'PER_R_new'] += mapeo_ordenado['diferencia']

        self.redondeo = mapeo_ordenado.loc[mapeo_ordenado['PER_R_new'] > 0, ['id_cnhv2', 'LPEH', 'PER_R_new']]
        print("Proceso de redondeo, asignación de remanentes y filtrado completado con éxito.")

    def pivotar(self):
        print("Pivotando datos...")

        def distribuir_LPEH(grupo):
            if self.redondeo is not None:
                grupo = grupo.sort_values(['PER_R_new'], ascending=[False])
            else:
                grupo = grupo.sort_values(['PER_LPEH'], ascending=[False])

            resultado = {}
            for i, row in enumerate(grupo.itertuples(), 1):
                resultado[f'LPEH_{i}'] = row.LPEH
                if self.redondeo is not None:
                    resultado[f'PER_{i}'] = row.PER_R_new
                else:
                    resultado[f'PER_{i}'] = row.PER_LPEH
            return pd.Series(resultado)

        if self.redondeo is not None:
            df_series = self.redondeo.groupby('id_cnhv2').apply(distribuir_LPEH)
        else:
            df_series = self.df_mapeado.groupby('id_cnhv2').apply(distribuir_LPEH)

        if isinstance(df_series, pd.Series):
            self.df_pivotado = df_series.unstack().reset_index()
        else:
            self.df_pivotado = df_series.reset_index()

        self.df_pivotado = self.df_pivotado.drop_duplicates(subset=['id_cnhv2'])

        path_excel_pivot = os.path.normpath(
            os.path.join(self.folder_output, f'cbp_lulucf_final_{self.zona}_{self.grupo}_pivotado.xlsx'))
        self.df_pivotado.to_excel(path_excel_pivot, index=False, sheet_name="resultados_pivot")

    def union_tablas(self):
        # 1. Usar directamente la capa temporal filtrada en sel_vectorial()
        ruta_fc = self.cbp_sel_fc

        if not ruta_fc or not arcpy.Exists(ruta_fc):
            print("❌ Error: No se encontró la capa filtrada en memoria/disco.")
            sys.exit()

        # 2. Extraer la tabla de atributos omitiendo la geometría (rápido y directo)
        campos = [f.name for f in arcpy.ListFields(ruta_fc) if f.type != 'Geometry']
        with arcpy.da.SearchCursor(ruta_fc, campos) as cursor:
            df_gdb = pd.DataFrame(cursor, columns=campos)

        # 3. Asegurar mismo tipo numérico (int64 para el Long de ArcGIS) en ambos lados
        df_gdb['id_cnhv2'] = df_gdb['id_cnhv2'].astype('int64')
        self.df_pivotado['id_cnhv2'] = self.df_pivotado['id_cnhv2'].astype('int64')

        # 4. Cruzar tablas (Left Join) conectando df_pivotado con la GDB
        self.tablas_unidas = pd.merge(self.df_pivotado, df_gdb, on='id_cnhv2', how='left')

        # 5. Separar los registros según el campo 'asigna_lpeh1'
        filas_unidas = len(self.tablas_unidas)

        print("\n" + "=" * 60)
        print(f"📊 CONTROL DE REGISTROS - ZONA: {self.zona}")
        print("=" * 60)
        print(f"Total en Tabla Unida (Sin filtros): {filas_unidas} registros")
        print("=" * 60 + "\n")

        # 6. Exportar el archivo unificado completo a CSV
        path_unidas = os.path.join(self.folder_output, f'tablas_unidas_{self.zona}_{self.grupo}.csv')
        self.tablas_unidas.to_csv(path_unidas, sep=';', index=False, encoding='utf-8-sig')

    def eliminacion_duplicados_lpehx_LPEHX_px_PERX(self):
        print("Filtrando y exportando registros duplicados (coincidencia total)...")

        df = self.tablas_unidas.copy()

        # Identificar dinámicamente todos los índices numéricos de posición (1, 2, 3...)
        posiciones = sorted(list({int(col.replace('LPEH_', '').replace('lpeh', ''))
                                  for col in df.columns if
                                  col.startswith('LPEH_') or (col.startswith('lpeh') and col[4:].isdigit())}))

        # Inicializar la máscara: asumimos True para todas las filas y filtramos con lógica AND
        es_duplicado_fila = pd.Series(True, index=df.index)

        for num in posiciones:
            col_lpeh = f'LPEH_{num}'
            col_per = f'PER_{num}'
            col_gdb_lpeh = f'lpeh{num}'
            col_gdb_p = f'p{num}'

            # Obtener las columnas; si no existen en el DataFrame se tratan como vacías (NaN)
            s_lpeh = df[col_lpeh] if col_lpeh in df.columns else pd.Series(None, index=df.index, dtype=object)
            s_per = df[col_per] if col_per in df.columns else pd.Series(None, index=df.index, dtype=float)
            s_gdb_lpeh = df[col_gdb_lpeh] if col_gdb_lpeh in df.columns else pd.Series(None, index=df.index,
                                                                                       dtype=object)
            s_gdb_p = df[col_gdb_p] if col_gdb_p in df.columns else pd.Series(None, index=df.index, dtype=float)

            # Caso A: Ambos lados están vacíos (coincidencia correcta por ausencia)
            ambos_vacios = s_lpeh.isna() & s_gdb_lpeh.isna()

            # Caso B: Ambos lados tienen datos Y cumplen estrictamente con los dos criterios
            ambos_rellenos_y_coinciden = (
                    s_lpeh.notna() & s_gdb_lpeh.notna() &
                    (s_lpeh.astype(str).str.strip() == s_gdb_lpeh.astype(str).str.strip()) &
                    ((s_per.astype(float) - s_gdb_p.astype(float)).abs() < 5)
            )

            # El par actual debe cumplir obligatoriamente el Caso A o el Caso B
            es_duplicado_fila &= (ambos_vacios | ambos_rellenos_y_coinciden)

        # Separación final de los DataFrames
        duplicados_lpehx_LPEHX = df[es_duplicado_fila]
        self.NO_duplicados_continuar_depuracion_lpehx_LPEHX_px_PERX = df[~es_duplicado_fila]

        # Definición de las rutas de salida con los nombres exactos solicitados
        path_duplicados = os.path.join(self.folder_output,
                                       f'revision_INTERNA_duplicados_lpehx_LPEHX_px_PERX_{self.zona}_{self.grupo}.csv')
        path_continuar = os.path.join(self.folder_output,
                                      f'continuar_SIN_duplicados_lpehx_LPEHX_px_PERX_{self.zona}_{self.grupo}.csv')

        # Exportación a archivos CSV respetando el delimitador ';' habitual de tu flujo
        duplicados_lpehx_LPEHX.to_csv(path_duplicados, sep=';', index=False, encoding='utf-8-sig')
        self.NO_duplicados_continuar_depuracion_lpehx_LPEHX_px_PERX.to_csv(path_continuar, sep=';', index=False,
                                                                   encoding='utf-8-sig')
        print(
            f"✅ Proceso completado. Duplicados extraídos: {len(duplicados_lpehx_LPEHX)} | Registros limpios para continuar: {len(self.NO_duplicados_continuar_depuracion_lpehx_LPEHX_px_PERX)}")


    def clasificacion_para_revision_manual(self):
        patron = 'V' if self.grupo == '7s' else 'J'
        etiqueta_patron = 'Vs' if self.grupo == '7s' else 'Js'

        print(
            f"\nClasificando registros por presencia de {etiqueta_patron} (Grupo {self.grupo}) y sumas condicionales...")

        # Partimos de la capa limpia de duplicados de la función anterior
        df = self.NO_duplicados_continuar_depuracion_lpehx_LPEHX_px_PERX.copy()
        total_inicial = len(df)

        # -------------------------------------------------------------------------
        # 1. SEPARACIÓN PRINCIPAL: LPEH_1 contiene o no V (si 7s) o J (si 8s)
        # -------------------------------------------------------------------------
        mask_lpeh1_target = df['LPEH_1'].str.contains(patron, case=False, na=False)

        self.registros_LPEH_1_CON_target = df[mask_lpeh1_target].copy()
        self.registros_LPEH_1_SIN_target = df[~mask_lpeh1_target].copy()

        # -------------------------------------------------------------------------
        # 2. RAMA: LPEH_1 SIN V/J
        # -------------------------------------------------------------------------
        df_sin = self.registros_LPEH_1_SIN_target.copy()
        cols_lpeh_2_plus = [col for col in df_sin.columns if col.startswith('LPEH_') and col != 'LPEH_1']

        # Evaluar si LPEH_2, 3, 4... contienen el patrón
        mask_any_target_2_plus = pd.Series(False, index=df_sin.index)
        for col in cols_lpeh_2_plus:
            mask_any_target_2_plus |= df_sin[col].str.contains(patron, case=False, na=False)

        self.LPEH_2_X_SI_target = df_sin[mask_any_target_2_plus].copy()
        self.LPEH_2_X_NO_target = df_sin[~mask_any_target_2_plus].copy()

        # -------------------------------------------------------------------------
        # 3. RAMA: LPEH_1 CON V/J
        # -------------------------------------------------------------------------
        df_con = self.registros_LPEH_1_CON_target.copy()
        cols_lpeh_todas = [col for col in df_con.columns if col.startswith('LPEH_')]

        suma_per_target = pd.Series(0.0, index=df_con.index)

        # Sumar PER_X strictly si su respectivo LPEH_X contiene el patrón objetivo
        for col_lpeh in cols_lpeh_todas:
            num = col_lpeh.split('_')[1]
            col_per = f'PER_{num}'

            if col_per in df_con.columns:
                mask_target_pos = df_con[col_lpeh].str.contains(patron, case=False, na=False)
                per_num = pd.to_numeric(df_con[col_per], errors='coerce').fillna(0)
                suma_per_target += per_num.where(mask_target_pos, 0)

        # Subdivisión por umbrales
        self.suma_PERs_X_CON_target_menor_igual_70 = df_con[suma_per_target <= 70].copy()
        self.suma_PERs_X_CON_target_70_85 = df_con[(suma_per_target > 70) & (suma_per_target < 85)].copy()
        self.suma_PERs_X_CON_target_mayor_igual_85 = df_con[suma_per_target >= 85].copy()

        # -------------------------------------------------------------------------
        # 4. EXPORTACIÓN A CSV
        # -------------------------------------------------------------------------
        archivos_generar = {
            f'registros_LPEH_1_SIN_{etiqueta_patron}_{self.zona}_{self.grupo}.csv': self.registros_LPEH_1_SIN_target,
            f'registros_LPEH_1_CON_{etiqueta_patron}_{self.zona}_{self.grupo}.csv': self.registros_LPEH_1_CON_target,
            f'revision_cruce_LPEH_2_X_SI_{etiqueta_patron}_{self.zona}_{self.grupo}.csv': self.LPEH_2_X_SI_target,
            f'revision_cruce_LPEH_2_X_NO_{etiqueta_patron}_{self.zona}_{self.grupo}.csv': self.LPEH_2_X_NO_target,
            f'revision_cruce_suma_PERs_X_CON_{etiqueta_patron}_menor_igual_70_{self.zona}_{self.grupo}.csv': self.suma_PERs_X_CON_target_menor_igual_70,
            f'revision_cruce_suma_PERs_X_CON_{etiqueta_patron}_70_85_{self.zona}_{self.grupo}.csv': self.suma_PERs_X_CON_target_70_85,
            f'revision_mejorar_detalle_cruce_suma_PERs_X_CON_{etiqueta_patron}_mayor_igual_85_{self.zona}_{self.grupo}.csv': self.suma_PERs_X_CON_target_mayor_igual_85
        }

        for nombre_csv, df_out in archivos_generar.items():
            ruta = os.path.join(self.folder_output, nombre_csv)
            df_out.to_csv(ruta, sep=';', index=False, encoding='utf-8-sig')

        # -------------------------------------------------------------------------
        # 5. CONTROL DE BALANCE DE REGISTROS
        # -------------------------------------------------------------------------
        subtotal_sin = len(self.LPEH_2_X_SI_target) + len(self.LPEH_2_X_NO_target)
        subtotal_con = (len(self.suma_PERs_X_CON_target_menor_igual_70) +
                        len(self.suma_PERs_X_CON_target_70_85) +
                        len(self.suma_PERs_X_CON_target_mayor_igual_85))

        total_salida = subtotal_sin + subtotal_con

        print("\n" + "=" * 65)
        print(f"         CONTROL DE REGISTROS: CRUCE {etiqueta_patron} Y SUMAS ({self.grupo})")
        print("=" * 65)
        print(f"Total inicial de registros a clasificar: {total_inicial}")
        print(f"  ├── 1. LPEH_1 SIN {etiqueta_patron}:                   {len(self.registros_LPEH_1_SIN_target)}")
        print(f"  │     ├── LPEH_2+ CON algún {etiqueta_patron}:         {len(self.LPEH_2_X_SI_target)}")
        print(f"  │     └── LPEH_2+ SIN ningún {etiqueta_patron}:        {len(self.LPEH_2_X_NO_target)}")
        print(f"  │")
        print(f"  └── 2. LPEH_1 CON {etiqueta_patron}:                   {len(self.registros_LPEH_1_CON_target)}")
        print(
            f"        ├── Suma PER_X (solo {etiqueta_patron}) <= 70%:  {len(self.suma_PERs_X_CON_target_menor_igual_70)}")
        print(
            f"        ├── Suma PER_X (solo {etiqueta_patron}) > 70% y < 85%: {len(self.suma_PERs_X_CON_target_70_85)}")
        print(
            f"        └── Suma PER_X (solo {etiqueta_patron}) >= 85%:  {len(self.suma_PERs_X_CON_target_mayor_igual_85)}")
        print("-" * 65)
        print(f"  Subtotal Rama SIN: {subtotal_sin} | Subtotal Rama CON: {subtotal_con}")
        print(f"  Total sumando las 5 ramas finales:            {total_salida}")
        print(
            f"  CUADRE PERFECTO (Entrada == Salida):          {'✅ SÍ' if total_inicial == total_salida else '❌ NO'}")
        print("=" * 65 + "\n")


########################################################################################################################
def ejecutar_cruce_lulucf():
    print("=== PROCESAMIENTO BATCH DE ZONAS (PB y C) ===")

    # 1. Prompts de entrada limpios de comillas de arrastre en Windows
    carpeta_entrada = input("1. Introduce la ruta de la CARPETA con los CSV de entrada (PB y C):\n> ").strip('\"\'')
    ruta_gdb = input("\n2. Introduce la ruta de la GDB (.gdb):\n> ").strip('\"\'')
    carpeta_salida = input("\n3. Introduce la ruta de la CARPETA DE SALIDA:\n> ").strip('\"\'')

    carpeta_entrada = os.path.normpath(carpeta_entrada)
    ruta_gdb = os.path.normpath(ruta_gdb)
    carpeta_salida = os.path.normpath(carpeta_salida)

    if not os.path.isdir(carpeta_entrada):
        print(f"❌ Error: La carpeta de entrada no existe: {carpeta_entrada}")
        return

    # 2. Buscar todos los archivos .csv en la carpeta de entrada
    archivos_csv = glob.glob(os.path.join(carpeta_entrada, "*.csv"))

    if not archivos_csv:
        print(f"❌ Error: No se encontraron archivos .csv en: {carpeta_entrada}")
        return

    # 3. Iterar sobre los archivos detectando dinámicamente la zona (PB o C)
    for ruta_datos in archivos_csv:
        nombre_archivo = os.path.basename(ruta_datos)
        nombre_lower = nombre_archivo.lower()

        # Detección flexible de zona
        if "_pb_" in nombre_lower or "pb" in nombre_lower:
            zona_analisis = "pb"
        elif "_c_" in nombre_lower or "canarias" in nombre_lower or "_c." in nombre_lower:
            zona_analisis = "c"
        else:
            print(f"⚠️ Omitiendo '{nombre_archivo}': No se pudo identificar la zona ('PB' o 'C').")
            continue

        print("\n" + "=" * 75)
        print(f"🚀 INICIANDO PROCESAMIENTO: ZONA '{zona_analisis.upper()}' | Archivo: {nombre_archivo}")
        print("=" * 75)

        procesador = mejora_nivel_detalle(
            ruta_input=ruta_datos,
            folder_output=carpeta_salida,
            zona=zona_analisis,
            path_gdb_vectorial=ruta_gdb
        )

        # Flujo de ejecución secuencial
        procesador.cargar_vectorial()
        procesador.sel_vectorial()
        procesador.mapeo()
        procesador.redondeo_mapeo()
        procesador.pivotar()
        procesador.union_tablas()
        procesador.eliminacion_duplicados_lpehx_LPEHX_px_PERX()
        procesador.clasificacion_para_revision_manual()

        print(f"\n✅ Proceso completado con éxito para la zona '{zona_analisis.upper()}'!")

    print("\n🎉 ¡EL FLUJO BATCH HA FINALIZADO PARA TODAS LAS ZONAS ENCONTRADAS!")


########################################################################################################################
if __name__ == "__main__":
    fecha_hora_inicio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"🚀 Ejecución iniciada el: {fecha_hora_inicio}\n")
    ini = time.time()

    ejecutar_cruce_lulucf()

    print("\n" + "="*50)
    fin = time.time()
    tiempo_total = fin-ini
    print(f"⏱️ El proceso ha tardado: {tiempo_total:.2f} segundos")
    print("="*50)

    # C:\Users\ihormigo\Desktop\Cruce_separacion_Vs_Js\1a_parte_Procesado_espacial\Resultado
    # C:\Users\ihormigo\Desktop\Cruce_preCNH24_LULUCF\1_datos originales\preCNH24_int_AAF_20260828.gdb
    # C:\Users\ihormigo\Desktop\Cruce_separacion_Vs_Js\res


