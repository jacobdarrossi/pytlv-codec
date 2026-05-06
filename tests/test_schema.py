"""Tests for SubfieldSchema (pack/unpack of structured TLV values)."""

import pytest

from pytlv_codec import (
    EncodingError,
    InvalidTLVError,
    LengthPrefix,
    LengthPrefixEncoding,
    Subfield,
    SubfieldSchema,
    SubfieldType,
)


class TestSubfieldValidation:
    """Subfield dataclass enforces fixed-size XOR variable-length."""

    def test_subfield_with_size_only_valid(self) -> None:
        sf = Subfield("foo", SubfieldType.BCD, size_bytes=3)
        assert not sf.is_variable

    def test_subfield_with_length_prefix_only_valid(self) -> None:
        sf = Subfield(
            "foo",
            SubfieldType.ASCII,
            length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, 1),
        )
        assert sf.is_variable

    def test_subfield_without_size_or_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="must specify"):
            Subfield("foo", SubfieldType.BCD)

    def test_subfield_with_both_size_and_prefix_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot specify both"):
            Subfield(
                "foo",
                SubfieldType.BCD,
                size_bytes=3,
                length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, 1),
            )


class TestLengthPrefixValidation:
    def test_size_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="size_bytes must be > 0"):
            LengthPrefix(LengthPrefixEncoding.BCD, 0)

    def test_max_value_bcd(self) -> None:
        # 2 bytes BCD = 4 digits = max 9999
        assert LengthPrefix(LengthPrefixEncoding.BCD, 2).max_value == 9999

    def test_max_value_ascii(self) -> None:
        # 3 bytes ASCII = 3 digits = max 999
        assert LengthPrefix(LengthPrefixEncoding.ASCII, 3).max_value == 999

    def test_max_value_binary(self) -> None:
        # 1 byte binary = max 255
        assert LengthPrefix(LengthPrefixEncoding.BINARY, 1).max_value == 255


class TestSchemaValidation:
    def test_schema_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="at least one subfield"):
            SubfieldSchema([])

    def test_schema_rejects_duplicate_names(self) -> None:
        with pytest.raises(ValueError, match="Duplicate"):
            SubfieldSchema(
                [
                    Subfield("foo", SubfieldType.BCD, size_bytes=3),
                    Subfield("foo", SubfieldType.ASCII, size_bytes=2),
                ]
            )


class TestFixedSizePack:
    def test_pack_bcd(self) -> None:
        schema = SubfieldSchema(
            [Subfield("acquirer", SubfieldType.BCD, size_bytes=3)]
        )
        result = schema.pack({"acquirer": "054497"})
        assert result == "054497"

    def test_pack_ascii_converts_to_hex(self) -> None:
        schema = SubfieldSchema(
            [Subfield("currency", SubfieldType.ASCII, size_bytes=3)]
        )
        result = schema.pack({"currency": "USD"})
        # 'U'=0x55, 'S'=0x53, 'D'=0x44
        assert result == "555344"

    def test_pack_binary(self) -> None:
        schema = SubfieldSchema(
            [Subfield("data", SubfieldType.BINARY, size_bytes=4)]
        )
        result = schema.pack({"data": "DEADBEEF"})
        assert result == "DEADBEEF"

    def test_pack_binary_normalizes_to_uppercase(self) -> None:
        schema = SubfieldSchema(
            [Subfield("data", SubfieldType.BINARY, size_bytes=4)]
        )
        assert schema.pack({"data": "deadbeef"}) == "DEADBEEF"

    def test_pack_mixed(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield("acquirer", SubfieldType.BCD, size_bytes=3),
                Subfield("currency", SubfieldType.ASCII, size_bytes=3),
                Subfield("data", SubfieldType.BINARY, size_bytes=2),
            ]
        )
        result = schema.pack(
            {"acquirer": "054497", "currency": "USD", "data": "ABCD"}
        )
        assert result == "054497" + "555344" + "ABCD"


