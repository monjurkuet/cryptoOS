# Recent Changes Report

Date: 2026-04-26
Repo: `cryptoOS`
Baseline reviewed: `794a750`
Head reviewed: `47db27b`

## Executive Summary

The recent changes are concentrated in `smart-money-signal-system` and add a full reinforcement-learning workflow around the existing whale-driven signal engine.

In plain terms, the system can now:

1. keep generating live BUY/SELL/NEUTRAL signals as before
2. watch how those signals perform over several future time horizons
3. store those outcomes in MongoDB
4. train a PPO-based RL policy offline from that historical outcome data
5. save checkpoints and reload or push improved runtime parameters back into the live system

This is a meaningful architecture shift: the signal system is no longer only rule-driven; it now has a feedback loop for tuning signal sensitivity over time.

## Commits Reviewed

Reviewed commits after `794a750`:

- `6b57890` — add `SignalOutcomeTracker` for reward computation
- `8a8fbfb` — wire `OutcomeTracker` into the event processor and entry points
- `3b94f7f` — add `OutcomeStore` with MongoDB persistence
- `3f000ea` — add `SignalOptEnv` Gymnasium environment
- `525bb18` — add PPO `ActorCritic` + `PPOAgent`
- `0523d2a` — add `torch`, `gymnasium`, `pymongo`
- `f02a362` — add `RLParameterServer`
- `285e190` — let `SignalGenerationProcessor` consume RL params
- `adcdee3` — wire parameter server and outcome store into startup paths
- `f56a5c1` — add retraining script and 6-hour cron-oriented workflow
- `47db27b` — add RL status and retraining API endpoints

## What Changed

### 1. Live signal generation is now RL-tunable

Before these changes, the signal processor used fixed logic to decide when to emit `BUY`, `SELL`, or `NEUTRAL`.

Now the processor accepts runtime-adjustable parameters:

- `bias_threshold`
- `conf_scale`
- `min_confidence`

These directly change how aggressive or selective signal generation is:

- `bias_threshold` decides how strong net trader bias must be before the system emits `BUY` or `SELL`
- `conf_scale` changes how strongly net bias maps into confidence
- `min_confidence` suppresses weak signals entirely

Operational effect:

- a lower `bias_threshold` makes the system more reactive
- a higher `min_confidence` makes the system more selective
- a higher `conf_scale` makes strong biases appear stronger faster

### 2. The system now tracks signal outcomes

New component: `SignalOutcomeTracker`

When a live signal is emitted, the system registers:

- signal direction
- confidence
- entry price
- timestamp

As future mark-price events arrive, it resolves the outcome over multiple horizons:

- 1 minute
- 5 minutes
- 15 minutes
- 1 hour

For each horizon it computes PnL:

- `BUY` wins if price rises
- `SELL` wins if price falls
- `NEUTRAL` produces `0.0`

Why this matters:

- the system now collects training labels automatically from real behavior
- performance is not guessed; it is measured from market movement after each signal

### 3. Outcomes are persisted to MongoDB

New component: `OutcomeStore`

Resolved outcomes are stored in MongoDB collection:

- database: `signal_system` by default
- collection: `rl_outcomes`

Stored fields include:

- `signal_id`
- `action`
- `confidence`
- `entry_price`
- `exit_price`
- `pnl_pct`
- `horizon_seconds`
- `timestamp`
- `resolved_at`

Why this matters:

- retraining can use real historical outcomes
- the RL loop survives restarts
- outcomes can be queried through the API

### 4. A PPO training stack was added

New RL modules:

- `src/signal_system/rl/environment.py`
- `src/signal_system/rl/policy.py`
- `src/signal_system/rl/training.py`

The RL environment converts recent outcomes into a compact observation vector including:

- recent average PnL
- PnL volatility
- win rate
- number of recent resolved signals
- current tunable params
- buy/sell outcome ratios
- short-horizon average PnL

The action space is discrete and intentionally small. The agent can:

- increase/decrease `bias_threshold`
- increase/decrease `conf_scale`
- increase/decrease `min_confidence`
- do nothing

