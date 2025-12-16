#!/usr/bin/env python3
"""
AALabelPP - Pipeline Completo End-to-End
Procesamiento completo de armonización de etiquetas farmacéuticas

Fecha: 2025-12-14
Versión: 1.0
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import json

# Módulos del proyecto
sys.path.append(str(Path(__file__).parent.parent))

from database.db_config import DatabaseEngine
from scripts.rag_engine import RAGEngine, EtiquetaArmonizada
from scripts.generate_documents import DocumentExporter


# ============================================================================
# PIPELINE MAESTRO
# ============================================================================

class AALabelPPPipeline:
    """Pipeline completo de procesamiento"""
    
    def __init__(
        self,
        modelo_embedding: str = 'multilingual-mpnet',
        modelo_llm: str = 'gpt-4',
        output_dir: Optional[Path] = None
    ):
        """Inicializar pipeline
        
        Args:
            modelo_embedding: Modelo para embeddings
            modelo_llm: Modelo LLM para generación
            output_dir: Directorio de salida (default: data/outputs)
        """
        self.modelo_embedding = modelo_embedding
        self.modelo_llm = modelo_llm
        
        if output_dir is None:
            self.output_dir = Path(__file__).parent.parent / "data" / "outputs"
        else:
            self.output_dir = output_dir
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar componentes
        print("\n" + "="*80)
        print("AALabelPP - INICIALIZANDO SISTEMA")
        print("="*80)
        
        DatabaseEngine.initialize()
        
        self.rag_engine = RAGEngine(
            modelo_embedding=modelo_embedding,
            modelo_llm=modelo_llm
        )
        
        print(f"\n✅ Sistema inicializado")
        print(f"   Directorio de salida: {self.output_dir}")
    
    def procesar_producto(
        self,
        nombre_producto: str,
        paises: List[str],
        secciones: Optional[List[str]] = None
    ) -> Dict:
        """Procesar un producto completo
        
        Args:
            nombre_producto: Nombre del producto
            paises: Códigos ISO de países
            secciones: Secciones a armonizar (None = todas)
            
        Returns:
            Diccionario con resultados
        """
        inicio = datetime.now()
        
        print("\n" + "="*80)
        print(f"PROCESANDO PRODUCTO: {nombre_producto}")
        print("="*80)
        print(f"\nPaíses: {', '.join(paises)}")
        
        if secciones:
            print(f"Secciones: {', '.join(secciones)}")
        else:
            print(f"Secciones: Todas las disponibles")
        
        try:
            # 1. ARMONIZACIÓN (RAG)
            print("\n📝 FASE 1: Armonización RAG")
            print("-" * 80)
            
            etiqueta = self.rag_engine.armonizar_etiqueta_completa(
                nombre_producto=nombre_producto,
                paises=paises,
                secciones=secciones
            )
            
            # 2. GENERACIÓN DE DOCUMENTOS
            print("\n📄 FASE 2: Generación de Documentos")
            print("-" * 80)
            
            archivos = DocumentExporter.exportar_completo(
                etiqueta=etiqueta,
                output_dir=self.output_dir
            )
            
            # 3. RESULTADOS
            duracion = (datetime.now() - inicio).total_seconds()
            
            resultado = {
                'exito': True,
                'producto': nombre_producto,
                'paises': paises,
                'secciones_procesadas': len(etiqueta.secciones),
                'duracion_segundos': duracion,
                'archivos_generados': {
                    'etiqueta': str(archivos['etiqueta']),
                    'analisis': str(archivos['analisis'])
                },
                'metadata': etiqueta.metadata
            }
            
            # Guardar metadata JSON
            self._guardar_metadata(resultado)
            
            self._imprimir_resumen(resultado)
            
            return resultado
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                'exito': False,
                'error': str(e),
                'producto': nombre_producto
            }
    
    def _guardar_metadata(self, resultado: Dict):
        """Guardar metadata del procesamiento"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_base = resultado['producto'].replace(' ', '_').lower()
        metadata_path = self.output_dir / f"{nombre_base}_metadata_{timestamp}.json"
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)
        
        print(f"   ✓ Metadata: {metadata_path}")
    
    def _imprimir_resumen(self, resultado: Dict):
        """Imprimir resumen de procesamiento"""
        print("\n" + "="*80)
        print("✅ PROCESAMIENTO COMPLETADO")
        print("="*80)
        
        print(f"\n📊 Resumen:")
        print(f"   • Producto: {resultado['producto']}")
        print(f"   • Países: {', '.join(resultado['paises'])}")
        print(f"   • Secciones procesadas: {resultado['secciones_procesadas']}")
        print(f"   • Duración: {resultado['duracion_segundos']:.1f} segundos")
        
        print(f"\n📁 Archivos generados:")
        print(f"   • Etiqueta armonizada: {Path(resultado['archivos_generados']['etiqueta']).name}")
        print(f"   • Análisis justificativo: {Path(resultado['archivos_generados']['analisis']).name}")
        
        print(f"\n📂 Ubicación: {self.output_dir}")
    
    def procesar_lote(
        self,
        productos: List[Dict],
        continuar_en_error: bool = True
    ) -> List[Dict]:
        """Procesar múltiples productos
        
        Args:
            productos: Lista de dicts con 'nombre', 'paises', 'secciones'
            continuar_en_error: Continuar si un producto falla
            
        Returns:
            Lista de resultados
        """
        print("\n" + "="*80)
        print(f"PROCESAMIENTO EN LOTE: {len(productos)} productos")
        print("="*80)
        
        resultados = []
        
        for i, producto_info in enumerate(productos, 1):
            print(f"\n[{i}/{len(productos)}]")
            
            try:
                resultado = self.procesar_producto(
                    nombre_producto=producto_info['nombre'],
                    paises=producto_info.get('paises', ['CO', 'EC', 'PE', 'BO']),
                    secciones=producto_info.get('secciones')
                )
                resultados.append(resultado)
                
            except Exception as e:
                print(f"\n❌ Error en producto {producto_info['nombre']}: {str(e)}")
                resultados.append({
                    'exito': False,
                    'producto': producto_info['nombre'],
                    'error': str(e)
                })
                
                if not continuar_en_error:
                    break
        
        # Resumen del lote
        exitosos = sum(1 for r in resultados if r['exito'])
        
        print("\n" + "="*80)
        print("RESUMEN DEL LOTE")
        print("="*80)
        print(f"\n✓ Exitosos: {exitosos}/{len(productos)}")
        print(f"✗ Fallidos: {len(productos) - exitosos}/{len(productos)}")
        
        return resultados


