 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# bio.sim()

Simulator configuration and execution. The `sim:` section in a scenario controls how the simulation runs.

---

## Spec Format

```yaml
sim:
  steps: 100                    # number of steps to run
  time_step: 0.1                # time delta per step (default: 1.0)
  simulator: SimpleSimulator    # simulator class (default)
  terminate: !ev "lambda state: state['population'] <= 0"  # early stop
```

---

## Fields

### `steps:`
Number of simulation steps to run. Each step advances the simulation by `time_step` units.

### `time_step:`
Time delta per step, used for rate calculations. Default: `1.0`

### `simulator:`
Simulator class to use. Default: `SimpleSimulator`

Available simulators:
- `SimpleSimulator` — basic ODE-style simulation
- `StochasticSimulator` — stochastic/Gillespie-style
- Custom simulators can be registered

### `terminate:`
Boolean expression evaluated each step. Simulation stops early if true.

```yaml
terminate: !ev "lambda state: state['population'] <= 0"
terminate: !ev "lambda state: state['time'] >= 50"
```

If not specified, runs for exactly `steps` iterations.

---

## Python API

```python
scenario = bio.build("scenarios.mutualism")
sim = bio.sim(scenario)

# Step-by-step execution
sim.step()              # advance one step
sim.step(n=10)          # advance multiple steps

# Run to completion
sim.run()               # run for scenario's configured steps
sim.run(steps=100)      # override step count

# State access
state = sim.state       # current state dict
trace = sim.trace       # list of all states
```

---

## Action Timing

Actions are instantaneous triggers — `sim.action()` returns immediately. Effects unfold over subsequent `step()` calls.

```python
sim.action("add_feedstock", "Lora", "ME1", 5.0)  # triggers action
sim.step()                                        # effects begin
sim.step(n=10)                                    # effects continue
```

---

## Termination

The simulation runs until one of:
1. `steps` iterations complete
2. `terminate` condition evaluates to true
3. `sim.run()` is called with explicit step count

```python
# Check if simulation ended early
if sim.terminated:
    print(f"Terminated at step {sim.current_step}")
```

---

## See Also

- [[ABIO Scenario|scenario]] — scenario spec format
- [[ABIO Run|run]] — running scenarios
- [[Agent Interface]] — agent interaction with simulator
