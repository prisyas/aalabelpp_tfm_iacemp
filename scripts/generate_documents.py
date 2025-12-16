"""
AALabelPP - Generador de Documentos
Generación de PDFs para etiquetas armonizadas y análisis justificativo

Fecha: 2025-12-14
Versión: 1.0
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from io import BytesIO

# PDF Generation
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT

# Modelos
sys.path.append(str(Path(__file__).parent.parent))
from scripts.rag_engine import EtiquetaArmonizada, SeccionArmonizada


# ============================================================================
# GENERADOR DE ETIQUETA ARMONIZADA
# ============================================================================

class EtiquetaPDFGenerator:
    """Genera PDF de etiqueta armonizada"""
    
    def __init__(self, output_path: Path):
        """Inicializar generador
        
        Args:
            output_path: Ruta del PDF a generar
        """
        self.output_path = output_path
        self.doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=36
        )
        
        # Estilos
        self.styles = getSampleStyleSheet()
        self._configurar_estilos()
        
        # Contenido
        self.story = []
    
    def _configurar_estilos(self):
        """Configurar estilos personalizados"""
        # Título principal
        self.styles.add(ParagraphStyle(
            name='TituloPrincipal',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a5490'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Título sección
        self.styles.add(ParagraphStyle(
            name='TituloSeccion',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold',
            borderWidth=1,
            borderColor=colors.HexColor('#3498db'),
            borderPadding=5,
            backColor=colors.HexColor('#ecf0f1')
        ))
        
        # Contenido
        self.styles.add(ParagraphStyle(
            name='ContenidoSeccion',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=14
        ))
        
        # Metadata
        self.styles.add(ParagraphStyle(
            name='Metadata',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        ))
    
    def generar(self, etiqueta: EtiquetaArmonizada):
        """Generar PDF de etiqueta armonizada
        
        Args:
            etiqueta: Etiqueta armonizada completa
        """
        # Encabezado
        self._agregar_encabezado(etiqueta)
        
        # Metadata
        self._agregar_metadata(etiqueta)
        
        self.story.append(Spacer(1, 0.5*inch))
        
        # Secciones
        for seccion in etiqueta.secciones:
            self._agregar_seccion(seccion)
        
        # Pie de página
        self._agregar_pie_pagina(etiqueta)
        
        # Generar PDF
        self.doc.build(self.story)
        print(f"   ✓ PDF generado: {self.output_path}")
    
    def _agregar_encabezado(self, etiqueta: EtiquetaArmonizada):
        """Agregar encabezado del documento"""
        # Título
        titulo = Paragraph(
            etiqueta.nombre_producto.upper(),
            self.styles['TituloPrincipal']
        )
        self.story.append(titulo)
        
        # Subtítulo
        subtitulo = Paragraph(
            f"ETIQUETA ARMONIZADA - REGIÓN ANDINA",
            self.styles['Heading3']
        )
        self.story.append(subtitulo)
        self.story.append(Spacer(1, 0.2*inch))
    
    def _agregar_metadata(self, etiqueta: EtiquetaArmonizada):
        """Agregar metadata del documento"""
        # Tabla de metadata
        data = [
            ['Países:', ', '.join(etiqueta.paises)],
            ['Fecha de generación:', etiqueta.fecha_generacion.strftime('%Y-%m-%d %H:%M')],
            ['Secciones armonizadas:', str(len(etiqueta.secciones))],
            ['Metodología:', 'RAG + Máxima Restrictividad']
        ]
        
        tabla = Table(data, colWidths=[2*inch, 4*inch])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        self.story.append(tabla)
    
    def _agregar_seccion(self, seccion: SeccionArmonizada):
        """Agregar una sección armonizada
        
        Args:
            seccion: Sección a agregar
        """
        # Título de la sección
        titulo = Paragraph(
            f"{seccion.codigo_seccion}: {seccion.nombre_seccion.upper()}",
            self.styles['TituloSeccion']
        )
        
        # Contenido
        contenido = Paragraph(
            seccion.contenido_armonizado,
            self.styles['ContenidoSeccion']
        )
        
        # Mantener título y contenido juntos
        elementos = KeepTogether([
            titulo,
            Spacer(1, 0.1*inch),
            contenido,
            Spacer(1, 0.2*inch)
        ])
        
        self.story.append(elementos)
    
    def _agregar_pie_pagina(self, etiqueta: EtiquetaArmonizada):
        """Agregar pie de página"""
        self.story.append(Spacer(1, 0.5*inch))
        
        nota = Paragraph(
            "<i>Este documento fue generado automáticamente por AALabelPP usando "
            "Retrieval-Augmented Generation (RAG) sobre normativas oficiales de la región andina. "
            "Requiere validación por experto regulatorio antes de uso oficial.</i>",
            self.styles['Metadata']
        )
        
        self.story.append(nota)


# ============================================================================
# GENERADOR DE ANÁLISIS JUSTIFICATIVO
# ============================================================================

class AnalisisJustificativoPDFGenerator:
    """Genera PDF de análisis justificativo con trazabilidad"""
    
    def __init__(self, output_path: Path):
        """Inicializar generador
        
        Args:
            output_path: Ruta del PDF a generar
        """
        self.output_path = output_path
        self.doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=36
        )
        
        self.styles = getSampleStyleSheet()
        self._configurar_estilos()
        self.story = []
    
    def _configurar_estilos(self):
        """Configurar estilos"""
        self.styles.add(ParagraphStyle(
            name='TituloPrincipal',
            parent=self.styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#c0392b'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='SeccionAnalisis',
            parent=self.styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor('#16a085'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold'
        ))
        
        self.styles.add(ParagraphStyle(
            name='Justificacion',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
            leading=13,
            leftIndent=20,
            backColor=colors.HexColor('#f9f9f9')
        ))
    
    def generar(self, etiqueta: EtiquetaArmonizada):
        """Generar PDF de análisis justificativo
        
        Args:
            etiqueta: Etiqueta armonizada
        """
        # Portada
        self._agregar_portada(etiqueta)
        
        # Resumen ejecutivo
        self._agregar_resumen_ejecutivo(etiqueta)
        
        self.story.append(PageBreak())
        
        # Análisis por sección
        for seccion in etiqueta.secciones:
            self._agregar_analisis_seccion(seccion)
        
        # Tabla de trazabilidad
        self._agregar_tabla_trazabilidad(etiqueta)
        
        # Conclusiones
        self._agregar_conclusiones(etiqueta)
        
        # Generar PDF
        self.doc.build(self.story)
        print(f"   ✓ Análisis justificativo: {self.output_path}")
    
    def _agregar_portada(self, etiqueta: EtiquetaArmonizada):
        """Agregar portada"""
        self.story.append(Spacer(1, 2*inch))
        
        titulo = Paragraph(
            "ANÁLISIS JUSTIFICATIVO",
            self.styles['TituloPrincipal']
        )
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.3*inch))
        
        producto = Paragraph(
            f"<b>Producto:</b> {etiqueta.nombre_producto}",
            self.styles['Heading2']
        )
        self.story.append(producto)
        
        self.story.append(Spacer(1, 0.5*inch))
        
        # Info
        info_data = [
            ['Países incluidos:', ', '.join(etiqueta.paises)],
            ['Fecha de análisis:', etiqueta.fecha_generacion.strftime('%Y-%m-%d')],
            ['Metodología:', 'RAG + Máxima Restrictividad'],
            ['Sistema:', 'AALabelPP v1.0']
        ]
        
        tabla_info = Table(info_data, colWidths=[2.5*inch, 3*inch])
        tabla_info.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))
        
        self.story.append(tabla_info)
    
    def _agregar_resumen_ejecutivo(self, etiqueta: EtiquetaArmonizada):
        """Agregar resumen ejecutivo"""
        self.story.append(PageBreak())
        
        titulo = Paragraph("1. RESUMEN EJECUTIVO", self.styles['Heading2'])
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.2*inch))
        
        resumen = f"""
