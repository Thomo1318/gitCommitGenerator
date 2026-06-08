#!/usr/bin/env bash
# Source the 1Password Environment directly into the current shell process in a zero-plaintext manner.
# We unset OP_SERVICE_ACCOUNT_TOKEN temporarily to fall back to the user's biometric session,
# because the beta CLI has limited support for reading Environments natively through Service Accounts.

ENV_ID="${GIT_CG_OP_ENV:-ce3a5m2atri7cxq7mdvofergt4}"
eval "$(env -u OP_SERVICE_ACCOUNT_TOKEN op environment read "$ENV_ID")"
exec "$@"
