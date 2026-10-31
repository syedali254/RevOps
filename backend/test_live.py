import os
import sys
import json

sys.path.insert(0, r'C:\sales_project\backend')
os.environ['DATABASE_URL'] = 'sqlite:///test.db'
os.environ['DRY_RUN'] = 'true'
os.environ['FRONTEND_ORIGIN'] = 'http://127.0.0.1:5173'
os.environ['TAVILY_API_KEY'] = ''
os.environ['EXA_API_KEY'] = ''
os.environ['GNEWS_API_KEY'] = ''
os.environ['BRAVE_API_KEY'] = ''
os.environ['OPENCORPORATES_API_KEY'] = ''

from app.db import init_db
from app.models import Campaign, Company, WorkflowRun, utcnow, StageEvent
from app.graph import run_workflow
import json

init_db()
from app.db import SessionLocal
db = SessionLocal()
c = Campaign(name='test', settings_json=json.dumps({
    'countries': ['United States'],
    'sectors': ['software'],
    'employee_min': 20,
    'employee_max': 200,
    'target_titles': [],
    'exclusions': [],
    'require_domain': True
}))
db.add(c); db.flush()
co = Company(campaign_id=c.id, canonical_name='Test Co', normalized_name='test co', website_domain='testco.com', country='United States', sector='software', employee_min=25, employee_max=60, record_kind='test_seed')
db.add(co); db.flush()
r = WorkflowRun(campaign_id=c.id, company_id=co.id, run_type='qualification', status='running', started_at=utcnow())
db.add(r); db.commit()
rid = r.id
db.close()

final = run_workflow(rid)
print('FINAL outcome:', final.get('outcome'))
print('FINAL error:', final.get('error'))

db = SessionLocal()
for e in db.query(StageEvent).filter(StageEvent.run_id==rid).order_by(StageEvent.id):
    print(f'  {e.stage}: {e.status} - {e.error_message}')