# ai-report-generator/backend/app/generators/chart_generator.py
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import os
from typing import List, Dict, Any
import logging
from app.config import settings
from app.utils.file_utils import FileUtils

logger = logging.getLogger(__name__)

class ChartGenerator:
    """
    Generates charts using Matplotlib for inclusion in reports.
    """
    
    def __init__(self):
        self.output_dir = settings.CHARTS_DIR
        FileUtils.ensure_directory(self.output_dir)
        
        # Set style
        plt.style.use('default')
        
    def generate_charts(self, report_id: str) -> List[str]:
        """
        Generate all required charts for the report.
        
        Args:
            report_id: Unique identifier for the report
            
        Returns:
            List of paths to generated chart images
        """
        chart_paths = []
        
        try:
            # Generate bar chart
            bar_chart_path = self._generate_bar_chart(report_id)
            if bar_chart_path:
                chart_paths.append(bar_chart_path)
            
            # Generate line chart
            line_chart_path = self._generate_line_chart(report_id)
            if line_chart_path:
                chart_paths.append(line_chart_path)
                
        except Exception as e:
            logger.error(f"Chart generation failed: {e}")
            # Return empty list if charts fail - report can still be generated
            
        return chart_paths
    
    def _generate_bar_chart(self, report_id: str) -> str:
        """
        Generate a bar chart showing performance metrics.
        """
        try:
            # Sample data
            categories = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
            values = [92.5, 89.3, 87.8, 90.1]
            
            # Create figure
            fig, ax = plt.subplots(figsize=(8, 5))
            
            # Create bars
            bars = ax.bar(categories, values, color=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D'])
            
            # Customize chart
            ax.set_ylabel('Percentage (%)')
            ax.set_title('Model Performance Metrics', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3, linestyle='--')
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height}%', ha='center', va='bottom')
            
            # Save chart
            filename = f"bar_chart_{report_id}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.tight_layout()
            plt.savefig(filepath, dpi=100, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Bar chart generated: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Bar chart generation failed: {e}")
            return None
    
    def _generate_line_chart(self, report_id: str) -> str:
        """
        Generate a line chart showing growth trends.
        """
        try:
            # Sample data
            x = [1, 2, 3, 4, 5, 6]
            y1 = [65, 72, 78, 85, 91, 95]
            y2 = [45, 58, 67, 74, 82, 88]
            
            # Create figure
            fig, ax = plt.subplots(figsize=(8, 5))
            
            # Plot lines
            ax.plot(x, y1, marker='o', linewidth=2, markersize=8, label='Proposed Model', color='#2E86AB')
            ax.plot(x, y2, marker='s', linewidth=2, markersize=8, label='Baseline', color='#A23B72')
            
            # Customize chart
            ax.set_xlabel('Time Period (months)')
            ax.set_ylabel('Performance (%)')
            ax.set_title('Performance Improvement Over Time', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.legend(loc='lower right')
            
            # Set x-axis ticks
            ax.set_xticks(x)
            
            # Save chart
            filename = f"line_chart_{report_id}.png"
            filepath = os.path.join(self.output_dir, filename)
            plt.tight_layout()
            plt.savefig(filepath, dpi=100, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Line chart generated: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Line chart generation failed: {e}")
            return None
    
    def generate_custom_chart(self, chart_data: Dict[str, Any], report_id: str) -> str:
        """
        Generate a custom chart based on provided data.
        
        Args:
            chart_data: Dictionary containing chart type and data
            report_id: Unique identifier for the report
            
        Returns:
            Path to generated chart image
        """
        chart_type = chart_data.get('type', 'bar')
        title = chart_data.get('title', 'Chart')
        data = chart_data.get('data', {})
        
        try:
            if chart_type == 'bar':
                return self._generate_bar_chart(report_id)
            elif chart_type == 'line':
                return self._generate_line_chart(report_id)
            else:
                logger.warning(f"Unsupported chart type: {chart_type}")
                return None
                
        except Exception as e:
            logger.error(f"Custom chart generation failed: {e}")
            return None