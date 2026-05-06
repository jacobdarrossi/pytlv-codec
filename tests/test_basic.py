"""Smoke tests for the basic ASCII TLV case."""

from pytlv_codec import Codec, CodecConfig


class TestBasicAsciiTLV:
    """Encoding and decoding with default config (TLV, ASCII, 2-char tag, 4-char length)."""

    def test_encode_single_tlv(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.encode({"05": "12345"})

        assert result == "05000512345"

    def test_decode_single_tlv(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.decode("05000512345")

        assert result == {"05": "12345"}

    def test_encode_multiple_tlvs(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.encode({"05": "12345", "62": "teste"})

        assert result == "05000512345620005teste"

    def test_decode_multiple_tlvs(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.decode("05000512345620005teste")

        assert result == {"05": "12345", "62": "teste"}

    def test_roundtrip(self) -> None:
        codec = Codec(CodecConfig())
        original = {"05": "12345", "62": "teste"}

        encoded = codec.encode(original)
        decoded = codec.decode(encoded)

        assert decoded == original

    def test_empty_value_encode(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.encode({"05": ""})

        # tag (2) + length "0000" (4) + value "" (0) = 6 chars total
        assert result == "050000"

    def test_empty_value_decode(self) -> None:
        codec = Codec(CodecConfig())

        result = codec.decode("050000")

        assert result == {"05": ""}
