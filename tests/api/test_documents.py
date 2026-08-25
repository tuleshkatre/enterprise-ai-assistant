from io import BytesIO

from tests.conftest import client


def test_upload_invalid_file(auth_headers):

    response = client.post(
        "/upload",
        files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_list_documents(auth_headers):

    response = client.get("/documents", headers=auth_headers)

    assert response.status_code == 200

    assert isinstance(response.json(), list)


def test_delete_nonexistent_document(auth_headers):

    response = client.delete("/documents/not_found.pdf", headers=auth_headers)

    assert response.status_code == 404


def test_documents_requires_auth():

    response = client.get("/documents")

    assert response.status_code == 401


def test_upload_pdf(auth_headers):

    with open("tests/data/sample.pdf", "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
            headers=auth_headers,
        )

    assert response.status_code == 200
