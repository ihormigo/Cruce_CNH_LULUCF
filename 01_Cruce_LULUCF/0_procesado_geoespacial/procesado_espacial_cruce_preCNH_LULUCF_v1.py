import os
import sys
import time
import arcpy
import pandas as pd
import geopandas as gpd


class cruce:
    def __init__(self, path_gdb_vectorial, path_lulucf, folder_output):
        self.path_gdb_vectorial = path_gdb_vectorial
        self.path_lulucf = path_lulucf
        self.folder_output = folder_output

        if not os.path.exists(self.folder_output):
            os.makedirs(self.folder_output, exist_ok=True)

        self.gdb_temporal = os.path.join(self.folder_output, "Temp_Procesos.gdb")
        if not arcpy.Exists(self.gdb_temporal):
            arcpy.management.CreateFileGDB(self.folder_output, "Temp_Procesos.gdb")

        self.cbp = None
        self.raster_rootname = 'LULUCF2021'
        self.filtro_zona = '_PB_'
        self.capa_objetivo = None
        self.cbp_sel = None
        self.zona = None
        self.epsg = None
        self.imagen = None
        self.transform = None
        self.metadatos = None
        self.lulucf_vec = None
        self.dataset = None
        self.cruce_cbp_lulucf = None
        self.gdb_folder = None
        self.identity = None
        self.path_excel = None
        self.df_mapeado = None
        self.redondeo = None
        self.df_pivotado = None
        self.lulucf_filtrado = False
        self.csv_limpio = None

        # Atributos para rutas temporales seguras
        self.cbp_sel_fc = None
        self.lulucf_vec_fc = None
        self.fc_identity_out = None

    # ------------------------------------------------------------------------------------------#
    # region       PARTE 1 - METODOLOGÍA CRUCE CBP (preCNH24) - LULUCF
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
        where_clause = f"id_tipestr IN ({lista_ids}) AND id_gh IS NULL AND identico_mfeff = 'ESI_TSI' and (obs_tipo not like '%56%' or obs_tipo is null) and asigna_eq <> 'C'" # ACTUALIZACION

        try:
            print("Filtrando capa en disco con ArcPy para cultivos y artificiales...")
            ruta_entrada = os.path.join(self.path_gdb_vectorial, self.capa_objetivo)

            self.cbp_sel_fc = os.path.join(self.gdb_temporal, f"temp_sel_art_{self.zona}")

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
    # ------------------------------------------------------------------------------------------
    def cargar_lulucf(self, path_lulucf=None):
        if path_lulucf is None:
            path_lulucf = self.path_lulucf

        if self.zona.lower() in ['c', 'canarias']:
            raster = f'{self.raster_rootname}_Can'
        elif self.zona.lower() in ['p', 'pb', 'península', 'peninsula']:
            raster = f'{self.raster_rootname}_PB'
        else:
            print(f'La zona {self.zona} introducida no es correcta')
            sys.exit()

        ruta_raster_gdb = os.path.normpath(os.path.join(path_lulucf, raster))

        # 🔑 SOLUCIÓN: Guardamos la ruta en el atributo de clase que buscará 'poligonizar'
        self.raster_clip = os.path.normpath(os.path.join(self.folder_output, f"temp_{raster}.tif"))

        try:
            print(f"✂️ Generando recorte optimizado por BBOX de '{raster}' desde la GDB...")
            if not os.path.exists(self.folder_output):
                os.makedirs(self.folder_output, exist_ok=True)

            # Extraemos la caja delimitadora (Bounding Box) de las parcelas seleccionadas
            xmin, ymin, xmax, ymax = self.cbp_sel.total_bounds
            bbox_string = f"{xmin} {ymin} {xmax} {ymax}"

            # Desactivamos pirámides y estadísticas en ArcPy para acelerar la escritura
            arcpy.env.pyramid = "NONE"
            arcpy.env.rasterStatistics = "NONE"

            if os.path.exists(self.raster_clip):
                os.remove(self.raster_clip)

            # Cortamos un rectángulo mínimo alrededor de tus parcelas de forma instantánea
            arcpy.management.Clip(
                in_raster=ruta_raster_gdb,
                rectangle=bbox_string,
                out_raster=self.raster_clip,
                clipping_geometry="NONE",
                maintain_clipping_extent="NO_MAINTAIN_EXTENT"
            )

            # Obtenemos el EPSG nativamente con ArcPy (así evitamos abrir Rasterio aquí)
            desc = arcpy.Describe(self.raster_clip)
            self.epsg = desc.spatialReference.factoryCode

            if self.epsg not in [25830, 32628]:
                print(f'El crs es {self.epsg} y debería ser 25830 o 32628')
                sys.exit()
            else:
                print(f'crs correcto {self.epsg}')

            print("✅ Recorte optimizado generado en disco con éxito.")

        except Exception as e:
            print(f"❌ Error al procesar el ráster con ArcPy: \n{e}")
            if os.path.exists(self.raster_clip):
                os.remove(self.raster_clip)
            sys.exit()

    # ------------------------------------------------------------------------------------------#
    def poligonizar(self):
        print("📐 Convirtiendo Ráster recortado a Polígonos de forma nativa en disco con ArcPy...")

        gdb_temporal = arcpy.env.scratchGDB
        self.lulucf_vec_fc = os.path.join(gdb_temporal, "temp_lulucf_vec_art_y_cult")

        if arcpy.Exists(self.lulucf_vec_fc):
            arcpy.management.Delete(self.lulucf_vec_fc)

        try:
            # Poligonización nativa ultra rápida (mantiene consistencia del píxel píxel)
            arcpy.conversion.RasterToPolygon(
                in_raster=self.raster_clip,
                out_polygon_features=self.lulucf_vec_fc,
                simplify="NO_SIMPLIFY",
                raster_field="Value"
            )

            # Limpiamos el .tif temporal del disco ya que no se requiere más
            if os.path.exists(self.raster_clip):
                os.remove(self.raster_clip)
                # 🔥 [SOLUCIÓN] Borrar únicamente el "ruido" del 65535 sin tocar los demás usos
                print("🧹 Eliminando el polígono de fondo NoData (65535) para limpiar el cruce...")
                with arcpy.da.UpdateCursor(self.lulucf_vec_fc, ["gridcode"]) as cursor:
                    for row in cursor:
                        if row[0] == 65535:
                            cursor.deleteRow()

            print(f'✅ Se han generado polígonos de forma nativa en el disco.')

        except Exception as e:
            print(f"❌ Error al poligonizar con ArcPy: \n{e}")
            if os.path.exists(self.raster_clip):
                os.remove(self.raster_clip)
            sys.exit()

    # ------------------------------------------------------------------------------------------#
    def filtro_lulucf(self):
        print('SE HA APLICADO EL FILTRO LULUCF PARA "ARTIFICIALES" O "CULTIVOS"')
        gdb_temporal = arcpy.env.scratchGDB
        fc_filtrado = os.path.join(gdb_temporal, "temp_lulucf_filtro_art_y_cult")

        where_clause = "(gridcode >= 700 AND gridcode < 800) OR (gridcode >= 800 AND gridcode < 900)"

        try:
            if arcpy.Exists(fc_filtrado):
                arcpy.management.Delete(fc_filtrado)

            arcpy.analysis.Select(self.lulucf_vec_fc, fc_filtrado, where_clause)

            # Reemplazamos la ruta por el archivo ya filtrado y limpiamos
            arcpy.management.Delete(self.lulucf_vec_fc)
            self.lulucf_vec_fc = fc_filtrado
            self.lulucf_filtrado = True
            print("✅ Filtro LULUCF aplicado correctamente en disco.")

        except Exception as e:
            print(f"❌ Error al filtrar el LULUCF con ArcPy: {e}")
            sys.exit()

    # ------------------------------------------------------------------------------------------#
    def identity_area(self, capa=None, sobrescribir=None):
        if self.lulucf_filtrado is not True:
            print('SE HA EJECUTADO EL PROCESO "SIN FILTRO LULUCF"')

        print("⚡ Ejecutando 'arcpy.analysis.Identity' nativo en disco...")
        gdb_temporal = arcpy.env.scratchGDB
        fc_identity_out = os.path.join(gdb_temporal, "temp_identity_art_y_cult")

        if arcpy.Exists(fc_identity_out):
            arcpy.management.Delete(fc_identity_out)

        try:
            # 1. Asegurar que 'a_cnh24' está calculado en el archivo de disco de entrada para que herede al Identity
            if not arcpy.ListFields(self.cbp_sel_fc, "a_cnh24"):
                arcpy.management.AddField(self.cbp_sel_fc, "a_cnh24", "DOUBLE")
            arcpy.management.CalculateField(self.cbp_sel_fc, "a_cnh24", "!shape.area!", "PYTHON3")

            # 🚀 El cruce espacial pesado se realiza en segundos usando el motor C++ de ArcPy
            arcpy.analysis.Identity(
                in_features=self.cbp_sel_fc,
                identity_features=self.lulucf_vec_fc,
                out_feature_class=fc_identity_out
            )

            print("📊 Calculando áreas y porcentajes de forma nativa en disco con ArcPy")

            # Crear y calcular campo A_LULUCF
            arcpy.management.AddField(fc_identity_out, "A_LULUCF", "DOUBLE")
            arcpy.management.CalculateField(fc_identity_out, "A_LULUCF", "!shape.area!", "PYTHON3")

            # Crear y calcular campo PER (Evitando división por cero)
            arcpy.management.AddField(fc_identity_out, "PER", "DOUBLE")
            arcpy.management.CalculateField(fc_identity_out, "PER",
                                            "!A_LULUCF! / !a_cnh24! * 100 if !a_cnh24! > 0 else 0", "PYTHON3")

            # Crear y calcular campo PER_R
            arcpy.management.AddField(fc_identity_out, "PER_R", "LONG")
            arcpy.management.CalculateField(fc_identity_out, "PER_R", "round(!PER!)", "PYTHON3")

            print('✅ Proceso de Identity y cálculos de área realizados correctamente en disco.')

        except Exception as e:
            print(f"❌ Error crítico durante el Identity con ArcPy: \n{e}")
            sys.exit()

        if sobrescribir is None:
            sobrescribir = 'S'

        self.cruce_cbp_lulucf = capa if capa is not None else 'CBP_LULUCF'

        if self.filtro_zona == '_PB_':
            self.dataset = 'etrs89'
        elif self.filtro_zona == '_C_':
            self.dataset = 'wgs84'

        self.gdb_folder = 'Cruce_CBP_LULUCF.gdb'
        cbp_lulucf_path = os.path.normpath(os.path.join(self.folder_output, self.gdb_folder))

        try:
            print(f"📦 Exportando resultado espacial directamente a la GDB final de forma nativa...")
            # Crear la GDB de salida si no existe
            gdb_dir = os.path.dirname(cbp_lulucf_path)
            gdb_name = os.path.basename(cbp_lulucf_path)
            if not arcpy.Exists(cbp_lulucf_path):
                arcpy.management.CreateFileGDB(gdb_dir, gdb_name)

            # Crear el Feature Dataset si no existe
            dataset_path = os.path.join(cbp_lulucf_path, self.dataset)
            if not arcpy.Exists(dataset_path):
                sr = arcpy.Describe(fc_identity_out).spatialReference
                arcpy.management.CreateFeatureDataset(cbp_lulucf_path, self.dataset, sr)

            # Copiar la capa de manera directa sin pasar por estructuras GeoPandas intermedias
            target_fc = os.path.join(dataset_path, self.cruce_cbp_lulucf)
            if arcpy.Exists(target_fc):
                if sobrescribir == 'S':
                    arcpy.management.Delete(target_fc)
                    arcpy.management.CopyFeatures(fc_identity_out, target_fc)
                    print(f"✅ Capa sobrescrita y guardada con éxito en: {target_fc}")
            else:
                arcpy.management.CopyFeatures(fc_identity_out, target_fc)
                print(f"✅ Capa guardada con éxito en: {target_fc}")

        except Exception as e:
            print(f"❌ Error al exportar a la GDB final con ArcPy: \n{e}")

    def extraccion_tabla(self):
        print("Extrayendo tabla tras el proceso de Identity (Optimizado sin cargar geometrías)...")
        campos_sel = ["OBJECTID", "id_cnhv2", "a_cnh24", "gridcode",
                      "A_LULUCF", "Shape_Length", "PER", "PER_R"]

        gdb_temporal = arcpy.env.scratchGDB
        fc_identity_out = os.path.join(gdb_temporal, "temp_identity_art_y_cult")

        # Control de seguridad tolerante a mayúsculas/minúsculas de ArcPy para los campos
        campos_existentes = {f.name.lower(): f.name for f in arcpy.ListFields(fc_identity_out)}
        campos_mapeados = []
        for c in campos_sel:
            if c.lower() in campos_existentes:
                campos_mapeados.append(campos_existentes[c.lower()])
            else:
                if c.lower() == 'objectid' and 'fid' in campos_existentes:
                    campos_mapeados.append(campos_existentes['fid'])
                elif c.lower() == 'shape_length' and 'shape_len' in campos_existentes:
                    campos_mapeados.append(campos_existentes['shape_len'])
                else:
                    campos_mapeados.append(c)

        # Extraemos las filas de atributos usando un SearchCursor rápido (evita Geometrías)
        data = []
        with arcpy.da.SearchCursor(fc_identity_out, campos_mapeados) as cursor:
            for row in cursor:
                data.append(row)

        # Generamos un DataFrame de Pandas clásico (ocupa menos del 5% de memoria que el GeoDataFrame)
        df_campos_sel = pd.DataFrame(data, columns=campos_sel)

        # Definimos la ruta siempre con extensión .csv
        self.path_excel = os.path.normpath(os.path.join(self.folder_output, f'cbp_lulucf_{self.zona}_art_y_cult.csv'))

        # Guardamos en CSV (delimitador punto y coma y codificación utf-8-sig)
        df_campos_sel.to_csv(self.path_excel, index=False, sep=';', encoding='utf-8-sig')
        print(f"✅ Tabla extraída correctamente en formato CSV: {self.path_excel} ({len(df_campos_sel)} registros)")

        # 🧹 LIMPIEZA TOTAL EN DISCO: Una vez finalizada la extracción, liberamos la GDB temporal
        try:
            arcpy.management.Delete(self.cbp_sel_fc)
            arcpy.management.Delete(self.lulucf_vec_fc)
            arcpy.management.Delete(fc_identity_out)
            print("🧹 Limpieza de archivos temporales en disco completada.")
        except Exception as e:
            print(f"⚠️ Nota de limpieza: No se pudieron borrar algunos archivos temporales: {e}")


