from dataclasses import dataclass

@dataclass(frozen=True)
class PayloadSignature:
    hash_value: str

    def __post_init__(self) -> None:
        if not self.hash_value or len(self.hash_value) != 64:
            raise ValueError("Payload signature must be a valid 64-character SHA-256 hex string.")