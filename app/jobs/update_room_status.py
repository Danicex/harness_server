
from datetime import datetime, date
from app.database import SessionDep
from app.crud import get_all_rooms, update_data

def update_room_statuses(session: SessionDep):
  
    room_list = get_all_rooms(session)  
    today = date.today().isoformat() 
    updated_count = 0
    
    for room in room_list:
        if room.get("check_out") == today:
            new_status = update_data("room", room.get("room_id"), {"status": "available"}, session)
            updated_count += 1
            print(f"Room {room.get('room_number')} status updated to available")
        
        
        elif room.get("check_in") == today:
            new_status = update_data("room", room.get("room_id"), {"status": "occupied"}, session)
            updated_count += 1
            print(f"Room {room.get('room_number')} status updated to occupied")
    
    print(f"Updated {updated_count} rooms")
    return updated_count