#!/usr/bin/env python3
"""
MLab Database Benchmark
========================
Reads the pre-generated CSV (Timestamp, Node_ID, Workload_Tag, KPI_Name, Value)
and benchmarks 4 databases on:
  1. WRITE delay — insert batches, measure latency per batch
  2. QUERY delay — run Q1-Q5, measure latency

Usage:
  python run_benchmark.py --csv benchmark_data.csv --db all
  python run_benchmark.py --csv benchmark_data.csv --db postgresql
  python run_benchmark.py --csv benchmark_data.csv --db clickhouse --batch-size 50000
"""
import argparse, csv, json, os, random, statistics, sys, time
from datetime import datetime, timezone, timedelta
from io import StringIO

def load_csv(path, limit=None):
    print(f"\nLoading {path}...")
    rows = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit: break
            ts = datetime.fromisoformat(row["Timestamp"])
            rows.append((ts, row["Node_ID"], row["Workload_Tag"], row["KPI_Name"], float(row["Value"])))
            if (i+1) % 1_000_000 == 0: print(f"  {i+1:,} rows...")
    print(f"  Total: {len(rows):,} rows")
    return rows

def get_stats(rows):
    ts = [r[0] for r in rows]
    return {"min_ts": min(ts), "max_ts": max(ts), "node_ids": sorted(set(r[1] for r in rows)),
            "workload_tags": sorted(set(r[2] for r in rows)), "kpi_names": sorted(set(r[3] for r in rows))}

# Helper function for ClickHouse timestamp formatting
def format_clickhouse_timestamp(dt):
    """Format datetime for ClickHouse (no 'T', no timezone)"""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# ---- PostgreSQL ----
class PostgreSQLBench:
    def __init__(self, host="localhost", port=5432, dbname="mlab_bench", user="mlab", password="mlab"):
        import psycopg2; self.conn = psycopg2.connect(host=host,port=port,dbname=dbname,user=user,password=password)
        self.conn.autocommit = True; self.label = "PostgreSQL"
    def setup(self):
        with self.conn.cursor() as c:
            c.execute("DROP TABLE IF EXISTS kpi_readings CASCADE;")
            c.execute("CREATE TABLE kpi_readings (timestamp TIMESTAMPTZ NOT NULL, node_id TEXT NOT NULL, workload_tag TEXT NOT NULL, kpi_name TEXT NOT NULL, value DOUBLE PRECISION NOT NULL);")
            c.execute("CREATE INDEX idx_ts_node_kpi ON kpi_readings (timestamp, node_id, kpi_name);")
    def insert_batch(self, rows):
        buf = StringIO()
        for ts,nid,wt,kn,v in rows: buf.write(f"{ts.isoformat()}\t{nid}\t{wt}\t{kn}\t{v}\n")
        buf.seek(0); start = time.monotonic()
        with self.conn.cursor() as c: c.copy_from(buf, "kpi_readings", columns=("timestamp","node_id","workload_tag","kpi_name","value"))
        return (time.monotonic()-start)*1000
    def run_sql(self, sql, params=None):
        start = time.monotonic()
        with self.conn.cursor() as c: c.execute(sql, params); rows = c.fetchall()
        return len(rows), (time.monotonic()-start)*1000
    def close(self): self.conn.close()

# ---- TimescaleDB ----
class TimescaleDBBench(PostgreSQLBench):
    def __init__(self, **kw): super().__init__(**kw); self.label = "TimescaleDB"
    def setup(self):
        with self.conn.cursor() as c:
            c.execute("DROP TABLE IF EXISTS kpi_readings CASCADE;")
            c.execute("CREATE TABLE kpi_readings (timestamp TIMESTAMPTZ NOT NULL, node_id TEXT NOT NULL, workload_tag TEXT NOT NULL, kpi_name TEXT NOT NULL, value DOUBLE PRECISION NOT NULL);")
            c.execute("SELECT create_hypertable('kpi_readings','timestamp',chunk_time_interval => INTERVAL '12 hours');")
            c.execute("CREATE INDEX idx_ts_node_kpi ON kpi_readings (timestamp, node_id, kpi_name);")

