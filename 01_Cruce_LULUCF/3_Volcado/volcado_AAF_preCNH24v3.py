import os
import sys
import time
import arcpy
import pandas as pd
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
        self.ruta_fc_objetivo = None  # Almacenará la ruta completa incluyendo el Dataset

        self.tabla_a_volcar = (
            r"C:\Users\ihormigo\Desktop\resultados_cruce\3 Resultados Atlas y 2a parte metod"
            r"\2 Resultados a procesar\2a parte metodologia (binomios 1_1)\A volcar 2a parte\PB\PB a volcar falta caso A.csv"
        )

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 1 - CARGA DE LA CAPA DESDE LA GDB
    # ------------------------------------------------------------------------------------------#

    def cargar_vectorial(self, zona=None):
        print('Ejecutando cargar vectorial')
        self.zona = zona.lower() if zona else ''
        walker = arcpy.da.Walk(self.path_gdb_vectorial, datatype="FeatureClass", type='Polygon')

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
                    # Ruta absoluta que ya incluye el Feature Dataset (etrs89 o wgs84)
                    self.ruta_fc_objetivo = os.path.join(root, nombre)
                    break
            if self.capa_objetivo: break

        if self.capa_objetivo:
            print(f"Capa poligonal identificada en la GDB: {self.capa_objetivo}")
            print(f"Ruta completa de trabajo: {self.ruta_fc_objetivo}")
        else:
            print("No se encontró ninguna capa de polígonos en la GDB.")
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

        directorio_ppal = self.folder_output
        nombre_gdb = os.path.basename(self.path_gdb_vectorial)
        nombre_base, ext = os.path.splitext(nombre_gdb)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        gdb_backup = os.path.join(directorio_ppal, f"{nombre_base}_bak_{timestamp}{ext}")

        try:
            print(
                f"Copiando directorio .gdb a velocidad de disco...\n   Origen:  {self.path_gdb_vectorial}\n   Destino: {gdb_backup}")

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

        valores_hic = ['V', 'V1', 'V14', 'V54', 'V6', 'V621', 'V622', 'J', 'J3', 'J4', 'J4.2', 'J4.3', 'J4.4',
                       'J4.5', 'J6', 'V2']

        self.df_volcado['Accion'] = pd.to_numeric(self.df_volcado['Accion'], errors='coerce')

        mask_acc2 = self.df_volcado['Accion'] == 2
        mask_acc3 = self.df_volcado['Accion'] == 3

        for x in range(1, 11):
            col_acc2 = f'LPEH_{x}'
            col_acc3 = f'lpeh{x}_3'

            # 🟢 CAMBIO: Sufijo _volcado para el campo temporal en Pandas
            col_lpeh_volcado = f'lpeh{x}_volcado'

            cols_resultado = [col_lpeh_volcado, f'fte_lpeh{x}', f'asigna_lpeh{x}', f'hic{x}', f'fte_hic{x}',
                              f'asigna_hic{x}']

            for col in cols_resultado:
                if col not in self.df_volcado.columns:
                    self.df_volcado[col] = None
                self.df_volcado[col] = self.df_volcado[col].astype('object')

            if col_acc2 not in self.df_volcado.columns: self.df_volcado[col_acc2] = np.nan
            if col_acc3 not in self.df_volcado.columns: self.df_volcado[col_acc3] = np.nan

            # Extraemos el valor lpeh que aplica a la fila actual
            lpeh_activo = np.where(mask_acc2, self.df_volcado[col_acc2], self.df_volcado[col_acc3])
            s_lpeh = pd.Series(lpeh_activo, index=self.df_volcado.index)

            # Guardamos en la columna con sufijo _volcado
            self.df_volcado[col_lpeh_volcado] = s_lpeh

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

            self.df_volcado.loc[mask_not_null & mask_in_hic, f'hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & mask_in_hic, f'fte_hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & mask_in_hic, f'asigna_hic{x}'] = 'x'

            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'hic{x}'] = 'nc'
            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'fte_hic{x}'] = 'x'
            self.df_volcado.loc[mask_not_null & ~mask_in_hic, f'asigna_hic{x}'] = 'x'

        print("✅ Árbol de decisiones aplicado correctamente a los 10 rangos LPEH.")

        # --- Guardar el CSV procesado ---
        print("Guardando el CSV procesado...")

        if not os.path.exists(self.folder_output):
            os.makedirs(self.folder_output)

        nombre_original = os.path.basename(self.tabla_a_volcar)
        nombre_sin_ext, ext = os.path.splitext(nombre_original)
        nuevo_nombre = f"{nombre_sin_ext}_volcado_REVISAR{ext}"

        ruta_salida = os.path.join(self.folder_output, nuevo_nombre)

        self.df_volcado.to_csv(ruta_salida, sep=';', index=False, encoding='utf-8-sig')
        print(f"✅ Archivo guardado con éxito en:\n{ruta_salida}")

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 4 - VOLCADO DE ATRIBUTOS A LA GDB
    # ------------------------------------------------------------------------------------------#

    def volcar_a_gdb(self):
        print("\n=== INICIANDO VOLCADO A LA CAPA DE LA GDB ===")

        if not self.capa_objetivo or not self.ruta_fc_objetivo:
            print("❌ Error: No se ha identificado la capa objetivo. Ejecuta 'cargar_vectorial' primero.")
            return

        # 1. Leer los campos que EXISTEN actualmente en la GDB original
        campos_existentes_gdb = [f.name for f in arcpy.ListFields(self.ruta_fc_objetivo)]

        # 2. LIMPIEZA DE GDB: Si se crearon campos '_volcado' por error en pruebas previas, los eliminamos
        campos_basura = [f for f in campos_existentes_gdb if f.endswith('_volcado')]
        if campos_basura:
            print(f" 🗑️ Eliminando campos residuales insertados por error en la GDB: {campos_basura}")
            arcpy.management.DeleteField(self.ruta_fc_objetivo, campos_basura)
            # Actualizamos la lista de campos tras el borrado
            campos_existentes_gdb = [f.name for f in arcpy.ListFields(self.ruta_fc_objetivo)]

        # 3. Crear el mapeo estricto: Solo pasamos datos si la columna original ya está en la GDB
        parejas_mapeo = []
        for x in range(1, 11):
            posibles_parejas = [
                # (Nombre que debe tener en GDB, Nombre que tiene en el DataFrame de Pandas)
                (f'lpeh{x}', f'lpeh{x}_volcado'),
                (f'fte_lpeh{x}', f'fte_lpeh{x}'),
                (f'asigna_lpeh{x}', f'asigna_lpeh{x}'),
                (f'hic{x}', f'hic{x}'),
                (f'fte_hic{x}', f'fte_hic{x}'),
                (f'asigna_hic{x}', f'asigna_hic{x}')
            ]

            for col_gdb, col_df in posibles_parejas:
                # LA CLAVE: Solo autorizamos la pareja si 'col_gdb' YA EXISTE en la Geodatabase
                if col_gdb in campos_existentes_gdb:
                    parejas_mapeo.append((col_gdb, col_df))

        if not parejas_mapeo:
            print("❌ Ninguno de los campos a volcar existe en la GDB original. No hay nada que actualizar.")
            return

        # Separar las listas autorizadas
        campos_gdb_validos = [p[0] for p in parejas_mapeo]
        campos_df_validos = [p[1] for p in parejas_mapeo]

        print(f"✅ Filtro aplicado: Se actualizarán EXCLUSIVAMENTE {len(campos_gdb_validos)} campos existentes.")

        # 4. Preparar diccionario de datos, extrayendo del CSV SOLO los campos autorizados
        df_limpio = self.df_volcado.dropna(subset=['id_cnhv2']).copy()
        df_limpio['id_key'] = df_limpio['id_cnhv2'].astype(str)

        dict_volcado = {}
        for _, row in df_limpio.iterrows():
            key = row['id_key']
            valores = [None if pd.isna(row[col]) else str(row[col]) for col in campos_df_validos]
            dict_volcado[key] = valores

        # 5. Ejecutar la actualización (UpdateCursor)
        campos_cursor = ['id_cnhv2'] + campos_gdb_validos
        registros_actualizados = 0

        edit = arcpy.da.Editor(self.path_gdb_vectorial)
        try:
            edit.startEditing(False, True)
            edit.startOperation()

            with arcpy.da.UpdateCursor(self.ruta_fc_objetivo, campos_cursor) as cursor:
                for row in cursor:
                    raw_id = row[0]
                    if raw_id is None:
                        continue

                    id_str = str(raw_id)

                    if id_str in dict_volcado:
                        nuevos_valores = dict_volcado[id_str]
                        # Sobrescribir los datos en el cursor
                        for idx, val in enumerate(nuevos_valores):
                            row[idx + 1] = val

                        cursor.updateRow(row)
                        registros_actualizados += 1

            edit.stopOperation()
            edit.stopEditing(True)

        except Exception as e:
            if edit.isEditing:
                edit.stopOperation()
                edit.stopEditing(False)
            print(f"❌ Error durante la actualización en la GDB: {e}")
            raise

        print(
            f"✅ Volcado completado: {registros_actualizados} polígonos actualizados preservando la estructura original de la GDB.")

    # ------------------------------------------------------------------------------------------#
    # ------------------------------------------------------------------------------------------#
    def ejecutar_volcado(self, zona='peninsula'):
        """Método orquestador que ejecuta todas las funciones de la clase secuencialmente."""
        print("=== INICIO DEL PROCESO DE VOLCADO ===")
        ini = time.time()
        print(time.strftime("%d/%m/%Y %H:%M:%S"))

        self.cargar_vectorial(zona)
        self.crear_respaldo_gdb()
        self.procesar_csv()
        self.volcar_a_gdb()

        fin = time.time()
        dif = fin - ini
        print(f"Proceso finalizado correctamente en {dif:.2f} segundos")


## ========================================================================================== ##
## ===================================== MAIN =============================================== ##
## ========================================================================================== ##
if __name__ == '__main__':
    proceso = volcado_aaf()
    proceso.ejecutar_volcado(zona='peninsula')