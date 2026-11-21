# Contributing

This guide explains how to report a problem, suggest a change and send code.

## Report a problem

Open an [issue](https://github.com/msantino/rowsift/issues) with:

- what you did, what you expected and what happened;
- the rowsift version and the Python version;
- the smallest file that reproduces it.

**Never attach real data.** A file that reproduces a reading problem almost never needs real names, phone numbers or tax ids. Replace them with invented values that keep the same shape: the same number of digits, the same separators, the same encoding. Tax ids used in examples must be invented and must not belong to anyone.

A vulnerability is reported in private, as described in [SECURITY.md](SECURITY.md), never in a public issue.

## Suggest a change

Open an issue that describes the file or the value you could not handle, before describing the solution. A sample that fails is the most useful thing a suggestion can carry.

## Send code

1. Open or comment on an issue before starting anything larger than a small fix.
2. Fork the repository, branch from `main` and open a pull request.
3. A pull request does one thing and says why.
4. Commits follow [Conventional Commits](https://www.conventionalcommits.org/) (`fix(read): keep the BOM out of the first header`). Pull requests are squashed on merge.

### Rules

- **No silent guesses.** A value that cannot be normalized with certainty is returned with a reason, not corrected.
- **No user-facing text.** Reasons are codes with data. Messages belong to the application.
- **No framework and no storage.** The library takes bytes and values and returns values.
- **Every behavior has a test, and every file format quirk has a fixture.** Fixtures are synthetic: they are written for the test and contain no real person's data.
- **Typed public API.** `mypy --strict` passes on `src` and `tests`.
- **Plain sentences.** Do not use the em dash character in any file.

### Run it locally

You need [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/).

```bash
just setup
just verify    # lint, type check, tests, text check and build
just fmt       # apply the formatter and the safe lint fixes
```

A pull request is merged only with `just verify` passing. CI runs the same recipe on every supported Python version.

## License of contributions

rowsift is distributed under the [Apache License 2.0](LICENSE). By sending a contribution you state that:

1. the contribution is yours, or you have the right to send it ([Developer Certificate of Origin 1.1](https://developercertificate.org/)). Sign your commits with `git commit -s`;
2. you license it under the Apache License 2.0, as section 5 of the license describes.

## Conduct

Be respectful. Technical disagreement is welcome, personal attacks are not. The maintainer may moderate comments and close discussions that leave that line.
