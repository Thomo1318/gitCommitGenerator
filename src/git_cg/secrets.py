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

            # Service accounts have scoped access. We load all fields from all accessible items
            # directly into the environment so dependencies like Opik can initialize correctly.
            vaults = await client.vaults.list_all()
            found_items = False
            for vault in vaults:
                try:
                    items = await client.items.list_all(vault.id)
                    for item_summary in items:
                        try:
                            item = await client.items.get(vault.id, item_summary.id)
                            found_items = True
                            for field in item.fields:
                                if field.title and getattr(field, "value", None):
                                    _op_cache[field.title] = field.value
                                    os.environ[field.title] = field.value
                        except Exception:
                            continue
                except Exception:
                    continue

            if not found_items:
                print("[Debug] 1Password SDK: No items found in any accessible vault.", file=sys.stderr)

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
