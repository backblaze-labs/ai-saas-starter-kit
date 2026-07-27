"""The presigned URL's Content-Disposition drives whether the browser renders
the object inline (preview modal) or downloads it (explicit download)."""

from app.repo import b2_client


class _CapturingS3:
    """Fake S3 client that records the Params of the last presign call."""

    def __init__(self):
        self.params: dict | None = None

    def generate_presigned_url(self, op, Params, ExpiresIn):  # boto3 kwarg casing
        self.params = Params
        return "https://b2.example/signed"


def test_download_forces_attachment(monkeypatch):
    fake = _CapturingS3()
    monkeypatch.setattr(b2_client, "get_s3_client", lambda: fake)

    b2_client.get_presigned_url("uploads/u/doc.pdf", filename="doc.pdf")

    # Default disposition is attachment so a stored file can't render in-browser.
    assert fake.params["ResponseContentDisposition"].startswith("attachment")


def test_preview_requests_inline(monkeypatch):
    fake = _CapturingS3()
    monkeypatch.setattr(b2_client, "get_s3_client", lambda: fake)

    b2_client.get_presigned_url("uploads/u/doc.pdf", filename="doc.pdf", disposition="inline")

    # Inline is what lets the preview modal render a PDF in its <iframe> instead
    # of triggering a download.
    assert fake.params["ResponseContentDisposition"].startswith("inline")
