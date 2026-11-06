# Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    User ||--o{ RefreshToken : has
    User ||--o{ Event : organizes
    User ||--o{ Booking : creates
    User ||--o{ Review : writes
    User ||--o{ Notification : receives
    User ||--o{ AuditLog : triggers

    Event ||--o{ Booking : contains
    Event ||--o{ Review : receives

    User {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        string role "admin | organizer | attendee"
        boolean is_active
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at "nullable for soft delete"
    }

    RefreshToken {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        timestamp expires_at
        boolean is_revoked
        timestamp created_at
    }

    Event {
        uuid id PK
        uuid organizer_id FK
        string title
        string description
        string location
        timestamp start_time
        timestamp end_time
        integer total_capacity
        integer available_tickets
        string status "draft | published | cancelled | completed"
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    Booking {
        uuid id PK
        uuid event_id FK
        uuid user_id FK
        integer ticket_count
        string status "confirmed | cancelled"
        timestamp created_at
        timestamp updated_at
        timestamp deleted_at
    }

    Review {
        uuid id PK
        uuid event_id FK
        uuid user_id FK
        integer rating "1 to 5"
        text comment
        timestamp created_at
        timestamp updated_at
    }

    Notification {
        uuid id PK
        uuid user_id FK
        string title
        text message
        string type "booking_confirmation | reminder | cancellation | system"
        boolean is_read
        timestamp created_at
    }

    AuditLog {
        uuid id PK
        uuid user_id FK "nullable for system actions"
        string action
        string entity_type
        uuid entity_id
        jsonb old_values
        jsonb new_values
        string ip_address
        timestamp created_at
    }
```

## Key Rules & Constraints
1. **Soft Delete**: `User`, `Event`, and `Booking` have `deleted_at`. Unique index on `User.email` must be conditional (`WHERE deleted_at IS NULL`) so deleted emails can be re-registered if desired.
2. **Concurrency Invariants**:
   - `Event.available_tickets >= 0`. Check constraint: `CHECK (available_tickets >= 0)`.
   - Booking service acquires a row lock: `SELECT * FROM events WHERE id = :event_id FOR UPDATE`.
3. **Audit Trail**: Every state change in `Event` and `Booking` must generate an `AuditLog` entry.
