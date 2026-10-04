"""Face geometry and cube-rotation rules for the 6-face board."""

from typing import Optional

NUM_FACES = 6
DEFAULT_FACE = 1  # Start on Front
FACE_LABELS = ["Top", "Front", "Left", "Bottom", "Back", "Right"]

# Navigation adjacency: face_index -> {direction: next_face_index}
# Horizontal ring: Front -> Right -> Back -> Left -> Front
# Vertical ring:   Front -> Top -> Back -> Bottom -> Front
FACE_ADJACENCY = {
    0: {"left": 2, "right": 5, "up": 4, "down": 1},   # Top
    1: {"left": 2, "right": 5, "up": 0, "down": 3},   # Front
    2: {"left": 4, "right": 1, "up": 0, "down": 3},   # Left
    3: {"left": 2, "right": 5, "up": 1, "down": 4},   # Bottom
    4: {"left": 5, "right": 2, "up": 3, "down": 0},   # Back
    5: {"left": 1, "right": 4, "up": 0, "down": 3},   # Right
}

# Geometric opposite of each face: Top<->Bottom, Front<->Back, Left<->Right.
OPPOSITE_FACE = {
    index: (index + 3) % NUM_FACES for index in range(NUM_FACES)
}

# Grid cell -> rotation direction for the four side (non-corner) cells.
_EDGE_DIRECTIONS = {
    (0, 1): "up",
    (1, 0): "left",
    (1, 2): "right",
    (2, 1): "down",
}


def rotation_target(face_index: int, row: int, col: int) -> Optional[int]:
    """Return the face the cube rotates to after a mark lands at (row, col).

    Middle cell: no movement (returns None).
    Side cell: rotate to the adjacent face in that direction.
    Corner cell: rotate 180 degrees to the opposite face.
    """
    if (row, col) == (1, 1):
        return None
    if row != 1 and col != 1:
        return OPPOSITE_FACE[face_index]
    return FACE_ADJACENCY[face_index][_EDGE_DIRECTIONS[(row, col)]]
