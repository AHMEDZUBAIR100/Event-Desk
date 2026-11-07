import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking, BookingStatus
from app.models.category import Category
from app.models.event import Event, EventStatus
from app.models.review import Review
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_user_soft_delete_unique_email(db_session: AsyncSession) -> None:
    """Tests that active users cannot share emails, but soft-deleted ones permit re-use."""
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    user1 = User(
        email=email,
        hashed_password="argon2_hashed_password",
        full_name="User One",
        role=UserRole.ATTENDEE,
    )
    db_session.add(user1)
    await db_session.flush()

    # Attempting to insert another active user with identical email must raise IntegrityError
    async with db_session.begin_nested():
        user2_duplicate = User(
            email=email,
            hashed_password="argon2_hashed_password_2",
            full_name="Duplicate User",
            role=UserRole.ATTENDEE,
        )
        db_session.add(user2_duplicate)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Now soft-delete user1
    user1.deleted_at = datetime.now(UTC)
    await db_session.flush()

    # An active user with same email is now valid because user1 is soft deleted
    user3 = User(
        email=email,
        hashed_password="argon2_hashed_password_new",
        full_name="User Three Re-registered",
        role=UserRole.ATTENDEE,
    )
    db_session.add(user3)
    await db_session.flush()
    assert user3.id is not None


@pytest.mark.asyncio
async def test_event_ticket_negative_available_fails(db_session: AsyncSession) -> None:
    """Verifies that tickets_available >= 0 check constraint is enforced."""
    organizer = User(
        email=f"org_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer",
        role=UserRole.ORGANIZER,
    )
    db_session.add(organizer)
    await db_session.flush()

    async with db_session.begin_nested():
        event_negative = Event(
            organizer_id=organizer.id,
            title="Invalid Event Negative",
            description="Desc",
            venue="Venue",
            starts_at=datetime.now(UTC) + timedelta(days=1),
            price=Decimal("10.00"),
            total_tickets=100,
            tickets_available=-1,
        )
        db_session.add(event_negative)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_event_ticket_exceeding_total_fails(db_session: AsyncSession) -> None:
    """Verifies that tickets_available <= total_tickets check constraint is enforced."""
    organizer = User(
        email=f"org2_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer 2",
        role=UserRole.ORGANIZER,
    )
    db_session.add(organizer)
    await db_session.flush()

    async with db_session.begin_nested():
        event_over = Event(
            organizer_id=organizer.id,
            title="Invalid Event Over",
            description="Desc",
            venue="Venue",
            starts_at=datetime.now(UTC) + timedelta(days=1),
            price=Decimal("10.00"),
            total_tickets=50,
            tickets_available=51,
        )
        db_session.add(event_over)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_booking_zero_quantity_fails(db_session: AsyncSession) -> None:
    """Tests booking quantity > 0 constraint."""
    organizer = User(
        email=f"org_b_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer B",
        role=UserRole.ORGANIZER,
    )
    attendee = User(
        email=f"att_b_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Attendee B",
        role=UserRole.ATTENDEE,
    )
    db_session.add_all([organizer, attendee])
    await db_session.flush()

    event = Event(
        organizer_id=organizer.id,
        title="Event",
        description="Desc",
        venue="Venue",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        price=Decimal("20.00"),
        total_tickets=10,
        tickets_available=10,
    )
    db_session.add(event)
    await db_session.flush()

    async with db_session.begin_nested():
        invalid_booking = Booking(
            user_id=attendee.id,
            event_id=event.id,
            quantity=0,
            total_price=Decimal("0.00"),
            status=BookingStatus.PENDING,
        )
        db_session.add(invalid_booking)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_booking_negative_price_fails(db_session: AsyncSession) -> None:
    """Tests booking total_price >= 0 constraint."""
    organizer = User(
        email=f"org_p_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer P",
        role=UserRole.ORGANIZER,
    )
    attendee = User(
        email=f"att_p_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Attendee P",
        role=UserRole.ATTENDEE,
    )
    db_session.add_all([organizer, attendee])
    await db_session.flush()

    event = Event(
        organizer_id=organizer.id,
        title="Event 2",
        description="Desc",
        venue="Venue",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        price=Decimal("20.00"),
        total_tickets=10,
        tickets_available=10,
    )
    db_session.add(event)
    await db_session.flush()

    async with db_session.begin_nested():
        invalid_price_booking = Booking(
            user_id=attendee.id,
            event_id=event.id,
            quantity=1,
            total_price=Decimal("-5.00"),
            status=BookingStatus.PENDING,
        )
        db_session.add(invalid_price_booking)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_review_rating_out_of_range_fails(db_session: AsyncSession) -> None:
    """Tests that review ratings must be between 1 and 5 inclusive."""
    organizer = User(
        email=f"org_r_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer R",
        role=UserRole.ORGANIZER,
    )
    reviewer = User(
        email=f"rev_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Reviewer",
        role=UserRole.ATTENDEE,
    )
    db_session.add_all([organizer, reviewer])
    await db_session.flush()

    event = Event(
        organizer_id=organizer.id,
        title="Event For Review",
        description="Desc",
        venue="Venue",
        starts_at=datetime.now(UTC) + timedelta(days=2),
        price=Decimal("10.00"),
        total_tickets=10,
        tickets_available=10,
    )
    db_session.add(event)
    await db_session.flush()

    # Rating 6 is invalid
    async with db_session.begin_nested():
        invalid_review_high = Review(
            user_id=reviewer.id,
            event_id=event.id,
            rating=6,
            comment="Too high rating",
        )
        db_session.add(invalid_review_high)
        with pytest.raises(IntegrityError):
            await db_session.flush()

    # Rating 0 is invalid
    async with db_session.begin_nested():
        invalid_review_zero = Review(
            user_id=reviewer.id,
            event_id=event.id,
            rating=0,
            comment="Zero rating",
        )
        db_session.add(invalid_review_zero)
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_category_and_event_relation(db_session: AsyncSession) -> None:
    """Tests Category model creation and Event foreign key linkage."""
    category = Category(
        name="Conferences",
        slug="conferences",
        description="Tech and industry conferences",
    )
    organizer = User(
        email=f"org_conf_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="hash",
        full_name="Organizer Conf",
        role=UserRole.ORGANIZER,
    )
    db_session.add_all([category, organizer])
    await db_session.flush()

    event = Event(
        organizer_id=organizer.id,
        category_id=category.id,
        title="PyCon 2026",
        description="Annual Python conference",
        venue="Convention Center",
        starts_at=datetime.now(UTC) + timedelta(days=30),
        price=Decimal("199.00"),
        total_tickets=500,
        tickets_available=500,
        status=EventStatus.PUBLISHED,
    )
    db_session.add(event)
    await db_session.flush()

    assert event.category_id == category.id
    assert event.category.name == "Conferences"
