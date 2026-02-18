"""Flask application factory."""
from flask import Flask, g, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf.csrf import CSRFProtect
from app.database import init_db
import os


def create_app(config_object='config.Config'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # Initialize CSRF protection
    csrf = CSRFProtect(app)
    
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"CSRF Error: {e.description}")
        if request.is_json or request.headers.get('HX-Request'):
             return jsonify({'status': 'error', 'message': 'La sesión ha expirado. Recarga la página.'}), 400
        flash('Tu sesión ha expirado o el formulario es inválido. Por favor intenta de nuevo.', 'warning')
        return redirect(request.referrer or '/')
    
    # PASO 5: Initialize Sentry for error tracking in production
    if os.getenv('SENTRY_DSN') and (app.config.get('ENV') == 'production' or os.getenv('FLASK_ENV') == 'production'):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        sentry_sdk.init(
            dsn=os.getenv('SENTRY_DSN'),
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% for profiling
            environment=os.getenv('FLASK_ENV', 'production'),
            release=os.getenv('GIT_COMMIT', 'unknown')
        )
    
    # PASO 6: Initialize Flask-Mail for email invitations
    from app.services.email_service import init_mail
    init_mail(app)
    
    # PASO 8: Initialize Redis Cache
    from app.services.cache_service import init_cache
    init_cache(app)
    
    # PASO 9: Setup Prometheus metrics instrumentation
    from app.blueprints.metrics import setup_metrics_instrumentation
    setup_metrics_instrumentation(app)
    
    # Production: Enable ProxyFix for HTTPS behind Nginx reverse proxy
    if app.config.get('ENV') == 'production' or app.config.get('FLASK_ENV') == 'production':
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,      # Trust X-Forwarded-For with 1 proxy
            x_proto=1,    # Trust X-Forwarded-Proto
            x_host=1,     # Trust X-Forwarded-Host
            x_port=1,     # Trust X-Forwarded-Port
            x_prefix=0    # No prefix (not behind a URL prefix)
        )
    
    # Initialize database
    init_db(app)
    
    # Register Jinja filters for formatting (MEJORA 7 + PACK)
    from app.utils.formatters import date_ar, datetime_ar, month_ar, year_ar, num_ar, money_ar, money_ar_2
    app.jinja_env.filters['date_ar'] = date_ar
    app.jinja_env.filters['datetime_ar'] = datetime_ar
    app.jinja_env.filters['month_ar'] = month_ar
    app.jinja_env.filters['year_ar'] = year_ar
    app.jinja_env.filters['num_ar'] = num_ar
    app.jinja_env.filters['money_ar'] = money_ar
    app.jinja_env.filters['money_ar_2'] = money_ar_2
    
    # SaaS Multi-Tenant: Load user and tenant context before each request
    # SaaS Multi-Tenant: Load user and tenant context before each request
    from app.middleware import load_user_and_tenant, check_subscription_status

    @app.before_request
    def before_request_handler():
        """Load user and tenant context for each request."""
        load_user_and_tenant()
        # SUBSCRIPTIONS_V1: Check subscription status
        try:
            check_subscription_status()
        except Exception as e:
            # Log error but don't block request if subscription check fails
            # This prevents infinite loops or hard crashes on DB errors
            app.logger.error(f"Error checking subscription status: {e}")

    # Error Handlers
    from app.exceptions import SaasError
    from flask import jsonify

    @app.errorhandler(SaasError)
    def handle_saas_error(error):
        """Handle custom application exceptions."""
        app.logger.error(f"SaaSError [{error.status_code}]: {error.message}")
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            # Return a styled alert for HTMX requests using the design system
            return f'''
            <div class="alert-custom alert-danger" role="alert" style="margin-bottom: var(--spacing-4);">
                <i class="alert-custom-icon bi bi-exclamation-triangle-fill"></i>
                <div class="alert-custom-content">{error.message}</div>
                <button type="button" class="alert-custom-close" onclick="this.parentElement.remove()">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
            ''', error.status_code
        
        if request.is_json:
            return jsonify(error.to_dict()), error.status_code
        
        # For regular requests: flash message and redirect back
        flash(error.message, 'danger')
        return redirect(request.referrer or '/')

    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json:
            return jsonify({'status': 'error', 'message': 'Not Found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def internal_error(error):
        import traceback
        app.logger.error(f"Unhandled Exception: {error}")
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        
        if request.is_json:
            return jsonify({'status': 'error', 'message': 'Internal Server Error'}), 500
            
        is_htmx = request.headers.get('HX-Request') == 'true'
        if is_htmx:
            return '<div class="alert alert-danger">Error interno del servidor.</div>', 500
            
        return render_template('errors/500.html'), 500

    def force_https():
        if not request.is_secure and not app.debug:
            return redirect(request.url.replace("http://", "https://"), code=301)
    
    # Context processor for invoice alerts (MEJORA 21) - now tenant-aware
    @app.context_processor
    def inject_invoice_alerts():
        """Inject invoice alert counts into all templates (tenant-scoped)."""
        try:
            # Only load alerts if user is authenticated AND tenant is selected
            if g.get('user') and g.get('tenant_id'):
                from app.database import get_session
                from app.services.invoice_alerts_service import get_invoice_alert_counts
                from datetime import date
                
                db_session = get_session()
                # Pass tenant_id to get alerts for current tenant only
                alerts = get_invoice_alert_counts(db_session, date.today(), tenant_id=g.tenant_id)
                return {'invoice_alerts': alerts}
        except Exception as e:
            # If there's any error, log and return empty alerts
            app.logger.warning(f"Error loading invoice alerts: {e}")
        
        return {'invoice_alerts': {'due_tomorrow_count': 0, 'overdue_count': 0, 'total_critical': 0}}
    
    # Context processor for current tenant info
    @app.context_processor
    def inject_tenant_info():
        """Inject current tenant information into templates."""
        try:
            if g.get('tenant_id') and g.get('user'):
                from app.database import get_session
                from app.models import Tenant
                from app.services.storage_service import get_storage_service
                
                db_session = get_session()
                tenant = db_session.query(Tenant).filter_by(id=g.tenant_id).first()
                if tenant:
                    # Generate public URL for logo if exists
                    logo_public_url = None
                    if tenant.logo_url:
                        storage = get_storage_service()
                        logo_public_url = storage.get_public_url(tenant.logo_url)
                    
                    return {
                        'current_tenant': tenant,
                        'logo_public_url': logo_public_url
                    }
        except Exception as e:
            app.logger.error(f"Error injecting tenant info: {e}")
            pass
        
        return {'current_tenant': None, 'logo_public_url': None}

    # Context processor for plan features (SUBSCRIPTIONS_V1)
    @app.context_processor
    def inject_plan_features():
        """Inject plan feature checking functions into templates."""
        from app.decorators.permissions import has_feature, get_feature_value
        
        def check_feature(feature_key):
            """Check if current tenant has a feature."""
            if not g.get('tenant_id'):
                return False
            try:
                return has_feature(g.tenant_id, feature_key)
            except Exception:
                return False
        
        def get_feature(feature_key, default=None):
            """Get feature value for current tenant."""
            if not g.get('tenant_id'):
                return default
            try:
                return get_feature_value(g.tenant_id, feature_key, default)
            except Exception:
                return default
        
        return {
            'has_feature': check_feature,
            'get_feature': get_feature
        }

    
    

    


    
    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.users import users_bp  # PASO 6
    from app.blueprints.catalog import catalog_bp
    from app.blueprints.sales import sales_bp
    from app.blueprints.customers import customers_bp
    from app.blueprints.suppliers import suppliers_bp
    from app.blueprints.invoices import invoices_bp
    from app.blueprints.balance import balance_bp
    from app.blueprints.ledger import ledger_bp
    from app.blueprints.settings import settings_bp
    from app.blueprints.quotes import quotes_bp  # MEJORA 13
    from app.blueprints.missing_products import missing_products_bp  # MEJORA 18
    from app.blueprints.debug import debug_bp
    from app.blueprints.metrics import metrics_bp  # PASO 9
    from app.blueprints.auth_google import auth_google_bp  # GOOGLE_AUTH
    from app.blueprints.admin import admin_bp  # ADMIN_PANEL_V1
    from app.blueprints.webhooks import webhooks_bp  # SUBSCRIPTIONS_V1

    
    app.register_blueprint(auth_bp)
    app.register_blueprint(auth_google_bp)  # GOOGLE_AUTH
    app.register_blueprint(admin_bp)  # ADMIN_PANEL_V1
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)  # PASO 6
    app.register_blueprint(catalog_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(balance_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(quotes_bp)  # MEJORA 13
    app.register_blueprint(missing_products_bp)  # MEJORA 18
    app.register_blueprint(debug_bp)
    app.register_blueprint(metrics_bp)  # PASO 9
    
    # Webhooks must be exempt from CSRF
    csrf.exempt(webhooks_bp)
    app.register_blueprint(webhooks_bp)  # SUBSCRIPTIONS_V1
    
    # Register CLI commands (ADMIN_PANEL_V1)
    from app.cli_commands import init_cli_commands
    init_cli_commands(app)
    
    app.logger.info(f"MAIL_SERVER={app.config.get('MAIL_SERVER')}")
    app.logger.info(f"MAIL_USERNAME={app.config.get('MAIL_USERNAME')}")
    app.logger.info(f"MAIL_DEFAULT_SENDER={app.config.get('MAIL_DEFAULT_SENDER')}")

    
    return app

