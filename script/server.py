import sys
import requests
import os
import tempfile
import logging
import contextlib
import io
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from flamapy.metamodels.fm_metamodel.transformations import UVLReader
from flamapy.metamodels.pysat_metamodel.transformations import FmToPysat
from flamapy.metamodels.bdd_metamodel.transformations import FmToBDD
from flamapy.metamodels.bdd_metamodel.operations import BDDConfigurationsNumber
from flamapy.metamodels.pysat_metamodel.operations import (
    PySATSatisfiable,
    PySATDeadFeatures,
    PySATCoreFeatures,
    PySATFalseOptionalFeatures
)

# Se configura la ruta del directorio donde se encuentre el servidor como ruta base donde se almacenarán los modelos generados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


EJEMPLOS_DIR = os.path.join(BASE_DIR, "ejemplos_contexto")

# Inicializacion del servidor
mcp = FastMCP("UVL_Variability_Server")

# Rutas para contextualizar al modelo UVL
UVL_GRAMMAR_URL = "https://raw.githubusercontent.com/Universal-Variability-Language/uvl-parser/main/uvl/UVLParser.g4"
UVL_README_URL  = "https://raw.githubusercontent.com/Universal-Variability-Language/uvl-parser/main/README.md"


# HERRAMIENTA 4: Obtención de ejemplos de referencia (Few-Shot Prompting) dinámicos
@mcp.tool()
def get_uvl_examples() -> str:
    """
    Proporciona ejemplos de pares (Descripción, Modelo UVL) correctos.
    Llamar a esta herramienta SIEMPRE antes de generar código para entender 
    cómo traducir descripciones a código UVL válido.
    """
    if not os.path.exists(EJEMPLOS_DIR):
        return f"Aviso: No se ha encontrado el directorio de ejemplos. La ruta de la carpeta debe ser: {EJEMPLOS_DIR}"

    ejemplos_compilados = []
    
    try:
        for filename in os.listdir(EJEMPLOS_DIR):
            if filename.endswith(".txt"):
                base_name = filename[:-4]
                txt_path = os.path.join(EJEMPLOS_DIR, filename)
                uvl_path = os.path.join(EJEMPLOS_DIR, f"{base_name}.uvl")
                
                
                with open(txt_path, "r", encoding="utf-8") as f:
                    descripcion = f.read().strip()
                
                
                uvl_code = "No se encontró el modelo UVL asociado."
                if os.path.exists(uvl_path):
                    with open(uvl_path, "r", encoding="utf-8") as f:
                        uvl_code = f.read().strip()
                
                
                bloque = f"""
### EJEMPLO: {base_name.upper()} ###
--- DESCRIPCIÓN ---
{descripcion}

--- CÓDIGO UVL ESPERADO ---
{uvl_code}
---------------------------------------
"""
                ejemplos_compilados.append(bloque)
                
        if not ejemplos_compilados:
            return "El directorio de ejemplos está vacío."
            
        return "Aquí tienes ejemplos de referencia de descripciones y su correcto modelado en UVL:\n\n" + "\n".join(ejemplos_compilados)
        
    except Exception as e:
        return f"Error al procesar el directorio de ejemplos: {str(e)}"




# HERRAMIENTA 1: Obtencion del contexto de UVL y de la gramatica oficial del mismo
@mcp.tool()
def get_uvl_grammar_rules() -> str:
    """
    Descarga la gramática de UVL. 
    Usar siempre antes de generar modelos.
    """
    try:
        # Se realiza la solicitud del README y de la gramatica
        r_grammar = requests.get(UVL_GRAMMAR_URL, timeout=10)
        r_grammar.raise_for_status()
        r_readme = requests.get(UVL_README_URL, timeout=10)
        readme = r_readme.text if r_readme.status_code == 200 else "README no disponible."
        
        return f"""
        --- CONTEXTO UVL (Readme del repositorio oficial de UVL) ---
        {readme}
        --- GRAMÁTICA FORMAL ---
        {r_grammar.text}
        """
    except Exception as e:
        return f"Error al obtener la gramática: {str(e)}"

