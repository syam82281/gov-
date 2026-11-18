import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .job_monitor import POLL_INTERVAL_SECONDS, scan_sources_once
from .models import JobLink, Opportunity
from .schemas import JobLinkCreate, JobLinkOut, OpportunityCreate, OpportunityOut

logger = logging.getLogger(__name__)

SEED = [
    dict(title="RRB NTPC Recruitment", organization="Railway Recruitment Boards", category="Railway", state="All India", qualification="12th / Degree (post-wise)", age_limit="As stated in official notification", last_date="Check official notification", apply_url="https://www.rrbcdg.gov.in/", notification_url="https://www.rrbcdg.gov.in/", description="Official RRB portal. Check the relevant regional RRB notification before applying.", featured=True, verified=True),
    dict(title="RRB Group D Recruitment", organization="Railway Recruitment Boards", category="Railway", state="All India", qualification="As stated in notification", age_limit="As stated in notification", last_date="Check official notification", apply_url="https://www.rrbcdg.gov.in/", description="Railway Level 1 recruitment information. Confirm dates and eligibility on the official RRB portal.", featured=True, verified=True),
    dict(title="SSC CGL", organization="Staff Selection Commission", category="Central Government", state="All India", qualification="Bachelor's degree (post-wise conditions apply)", age_limit="Post-wise; see notification", last_date="Check official notification", apply_url="https://ssc.gov.in/", description="Combined Graduate Level examination. Read the current SSC notification.", featured=True, verified=True),
    dict(title="SSC CHSL", organization="Staff Selection Commission", category="Central Government", state="All India", qualification="12th pass (post-wise conditions apply)", age_limit="See official notification", last_date="Check official notification", apply_url="https://ssc.gov.in/", description="Combined Higher Secondary Level examination.", featured=True, verified=True),
    dict(title="UPSC Civil Services", organization="Union Public Service Commission", category="Central Government", state="All India", qualification="Bachelor's degree", age_limit="Category-wise; see notification", last_date="Check official notification", apply_url="https://upsc.gov.in/", description="Civil Services Examination and official UPSC announcements.", featured=True, verified=True),
    dict(title="IBPS Recruitment", organization="Institute of Banking Personnel Selection", category="Banking", state="All India", qualification="Post-wise; see notification", age_limit="Post-wise; see notification", last_date="Check official notification", apply_url="https://www.ibps.in/", description="Banking recruitment notifications, calendars and application links.", featured=True, verified=True),
    dict(title="SBI Careers", organization="State Bank of India", category="Banking", state="All India", qualification="Post-wise; see notification", age_limit="Post-wise; see notification", last_date="Check official notification", apply_url="https://sbi.co.in/web/careers", description="SBI recruitment and career opportunities.", featured=True, verified=True),
    dict(title="APPSC Recruitment", organization="Andhra Pradesh Public Service Commission", category="State Government", state="Andhra Pradesh", qualification="Post-wise; see notification", age_limit="Post-wise; see notification", last_date="Check official notification", apply_url="https://psc.ap.gov.in/", description="Andhra Pradesh Public Service Commission notifications.", featured=True, verified=True),
    dict(title="AP Police Recruitment", organization="Andhra Pradesh State Level Police Recruitment Board", category="Police", state="Andhra Pradesh", qualification="Post-wise; see notification", age_limit="Post-wise; see notification", last_date="Check official notification", apply_url="https://slprb.ap.gov.in/", description="Andhra Pradesh police recruitment notifications and updates.", featured=True, verified=True),
    dict(title="UPSC / Government Exam Updates", organization="UPSC", category="Exams", state="All India", qualification="Varies by exam", age_limit="Varies by exam", last_date="Check official website", apply_url="https://upsc.gov.in/", description="Official examination notices, schedules and results.", verified=True),
    dict(title="National Career Service", organization="Ministry of Labour & Employment", category="Employment Services", state="All India", qualification="Varies by vacancy", age_limit="Varies by vacancy", last_date="See vacancy details", apply_url="https://www.ncs.gov.in/", description="Government employment and career services.", verified=True),
    dict(title="DigiLocker", organization="Ministry of Electronics & IT", category="Citizen Services", state="All India", qualification="Not applicable", age_limit="Not applicable", last_date="Not applicable", apply_url="https://www.digilocker.gov.in/", description="Access eligible digital documents and certificates.", verified=True),
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        if db.scalar(select(Opportunity.id).limit(1)) is None:
            for item in SEED:
                db.add(Opportunity(**item))
            db.commit()
    monitor_enabled = os.getenv("JOB_MONITOR_ENABLED", "true").lower() == "true"
    monitor_task = None
    if monitor_enabled:
        async def monitor_forever():
            while True:
                try:
                    await asyncio.to_thread(scan_sources_once)
                except Exception:
                    logger.exception("Job link monitoring cycle failed")
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

        monitor_task = asyncio.create_task(monitor_forever())
    try:
        yield
    finally:
        if monitor_task:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

app = FastAPI(title="Bharat One Government Portal API", version="1.0.0", lifespan=lifespan)
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"message": "Bharat One API is running", "docs": "/docs"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.get("/api/categories")
def categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Opportunity.category).where(Opportunity.active == True).distinct().order_by(Opportunity.category)).all()
    return rows

@app.get("/api/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    search: str = Query(default="", max_length=100),
    category: str = "",
    state: str = "",
    featured: bool | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Opportunity).where(Opportunity.active == True)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(Opportunity.title.ilike(term), Opportunity.organization.ilike(term), Opportunity.description.ilike(term)))
    if category and category != "All":
        stmt = stmt.where(Opportunity.category == category)
    if state and state != "All":
        stmt = stmt.where(or_(Opportunity.state == state, Opportunity.state == "All India"))
    if featured is not None:
        stmt = stmt.where(Opportunity.featured == featured)
    return db.scalars(stmt.order_by(Opportunity.featured.desc(), Opportunity.organization, Opportunity.title)).all()

@app.get("/api/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    item = db.get(Opportunity, opportunity_id)
    if not item or not item.active:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return item

def require_admin(x_admin_key: str | None = Header(default=None)):
    expected = os.getenv("ADMIN_API_KEY", "change-this-admin-key")
    if not x_admin_key or x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Valid X-Admin-Key header required")

@app.get("/api/job-links", response_model=list[JobLinkOut])
def list_job_links(db: Session = Depends(get_db)):
    stmt = select(JobLink).where(JobLink.active == True).order_by(JobLink.start_date, JobLink.title)
    return db.scalars(stmt).all()

@app.post("/api/job-links", response_model=JobLinkOut, status_code=201, dependencies=[Depends(require_admin)])
def create_job_link(payload: JobLinkCreate, db: Session = Depends(get_db)):
    values = payload.model_dump(mode="python")
    values["apply_url"] = str(payload.apply_url)
    item = JobLink(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.post("/api/opportunities", response_model=OpportunityOut, status_code=201, dependencies=[Depends(require_admin)])
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    item = Opportunity(**payload.model_dump(mode="json"))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.patch("/api/opportunities/{opportunity_id}", response_model=OpportunityOut, dependencies=[Depends(require_admin)])
def update_opportunity(opportunity_id: int, payload: OpportunityCreate, db: Session = Depends(get_db)):
    item = db.get(Opportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    for key, value in payload.model_dump(mode="json").items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item

@app.delete("/api/opportunities/{opportunity_id}", status_code=204, dependencies=[Depends(require_admin)])
def deactivate_opportunity(opportunity_id: int, db: Session = Depends(get_db)):
    item = db.get(Opportunity, opportunity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    item.active = False
    db.commit()
