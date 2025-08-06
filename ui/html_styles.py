"""HTML styles and templates for the Streamlit app"""

# Enhanced table styles
ENHANCED_TABLE_STYLES = """
<style>
.enhanced-table {
    font-family: 'Arial', sans-serif;
}
.issue-row {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
    background-color: #f9f9f9;
}
.issue-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-weight: bold;
}
.issue-type {
    background-color: #ff6b6b;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9em;
}
.page-info {
    background-color: #4ecdc4;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.9em;
    cursor: pointer;
}
.original-text {
    background-color: #ffe6e6;
    border-left: 4px solid #ff6b6b;
    padding: 10px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    line-height: 1.4;
}
.suggestion-text {
    background-color: #e6ffe6;
    border-left: 4px solid #4caf50;
    padding: 10px;
    margin: 8px 0;
    border-radius: 0 4px 4px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    line-height: 1.4;
}
.location-info {
    color: #666;
    font-style: italic;
    margin-bottom: 8px;
}

.issue-navigation {
    background-color: #e3f2fd;
    border: 1px solid #2196f3;
    border-radius: 6px;
    padding: 10px;
    margin: 10px 0;
    text-align: center;
}
.nav-button {
    background-color: #2196f3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 5px 10px;
    margin: 0 5px;
    cursor: pointer;
    font-size: 0.9em;
}
.nav-button:hover {
    background-color: #1976d2;
}

.difference-highlight {
    line-height: 1.6;
}
.navigation-section {
    background-color: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    padding: 8px 12px;
    margin: 8px 0;
    font-size: 0.9em;
}
.nav-link {
    color: #007bff;
    text-decoration: none;
    font-weight: 500;
}
.nav-link:hover {
    color: #0056b3;
    text-decoration: underline;
}
.search-instruction {
    color: #6c757d;
    font-style: italic;
}
</style>
"""

# JavaScript for navigation
NAVIGATION_JAVASCRIPT = """
<script>
function jumpToPage(pageNumber) {
    // Find first issue on this page
    const issues = document.querySelectorAll('.issue-row');
    for (let issue of issues) {
        const pageSpan = issue.querySelector('.page-info');
        if (pageSpan && pageSpan.textContent.includes('Page ' + pageNumber)) {
            issue.scrollIntoView({ behavior: 'smooth', block: 'center' });
            issue.style.backgroundColor = '#fff3cd';
            setTimeout(function() {
                issue.style.backgroundColor = '';
            }, 3000);
            break;
        }
    }
}
</script>
"""

# Combined styles and scripts
FULL_STYLES_AND_SCRIPTS = ENHANCED_TABLE_STYLES + NAVIGATION_JAVASCRIPT