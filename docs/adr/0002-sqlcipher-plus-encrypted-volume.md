# SQLCipher database and an encrypted volume, both required

The owner asked for a high security bar on a product anyone installs. The store is SQLCipher (via `sqlcipher3`, which ships wheels for Linux, macOS and Windows) with AES-GCM blobs, and install refuses an unencrypted volume; an inconclusive check needs a recorded owner attestation. Plain SQLite on full-disk encryption alone was rejected because copies and backups would be plaintext.
