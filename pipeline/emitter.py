import os
import sys
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ValidationError

# Define Pydantic Schema for Event Validation
class StoreEventSchema(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique event UUID")
    store_id: str = Field(..., min_length=1, description="Store ID (e.g. ST1008)")
    camera_id: str = Field(..., min_length=1, description="Camera ID (e.g. CAM1, CAM3)")
    visitor_id: Optional[uuid.UUID] = Field(None, description="Resolved Global Visitor UUID")
    event_type: str = Field(..., description="ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, etc.")
    timestamp: datetime = Field(..., description="Event timestamp (ISO-8601)")
    zone_id: Optional[str] = Field(None, description="Zone name if applicable")
    dwell_ms: Optional[int] = Field(None, description="Dwell duration in milliseconds")
    is_staff: bool = Field(default=False, description="Flag indicating if the track belongs to store staff")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata coordinates / dimensions")

    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            # Parse string ISO timestamp to datetime
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        return v


class EventEmitter:
    def __init__(self, output_path: str = "events/events.jsonl"):
        self.output_path = output_path
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

    def emit(self, raw_event_data: Dict[str, Any]) -> Optional[uuid.UUID]:
        """
        Validates, serializes, and appends the event to the JSONL log file.
        Returns the generated event_id if successful, else None.
        """
        try:
            # 1. Staff Filter: Auto-tag as staff if camera is CAM4 (backroom)
            if raw_event_data.get("camera_id") == "CAM4":
                raw_event_data["is_staff"] = True
                
            # 2. Schema Validation using Pydantic
            validated_event = StoreEventSchema(**raw_event_data)
            
            # 3. Serialization
            # Convert datetime to ISO-8601 string and UUIDs to string representation
            event_dict = validated_event.model_dump()
            event_dict["event_id"] = str(event_dict["event_id"])
            if event_dict["visitor_id"]:
                event_dict["visitor_id"] = str(event_dict["visitor_id"])
            event_dict["timestamp"] = event_dict["timestamp"].isoformat().replace("+00:00", "Z")
            
            # 4. Append to JSONL File
            with open(self.output_path, mode='a', encoding='utf-8') as f:
                f.write(json.dumps(event_dict) + "\n")
                
            print(f"Emitted event [{validated_event.event_type}] successfully: {event_dict['event_id']}")
            return validated_event.event_id

        except ValidationError as ve:
            print(f"Schema Validation Error: Failed to emit event. Errors: {ve.errors()}", file=sys.stderr)
            return None
        except IOError as ioe:
            print(f"Disk Write Error: Failed to write event to {self.output_path}. Error: {ioe}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Unexpected Ingestion Error: {str(e)}", file=sys.stderr)
            return None


# --- Demonstration & Self Tests ---

if __name__ == "__main__":
    emitter = EventEmitter("events/events.jsonl")
    
    print("Testing Event Emission System...")
    print("-" * 60)
    
    # 1. Valid Event Example
    valid_event = {
        "store_id": "ST1008",
        "camera_id": "CAM1",
        "visitor_id": "89aee4e3-82b8-47af-a7b9-255c11edb63f",
        "event_type": "ZONE_ENTER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zone_id": "skincare",
        "dwell_ms": 0,
        "confidence": 0.94,
        "metadata": {"bbox": [120.0, 150.0, 320.0, 480.0]}
    }
    print("Emitting valid event...")
    event_id = emitter.emit(valid_event)
    assert event_id is not None, "Failed to emit valid event"
    
    # 2. Staff Event Example (Auto-Filter)
    staff_event = {
        "store_id": "ST1008",
        "camera_id": "CAM4", # Backroom camera -> should auto-tag is_staff = True
        "visitor_id": "ae807ae0-f71f-494d-bf26-48b871536e39",
        "event_type": "ENTRY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.91,
    }
    print("\nEmitting staff event...")
    staff_event_id = emitter.emit(staff_event)
    assert staff_event_id is not None, "Failed to emit staff event"
    
    # 3. Invalid Event Example (Should catch validation error and handle gracefully)
    invalid_event = {
        "store_id": "", # Invalid: empty string is handled but let's check validation rules
        "camera_id": "CAM1",
        "event_type": "ZONE_ENTER",
        "timestamp": "invalid-date-string", # Invalid date formatting
        "confidence": 5.2, # Invalid: must be <= 1.0
    }
    print("\nEmitting invalid event (Expect validation errors):")
    result = emitter.emit(invalid_event)
    assert result is None, "Validation failed to catch structural error"
    
    print("\n" + "=" * 60)
    print("ALL EMITTER SELF-TESTS PASSED")
    print("=" * 60)
