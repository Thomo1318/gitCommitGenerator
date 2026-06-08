import os
import sys

# Fallback typing if onepassword SDK is not installed
try:
    from onepassword import Client
except ImportError:
    Client = None

_op_client = None


def _get_op_client() -> Client | None:
    global _op_client
    if _op_client is not None:
        return _op_client
    if Client is None:
        return None

    op_token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not op_token:
        return None

    try:
        # The SDK takes the token via the authenticate() method
        _op_client = Client.authenticate(
            auth=op_token, integration_name="gitCommitGenerator", integration_version="0.1.7"
        )
        return _op_client
    except Exception as e:
        # Log but do not crash; fallback to missing secret behavior
        print(f"[Debug] 1Password SDK authentication failed: {e}", file=sys.stderr)
        return None


def resolve_secret(secret_key: str, default_value: str = "") -> str:
    """
    Resolve a secret value.
    1. Checks the local os.environ.
    2. Queries the 1Password SDK for the secret_key within the configured Environment ID.
    """
    # 1. Local environment injection or override
    val = os.environ.get(secret_key)
    if val:
        return val

    # 2. 1Password SDK Native Resolution
    client = _get_op_client()
    if not client:
        return default_value

    env_id = os.environ.get("GIT_CG_OP_ENV", "ce3a5m2atri7cxq7mdvofergt4")

    try:
        # Retrieve the item by its UUID
        item = client.items.get(env_id)

        # Search fields for the matching key
        for field in item.fields:
            if field.title == secret_key and field.value:
                return field.value
    except Exception as e:
        print(f"[Debug] Failed to fetch {secret_key} from 1Password item {env_id}: {e}", file=sys.stderr)

    return default_value
