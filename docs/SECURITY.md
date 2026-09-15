# Security and privacy baseline

- `Secrets.h`, `.env` and SQLite files are ignored; only examples are committed.
- MQTT messages are checked against their topic, `device_id`, required fields, event enum, slot range and sequence type.
- `(device_id, seq)` prevents duplicate event insertion and provides basic replay resistance; it is not cryptographic authentication.
- Commands are allow-listed; arbitrary JSON is never executed.
- Gateway logs only validation errors and never logs credentials.
- Heartbeat and last-seen status expose device availability.
- Demo patient identifiers are synthetic.
- MQTT credentials may be configured when the broker supports them.

Known limitations: no TLS, OAuth, PKI or per-user authorization. This is acceptable for a local classroom prototype and is not a production medical-security design.

The demo may use unauthenticated `test.mosquitto.org:1883`. It is public and suitable only for synthetic PB01 events; never send real patient data or credentials. Prefer a local authenticated broker for the classroom presentation when available.
