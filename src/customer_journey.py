#!/usr/bin/env python3
"""
BlackRoad Customer Journey Mapper
Maps, analyzes and visualizes multi-channel customer journeys.
"""

import dataclasses
import sqlite3
import datetime
import json
import argparse
import sys
import os
import math
import uuid
from typing import Optional, List, Dict, Any, Tuple
from collections import defaultdict, Counter
import itertools

# ── ANSI Colors ────────────────────────────────────────────────────────────────
RED     = "\033[0;31m"
GREEN   = "\033[0;32m"
YELLOW  = "\033[1;33m"
CYAN    = "\033[0;36m"
BLUE    = "\033[0;34m"
MAGENTA = "\033[0;35m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
NC      = "\033[0m"

DEFAULT_DB = os.path.expanduser("~/.blackroad/customer_journey.db")


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Touchpoint:
    id: str
    session_id: str
    customer_id: str
    channel: str
    page: str
    event_type: str
    timestamp: str
    duration_ms: int
    metadata: Dict[str, Any]


@dataclasses.dataclass
class FunnelStage:
    id: str
    name: str
    position: int
    description: str
    entry_event: str
    exit_event: str


@dataclasses.dataclass
class CustomerSession:
    id: str
    customer_id: str
    start_time: str
    end_time: Optional[str]
    channel: str
    device: str
    converted: bool
    conversion_value: float


@dataclasses.dataclass
class ConversionPath:
    id: str
    session_id: str
    stages_visited: List[str]
    path_signature: str
    converted: bool
    created_at: str


@dataclasses.dataclass
class DropoffEvent:
    id: str
    session_id: str
    stage_id: str
    stage_name: str
    timestamp: str
    reason: str


# ── Core Mapper ────────────────────────────────────────────────────────────────

