# Hexage threat model

The user's `hexage.yaml` stores OAuth client parameters in plaintext in the
user profile. Tokens are stored separately in the system keychain or in process
memory. Snapshots and backups contain only container data.

The password protects the key phrase, and the key phrase protects the content.
An attacker who copies the file can test password guesses offline. Argon2id
raises the cost of each guess. Use a unique, long password. AES-GCM
authentication makes container modifications detectable. A genuine old snapshot
remains genuine, so comparison uses the encrypted revision history.

The plaintext header reveals the size, the algorithms, the parameters, and the
random cryptographic values. Cloud providers additionally see the fact of
transfer, the name, the size, the time, and the cloud file metadata. The
password, the key phrase, keys, notes, and history are never sent to providers
in plaintext. A provider can delete or hide a snapshot and show an available
older version. With a truncated history the ordering may be unknown.

Auto-lock triggers after five minutes without input events in the application.
It closes open editors, discards unsaved edits, and hides notes. A write request
already handed to a worker thread may still complete. Python, Tk, the clipboard,
system dumps, and swap may retain data. Hexage does not protect against malware
or another process with access to the unlocked computer. Changing the password
keeps the data key the same and does not revoke old copies.

Writing targets local filesystems that support atomic replacement and hard
links, such as NTFS and ext4. On Linux, new directories are created with mode
0700 and containers with mode 0600. Windows inherits the ACL of the profile
directory. Directory sync is performed on Linux. Inter-process locking
coordinates Hexage instances. An external process with write access can corrupt
or replace files. Containers and backups remain encrypted, and deleting a note
does not erase old snapshots.
