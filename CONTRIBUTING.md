# Contributing

Thanks for considering a contribution to `pytlv-codec`.

## Development setup

```bash
git clone https://github.com/jacobdarrossi/pytlv-codec.git
cd pytlv-codec
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quality gates

The CI pipeline runs all of these on every push and pull request:

```bash
ruff check .                        # lint
ruff format --check .               # formatting
mypy src/pytlv_codec                # type check (strict)
pytest                              # tests
```

Before submitting a PR, please make sure the same commands pass locally.

## Pull requests

1. Open an issue first to discuss anything beyond a small fix.
2. Add tests for any new behavior or fix.
3. Update `CHANGELOG.md` under the `[Unreleased]` section.
4. Make sure all quality gates pass locally.
5. Keep PRs focused — one logical change per PR.

## Releases

Releases are automated via GitHub Actions. To cut a new version:

1. Bump the version in `pyproject.toml` and `src/pytlv_codec/__init__.py`.
2. Move `[Unreleased]` entries in `CHANGELOG.md` under the new version.
3. Commit, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. GitHub Actions builds the distribution and publishes to PyPI via trusted publishing.

## Code of conduct

Be respectful. Keep technical discussion on technical merit.
