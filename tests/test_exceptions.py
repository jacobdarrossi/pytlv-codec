"""Tests for the custom exception hierarchy."""

import pytest

from pytlv_codec import (
    Codec,
    CodecConfig,
    EncodingError,
    InvalidTLVError,
    LengthMeasure,
    Order,
    PytlvError,
    UnsupportedConfigError,
)


class TestExceptionHierarchy:
    """Custom exceptions inherit from PytlvError + relevant built-ins."""

    def test_invalid_tlv_is_pytlv_error(self) -> None:
        assert issubclass(InvalidTLVError, PytlvError)

    def test_invalid_tlv_is_value_error(self) -> None:
        assert issubclass(InvalidTLVError, ValueError)

    def test_encoding_error_is_pytlv_error(self) -> None:
        assert issubclass(EncodingError, PytlvError)

    def test_encoding_error_is_value_error(self) -> None:
        assert issubclass(EncodingError, ValueError)

    def test_unsupported_config_is_pytlv_error(self) -> None:
        assert issubclass(UnsupportedConfigError, PytlvError)

    def test_unsupported_config_is_not_implemented_error(self) -> None:
        assert issubclass(UnsupportedConfigError, NotImplementedError)


class TestEncodingErrors:
    """Errors raised during encode."""

    def test_tag_with_wrong_size_raises_encoding_error(self) -> None:
        codec = Codec(CodecConfig())  # tag_size=2

        with pytest.raises(EncodingError, match="Tag 'X' has length 1, expected 2"):
            codec.encode({"X": "value"})

    def test_empty_value_when_disallowed_raises_encoding_error(self) -> None:
        codec = Codec(CodecConfig(allow_empty_value=False))

        with pytest.raises(EncodingError, match="Empty value not allowed"):
            codec.encode({"01": ""})

    def test_value_too_long_raises_encoding_error(self) -> None:
        codec = Codec(CodecConfig(length_size=2))  # max length 99

        with pytest.raises(EncodingError, match="Length 100 exceeds maximum"):
            codec.encode({"01": "x" * 100})

    def test_tag_with_invalid_char_raises_encoding_error(self) -> None:
        codec = Codec(CodecConfig())  # ASCII default → alphanumeric

        with pytest.raises(EncodingError, match="invalid character"):
            codec.encode({"0!": "value"})  # '!' is not alphanumeric

    def test_tag_with_space_raises_encoding_error(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(EncodingError, match="invalid character"):
            codec.encode({"0 ": "value"})  # space is not alphanumeric

    def test_tag_alphanumeric_accepted(self) -> None:
        codec = Codec(CodecConfig())

        # both numeric and letter tags should work for ASCII encoding
        codec.encode({"AB": "value"})  # should not raise
        codec.encode({"99": "value"})  # should not raise
        codec.encode({"A1": "value"})  # mixed should also work


class TestDecodingErrors:
    """Errors raised during decode."""

    def test_truncated_tag_raises_invalid_tlv(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(InvalidTLVError, match="Truncated tag"):
            codec.decode("0")  # only 1 char, tag needs 2

    def test_truncated_length_raises_invalid_tlv(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(InvalidTLVError, match="Truncated length"):
            codec.decode("05")  # tag OK, length needs 4 more

    def test_truncated_value_raises_invalid_tlv(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(InvalidTLVError, match="Truncated value"):
            codec.decode("050010abc")  # length=10 but only 3 chars after

    def test_invalid_length_raises_invalid_tlv(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(InvalidTLVError, match="Invalid length"):
            codec.decode("05XXXXabcd")  # length not numeric

    def test_duplicate_tag_raises_invalid_tlv(self) -> None:
        codec = Codec(CodecConfig(allow_duplicate_tags=False))

        with pytest.raises(InvalidTLVError, match="Duplicate tag"):
            codec.decode("050003abc050003def")


class TestUnsupportedConfig:
    """UnsupportedConfigError raised for current limits."""

    def test_logical_units_length_measure_raises_unsupported_config(self) -> None:
        codec = Codec(CodecConfig(length_counts=LengthMeasure.LOGICAL_UNITS))

        with pytest.raises(UnsupportedConfigError, match="length_counts=logical_units"):
            codec.encode({"01": "x"})


class TestExceptionsCanBeCaughtGenerically:
    """Multiple inheritance: existing generic handlers still work."""

    def test_encoding_error_caught_as_value_error(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(ValueError):
            codec.encode({"X": "value"})

    def test_invalid_tlv_caught_as_value_error(self) -> None:
        codec = Codec(CodecConfig())

        with pytest.raises(ValueError):
            codec.decode("0")

    def test_unsupported_config_caught_as_not_implemented(self) -> None:
        codec = Codec(CodecConfig(length_counts=LengthMeasure.LOGICAL_UNITS))

        with pytest.raises(NotImplementedError):
            codec.encode({"01": "x"})

    def test_all_caught_as_pytlv_error(self) -> None:
        codec_a = Codec(CodecConfig())
        codec_b = Codec(CodecConfig(length_counts=LengthMeasure.LOGICAL_UNITS))

        with pytest.raises(PytlvError):
            codec_a.encode({"X": "value"})
        with pytest.raises(PytlvError):
            codec_a.decode("0")
        with pytest.raises(PytlvError):
            codec_b.encode({"01": "x"})
