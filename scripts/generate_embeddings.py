"""
AALabelPP - Generación de Embeddings Vectoriales
Vectorización de artículos normativos para búsqueda semántica RAG

Fecha: 2025-12-14
Versión: 1.0
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from tqdm import tqdm

# ML/NLP
import torch
from sentence_transformers import SentenceTransformer

# Database
sys.path.append(str(Path(__file__).parent.parent))
from database.db_config import get_db_session, DatabaseEngine
from database.models import ArticuloNormativo, EmbeddingVectorial, DocumentoNormativo

# ============================================================================
# CONFIGURACIÓN DE MODELOS
# ============================================================================

MODELOS_DISPONIBLES = {
    'multilingual-mpnet': {
        'nombre': 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2',
        'dimension': 768,
        'descripcion': 'Multilingüe, balanceado calidad/velocidad',
        'velocidad': 'media',
        'calidad': 'alta',
        'recomendado': True
    },
    'multilingual-minilm': {
        'nombre': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
        'dimension': 384,
        'descripcion': 'Multilingüe, rápido, liviano',
        'velocidad': 'rápida',
        'calidad': 'media',
        'recomendado': False
    },
    'spanish-roberta': {
        'nombre': 'hiiamsid/sentence_similarity_spanish_es',
        'dimension': 768,
        'descripcion': 'Especializado en español',
        'velocidad': 'media',
        'calidad': 'alta',
        'recomendado': True
    },
    'labse': {
        'nombre': 'sentence-transformers/LaBSE',
        'dimension': 768,
        'descripcion': 'Language-agnostic BERT, 109 idiomas',
        'velocidad': 'lenta',
        'calidad': 'muy alta',
        'recomendado': False
    }
}

# Modelo por defecto
MODELO_DEFAULT = 'multilingual-mpnet'


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class EmbeddingGenerado:
    """Resultado de generación de embedding"""
    articulo_id: int
    embedding: np.ndarray
    tiempo_generacion: float
    modelo: str
    dimension: int


# ============================================================================
# GENERADOR DE EMBEDDINGS
# ============================================================================

class EmbeddingGenerator:
    """Generador de embeddings con múltiples modelos"""
    
    def __init__(self, modelo_nombre: str = MODELO_DEFAULT):
        """Inicializar generador
        
        Args:
            modelo_nombre: Clave del modelo en MODELOS_DISPONIBLES
        """
        if modelo_nombre not in MODELOS_DISPONIBLES:
            raise ValueError(f"Modelo no reconocido: {modelo_nombre}")
        
        self.modelo_config = MODELOS_DISPONIBLES[modelo_nombre]
        self.modelo_nombre = modelo_nombre
        self.modelo_path = self.modelo_config['nombre']
        self.dimension = self.modelo_config['dimension']
        
        print(f"\n🤖 Cargando modelo: {self.modelo_path}")
        print(f"   Dimensión: {self.dimension}")
        print(f"   Descripción: {self.modelo_config['descripcion']}")
        
        # Detectar dispositivo (GPU si está disponible)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"   Dispositivo: {self.device.upper()}")
        
        # Cargar modelo
        self.modelo = SentenceTransformer(
            self.modelo_path,
            device=self.device
        )
        
        print(f"   ✓ Modelo cargado exitosamente")
    
    def generar_embedding(self, texto: str) -> np.ndarray:
        """Generar embedding para un texto
        
        Args:
            texto: Texto a vectorizar
            
        Returns:
            Vector numpy de embeddings
        """
        # Normalizar texto (limitar longitud)
        max_length = 512  # Tokens máximos
        texto = texto[:max_length * 4]  # Aproximado (4 chars = 1 token)
        
        # Generar embedding
        embedding = self.modelo.encode(
            texto,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True  # L2 normalization
        )
        
        return embedding
    
    def generar_batch(self, textos: List[str], batch_size: int = 32) -> List[np.ndarray]:
        """Generar embeddings por lotes (más eficiente)
        
        Args:
            textos: Lista de textos
            batch_size: Tamaño del lote
            
        Returns:
            Lista de embeddings
        """
        embeddings = self.modelo.encode(
            textos,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=True,
            normalize_embeddings=True
        )
        
        return embeddings


# ============================================================================
# PROCESADOR DE ARTÍCULOS
# ============================================================================

class ArticulosEmbedder:
    """Procesa artículos y genera embeddings"""
    
    def __init__(self, modelo_nombre: str = MODELO_DEFAULT):
        self.generator = EmbeddingGenerator(modelo_nombre)
        self.estadisticas = {
            'total_procesados': 0,
            'nuevos': 0,
            'actualizados': 0,
            'errores': 0,
            'tiempo_total': 0
        }
    
    def obtener_articulos_pendientes(
        self,
        solo_sin_embeddings: bool = True,
        limite: Optional[int] = None
    ) -> List[ArticuloNormativo]:
        """Obtener artículos que necesitan embeddings
        
        Args:
            solo_sin_embeddings: Solo artículos sin embeddings del modelo actual
            limite: Límite de artículos (None = todos)
            
        Returns:
            Lista de artículos
        """
        with get_db_session() as session:
            query = session.query(ArticuloNormativo)
            
            if solo_sin_embeddings:
                # Subconsulta: artículos que ya tienen embedding de este modelo
                from sqlalchemy import exists, and_
                
                subquery = session.query(EmbeddingVectorial.articulo_id).filter(
                    and_(
                        EmbeddingVectorial.articulo_id == ArticuloNormativo.id,
                        EmbeddingVectorial.modelo_embedding == self.generator.modelo_path
                    )
                )
                
                # Filtrar artículos sin embedding
                query = query.filter(~exists(subquery))
            
            if limite:
                query = query.limit(limite)
            
            articulos = query.all()
            
            # Desconectar de la sesión para evitar lazy loading issues
            for art in articulos:
                session.expunge(art)
            
            return articulos
    
    def procesar_articulo(
        self,
        articulo: ArticuloNormativo,
        actualizar_existente: bool = False
    ) -> Optional[EmbeddingGenerado]:
        """Procesar un artículo individual
        
        Args:
            articulo: Artículo a procesar
            actualizar_existente: Si True, actualiza embedding existente
            
        Returns:
            EmbeddingGenerado o None si falla
        """
        inicio = datetime.now()
        
        try:
            # Usar texto normalizado si existe, sino completo
            texto = articulo.texto_normalizado or articulo.texto_completo
            
            if not texto or len(texto.strip()) < 10:
                print(f"⚠ Artículo {articulo.id}: Texto insuficiente")
                return None
            
            # Generar embedding
            embedding = self.generator.generar_embedding(texto)
            
            tiempo = (datetime.now() - inicio).total_seconds()
            
            return EmbeddingGenerado(
                articulo_id=articulo.id,
                embedding=embedding,
                tiempo_generacion=tiempo,
                modelo=self.generator.modelo_path,
                dimension=len(embedding)
            )
            
        except Exception as e:
            print(f"✗ Error procesando artículo {articulo.id}: {str(e)}")
            self.estadisticas['errores'] += 1
            return None
    
    def guardar_embeddings(
        self,
        embeddings: List[EmbeddingGenerado],
        actualizar_existente: bool = False
    ):
        """Guardar embeddings en la base de datos
        
        Args:
            embeddings: Lista de embeddings generados
            actualizar_existente: Si True, actualiza existentes
        """
        with get_db_session() as session:
            for emb in embeddings:
                # Verificar si existe
                existente = session.query(EmbeddingVectorial).filter(
                    EmbeddingVectorial.articulo_id == emb.articulo_id,
                    EmbeddingVectorial.modelo_embedding == emb.modelo
                ).first()
                
                if existente:
                    if actualizar_existente:
                        existente.embedding = emb.embedding.tolist()
                        existente.fecha_generacion = datetime.utcnow()
                        existente.dimension_vector = emb.dimension
                        self.estadisticas['actualizados'] += 1
                    else:
                        continue  # Saltar
                else:
                    # Crear nuevo
                    nuevo = EmbeddingVectorial(
                        articulo_id=emb.articulo_id,
                        modelo_embedding=emb.modelo,
                        dimension_vector=emb.dimension,
                        embedding=emb.embedding.tolist(),
                        fecha_generacion=datetime.utcnow(),
                        confianza_embedding=1.0
                    )
                    session.add(nuevo)
                    self.estadisticas['nuevos'] += 1
            
            session.commit()
    
    def procesar_todos(
        self,
        batch_size: int = 32,
        guardar_cada: int = 100,
        limite: Optional[int] = None
    ):
        """Procesar todos los artículos pendientes
        
        Args:
            batch_size: Tamaño de lote para procesamiento
            guardar_cada: Guardar cada N artículos
            limite: Límite de artículos a procesar
        """
        print("\n" + "="*80)
        print("GENERACIÓN DE EMBEDDINGS - INICIO")
        print("="*80)
        
        inicio_total = datetime.now()
        
        # Obtener artículos pendientes
        print("\n📊 Obteniendo artículos pendientes...")
        articulos = self.obtener_articulos_pendientes(
            solo_sin_embeddings=True,
            limite=limite
        )
        
        if not articulos:
            print("✓ Todos los artículos ya tienen embeddings")
            return
        
        print(f"   Artículos a procesar: {len(articulos)}")
        print(f"   Modelo: {self.generator.modelo_nombre}")
        print(f"   Dimensión: {self.generator.dimension}")
        
        # Procesar por lotes
        embeddings_pendientes = []
        
        print("\n🔄 Generando embeddings...")
        
        with tqdm(total=len(articulos), desc="Procesando") as pbar:
            batch_textos = []
            batch_articulos = []
            
            for i, articulo in enumerate(articulos):
                texto = articulo.texto_normalizado or articulo.texto_completo
                
                if texto and len(texto.strip()) >= 10:
                    batch_textos.append(texto)
                    batch_articulos.append(articulo)
                
                # Procesar batch cuando está lleno
                if len(batch_textos) >= batch_size or i == len(articulos) - 1:
                    if batch_textos:
                        # Generar embeddings del batch
                        embeddings = self.generator.generar_batch(
                            batch_textos,
                            batch_size=batch_size
                        )
                        
                        # Crear objetos EmbeddingGenerado
                        for art, emb in zip(batch_articulos, embeddings):
                            embeddings_pendientes.append(
                                EmbeddingGenerado(
                                    articulo_id=art.id,
                                    embedding=emb,
                                    tiempo_generacion=0.0,
                                    modelo=self.generator.modelo_path,
                                    dimension=len(emb)
                                )
                            )
                        
                        # Guardar si alcanzamos el límite
                        if len(embeddings_pendientes) >= guardar_cada:
                            self.guardar_embeddings(embeddings_pendientes)
                            embeddings_pendientes = []
                        
                        batch_textos = []
                        batch_articulos = []
                
                pbar.update(1)
                self.estadisticas['total_procesados'] += 1
        
        # Guardar embeddings restantes
        if embeddings_pendientes:
            print("\n💾 Guardando embeddings finales...")
            self.guardar_embeddings(embeddings_pendientes)
        
        # Estadísticas finales
        tiempo_total = (datetime.now() - inicio_total).total_seconds()
        self.estadisticas['tiempo_total'] = tiempo_total
        
        self.imprimir_estadisticas()
    
    def imprimir_estadisticas(self):
        """Imprimir estadísticas de procesamiento"""
        print("\n" + "="*80)
        print("ESTADÍSTICAS DE GENERACIÓN")
        print("="*80)
        
        stats = self.estadisticas
        
        print(f"\n📊 Resumen:")
        print(f"   • Total procesados: {stats['total_procesados']}")
        print(f"   • Nuevos embeddings: {stats['nuevos']}")
        print(f"   • Actualizados: {stats['actualizados']}")
        print(f"   • Errores: {stats['errores']}")
        print(f"   • Tiempo total: {stats['tiempo_total']:.2f} segundos")
        
        if stats['total_procesados'] > 0:
            promedio = stats['tiempo_total'] / stats['total_procesados']
            print(f"   • Tiempo promedio: {promedio:.3f} seg/artículo")
            print(f"   • Velocidad: {1/promedio:.1f} artículos/seg")


# ============================================================================
# VERIFICADOR DE EMBEDDINGS
# ============================================================================

class EmbeddingsVerificador:
    """Verifica calidad y completitud de embeddings"""
    
    @staticmethod
    def verificar_cobertura() -> Dict:
        """Verificar cobertura de embeddings"""
        with get_db_session() as session:
            from sqlalchemy import func
            
            # Total de artículos
            total_articulos = session.query(
                func.count(ArticuloNormativo.id)
            ).scalar()
            
            # Artículos con embeddings
            total_embeddings = session.query(
                func.count(EmbeddingVectorial.id.distinct())
            ).scalar()
            
            # Por modelo
            por_modelo = session.query(
                EmbeddingVectorial.modelo_embedding,
                func.count(EmbeddingVectorial.id)
            ).group_by(EmbeddingVectorial.modelo_embedding).all()
            
            cobertura = {
                'total_articulos': total_articulos,
                'total_embeddings': total_embeddings,
                'cobertura_pct': (total_embeddings / total_articulos * 100) if total_articulos > 0 else 0,
                'por_modelo': dict(por_modelo)
            }
            
            return cobertura
    
    @staticmethod
    def imprimir_reporte():
        """Imprimir reporte de cobertura"""
        print("\n" + "="*80)
        print("REPORTE DE EMBEDDINGS")
        print("="*80)
        
        cobertura = EmbeddingsVerificador.verificar_cobertura()
        
        print(f"\n📊 Cobertura General:")
        print(f"   • Total de artículos: {cobertura['total_articulos']}")
        print(f"   • Artículos con embeddings: {cobertura['total_embeddings']}")
        print(f"   • Cobertura: {cobertura['cobertura_pct']:.1f}%")
        
        if cobertura['por_modelo']:
            print(f"\n🤖 Por Modelo:")
            for modelo, count in cobertura['por_modelo'].items():
                modelo_short = modelo.split('/')[-1]
                print(f"   • {modelo_short}: {count} embeddings")
        
        # Estadísticas de dimensiones
        with get_db_session() as session:
            dimensiones = session.query(
                EmbeddingVectorial.dimension_vector,
                func.count(EmbeddingVectorial.id)
            ).group_by(EmbeddingVectorial.dimension_vector).all()
            
            if dimensiones:
                print(f"\n📐 Dimensiones:")
                for dim, count in dimensiones:
                    print(f"   • {dim}D: {count} embeddings")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generar embeddings vectoriales para artículos normativos"
    )
    parser.add_argument(
        '--modelo',
        default=MODELO_DEFAULT,
        choices=list(MODELOS_DISPONIBLES.keys()),
        help='Modelo de embeddings a utilizar'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=32,
        help='Tamaño de lote para procesamiento'
    )
    parser.add_argument(
        '--limite',
        type=int,
        help='Límite de artículos a procesar'
    )
    parser.add_argument(
        '--actualizar',
        action='store_true',
        help='Actualizar embeddings existentes'
    )
    parser.add_argument(
        '--verificar',
        action='store_true',
        help='Solo verificar cobertura de embeddings'
    )
    parser.add_argument(
        '--listar-modelos',
        action='store_true',
        help='Listar modelos disponibles'
    )
    
    args = parser.parse_args()
    
    # Listar modelos
    if args.listar_modelos:
        print("\n" + "="*80)
        print("MODELOS DISPONIBLES")
        print("="*80)
        for key, config in MODELOS_DISPONIBLES.items():
            recomendado = " ⭐ RECOMENDADO" if config['recomendado'] else ""
            print(f"\n🤖 {key}{recomendado}")
            print(f"   Nombre: {config['nombre']}")
            print(f"   Dimensión: {config['dimension']}")
            print(f"   Velocidad: {config['velocidad']}")
            print(f"   Calidad: {config['calidad']}")
            print(f"   Descripción: {config['descripcion']}")
        return
    
    # Verificar cobertura
    if args.verificar:
        EmbeddingsVerificador.imprimir_reporte()
        return
    
    # Generar embeddings
    try:
        # Inicializar BD
        DatabaseEngine.initialize()
        
        # Crear processor
        processor = ArticulosEmbedder(modelo_nombre=args.modelo)
        
        # Procesar artículos
        processor.procesar_todos(
            batch_size=args.batch_size,
            limite=args.limite
        )
        
        # Verificar resultados
        print("\n")
        EmbeddingsVerificador.imprimir_reporte()
        
        print("\n" + "="*80)
        print("✅ GENERACIÓN DE EMBEDDINGS COMPLETADA")
        print("="*80)
        print("\n🚀 Próximo paso: python scripts/rag_engine.py")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
