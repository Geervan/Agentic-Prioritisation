from pathlib import Path
from datetime import datetime
import json

def generate_html_report(testcases, final_order, explanations):
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = reports_dir / f"report_{timestamp}.html"

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
        </style>
    </head>

    <body>
        <h1>Agentic AI Test Prioritization Report</h1>
        <div class="timestamp">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>

        <h2>Final Ranking</h2>
        <p><strong>{final_order}</strong></p>

        <h2>Detailed Testcase Breakdown</h2>

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
    </body>
    </html>
    """

    # Save file
    with report_path.open("w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nHTML report saved at: {report_path}\n")
    return report_path
