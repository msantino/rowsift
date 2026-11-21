# Security

## Report a vulnerability

**Do not open a public issue for a vulnerability.**

Use GitHub's private reporting: on the **Security** tab of this repository, choose **Report a vulnerability**. The report reaches the maintainer only.

Include what you can: what the vulnerability allows, how to reproduce it, and the rowsift and Python versions. If a file is needed to reproduce it, build one with invented data.

You get an answer within 7 days. Please do not disclose the problem before a fix is available.

## What is in scope

rowsift parses files that come from untrusted people. These are treated as vulnerabilities:

- a file that makes the library use memory or time far beyond its documented limits, such as a compressed workbook that expands to a very large size;
- a file that makes the library read, write or execute anything outside the bytes it was given;
- personal data that ends up in an exception message, a log line or a report when the documentation says it is masked.

A wrong parsing result with no security consequence is a bug: open a regular issue.

## Supported versions

Only the latest released version receives security fixes.