# ---- ClickHouse ----
class ClickHouseBench:
    def __init__(self, host="localhost", port=9000):
        from clickhouse_driver import Client; self.client = Client(host=host,port=port); self.label = "ClickHouse"
    def setup(self):
        self.client.execute("DROP TABLE IF EXISTS kpi_readings")
        self.client.execute("CREATE TABLE kpi_readings (timestamp DateTime64(3,'UTC'), node_id String, workload_tag String, kpi_name String, value Float64) ENGINE=MergeTree() PARTITION BY toYYYYMMDD(timestamp) ORDER BY (timestamp,node_id,kpi_name) SETTINGS index_granularity=8192")
    def insert_batch(self, rows):
        start = time.monotonic()
        self.client.execute("INSERT INTO kpi_readings (timestamp,node_id,workload_tag,kpi_name,value) VALUES", rows)
        return (time.monotonic()-start)*1000
    def run_sql(self, sql, params=None):
        start = time.monotonic(); result = self.client.execute(sql)
        return len(result), (time.monotonic()-start)*1000
    def close(self): self.client.disconnect()

# ---- InfluxDB ----
class InfluxDBBench:
    def __init__(self, url="http://localhost:8086", token="mlab-bench-token", org="mlab", bucket="mlab_bench"):
        from influxdb_client import InfluxDBClient; from influxdb_client.client.write_api import SYNCHRONOUS
        self.client = InfluxDBClient(url=url,token=token,org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.client.query_api(); self.org=org; self.bucket=bucket; self.label="InfluxDB"
    def setup(self):
        try:
            d = self.client.delete_api()
            d.delete(start=datetime(1970,1,1,tzinfo=timezone.utc),stop=datetime(2100,1,1,tzinfo=timezone.utc),predicate="",bucket=self.bucket,org=self.org)
        except: pass
    def insert_batch(self, rows):
        from influxdb_client import Point, WritePrecision
        pts = []
        for ts,nid,wt,kn,v in rows:
            pts.append(Point("kpi_readings").tag("node_id",nid).tag("workload_tag",wt).tag("kpi_name",kn).field("value",float(v)).time(ts,WritePrecision.MS))
        start = time.monotonic(); self.write_api.write(bucket=self.bucket,record=pts)
        return (time.monotonic()-start)*1000
    def run_flux(self, flux):
        start = time.monotonic(); tables = self.query_api.query(flux,org=self.org)
        return sum(len(t.records) for t in tables), (time.monotonic()-start)*1000
    def close(self): self.client.close()

# ---- WRITE BENCHMARK ----
def benchmark_writes(db, rows, batch_size):
    print(f"\n{'='*60}\n  WRITE BENCHMARK - {db.label}\n  Rows: {len(rows):,} | Batch: {batch_size:,}\n{'='*60}")
    db.setup(); lats = []; inserted = 0
    num_b = (len(rows)+batch_size-1)//batch_size; rpt = max(1,num_b//10)
    t0 = time.monotonic()
    for i in range(0,len(rows),batch_size):
        batch = rows[i:i+batch_size]; lat = db.insert_batch(batch); lats.append(lat); inserted += len(batch)
        bn = i//batch_size+1
        if bn%rpt==0 or bn==num_b:
            el=time.monotonic()-t0; rate=inserted/el; pct=inserted/len(rows)*100
            print(f"  {pct:5.1f}% | Batch {bn}/{num_b} | {lat:.1f}ms | {rate:,.0f} rows/sec")
    tt = time.monotonic()-t0
    r = {"database":db.label,"test":"write","total_rows":inserted,"batch_size":batch_size,
         "total_time_sec":round(tt,3),"ingestion_rate_rows_per_sec":round(inserted/tt,2),
         "mean_batch_latency_ms":round(statistics.mean(lats),2),"median_batch_latency_ms":round(statistics.median(lats),2),
         "p95_batch_latency_ms":round(sorted(lats)[int(len(lats)*0.95)],2),
         "min_batch_latency_ms":round(min(lats),2),"max_batch_latency_ms":round(max(lats),2),
         "stddev_batch_latency_ms":round(statistics.stdev(lats),2) if len(lats)>1 else 0}
    print(f"\n  RESULTS: {r['ingestion_rate_rows_per_sec']:,.0f} rows/sec | Mean: {r['mean_batch_latency_ms']:.1f}ms | P95: {r['p95_batch_latency_ms']:.1f}ms")
    return r

# ---- QUERY BENCHMARK ----
def benchmark_queries(db, stats, retries=20):
    print(f"\n{'='*60}\n  QUERY BENCHMARK - {db.label}\n{'='*60}")
    results = []; min_ts=stats["min_ts"]; max_ts=stats["max_ts"]
    nodes=stats["node_ids"]; kpis=stats["kpi_names"]
    n1=nodes[0]; n2=nodes[1] if len(nodes)>1 else nodes[0]
    cpu_kpis = [k for k in kpis if "cpu_percent" in k][:3] or kpis[:3]
    is_i = db.label=="InfluxDB"; is_c = db.label=="ClickHouse"

    def rw(dur_min):
        w=timedelta(minutes=dur_min); ms=max_ts-w
        if ms<=min_ts: return min_ts,max_ts
        o=random.uniform(0,(ms-min_ts).total_seconds()); s=min_ts+timedelta(seconds=o); return s,s+w

    def q1(s,e):
        if is_i:
            kf=" or ".join([f'r["kpi_name"]=="{k}"' for k in cpu_kpis])
            return db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["_measurement"]=="kpi_readings")|>filter(fn:(r)=>r["node_id"]=="{n1}")|>filter(fn:(r)=>{kf})')
        elif is_c:
            ks=",".join([f"'{k}'" for k in cpu_kpis])
            # Use ClickHouse-friendly timestamp format
            s_fmt = format_clickhouse_timestamp(s)
            e_fmt = format_clickhouse_timestamp(e)
            return db.run_sql(f"SELECT * FROM kpi_readings WHERE timestamp>='{s_fmt}' AND timestamp<='{e_fmt}' AND node_id='{n1}' AND kpi_name IN ({ks})")
        else: return db.run_sql("SELECT * FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=ANY(%s)",(s,e,n1,cpu_kpis))

    def q2(s,e):
        kpi=cpu_kpis[0]
        if is_i: return db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["_measurement"]=="kpi_readings" and r["kpi_name"]=="{kpi}" and r["node_id"]=="{n1}")|>aggregateWindow(every:1h,fn:max,createEmpty:false)|>filter(fn:(r)=>r["_value"]>90.0)')
        elif is_c:
            s_fmt = format_clickhouse_timestamp(s)
            e_fmt = format_clickhouse_timestamp(e)
            return db.run_sql(f"SELECT toStartOfHour(timestamp) AS i,max(value),min(value) FROM kpi_readings WHERE timestamp>='{s_fmt}' AND timestamp<='{e_fmt}' AND node_id='{n1}' AND kpi_name='{kpi}' GROUP BY i HAVING max(value)>90.0 OR min(value)<5.0")
        else: return db.run_sql("SELECT date_trunc('hour',timestamp) AS i,MAX(value),MIN(value) FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=%s GROUP BY i HAVING MAX(value)>90.0 OR MIN(value)<5.0",(s,e,n1,kpi))

    def q3(s,e):
        kpi=cpu_kpis[0]
        if is_i: return db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["_measurement"]=="kpi_readings" and r["kpi_name"]=="{kpi}" and r["node_id"]=="{n1}")|>stddev()')
        elif is_c:
            s_fmt = format_clickhouse_timestamp(s)
            e_fmt = format_clickhouse_timestamp(e)
            return db.run_sql(f"SELECT stddevPop(value) FROM kpi_readings WHERE timestamp>='{s_fmt}' AND timestamp<='{e_fmt}' AND node_id='{n1}' AND kpi_name='{kpi}'")
        else: return db.run_sql("SELECT stddev(value) FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=%s",(s,e,n1,kpi))

    def q4(s,e):
        if is_i:
            kf=" or ".join([f'r["kpi_name"]=="{k}"' for k in cpu_kpis])
            return db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["_measurement"]=="kpi_readings" and r["node_id"]=="{n1}")|>filter(fn:(r)=>{kf})|>aggregateWindow(every:1h,fn:mean,createEmpty:false)')
        elif is_c:
            ks=",".join([f"'{k}'" for k in cpu_kpis])
            s_fmt = format_clickhouse_timestamp(s)
            e_fmt = format_clickhouse_timestamp(e)
            return db.run_sql(f"SELECT toStartOfHour(timestamp) AS i,kpi_name,avg(value) FROM kpi_readings WHERE timestamp>='{s_fmt}' AND timestamp<='{e_fmt}' AND node_id='{n1}' AND kpi_name IN ({ks}) GROUP BY i,kpi_name ORDER BY i")
        else: return db.run_sql("SELECT date_trunc('hour',timestamp) AS i,kpi_name,AVG(value) FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=ANY(%s) GROUP BY i,kpi_name ORDER BY i",(s,e,n1,cpu_kpis))

    def q5(s,e):
        kpi=cpu_kpis[0]
        if is_i:
            t=time.monotonic()
            db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["kpi_name"]=="{kpi}" and r["node_id"]=="{n1}")|>aggregateWindow(every:1h,fn:mean,createEmpty:false)')
            db.run_flux(f'from(bucket:"{db.bucket}")|>range(start:{s.isoformat()},stop:{e.isoformat()})|>filter(fn:(r)=>r["kpi_name"]=="{kpi}" and r["node_id"]=="{n2}")|>aggregateWindow(every:1h,fn:mean,createEmpty:false)')
            return 0,(time.monotonic()-t)*1000
        elif is_c:
            s_fmt = format_clickhouse_timestamp(s)
            e_fmt = format_clickhouse_timestamp(e)
            return db.run_sql(f"SELECT a.i,a.v-b.v FROM(SELECT toStartOfHour(timestamp)AS i,avg(value)AS v FROM kpi_readings WHERE timestamp>='{s_fmt}'AND timestamp<='{e_fmt}'AND node_id='{n1}'AND kpi_name='{kpi}'GROUP BY i)a JOIN(SELECT toStartOfHour(timestamp)AS i,avg(value)AS v FROM kpi_readings WHERE timestamp>='{s_fmt}'AND timestamp<='{e_fmt}'AND node_id='{n2}'AND kpi_name='{kpi}'GROUP BY i)b ON a.i=b.i")
        else: return db.run_sql("SELECT a.i,a.v-b.v FROM(SELECT date_trunc('hour',timestamp)AS i,AVG(value)AS v FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=%s GROUP BY i)a JOIN(SELECT date_trunc('hour',timestamp)AS i,AVG(value)AS v FROM kpi_readings WHERE timestamp>=%s AND timestamp<=%s AND node_id=%s AND kpi_name=%s GROUP BY i)b ON a.i=b.i",(s,e,n1,cpu_kpis[0],s,e,n2,cpu_kpis[0]))

    for qname,qfn,dur in [("Q1_RawData",q1,10),("Q2_OutOfRange",q2,180),("Q3_Aggregation",q3,60),("Q4_Downsampling",q4,24*60),("Q5_TwoNodeCompare",q5,24*60)]:
        print(f"\n  {qname}:")
        lats=[]
        for _ in range(retries): s,e=rw(dur); _,lat=qfn(s,e); lats.append(lat)
        r={"database":db.label,"test":"query","query":qname,"min_ms":round(min(lats),2),"mean_ms":round(statistics.mean(lats),2),
           "median_ms":round(statistics.median(lats),2),"p95_ms":round(sorted(lats)[int(len(lats)*0.95)],2),
           "max_ms":round(max(lats),2),"stddev_ms":round(statistics.stdev(lats),2)if len(lats)>1 else 0}
        results.append(r)
        print(f"    Min:{r['min_ms']}ms | Mean:{r['mean_ms']}ms | P95:{r['p95_ms']}ms | Max:{r['max_ms']}ms")
    return results

