 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Bio.report()

Generate reports from experimental results. Wraps the DAT `dat_report` function to produce Excel spreadsheets from experiment data.

---

## Synopsis

```bash
bio report                             # report on current DAT
bio report --show --sheets agent       # generate, group by agent, and open
bio report path/to/experiment          # report on specific DAT
```

```python
bio = Bio()
results: list[dict] = bio.run("catalog/experiments/sweep")
bio.report(results)                    # table to Excel
bio.report(results, show=True)         # generate and open
```

---

## Report Block Fields

```yaml
report:
  type: table                      # table | detailed (default: table)
  title: "Mutualism Results"       # title for the Excel file
  folder: reports/                 # output folder (default: current DAT)
  metrics: [score, steps]          # metrics to include (default: all)
  columns: [agent, seed, score]    # columns to include (default: all)
  sheets: [agent]                  # split into sheets by this column
  show: true                       # open Excel after generating (default: false)
```

---

## Report Types

### `table`

Generates an Excel spreadsheet using DAT's `dat_report` function. Each row is one experiment run, columns are axis values and computed metrics.

```yaml
report:
  type: table
  title: "Parameter Sweep Results"
  metrics: [score, final_ME1, success]
  sheets: [scenario]               # one sheet per scenario
  show: true                       # open when done
```

The underlying `dat_report` function:
- Collects data points from DATs using metric functions
- Builds a DataFrame with axis values and metrics
- Outputs to Excel with optional sheet splitting

### `detailed`

*For later implementation.* Will provide expanded per-run information including timelines, action traces, and full state snapshots.

```yaml
report:
  type: detailed
  # TBD
```

---

## Examples

### Basic CLI Usage

```bash
# Generate report on current DAT
bio report

# Generate and open in spreadsheet app
bio report --show

# Report on a specific experiment DAT
bio report catalog/experiments/sweep

# Specify output folder
bio report --folder reports/

# Include only specific metrics
bio report --metrics score,steps,success
```

### Python Usage

```python
bio = Bio()

# Run experiment and report
experiment = bio.fetch("catalog/experiments/parameter_sweep")
results = bio.run(experiment)

# Generate Excel report
bio.report(results, title="Sweep Results")

# Generate and open immediately
bio.report(results, title="Sweep Results", show=True)

# Split into sheets by scenario
bio.report(results, sheets=["scenario"], show=True)
```

### Report Block in Spec

```yaml
experiment.parameter_sweep:
  scenario: !ref baseline
  name: "temp{temperature}_me{initial_ME1}"

  axes:
    temperature: [20, 25, 30]
    initial_ME1: [1.0, 2.0, 5.0]

  report:                            # report block for this experiment
    type: table
    title: "Temperature Sweep"
    metrics: [score, efficiency]
    show: true
```

### Multiple Reports

```yaml
experiment.full_analysis:
  scenario: !ref baseline
  name: "{agent}_s{seed}"

  axes:
    agent: [random, llm]
    seeds: 10

  reports:                           # multiple report blocks
    - type: table
      title: "Summary by Agent"
      sheets: [agent]
      show: false

    - type: table
      title: "All Runs"
      columns: [agent, seed, score, steps]
      show: true
```

### Custom Metrics

```yaml
experiment.with_metrics:
  scenario: !ref mutualism
  name: "temp{temperature}"

  axes:
    temperature: [20, 25, 30]

  metrics:                           # custom metric functions
    efficiency: !_ trace.final['ME2'] / trace.steps
    stability: !_ std(trace.timeline['ME1'])

  report:
    type: table
    metrics: [score, efficiency, stability]
    show: true
```

---

## DAT Integration

The `table` report type calls DAT's `dat_report` function:

```python
dat_report(
    spec,
    title=title,
    folder=folder,
    source=source,
    metrics=metrics,
    columns=columns,
    sheets=sheets,
    show=show
)
```

This produces Excel files with:
- One row per experiment run
- Columns for axis values (scenario, temperature, seed, etc.)
- Columns for each computed metric
- Optional sheet splitting by any column

---

## See Also

- [[ABIO Run|run]] — run experiments
- [[classes/execution/Experiment|Experiment]] — experiment class and run behavior
- [[Execution Guide]] — execution model overview
