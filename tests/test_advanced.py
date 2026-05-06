"""Tests for advanced configurations: LTV, BCD/HEX/BINARY encodings, length_includes_tag, value_type=BINARY."""

import pytest

from pytlv_codec import (
    Codec,
    CodecConfig,
    Encoding,
    EncodingError,
    InvalidTLVError,
    Order,
    ValueType,
)


class TestLTVOrder:
    """LTV: length comes before tag."""

    def test_encode_ltv_simple(self) -> None:
        config = CodecConfig(order=Order.LTV)
        codec = Codec(config)

        result = codec.encode({"05": "12345"})

        # LTV: length(0005) + tag(05) + value(12345)
        assert result == "00050512345"

    def test_decode_ltv_simple(self) -> None:
        config = CodecConfig(order=Order.LTV)
        codec = Codec(config)

        result = codec.decode("00050512345")

        assert result == {"05": "12345"}

    def test_ltv_roundtrip(self) -> None:
        config = CodecConfig(order=Order.LTV)
        codec = Codec(config)

        original = {"05": "abc", "62": "test"}
        encoded = codec.encode(original)
        decoded = codec.decode(encoded)

        assert decoded == original


class TestBinaryValueType:
    """value_type=BINARY: value string is hex repr; length = bytes (chars/2)."""

    def test_encode_binary_value(self) -> None:
        config = CodecConfig(value_type=ValueType.BINARY)
        codec = Codec(config)

        # Value "0000000000" = 5 hex pairs = 5 bytes binary
        result = codec.encode({"05": "0000000000"})

        # length should be 5 (bytes), formatted as "0005"
        assert result == "0500050000000000"

    def test_decode_binary_value(self) -> None:
        config = CodecConfig(value_type=ValueType.BINARY)
        codec = Codec(config)

        result = codec.decode("0500050000000000")

        assert result == {"05": "0000000000"}

    def test_binary_value_odd_length_raises(self) -> None:
        config = CodecConfig(value_type=ValueType.BINARY)
        codec = Codec(config)

        with pytest.raises(EncodingError, match="must have an even number of characters"):
            codec.encode({"05": "12345"})  # 5 chars, odd

    def test_binary_value_invalid_hex_raises(self) -> None:
        config = CodecConfig(value_type=ValueType.BINARY)
        codec = Codec(config)

        with pytest.raises(EncodingError, match="invalid character"):
            codec.encode({"05": "ZZZZ"})  # not hex


class TestLengthIncludesTag:
    """length_includes_tag: length counts tag+value bytes (LTV variant)."""

    def test_ltv_length_includes_tag_ascii(self) -> None:
        config = CodecConfig(
            order=Order.LTV,
            length_includes_tag=True,
        )
        codec = Codec(config)

        # tag "05" = 2 chars ASCII = 2 bytes
        # value "abc" = 3 chars ASCII = 3 bytes
        # length = 2 + 3 = 5 → "0005"
        result = codec.encode({"05": "abc"})

        assert result == "000505abc"

    def test_ltv_length_includes_tag_decode(self) -> None:
        config = CodecConfig(
            order=Order.LTV,
            length_includes_tag=True,
        )
        codec = Codec(config)

        result = codec.decode("000505abc")

        assert result == {"05": "abc"}

    def test_length_includes_tag_smaller_than_tag_raises(self) -> None:
        config = CodecConfig(
            order=Order.LTV,
            length_includes_tag=True,
        )
        codec = Codec(config)

        # length=1, but tag is 2 bytes — invalid
        with pytest.raises(InvalidTLVError, match="smaller than tag size"):
            codec.decode("000105")