Este documento presenta el análisis justificativo de la armonización regulatoria 
de la etiqueta del producto <b>{etiqueta.nombre_producto}</b> para los países de la región andina: 
{', '.join(etiqueta.paises)}.

La armonización se realizó mediante un sistema de Retrieval-Augmented Generation (RAG) que:
<br/>
1. Recupera artículos normativos relevantes de las bases de datos oficiales<br/>
2. Aplica el criterio de <b>máxima restrictividad</b> cuando existen diferencias entre países<br/>
3. Genera contenido armonizado respaldado por evidencia normativa específica<br/>
<br/>
Se armonizaron <b>{len(etiqueta.secciones)} secciones</b> de la etiqueta, con trazabilidad 
completa hacia {sum(len(s.articulos_fuente) for s in etiqueta.secciones)} artículos normativos.
"""
        
        self.story.append(Paragraph(resumen, self.styles['Normal']))
    
    def _agregar_analisis_seccion(self, seccion: SeccionArmonizada):
        """Agregar análisis de una sección
        
        Args:
            seccion: Sección a analizar
        """
        # Título
        titulo = Paragraph(
            f"<b>{seccion.codigo_seccion}:</b> {seccion.nombre_seccion}",
            self.styles['SeccionAnalisis']
        )
        self.story.append(titulo)
        
        # Justificación
        if seccion.justificacion:
            just = Paragraph(
                f"<b>Justificación:</b><br/>{seccion.justificacion}",
                self.styles['Justificacion']
            )
            self.story.append(just)
        
        # Fuentes
        if seccion.articulos_fuente:
            self.story.append(Spacer(1, 0.1*inch))
            
            fuentes_data = [['País', 'Documento', 'Artículo', 'Similitud']]
            for art in seccion.articulos_fuente[:5]:  # Top 5
                fuentes_data.append([
                    art.pais,
                    art.documento,
                    art.numero_articulo,
                    f"{art.similitud:.1%}"
                ])
            
            tabla_fuentes = Table(fuentes_data, colWidths=[1.2*inch, 1.5*inch, 1*inch, 1*inch])
            tabla_fuentes.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            
            self.story.append(tabla_fuentes)
        
        self.story.append(Spacer(1, 0.2*inch))
    
    def _agregar_tabla_trazabilidad(self, etiqueta: EtiquetaArmonizada):
        """Agregar tabla completa de trazabilidad"""
        self.story.append(PageBreak())
        
        titulo = Paragraph("2. TABLA DE TRAZABILIDAD COMPLETA", self.styles['Heading2'])
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.2*inch))
        
        # Construir datos
        data = [['Sección', 'País', 'Documento', 'Artículo']]
        
        for seccion in etiqueta.secciones:
            for art in seccion.articulos_fuente:
                data.append([
                    seccion.codigo_seccion,
                    art.pais,
                    art.documento,
                    art.numero_articulo
                ])
        
        tabla = Table(data, colWidths=[1.5*inch, 1.2*inch, 1.8*inch, 1*inch])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        
        self.story.append(tabla)
    
    def _agregar_conclusiones(self, etiqueta: EtiquetaArmonizada):
        """Agregar conclusiones"""
        self.story.append(Spacer(1, 0.3*inch))
        
        titulo = Paragraph("3. CONCLUSIONES Y RECOMENDACIONES", self.styles['Heading2'])
        self.story.append(titulo)
        self.story.append(Spacer(1, 0.2*inch))
        
        conclusiones = f"""
