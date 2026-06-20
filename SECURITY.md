# Security Policy

## Supported use

This project is designed to run locally on the user's own machine. The web UI
binds to `127.0.0.1` by default and should not be exposed directly to the
public internet.

## Reporting issues

Please open a GitHub issue for security-relevant bugs that do not expose
private data. If the issue includes sensitive details, share only a minimal
description publicly and coordinate privately with the repository owner.

## Out of scope

The following uses are not supported:

- Bypassing authentication, authorization, DRM, encryption, or paywalls.
- Downloading recordings the user is not authorized to access.
- Running this project as a public downloader service for third-party users.
- Storing or redistributing other people's match recordings.

## Local data

Successful downloads may be recorded in `~/Downloads/SosyalHaliSaha/downloads.jsonl`.
Downloaded videos, partial files, logs, virtual environments, and IDE settings
should not be committed to the repository.
