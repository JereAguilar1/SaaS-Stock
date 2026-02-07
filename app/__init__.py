"""Flask application factory."""
from flask import Flask, g
from app.database import db, init_db
import os


def create_app(config_object='config.Config'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_object)
    
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
    from app.middleware import load_user_and_tenant
    from flask import request, redirect

    @app.before_request
    def before_request_handler():
        """Load user and tenant context for each request."""
        load_user_and_tenant()

    @app.errorhandler(500)
    def internal_error(error):
        import traceback
        app.logger.error(f"Server Error: {error}")
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        app.logger.error(f"Unhandled Exception: {e}")
        app.logger.error(f"Traceback: {traceback.format_exc()}")
        return "Internal Server Error", 500

    def force_https():
        if not request.is_secure and not app.debug:
            return redirect(request.url.replace("http://", "https://"), code=301)
    
    # Context processor for invoice alerts (MEJORA 21) - now tenant-aware
    @app.context_processor
    def inject_invoice_alerts():
        """Inject invoice alert counts into all templates (tenant-scoped)."""
        try:
            # Only load alerts if user is authenticated AND tenant is selected
            if g.user and g.tenant_id:
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
        if g.get('tenant_id') and g.get('user'):
            try:
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
            except Exception:
                pass
        
        return {'current_tenant': None, 'logo_public_url': None}

    
    

    


    
    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.main import main_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.users import users_bp  # PASO 6
    from app.blueprints.catalog import catalog_bp
    from app.blueprints.sales import sales_bp
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

    
    app.register_blueprint(auth_bp)
    app.register_blueprint(auth_google_bp)  # GOOGLE_AUTH
    app.register_blueprint(admin_bp)  # ADMIN_PANEL_V1
    app.register_blueprint(main_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(users_bp)  # PASO 6
    app.register_blueprint(catalog_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(invoices_bp)
    app.register_blueprint(balance_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(quotes_bp)  # MEJORA 13
    app.register_blueprint(missing_products_bp)  # MEJORA 18
    app.register_blueprint(debug_bp)
    app.register_blueprint(metrics_bp)  # PASO 9
    
    # Register CLI commands (ADMIN_PANEL_V1)
    from app.cli_commands import init_cli_commands
    init_cli_commands(app)
    
    app.logger.info(f"MAIL_SERVER={app.config.get('MAIL_SERVER')}")
    app.logger.info(f"MAIL_USERNAME={app.config.get('MAIL_USERNAME')}")
    app.logger.info(f"MAIL_DEFAULT_SENDER={app.config.get('MAIL_DEFAULT_SENDER')}")

    
    return app

