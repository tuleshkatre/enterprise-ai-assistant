from app.rag.generator import generate_answer


def test_generator_with_context():

    docs = [{"content": "Employees receive 12 sick leave days annually."}]

    answer = generate_answer("How many sick leave days?", docs)

    assert isinstance(answer, str)

    assert len(answer) > 0
