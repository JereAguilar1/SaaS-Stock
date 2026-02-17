from sqlalchemy import create_engine, inspect
import pprint

try:
    engine = create_engine('postgresql://stock:stock@db/stock')
    inspector = inspect(engine)
    constraints = inspector.get_check_constraints('sale')
    print("Constraints found:")
    pprint.pprint(constraints)
except Exception as e:
    print(f"Error: {e}")
