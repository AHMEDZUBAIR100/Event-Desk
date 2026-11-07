# Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--o{ RefreshToken : "owns"
    User ||--o{ Event : "organizes"
    User ||--o{ Booking : "books"
    User ||--o{ Review : "writes"
    User ||--o{ Notification : "receives"
    User ||--o{ AuditLog : "triggers (actor)"

    Category ||--o{ Event : "classifies"

    Event ||--o{ EventTag : "tagged with"
    Tag ||--o{ EventTag : "attached to"

    Event ||--o{ Booking : "contains"
    Event ||--o{ Review : "receives"

    Review ||--o{ Review : "parent/replies"

    User {
        uuid id PK
        string email UK "unique if deleted_at IS NULL"
        string hashed_password
        string full_name
        string role "ENUM: admin, organizer, attendee"
        boolean is_active "default: true"
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at "nullable (soft-delete)"
    }

    RefreshToken {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        timestamp expires_at
        boolean revoked "default: false"
        timestamp created_at
    }

    Category {
        uuid id PK
        string name
        string slug UK
        string description "nullable"
        timestamp created_at
        timestamp updated_at
    }

    Tag {
        uuid id PK
        string name
        string slug UK
        timestamp created_at
        timestamp updated_at
    }

    EventTag {
        uuid event_id PK, FK
        uuid tag_id PK, FK
    }

    Event {
        uuid id PK
        uuid organizer_id FK
        uuid category_id FK "nullable"
        string title
        text description
        string venue
        timestamp starts_at
        numeric price "NUMERIC(10,2), default: 0.00"
        integer total_tickets "CHECK >= 0"
        integer tickets_available "CHECK >= 0 AND <= total_tickets"
        string status "ENUM: draft, published, cancelled, completed"
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at "nullable (soft-delete)"
    }

    Booking {
        uuid id PK
        uuid user_id FK
        uuid event_id FK
        integer quantity "CHECK > 0"
        numeric total_price "NUMERIC(10,2)"
        string status "ENUM: pending, confirmed, cancelled"
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at "nullable (soft-delete)"
    }

    Review {
        uuid id PK
        uuid user_id FK
        uuid event_id FK
        uuid parent_id FK "nullable (threaded replies)"
        integer rating "CHECK 1 to 5"
        text comment
        timestamp created_at
        timestamp updated_at
    }

    Notification {
        uuid id PK
        uuid user_id FK
        string type "ENUM: booking_confirmation, booking_cancellation, event_reminder, event_update, system"
        string title
        text body
        boolean is_read "default: false"
        jsonb data "default: '{}'"
        timestamp created_at
    }

    AuditLog {
        uuid id PK
        uuid actor_id FK "nullable (system actions)"
        string action "CREATE, UPDATE, DELETE, CANCEL, etc."
        string entity_type "User, Event, Booking, etc."
        uuid entity_id
        jsonb metadata "default: '{}'"
        timestamp created_at
    }
```

---

## Key Rules & Constraints

1. **Soft Delete**:
   - `User`, `Event`, and `Booking` models use `deleted_at`.
   - The unique index on `User.email` is partial (`WHERE deleted_at IS NULL`), allowing reuse of emails if an account is soft-deleted.
2. **Concurrency Invariants**:
   - `Event.tickets_available`: `CHECK (tickets_available >= 0 AND tickets_available <= total_tickets)`.
   - `Event.total_tickets`: `CHECK (total_tickets >= 0)`.
   - `Event.price`: `CHECK (price >= 0)`.
   - Concurrency control: Ticket booking operations acquire an exclusive row-level lock:
     ```sql
     SELECT * FROM events WHERE id = :event_id FOR UPDATE;
     ```
3. **Data Integrity & Ratings**:
   - `Review.rating`: `CHECK (rating >= 1 AND rating <= 5)`.
   - `Booking.quantity`: `CHECK (quantity > 0)`.
   - `Booking.total_price`: `CHECK (total_price >= 0)`.
4. **Audit Trail**:
   - Critical domain events (create/update event, create/cancel booking, role alteration) insert records into `audit_logs` **after** successful transaction commit.
5. **Common Indexes**:
   - `uq_users_active_email` on `users(email) WHERE deleted_at IS NULL`
   - `ix_users_role_active` on `users(role, is_active) WHERE deleted_at IS NULL`
   - `ix_refresh_tokens_user_revoked` on `refresh_tokens(user_id, revoked, expires_at)`
   - `ix_events_active_catalog` on `events(status, starts_at) WHERE deleted_at IS NULL`
   - `ix_events_organizer_id` on `events(organizer_id) WHERE deleted_at IS NULL`
   - `ix_events_category_id` on `events(category_id) WHERE deleted_at IS NULL`
   - `ix_bookings_user_active` on `bookings(user_id, created_at DESC) WHERE deleted_at IS NULL`
   - `ix_bookings_event_status` on `bookings(event_id, status) WHERE deleted_at IS NULL`
   - `ix_reviews_event_parent` on `reviews(event_id, parent_id, created_at DESC)`
   - `ix_notifications_user_unread` on `notifications(user_id, is_read, created_at DESC)`
   - `ix_audit_logs_entity` on `audit_logs(entity_type, entity_id)`
   - `ix_audit_logs_actor_created` on `audit_logs(actor_id, created_at DESC)`