class CustomerJourneyMapper:
    """Maps and analyzes multi-stage customer journeys with funnel analytics."""

    def __init__(self, db_path: str = DEFAULT_DB):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        """Initialize the 5-table schema."""
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS funnel_stages (
                id           TEXT PRIMARY KEY,
                name         TEXT NOT NULL UNIQUE,
                position     INTEGER NOT NULL,
                description  TEXT,
                entry_event  TEXT,
                exit_event   TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id               TEXT PRIMARY KEY,
                customer_id      TEXT NOT NULL,
                start_time       TEXT NOT NULL,
                end_time         TEXT,
                channel          TEXT NOT NULL,
                device           TEXT NOT NULL,
                converted        INTEGER DEFAULT 0,
                conversion_value REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS touchpoints (
                id           TEXT PRIMARY KEY,
                session_id   TEXT NOT NULL,
                customer_id  TEXT NOT NULL,
                channel      TEXT NOT NULL,
                page         TEXT NOT NULL,
                event_type   TEXT NOT NULL,
                timestamp    TEXT NOT NULL,
                duration_ms  INTEGER DEFAULT 0,
                metadata     TEXT DEFAULT '{}',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS conversion_paths (
                id             TEXT PRIMARY KEY,
                session_id     TEXT NOT NULL,
                stages_visited TEXT NOT NULL,
                path_signature TEXT NOT NULL,
                converted      INTEGER DEFAULT 0,
                created_at     TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS dropoff_events (
                id         TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                stage_id   TEXT NOT NULL,
                stage_name TEXT NOT NULL,
                timestamp  TEXT NOT NULL,
                reason     TEXT DEFAULT 'unknown',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_tp_session   ON touchpoints(session_id);
            CREATE INDEX IF NOT EXISTS idx_tp_customer  ON touchpoints(customer_id);
            CREATE INDEX IF NOT EXISTS idx_tp_timestamp ON touchpoints(timestamp);
            CREATE INDEX IF NOT EXISTS idx_cp_sig       ON conversion_paths(path_signature);
        """)
        self.conn.commit()

    # ── Stage Management ───────────────────────────────────────────────────────

    def define_funnel_stage(
        self,
        name: str,
        position: int,
        description: str = "",
        entry_event: str = "",
        exit_event: str = "",
    ) -> FunnelStage:
        """Insert or replace a funnel stage definition."""
        stage_id = str(uuid.uuid4())
        cur = self.conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO funnel_stages
               (id, name, position, description, entry_event, exit_event)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (stage_id, name, position, description, entry_event, exit_event),
        )
        self.conn.commit()
        return FunnelStage(stage_id, name, position, description, entry_event, exit_event)

    # ── Session Lifecycle ──────────────────────────────────────────────────────

    def start_session(
        self, customer_id: str, channel: str, device: str = "unknown"
    ) -> str:
        """Create and persist a new customer session; returns session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO sessions
               (id, customer_id, start_time, channel, device, converted, conversion_value)
               VALUES (?, ?, ?, ?, ?, 0, 0.0)""",
            (session_id, customer_id, now, channel, device),
        )
        self.conn.commit()
        return session_id

    def record_touchpoint(
        self,
        session_id: str,
        customer_id: str,
        channel: str,
        page: str,
        event_type: str,
        duration_ms: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a touchpoint and detect funnel stage transitions."""
        tp_id = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        meta_str = json.dumps(metadata or {})
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO touchpoints
               (id, session_id, customer_id, channel, page, event_type,
                timestamp, duration_ms, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tp_id, session_id, customer_id, channel, page, event_type,
             now, duration_ms, meta_str),
        )
        self.conn.commit()

        # Check for stage transition based on entry_event match
        stage_info: Dict[str, Any] = {}
        cur.execute(
            "SELECT * FROM funnel_stages WHERE entry_event = ? ORDER BY position",
            (event_type,),
        )
        row = cur.fetchone()
        if row:
            stage_info = {
                "stage_entered": row["name"],
                "position": row["position"],
                "stage_id": row["id"],
            }
        return {"touchpoint_id": tp_id, **stage_info}

    def end_session(
        self,
        session_id: str,
        converted: bool = False,
        conversion_value: float = 0.0,
    ) -> ConversionPath:
        """Close a session, build the conversion path, and detect dropoffs."""
        now = datetime.datetime.utcnow().isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """UPDATE sessions SET end_time=?, converted=?, conversion_value=?
               WHERE id=?""",
            (now, int(converted), conversion_value, session_id),
        )

        # Build ordered list of stages visited in this session
        cur.execute(
            """SELECT DISTINCT fs.id, fs.name, fs.position
               FROM touchpoints tp
               JOIN funnel_stages fs ON tp.event_type = fs.entry_event
               WHERE tp.session_id = ?
               ORDER BY fs.position""",
            (session_id,),
        )
        stages = cur.fetchall()
        stages_visited = [r["name"] for r in stages]
        path_signature = " → ".join(stages_visited) if stages_visited else "direct"

        path_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO conversion_paths
               (id, session_id, stages_visited, path_signature, converted, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (path_id, session_id, json.dumps(stages_visited),
             path_signature, int(converted), now),
        )

        # Detect dropoffs: all stages NOT visited
        if not converted:
            cur.execute("SELECT * FROM funnel_stages ORDER BY position")
            all_stages = cur.fetchall()
            visited_names = set(stages_visited)
            for st in all_stages:
                if st["name"] not in visited_names:
                    drop_id = str(uuid.uuid4())
                    cur.execute(
                        """INSERT INTO dropoff_events
                           (id, session_id, stage_id, stage_name, timestamp, reason)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (drop_id, session_id, st["id"], st["name"], now, "stage_not_reached"),
                    )
                    break  # Record only the first missed stage as the dropoff point

        self.conn.commit()
        return ConversionPath(
            path_id, session_id, stages_visited, path_signature, converted, now
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    def analyze_funnel(self, days: int = 30) -> List[Dict[str, Any]]:
        """Per-stage funnel metrics: entry count, conversion rate, avg time, drop-off rate."""
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(days=days)
        ).isoformat()
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM funnel_stages ORDER BY position")
        stages = cur.fetchall()

        results = []
        total_sessions_query = cur.execute(
            "SELECT COUNT(*) FROM sessions WHERE start_time >= ?", (cutoff,)
        ).fetchone()[0]

        for i, stage in enumerate(stages):
            # Sessions that reached this stage
            cur.execute(
                """SELECT COUNT(DISTINCT tp.session_id) FROM touchpoints tp
                   JOIN sessions s ON tp.session_id = s.id
                   WHERE tp.event_type = ? AND s.start_time >= ?""",
                (stage["entry_event"], cutoff),
            )
            entry_count = cur.fetchone()[0]

            # Sessions that exited (reached next stage)
            exit_count = 0
            if i + 1 < len(stages):
                next_stage = stages[i + 1]
                cur.execute(
                    """SELECT COUNT(DISTINCT tp.session_id) FROM touchpoints tp
                       JOIN sessions s ON tp.session_id = s.id
                       WHERE tp.event_type = ? AND s.start_time >= ?""",
                    (next_stage["entry_event"], cutoff),
                )
                exit_count = cur.fetchone()[0]
            else:
                # Last stage: exits = conversions
                cur.execute(
                    """SELECT COUNT(DISTINCT s.id) FROM sessions s
                       JOIN touchpoints tp ON s.id = tp.session_id
                       WHERE s.converted = 1 AND tp.event_type = ?
                       AND s.start_time >= ?""",
                    (stage["entry_event"], cutoff),
                )
                exit_count = cur.fetchone()[0]

            conversion_rate = (exit_count / entry_count * 100) if entry_count else 0.0
            drop_off_rate = 100.0 - conversion_rate

            # Average duration at this stage (ms)
            cur.execute(
                """SELECT AVG(duration_ms) FROM touchpoints tp
                   JOIN sessions s ON tp.session_id = s.id
                   WHERE tp.event_type = ? AND s.start_time >= ?""",
                (stage["entry_event"], cutoff),
            )
            avg_dur = cur.fetchone()[0] or 0.0

            results.append({
                "stage_id": stage["id"],
                "stage_name": stage["name"],
                "position": stage["position"],
                "entry_count": entry_count,
                "exit_count": exit_count,
                "conversion_rate": round(conversion_rate, 2),
                "drop_off_rate": round(drop_off_rate, 2),
                "avg_duration_ms": round(avg_dur, 2),
            })
        return results

    def get_top_conversion_paths(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Group path signatures and return top paths by frequency."""
        cur = self.conn.cursor()
        cur.execute(
            """SELECT path_signature,
                      COUNT(*) as occurrences,
                      SUM(converted) as conversions,
                      ROUND(100.0 * SUM(converted) / COUNT(*), 2) as conversion_rate
               FROM conversion_paths
               GROUP BY path_signature
               ORDER BY occurrences DESC
               LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    def analyze_dropoffs(self, stage_id: str) -> Dict[str, Any]:
        """Aggregate dropoff reasons, time-of-day patterns, and channel breakdown."""
        cur = self.conn.cursor()

        # Reason aggregation
        cur.execute(
            """SELECT reason, COUNT(*) as count
               FROM dropoff_events WHERE stage_id = ?
               GROUP BY reason ORDER BY count DESC""",
            (stage_id,),
        )
        reasons = {r["reason"]: r["count"] for r in cur.fetchall()}

        # Time-of-day pattern (hour buckets)
        cur.execute(
            """SELECT CAST(SUBSTR(timestamp, 12, 2) AS INTEGER) as hour, COUNT(*) as count
               FROM dropoff_events WHERE stage_id = ?
               GROUP BY hour ORDER BY hour""",
            (stage_id,),
        )
        time_pattern = {r["hour"]: r["count"] for r in cur.fetchall()}

        # Channel breakdown via joined session
        cur.execute(
            """SELECT s.channel, COUNT(*) as count
               FROM dropoff_events de
               JOIN sessions s ON de.session_id = s.id
               WHERE de.stage_id = ?
               GROUP BY s.channel ORDER BY count DESC""",
            (stage_id,),
        )
        channels = {r["channel"]: r["count"] for r in cur.fetchall()}

        return {
            "stage_id": stage_id,
            "reasons": reasons,
            "time_of_day": time_pattern,
            "by_channel": channels,
            "total_dropoffs": sum(reasons.values()),
        }

    def get_channel_attribution(self, days: int = 30) -> List[Dict[str, Any]]:
        """Per-channel sessions, conversions, conversion_rate, avg_value."""
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(days=days)
        ).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """SELECT channel,
                      COUNT(*) as sessions,
                      SUM(converted) as conversions,
                      ROUND(100.0 * SUM(converted) / COUNT(*), 2) as conversion_rate,
                      ROUND(AVG(CASE WHEN converted=1 THEN conversion_value ELSE NULL END), 2)
                          as avg_value
               FROM sessions WHERE start_time >= ?
               GROUP BY channel ORDER BY conversions DESC""",
            (cutoff,),
        )
        return [dict(r) for r in cur.fetchall()]

    def compute_customer_ltv_segments(self, buckets: int = 5) -> List[Dict[str, Any]]:
        """Segment customers by total conversion_value using equal-width bucketing."""
        cur = self.conn.cursor()
        cur.execute(
            """SELECT customer_id, SUM(conversion_value) as ltv
               FROM sessions WHERE converted = 1
               GROUP BY customer_id"""
        )
        rows = cur.fetchall()
        if not rows:
            return []

        ltvs = [r["ltv"] for r in rows]
        min_ltv, max_ltv = min(ltvs), max(ltvs)
        width = (max_ltv - min_ltv) / buckets if max_ltv > min_ltv else 1.0

        segments: List[Dict[str, Any]] = []
        for i in range(buckets):
            lo = min_ltv + i * width
            hi = lo + width
            members = [r["customer_id"] for r in rows if lo <= r["ltv"] < hi]
            # Last bucket is inclusive on right
            if i == buckets - 1:
                members = [r["customer_id"] for r in rows if lo <= r["ltv"] <= hi]
            segments.append({
                "bucket": i + 1,
                "ltv_min": round(lo, 2),
                "ltv_max": round(hi, 2),
                "customer_count": len(members),
                "label": f"Segment {i + 1}",
            })
        return segments

    def get_journey_heatmap(self, hours: int = 168) -> Dict[str, Any]:
        """Return a 24×7 matrix of touchpoint counts by hour-of-day × day-of-week."""
        cutoff = (
            datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        ).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """SELECT timestamp FROM touchpoints WHERE timestamp >= ?""",
            (cutoff,),
        )
        rows = cur.fetchall()

        # matrix[day_of_week][hour] — Mon=0 … Sun=6
        matrix: List[List[int]] = [[0] * 24 for _ in range(7)]
        for r in rows:
            try:
                dt = datetime.datetime.fromisoformat(r["timestamp"])
                matrix[dt.weekday()][dt.hour] += 1
            except (ValueError, TypeError):
                pass

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return {
            "matrix": matrix,
            "day_labels": day_names,
            "hour_labels": [f"{h:02d}:00" for h in range(24)],
            "total_touchpoints": sum(sum(row) for row in matrix),
        }

    def close(self) -> None:
        self.conn.close()


# ── ASCII Funnel Visualisation ─────────────────────────────────────────────────

def render_funnel(stages: List[Dict[str, Any]]) -> None:
    """Render an ASCII funnel with unicode box chars."""
    if not stages:
        print(f"{YELLOW}No funnel stages defined.{NC}")
        return

    max_width = 60
    print(f"\n{BOLD}{CYAN}{'═' * max_width}{NC}")
    print(f"{BOLD}{CYAN}  CUSTOMER JOURNEY FUNNEL{NC}")
    print(f"{BOLD}{CYAN}{'═' * max_width}{NC}\n")

    top_entry = stages[0]["entry_count"] if stages else 1

    for idx, stage in enumerate(stages):
        entry = stage["entry_count"]
        ratio = (entry / top_entry) if top_entry else 0
        bar_width = max(4, int(ratio * (max_width - 20)))
        bar = "█" * bar_width
        padding = " " * ((max_width - bar_width) // 2)

        color = GREEN if stage["conversion_rate"] >= 50 else (
            YELLOW if stage["conversion_rate"] >= 25 else RED
        )

        print(f"  {BOLD}Stage {stage['position']:>2}: {stage['stage_name']:<20}{NC}")
        print(f"  {padding}{color}{bar}{NC}")
        print(
            f"  {'':>4}  Entries: {entry:<6}  "
            f"Conv: {color}{stage['conversion_rate']:>5.1f}%{NC}  "
            f"Drop: {RED}{stage['drop_off_rate']:>5.1f}%{NC}  "
            f"Avg: {DIM}{stage['avg_duration_ms']:.0f}ms{NC}"
        )
        if idx < len(stages) - 1:
            arrow_pad = " " * (max_width // 2 - 1)
            print(f"  {arrow_pad}{DIM}▼{NC}")
    print(f"\n  {BOLD}{CYAN}{'═' * max_width}{NC}\n")


def render_heatmap(heatmap: Dict[str, Any]) -> None:
    """Print a compact 7×24 heatmap grid."""
    matrix    = heatmap["matrix"]
    day_labels = heatmap["day_labels"]
    flat       = [v for row in matrix for v in row]
    max_val    = max(flat) if flat else 1
    blocks     = " ░▒▓█"

    print(f"\n{BOLD}{CYAN}  JOURNEY HEATMAP  (last {heatmap['total_touchpoints']} touchpoints){NC}")
    header = "     " + "".join(f"{h:>3}" for h in range(0, 24, 2))
    print(f"{DIM}{header}{NC}")
    for d_idx, day in enumerate(day_labels):
        row = ""
        for h in range(24):
            val = matrix[d_idx][h]
            lvl = int((val / max_val) * (len(blocks) - 1)) if max_val else 0
            row += blocks[lvl] * 2 if h % 2 == 0 else ""
        print(f"  {BOLD}{day}{NC}  {row}")
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def cmd_funnel(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    if args.funnel_cmd == "add":
        stage = mapper.define_funnel_stage(
            args.name, args.position,
            getattr(args, "description", ""),
            getattr(args, "entry_event", ""),
            getattr(args, "exit_event", ""),
        )
        print(f"{GREEN}✓ Stage '{stage.name}' (pos {stage.position}) created.{NC}")
    elif args.funnel_cmd == "show":
        stages = mapper.analyze_funnel(days=getattr(args, "days", 30))
        render_funnel(stages)
    else:
        print(f"{RED}Unknown funnel subcommand.{NC}")


def cmd_session(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    sid = mapper.start_session(args.customer_id, args.channel,
                               getattr(args, "device", "unknown"))
    print(f"{GREEN}✓ Session started: {sid}{NC}")


def cmd_touchpoint(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    meta = {}
    if hasattr(args, "meta") and args.meta:
        try:
            meta = json.loads(args.meta)
        except json.JSONDecodeError:
            pass
    result = mapper.record_touchpoint(
        args.session_id, args.customer_id, args.channel,
        args.page, args.event_type,
        getattr(args, "duration_ms", 0), meta,
    )
    print(f"{GREEN}✓ Touchpoint recorded: {result}{NC}")


def cmd_analyze(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    days = getattr(args, "days", 30)
    stages = mapper.analyze_funnel(days=days)
    render_funnel(stages)
    print(f"{CYAN}Funnel analysis over last {days} days — {len(stages)} stages.{NC}")


def cmd_paths(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    limit = getattr(args, "limit", 10)
    paths = mapper.get_top_conversion_paths(limit=limit)
    print(f"\n{BOLD}{CYAN}  TOP {limit} CONVERSION PATHS{NC}")
    print(f"  {'Path Signature':<50} {'Count':>6}  {'Conv%':>6}")
    print(f"  {'─' * 50} {'─' * 6}  {'─' * 6}")
    for p in paths:
        print(
            f"  {p['path_signature']:<50} "
            f"{p['occurrences']:>6}  "
            f"{GREEN}{p['conversion_rate']:>5.1f}%{NC}"
        )
    print()


def cmd_dropoffs(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    result = mapper.analyze_dropoffs(args.stage_id)
    print(f"\n{BOLD}{CYAN}  DROPOFF ANALYSIS — Stage {args.stage_id[:8]}…{NC}")
    print(f"  Total dropoffs : {result['total_dropoffs']}")
    print(f"  Reasons        : {result['reasons']}")
    print(f"  By channel     : {result['by_channel']}")
    print(f"  Time of day    : {result['time_of_day']}\n")


def cmd_channels(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    days = getattr(args, "days", 30)
    data = mapper.get_channel_attribution(days=days)
    print(f"\n{BOLD}{CYAN}  CHANNEL ATTRIBUTION (last {days}d){NC}")
    print(f"  {'Channel':<20} {'Sessions':>8}  {'Conv':>6}  {'Rate%':>6}  {'Avg $':>8}")
    print(f"  {'─' * 20} {'─' * 8}  {'─' * 6}  {'─' * 6}  {'─' * 8}")
    for r in data:
        print(
            f"  {r['channel']:<20} {r['sessions']:>8}  "
            f"{r['conversions']:>6}  "
            f"{GREEN}{r['conversion_rate']:>5.1f}%{NC}  "
            f"{r['avg_value'] or 0.0:>8.2f}"
        )
    print()


def cmd_heatmap(mapper: CustomerJourneyMapper, args: argparse.Namespace) -> None:
    hours = getattr(args, "hours", 168)
    hm = mapper.get_journey_heatmap(hours=hours)
    render_heatmap(hm)


# ── Entry Point ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="customer_journey",
        description="BlackRoad Customer Journey Mapper",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    sub = parser.add_subparsers(dest="command")

    # funnel
    p_funnel = sub.add_parser("funnel", help="Manage funnel stages")
    fsub = p_funnel.add_subparsers(dest="funnel_cmd")
    p_add = fsub.add_parser("add", help="Add a funnel stage")
    p_add.add_argument("name")
    p_add.add_argument("position", type=int)
    p_add.add_argument("--description", default="")
    p_add.add_argument("--entry-event", dest="entry_event", default="")
    p_add.add_argument("--exit-event", dest="exit_event", default="")
    fsub.add_parser("show", help="Show funnel analysis").add_argument(
        "--days", type=int, default=30
    )

    # session
    p_sess = sub.add_parser("session", help="Start a customer session")
    p_sess.add_argument("customer_id")
    p_sess.add_argument("channel")
    p_sess.add_argument("--device", default="unknown")

    # touchpoint
    p_tp = sub.add_parser("touchpoint", help="Record a touchpoint")
    p_tp.add_argument("session_id")
    p_tp.add_argument("customer_id")
    p_tp.add_argument("channel")
    p_tp.add_argument("page")
    p_tp.add_argument("event_type")
    p_tp.add_argument("--duration-ms", dest="duration_ms", type=int, default=0)
    p_tp.add_argument("--meta", default="{}")

    # analyze
    p_an = sub.add_parser("analyze", help="Full funnel analysis")
    p_an.add_argument("--days", type=int, default=30)

    # paths
    p_paths = sub.add_parser("paths", help="Top conversion paths")
    p_paths.add_argument("--limit", type=int, default=10)

    # dropoffs
    p_drop = sub.add_parser("dropoffs", help="Dropoff analysis for a stage")
    p_drop.add_argument("stage_id")

    # channels
    p_ch = sub.add_parser("channels", help="Channel attribution report")
    p_ch.add_argument("--days", type=int, default=30)

    # heatmap
    p_hm = sub.add_parser("heatmap", help="Journey heatmap")
    p_hm.add_argument("--hours", type=int, default=168)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    mapper = CustomerJourneyMapper(db_path=args.db)
    try:
        dispatch = {
            "funnel":     cmd_funnel,
            "session":    cmd_session,
            "touchpoint": cmd_touchpoint,
            "analyze":    cmd_analyze,
            "paths":      cmd_paths,
            "dropoffs":   cmd_dropoffs,
            "channels":   cmd_channels,
            "heatmap":    cmd_heatmap,
        }
        fn = dispatch.get(args.command)
        if fn:
            fn(mapper, args)
        else:
            print(f"{RED}Unknown command: {args.command}{NC}")
            sys.exit(1)
    finally:
        mapper.close()


if __name__ == "__main__":
    main()
