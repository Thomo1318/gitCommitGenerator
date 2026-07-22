import os

import opik

from git_cg.main import ENGINE_REGISTRY, build_system_prompt, generate_commit_message, get_ai_client

client = opik.Opik()
dataset = client.get_dataset(name="commit-message-eval")
items = dataset.get_items()

if not items:
    print("Dataset is empty!")
    exit(1)

print(f"Got {len(items)} items in dataset.")
item = items[0]

diff_output = item.get("diff_output", "") if isinstance(item, dict) else getattr(item, "diff_output", "")
system_prompt = build_system_prompt(diff_output, verbose=False)

engine = os.environ.get("GIT_CG_ENGINE", "mtplx")
ai_client = get_ai_client(engine)

engine_config = ENGINE_REGISTRY.get(engine.lower())
prefix = engine_config.prefix if engine_config else "OMLX"
model_name = os.environ.get(f"{prefix}_MODEL", os.environ.get("OMLX_MODEL", "default"))

print(f"Generating commit with model {model_name} on engine {engine}...")
commit_plan = generate_commit_message(
    client=ai_client, diff_output=diff_output, model_name=model_name, system_prompt=system_prompt
)

print("Generation complete.")
print(commit_plan.render())