def procesar_zona(tarea, path_gdb_vectorial, path_lulucf, folder_output, filtro=False):
    objeto_cruce = cruce(path_gdb_vectorial=path_gdb_vectorial,
                         path_lulucf=path_lulucf,
                         folder_output=folder_output)
    objeto_cruce.zona = tarea['zona']

    print(f"\n{'=' * 22}\nINICIANDO TAREA: Zona {tarea['zona']}\n{'=' * 22}")
    ini_tarea = time.time()

    try:
        # 2. Ejecución secuencial de la lógica de la clase
        objeto_cruce.cargar_vectorial(zona=tarea['zona'])
        objeto_cruce.sel_vectorial()
        objeto_cruce.cargar_lulucf()
        objeto_cruce.poligonizar()

        if filtro == True:
            objeto_cruce.filtro_lulucf()
        else:
            pass

        if objeto_cruce.lulucf_filtrado is True:
            objeto_cruce.identity_area(capa=f'CBP_LULUCF_{tarea["zona"]}_art_y_cult_CON_FILTRO', sobrescribir='S')
        else:
            objeto_cruce.identity_area(capa=f'CBP_LULUCF_{tarea["zona"]}_art_y_cult_SIN_FILTRO', sobrescribir='S')

        objeto_cruce.extraccion_tabla()

        fin_tarea = time.time()
        print(f"✅ Tarea {tarea['zona']} terminada en {fin_tarea - ini_tarea:.2f} segundos.")

    except Exception as e:
        # Si una zona falla, el error se captura aquí, permitiendo que el bucle principal continúe
        print(f"❌ Error crítico en la zona {tarea['zona']}: {e}")


