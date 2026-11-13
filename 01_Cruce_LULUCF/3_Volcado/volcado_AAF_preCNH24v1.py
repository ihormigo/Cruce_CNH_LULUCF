# VOLCADO DE LA preCNH24 de AAF

import os
import sys
import time
import arcpy
import pandas as pd
import geopandas as gpd
import numpy as np
import shutil

class volcado_aaf:
    def __init__(self):
        # Habilitar sobrescritura global de ArcPy para evitar el Error 000210
        arcpy.env.overwriteOutput = True

        self.path_gdb_vectorial = r"C:\Users\ihormigo\Desktop\resultados_cruce\0 datos originales\preCNH24v1_int_AAF_20260731.gdb"
        self.folder_output = r"C:\Users\ihormigo\Desktop\Volcado_pruebas"
        self.filtro_zona = '_PB_'
        self.capa_objetivo = None
        self.tabla_a_volcar = (
            r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod"
            r"\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\A volcar 2a parte\PB\PB a volcar falta caso A.csv"
        )

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 1 - CARGA DE LA CAPA DESDE LA GDB Y FILTRADO PARA AAF y otras condiciones
    # ------------------------------------------------------------------------------------------#

    def cargar_vectorial(self, zona=None):
        print('Ejecutando cargar vectorial')
        self.zona = zona
        walker = arcpy.da.Walk(self.path_gdb_vectorial, datatype="FeatureClass", type='Polygon')
        self.zona = zona.lower()

        if self.zona in ['península', 'peninsula', 'p', 'pb']:
            self.filtro_zona = '_PB_'
        elif self.zona in ['c', 'canarias']:
            self.filtro_zona = '_C_'
        else:
            print('No se ha encontrado la zona indicada')
            sys.exit()

        for root, dirnames, filenames in walker:
            for nombre in filenames:
                if self.filtro_zona in nombre:
                    self.capa_objetivo = nombre
                    break
            if self.capa_objetivo: break

        if self.capa_objetivo:
            print(f"Capa poligonal identificada en la GDB: {self.capa_objetivo} (Se filtrará antes de cargar en RAM)")
        else:
            print("No se encontró ninguna capa de polígonos en la GDB.")
            sys.exit()


    # ------------------------------------------------------------------------------------------#
    # ------------------------------------------------------------------------------------------#
    def sel_vectorial(self):
        seleccion = [71, 72, 75, 76, 77, 8, 811, 812, 82, 83, 84, 85, 861, 862, 863, 864, 865, 87, 88, 89]

        lista_ids = ", ".join(map(str, seleccion))
        where_clause = f"id_tipestr IN ({lista_ids}) AND id_gh IS NULL AND identico_mfeff = 'ESI_TSI' and (obs_tipo not like '%56%' or obs_tipo is null) and asigna_eq <> 'C'"  # ACTUALIZACION

        try:
            print("Filtrando capa en disco con ArcPy para cultivos y artificiales...")
            ruta_entrada = os.path.join(self.path_gdb_vectorial, self.capa_objetivo)

            # 🔑 SOLUCIÓN MODIFICADA: Usamos una GDB temporal propia para evitar bloqueos del sistema
            if not os.path.exists(self.folder_output):
                os.makedirs(self.folder_output)

            gdb_temporal = os.path.join(self.folder_output, "temp_volcado.gdb")
            if not arcpy.Exists(gdb_temporal):
                arcpy.management.CreateFileGDB(self.folder_output, "temp_volcado.gdb")

            self.cbp_sel_fc = os.path.join(gdb_temporal, "temp_sel_art_y_cult")

            if arcpy.Exists(self.cbp_sel_fc):
                arcpy.management.Delete(self.cbp_sel_fc)

            # ArcPy filtra en disco de forma ultra rápida
            arcpy.analysis.Select(ruta_entrada, self.cbp_sel_fc, where_clause)

            print("Cargando la selección optimizada en GeoPandas...")
            self.cbp_sel = gpd.read_file(gdb_temporal, layer="temp_sel_art_y_cult")

            # ⚠️ NO eliminamos 'self.cbp_sel_fc' aquí porque ArcPy Identity lo va a necesitar

            self.cbp_sel['a_cnh24'] = self.cbp_sel.geometry.area
            print(f'✅ Tras la selección quedan {len(self.cbp_sel)} registros cargados de forma segura.')

        except Exception as e:
            print(f"Error crítico al hacer la selección con ArcPy/GeoPandas: {e}")
            sys.exit()

        # ------------------------------------------------------------------------------------------#
        # region       PARTE 2 - RESPALDO AUTOMÁTICO DIRECTO (COPIA TIPO EXPLORADOR DE WINDOWS)
        # ------------------------------------------------------------------------------------------#

    def crear_respaldo_gdb(self):
        """Copia la carpeta .gdb completa a nivel de archivo (equivalente a Ctrl+C / Ctrl+V)."""
        print("\n=== CREANDO COPIA DE SEGURIDAD RÁPIDA DE LA GDB (SISTEMA DE ARCHIVOS) ===")

        if not os.path.exists(self.path_gdb_vectorial):
            print(f"❌ Error: No existe la GDB de origen en: {self.path_gdb_vectorial}")
            sys.exit()

        # Generar ruta del duplicado en la misma carpeta base con sufijo de fecha/hora
        directorio_ppal = self.folder_output
        nombre_gdb = os.path.basename(self.path_gdb_vectorial)
        nombre_base, ext = os.path.splitext(nombre_gdb)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        gdb_backup = os.path.join(directorio_ppal, f"{nombre_base}_bak_{timestamp}{ext}")

        try:
            print(
                f"Copiando directorio .gdb a velocidad de disco...\n   Origen:  {self.folder_output}\n   Destino: {gdb_backup}")

            # shutil.copytree duplica la carpeta completa.
            # ignore_patterns('*.lock') evita errores si hay bloqueos abiertos en ArcGIS Pro/ArcPy.
            shutil.copytree(
                self.path_gdb_vectorial,
                gdb_backup,
                ignore=shutil.ignore_patterns('*.lock')
            )
            print("✅ Copia de seguridad de la GDB creada con éxito.")

        except Exception as e:
            print(f"❌ ERROR CRÍTICO al realizar la copia de la GDB: {e}")
            sys.exit("Proceso abortado por seguridad para proteger los datos originales.")

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 3 - PROCESAMIENTO DEL CSV Y ÁRBOL DE DECISIONES
    # ------------------------------------------------------------------------------------------#
    def procesar_csv(self):
        print("\nCargando el CSV a volcar...")
        try:
            self.df_volcado = pd.read_csv(self.tabla_a_volcar, sep=';', encoding='utf-8', dtype={'id_cnhv2': 'Int64'})

        except FileNotFoundError:
            print(f"No se encontró el archivo CSV en la ruta:\n{self.tabla_a_volcar}")
            sys.exit()

        print(f"CSV cargado con {len(self.df_volcado)} registros. Aplicando árbol de decisiones...")

        # Lista de valores admitidos para HIC
        valores_hic = ['V', 'V1', 'V14', 'V54', 'V6', 'V621', 'V622', 'J', 'J3', 'J4', 'J4.2', 'J4.3', 'J4.4',
                       'J4.5', 'J6', 'V2']

        # Asegurar que los nombres de columnas coinciden, convertimos Accion a numérico por seguridad
        self.df_volcado['Accion'] = pd.to_numeric(self.df_volcado['Accion'], errors='coerce')

        # Máscaras globales (sabiendo que solo existen 2 y 3)
        mask_acc2 = self.df_volcado['Accion'] == 2
        mask_acc3 = self.df_volcado['Accion'] == 3

        # Iteramos del 1 al 10 para los 10 posibles LPEH
        for x in range(1, 11):
            col_acc2 = f'LPEH_{x}'
            col_acc3 = f'lpeh{x}_3'

            cols_resultado = [f'fte_lpeh{x}', f'asigna_lpeh{x}', f'hic{x}', f'fte_hic{x}', f'asigna_hic{x}']
            for col in cols_resultado:
                if col not in self.df_volcado.columns:
                    self.df_volcado[col] = None
                self.df_volcado[col] = self.df_volcado[col].astype('object')

            # Creamos columnas vacías en caso de que el CSV original no las tenga (previene KeyError)
            if col_acc2 not in self.df_volcado.columns: self.df_volcado[col_acc2] = np.nan
            if col_acc3 not in self.df_volcado.columns: self.df_volcado[col_acc3] = np.nan

            # Extraemos en una sola Serie temporal el valor lpeh que aplica a la fila actual
            lpeh_activo = np.where(mask_acc2, self.df_volcado[col_acc2], self.df_volcado[col_acc3])
            s_lpeh = pd.Series(lpeh_activo, index=self.df_volcado.index)

            # Filtramos aquellos que sean nulos o estén vacíos
            mask_not_null = s_lpeh.notna() & (s_lpeh.astype(str).str.strip() != '') & (
                        s_lpeh.astype(str).str.lower() != 'nan')

            # -- 1ª Parte: Reglas según Acción --
            # Acción = 2
            self.df_volcado.loc[mask_acc2 & mask_not_null, f'fte_lpeh{x}'] = '628'
            self.df_volcado.loc[mask_acc2 & mask_not_null, f'asigna_lpeh{x}'] = '2bb'

            # Acción = 3
            self.df_volcado.loc[mask_acc3 & mask_not_null, f'fte_lpeh{x}'] = 'x'
            self.df_volcado.loc[mask_acc3 & mask_not_null, f'asigna_lpeh{x}'] = '5a'

            # -- 2ª Parte: Reglas HIC --
            mask_in_hic = s_lpeh.isin(valores_hic)

            # Si el LPEH cumple el IN
            self.df_volcado.loc[mask_not_null & mask_in_hic, f'hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & mask_in_hic, f'fte_hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & mask_in_hic, f'asigna_hic{x}'] = 'x'

            # Si el LPEH NO cumple el IN
            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'hic{x}'] = 'nc'
            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'fte_hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'asigna_hic{x}'] = 'x'

        print("✅ Árbol de decisiones aplicado correctamente a los 10 rangos LPEH.")

        # --- Guardar el CSV procesado ---
        print("Guardando el CSV procesado...")

        # Comprobar si la carpeta de salida existe, si no, crearla
        if not os.path.exists(self.folder_output):
            os.makedirs(self.folder_output)

        # Extraer el nombre original sin ruta y añadir el sufijo _volcado
        nombre_original = os.path.basename(self.tabla_a_volcar)
        nombre_sin_ext, ext = os.path.splitext(nombre_original)
        nuevo_nombre = f"{nombre_sin_ext}_volcado_REVISAR{ext}"

        # Construir la ruta completa de salida
        ruta_salida = os.path.join(self.folder_output, nuevo_nombre)

        # Exportar el CSV (usamos utf-8-sig para que Excel en Windows lea bien tildes y eñes)
        self.df_volcado.to_csv(ruta_salida, sep=';', index=False, encoding='utf-8-sig')

        print(f"✅ Archivo guardado con éxito en:\n{ruta_salida}")

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 4 - VOLCADO DE ATRIBUTOS A LA GDB
    # ------------------------------------------------------------------------------------------#
    def volcar_a_gdb(self):
        print("\n=== INICIANDO VOLCADO A LA CAPA DE LA GDB ===")
        if not self.capa_objetivo:
            print("❌ Error: No se ha identificado la capa objetivo. Debes ejecutar 'cargar_vectorial' primero.")
            return

        ruta_fc_objetivo = os.path.join(self.path_gdb_vectorial, self.capa_objetivo)

        campos_a_volcar = []
        for x in range(1, 11):
            campos_a_volcar.extend([
                f'fte_lpeh{x}', f'asigna_lpeh{x}',
                f'hic{x}', f'fte_hic{x}', f'asigna_hic{x}'
            ])

        print("Verificando campos en la capa vectorial de la GDB...")
        campos_existentes_gdb = [f.name for f in arcpy.ListFields(ruta_fc_objetivo)]

        for col in campos_a_volcar:
            if col not in campos_existentes_gdb:
                print(f" ➕ Creando campo ausente en GDB: {col}")
                arcpy.management.AddField(ruta_fc_objetivo, col, "TEXT", field_length=50)

        print("Indexando datos del CSV procesado...")
        df_limpio = self.df_volcado.dropna(subset=['id_cnhv2']).copy()
        df_limpio['id_key'] = df_limpio['id_cnhv2'].astype(str).str.split('.').str[0].str.strip()

        dict_volcado = {}
        for _, row in df_limpio.iterrows():
            key = row['id_key']
            valores = [None if pd.isna(row[col]) else str(row[col]) for col in campos_a_volcar]
            dict_volcado[key] = valores

        campos_cursor = ['id_cnhv2'] + campos_a_volcar
        print(f"Actualizando registros en: {self.capa_objetivo}...")

        registros_actualizados = 0
        with arcpy.da.UpdateCursor(ruta_fc_objetivo, campos_cursor) as cursor:
            for row in cursor:
                raw_id = row[0]
                if raw_id is None:
                    continue

                id_str = str(raw_id).split('.')[0].strip()

                if id_str in dict_volcado:
                    nuevos_valores = dict_volcado[id_str]
                    for idx, val in enumerate(nuevos_valores):
                        row[idx + 1] = val

                    cursor.updateRow(row)
                    registros_actualizados += 1

        print(f"✅ Volcado completado: {registros_actualizados} polígonos actualizados con éxito en la GDB.")

    # ------------------------------------------------------------------------------------------#
    # ------------------------------------------------------------------------------------------#
    def ejecutar_volcado(self, zona='peninsula'):
        """Método orquestador que ejecuta todas las funciones de la clase secuencialmente."""
        print("=== INICIO DEL PROCESO DE VOLCADO ===")
        ini = time.time()
        print(time.strftime("%d/%m/%Y %H:%M:%S"))
        
        self.cargar_vectorial(zona)
        self.sel_vectorial()
        self.crear_respaldo_gdb()
        self.procesar_csv()
        self.volcar_a_gdb()

        fin = time.time()
        dif = fin-ini
        print(f"Proceso finalizado correctamente en {dif:.2f} segundos")

## ========================================================================================== ##
## ===================================== MAIN =============================================== ##
## ========================================================================================== ##
if __name__ == '__main__':
    # Se instancia la clase y se ejecuta el flujo completo usando la configuración por defecto (_PB_ / península)
    proceso = volcado_aaf()
    proceso.ejecutar_volcado(zona='peninsula')

