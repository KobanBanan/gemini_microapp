"""UI module for displaying analysis results and database management"""

from .display_results import display_analysis_results, display_enhanced_results_table
from .html_styles import FULL_STYLES_AND_SCRIPTS, ENHANCED_TABLE_STYLES, NAVIGATION_JAVASCRIPT
from .database_ui import (
    render_analysis_history_sidebar,
    render_full_analysis_history,
    render_database_management,
    save_current_analysis_to_db
)

__all__ = [
    'display_analysis_results',
    'display_enhanced_results_table', 
    'FULL_STYLES_AND_SCRIPTS',
    'ENHANCED_TABLE_STYLES',
    'NAVIGATION_JAVASCRIPT',
    'render_analysis_history_sidebar',
    'render_full_analysis_history', 
    'render_database_management',
    'save_current_analysis_to_db'
]