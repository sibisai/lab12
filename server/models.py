from datetime import datetime, timezone
from sqlalchemy import (
    Column, Index, Integer, String, DateTime, Boolean,
    JSON, ForeignKey, Numeric, Table, text, func
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
Base = declarative_base()

# association for many-to-many user ↔ role
user_roles = Table(
    "user_roles", Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id                       = Column(Integer, primary_key=True, index=True)
    username                 = Column(String, unique=True, index=True, nullable=False)
    hashed_password          = Column(String, nullable=False)

    # new fields
    full_name                = Column(String)
    subscription_plan        = Column(String, nullable=False, default="free")
    subscription_started_at  = Column(DateTime(timezone=True))
    subscription_expires_at  = Column(DateTime(timezone=True))
    active_subscriber        = Column(Boolean, default=False)
    summarize_call_count     = Column(Integer, default=0)
    last_summarize_at        = Column(DateTime(timezone=True))
    usage_period_start       = Column(DateTime(timezone=True))

    # audit
    created_at               = Column(DateTime(timezone=True),
                                      default=lambda: datetime.now(timezone.utc),
                                      nullable=False)
    updated_at               = Column(DateTime(timezone=True),
                                      default=lambda: datetime.now(timezone.utc),
                                      onupdate=lambda: datetime.now(timezone.utc),
                                      nullable=False)
    last_login               = Column(DateTime(timezone=True),
                                      default=lambda: datetime.now(timezone.utc),
                                      onupdate=lambda: datetime.now(timezone.utc),
                                      nullable=True)
    email_verified = Column(Boolean, default=False)

    # relationships
    email_verifications = relationship(
      "EmailVerification",
      back_populates="user",
      cascade="all, delete-orphan"
    )
    feedback_entries         = relationship("UserFeedback", back_populates="user",
                                            cascade="all, delete-orphan")
    subscription_history     = relationship("UserSubscriptionHistory",
                                            back_populates="user",
                                            cascade="all, delete-orphan")
    summarize_calls          = relationship("SummarizeCall",
                                            back_populates="user",
                                            cascade="all, delete-orphan")
    tokens                   = relationship("UserToken",
                                            back_populates="user",
                                            cascade="all, delete-orphan")
    roles                    = relationship("Role",
                                            secondary=user_roles,
                                            back_populates="users")

class UserFeedback(Base):
    __tablename__ = "user_feedback"
    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    feedback     = Column(JSON, nullable=False)
    created_at   = Column(DateTime(timezone=True),
                          default=lambda: datetime.now(timezone.utc),
                          nullable=False)
    user         = relationship("User", back_populates="feedback_entries")

class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id       = Column(Integer, primary_key=True)
    name     = Column(String, unique=True, nullable=False)
    quota    = Column(Integer, nullable=False)
    price    = Column(Numeric(10,2), nullable=False)
    history  = relationship("UserSubscriptionHistory", back_populates="plan")

class UserSubscriptionHistory(Base):
    __tablename__ = "user_subscription_history"
    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_id     = Column(Integer, ForeignKey("subscription_plans.id"), nullable=False)
    started_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at    = Column(DateTime(timezone=True))
    user        = relationship("User", back_populates="subscription_history")
    plan        = relationship("SubscriptionPlan", back_populates="history")

class SummarizeCall(Base):
    __tablename__ = "summarize_calls"
    id               = Column(Integer, primary_key=True)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    called_at        = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    transcript_length = Column(Integer, nullable=False)
    tokens_used      = Column(Integer, nullable=False)
    user             = relationship("User", back_populates="summarize_calls")

class UserToken(Base):
    __tablename__ = "user_tokens"
    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    provider       = Column(String, nullable=False)
    refresh_token  = Column(String, nullable=False)
    expires_at     = Column(DateTime(timezone=True), nullable=False)
    user           = relationship("User", back_populates="tokens")

class Role(Base):
    __tablename__ = "roles"
    id    = Column(Integer, primary_key=True)
    name  = Column(String, unique=True, nullable=False)
    users = relationship("User", secondary=user_roles, back_populates="roles")

class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id    = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False) 
    email      = Column(String, nullable=False, index=True)
    code       = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed   = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user       = relationship("User", back_populates="email_verifications")

Index("ix_email_unexpired",
      EmailVerification.email,
      EmailVerification.consumed,
      EmailVerification.expires_at)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    email      = Column(String, nullable=False, index=True)
    code       = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed   = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="password_resets")

# back‑populate in User:
User.password_resets = relationship(
    "PasswordReset",
    back_populates="user",
    cascade="all, delete-orphan"
)

Index(
    "ix_password_reset_unexpired",
    PasswordReset.email,
    PasswordReset.consumed,
    PasswordReset.expires_at
)



