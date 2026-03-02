# Parental Control 30-Minute Cooldown Feature

## Overview
Parents must wait 30 minutes between modifications to parental control settings for a particular child. This prevents frequent changes and ensures stability in child account management.

## How It Works

### Cooldown Timer
- When a parent updates parental control settings for a child, the system records the modification timestamp
- Any subsequent modification attempts within 30 minutes will be blocked
- The cooldown applies per child (different children can be modified independently)

### API Behavior

#### Successful Update
When updating parental controls and the cooldown period has passed:
```json
{
  "success": true,
  "message": "Settings updated successfully",
  "synced_with_transatel": true
}
```

#### Blocked Update (Cooldown Active)
When attempting to update within 30 minutes:
```json
{
  "detail": {
    "success": false,
    "message": "Please wait 15 minutes and 30 seconds before making another change",
    "error": "COOLDOWN_ACTIVE",
    "time_remaining_seconds": 930,
    "last_modified_at": "2026-02-27T10:30:00"
  }
}
```
HTTP Status: `429 Too Many Requests`

## API Endpoint

### Update Parental Controls
```
PUT /api/parental-controls/child/{child_sim_card_id}
```

**Query Parameters:**
- `customer_id` (required): Parent's customer ID
- `sync_with_transatel` (optional): Whether to sync with Transatel API (default: true)

**Request Body:**
```json
{
  "params": [
    {
      "name": "voice_calls_enabled",
      "value": "true"
    },
    {
      "name": "mobile_data_enabled",
      "value": "false"
    }
  ]
}
```

**Response Codes:**
- `200 OK`: Settings updated successfully
- `429 Too Many Requests`: Cooldown period active, must wait
- `500 Internal Server Error`: Update failed

## Database Schema

### New Column
Added to `parental_controls` table:
```sql
last_modified_at DATETIME NULL
```

This column tracks when the parental control settings were last modified for cooldown enforcement.

## Implementation Details

### Cooldown Check Logic
1. Query existing parental control record for the child
2. Check if `last_modified_at` exists
3. Calculate time difference between now and last modification
4. If less than 30 minutes, reject with error message showing time remaining
5. If 30+ minutes or first modification, allow update and set `last_modified_at` to current time

### Time Remaining Calculation
The error response includes:
- Human-readable format: "X minutes and Y seconds"
- Machine-readable format: `time_remaining_seconds` (total seconds)
- Last modification timestamp: `last_modified_at` (ISO 8601 format)

## Frontend Integration

### Recommended UI Flow
1. Display last modification time to parent
2. Show countdown timer if cooldown is active
3. Disable "Save" button during cooldown period
4. Show clear message: "You can modify settings again in X minutes"

### Example Frontend Logic
```javascript
// Check if cooldown is active before allowing form submission
async function updateParentalControls(childId, settings) {
  try {
    const response = await fetch(`/api/parental-controls/child/${childId}?customer_id=${customerId}`, {
      method: 'PUT',
      body: JSON.stringify(settings)
    });
    
    if (response.status === 429) {
      const error = await response.json();
      alert(error.detail.message);
      // Start countdown timer with error.detail.time_remaining_seconds
      return;
    }
    
    // Success - show confirmation
    alert('Settings updated successfully');
  } catch (error) {
    console.error('Update failed:', error);
  }
}
```

## Benefits
- Prevents impulsive or excessive changes to child settings
- Reduces API load and Transatel sync operations
- Encourages thoughtful parental control management
- Provides clear feedback on when next change is allowed

## Notes
- Cooldown is per child - parents can modify different children's settings independently
- First-time setup has no cooldown restriction
- Cooldown timer uses UTC timezone for consistency
- Manual sync endpoint (`POST /api/parental-controls/sync`) is not affected by cooldown