class TestFixedSizeUnpack:
    def test_unpack_bcd(self) -> None:
        schema = SubfieldSchema(
            [Subfield("acquirer", SubfieldType.BCD, size_bytes=3)]
        )
        assert schema.unpack("054497") == {"acquirer": "054497"}

    def test_unpack_ascii_converts_back_from_hex(self) -> None:
        schema = SubfieldSchema(
            [Subfield("currency", SubfieldType.ASCII, size_bytes=3)]
        )
        assert schema.unpack("555344") == {"currency": "USD"}

    def test_unpack_binary_normalizes_to_uppercase(self) -> None:
        schema = SubfieldSchema(
            [Subfield("data", SubfieldType.BINARY, size_bytes=4)]
        )
        assert schema.unpack("deadbeef") == {"data": "DEADBEEF"}

    def test_roundtrip_mixed(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield("acquirer", SubfieldType.BCD, size_bytes=3),
                Subfield("currency", SubfieldType.ASCII, size_bytes=3),
                Subfield("data", SubfieldType.BINARY, size_bytes=2),
            ]
        )
        original = {"acquirer": "054497", "currency": "USD", "data": "ABCD"}
        assert schema.unpack(schema.pack(original)) == original


class TestVariableLengthPack:
    def test_pack_variable_bcd_with_bcd_prefix(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "merchant_id",
                    SubfieldType.BCD,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
                )
            ]
        )
        # 6 digits = 3 bytes; prefix BCD 1 byte = 2 digits = "03"
        assert schema.pack({"merchant_id": "123456"}) == "03123456"

    def test_pack_variable_ascii_with_bcd_prefix(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "merchant_name",
                    SubfieldType.ASCII,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
                )
            ]
        )
        result = schema.pack({"merchant_name": "STORE"})
        expected_hex = "STORE".encode("ascii").hex().upper()
        # "STORE" = 5 bytes; prefix "05"
        assert result == "05" + expected_hex

    def test_pack_variable_binary_with_bcd_prefix(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "data",
                    SubfieldType.BINARY,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=2),
                )
            ]
        )
        # 4 bytes; prefix BCD 2 bytes = 4 digits = "0004"
        assert schema.pack({"data": "DEADBEEF"}) == "0004DEADBEEF"

    def test_pack_variable_binary_with_binary_prefix(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "data",
                    SubfieldType.BINARY,
                    length_prefix=LengthPrefix(
                        LengthPrefixEncoding.BINARY, size_bytes=1
                    ),
                )
            ]
        )
        # 4 bytes value; prefix is 1 binary byte = "04"
        assert schema.pack({"data": "DEADBEEF"}) == "04DEADBEEF"


class TestVariableLengthUnpack:
    def test_unpack_variable_bcd(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "merchant_id",
                    SubfieldType.BCD,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
                )
            ]
        )
        assert schema.unpack("03123456") == {"merchant_id": "123456"}

    def test_unpack_variable_ascii(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "merchant_name",
                    SubfieldType.ASCII,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
                )
            ]
        )
        # "STORE" hex = "5354 4F52 45" = "53544F5245"
        assert schema.unpack("0553544F5245") == {"merchant_name": "STORE"}

    def test_roundtrip_variable_mixed(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield("acquirer", SubfieldType.BCD, size_bytes=3),
                Subfield(
                    "merchant_name",
                    SubfieldType.ASCII,
                    length_prefix=LengthPrefix(LengthPrefixEncoding.BCD, size_bytes=1),
                ),
                Subfield("currency", SubfieldType.ASCII, size_bytes=3),
            ]
        )
        original = {
            "acquirer": "054497",
            "merchant_name": "STORE TEST",
            "currency": "USD",
        }
        assert schema.unpack(schema.pack(original)) == original


