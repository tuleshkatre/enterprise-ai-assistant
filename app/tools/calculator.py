import numexpr as ne
from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression.
    """

    try:
        result = ne.evaluate(expression)

        return str(result.item())

    except Exception as e:
        return f"Calculation error: {str(e)}"
