from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.models.base import Base

class Call(Base):
    __tablename__ = "calls"

    call_id = Column(String, primary_key=True, index=True)
    phone_number = Column(String, nullable=True)
    status = Column(String, default="started")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    transcript = Column(Text, nullable=True)

    events = relationship("CallEvent", back_populates="call", cascade="all, delete-orphan")


class CallEvent(Base):
    __tablename__ = "call_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    call_id = Column(String, ForeignKey("calls.call_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    latency_ms = Column(Integer, default=0)
    error = Column(Text, nullable=True)

    call = relationship("Call", back_populates="events")

    __table_args__ = (
        UniqueConstraint("call_id", "event_type", name="uq_call_event_type"),
    )
