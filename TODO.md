# Roadmap & Tasks

> [!TIP]
>
> ### Use **`GitHub Flavored Markdown (GFM) Alerts`** when reviewing this document.
>
> There are exactly 5 of these alert types available, and each renders with a distinct color and icon on platforms that support them (like GitHub, and modern markdown viewers).
>
> Both the codeblock and an example are provided for each of the 5 below. This is what the different markdown renderers (if supported) will display for each alert type:

1. **`[!NOTE]`** (Blue)
   Highlights information that users should take into account, even when skimming.

   ```markdown
   > [!NOTE]
   > This is a note alert.
   ```

   > [!NOTE]
   > This is a note alert.

2. **`[!TIP]`** (Green)
   Optional information to help a user be more successful (e.g., best practices, shortcuts).

   ```markdown
   > [!TIP]
   > This is a tip alert.
   ```

   > [!TIP]
   > This is a tip alert.

3. **`[!IMPORTANT]`** (Purple)
   Crucial information necessary for users to succeed or understand the context.

   ```markdown
   > [!IMPORTANT]
   > This is an important alert.
   ```

   > [!IMPORTANT]
   > This is an important alert.

4. **`[!WARNING]`** (Yellow)
   Critical content demanding immediate user attention due to potential risks.

   ```markdown
   > [!WARNING]
   > This is a warning alert.
   ```

   > [!WARNING]
   > This is a warning alert.

5. **`[!CAUTION]`** (Red)
   Negative potential consequences of an action (e.g., data loss, breaking changes).

   ```markdown
   > [!CAUTION]
   > This is a caution alert.
   ```

   > [!CAUTION]
   > This is a caution alert.

   <blockquote>
   <p>
   This can also be used for notes, tips, warnings, cautions, important info, etc as well as what is listed above. It just renders different!
   </p>
   </blockquote>

## All 5 together:

> [!NOTE]
> This is a note alert.

> [!TIP]
> This is a tip alert.

> [!IMPORTANT]
> This is an important alert.

> [!WARNING]
> This is a warning alert.

> [!CAUTION]
> This is a caution alert.

---