class TestPackErrors:
    def test_missing_subfield_raises(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield("a", SubfieldType.BCD, size_bytes=2),
                Subfield("b", SubfieldType.BCD, size_bytes=2),
            ]
        )
        with pytest.raises(EncodingError, match="Missing"):
            schema.pack({"a": "1234"})

    def test_unknown_subfield_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BCD, size_bytes=2)])
        with pytest.raises(EncodingError, match="Unknown"):
            schema.pack({"a": "1234", "extra": "5678"})

    def test_bcd_wrong_size_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BCD, size_bytes=3)])
        with pytest.raises(EncodingError, match="expects 6 digits"):
            schema.pack({"a": "12345"})

    def test_bcd_invalid_chars_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BCD, size_bytes=2)])
        with pytest.raises(EncodingError, match="non-digit"):
            schema.pack({"a": "12AB"})

    def test_ascii_wrong_size_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.ASCII, size_bytes=3)])
        with pytest.raises(EncodingError, match="expects 3 chars"):
            schema.pack({"a": "USDX"})

    def test_ascii_non_ascii_chars_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.ASCII, size_bytes=3)])
        with pytest.raises(EncodingError, match="non-ASCII"):
            schema.pack({"a": "ção"})

    def test_binary_wrong_size_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BINARY, size_bytes=2)])
        with pytest.raises(EncodingError, match="expects 4 hex chars"):
            schema.pack({"a": "ABCDEF"})

    def test_binary_invalid_chars_raises(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BINARY, size_bytes=2)])
        with pytest.raises(EncodingError, match="non-hex"):
            schema.pack({"a": "ZZZZ"})

    def test_variable_value_exceeds_prefix_max(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "a",
                    SubfieldType.BCD,
                    length_prefix=LengthPrefix(
                        LengthPrefixEncoding.BCD, size_bytes=1
                    ),
                )
            ]
        )
        # 1-byte BCD prefix = max 99 bytes = 198 digits
        with pytest.raises(EncodingError, match="exceeds max"):
            schema.pack({"a": "0" * 200})  # 100 bytes


class TestUnpackErrors:
    def test_truncated_fixed_subfield(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BCD, size_bytes=3)])
        with pytest.raises(InvalidTLVError, match="Truncated subfield"):
            schema.unpack("123")

    def test_extra_data_after_schema(self) -> None:
        schema = SubfieldSchema([Subfield("a", SubfieldType.BCD, size_bytes=2)])
        with pytest.raises(InvalidTLVError, match="Extra data"):
            schema.unpack("1234EXTRA")

    def test_truncated_length_prefix(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "a",
                    SubfieldType.BCD,
                    length_prefix=LengthPrefix(
                        LengthPrefixEncoding.BCD, size_bytes=2
                    ),
                )
            ]
        )
        with pytest.raises(InvalidTLVError, match="Truncated length prefix"):
            schema.unpack("12")

    def test_truncated_variable_value(self) -> None:
        schema = SubfieldSchema(
            [
                Subfield(
                    "a",
                    SubfieldType.BCD,
                    length_prefix=LengthPrefix(
                        LengthPrefixEncoding.BCD, size_bytes=1
                    ),
                )
            ]
        )
        # prefix "05" says 5 bytes; only 1 byte (2 chars) provided
        with pytest.raises(InvalidTLVError, match="Truncated value"):
            schema.unpack("0512")


class TestSchemaIntegrationWithCodec:
    """Schema output is consumable by Codec with value_type=BINARY."""

    def test_schema_payload_used_as_codec_value(self) -> None:
        from pytlv_codec import (
            Codec,
            CodecConfig,
            Encoding,
            Order,
            ValueType,
        )

        schema = SubfieldSchema(
            [
                Subfield("acquirer", SubfieldType.BCD, size_bytes=3),
                Subfield("currency", SubfieldType.ASCII, size_bytes=3),
            ]
        )
        payload_hex = schema.pack({"acquirer": "054497", "currency": "USD"})

        codec = Codec(
            CodecConfig(
                order=Order.LTV,
                tag_size=2,
                tag_encoding=Encoding.BCD,
                length_size=4,
                length_encoding=Encoding.BCD,
                value_type=ValueType.BINARY,
                length_includes_tag=True,
            )
        )

        encoded = codec.encode({"33": payload_hex})

        # Round trip
        decoded = codec.decode(encoded)
        assert decoded == {"33": payload_hex}

        # Then unpack subfields
        fields = schema.unpack(decoded["33"])
        assert fields == {"acquirer": "054497", "currency": "USD"}
