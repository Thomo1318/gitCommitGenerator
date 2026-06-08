import asyncio
import os

from onepassword import Client


async def test():
    token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not token:
        print("No token")
        return
    client = await Client.authenticate(auth=token, integration_name="gitCommitGenerator", integration_version="0.1.7")
    vaults_iter = await client.vaults.list()
    print("Vaults:", vaults_iter)
    vault_list = [v async for v in vaults_iter]
    print("Vault list", vault_list)
    env_id = "ce3a5m2atri7cxq7mdvofergt4"
    for v in vault_list:
        print("Trying vault:", v.id)
        try:
            item = await client.items.get(v.id, env_id)
            print("Item found!", item.title)
            for f in item.fields:
                print(f.title, f.value)
            break
        except Exception as e:
            print("Not in vault", v.id, e)


asyncio.run(test())
