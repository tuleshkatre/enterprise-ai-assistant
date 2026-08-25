from ddgs import DDGS
from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """
    Search the web for recent information.
    """

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        print("RESULTS:", results)

        if not results:
            return "No results found."

        output = []

        for r in results:
            output.append(
                f"Title: {r.get('title', '')}\n"
                f"Body: {r.get('body', '')}\n"
                f"URL: {r.get('href', '')}"
            )

        return "\n\n".join(output)

    except Exception as e:
        print("SEARCH ERROR:", e)
        return f"Search error: {e}"