# ============================================================================
# CASOS DE PRUEBA
# ============================================================================

CASOS_PRUEBA = {
    'ibuprofeno': {
        'nombre': 'Ibuprofeno 400mg Tabletas',
        'paises': ['CO', 'EC', 'PE', 'BO'],
        'secciones': ['NOMBRE', 'COMPOSICION', 'INDICACIONES', 'CONTRAINDICACIONES', 'ADVERTENCIAS']
    },
    'amoxicilina': {
        'nombre': 'Amoxicilina 500mg Cápsulas',
        'paises': ['CO', 'EC'],
        'secciones': ['NOMBRE', 'COMPOSICION', 'INDICACIONES', 'POSOLOGIA']
    },
    'paracetamol': {
        'nombre': 'Paracetamol 500mg Tabletas',
        'paises': ['CO', 'EC', 'PE', 'BO'],
        'secciones': None  # Todas las secciones
    }
}


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AALabelPP - Pipeline completo de armonización",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Procesar un producto (todas las secciones)
  python pipeline_complete.py --producto "Ibuprofeno 400mg" --paises CO,EC,PE,BO

  # Procesar secciones específicas
  python pipeline_complete.py --producto "Amoxicilina 500mg" --paises CO,EC --secciones NOMBRE,COMPOSICION,INDICACIONES

  # Ejecutar caso de prueba predefinido
  python pipeline_complete.py --test ibuprofeno

  # Procesar múltiples casos de prueba
  python pipeline_complete.py --test-all
        """
    )
    
    # Opciones de producto
    parser.add_argument(
        '--producto',
        help='Nombre del producto farmacéutico'
    )
    parser.add_argument(
        '--paises',
        default='CO,EC,PE,BO',
        help='Códigos ISO de países (separados por coma)'
    )
    parser.add_argument(
        '--secciones',
        help='Códigos de secciones (separados por coma, opcional)'
    )
    
    # Opciones de modelos
    parser.add_argument(
        '--embedding-model',
        default='multilingual-mpnet',
        choices=['multilingual-mpnet', 'multilingual-minilm', 'spanish-roberta'],
        help='Modelo de embeddings'
    )
    parser.add_argument(
        '--llm-model',
        default='gpt-4',
        help='Modelo LLM (gpt-4, gpt-3.5-turbo, gemini-pro)'
    )
    
    # Opciones de salida
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Directorio de salida personalizado'
    )
    
    # Casos de prueba
    parser.add_argument(
        '--test',
        choices=list(CASOS_PRUEBA.keys()),
        help='Ejecutar caso de prueba predefinido'
    )
    parser.add_argument(
        '--test-all',
        action='store_true',
        help='Ejecutar todos los casos de prueba'
    )
    
    args = parser.parse_args()
    
    # Validar
    if not args.producto and not args.test and not args.test_all:
        parser.error("Debe especificar --producto, --test, o --test-all")
    
    # Inicializar pipeline
    pipeline = AALabelPPPipeline(
        modelo_embedding=args.embedding_model,
        modelo_llm=args.llm_model,
        output_dir=args.output_dir
    )
    
    # Ejecutar
    if args.test:
        # Caso de prueba individual
        caso = CASOS_PRUEBA[args.test]
        pipeline.procesar_producto(
            nombre_producto=caso['nombre'],
            paises=caso['paises'],
            secciones=caso['secciones']
        )
    
    elif args.test_all:
        # Todos los casos de prueba
        productos = [
            {
                'nombre': caso['nombre'],
                'paises': caso['paises'],
                'secciones': caso['secciones']
            }
            for caso in CASOS_PRUEBA.values()
        ]
        pipeline.procesar_lote(productos)
    
    else:
        # Producto especificado manualmente
        paises = args.paises.split(',')
        secciones = args.secciones.split(',') if args.secciones else None
        
        pipeline.procesar_producto(
            nombre_producto=args.producto,
            paises=paises,
            secciones=secciones
        )


if __name__ == "__main__":
    main()
