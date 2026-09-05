# UVL_Generator - Servidor MCP para Generación y Validación de Modelos UVL

Este repositorio contiene un servidor basado en el estándar Model Context Protocol (MCP) diseñado para transformar un LLM comercial (como Claude) en un asistente de ingeniería autónomo experto en la variabilidad de software. El sistema erradica las alucinaciones estructurales conectando la IA con analizadores sintácticos y solucionadores matemáticos formales en tiempo real.

**Características principales**

* **Asimilación dinámica de gramática:** Inyección automática de la gramática oficial ANTLR4 de UVL antes de iniciar la generación.


* **Few-Shot Prompting:** Inserción de pares exactos (descripción natural - modelo UVL) para alinear el estilo arquitectónico del LLM con el diseño humano. Actualmente, se incluyen en el repositorio ejemplos de modelos UVL para proporcionar como ejemplos.


* **Validación agéntica iterativa:** Compilación y evaluación semántica mediante el framework Flamapy (motores SAT y BDD). Si hay un error, el LLM recibe el feedback y se autocorrige.


* **Persistencia segura:** Guardado automático de los archivos .uvl en disco local, pero únicamente si han superado con éxito todas las validaciones matemáticas.



---

### Instalación del Servidor Local

Se recomienda utilizar Python 3.12 para garantizar la compatibilidad con las dependencias del validador Flamapy.

1. Se debe clonar o extraer el código fuente en el entorno local y navegar hasta ese directorio en la terminal.


2. A continuación, se crea un entorno virtual aislado para las dependencias:


```bash
python -m venv venv

```


3. Se procede a activar el entorno virtual recién creado:


* **Windows:** `venv\Scripts\activate`

* **macOS / Linux:** `source venv/bin/activate`



4. Se deben instalar las dependencias requeridas del proyecto:


```bash
pip install -r requirements.txt

```


5. Finalmente, se inicia el servidor MCP localmente:


```bash
python server.py

```


Si la ejecución es correcta, la terminal quedará en escucha mostrando el mensaje: `Iniciando servidor MCP de UVL...`.



---

### Conexión con Claude Desktop

Para que el modelo de IA pueda invocar las herramientas de validación, es necesario vincular este servidor local con la aplicación cliente oficial.

1. En primer lugar, se debe instalar y abrir la aplicación Claude Desktop.


2. Se debe navegar a Archivo > Configuración (o File > Settings), y acceder a la pestaña Desarrollador.


3. Se hace clic en Editar configuración para abrir el archivo `claude_desktop_config.json`.


4. Se añade el servidor MCP a la configuración, apuntando a los ejecutables exactos del entorno virtual. Es necesario sustituir `C:\\ruta_personal_archivos` por el directorio real donde se ubicó el proyecto:



```json
{
  "mcpServers": {
    "servidor_tfg_uvl": {
      "command": "C:\\ruta_personal_archivos\\venv\\Scripts\\python.exe",
      "args": [
        "C:\\ruta_personal_archivos\\server.py"
      ]
    }
  }
}

```

5. Se guarda el archivo JSON y se reinicia por completo Claude Desktop (asegurando su cierre también en segundo plano).


6. Al abrir un nuevo chat, se debe hacer clic en el icono de Conectores (el símbolo de enchufe o `+`) y verificar que el servidor `servidor_tfg_uvl` aparece disponible para ser utilizado.
