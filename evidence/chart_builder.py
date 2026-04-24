"""
PROVCHAIN — Chart Builder
=========================
Generates charts for the evidence bundle using matplotlib.
"""

import io
import matplotlib.pyplot as plt

from monitoring.models import PropagationReport, ScanRecord


def build_propagation_chart(report: PropagationReport, scan_record: ScanRecord) -> bytes:
    """
    Generates a propagation_timeline.png (or domain risk distribution pie chart) 
    visualizing the spread of the asset.
    Returns the raw PNG image bytes.
    """
    risk_dist = report.metrics.domain_risk_distribution
    
    labels = list(risk_dist.keys())
    sizes = list(risk_dist.values())
    
    # Define colors mapped to risk levels
    color_map = {
        'HIGH': '#ea4335',     # Red
        'MEDIUM': '#fbbc04',   # Yellow
        'LOW': '#34a853',      # Green
    }
    
    colors = [color_map.get(label.upper(), '#9aa0a6') for label in labels]
    
    fig, ax = plt.subplots(figsize=(6, 4))
    
    if sum(sizes) > 0:
        ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.title('Propagation Domain Risk Distribution')
    else:
        # Render an empty placeholder plot if no hits
        ax.text(0.5, 0.5, 'No propagation recorded', 
                horizontalalignment='center', verticalalignment='center', fontsize=12)
        ax.axis('off')
        plt.title('Propagation Domain Risk Distribution')
        
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig)
    
    return buffer.getvalue()
