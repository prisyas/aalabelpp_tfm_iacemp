#!/usr/bin/env python3
"""
AALabelPP - Setup Completo de Datos
Script maestro que ejecuta todo el proceso de preparación de datos

Fecha: 2025-12-14
Versión: 1.0
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Añadir paths
sys.path.append(str(Path(__file__).parent.parent))

from scripts.download_normatives import (
    descargar_todas_normativas,
    guardar_metadatos,
    imprimir_resumen
)
from scripts.ingest_pipeline import PipelineIngestion
from database.db_config import (
    DatabaseEngine,
    verificar_conexion,
    verificar_extension_pgvector,
    obtener_estadisticas_db
)


class SetupCompleto:
    """Orquestador del setup completo de datos"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data" / "normativas"
        self.resultados = {
            'fecha_ejecucion': datetime.now().isoformat(),
            'pasos_completados': [],
            'errores': [],
            'estadisticas': {}
        }
    
    def paso_1_verificar_bd(self) -> bool:
        """Paso 1: Verificar conexión a base de datos"""
        print("\n" + "="*80)
        print("PASO 1: VERIFICAR BASE DE DATOS")
        print("="*80)
        
        try:
            # Inicializar motor
            DatabaseEngine.initialize()
            
            # Verificar conexión
            if not verificar_conexion():
                raise Exception("No se pudo conectar a la base de datos")
            
            # Verificar pgvector
            if not verificar_extension_pgvector():
                print("⚠ Advertencia: pgvector no detectado")
                print("   El sistema funcionará, pero la búsqueda vectorial no estará disponible")
            
            # Obtener estadísticas
            stats = obtener_estadisticas_db()
            print(f"\n📊 Estadísticas de BD:")
            for key, value in stats.items():
                print(f"  • {key}: {value}")
            
            self.resultados['pasos_completados'].append('verificar_bd')
            self.resultados['estadisticas']['bd_inicial'] = stats
            
            print("\n✅ Base de datos verificada")
            return True
            
        except Exception as e:
            error_msg = f"Error verificando BD: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.resultados['errores'].append(error_msg)
            return False
    
    def paso_2_descargar_normativas(self, force: bool = False) -> bool:
        """Paso 2: Descargar normativas oficiales"""
        print("\n" + "="*80)
        print("PASO 2: DESCARGAR NORMATIVAS OFICIALES")
        print("="*80)
        
        try:
            resultados = descargar_todas_normativas(force=force)
            
            # Guardar metadatos
            metadata_file = self.data_dir / "metadatos_descarga.json"
            guardar_metadatos(resultados, metadata_file)
            
            # Resumen
            imprimir_resumen(resultados)
            
            self.resultados['pasos_completados'].append('descargar_normativas')
            self.resultados['estadisticas']['descarga'] = {
                'exitosos': len(resultados['exitosas']),
                'fallidos': len(resultados['fallidas']),
                'omitidos': len(resultados['omitidas'])
            }
            
            # Verificar que al menos 1 documento fue descargado
            if len(resultados['exitosas']) == 0 and len(resultados['omitidas']) == 0:
                raise Exception("No se descargó ningún documento")
            
            print("\n✅ Normativas descargadas")
            return True
            
        except Exception as e:
            error_msg = f"Error descargando normativas: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.resultados['errores'].append(error_msg)
            return False
    
    def paso_3_procesar_documentos(self) -> bool:
        """Paso 3: Procesar y cargar documentos en BD"""
        print("\n" + "="*80)
        print("PASO 3: PROCESAR Y CARGAR DOCUMENTOS")
        print("="*80)
        
        try:
            # Cargar metadatos
            metadata_file = self.data_dir / "metadatos_descarga.json"
            if not metadata_file.exists():
                raise Exception("No se encontró metadatos_descarga.json")
            
            with open(metadata_file) as f:
                metadatos = json.load(f)
            
            # Procesar cada documento
            pipeline = PipelineIngestion()
            resultados = []
            
            for num_doc, metadata in metadatos.get('metadatos', {}).items():
                pdf_path = Path(metadata['archivo_local'])
                
                if not pdf_path.exists():
                    print(f"\n⚠ PDF no encontrado: {pdf_path}")
                    continue
                
                print(f"\n{'─'*80}")
                resultado = pipeline.procesar_documento(pdf_path, metadata)
                resultados.append(resultado)
            
            # Estadísticas
            exitosos = [r for r in resultados if r['exito']]
            fallidos = [r for r in resultados if not r['exito']]
            
            print("\n" + "="*80)
            print("RESUMEN DE PROCESAMIENTO")
            print("="*80)
            print(f"\n📊 Estadísticas:")
            print(f"  • Total procesados: {len(resultados)}")
            print(f"  • ✓ Exitosos: {len(exitosos)}")
            print(f"  • ✗ Fallidos: {len(fallidos)}")
            
            if exitosos:
                total_articulos = sum(r['num_articulos'] for r in exitosos)
                print(f"  • 📄 Total artículos cargados: {total_articulos}")
                
                print(f"\n✓ Documentos procesados exitosamente:")
                for r in exitosos:
                    metadata = r['metadata']
                    print(f"  • {metadata['pais']}: {metadata['numero_documento']}")
                    print(f"    → {r['num_articulos']} artículos, {r['num_paginas']} páginas")
            
            if fallidos:
                print(f"\n✗ Documentos fallidos:")
                for r in fallidos:
                    metadata = r['metadata']
                    print(f"  • {metadata['pais']}: {metadata['numero_documento']}")
                    print(f"    Errores: {', '.join(r['errores'])}")
            
            self.resultados['pasos_completados'].append('procesar_documentos')
            self.resultados['estadisticas']['procesamiento'] = {
                'total': len(resultados),
                'exitosos': len(exitosos),
                'fallidos': len(fallidos),
                'total_articulos': sum(r.get('num_articulos', 0) for r in exitosos)
            }
            
            if len(exitosos) == 0:
                raise Exception("No se pudo procesar ningún documento")
            
            print("\n✅ Documentos procesados y cargados")
            return True
            
        except Exception as e:
            error_msg = f"Error procesando documentos: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.resultados['errores'].append(error_msg)
            import traceback
            traceback.print_exc()
            return False
    
    def paso_4_verificar_datos(self) -> bool:
        """Paso 4: Verificar que los datos se cargaron correctamente"""
        print("\n" + "="*80)
        print("PASO 4: VERIFICAR DATOS CARGADOS")
        print("="*80)
        
        try:
            from database.models import DocumentoNormativo, ArticuloNormativo
            from sqlalchemy import func
            
            with DatabaseEngine.get_session() as session:
                # Contar documentos
                num_docs = session.query(func.count(DocumentoNormativo.id)).scalar()
                print(f"\n📄 Documentos en BD: {num_docs}")
                
                # Contar artículos
                num_arts = session.query(func.count(ArticuloNormativo.id)).scalar()
                print(f"📑 Artículos en BD: {num_arts}")
                
                # Documentos por país
                print(f"\n📊 Distribución por país:")
                from database.models import Pais
                paises = session.query(Pais).all()
                
                for pais in paises:
                    docs_pais = session.query(func.count(DocumentoNormativo.id)).filter(
                        DocumentoNormativo.pais_id == pais.id
                    ).scalar()
                    
                    arts_pais = session.query(func.count(ArticuloNormativo.id)).join(
                        DocumentoNormativo
                    ).filter(
                        DocumentoNormativo.pais_id == pais.id
                    ).scalar()
                    
                    print(f"  • {pais.nombre} ({pais.codigo_iso}):")
                    print(f"    - Documentos: {docs_pais}")
                    print(f"    - Artículos: {arts_pais}")
                
                self.resultados['estadisticas']['verificacion'] = {
                    'documentos': num_docs,
                    'articulos': num_arts
                }
            
            if num_docs == 0:
                raise Exception("No hay documentos en la base de datos")
            
            print("\n✅ Datos verificados")
            return True
            
        except Exception as e:
            error_msg = f"Error verificando datos: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.resultados['errores'].append(error_msg)
            return False
    
    def guardar_reporte(self):
        """Guardar reporte de ejecución"""
        reporte_path = self.data_dir.parent / "setup_reporte.json"
        
        with open(reporte_path, 'w', encoding='utf-8') as f:
            json.dump(self.resultados, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Reporte guardado: {reporte_path}")
    
    def ejecutar_completo(self, force_download: bool = False) -> bool:
        """Ejecutar setup completo"""
        print("\n" + "="*80)
        print("🚀 AALabelPP - SETUP COMPLETO DE DATOS")
        print("="*80)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        inicio = datetime.now()
        
        # Paso 1: Verificar BD
        if not self.paso_1_verificar_bd():
            print("\n❌ Setup cancelado: problemas con base de datos")
            return False
        
        # Paso 2: Descargar normativas
        if not self.paso_2_descargar_normativas(force=force_download):
            print("\n❌ Setup cancelado: problemas descargando normativas")
            return False
        
        # Paso 3: Procesar documentos
        if not self.paso_3_procesar_documentos():
            print("\n❌ Setup cancelado: problemas procesando documentos")
            return False
        
        # Paso 4: Verificar datos
        if not self.paso_4_verificar_datos():
            print("\n⚠ Advertencia: problemas verificando datos")
        
        # Tiempo total
        duracion = datetime.now() - inicio
        self.resultados['duracion_total_seg'] = duracion.total_seconds()
        
        # Guardar reporte
        self.guardar_reporte()
        
        # Resumen final
        print("\n" + "="*80)
        print("✅ SETUP COMPLETADO EXITOSAMENTE")
        print("="*80)
        print(f"\n⏱  Duración total: {duracion}")
        print(f"\n📊 Resumen:")
        print(f"  • Pasos completados: {len(self.resultados['pasos_completados'])}/4")
        print(f"  • Documentos cargados: {self.resultados['estadisticas'].get('verificacion', {}).get('documentos', 0)}")
        print(f"  • Artículos cargados: {self.resultados['estadisticas'].get('verificacion', {}).get('articulos', 0)}")
        
        if self.resultados['errores']:
            print(f"\n⚠ Errores encontrados: {len(self.resultados['errores'])}")
        
        print("\n🎉 Sistema listo para generar embeddings y activar RAG")
        print("\nPróximos pasos:")
        print("  1. python scripts/generate_embeddings.py")
        print("  2. python scripts/rag_pipeline.py")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Setup completo de datos para AALabelPP"
    )
    parser.add_argument(
        '--force-download',
        action='store_true',
        help='Forzar descarga de normativas incluso si ya existen'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Saltar descarga (usar normativas ya descargadas)'
    )
    
    args = parser.parse_args()
    
    setup = SetupCompleto()
    
    if args.skip_download:
        # Solo procesar documentos existentes
        print("\n⚠ Saltando descarga, procesando documentos existentes...")
        setup.paso_1_verificar_bd()
        setup.paso_3_procesar_documentos()
        setup.paso_4_verificar_datos()
        setup.guardar_reporte()
    else:
        # Setup completo
        exito = setup.ejecutar_completo(force_download=args.force_download)
        sys.exit(0 if exito else 1)


if __name__ == "__main__":
    main()