def create_db(name, args):
    if name=="postgresql": return PostgreSQLBench(host=args.host,port=5432)
    elif name=="timescaledb": return TimescaleDBBench(host=args.host,port=5433)
    elif name=="clickhouse": return ClickHouseBench(host=args.host,port=9000)
    elif name=="influxdb": return InfluxDBBench(url=f"http://{args.host}:8086",token=args.influx_token)

def main():
    p = argparse.ArgumentParser(description="MLab Database Benchmark")
    p.add_argument("--csv",required=True); p.add_argument("--db",required=True,choices=["postgresql","timescaledb","clickhouse","influxdb","all"])
    p.add_argument("--test",choices=["write","query","both"],default="both"); p.add_argument("--batch-size",type=int,default=20000)
    p.add_argument("--query-retries",type=int,default=20); p.add_argument("--limit",type=int,default=None)
    p.add_argument("--host",default="localhost"); p.add_argument("--influx-token",default="mlab-bench-token")
    args = p.parse_args()

    rows = load_csv(args.csv, args.limit); stats = get_stats(rows)
    print(f"\nData: {stats['min_ts']} -> {stats['max_ts']} | Nodes: {stats['node_ids']} | KPIs: {len(stats['kpi_names'])}")

    dbs = ["postgresql","timescaledb","clickhouse","influxdb"] if args.db=="all" else [args.db]
    all_r = []; os.makedirs("benchmark_results",exist_ok=True)

    for dn in dbs:
        try:
            print(f"\n{'#'*60}\n  {dn.upper()}\n{'#'*60}")
            db = create_db(dn, args)
            if args.test in ("write","both"): all_r.append(benchmark_writes(db, rows, args.batch_size))
            if args.test in ("query","both"): all_r.extend(benchmark_queries(db, stats, args.query_retries))
            db.close()
        except Exception as e: print(f"\n  ERROR: {e}"); import traceback; traceback.print_exc()

    # Save results
    if all_r:
        with open("benchmark_results/results.csv","w",newline="") as f:
            ks=set(); [ks.update(r.keys()) for r in all_r]
            w=csv.DictWriter(f,fieldnames=sorted(ks)); w.writeheader(); w.writerows(all_r)
        with open("benchmark_results/results.json","w") as f: json.dump(all_r,f,indent=2,default=str)

    # Print summary
    wr=[r for r in all_r if r.get("test")=="write"]
    if wr:
        print(f"\n{'='*70}\n  WRITE PERFORMANCE\n{'='*70}")
        print(f"  {'Database':<15}{'Rate (rows/s)':>14}{'Total Time':>12}{'Mean Delay':>12}{'P95 Delay':>11}")
        for r in wr: print(f"  {r['database']:<15}{r['ingestion_rate_rows_per_sec']:>14,.0f}{r['total_time_sec']:>10.1f}s{r['mean_batch_latency_ms']:>9.1f}ms{r['p95_batch_latency_ms']:>8.1f}ms")

    qr=[r for r in all_r if r.get("test")=="query"]
    if qr:
        print(f"\n{'='*70}\n  QUERY LATENCY (mean ms)\n{'='*70}")
        print(f"  {'Database':<15}{'Q1':>8}{'Q2':>8}{'Q3':>8}{'Q4':>8}{'Q5':>8}")
        for dn in dbs:
            dr=[r for r in qr if dn in r["database"].lower()]
            if dr:
                v={r["query"]:r["mean_ms"] for r in dr}; nm=dr[0]["database"]
                print(f"  {nm:<15}{v.get('Q1_RawData','-'):>8}{v.get('Q2_OutOfRange','-'):>8}{v.get('Q3_Aggregation','-'):>8}{v.get('Q4_Downsampling','-'):>8}{v.get('Q5_TwoNodeCompare','-'):>8}")

    print(f"\n  Results saved to benchmark_results/")

if __name__=="__main__": main()