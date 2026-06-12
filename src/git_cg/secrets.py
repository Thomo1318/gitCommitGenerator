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
    """
    Populate the module-level 1Password cache and mirror discovered secret fields into environment variables.
    
    If the 1Password SDK is unavailable or OP_SERVICE_ACCOUNT_TOKEN is not set, the function returns without side effects. Otherwise it authenticates using the service account token, iterates all accessible vaults and items, and for every item field that has a title and a non-empty value stores that value in the module cache `_op_cache` and sets the corresponding process environment variable. If no items are found or an error occurs during fetching, a debug message is printed to stderr.
    """
    global _op_cache
    _op_cache = {}

    if Client is None:
        return

    op_token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not op_token:
        return

    async def fetch():
        """
        Fetch all accessible vault items from 1Password and populate the module cache and process environment with discovered field values.
        
        For each field that has a title and a non-empty value, stores the value in the module-level `_op_cache` and sets the same key in `os.environ`. If no items are found, writes a debug message to stderr; if the fetch process fails, writes a debug error message to stderr.
        """
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
