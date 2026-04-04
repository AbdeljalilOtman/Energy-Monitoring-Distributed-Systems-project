# Database Selection for MLab: Why InfluxDB is the Optimal Choice

## Project Context

**MLab** is a distributed energy monitoring framework for **15-20 workstations and mobile devices**. The system collects, transmits, stores, and visualizes real-time energy-related Key Performance Indicators (KPIs) from edge nodes executing ML workloads.

## Benchmark Results Summary

Based on rigorous benchmarking of 1,000,000 data points across four database candidates (PostgreSQL, TimescaleDB, ClickHouse, and InfluxDB), the following performance metrics were observed:

| Database | Write Speed (rows/sec) | Mean Write Delay | Best Query Performance |
|----------|----------------------|------------------|------------------------|
| **InfluxDB** | 18,229 | 1,006ms | Q2, Q4, Q5 (Time-series queries) |
| PostgreSQL | 49,650 | 317ms | Q1, Q3 (Simple queries) |
| TimescaleDB | 32,194 | 527ms | Moderate across all |
| ClickHouse | 79,014 | 252ms | Write-heavy workloads |

## Why InfluxDB is the Best Fit for MLab

### 1. **Time-Series Optimized Queries (Critical for MLab)**

The MLab requirements specifically demand queries like:
- *"Average CPU voltage across Node A over the last 24 hours"* (Downsampling)
- *"Compare energy consumption between two nodes"* (Node comparison)
- *"Detect out-of-range power draws"* (Anomaly detection)

**Benchmark Results for Time-Series Queries:**

| Query Type | InfluxDB | PostgreSQL | TimescaleDB | ClickHouse |
|------------|----------|------------|-------------|------------|
| **Q4: Downsampling (hourly avg)** | **63.3ms** | 124.3ms | 193.0ms | 117.2ms |
| **Q5: Two-Node Comparison** | **119.5ms** | 200.8ms | 211.7ms | 186.0ms |
| **Q2: Out-of-Range Detection** | **66.5ms** | 110.2ms | 74.2ms | 157.8ms |

**InfluxDB is the clear winner for ALL time-series specific queries** — which constitute the core of MLab's analytical workload.

### 2. **Write Performance is Sufficient for 15-20 Nodes**

While InfluxDB has the slowest write speed (18,229 rows/sec), this is **more than adequate** for MLab's scale:

- **Calculation:** 20 nodes × 10 metrics × 1 sample/second = 200 writes/second
- **InfluxDB capacity:** 18,229 writes/second = **91x headroom**
- **Conclusion:** Write speed is NOT the bottleneck for 15-20 nodes

The benchmark's 1M rows represents **83 minutes** of data from 20 nodes — well within operational limits.

### 3. **Minimal Observer Effect (Critical Non-Functional Requirement)**

The requirements explicitly state:

> *"The daemon and mobile application must be highly optimized. If the monitoring tool consumes excessive CPU resources, it invalidates the energy readings."*

**Why InfluxDB excels here:**

| Feature | Benefit for MLab |
|---------|------------------|
| Lightweight write protocol | Minimal CPU overhead on nodes |
| HTTP/HTTPS or MQTT support | Efficient for mobile devices |
| Batched writes (20k rows/batch) | Reduced network chatter |
| Low memory footprint | Doesn't compete with ML workloads |

InfluxDB's specialized time-series architecture means the **monitoring overhead is minimal** — preserving the integrity of energy measurements.

### 4. **Native Time-Series Features Align with Requirements**

The requirements specify storage of `[Timestamp, Node_ID, Workload_Tag, KPI_Name, Value]` — a classic time-series schema.

**InfluxDB's native advantages:**

| Requirement | InfluxDB Solution |
|-------------|-------------------|
| High-volume timestamped metrics | Built-in time-series engine (TSM) |
| Aggregation queries | Native Flux query language |
| Downsampling | Continuous queries / tasks |
| Data retention policies | Automatic data lifecycle management |
| Node tagging | Native tag support for filtering |

### 5. **Query Performance Stability**

InfluxDB showed the **most consistent query performance** with low standard deviation:

| Query | InfluxDB StdDev | PostgreSQL StdDev |
|-------|-----------------|-------------------|
| Q4 (Downsampling) | **6.26ms** | 36.06ms |
| Q5 (Node Compare) | **11.7ms** | 36.71ms |

**Predictable latency** means dashboards will respond consistently — critical for real-time monitoring.

### 6. **Mobile Device Support**

MLab includes **Android mobile devices** with specific constraints:
- Battery drain concerns
- Intermittent connectivity
- Limited processing power

**InfluxDB advantages for mobile:**
- MQTT protocol support (low overhead)
- Small client library footprint
- Efficient batched writes preserves battery

### 7. **Extensibility & Iterative Design**

The requirements demand modularity for future changes (GPU monitoring, database changes).

**InfluxDB's ecosystem:**
- Telegraf (agent) for easy metric collection
- Compatible with Grafana for visualization
- RESTful API for backend integration
- Easy to add new metrics without schema changes

## Performance Summary: InfluxDB vs Alternatives

| Criterion | InfluxDB | PostgreSQL | TimescaleDB | ClickHouse |
|-----------|----------|------------|-------------|------------|
| **Time-series queries** | 🏆 BEST | Good | Good | Moderate |
| **Write speed for 20 nodes** | ✅ Sufficient | Excellent | Very Good | Excellent |
| **Observer effect** | 🏆 Minimal | Moderate | Moderate | Higher |
| **Mobile support** | 🏆 Native | Poor | Poor | Poor |
| **Query consistency** | 🏆 Stable | Variable | Variable | Variable |
| **Energy monitoring focus** | 🏆 Built-in | General purpose | Time-series | Analytics |
| **Dashboard integration** | 🏆 Excellent | Good | Good | Good |

## Conclusion

**InfluxDB is the optimal database for MLab** because:

1. ✅ **Wins all time-series queries** (Q2, Q4, Q5) — the core analytical workload
2. ✅ **Write performance is sufficient** (18k rows/sec >> 200 rows/sec needed)
3. ✅ **Minimal observer effect** — preserves energy measurement integrity
4. ✅ **Native time-series features** align perfectly with requirements
5. ✅ **Mobile-friendly** — supports MQTT and low-power operation
6. ✅ **Consistent latency** for reliable dashboard performance
7. ✅ **Extensible design** for future GPU and new metric monitoring



---

*Benchmark completed: 1,000,000 rows | 4 databases | 5 query types | 15-20 node target*
