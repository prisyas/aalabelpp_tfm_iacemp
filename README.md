# 🏥 AALabelPP - Automated Andean Labeling using RAG

## Automatización para la Armonización de Etiquetado de Productos Farmacéuticos

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL 14+](https://img.shields.io/badge/postgresql-14+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 **DESCRIPCIÓN**

**AALabelPP** es un sistema inteligente basado en **Retrieval-Augmented Generation (RAG)** diseñado para automatizar la armonización de etiquetado de productos farmacéuticos para la región andina (Colombia, Ecuador, Perú y Bolivia).

El sistema utiliza modelos de lenguaje avanzados combinados con búsqueda semántica sobre normativas oficiales para generar:

✅ **Etiquetas armonizadas** que cumplen con los requisitos de los 4 países (Ecuador, Colombia, Perú y Bolivia - Zona Andina) 
✅ **Análisis justificativos** con citación explícita de fuentes normativas  
✅ **Trazabilidad completa** de decisiones y evidencia regulatoria  

---

## 🎯 **CARACTERÍSTICAS PRINCIPALES**

### **1. Enfoque RAG (Retrieval-Augmented Generation)**
- Recuperación semántica de artículos normativos relevantes
- Generación condicionada sobre evidencia verificable
- Mitigación de alucinaciones mediante anclaje en fuentes oficiales

### **2. Multi-País**
- Soporte simultáneo para 4 países andinos
- Base de conocimiento normativo estructurada
- Armonización basada en criterio de máxima restrictividad

### **3. Búsqueda Vectorial**
- Indexación mediante `pgvector` (PostgreSQL)
- Algoritmo HNSW para búsqueda ultra-rápida
- Soporte para múltiples modelos de embeddings

### **4. Validación Humana**
- Flujo con aprobación obligatoria de expertos
- Interfaz para revisión y ajustes
- Control de calidad multi-nivel


## 🏗️ **ARQUITECTURA**


┌──────────────────────────────────────────────────────────┐
│                    INTERFAZ USUARIO                       │
│            (Carga PDF → Recibe PDFs armonizados)         │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│              PIPELINE DE PROCESAMIENTO                    │
│  ┌────────┐  ┌──────────┐  ┌─────────┐  ┌────────────┐ │
│  │Ingesta │→ │Segmenta- │→ │Consulta │→ │ Generación │ │
│  │  PDF   │  │   ción   │  │   RAG   │  │   Docs     │ │
│  └────────┘  └──────────┘  └─────────┘  └────────────┘ │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│              MOTOR RAG (NÚCLEO INTELIGENTE)              │
│  ┌──────────────────┐       ┌────────────────────────┐  │
│  │   Recuperación   │  ←──→ │    Base Vectorial      │  │
│  │   Semántica      │       │  (FAISS/Chroma/pgv)    │  │
│  └────────┬─────────┘       └────────────────────────┘  │
│           │                                               │
│           v                                               │
│  ┌──────────────────┐       ┌────────────────────────┐  │
│  │   Generación     │  ←──→ │    LLM (Gemini/GPT)    │  │
│  │  Condicionada    │       │                        │  │
│  └──────────────────┘       └────────────────────────┘  │
└───────────────────────┬──────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────────────────┐
│         BASE DE CONOCIMIENTO NORMATIVO                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  PostgreSQL 14+ con pgvector                       │  │
│  │  • 4 países (CO, EC, PE, BO)                      │  │
│  │  • Decretos, resoluciones, acuerdos               │  │
│  │  • Artículos segmentados                          │  │
│  │  • Embeddings vectoriales indexados               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 📂 **ESTRUCTURA DEL PROYECTO**

```
aalabelpp_proyecto/
│
├── database/                  # Base de datos
│   ├── schema.sql            # Esquema SQL completo
│   ├── models.py             # Modelos SQLAlchemy
│   └── db_config.py          # Configuración y conexión
│
├── scripts/                   # Scripts de procesamiento
│   ├── ingest_pdf.py         # Ingesta de PDFs
│   ├── segment.py            # Segmentación de texto
│   ├── generate_embeddings.py # Generación de embeddings
│   └── rag_pipeline.py       # Pipeline completo RAG
│
├── data/                      # Datos y documentos
│   ├── normativas/           # PDFs de normativas
│   ├── uploads/              # Etiquetas de entrada
│   └── outputs/              # Etiquetas armonizadas
│
├── docs/                      # Documentación
│   ├── DATABASE.md           # Documentación de BD
│   ├── API.md                # Documentación de API
│   └── DEPLOYMENT.md         # Guía de despliegue
│
├── tests/                     # Tests unitarios
│   ├── test_database.py
│   ├── test_rag.py
│   └── test_pipeline.py
│
├── requirements.txt           # Dependencias Python
├── .env.example              # Variables de entorno (ejemplo)
├── README.md                 # Este archivo
└── LICENSE                   # Licencia del proyecto
```

---

## ⚙️ **INSTALACIÓN**

### **Prerrequisitos:**

- Python 3.10+
- PostgreSQL 16+ con extensión `pgvector`
- Tesseract OCR (para PDFs escaneados)
- API keys: OpenAI o Google Gemini

### **Paso 1: Clonar repositorio**

```bash
git clone https://github.com/prisyas/aalabelpp_tfm_iacemp.git
cd aalabelpp_proyecto
```

### **Paso 2: Crear entorno virtual**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

### **Paso 3: Instalar dependencias**

```bash
pip install -r requirements.txt
```

### **Paso 4: Configurar variables de entorno**

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

Contenido de `.env`:

```env
# Base de datos
DB_HOST=localhost
DB_PORT=5432
DB_NAME=aalabelpp_db
DB_USER=postgres
DB_PASSWORD=tu_password

# API Keys
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AI...

# Configuración
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
LLM_MODEL=gpt-4
```

### **Paso 5: Setup de base de datos**

```bash
cd database
python db_config.py setup
```

Esto creará automáticamente:
- Extensiones pgvector y uuid-ossp
- 8 tablas principales
- Vistas y funciones auxiliares
- Datos iniciales (países, secciones)

### **Paso 6: Verificar instalación**

```bash
python db_config.py verify
python db_config.py stats
```

---

## 🚀 **USO RÁPIDO**

### **1. Cargar normativas (primera vez)**

```bash
python scripts/load_normatives.py \
    --country CO \
    --file data/normativas/colombia_decreto_677_1995.pdf
```

### **2. Generar embeddings**

```bash
python scripts/generate_embeddings.py \
    --model sentence-transformers/all-mpnet-base-v2
```

### **3. Procesar una etiqueta**

```bash
python scripts/rag_pipeline.py \
    --input data/uploads/etiqueta_producto_x.pdf \
    --output data/outputs/ \
    --countries CO,EC,PE,BO
```

### **4. Resultados**

El sistema genera:
- `etiqueta_armonizada.pdf` - Etiqueta final en español
- `analisis_justificativo.pdf` - Análisis con citas normativas

---

## 📊 **MÉTRICAS Y KPIS**

El sistema implementa 16 KPIs organizados en 4 categorías:

### **Técnicos:**
- Precisión de segmentación: ≥90%
- Relevancia de evidencia (P@5): ≥0.80
- Tasa de éxito sin errores: ≥98%
- Tiempo de procesamiento: ≤5 min

### **Calidad:**
- Concordancia con checklists: ≥95%
- Errores factuales: ≤0.5 por etiqueta
- Trazabilidad: 100%
- Claridad (Flesch-Kincaid): 50-60

### **Adopción:**
- Tasa de adopción: ≥80% en 6 meses
- Satisfacción de usuarios: ≥4.0/5.0
- Tiempo de validación: ≤4 horas
- Retrabajo mayor: ≤10%

### **Impacto:**
- Reducción de tiempo: ≥50%
- Capacidad de procesamiento: +40%
- Time-to-market: -20%
- Observaciones regulatorias: -30%

---

## 🧪 **TESTING**

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=aalabelpp tests/

# Tests específicos
pytest tests/test_database.py
pytest tests/test_rag.py
```

---

## 📄 **LICENCIA**

Este repositorio contiene software y contenido propietario. Todo el contneido y código fuente es propietarrio de Priscila Andrade. 
Queda estrictamente prohibido la copia, distribución, modificación, ingeniería inversa o cualquier uso no autorizado de este proyecto, ya sea de forma total o porcial, sin el consertimiento previo y por escrito de la autora.
Todos los derechos reservados.
Copyrigth © 2025 Priscila Andrade.
---

## ✨ **CRÉDITOS**

**Proyecto académico de Maestría**  
Universidad: Centro Europeo de Másteres y Posgrados - CEMP. Univerisidad  
Programa: Maestría en Desarrollo de Aplicaciones de Inteligencia Artificial en Sanidad.
Autor: Priscila Andrade  
Año: 2025

**Tecnologías principales:**
- PostgreSQL + pgvector
- LangChain / LlamaIndex
- OpenAI GPT-4 / Google Gemini

---

## 📧 **CONTACTO**

Para preguntas, sugerencias o colaboraciones:

- Email: prisyandrade@hotmai.com
- LinkedIn: linkedin.com/in/priscilasilvanaandrade
- GitHub:https://github.com/prisyas

---

## ⚠️ **DISCLAIMER**

Este sistema es una **herramienta de asistencia** que requiere validación humana obligatoria. La responsabilidad final sobre el cumplimiento regulatorio recae en profesionales calificados, no en el sistema automatizado.

**No debe usarse como:**
- Sistema de aprobación automática de etiquetas
- Reemplazo de expertos regulatorios
- Fuente única de interpretación normativa

---