The reward is mostly recent average PnL, with a small penalty when the agent becomes too restrictive and produces too few signals.

### 5. Checkpoint loading was added for live inference

New component: `RLParameterServer`

At startup, the API and standalone entry points try to load the latest `.pt` checkpoint from:

- `smart-money-signal-system/checkpoints/`

The parameter server:

- stores active runtime params in memory
- exposes them safely to live readers
- supports manual updates
- can load the newest checkpoint automatically

Why this matters:

- trained parameters become part of normal startup
- the live service can adopt improvements without code changes

### 6. Offline retraining was added

New entry point:

- `uv run python -m signal_system.rl.retrain`

This script:

1. connects to MongoDB
2. reads recent `rl_outcomes`
3. if none exist, reconstructs synthetic outcomes from `market_scraper.signals` and candle collections
4. trains the PPO agent offline
5. writes a timestamped checkpoint
6. optionally pushes the resulting params into the running API

Default behavior:

- checkpoint directory: `smart-money-signal-system/checkpoints/`
- default episodes: `100`

Important cold-start behavior:

If `rl_outcomes` is empty, the script attempts to reconstruct outcomes from:

- `market_scraper.signals`
- `btc_candles_1m`
- `btc_candles_5m`
- `btc_candles_15m`
- `btc_candles_1h`

That means retraining can still work before the live RL loop has accumulated enough native outcome history.

### 7. New API endpoints were added

Under `http://localhost:4341/api/v1`:

- `GET /rl/status`
- `GET /rl/params`
- `PUT /rl/params`
- `GET /rl/outcomes`
- `POST /rl/retrain`

These endpoints turn the RL system into an operable feature, not just internal code.

## How To Use The New Features

### Start the signal system

From `smart-money-signal-system/`:

```bash
uv sync
uv run python -m signal_system server
```

Or from the repo root:

```bash
./scripts/start-all.sh --background
```

What happens on startup:

- dependencies are initialized
- the latest RL checkpoint is loaded if one exists
- the loaded params are pushed into `SignalGenerationProcessor`
- Redis subscriptions are started

### Confirm RL is active

```bash
curl http://localhost:4341/api/v1/rl/status
```

Look for:

- `params`
- `last_updated`
- `checkpoint_path`

Interpretation:

- `checkpoint_path = null` means no checkpoint has been loaded yet
- non-null means the server found and loaded a saved model

### Inspect current runtime parameters

```bash
curl http://localhost:4341/api/v1/rl/params
```

Expected response shape:

```json
{
  "params": {
    "bias_threshold": 0.2,
    "conf_scale": 1.0,
    "min_confidence": 0.3
  }
}
```

### Update parameters manually

Example:

```bash
curl -X PUT http://localhost:4341/api/v1/rl/params \
  -H "Content-Type: application/json" \
  -d '{"bias_threshold":0.25,"conf_scale":1.2,"min_confidence":0.35}'
```

Use this when:

- you want to experiment without retraining
- you want to roll back overly aggressive params
- you want to tune selectivity during live observation

### View recent resolved outcomes

```bash
curl "http://localhost:4341/api/v1/rl/outcomes?limit=20"
```

Use this to answer:

- are outcomes being recorded?
- what is recent average PnL?
- what is the recent win rate?
- is the system resolving horizons correctly?

### Trigger retraining from CLI

```bash
uv run python -m signal_system.rl.retrain --episodes 200
```

Push the new parameters into the live API after training:

```bash
uv run python -m signal_system.rl.retrain --episodes 200 --push
```

### Trigger retraining from API

```bash
curl -X POST "http://localhost:4341/api/v1/rl/retrain?episodes=200"
```

Behavior:

- starts a background process
- returns immediately
- training progress itself is not streamed through the API
- after completion, updated params can be checked through `/rl/status` and `/rl/params`

## Environment and Dependency Changes

### Python / dependencies

`smart-money-signal-system/pyproject.toml` now explicitly includes:

- `gymnasium`
- `pymongo`
- `torch`