# HERRAMIENTA 2: Validador sintactico y semantico usando Flamapy
@mcp.tool()
def validate_uvl_syntax_sat_bdd(uvl_code: str) -> str:
    """
    Valida la sintaxis de un modelo UVL usando Flamapy.
    Comprueba la satisfacibilidad del modelo generado una vez validado.
    El LLM debe llamar SIEMPRE a esta herramienta tras generar un modelo.
    """
       
    # Se realiza una limpieza de los posibles markdowns que el modelo ofrezca
    uvl_code = uvl_code.strip()
    if uvl_code.startswith("```"):
        lines = uvl_code.split("\n")
        end = -1 if lines[-1].strip().startswith("```") else len(lines)
        uvl_code = "\n".join(lines[1:end])
    if uvl_code.startswith("uvl\n"):
        uvl_code = uvl_code[4:]


    # Se genera un archivo temporal seguro para que Flamapy pueda leerlo
    temp_dir = tempfile.gettempdir()
    uvl_path = os.path.join(temp_dir, "claude_temp_model.uvl")
    
    try:
        with open(uvl_path, 'w', encoding='utf-8') as f:
            f.write(uvl_code)

        # Se desactivan los logs temporalmente para no interferir en la comunicacion del servidor MCP
        logging.disable(logging.CRITICAL)
        
        # Ejecucion de Flamapy
        reader = UVLReader(uvl_path)
        model = reader.transform()

        # Análisis Semántico (SAT y BDD) si la sintaxis es correcta
        sat_result = None
        num_configs = None
        analysis_report = ""
        has_anomalies = False
        
        if model is not None:
            try:
                # Análisis SAT (¿Es satisfacible?)
                sat_model = FmToPysat(model).transform()
                sat_result = PySATSatisfiable().execute(sat_model).get_result()

                if sat_result:
                    # Comprobación de dead features, core features (siempre presentes) 
                    # y false optional features (modeladas con optional pero siempre obligatorias)
                    dead_feats = PySATDeadFeatures().execute(sat_model).get_result()
                    core_feats = PySATCoreFeatures().execute(sat_model).get_result()
                    false_opts = PySATFalseOptionalFeatures().execute(sat_model).get_result()

                    dead_names = [str(f) for f in dead_feats] if dead_feats else []
                    core_names = [str(f) for f in core_feats] if core_feats else []
                    false_opt_names = [str(f) for f in false_opts] if false_opts else []

                    if dead_names or false_opt_names:
                        has_anomalies = True


                    # Análisis BDD (Número de configuraciones) solo si es satisfacible
                
                    bdd_model = FmToBDD(model).transform()
                    num_configs = BDDConfigurationsNumber().execute(bdd_model).get_result()

                    analysis_report = f"""
--- INFORME DE AUDITORÍA SEMÁNTICA ---
- Configuraciones válidas totales: {num_configs}
- Configuraciones core (siempre presentes, por mandatory o por restricciones): {', '.join(core_names) if core_names else 'Ninguna'}
- Características muertas (dead features): {', '.join(dead_names) if dead_names else 'Ninguna (Perfecto)'}
- Falsas Opcionales (False optional features): {', '.join(false_opt_names) if false_opt_names else 'Ninguna (Perfecto)'}
---------------------------------------
                    """

            except ImportError:
                pass # Si faltan las librerías, se omite silenciosamente para no romper el validador base

        # Restauracion de los logs
        logging.disable(logging.NOTSET)

        # Evaluación del resultado
        if model is None:
            msg = getattr(reader, 'get_error_message', lambda: "Error desconocido del parser")()
            return f"Validación fallida. Flamapy detectó el siguiente error sintáctico:\n{msg}\nPor favor, corrígelo iterativamente."
        
        if sat_result is False:
            return "Validación semántica fallida: El modelo tiene 0 configuraciones válidas debido a restricciones contradictorias (Void Model). Analiza las exclusiones y corrígelas."
        
        if sat_result is True:
            # Se verifica si se han detectado anomalías del tipo dead_features o false_optional
            if has_anomalies:

                deficiencias_dir = os.path.join(BASE_DIR,"modelos_con_deficiencias")
                os.makedirs(deficiencias_dir,exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                deficiente_filename = f"modelo_deficiente_{timestamp}.uvl"
                filepath = os.path.join(deficiencias_dir, deficiente_filename) 
                replacements = {
                    'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
                    'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
                    'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
                    '—': '-', '–': '-', 
                    '→': '=>', '->': '=>' 
                }
                for char, replacement in replacements.items():
                    uvl_code = uvl_code.replace(char, replacement) 
                try:
                    with open(filepath,"w",encoding="utf-8") as f:
                        f.write(uvl_code)
                    guardado_msg = f"\n[Nota del sistema: Este modelo intermedio ha sido guardado automáticamente en 'modelos_con_deficiencias/{deficiente_filename}' para investigación]."
                except Exception:
                    guardado_msg = ""

                return f"Validation Warning: El modelo es satisfacible, pero contiene anomalías graves de diseño.\n{analysis_report}{guardado_msg}\nLee el informe, razona por qué ocurren estas anomalías, corrige el código UVL y vuelve a validarlo hasta que no tenga anomalías."    
                 
            else:
                return f"Validation Success: El modelo es lógicamente perfecto.\n{analysis_report}"
    except Exception as e:
        logging.disable(logging.NOTSET)
        return f"Validación fallida: error interno de sintaxis detectado:\n{str(e)}"
    finally:
        # Limpieza de archivos temporales
        if os.path.exists(uvl_path):
            try: os.remove(uvl_path)
            except: pass


# HERRAMIENTA 3: GUARDAR
@mcp.tool()
def save_valid_model(uvl_code: str, filename: str) -> str:
    """
    Guarda el modelo UVL validado en disco. 
    Solo llamar si el validador ha devuelto Success.
    """
    modelos_dir = os.path.join(BASE_DIR, "modelos_generados")

    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U',
        '—': '-', '–': '-',  
        '→': '=>', '->': '=>' 
    }
    for char, replacement in replacements.items():
        uvl_code = uvl_code.replace(char, replacement)
    
    try:
        os.makedirs(modelos_dir, exist_ok=True)
        if not filename.endswith(".uvl"):
            filename += ".uvl"
            
        filepath = os.path.join(modelos_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(uvl_code)
            
        return f"Éxito: modelo guardado en {filepath}"
    except Exception as e:
        return f"Error de permisos al guardar el archivo: {str(e)}"





# MAIN
if __name__ == "__main__":
    print("Iniciando servidor MCP de UVL...", file=sys.stderr)
    mcp.run()