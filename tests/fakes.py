from __future__ import annotations

from api.shared.email_sender import EmailSender
from api.shared.image_storage import ImageStorage, StoredImage


class FakeImageStorage(ImageStorage):
    """Substitui o Cloudinary nos testes: guarda envios e exclusoes em memoria."""

    def __init__(self) -> None:
        self.uploads: list[tuple[bytes, str]] = []
        self.deleted: list[str] = []

    async def upload(self, image: bytes, folder: str) -> StoredImage:
        self.uploads.append((image, folder))
        public_id = f"{folder}/{len(self.uploads)}"
        return StoredImage(
            url=f"https://res.cloudinary.com/test/image/upload/{public_id}.png",
            public_id=public_id,
        )

    async def delete(self, public_id: str) -> None:
        self.deleted.append(public_id)


class FakeEmailSender(EmailSender):
    """Substitui o Brevo nos testes: guarda os e-mails em memoria em vez de enviar."""

    def __init__(self) -> None:
        self.password_reset_codes: list[tuple[str, str, str]] = []

    async def send_password_reset_code(self, to: str, name: str, code: str) -> None:
        self.password_reset_codes.append((to, name, code))
