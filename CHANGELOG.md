# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.1] — 2026-05-06

### Removed
- `LengthMeasure` enum and `length_counts` field on `CodecConfig`. Length is now always counted in bytes-on-wire (the previous default and only supported value). The flag and unsupported-config guard added unnecessary surface area for a feature that wasn't needed yet. Will be reintroduced as a non-breaking enum addition if a real protocol case requires logical-units counting.

### Changed
- Cleanup of related guard logic in `Codec`. No behavior change for users not setting `length_counts` (the only previously valid value).

## [0.3.0] — 2026-05-06

### Added
- `SubfieldSchema` for schema-driven pack/unpack of structured TLV values.
- `Subfield`, `LengthPrefix`, `SubfieldType`, `LengthPrefixEncoding` public types.
- Support for fixed-size and variable-length subfields with `[length-prefix][value]` layout.
- Natural ↔ hex conversion for BCD digits, ASCII text, and BINARY hex chars.
- Length prefix encodings: BCD, ASCII, and BINARY.
- 36 new tests covering schema scenarios (86 total, all passing).
- README extended with schema-driven payload example.

## [0.2.0] — 2026-05-06

### Added
- `Order.LTV` (length-then-tag-then-value) layout.
- `length_includes_tag` flag for LTV variants where length covers tag + value.
- Encodings for tag/length: ASCII, BCD, HEX, BINARY.
- `ValueType.BINARY` length calculation (value string is hex repr; length = bytes).
- Encoding-aware alphabet validation for tags and values.

## [0.1.0] — 2026-05-05

### Added
- Initial release with basic ASCII TLV codec.
- `CodecConfig` with full design surface.
- Custom exception hierarchy: `PytlvError`, `InvalidTLVError`, `EncodingError`, `UnsupportedConfigError`.
- 7 tests covering single TLV, multiple TLVs, roundtrip, and empty value handling.
- Tooling: ruff, mypy strict, pytest, hatchling.
- MIT license, README with quick start and config example.
