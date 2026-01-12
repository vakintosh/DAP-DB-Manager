# Profiling and Performance Analysis

This directory contains tools for profiling and analyzing the performance of dap-db-manager.

## Quick Start

```bash
# 1. Install profiling dependencies
uv sync --dev

# 2. Run benchmarks
pytest tests/test_benchmarks.py --benchmark-only

# 3. Profile database generation
python profiling/profile_database_generation.py /path/to/music

# 4. Check for performance regressions
pytest tests/test_performance_regression.py
```

## Tools Overview

### 1. Benchmark Tests (`tests/test_benchmarks.py`)

Micro-benchmarks using pytest-benchmark to measure performance of individual operations.

**Usage:**
```bash
# Run all benchmarks
pytest tests/test_benchmarks.py --benchmark-only

# Save baseline for comparison
pytest tests/test_benchmarks.py --benchmark-only --benchmark-save=baseline

# Compare against baseline
pytest tests/test_benchmarks.py --benchmark-only --benchmark-compare=0001

# View histogram of results
pytest tests/test_benchmarks.py --benchmark-only --benchmark-histogram

# Run specific benchmark
pytest tests/test_benchmarks.py::TestTitleformatBenchmarks::test_simple_field_parsing_benchmark --benchmark-only
```

**What it measures:**
- TagFile creation, reading, and writing
- IndexFile operations
- Titleformat parsing and evaluation
- Utility function conversions
- Database initialization

### 2. Profiling Scripts

Detailed profiling to find performance bottlenecks using Python's cProfile.

#### Database Generation Profiling

```bash
python profiling/profile_database_generation.py /path/to/music
```

Profiles the entire database generation process and shows:
- Top functions by cumulative time
- Top functions by total time
- Saves detailed profile to `profile_database_generation.prof`

#### Tag Parsing Profiling

```bash
python profiling/profile_tag_parsing.py /path/to/audio/file.mp3
```

Profiles tag reading for a single audio file.

#### Titleformat Profiling

```bash
# Profile simple format string
python profiling/profile_titleformat.py "%artist% - %album%"

# Profile complex format with 5000 iterations
python profiling/profile_titleformat.py "$if(%albumartist%,%albumartist%,%artist%)" 5000
```

Profiles titleformat parsing and evaluation.

#### Memory Profiling

```bash
python profiling/memory_profile.py /path/to/music
```

Profiles memory usage during database generation. Requires `memory_profiler` package.

**Line-by-line memory profiling:**
```bash
python -m memory_profiler profiling/memory_profile.py /path/to/music
```

### 3. Performance Analysis

Analyze and compare profiling results:

```bash
# Analyze a single profile
python profiling/analyze_performance.py profile_database_generation.prof

# Show top 50 functions
python profiling/analyze_performance.py profile_database_generation.prof 50

# Compare two profiles
python profiling/analyze_performance.py --compare old.prof new.prof
```

### 4. Performance Regression Tests (`tests/test_performance_regression.py`)

Automated tests that track performance over time and alert on regressions.

**Usage:**
```bash
# Run regression tests
pytest tests/test_performance_regression.py -v

# Update baselines after optimization
pytest tests/test_performance_regression.py --update-baselines

# View current baselines
cat tests/.performance_baselines.json
```

**How it works:**
- First run establishes baseline performance metrics
- Subsequent runs compare against baseline
- Warns if performance is >10% slower
- Fails if performance is >25% slower
- Use `--update-baselines` to update after intentional changes

## Profiling Workflow

### Finding Bottlenecks

1. **Start with benchmarks** to identify slow areas:
   ```bash
   pytest tests/test_benchmarks.py --benchmark-only
   ```

2. **Profile the slow operation**:
   ```bash
   python profiling/profile_database_generation.py /path/to/music
   ```

3. **Analyze the profile**:
   ```bash
   python profiling/analyze_performance.py profile_database_generation.prof
   ```

4. **Look for**:
   - Functions with high `tottime` (time spent in function itself)
   - Functions with high `cumtime` (time including called functions)
   - Functions called many times (`ncalls`)

### Optimizing Performance

1. **Make changes** to optimize slow functions

2. **Profile again** and save:
   ```bash
   python profiling/profile_database_generation.py /path/to/music
   mv profile_database_generation.prof profile_before.prof
   # Make changes
   python profiling/profile_database_generation.py /path/to/music
   mv profile_database_generation.prof profile_after.prof
   ```

3. **Compare results**:
   ```bash
   python profiling/analyze_performance.py --compare profile_before.prof profile_after.prof
   ```

4. **Update regression test baselines**:
   ```bash
   pytest tests/test_performance_regression.py --update-baselines
   ```

### Continuous Performance Monitoring

Run regression tests in CI/CD:

```bash
# In CI pipeline
pytest tests/test_performance_regression.py -v
```

This will fail the build if performance degrades by >25%.

## Advanced Profiling

### Interactive Profile Analysis

Explore profile files interactively:

```bash
python -m pstats profile_database_generation.prof
```

Commands in pstats shell:
- `sort cumulative` - Sort by cumulative time
- `sort tottime` - Sort by total time
- `stats 20` - Show top 20 functions
- `callers <function>` - Show who calls this function
- `callees <function>` - Show what this function calls

### Line Profiler

For line-by-line profiling (requires `line_profiler`):

```bash
pip install line_profiler

# Add @profile decorator to function you want to profile
# Then run:
kernprof -l -v your_script.py
```

### Flame Graphs

Generate flame graphs from profile data (requires `flameprof`):

```bash
pip install flameprof
python profiling/profile_database_generation.py /path/to/music
flameprof profile_database_generation.prof > flamegraph.svg
```

## Tips

1. **Use realistic test data**: Profile with real music collections of various sizes

2. **Multiple runs**: Run profiles multiple times to account for variance
   ```bash
   for i in {1..5}; do
       python profiling/profile_database_generation.py /path/to/music
       mv profile_database_generation.prof profile_run_$i.prof
   done
   ```

3. **Profile in production-like environment**: Use similar hardware and data sizes

4. **Focus on hot paths**: Optimize functions that are called frequently or take significant time

5. **Measure before and after**: Always profile before optimizing and compare results

6. **Check memory usage**: Memory issues can cause slowdowns
   ```bash
   python profiling/memory_profile.py /path/to/music
   ```

## Benchmark Results Storage

Benchmark results are stored in `.benchmarks/` directory (automatically created).

```bash
# List all benchmark runs
ls -la .benchmarks/

# Compare specific runs
pytest-benchmark compare 0001 0002
```

## Performance Baselines

Performance regression baselines are stored in:
- `tests/.performance_baselines.json` - Contains timing data for each test

This file should be committed to version control to track performance over time.

## See Also

- [pytest-benchmark documentation](https://pytest-benchmark.readthedocs.io/)
- [Python cProfile documentation](https://docs.python.org/3/library/profile.html)
- [memory_profiler documentation](https://pypi.org/project/memory-profiler/)