<b>Conclusiones principales:</b><br/><br/>

1. Se logró la armonización de {len(etiqueta.secciones)} secciones de la etiqueta del producto 
{etiqueta.nombre_producto} aplicando el criterio de máxima restrictividad.<br/><br/>

2. Todas las decisiones de armonización están respaldadas por evidencia normativa específica, 
con trazabilidad completa hacia artículos oficiales de {', '.join(etiqueta.paises)}.<br/><br/>

3. El sistema RAG identificó y recuperó artículos relevantes con alta precisión semántica, 
garantizando la aplicabilidad de los requisitos.<br/><br/>

<b>Recomendaciones:</b><br/><br/>

• Este documento requiere <b>validación por experto regulatorio</b> antes de uso oficial.<br/>
• Se recomienda revisión especial de secciones con requisitos altamente divergentes entre países.<br/>
• Mantener actualizada la base de conocimiento normativo para reflejar cambios regulatorios.<br/>
"""
        
        self.story.append(Paragraph(conclusiones, self.styles['Normal']))


# ============================================================================
# EXPORTADOR COMPLETO
# ============================================================================

class DocumentExporter:
    """Exportador completo de documentos"""
    
    @staticmethod
    def exportar_completo(
        etiqueta: EtiquetaArmonizada,
        output_dir: Path
    ) -> Dict[str, Path]:
        """Exportar etiqueta y análisis justificativo
        
        Args:
            etiqueta: Etiqueta armonizada
            output_dir: Directorio de salida
            
        Returns:
            Diccionario con rutas de archivos generados
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Nombres de archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_base = etiqueta.nombre_producto.replace(' ', '_').lower()
        
        etiqueta_path = output_dir / f"{nombre_base}_armonizada_{timestamp}.pdf"
        analisis_path = output_dir / f"{nombre_base}_analisis_{timestamp}.pdf"
        
        print(f"\n📄 Generando documentos...")
        
        # Generar etiqueta
        gen_etiqueta = EtiquetaPDFGenerator(etiqueta_path)
        gen_etiqueta.generar(etiqueta)
        
        # Generar análisis
        gen_analisis = AnalisisJustificativoPDFGenerator(analisis_path)
        gen_analisis.generar(etiqueta)
        
        print(f"\n✅ Documentos generados exitosamente")
        
        return {
            'etiqueta': etiqueta_path,
            'analisis': analisis_path
        }


# ============================================================================
# CLI
# ============================================================================

def main():
    print("Generador de documentos - Use desde rag_engine.py")


if __name__ == "__main__":
    main()
