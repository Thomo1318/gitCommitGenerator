import asyncio
import os

from onepassword import Client


async def test():
    token = os.environ.get("OP_SERVICE_ACCOUNT_TOKEN")
    if not token:
        print("No token")
        return
    client = await Client.authenticate(auth=token, integration_name="gitCommitGenerator", integration_version="0.1.7")
    print("Client:", client)
    item = await client.items.get("ce3a5m2atri7cxq7mdvofergt4")
    print("Item fields:", len(item.fields))
    for f in item.fields:
        print(f.title)


asyncio.run(test())
