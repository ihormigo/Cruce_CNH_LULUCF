import arcpy

print("=== Verificación de ArcPy ===")

# Obtener información de la instalación de ArcGIS Pro
install_info = arcpy.GetInstallInfo()
print(f"Versión de ArcGIS Pro: {install_info['Version']}")
print(f"Ruta de instalación: {install_info['InstallDir']}")

# Comprobar el estado de la licencia
license_code = arcpy.CheckProduct("ArcInfo")
print(f"Estado de licencia (ArcInfo): {license_code}")

print("\n¡ArcPy está configurado y funcionando correctamente!")