Python requirement is `>=3.11`.

### New environment variables

For RL outcome persistence:

```env
SIGNAL_MONGO__URL=mongodb://localhost:27017
SIGNAL_MONGO__DATABASE=signal_system
```

Existing core vars still matter:

```env
REDIS_URL=redis://localhost:6379/0
REDIS_CHANNEL_PREFIX=events
API_HOST=0.0.0.0
API_PORT=4341
SYMBOL=BTC
```

## Integration Notes

The signal system now depends more strongly on two event streams from `market-scraper`:

- `events:trader_positions`
- `events:mark_price`

Why `mark_price` matters now:

- signal emission alone is not enough for RL
- the system needs follow-up price updates to resolve rewards

If mark-price events are missing or delayed:

- live signals still work
- RL outcome storage will lag or remain empty
- retraining will depend more heavily on synthetic backfill

## Files Added or Significantly Changed

### New RL files

- `smart-money-signal-system/src/signal_system/rl/environment.py`
- `smart-money-signal-system/src/signal_system/rl/outcome_store.py`
- `smart-money-signal-system/src/signal_system/rl/outcome_tracker.py`
- `smart-money-signal-system/src/signal_system/rl/parameter_server.py`
- `smart-money-signal-system/src/signal_system/rl/policy.py`
- `smart-money-signal-system/src/signal_system/rl/retrain.py`
- `smart-money-signal-system/src/signal_system/rl/training.py`

### Wiring changes

- `smart-money-signal-system/src/signal_system/__main__.py`
- `smart-money-signal-system/src/signal_system/api/main.py`
- `smart-money-signal-system/src/signal_system/api/routes.py`
- `smart-money-signal-system/src/signal_system/services/event_processor.py`
- `smart-money-signal-system/src/signal_system/signal_generation/processor.py`
- `smart-money-signal-system/src/signal_system/config.py`

### Tests added

- `smart-money-signal-system/tests/unit/test_environment.py`
- `smart-money-signal-system/tests/unit/test_event_processor_outcome.py`
- `smart-money-signal-system/tests/unit/test_outcome_store.py`
- `smart-money-signal-system/tests/unit/test_outcome_tracker.py`
- `smart-money-signal-system/tests/unit/test_parameter_server.py`
- `smart-money-signal-system/tests/unit/test_policy.py`
- `smart-money-signal-system/tests/unit/test_signal_processor_rl.py`
- `smart-money-signal-system/tests/unit/test_training.py`

## Important Caveats

### 1. Local uncommitted changes exist

At review time, the working tree already contains local modifications not introduced by this report work:

- modified: `smart-money-signal-system/src/signal_system/rl/retrain.py`
- modified: `uv.lock`
- untracked: `smart-money-signal-system/checkpoints/`

That matters because:

- your current local behavior may differ slightly from the last committed version
- generated checkpoints are intentionally part of runtime state but should be reviewed before committing

### 2. Retraining is offline, not continuous online learning

The current design is sensible and safer operationally:

- live services collect outcomes
- training happens in a separate process
- new params are loaded or pushed after training

This avoids destabilizing live inference with in-process training.

### 3. The RL agent tunes thresholds, not trade execution

This RL layer does **not** place trades and does **not** directly forecast price.

It tunes the parameters of the existing signal engine:

- when to emit directional signals
- how strong confidence should be
- how much weak signals should be filtered

That is a narrower and safer scope than end-to-end trading automation.

## Documentation Updates Made

The docs were updated to reflect the recent changes:

- root `README.md` now mentions RL components and the checkpoint/outcome flow
- `smart-money-signal-system/README.md` now documents the RL features and usage
- `market-scraper/README.md` had an outdated hard-coded root path corrected

## Bottom Line

These changes move the repo from a static whale-signal engine to a learning-capable signal platform.

The practical new operating loop is:

1. run the system
2. let signals accumulate
3. let mark-price events resolve outcomes
4. inspect `/api/v1/rl/outcomes`
5. retrain with CLI or API
6. load or push the new checkpoint-backed params

That is the key story of the recent work.
