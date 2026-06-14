"""
MapReduce Engine — pure Python parallel processing.
Pipeline: Split → Map → Shuffle → Reduce
"""

import re
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict


# ──────────────────────────────────────────────────────────────────
# Patterns
# ──────────────────────────────────────────────────────────────────
HTTP_STATUS_PATTERN = re.compile(r'" (\d{3}) ')
HOUR_PATTERN        = re.compile(r'\[(\d{2})/\w+/\d{4}:(\d{2}):')
IP_PATTERN          = re.compile(r'^(\d{1,3}(?:\.\d{1,3}){3})')
METHOD_PATTERN      = re.compile(r'"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)')

CHUNK_SIZE = 500   # lines per chunk


class MapReduceEngine:
    """
    Orchestrates a full MapReduce workflow over a log file.

    Stages
    ------
    1. split()   – break file into line-chunks
    2. map()     – emit (key, 1) pairs per chunk (parallel threads)
    3. shuffle() – group values by key
    4. reduce()  – sum counts per key
    """

    def __init__(self, filepath: str, chunk_size: int = CHUNK_SIZE):
        self.filepath   = filepath
        self.chunk_size = chunk_size

    # ── Stage 1: Split ────────────────────────────────────────────
    def split(self) -> list[list[str]]:
        """Read file and divide into fixed-size line chunks."""
        with open(self.filepath, "r", encoding="utf-8", errors="replace") as fh:
            lines = [line.rstrip("\n") for line in fh if line.strip()]

        num_chunks = max(1, math.ceil(len(lines) / self.chunk_size))
        chunks = [
            lines[i * self.chunk_size : (i + 1) * self.chunk_size]
            for i in range(num_chunks)
        ]
        return chunks

    # ── Stage 2: Map (single chunk) ───────────────────────────────
    @staticmethod
    def map_chunk(chunk: list[str]) -> list[tuple[str, int]]:
        """
        Emit (key, 1) pairs for every log line in the chunk.
        Keys:
          - HTTP_<status>  e.g. HTTP_404
          - HOUR_<hh>      e.g. HOUR_14
          - METHOD_<verb>  e.g. METHOD_GET
          - IP_<address>   e.g. IP_192.168.1.1
        """
        pairs: list[tuple[str, int]] = []
        for line in chunk:
            m = HTTP_STATUS_PATTERN.search(line)
            if m:
                pairs.append((f"HTTP_{m.group(1)}", 1))

            m = HOUR_PATTERN.search(line)
            if m:
                pairs.append((f"HOUR_{m.group(2)}", 1))

            m = METHOD_PATTERN.search(line)
            if m:
                pairs.append((f"METHOD_{m.group(1)}", 1))

            m = IP_PATTERN.match(line)
            if m:
                pairs.append((f"IP_{m.group(1)}", 1))

        return pairs

    # ── Stage 3: Shuffle & Sort ───────────────────────────────────
    @staticmethod
    def shuffle(all_pairs: list[tuple[str, int]]) -> dict[str, list[int]]:
        """Group values by key (sorted for reproducibility)."""
        grouped: dict[str, list[int]] = defaultdict(list)
        for key, value in all_pairs:
            grouped[key].append(value)
        return dict(sorted(grouped.items()))

    # ── Stage 4: Reduce ───────────────────────────────────────────
    @staticmethod
    def reduce(grouped: dict[str, list[int]]) -> dict[str, int]:
        """Sum values for each key."""
        return {key: sum(values) for key, values in grouped.items()}

    # ── Orchestrator ──────────────────────────────────────────────
    def run(self) -> dict:
        """
        Execute the full MapReduce pipeline and return structured results.
        """
        # 1. Split
        chunks = self.split()
        total_lines = sum(len(c) for c in chunks)
        num_chunks  = len(chunks)

        # 2. Map — parallel using ThreadPoolExecutor
        all_pairs: list[tuple[str, int]] = []
        with ThreadPoolExecutor(max_workers=min(num_chunks, 8)) as pool:
            futures = {pool.submit(self.map_chunk, chunk): i
                       for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                all_pairs.extend(future.result())

        # 3. Shuffle
        grouped = self.shuffle(all_pairs)

        # 4. Reduce
        counts = self.reduce(grouped)

        # ── Post-process into clean analytics ─────────────────────
        http_errors   = {}
        hourly_traffic = {}
        method_counts  = {}
        top_ips        = {}

        for key, count in counts.items():
            if key.startswith("HTTP_"):
                code = key[5:]
                http_errors[code] = count
            elif key.startswith("HOUR_"):
                hour = key[5:]
                hourly_traffic[hour] = count
            elif key.startswith("METHOD_"):
                method = key[7:]
                method_counts[method] = count
            elif key.startswith("IP_"):
                ip = key[3:]
                top_ips[ip] = count

        # Keep only error codes (4xx / 5xx)
        error_codes = {
            code: cnt for code, cnt in http_errors.items()
            if code.startswith(("4", "5"))
        }

        # Top 10 IPs
        top_10_ips = dict(
            sorted(top_ips.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Busiest hours (sorted)
        sorted_hours = dict(sorted(hourly_traffic.items()))

        # Peak hour
        peak_hour = (
            max(hourly_traffic, key=hourly_traffic.get)
            if hourly_traffic else "N/A"
        )

        total_requests = sum(http_errors.values())
        total_errors   = sum(error_codes.values())
        error_rate     = (
            round(total_errors / total_requests * 100, 2) if total_requests else 0
        )

        return {
            "meta": {
                "total_lines":    total_lines,
                "num_chunks":     num_chunks,
                "chunk_size":     self.chunk_size,
                "total_requests": total_requests,
                "total_errors":   total_errors,
                "error_rate_pct": error_rate,
                "peak_hour":      peak_hour,
            },
            "http_status_counts": http_errors,
            "error_codes":        error_codes,
            "hourly_traffic":     sorted_hours,
            "method_counts":      method_counts,
            "top_ips":            top_10_ips,
        }
