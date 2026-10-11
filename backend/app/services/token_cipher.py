from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class TokenEncryptionConfigurationError(RuntimeError):
    pass


class TokenDecryptionError(RuntimeError):
    pass


class TokenCipher:
    """Encrypt OAuth tokens with a rotation-friendly Fernet key ring."""

    def __init__(self, encoded_keys: str) -> None:
        keys = [value.strip().encode() for value in encoded_keys.split(",") if value.strip()]
        if not keys:
            raise TokenEncryptionConfigurationError("TOKEN_ENCRYPTION_KEYS 未配置")
        try:
            self._cipher = MultiFernet([Fernet(key) for key in keys])
        except (TypeError, ValueError) as exc:
            raise TokenEncryptionConfigurationError(
                "TOKEN_ENCRYPTION_KEYS 必须是有效的 Fernet 密钥，多个密钥用逗号分隔"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("不能加密空 Token")
        return self._cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise TokenDecryptionError("Token 密文无法使用当前密钥解密") from exc

    def rotate(self, ciphertext: str) -> str:
        try:
            return self._cipher.rotate(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise TokenDecryptionError("Token 密文无法使用当前密钥轮换") from exc
