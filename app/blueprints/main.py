"""Main blueprint with health check endpoint."""
from flask import Blueprint, jsonify
from sqlalchemy import text
from app.database import get_session

main_bp = Blueprint('main', __name__)


# Note: Root route (/) is now handled by auth blueprint (MEJORA 8)


@main_bp.route('/health')
def health():
    """Health check endpoint that validates database connection."""
    try:
        session = get_session()
        # Execute simple query to test connection
        result = session.execute(text("SELECT 1 as health_check"))
        row = result.fetchone()
        
        if row and row[0] == 1:
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'message': 'Database connection successful'
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'error',
                'message': 'Unexpected query result'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'message': 'Failed to connect to database'
        }), 500