## ========================================================================================== ##
## ========================================================================================== ##
if __name__ == "__main__":
    from datetime import datetime

    # Registro de inicio
    inicio_ejecucion = datetime.now()
    print(f"INICIO DE LA EJECUCION DEL SCRIPT : {inicio_ejecucion.strftime('%d/%m/%Y %H:%M:%S')}")
    ini_global = time.time()

    print("=== CONFIGURACIÓN DE RUTAS DE ENTRADA Y SALIDA ===")
    path_gdb_vectorial = input(r"1. Ruta de la GDB vectorial original (.gdb): ").strip('\'"')
    path_lulucf = input(r"2. Ruta de la GDB de LULUCF (.gdb): ").strip('\'"')
    folder_output = input(r"3. Ruta de la carpeta de salida: ").strip('\'"')

    # Configuración de las tareas a realizar
    tareas = [
        {'zona': 'c', 'filtro': False}, # Este filtro dejo de usarse en la metodología
        {'zona': 'pb', 'filtro': False},
    ]

    for tarea in tareas:
        procesar_zona(tarea, path_gdb_vectorial, path_lulucf, folder_output, filtro=tarea['filtro'])

    # Registro de fin
    fin_global = time.time()
    print(f"\n🏁 Todo el proceso finalizado en {(fin_global - ini_global) :.2f} segundos.")

# C:\Users\ihormigo\Desktop\resultados_cruce\0 datos originales\preCNH24v1_int_AAF_20260731.gdb
# C:\Users\ihormigo\Desktop\resultados_cruce\0 datos originales\Serie20240920.gdb
# C:\Users\ihormigo\Desktop\PRUEBAS\Procesado_geoespacial
