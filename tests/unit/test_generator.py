from app.rag.generator import generate_answer


def test_generator_no_context():

    answer = generate_answer("What is leave policy?", [])

    assert answer == "I could not find the answer in the provided documents."
