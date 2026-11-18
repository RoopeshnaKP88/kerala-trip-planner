"""PostgreSQL: permanent itineraries."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from .config import settings
from .models import TripState

engine = create_engine(settings.database_url, pool_pre_ping=True)


class Base(DeclarativeBase):
    pass


class Itinerary(Base):
    __tablename__ = "itineraries"
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    destination: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(engine)


def save_trip(trip: TripState) -> None:
    with Session(engine) as s:
        s.merge(
            Itinerary(
                session_id=trip.session_id,
                destination=trip.destination,
                data=trip.model_dump(),
                updated_at=datetime.utcnow(),
            )
        )
        s.commit()

def list_trips(limit: int = 10) -> list[dict]:
       with Session(engine) as s:
           rows = s.scalars(select(Itinerary).order_by(Itinerary.updated_at.desc()).limit(limit)).all()
           return [{"session_id": r.session_id, "destination": r.destination,
                    "updated_at": r.updated_at.isoformat()} for r in rows]


def get_trip(session_id: str) -> TripState | None:
       with Session(engine) as s:
           row = s.get(Itinerary, session_id)
           return TripState.model_validate(row.data) if row else None