from pathlib import Path
from datetime import datetime
import json

def generate_html_report(testcases, final_order, explanations, dataset_name: str, validation_result=None):
    # Create dataset-specific subdirectory under D:/PBL/reports
    dataset_reports_dir = Path("D:/PBL/reports") / dataset_name
    dataset_reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = dataset_reports_dir / f"report_{dataset_name}_{timestamp}.html"

    # Color rules based on priority
    def priority_color(idx):
        if idx == 0:
            return "#ff6b6b"   # High - Red
        elif idx == 1:
            return "#ffa502"   # Medium - Orange
        else:
            return "#1e90ff"   # Low - Blue

    # HTML TEMPLATE
    html = f"""
    <html>
    <head>
        <title>Agentic AI Test Prioritization Report</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f4f6f9;
                padding: 20px;
            }}

            h1 {{
                color: #333;
                text-align: center;
                margin-bottom: 10px;
            }}

            .timestamp {{
                text-align: center;
                margin-bottom: 25px;
                color: #666;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            }}

            th {{
                background: #2f3542;
                color: white;
                padding: 12px;
                font-size: 16px;
            }}

            td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #eee;
            }}

            .priority-badge {{
                padding: 6px 12px;
                color: white;
                font-weight: bold;
                border-radius: 6px;
            }}

            .table-container {{
                max-height: 600px;
                overflow-y: auto;
                border-radius: 10px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.15);
            }}
        </style>
    </head>

    <body>
        <h1>Agentic AI Test Prioritization Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

        <h2>Final Ranking</h2>
        <p><strong>{final_order}</strong></p>

        """

    # Add validation metrics FIRST if available
    if validation_result:
        apfd_scores = validation_result.get("apfd_scores", {})
        early_detection = validation_result.get("early_fault_detection", {})
        wasted_effort = validation_result.get("wasted_effort", 0)
        time_saved = validation_result.get("time_saved", 0.0)
        total_tests = validation_result.get("total_tests", 0)

        agentic_apfd = apfd_scores.get("agentic_apfd", 0)
        random_apfd = apfd_scores.get("random_apfd", 0)
        fifo_apfd = apfd_scores.get("fifo_apfd", 0)
        reverse_apfd = apfd_scores.get("reverse_apfd", 0)

        html += f"""
        <h2>Validation Metrics</h2>
        <div class="table-container">
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Description</th>
            </tr>
            <tr>
                <td><strong>APFD (Agentic AI)</strong></td>
                <td>{agentic_apfd:.4f}</td>
                <td>[Average Percentage of Faults Detected - Higher is better, 0-1 scale]</td>
            </tr>
            <tr>
                <td><strong>APFD (Random Baseline)</strong></td>
                <td>{random_apfd:.4f}</td>
                <td>[Random ordering APFD - baseline for comparison]</td>
            </tr>
            <tr>
                <td><strong>APFD (Original Order)</strong></td>
                <td>{fifo_apfd:.4f}</td>
                <td>[Original FIFO test order APFD - current status baseline]</td>
            </tr>
            <tr>
                <td><strong>APFD (Reverse Order)</strong></td>
                <td>{reverse_apfd:.4f}</td>
                <td>[Worst-case ordering APFD - lower bound comparison]</td>
            </tr>
            <tr>
                <td><strong>Wasted Effort</strong></td>
                <td>{wasted_effort} passing tests</td>
                <td>[Passing tests executed before all faults found - Lower is better]</td>
            </tr>
            <tr>
                <td><strong>Time Saved vs Random</strong></td>
                <td>{time_saved:.2f} seconds</td>
                <td>[Cumulative execution time savings compared to random ordering]</td>
            </tr>
        """

        # Add early fault detection rows
        if early_detection:
            for k in sorted(early_detection.keys()):
                k_percent = round(100 * k / max(1, total_tests), 1)
                efd_value = early_detection[k]
                html += f"""
            <tr>
                <td><strong>Early Fault Detection @ {k_percent:.0f}%</strong></td>
                <td>{efd_value:.2f}%</td>
                <td>[Percentage of failing tests caught in first {k_percent:.0f}% of tests]</td>
            </tr>
        """

        html += """
        </table>
        </div>
        """

    html += """
        <h2>Detailed Testcase Breakdown</h2>

        <div class="table-container">
        <table>
            <tr>
                <th>Priority</th>
                <th>ID</th>
                <th>Name</th>
                <th>Component</th>
                <th>Element</th>
                <th>Reason</th>
            </tr>
    """

    # Populate table rows
    for idx, tc_id in enumerate(final_order):
        tc = next(t for t in testcases if t["id"] == tc_id)
        color = priority_color(idx)

        reason = explanations.get(str(tc_id), "No explanation available")

        html += f"""
            <tr>
                <td><span class="priority-badge" style="background:{color};">#{idx+1}</span></td>
                <td>{tc['id']}</td>
                <td>{tc['name']}</td>
                <td>{tc['component']}</td>
                <td>{tc['ui_element']}</td>
                <td>{reason}</td>
            </tr>
        """

    html += """
        </table>
        </div>
    """

    html += """
    </body>
    </html>
    """

    # Save file
    with report_path.open("w", encoding="utf-8") as f:
        f.write(html)

    return report_path
