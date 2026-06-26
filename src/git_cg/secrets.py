import asyncio
import os
import sys

# Fallback typing if onepassword SDK is not installed
try:
    from onepassword import Client
except ImportError:
    Client = None

_op_cache = None

# Environment variable allow-list for libraries that cannot use resolve_secret()
ENV_EXPORT_ALLOWLIST = {
    "OPIK_API_KEY",
    "OPIK_WORKSPACE",
    "OPIK_BASE_URL",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OMLX_API_KEY",
    "OMLX_BASE_URL",
    "MTPLX_API_KEY",
    "MTPLX_BASE_URL",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
    "SENTRY_RELEASE",
}


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

    # Short-circuit to prevent 1Password rate-limiting (hammering) when invoked multiple times by hooks.
    # If the environment already has the necessary secrets (e.g. via .env), skip the O(N) vault fetch.
    opik_key = os.environ.get("OPIK_API_KEY")
    if opik_key and not opik_key.startswith("op://"):
        return

    async def fetch():
        """
        Fetch all accessible vault items from 1Password and populate the module cache and process environment with discovered field values.

        For each field that has a title and a non-empty value, stores the value in the module-level `_op_cache`. Only exports to `os.environ` if the field title is in ENV_EXPORT_ALLOWLIST. If no items are found, writes a debug message to stderr; if the fetch process fails, writes a debug error message to stderr.
        """
        try:
            client = await Client.authenticate(
                auth=op_token, integration_name="gitCommitGenerator", integration_version="0.1.7"
            )

            # Service accounts have scoped access. We load all fields from all accessible items
            # into the cache. Only export to os.environ for libraries that cannot use resolve_secret().
            vaults = await client.vaults.list()
            found_items = False
            for vault in vaults:
                try:
                    items = await client.items.list(vault.id)
                    for item_summary in items:
                        try:
                            item = await client.items.get(vault.id, item_summary.id)
                            found_items = True
                            for field in item.fields:
                                if field.title and getattr(field, "value", None):
                                    # Detect duplicate field titles and fail fast
                                    if field.title in _op_cache:
                                        raise ValueError(
                                            f"Duplicate field title '{field.title}' found in vault '{vault.id}' "
                                            f"item '{item_summary.id}'. This would cause silent overwrites. "
                                            f"Please ensure field titles are unique across all 1Password items."
                                        )
                                    _op_cache[field.title] = field.value
                                    # Only export to os.environ if explicitly allowed
                                    if field.title in ENV_EXPORT_ALLOWLIST:
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
    Resolve a secret value from the environment or cached 1Password fields.
    
    Parameters:
    	secret_key (str): The environment variable or field name to resolve.
    	default_value (str): The value to return when no secret is found.
    
    Returns:
    	str: The resolved secret value, or `default_value` when no matching value exists.
    """
    # 1. Local environment injection or override
    val = os.environ.get(secret_key)
    if val:
        return val

    # 2. 1Password SDK Native Resolution via Cache
    global _op_cache
    if _op_cache is None:
        _populate_cache()

    if _op_cache is not None and secret_key in _op_cache:
        return _op_cache[secret_key]

    return default_value
