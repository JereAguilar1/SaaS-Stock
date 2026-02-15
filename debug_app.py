from app import create_app
try:
    app = create_app()
    print("App created successfully")
    with app.test_request_context('/dashboard/'):
        from flask import g
        from app.middleware import load_user_and_tenant
        # Mock session
        from flask import session
        session['user_id'] = 1
        session['tenant_id'] = 1
        load_user_and_tenant()
        print(f"User: {g.user}")
        print(f"Tenant: {g.tenant_id}")
except Exception as e:
    import traceback
    print(f"Error creating app: {e}")
    traceback.print_exc()
