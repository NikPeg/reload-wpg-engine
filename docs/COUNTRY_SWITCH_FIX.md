# Country Switch Fix

## Problem

When a player attempted to re-register and switch to a new country, the system would throw an `IntegrityError`:

```
IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: players.telegram_id
```

This occurred because the `complete_registration` function in `registration.py` was trying to create a new player record with the same `telegram_id`, which violates the unique constraint on the `telegram_id` column.

## Root Cause

The re-registration flow was:
1. User calls `/register` while already registered
2. System asks for confirmation
3. User confirms with "ПОДТВЕРЖДАЮ"
4. System detaches player from old country (sets `country_id = None`)
5. User goes through registration again
6. System calls `complete_registration`
7. **BUG**: `complete_registration` always tried to create a new player record, even if one already existed

## Solution

Modified the `complete_registration` function in `wpg_engine/adapters/telegram/handlers/registration.py` to:

1. Check if a player with the given `telegram_id` already exists
2. If exists: **update** the existing player record with the new country and user info
3. If doesn't exist: create a new player record

This is the same pattern already used in the `process_example_selection` function, which handles country selection from examples.

## Code Changes

**File**: `wpg_engine/adapters/telegram/handlers/registration.py`

**Before** (lines 527-535):
```python
# Create player with PLAYER role (registration is for countries, not admins)
await game_engine.create_player(
    game_id=data["game_id"],
    telegram_id=data["user_id"],
    username=message.from_user.username,
    display_name=message.from_user.full_name,
    country_id=country.id,
    role=PlayerRole.PLAYER,
)
```

**After** (lines 527-546):
```python
# Check if player already exists (re-registration case)
result = await game_engine.db.execute(
    select(Player).where(Player.telegram_id == data["user_id"])
)
existing_player = result.scalar_one_or_none()

if existing_player:
    # Update existing player with new country
    existing_player.country_id = country.id
    existing_player.username = message.from_user.username
    existing_player.display_name = message.from_user.full_name
    await game_engine.db.commit()
else:
    # Create new player with PLAYER role (registration is for countries, not admins)
    await game_engine.create_player(
        game_id=data["game_id"],
        telegram_id=data["user_id"],
        username=message.from_user.username,
        display_name=message.from_user.full_name,
        country_id=country.id,
        role=PlayerRole.PLAYER,
    )
```

## Benefits

1. **No IntegrityError**: Players can now switch countries without errors
2. **Data consistency**: Only one player record per `telegram_id` is maintained
3. **User info updates**: Username and display name are updated on re-registration
4. **Old countries preserved**: Previous countries remain in the database and can be deleted by admin using `/delete_country`

## Test Coverage

Created comprehensive test suite in `tests/test_country_switch.py`:

1. `test_player_can_switch_countries` - Basic country switching test
2. `test_multiple_country_switches` - Tests switching through multiple countries
3. `test_integrity_error_does_not_occur_on_reregistration` - Verifies the specific bug is fixed
4. `test_old_country_remains_in_database_after_switch` - Confirms old countries persist
5. `test_player_info_updates_on_reregistration` - Verifies username/display name updates

All tests pass ✅

## Related Files

- Fixed: `wpg_engine/adapters/telegram/handlers/registration.py`
- Tests: `tests/test_country_switch.py`
- Model: `wpg_engine/models/player.py` (has unique constraint on `telegram_id`)

## Migration Status

No database migration required - this is a code-only fix that properly handles the existing unique constraint on `players.telegram_id`.

