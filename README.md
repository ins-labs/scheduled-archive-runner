# Scheduled archive runner

Generic private-configuration archive verification code. No source identities, namespace values, remote account identities or destination paths are included in this repository.

Dependencies are locked. Workflows accept one encrypted configuration secret and never upload data as artifacts or caches. Only manual and clock triggers are permitted. The clock template is deliberately not enabled pending privacy audit and commissioning.

Each run checks read-only source privileges, creates an encrypted archive, uploads it to private remote storage and verifies the readback. A disposable local restore checks records and required indexes when due. Encrypted private receipts retain last successful operation and restore timestamps across fresh runners. Retention touches only matching configured archive names after verified upload. Receipt pruning is not enabled.

No source writes, account upgrades or public storage links are made. Failure messages are generic. Local working files are removed on exit. Logs and workflow metadata will be public if this repository becomes public. Runtime configuration belongs only in encrypted secrets, never repository variables.

A separate monitor must check private receipts for operation age over 26 hours and restore age over 8 days, and alert on inaccessible state. A workflow cannot reliably detect that its own schedule never fired.

The slot 2 feasibility probe workflow is manually triggered to fetch an operator-configured page URL from repository secret `SLOT_2_PROBE_URL`. It records only the HTTP status code and response byte count to step output and job summary without storing or logging page identity, content, or media.
