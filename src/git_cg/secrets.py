import asyncio
import os
import sys

# Fallback typing if onepassword SDK is not installed
try:
    from onepassword import Client
except ImportError:
    Client = None

_op_cache = None


def _populate_cache():
    global _op_cache
    _op_cache = {}

    if Client is None:
        return

    op_token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not op_token:
        return

    async def fetch():
        try:
            client = await Client.authenticate(
                auth=op_token, integration_name="gitCommitGenerator", integration_version="0.1.7"
            )
            env_id = os.environ.get("GIT_CG_OP_ENV", "ce3a5m2atri7cxq7mdvofergt4")

            vaults = await client.vaults.list()
            item = None
            for vault in vaults:
                try:
                    item = await client.items.get(vault.id, env_id)
                    break
                except Exception:
                    continue

            if item:
                for field in item.fields:
                    if field.title and getattr(field, "value", None):
                        _op_cache[field.title] = field.value
            else:
                print(f"[Debug] 1Password SDK fetch failed: Item {env_id} not found in any vault.", file=sys.stderr)
        except Exception as e:
            print(f"[Debug] 1Password SDK fetch failed: {e}", file=sys.stderr)

    asyncio.run(fetch())


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

    # 2. 1Password SDK Native Resolution via Cache
    global _op_cache
    if _op_cache is None:
        _populate_cache()

    if secret_key in _op_cache:
        return _op_cache[secret_key]

    return default_value
