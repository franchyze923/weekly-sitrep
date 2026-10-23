"""SQLAlchemy models. SQLite by default; DATABASE_URL can point at Postgres later."""
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint, create_engine, select)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from . import config


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    reports: Mapped[list] = relationship("Report", back_populates="project")


class User(Base):
    """Built-in accounts for the login form. OIDC users are not stored here."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(256), unique=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("project_id", "week_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    week_start: Mapped[date] = mapped_column(Date)  # always a Monday
    raw_text: Mapped[str] = mapped_column(Text, default="")
    summary_text: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(256), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="reports")


engine = create_engine(config.DATABASE_URL, connect_args={"check_same_thread": False}
                       if config.DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def init_db():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if s.scalar(select(Project).limit(1)) is None:
            for i, name in enumerate(config.SEED_PROJECTS):
                s.add(Project(slug=slugify(name), name=name, sort_order=i))
            s.commit()


def get_session():
    with SessionLocal() as s:
        yield s


def active_projects(s: Session):
    return list(s.scalars(select(Project).where(Project.active == True).order_by(Project.sort_order, Project.name)))


def get_report(s: Session, project: Project, week_start: date):
    return s.scalar(select(Report).where(Report.project_id == project.id, Report.week_start == week_start))


def get_or_create_report(s: Session, project: Project, week_start: date) -> Report:
    report = get_report(s, project, week_start)
    if report is None:
        report = Report(project_id=project.id, week_start=week_start)
        s.add(report)
        s.flush()
    return report
