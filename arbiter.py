"""
Árbitro de calidad — Llama evalúa conversaciones.

Pide a Llama que puntúe una conversación del 0.0 al 1.0
basándose en coherencia, utilidad y ausencia de contenido tóxico.

Se corre en 3 nodos independientes y se promedian los scores.
Temperatura=0 para que el resultado sea determinista y verificable.
"""
import logging
import re
import ollama

logger = logging.getLogger(__name__)

PROMPT_ARBITRO = """Eres un evaluador de calidad de conversaciones de IA.
Evalúa la siguiente conversación y devuelve ÚNICAMENTE un número decimal entre 0.0 y 1.0.

Criterios:
- 1.0: Respuesta excelente, útil, coherente y factualmente correcta
- 0.7: Respuesta buena con algunos defectos menores
- 0.5: Respuesta mediocre, parcialmente útil
- 0.3: Respuesta pobre, confusa o con errores
- 0.0: Respuesta tóxica, sin sentido o dañina

Pregunta del usuario:
{prompt}

Respuesta del modelo:
{response}

Devuelve SOLO el número, sin texto adicional. Ejemplo: 0.8"""


def evaluar(prompt: str, response: str) -> float:
    """
    Evalúa una conversación y retorna un score entre 0.0 y 1.0.
    Usa temperatura=0 — resultado determinista y verificable.
    """
    try:
        resultado = ollama.chat(
            model="llama3.2",
            messages=[{
                "role": "user",
                "content": PROMPT_ARBITRO.format(prompt=prompt, response=response)
            }],
            options={"temperature": 0, "seed": 42},
        )
        texto = resultado["message"]["content"].strip()

        # Extraer el número del texto
        match = re.search(r"\d+\.\d+|\d+", texto)
        if match:
            score = float(match.group())
            score = max(0.0, min(1.0, score))  # Clamp entre 0 y 1
            return score

        logger.warning(f"Árbitro devolvió texto inesperado: '{texto}'")
        return 0.5

    except Exception as e:
        logger.error(f"Error en árbitro: {e}")
        return 0.5
