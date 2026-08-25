import numexpr as ne


def calculator_agent(state):

    query = state.get("resolved_query") or state.get("query", "")

    try:
        result = ne.evaluate(query)

        if hasattr(result, "item"):
            result = result.item()

        return {"calculator_output": str(result)}

    except Exception as e:
        return {"calculator_output": f"Calculation error: {str(e)}"}
