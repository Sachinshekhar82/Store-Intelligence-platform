from typing import List, Tuple, Optional

def point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm to determine if a point (x, y) is inside a polygon.
    polygon: List of (x, y) coordinate tuples defining the vertices.
    """
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    """
    Checks if points A, B, C are in counter-clockwise order.
    """
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

def intersect(line1: Tuple[Tuple[float, float], Tuple[float, float]], 
              line2: Tuple[Tuple[float, float], Tuple[float, float]]) -> bool:
    """
    Returns True if line segment line1 (A->B) and line2 (C->D) intersect.
    """
    A, B = line1
    C, D = line2
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

def check_tripwire_crossing(prev_pos: Tuple[float, float], 
                            curr_pos: Tuple[float, float], 
                            tripwire: List[Tuple[float, float]]) -> Optional[str]:
    """
    Determines if a track crossing (prev_pos -> curr_pos) intersects the tripwire line segment.
    tripwire: List containing exactly two coordinate tuples [(x1, y1), (x2, y2)]
    Returns 'ENTRY' if crossing from outside to inside (left to right / top to bottom),
    'EXIT' if crossing in the opposite direction, or None if no crossing occurred.
    """
    if len(tripwire) < 2:
        return None
        
    A = tripwire[0]
    B = tripwire[1]
    
    # Check if crossing occurred
    if intersect((prev_pos, curr_pos), (A, B)):
        # Determine direction: Vector cross-product
        # Cross product of tripwire vector (B - A) and movement vector (curr - prev)
        trip_dx = B[0] - A[0]
        trip_dy = B[1] - A[1]
        
        move_dx = curr_pos[0] - prev_pos[0]
        move_dy = curr_pos[1] - prev_pos[1]
        
        cross_product = (trip_dx * move_dy) - (trip_dy * move_dx)
        
        if cross_product > 0:
            return "ENTRY"
        else:
            return "EXIT"
            
    return None
