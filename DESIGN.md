# Hexage implementation

1. Freeze the format and the recovery policy.
2. Implement the codec, atomic writing, and the desktop interface.
3. Connect file exchange to revision comparison.
4. Connect separate OAuth and cloud exchange adapters.
5. Verify the format, write failures, and Tk behavior on Windows and Linux.

| Snapshot state | Recovery from a file or the cloud |
| --- | --- |
| Active file is missing | Confirm installation |
| Revision and content match | Already up to date |
| Revision matches, content differs | Reject |
| Ancestor | Confirm rollback with a backup |
| Descendant with a later date | Confirm replacement with a backup |
| Divergence, contradictory clocks, or unknown order | Show the reason, request confirmation of replacement with a backup |
| Different vault | Confirm replacement with a backup |
| Open failure | Reject |

## Format 1

Big-endian byte order. The header is 57 bytes, Python struct
`>4sBBBIBB16s12s12sI`. Fields in order: ASCII `HXGE`, version 1, cipher 1
(AES-256-GCM), KDF 1 (Argon2id v19), memory in KiB (u32), passes and lanes
(u8 each), salt, two nonces, and the length of the second ciphertext with tag
(u32). The admissible v1 read profile is fixed: 65536 KiB, 3 passes, 4 lanes.
Salt is 16 bytes, nonce 12 bytes, tags 16 bytes. Next come 60 bytes of the
wrapped key phrase and the data ciphertext up to the end of the file. The
maximum file size is 16 MiB.

The password is encoded as UTF-8 without normalization, from 1 to 65536 bytes.
Argon2id derives 32 bytes for encrypting the key phrase. The key phrase is
32 random bytes in canonical Base64URL with padding. HKDF-SHA-256 derives
32 bytes for the data from the original 32 bytes, without an explicit salt,
with info `Hexage/v1/data-key`. The key phrase AAD is ASCII `Hexage/v1/wrap`
plus the full header. The data AAD is ASCII `Hexage/v1/data`, the full header,
and the wrapped key phrase. On every write both operations receive fresh
nonces; when the password changes, a salt is generated as well. The data key
is preserved.

The data is JSON in UTF-8. Fields `vault`, `revision`, `ancestors`, `changed`,
`notes`. Identifiers are 32 lowercase hexadecimal characters. The history holds
up to 256 ancestors, from the nearest to the oldest. The date format is
`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`. A note contains `id`, `title`, and `text`.
Up to 10000 notes, a title of up to 4096 UTF-8 bytes, and text of up to
4194304 UTF-8 bytes.

## Integration verification

Google documents the Desktop client, loopback, S256, and `drive.appdata` with
the `appDataFolder` parent.
[OAuth](https://developers.google.com/identity/protocols/oauth2/native-app)
[Drive](https://developers.google.com/workspace/drive/api/guides/appdata)

Yandex documents the registered Redirect URI, state validation, and PKCE. In
the help, exchanging a code with PKCE may omit the secret. The minimum Disk
permission is `cloud_api:disk.app_folder`. Disk downloads respond with a 302 to
`*.storage.yandex.net`, while Drive responds with a 302 to
`*.googleusercontent.com`. Hexage follows redirects only within the provider's
domains, without transmitting the token, and no more than five hops.
[OAuth](https://yandex.ru/dev/id/doc/en/codes/code-url)
[Folder permission](https://yandex.ru/dev/api360/doc/ru/ref/ServiceApplicationsService/ServiceApplicationsService_Create)
[Disk API](https://yandex.ru/dev/disk/rest/)

The KDF profile is taken from RFC 9106. cryptography is used for AES-GCM and
HKDF, argon2-cffi for Argon2id, and Tk 8.6 for the UI.
[RFC](https://www.rfc-editor.org/rfc/rfc9106.html#section-7.4)
[Tkinter](https://docs.python.org/3/library/tkinter.html)