class TestRealWorldAcquirerExample:
    """Reproduces a real-world acquirer-style sub-field encoding.

    Represents an ISO 8583 sub-field with multiple concatenated subfields packed
    as binary data. The TLV envelope itself uses LTV order with BCD-encoded tag
    and length, where length includes the tag bytes. This is the format described
    in publicly documented Brazilian acquirer integrations.

    Encoded structure:
    - L (4 BCD digits = 2 bytes packed) — total length including tag
    - T (2 BCD digits = 1 byte packed) — sub-field identifier
    - V (37 bytes) — application data, opaque to this codec
    """

    def test_encode_real_world_subfield(self) -> None:
        # Value is a 74-char hex representation of 37 bytes of opaque application data
        # (in the wild, this would be a concatenation of multiple application
        # subfields — currency code, amounts, references — but to this codec
        # it is just opaque payload).
        opaque_payload = (
            "05449700000100096508400000010009660000010009"
            "665553443132333435021234567806"
        )
        assert len(opaque_payload) == 74  # 37 bytes when interpreted as hex

        config = CodecConfig(
            order=Order.LTV,
            tag_size=2,
            tag_encoding=Encoding.BCD,
            length_size=4,
            length_encoding=Encoding.BCD,
            value_type=ValueType.BINARY,
            length_includes_tag=True,
        )
        codec = Codec(config)

        result = codec.encode({"33": opaque_payload})

        # Expected: length(0038) + tag(33) + value(74 hex chars)
        # 0038 = 38 bytes total (1 tag byte BCD + 37 value bytes)
        expected = "0038" + "33" + opaque_payload
        assert result == expected
        assert len(result) == 80  # 4 + 2 + 74

    def test_decode_real_world_subfield(self) -> None:
        config = CodecConfig(
            order=Order.LTV,
            tag_size=2,
            tag_encoding=Encoding.BCD,
            length_size=4,
            length_encoding=Encoding.BCD,
            value_type=ValueType.BINARY,
            length_includes_tag=True,
        )
        codec = Codec(config)

        encoded = (
            "0038330544970000010009650840000001000966"
            "00000100096655534431323334350212345678"
            "06"
        )

        result = codec.decode(encoded)

        assert "33" in result
        assert result["33"].startswith("054497")
        assert result["33"].endswith("7806")
        assert len(result["33"]) == 74

    def test_real_world_roundtrip(self) -> None:
        config = CodecConfig(
            order=Order.LTV,
            tag_size=2,
            tag_encoding=Encoding.BCD,
            length_size=4,
            length_encoding=Encoding.BCD,
            value_type=ValueType.BINARY,
            length_includes_tag=True,
        )
        codec = Codec(config)

        original = {
            "33": (
                "05449700000100096508400000010009660000010009"
                "665553443132333435021234567806"
            )
        }
        encoded = codec.encode(original)
        decoded = codec.decode(encoded)

        assert decoded == original


class TestBCDEncodingValidation:
    """BCD encoding restricts tag chars to digits 0-9."""

    def test_bcd_tag_with_letter_raises(self) -> None:
        config = CodecConfig(tag_encoding=Encoding.BCD)
        codec = Codec(config)

        with pytest.raises(EncodingError, match="invalid character"):
            codec.encode({"AB": "test"})

    def test_bcd_tag_numeric_accepted(self) -> None:
        config = CodecConfig(tag_encoding=Encoding.BCD)
        codec = Codec(config)

        # Should not raise — all numeric is valid BCD
        codec.encode({"99": "test"})


class TestHexEncodingValidation:
    """HEX encoding allows 0-9, a-f, A-F."""

    def test_hex_tag_with_alpha_accepted(self) -> None:
        config = CodecConfig(tag_encoding=Encoding.HEX, tag_size=4)
        codec = Codec(config)

        # EMV-style hex tag
        codec.encode({"9F02": "test"})

    def test_hex_tag_with_invalid_char_raises(self) -> None:
        config = CodecConfig(tag_encoding=Encoding.HEX, tag_size=2)
        codec = Codec(config)

        with pytest.raises(EncodingError, match="invalid character"):
            codec.encode({"GG": "test"})  # G not hex
