from __future__ import annotations

from httpx import AsyncClient


async def test_generic_export_csv_xlsx_pdf(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    admin = await auth_headers("admin", "admin123")

    csv_response = await client.get(
        "/api/v1/transfer/export/resource/students?fmt=csv", headers=admin
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "attachment" in csv_response.headers["content-disposition"]
    assert "学号" in csv_response.text

    xlsx_response = await client.get(
        "/api/v1/transfer/export/resource/students?fmt=xlsx", headers=admin
    )
    assert xlsx_response.status_code == 200
    assert xlsx_response.content[:2] == b"PK"

    pdf_response = await client.get(
        "/api/v1/transfer/export/resource/students?fmt=pdf", headers=admin
    )
    assert pdf_response.status_code == 200
    assert pdf_response.content[:5] == b"%PDF-"

    template = await client.get("/api/v1/transfer/template/students", headers=admin)
    assert template.status_code == 200
    assert "student_no" in template.text


async def test_generic_export_requires_permission(
    client: AsyncClient, seed: dict[str, int], auth_headers
) -> None:
    student = await auth_headers("s001", "student123")
    response = await client.get("/api/v1/transfer/export/resource/audit?fmt=csv", headers=student)
    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