> [!NOTE]
> The primary backlog has been formally migrated to [GitHub Issues](https://github.com/Thomo1318/gitCommitGenerator/issues) to provide better visibility, tracking, and collaboration. However, the migration is not yet fully complete, and some active implementation features may still be added and temporarily tracked in this file before being transitioned.

---

TODO:

- Determine how difficult it would be to rename the tool ACE (A.C.E) "Automatic Commit Engine"

---

Review [git-pkgs](https://github.com/git-pkgs) and determine if its tools could improve `git-cg`

---

Review [OpenLore](https://github.com/clay-good/OpenLore) and identify if there are features we should consider integrating into our tool, could we include `OpenLore` in our tool, compare it to existing similar tools, document the findings.

---

- Consider creating a [Gradio](https://gradio.app/) integration

---

- Determine a solution to integrate this action:
  - on/off/custom (`if blast radius >x` or `if review identifies risk >x`, etc.), ? Other scenarios?
  - If `git-cg` is running in `hook-mode` and it is identified that the action requires user interaction (determine use cases) alert the user (? Use `alerter` so the user can interact by clicking yes/no/other) that then pops open the TUI for the user to act, scenarios like confirming a split commit, acknowledging a high risk item or blast radius, etc.

---

- Review [fitinprogress](https://open-vsx.org/vscode/item?itemName=YusukeAbe.gitinprogress) to identify features to include in `git-cg`

- With the planned config integration make the majority of the app's functions be able to toggle on/off
- Identify possible functions that we should consider integrating with this feature
- Your own push:

self-hosted ntfy, or Pushover

? Integrate to alert user when actions have completed e.g. PR review, commit generation, user intervention required, etc.
In the Secure Enclave:

Your API keys sit in the hardware-backed iOS keychain and are sent only to the service that needs them.
? Use KeyChain for auth in `gitCommitGenerator`

---

- Determine the best solution regarding [ThermalForge](https://github.com/ProducerGuy/ThermalForge). We need to look at all issues and PRs from other users and determine if we should fork the official version and then update the forked version to include the fixes proposed by other devs. We should also check if there is an ETA on when the official tool will be updated and if it would be worth the wait. This should be done and documented in a new issue. This could also be the place where we decide to abandon our forked version and just use the official tool, or move to a different tool (which is not an ideal solution as MTPLX uses it within its code to monitor temps and alter fan speeds depending on live chip temperatures). The reason I raise this point is that the official [ThermalForge](https://github.com/ProducerGuy/ThermalForge) has not been updated since `20 April 2026` and there are several issues and PRs that have been opened since then that have not been addressed. Document the findings in `scratch/reviews/ADR-0005_Review/Review/thermalforge_update_assessment.md`.

---

- Determine if we should integrate [wrkflw](https://github.com/bahdotsh/wrkflw) or an alternate tool (identify any others, or possibly some we already have locally or are using, for example does `hk` have this capability?) to test our GitHub Actions workflows locally before pushing to GitHub.

---

- Determine if tools like [apfel GitHub](https://github.com/Arthur-Ficial/apfel) [apfel Official Site](https://apfel.franzai.com/), [afm-Server](https://github.com/Techopolis/afm-Server), [apple-intelligence-cli](https://github.com/onmyway133/apple-intelligence-cli), [iClaw](https://github.com/lastByteLLC/iclaw/) (check this ones routing and determine if it could be used in our tool, this applies to all proposed tools). Additionally, we need to review this [Apple Intelligence - Foundation Models Documentation](https://developer.apple.com/documentation/foundationmodels) and determine if we could integrate `Apple Intelligence` (our custom integration rather than using one of the listed tools) into our app which could run along-side of our primary LLM solution (`MTPLX`) rather than either running a second instance of `MTPLX`, an `oMLX` instance or agent swaps in `MTPLX`. If they are light enough they may possibly be used for `_cheap_llm_call` or other lightweight tasks. This would need to be `opt-in`/`opt-out` for users not on an `Apple` device or on an `Apple` device that is not compatible with `Apple Intelligence` (this would include the macOS version, `M Series Chip` and `apple Intelligence` compatible and installed).

- Check the following for potential integration along with any additional apple tools (Confirmed to exist on Apple's Developer site):
  - Apple Intelligence tools:
    - [Apple Intelligence and Machine Learning](https://developer.apple.com/documentation/technologyoverviews/ai-machine-learning)
      - **[AI & Machine Learning Resources](https://developer.apple.com/machine-learning/resources/) Review this in detail!**
      - **[Generative Models](https://developer.apple.com/documentation/technologyoverviews/generative-models) Review this in detail!**
      - [Built-in Intelligence](https://developer.apple.com/documentation/technologyoverviews/built-in-intelligence)
      - [Apple Intelligence](https://developer.apple.com/documentation/technologyoverviews/apple-intelligence)
    - [AppIntents](https://developer.apple.com/documentation/AppIntents)
    - [App Intents Testing (Beta)](https://developer.apple.com/documentation/AppIntentsTesting)
    - [Core AI](https://developer.apple.com/documentation/CoreAI)
    - [Evaluations](https://developer.apple.com/documentation/Evaluations)
    - [Foundation Models](https://developer.apple.com/documentation/FoundationModels)
    - [Visual Intelligence](https://developer.apple.com/documentation/VisualIntelligence)
    - [Media Intelligence](https://developer.apple.com/documentation/MediaIntelligence)
  - Other Apple Frameworks and tools:
    - [Core Foundation](https://developer.apple.com/documentation/CoreFoundation)
    - [Apple silicon](https://developer.apple.com/documentation/apple-silicon)
    - [Background Tasks](https://developer.apple.com/documentation/BackgroundTasks)
    - [Latent Semantic Mapping](https://developer.apple.com/documentation/LatentSemanticMapping)
    - [ML Compute](https://developer.apple.com/documentation/MLCompute)
      > [!IMPORTANT]
      > ML Compute is deprecated. Instead, use BNNS for CPU tasks, Metal Performance Shaders for GPU work, and Core ML for tensor APIs.
      - [BNNS](https://developer.apple.com/documentation/Accelerate/BNNS)
      - [Metal Performance Shaders](https://developer.apple.com/documentation/MetalPerformanceShaders)
      - [Core ML](https://developer.apple.com/documentation/CoreML)
    - [Uniform Type Identifiers](https://developer.apple.com/documentation/UniformTypeIdentifiers)
    - [Accelerate Framework](https://developer.apple.com/documentation/Accelerate)
    -
  - Not confirmed if real as they were an AI generated list and not verified on Apple's developer site.
    - [ML Compute](https://developer.apple.com/documentation/mlcompute)
    - [Model ContextKit](https://developer.apple.com/documentation/modelcontextkit)
    - [Model Evaluation](https://developer.apple.com/documentation/modelevaluation)
    - [Model Utilities](https://developer.apple.com/documentation/modelutilities)
    - [ModelBuilder](https://developer.apple.com/documentation/ModelBuilder)
    - [ModelIO](https://developer.apple.com/documentation/ModelIO)
    - [NaturalLanguage](https://developer.apple.com/documentation/naturallanguage)
    - [PerformanceMetrics](https://developer.apple.com/documentation/performancemetrics)
    - [QuickLook](https://developer.apple.com/documentation/quicklook)
    - [Realms (Swift)](https://developer.apple.com/documentation/realms)
    - [TextKit 2](https://developer.apple.com/documentation/textkit2)
    - [Vision](https://developer.apple.com/documentation/vision)
  - Apple Tech Notes Page:
    - [Technotes](https://developer.apple.com/documentation/Technotes)

- Determine if [Metrickit](https://developer.apple.com/documentation/MetricKit) could be used to gather metrics for our `git-cg` and if so, determine what metrics we should track and how we should use them to improve the tool (and if we need to). Additionally, we should review [Mozilla Telemetry](https://github.com/mozilla/telemetry) for any other ideas or tools we could use to gather metrics for our `git-cg`.

- Consider integrating [CVE Bin Tool](https://github.com/ossf/cve-bin-tool) to complete a scan of the binary if we decide to compile this into a binary for release.

- We need to carefully consider if we need to track **any** metrics at all, should we really be tracking this information for open source software, doesn't this violate some kind of privacy principle, even if we aggregate it and anonymize it... what is the risk of PII being leaked... or do we remove the tracking from the prod app and only collect metrics from either my local development or another developer who opts in?

- [ ] **Feature Intelligent / Automated AI Commit Grouping**
  - **Problem**: When a user has a massive diff containing multiple logical features, extracting a single commit message is inaccurate and poor practice. The current plan of "manual staging" (`git-cg stage`) is useful but still places the cognitive burden of grouping on the user.
  - **Proposed Solutions for Investigation**:
    - **Method 1: Pre-Flight AI Grouping (Highly Recommended)**: Run a fast, cheap LLM call (e.g., Haiku or Qwen) using only the `git status` output and branch name. The LLM returns a JSON payload of logically grouped files and suggested commit titles. The TUI presents these to the user for one-click processing, keeping token costs near-zero.

    Before extracting the massive, token-heavy `git diff`, we run a very cheap, high-speed LLM call (perhaps using a smaller/faster model) with just the output of `git status` and the current branch name.
    - **How it works:** We prompt the LLM: "Here is a list of modified files and the branch name. Group them into logical, deployable commits and suggest a short title for each. Return as JSON."
    - **The Workflow:** The tool presents these groups to you in the TUI:

    ```text
    🧠 git-cg has identified 3 logical commits:
    1. [Code] Sentry Integration (8 files)
    2. [Tooling] Promptfoo Sync Script (2 files)
    3. [Docs] VizVibe Context Map (1 file)

    ❯ Process Group 1
    Process All Sequentially
    Manually adjust groups
    ```

    - **Why it's great:** It costs almost nothing in tokens because it only reads file paths, not the full code diffs, yet file names and branch context are usually enough to deduce logical groupings (exactly how I just did it for you).

    - **Method 2: Heuristic / Path-Based Clustering (Deterministic Fallback)**: Cluster files natively in Python based on heuristics like file extension (e.g., all `.md` together) or directory proximity (`src/git_cg` and `tests/git_cg`). Fast and zero-inference.

      If the user is offline or wants to avoid extra LLM calls, we can implement Python-native clustering logic.
      - **How it works:** We group files based on heuristics like:
        - **File Extension:** All `.md` files in one commit, all `.py` files in another.
        - **Directory Proximity:** If changes are in `src/git_cg/` and `tests/`, group them by feature suffix.
        - **Filename matching:** e.g., Grouping `telemetry.py` with `test_telemetry.py`.
      - **Why it's great:** It's instantaneous and requires zero AI inference, fulfilling your TODO.md note about wanting to easily split code from documentation.

    - **Method 3: Delta Context Chunking (Advanced)**: Use AST parsing or a tool like `difftastic` to identify files that actually share code dependencies, ensuring intermediate commits don't break the build.

      If a user has a massive 50+ file monorepo update, even file paths might not be enough context.
      - **How it works:** We use a tool like difftastic or AST parsing to identify which files actually share code dependencies (e.g., "File A imported the new function from File B, so they must be committed together to prevent breaking the build").
      - **Why it's great:** It prevents "broken" intermediate commits where a test is committed without the code it tests.

- [ ] **Feature: PR Description Generation using CodeRabbit Walkthroughs**
  - **Problem**: Generating PR descriptions from raw code diffs is contextually heavy and often produces overly granular or poorly abstracted text.
  - **Solution**: Implement a new `git-cg --pr-desc` command that queries the GitHub API to fetch the most recent CodeRabbit automated review comment (specifically the Walkthrough and Changes table) for the current branch/PR.
  - **Implementation**: Feed the CodeRabbit high-level summary (alongside the issue tracker requirements) into the LLM as context. Instruct the LLM to synthesize this pre-abstracted human-readable summary into a standard PR Description (Summary, Problem, Changes, Impact, Testing).
  - **Benefits**: Yields significantly higher quality PR descriptions with minimal token usage by leveraging the architectural abstractions already generated by CodeRabbit.

- [ ] **Feature: Eliminate Node.js Dependency from the Project**
  - **Problem**: The project relies on Node.js and a `package.json` file exclusively for running `scripts/validateCommitHook.mjs` during the `commit-msg` git hook phase, and generating Markdown Table of Contents via `doctoc`.
  - **Solution**: Replace both of these dependencies with Python-native equivalents to fully consolidate the repository into a pure Python/uv ecosystem.
  - **Implementation**:
    - [ ] Create `src/git_cg/validate.py` and a `git-cg validate` CLI command to natively handle commit syntax validation, trailer checks, and issue reference validation by reading `gitops_agent_sop.json`.
    - [ ] Update `hk.pkl` to run `uv run python -m git_cg.main validate "{{commit_msg_file}}"`.
    - [ ] Replace `doctoc` in `hk.pkl` with `mdformat-toc` (or remove if Zensical handles TOC natively).
    - [ ] Delete `package.json` and `scripts/validateCommitHook.mjs`.

- [ ] Can we somehow allocate a higher priority/system resources to `git-cg` when it is running? i.e. allocate more CPU / GPU / RAM to it? or `nice` it? So that it runs faster and more efficiently? I'm not sure if this is possible, but it's worth investigating.

- [ ] **Feature: Incremental Commit Generation with Delta Diffs and Caching**
  - **Problem**: When a user aborts a generation, makes a minor fix (like `ruff format`), and regenerates, the tool discards the highly valuable draft commit message and costs extra tokens to re-analyze the entire diff from scratch.
  - **Solution**: Pass the previously generated draft commit message alongside the "delta diff" (changed lines since last generation) to the LLM.
  - **Implementation**: The prompt becomes: _"Here is your previously generated draft commit message. The user has made the following minor tweaks since then (Delta Diff). Please update the draft message to incorporate these minor changes."_
  - **Note**: This is a standalone core engine feature and should be tracked in a separate issue outside of the current LLMOps epic.
  - Would [Difftastic](https://github.com/Wilfred/difftastic) assist with this?

- [ ] (This needs extensive analysis review and documentation for the user as well as a good understanding of the options available, best practices etc.) Improve the viusal TUI from the very start of the process to the end to make the process more fluid and user friendly. i.e. as soon as the user runs `git-cg -i` the TUI should display the `git diff` in the main body of the screen and ask the user if they want to generate a commit message. The prompt should be displayed in the main body of the screen as well, i.e. not in a sidebar. This TUI should be interactive and allow the user to scroll through the `git diff` and the generated commit message. It should also allow the user to edit the generated commit message. The user should be able to generate a new commit message by clicking the generate button or pressing the enter key. The user should be able to save the commit message by clicking the save button or pressing the enter key. The user should be able to exit the tool by clicking the exit button or pressing the escape key.

- [ ] Include a help and/or a `Keyboard Shortcuts` option for the TUI that displays the same information as the `--help` option for the CLI, but in a TUI format. this could be a section in the TUI that can be toggled on and off, i.e. the user can press a key to display the help information and press the same key to hide it.

- [ ] Include a `begginers` option during initial install of the tool which will install a `begginers` module which will provide them with easy to understand explanations on each of the `git` actions/principals/commands used by the tool. and also the reasoning behind using the tool in a way they can understand. This needs to be an option so experienced developers don't need to have it enabled and can skip through the prompts. The option should be enabled by default and can be disabled by the user during installation or at a later time via the tools settings.
  - [ ] This could spin-off to a tutorial/learning module for `git` itself.
  - [ ] This could be its own tool, i.e. a `git-cg-begginer` command that can be run independently of the main tool.
  - [ ] It should provide suggestions for how to improve the commit message to be more like a professional commit message.
  - [ ] It could provide a step by step walkthrough of how to use the tool, interactive and customisable.
  - [ ] Provide the learning material in a clear concise manner, that can be toggled on and off, i.e. the user can press a key to display the help information and press the same key to hide it.
  - [ ] Provide a "dry-run" sandbox mode where beginners can practice generating and editing commits without actually modifying their local git history.
  - [ ] Add inline tooltips to the TUI (e.g., hovering or pressing ? over "feat" explains what a feature commit is according to Conventional Commits).
  - [ ] Let the user know what to look out for in the agent-generated commits, since they are not always perfect.
  - This includes working through the tools' output from top to bottom, ensuring the title is correctly structured.
    - Ensure that the points in the body of the commit message actually identify the changes made.
    - Verify that the most important point is the title of the commit message.
    - Check that additional changes aren't missing from the body, and that the metadata at the end of the commit message is correct.
    - If the user identifies any problems with the generated message, explain to the user how to use the `Regenerate` function.
    - Explain the language to use when prompting the agent when using the `Regenerate` option (e.g., "This is the most important change, make it the title of the commit message" or "The `SemVer-Impact` needs to be minor", etc).
    - (TODO: I think I need to come up with some improved examples.) Output some examples of excellent and bad commit messages with clear explanations. I haveclosed
  - [ ] Create an onboarding wizard on first run that asks the user their experience level ("Beginner", "Intermediate", "Expert") and configures the default verbosity of the tool accordingly.
  - [ ] interactivly be able to "click-through" all of the sections of the commit message with clear explanations for each section e.g. "📝 docs(adr): update observability stack" my very first thoughts are

- [ ] Ensure that when a commit is triggered in an IDE the process doesn't continue until the user has either saved or clicked the tick to accept the commit. Currently the IDE shows the user the proposed commit message but continues and commits it regardless of the users actions.

- [ ] Explore implementing either [Baseline](https://github.com/SecondSonConsulting/Baseline) or a similar function.
- [ ] have a check run that identifies if there is a newer release of the users chosen LLM model, if there is ask them if they want to download it and use it. if the user selcts no then do not ask them again but inform them that a persistant message will be shown eachtime they run the tool with the command to download and use the newer version. This will be an unobtrusive message shown as an additional colour item in the start up message:

  ```text
  gitCommitGenerator  main 📦+3?14⇡3 🐍 v3.14.5 (gitcommitgenerator)
  ❯ git-cg -i -v
  [22:55:25] Starting git-cg...                                                                             main.py:851
             Engine: mtplx                                                                                  main.py:852
             Commit Msg File: .git/COMMIT_EDITMSG                                                           main.py:853
             Commit Source: None                                                                            main.py:854
             Interactive Mode: True                                                                         main.py:855
             Using rtk for token compression...                                                             main.py:890
             Extracted git diff (14631 characters).                                                         main.py:913
             AI Client initialized. Calling mtplx to generate commit message...                             main.py:921
             Using model: Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed                                       main.py:934
             A newer model is available run  `git-cg --update-model`  to download it.                       main.py:934
             Analyzing diff signals and ranking intents...                                                  main.py:532
  ```

- [ ] **Umbrella** Epic: LLMOps Stack Augmentation (Opik + Promptfoo + OpenLLMetry + Sentry)
- [ ] **Integrate OpenLLMetry** Integrate OpenLLMetry for vendor-neutral OTel tracing
- [ ] **Integrate Promptfoo** Integrate Promptfoo for automated CI evaluation and red-teaming
- [ ] **Integrate Sentry** Integrate Sentry SDK for application crash reporting and error tracking
  - [ ] Explore `Feature Flag` SDKs from the listed solutions or alternate better options if available. I would prefer to stick with the listed options as they are the ones recomended by Sentry. We need to identify which solution proivides us with the best features on free, freemium or 'free self-hosted' options. Listed `Feature Flag` SDKs:
    - [ ] LaunchDarkly
    - [ ] OpenFeature
    - [ ] Statsig
    - [ ] Unleash
    - [ ] Additionally, Sentry allows "different sollutions to evaluate feature flags" if we want to choose an option not listed here.
  - [ ] To integrate the `sentry-sdk` with one of the listed `Feature Flag` SDKs the code for each is provided by Sentry:
    - #### LaunchDarkly
      - Configure SDK - Add `LaunchDarklyIntegration` to your integrations list.

        ```python
        import sentry_sdk
        from sentry_sdk.integrations.launchdarkly import LaunchDarklyIntegration
        import ldclient

        sentry_sdk.init(
          dsn="https://6188c2af95af5873af3d2f5acfcbde65@o4509950333550592.ingest.us.sentry.io/4509950397775872",
          # Add data like request headers and IP for users, if applicable;
          # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
          send_default_pii=True,
          integrations=[
              LaunchDarklyIntegration(),
          ],
        )
        ```

      - Verify - Test your setup by evaluating a flag, then capturing an exception. Check the Feature Flags table in Issue Details to confirm that your error event has recorded the flag and its result.

        ```python
        client = ldclient.get()
        client.variation("hello", Context.create("test-context"), False)  # Evaluate a flag with a default value.
        sentry_sdk.capture_exception(Exception("Something went wrong!"))
        ```

    - #### OpenFeature:
      - Configure SDK - Add `OpenFeatureIntegration` to your integrations list.

        ```python
        import sentry_sdk
        from sentry_sdk.integrations.openfeature import OpenFeatureIntegration
        from openfeature import api

        sentry_sdk.init(
            dsn="https://6188c2af95af5873af3d2f5acfcbde65@o4509950333550592.ingest.us.sentry.io/4509950397775872",
            # Add data like request headers and IP for users, if applicable;
            # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
            send_default_pii=True,
            integrations=[
                OpenFeatureIntegration(),
            ],
        )
        ```

      - Verify - Test your setup by evaluating a flag, then capturing an exception. Check the Feature Flags table in Issue Details to confirm that your error event has recorded the flag and its result.

        ```python
        client = api.get_client()
        client.get_boolean_value("hello", default_value=False)  # Evaluate a flag with a default value.
        sentry_sdk.capture_exception(Exception("Something went wrong!"))
        ```

    - #### Statsig:
      - Configure SDK - Add `StatsigIntegration` to your integrations list.

        ```python
        import sentry_sdk
        from sentry_sdk.integrations.statsig import StatsigIntegration
        from statsig.statsig_user import StatsigUser
        from statsig import statsig
        import time

        sentry_sdk.init(
            dsn="https://6188c2af95af5873af3d2f5acfcbde65@o4509950333550592.ingest.us.sentry.io/4509950397775872",
            # Add data like request headers and IP for users, if applicable;
            # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
            send_default_pii=True,
            integrations=[
                StatsigIntegration(),
            ],
        )
        statsig.initialize("server-secret-key")
        ```

      - Verify - Test your setup by evaluating a flag, then capturing an exception. Check the Feature Flags table in Issue Details to confirm that your error event has recorded the flag and its result.

        ```python
        while not statsig.is_initialized():
            time.sleep(0.2)

        result = statsig.check_gate(StatsigUser("my-user-id"), "my-feature-gate")  # Evaluate a flag.
        sentry_sdk.capture_exception(Exception("Something went wrong!"))
        ```

    - #### Unleash:
      - Configure SDK - Add `UnleashIntegration` to your integrations list.

        ```python
        import sentry_sdk
        from sentry_sdk.integrations.unleash import UnleashIntegration
        from UnleashClient import UnleashClient

        sentry_sdk.init(
            dsn="https://6188c2af95af5873af3d2f5acfcbde65@o4509950333550592.ingest.us.sentry.io/4509950397775872",
            # Add data like request headers and IP for users, if applicable;
            # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
            send_default_pii=True,
            integrations=[UnleashIntegration()],
        )

        unleash = UnleashClient(...)  # See Unleash quickstart.
        unleash.initialize_client()
        ```

      - Verify - Test your setup by evaluating a flag, then capturing an exception. Check the Feature Flags table in Issue Details to confirm that your error event has recorded the flag and its result.

        ```python
        test_flag_enabled = unleash.is_enabled("test-flag")  # Evaluate a flag.
        sentry_sdk.capture_exception(Exception("Something went wrong!"))
        ```

  - [ ] Once we have identified which one we will use we will integrate it into the project and then integrate it with the Sentry SDK.
  - [ ] When the chosen `Feature Flag` option has been integrated we will then configure `Change Tracking`.

    > Integrating Sentry with your feature flag provider enables Sentry to correlate feature flag changes with new error events and mark certain changes as suspicious. Learn more about how to interact with feature flag insights within the Sentry UI by reading the documentation.

---

- [ ] Look at this [MTPLX Server](https://github.com/youssofal/MTPLX#the-server)

- [x] Configure git ssh signing using 1Password

---

- [ ] Look at [Janis Article](https://medium.com/@PowerUpSkills/stop-making-ai-agents-rediscover-your-codebase-and-burn-your-tokens-7943325671d4)

---

---

- [ ] Confirm this [no vector search](https://buzzgrewal.medium.com/ai-agents-dont-need-vector-search-anymore-inside-the-agentic-search-stack-replacing-rag-in-2026-58efcabe4f6f)

---

Consider integfrating this: [hunk](https://github.com/modem-dev/hunk)

---

- [ ] ELK Stack

---

- [ ] Rapid-MLX

---

- [ ] [task](https://taskfile.dev/)

---

- [ ] [iii](https://iii.dev/)

---

- [ ] [dify](https://github.com/langgenius/dify)

---

- [ ] [RAG vs RLM](https://www.towardsdeeplearning.com/rlms-the-mit-trick-that-makes-a-small-ai-beat-gpt-5-668c7744cda7)

---

- [ ] Add a function `git-cg config` that will allow the user to configure the model they want to use which will switch the `$MODEL` environment variable.
  - [ ] It should also allow them to tune the model to find the best depth for their system. It should also allow them to select the depth they want to use. These should be saved to the .env file. It should also be able to save these settings to a file that can be copied to other systems, but only contain the settings and not any other information. It should have some kind of safety mechanism to prevent accidental changes to the .env file, so that it is not corrupted. I have already created the skeleton for the `gum` wizard in the `git-cg-config` function in the script so I will just need to flesh out the details.
  - [ ] This will also allow them to set up the remote repository connection with git. I have already created the file `git-cg-config-test.sh` to test the `git-cg-config` function.
  - [ ] This will be part of an overall configuration package which will be able to be set easily via the CLI and a `gum` wizard to help them get set up or change configuration after the initial setup.

---

- [ ] if they want to commit in stages they can select which files to commit and which to skip and run `git-cg stage` or `git-cg -s` to stage the selected files and `git-cg push` or `git-cg -p` to push the staged files and commit them with the generated commit message. For example currently I have about 10 files that need to be commited. they are a mixture of `.py` and `.md` files. I would like to commit the `.py` files first with a commit message, then the `.md` files with a different commit message. This allows me to generate better commit messages because I can pick out the code files and documentation, test, image files, etc. this method has seemed to provide the best results for me so far.

---

- [ ] start logging start to finish times everytime we create a commit message, this can be viewed with `git-cg-logs`

---

- [ ] Review "[text](https://pub.towardsai.net/llmops-the-end-to-end-pipeline-for-reliable-ai-applications-a-complete-guide-2285564a6d6b)" for possibly integrating the articles solutions.

---

- [ ] Look at integrating some of the principals from this into our project [text](https://pub.towardsai.net/claude-code-is-a-mess-until-you-install-this-official-plugin-f94e7cac723f)

---

- [ ] Add to the initial install script to run `mtplx tune`

---

- [ ] Add an option to the TUI menu `print plain text and add to clipboard`

---

- [ ] Add new TUI option `review changes` to review changes with `git diff` and `git log`.

---

- [ ] Add the files being commited to the bottom of the commit message. (Determine if this is wanted data in a commit message or not)

---

- [ ] Integrate a feature that allows the user to select a previously generated commit message and view its `git log` summary of each file, and `git diff` summary of each file.
  - [ ] Create a submenu that shows the git log summaries of each file for a selected commit, with the option of viewing the full log of each file.
  - [ ] Create a submenu that shows the git diff summaries of each file for a selected commit, with the option of viewing the full diff of each file.

---

- [ ] Add all successful git messages to a db and index them as they are added to easily search and view logs, and diffs of previous commits. If they either have the same number e.g. `#43` as they have on GitHub that could help with filtering or searching for specific commits.

---

- [ ] We can look at integrating fd, rg and rga which will be the tools working in the background to search for items relating to commits or other data.

---

- [ ] Add a feature where git-cg runs in background constantly updating diff and commit message, so it is generated by the time the user goes to actually generate and push the commit message.
  - It could then have a feature where the user gets to the point of wanting to review and push the commit, if they are unhappy with the message they can edit it, if they want to commit in stages they can select which files to commit and which to skip and run `git-cg stage` or `git-cg -s` to stage the selected files and `git-cg push` or `git-cg -p` to push the staged files and commit them with the generated commit message. For example currently I have about 10 files that need to be commited. they are a mixture of `.py` and `.md` files. I would like to commit the `.py` files first with a commit message, then the `.md` files with a different commit message. This allows me to generate better commit messages because I can pick out the code files and documentation, test, image files, etc. this method has seemed to provide the best results for me so far.

---

- [ ] Look at LLMOps and MLOps and how we can use them to improve our project. [text](https://aimultiple.com/llmops-tools)

| Tools                  | Type                           |
| ---------------------- | ------------------------------ |
| Dust                   | Integration framework          |
| LlamaIndex             | Integration framework          |
| Langchain              | Integration framework          |
| Deep Lake              | Vector databases               |
| Weaviate               | Vector databases               |
| Bespoken               | LLM testing tools              |
| Trulens                | LLM testing tools              |
| Scale                  | LLM testing tools              |
| Prolific               | RLHF services                  |
| Appen                  | RLHF services                  |
| Clickworker            | RLHF services                  |
| Argilla                | Fine-tuning tools              |
| PromptLayer            | Fine-tuning tools              |
| Octo ML                | Fine-tuning tools              |
| Together AI            | Fine-tuning tools              |
| DeepSpeed              | Fine-tuning tools              |
| Phoenix by Arize       | LLM monitoring & observability |
| Fiddler                | LLM monitoring & observability |
| Helicone               | LLM monitoring & observability |
| Gantry                 | LLM monitoring & observability |
| Clear ML               | MLOPs tools & frameworks       |
| Ignazio                | MLOPs tools & frameworks       |
| HuggingFace            | MLOPs tools & frameworks       |
| Tecton                 | MLOPs tools & frameworks       |
| Weights & Biases       | MLOPs tools & frameworks       |
| Amazon Bedrock         | Data / cloud platforms         |
| DataBricks             | Data / cloud platforms         |
| Azure ML               | Data / cloud platforms         |
| Vertex AI              | Data / cloud platforms         |
| Snowflake              | Data / cloud platforms         |
| Nemo by Nvidia         | LLMOps frameworks              |
| Deep Lake              | LLMOps frameworks              |
| Fine-Tuner AI          | LLMOps frameworks              |
| Snorkel AI             | LLMOps frameworks              |
| Zen ML                 | LLMOps frameworks              |
| Lamini AI              | LLMOps frameworks              |
| Comet                  | LLMOps frameworks              |
| TrueFoundry            | LLMOps Frameworks              |
| Titan ML               | LLMOps frameworks              |
| Haystack by Deepset AI | LLMOps frameworks              |
| Valohai                | LLMOps frameworks              |
| OpenAI                 | LLMs                           |
| Anthropic Claude       | LLMs                           |
| Cohere                 | LLMs                           |
| AI21 Labs              | LLMs                           |

<p>Cem Dilmegani (2026) - &ldquo;Top LLMOps Tools & Compare them to MLOPs&rdquo;. Published online at AIMultiple.com. Retrieved May 18, 2026, from: <a href="https://aimultiple.com/llmops-tools">https://aimultiple.com/llmops-tools</a> [Online Resource]</p>

<p>Cem Dilmegani (2026) - &ldquo;Compare 45+ MLOps Tools in 2026&rdquo;. Published online at AIMultiple.com. Retrieved March 2, 2026, from: <a href="https://aimultiple.com/mlops-tools">https://aimultiple.com/mlops-tools</a> [Online Resource]</p>

- [ ] Look at [Supervised Fine-Tuning vs Reinforcement Learning](https://aimultiple.com/rl-vs-sft)

- [ ] Run "Braintrust" evals through pytest everytime a meaningful change is made.

- [ ] Look at enforching: "Why JSON and not markdown? Anthropic found that models are “less likely to inappropriately change or overwrite JSON files compared to Markdown.” A small detail, but it matters when the agent is running autonomously for hours."

- [ ] Review this article for possible harness setup [Harness Engineering](https://ai.gopubby.com/harness-engineering-what-every-ai-engineer-needs-to-know-in-2026-0ab649e5686a)

- [ ] Look at [eval-view](https://github.com/hidai25/eval-view)

- [ ] Explore the use of "Synthtic Data" for:
  - **Machine learning**
    - **Training data augmentation**:
      Synthetic data expands the available dataset by creating realistic, statistically accurate samples that mirror the distribution of real-world data. This is especially valuable when training AI models that suffer from class imbalance or when collecting real data is too costly, time-consuming, or legally restricted.

      By including additional variations in the dataset, such as lighting changes in computer vision or noise variations in audio, models become more resilient to environmental changes and unexpected inputs.

    - **Rare event simulation**:

      Many AI models underperform when predicting events that occur infrequently because these events are poorly represented in real datasets. Synthetic data solves this by generating numerous realistic examples of such rare events, preserving their statistical and contextual properties.

      This approach enables models to “experience” and learn from scenarios they might never encounter during traditional training, leading to higher recall and better preparedness for mission-critical situations such as fraud detection, equipment failure prediction, or emergency response planning.

    - **Automated data labeling**:

      Manually labeling data is often one of the most expensive and time-consuming stages of AI development, particularly for tasks like object detection or speech recognition. Synthetic data generation can include automatic label assignment during the creation process.

      This eliminates human annotation errors, speeds up model development, and allows teams to create large, precisely labeled datasets tailored to specific business needs, whether for detecting anomalies in manufacturing, recognizing entities in legal documents, or identifying objects in aerial imagery.

        <p>Cem Dilmegani (2026) - &ldquo;Top 25 Synthetic Data Use Cases&rdquo;. Published online at AIMultiple.com. Retrieved March 5, 2026, from: <a href="https://aimultiple.com/synthetic-data-use-cases">https://aimultiple.com/synthetic-data-use-cases</a> [Online Resource]</p>

- [ ] Review these tools for possible integration:

Organise into a table.

| Tool          | Category   | Open Source      | Best For                        |
| ------------- | ---------- | ---------------- | ------------------------------- |
| Langfuse      | All-in-One | Yes (MIT)        | Most teams starting out         |
| LangSmith     | All-in-One | No               | LangChain users                 |
| Braintrust    | All-in-One | No               | Prompt experimentation          |
| Opik          | All-in-One | Yes (Apache 2.0) | Comet users, low-code platforms |
| Confident AI  | Evaluation | No               | Evaluation-first observability  |
| Arize Phoenix | Evaluation | Yes              | OpenTelemetry integration       |
| TruLens       | Evaluation | Yes              | RAG quality metrics             |
| Galileo AI    | Evaluation | No               | Real-time guardrails            |
| Evidently AI  | Evaluation | Yes              | ML + LLM unified monitoring     |
| Helicone      | Gateway    | Yes              | Fastest setup, caching          |
| Portkey       | Gateway    | Yes              | Multi-provider routing          |
| OpenLLMetry   | Gateway    | Yes              | Existing APM integration        |
| Datadog       | Enterprise | No               | Datadog customers               |
| New Relic     | Enterprise | No               | New Relic customers             |
| W&B Weave     | Enterprise | Yes              | MLOps experiment tracking       |

- [ ] Review [LLM Observability Tools](https://www.firecrawl.dev/blog/best-llm-observability-tools)

- [ ] Review:

| If You Need...              | Best Choice         | Runner-Up           | Why                                                  |
| --------------------------- | ------------------- | ------------------- | ---------------------------------------------------- |
| RAG evaluation              | Ragas               | DeepEval            | Purpose-built RAG metrics + synthetic test data      |
| CI/CD test gating           | Promptfoo           | DeepEval            | CLI-native, YAML config, integrates with any CI      |
| Production observability    | Langfuse            | Arize Phoenix       | Open-source, self-hostable, vendor-agnostic          |
| LangChain-native monitoring | LangSmith           | Langfuse            | Deepest integration, annotation queues, datasets     |
| Agent evaluation            | DeepEval            | Braintrust          | Dedicated agent metrics, multi-step trace evaluation |
| Security / red teaming      | Promptfoo           | DeepEval            | 50+ vulnerability types, adversarial test generation |
| All-in-one platform         | Braintrust          | Confident AI        | Eval + tracing + experiments in one tool             |
| $0 budget (fully free)      | Promptfoo + Phoenix | DeepEval + Langfuse | Both combos cover testing + observability at $0      |
| Human eval / annotation     | LangSmith           | Braintrust          | Best annotation UI and labeling workflows            |
| Compliance / EU AI Act      | Confident AI        | Braintrust          | Built-in audit trails and documentation              |

---

- [ ] Zensical Documentation Overhaul

- Remove obsolete pages such as "Agent Handoff" and "Walkthrough".
- Ensure the content of the documentation site reflects recent PRs, Issues, and architectural changes (e.g. `git-cg` tool, guided regeneration, new SOP loading logic).
- Ensure documentation formatting aligns with `git-cg` standard formatting.
- Add `CHANGELOG.md` to the top-level navigation.
- Add a "Feature Spotlight" entry documenting the GUI editor `index.lock` hook collision, `hk` stash safety, and the `--gui`/`--term` flags.

---

- [ ] Configure Package Publishing

- Although the package `gitcommitgenerator` is built with `hatchling` (CLI tool `git-cg`), there is currently no pipeline for publishing to PyPI or Homebrew.
- Investigate and set up a GitHub Action workflow to automatically publish releases to PyPI upon tagging.
- Ensure the package metadata and entry points in `pyproject.toml` are correctly configured for public consumption.

---

- [ ] Consider adding these libraries where needed:
  - [ ] polars
  - [ ] rich
    - [ ] ? Full go front end with python backend. This would open the whole charmbracelet suite to us.
    - [ ] [progress bars](https://arc.net/l/quote/yncaivfb)
    - [ ] [Logging with rich handler](https://arc.net/l/quote/kvyuysnl)
    - [ ] [Console recording and export](https://arc.net/l/quote/zhqzjuwr)
  - [ ] sentence-transformers (for semantic similarity and matching the `intent`)
  - [ ] perfect
  - [ ] "walrus" operator for fetching the gitmoji's to match with intent
  - [ ] functools.cache
  - [ ] cached_property
  - [ ] contextlib.contextmanager
    - [ ] `ExitStack`
  - [ ] `@dataclasses`
    - [ ] `field()`
    - [ ] `__post_init__`
    - [ ] `frozen=True`
    - [ ] `repr=False`
  - [ ] `executing`
  - [ ] `python-magic`
  - [ ] `glom`
  - [ ] `deal`
  - [ ] `crosshair`
  - [ ] `immutables`
  - [ ] `tenacity`
  - [ ] `boltons`
  - [ ] `msgspec`
  - [ ] `structlog`
  - [ ] `diskcache`
  - [ ] `pyinstrument`
  - [ ] `anyio`
  - [ ] `orjson`
  - [ ] `py-spy`
  - [ ] `loguru`
  - [ ] `pydantic-settings`
  - [ ] `pydantic-aioredis`
  - [ ] `pydantic-yaml`
  - [ ] `sqlite-utils`
  - [ ] `rapidfuzz`
  - [ ] `sqlglot`
  - [ ] `__init_subclass__`
  - [ ] `betterproto`
  - [ ] `tqdm`
  - [ ] `dotenv`
  - [ ] `SQLAlchemy 2.0 Async`
  - [ ] `alembic`
  - [ ] `pytest-asyncio`
  - [ ] `sentry_sdk`
  - [ ] `redis.asyncio`
  - [ ] Swagger UI
  - [ ] ReDoc
  - [ ] GraphQL — Strawberry
  - [ ] fastapi-versioning
  - [ ] Uvicorn
  - [ ] `logging`
  - [ ] `prometheus_client`
    - [ ] `Counter`
    - [ ] `Gauge`
    - [ ] `Histogram`
    - [ ] `Summary`
  - [ ] Structural Pattern Matching for Complex Conditionals
  - [ ] Context Manager Protocol for Resource Management
  - [ ] Descriptor Protocol for Reusable Validation
  - [ ] Slots for Memory-Efficient Classes
  - [ ] Functools Cache Decorators Beyond Simple Memoization
  - [ ] Generator Expressions for Memory-Efficient Pipelines
  - [ ] ChainMap for Elegant Configuration Management
  - [ ] Singledispatch for Clean Polymorphism
  - [ ] Walrus Operator for Efficient Conditionals
  - [ ] `msgpack`
  - [ ] `alive_progress`
  - [ ] `dask`
  - [ ] `pathlib`
  - [ ] `cerebrus`
  - [ ] `hypothesis`
  - [ ] `pyinstrument`
  - [ ] `uvloop`
  - [ ] `multiprocessing`
  - [ ] `RustPython Extensions`
  - [ ] `joblib`
  - [ ]

---

- [ ] [ML Algorithms](https://medium.com/@atharvjaiswal56/7-machine-learning-algorithms-every-python-developer-should-know-in-2026-51abe7921b12)

  ```text
  Your data has labels?
  ├── YES → Supervised Learning
  │   ├── Predicting a number → Linear Regression or XGBoost
  │   ├── Predicting a category
  │   │   ├── Small dataset / text data → Logistic Regression or SVM
  │   │   ├── Tabular / structured data → Random Forest or XGBoost
  │   │   └── Images / audio / large data → Neural Network
  │   └── Need to explain the model to stakeholders → Random Forest
  └── NO → Unsupervised Learning
      └── Find groups in data → K-Means Clustering
  ```

---

- [ ] RAG Architectures
  - [ ] Naive RAG
  - [ ] Hybrid RAG + Reranking
  - [ ] Agentic RAG with LangGraph
  - [ ] GRAPHRAG

---

- [ ] `llm-wiki` integration

---

- [ ] [dflash](https://github.com/dflash-dev/dflash)

---

- [ ] [lat.md](https://medium.com/agentic-builders/how-to-use-lat-md-turn-any-folder-into-a-validated-knowledge-graph-8cffac54ceaa)

---

- [ ] `Cloup` is an extension of Click that enhances help messages and adds advanced parameter grouping.

---

- [ ] [Prompt Toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit)is a library for building highly interactive command-line applications. It supports advanced features like auto-completion, syntax highlighting, and multiline editing.

---

- [ ] [Best Python CLI Libraries](https://levelup.gitconnected.com/best-python-libraries-for-command-line-interface-cli-development-31f7894a85aa)

---

- [ ] [RAGFlow](https://github.com/infiniflow/ragflow)

---

- [ ] [Vector Observability](https://github.com/vectordotdev/vector)

---

- [ ] Benchmark `dspark` models and explore attaching/integrating them with our existing local inference engines (`MTPLX` / `oMLX`). Evaluate their performance, token efficiency, and compatibility for commit generation workloads.
