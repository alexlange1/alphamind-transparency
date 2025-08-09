#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
import os
from typing import List, Tuple

# Resolve project directory relative to this script's location
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
NAV_PATH = os.path.join(PROJECT_DIR, "nav_history.tsv")
OUT_HTML = os.path.join(PROJECT_DIR, "nav.html")


def read_nav() -> List[Tuple[str, float]]:
    rows: List[Tuple[str, float]] = []
    if not os.path.exists(NAV_PATH):
        return rows
    with open(NAV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ts = row.get("timestamp")
            try:
                nav = float(row.get("nav_tao") or 0.0)
            except Exception:
                continue
            if ts:
                rows.append((ts, nav))
    return rows


def render_html(data: List[Tuple[str, float]]) -> str:
    # Filter out zero NAV entries
    filtered: List[Tuple[str, float]] = [
        (ts, nav) for ts, nav in data if isinstance(nav, (int, float)) and nav > 0.0
    ]
    if filtered:
        data = filtered

    labels = [ts for ts, _ in data]
    values = [nav for _, nav in data]

    # Dynamic y-axis bounds with small padding
    if values:
        vmin = min(values)
        vmax = max(values)
        if vmax == vmin:
            margin = (abs(vmin) * 0.01) if vmin != 0 else 1.0
        else:
            margin = (vmax - vmin) * 0.05
        y_min = vmin - margin
        y_max = vmax + margin
    else:
        y_min = 0
        y_max = 1

    # Inline the data to avoid local file CORS issues
    labels_js = json.dumps(labels)
    values_js = json.dumps(values)
    return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <meta http-equiv=\"refresh\" content=\"60\" />
  <title>TAO20 NAV</title>
  <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
  <style>
    body {{ font-family: -apple-system, system-ui, Segoe UI, Roboto, Helvetica, Arial; margin: 20px; }}
    #wrap {{ max-width: 980px; margin: 0 auto; }}
    canvas {{ width: 100%; height: 420px; }}
  </style>
  </head>
  <body>
  <div id=\"wrap\">
    <h2>TAO20 NAV (τ)</h2>
    <canvas id=\"navChart\"></canvas>
  </div>
  <script>
    const labels = {labels_js};
    const values = {values_js};
    const yMin = {y_min};
    const yMax = {y_max};
    const ctx = document.getElementById('navChart').getContext('2d');
    const chart = new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: labels,
        datasets: [{{
          label: 'NAV (τ)',
          data: values,
          borderColor: 'rgba(54, 162, 235, 1)',
          backgroundColor: 'rgba(54, 162, 235, 0.15)',
          tension: 0.2,
          pointRadius: 0
        }}]
      }},
      options: {{
        responsive: true,
        scales: {{
          x: {{
            ticks: {{ maxRotation: 45, minRotation: 45, autoSkip: true }},
          }},
          y: {{ beginAtZero: false, min: yMin, max: yMax }}
        }},
        plugins: {{
          legend: {{ display: true }}
        }}
      }}
    }});
  </script>
  </body>
  </html>
"""


def main() -> None:
    data = read_nav()
    html_doc = render_html(data)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_doc)


if __name__ == "__main__":
    main()


