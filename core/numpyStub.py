# numpyStub.py - minimal NumPy replacement for PyPongOnline UI
# Supports: full(), copy(), asarray(), NDArray with .shape, and row.fill(value)

def full(shape, fill_value):
    """
    Create a full array.
    - shape: int (1D) or tuple (rows, cols) for 2D
    - fill_value: value to fill
    """
    if isinstance(shape, int):
        # 1D array
        return NDArrayRow([fill_value for _ in range(shape)])
    elif isinstance(shape, tuple) and len(shape) == 2:
        rows, cols = shape
        return NDArray([NDArrayRow([fill_value for _ in range(cols)]) for _ in range(rows)])
    else:
        raise ValueError(f"Unsupported shape: {shape}")



def array(obj):
    """
    Convert a list or iterable to NDArray (2D or 1D)
    """
    # If already 2D list, wrap rows
    if isinstance(obj, list) and all(isinstance(row, list) for row in obj):
        return NDArray([NDArrayRow(row) for row in obj])
    return NDArrayRow(list(obj))


def copy(obj):
    """
    Deep copy a 2D array or 1D row
    """
    if isinstance(obj, NDArray):
        return NDArray([row.copy() for row in obj])
    if isinstance(obj, NDArrayRow):
        return NDArrayRow(obj[:])
    return obj[:]


def asarray(obj):
    """
    Convert list of lists or list to NDArray
    """
    return array(obj)


class NDArrayRow(list):
    """
    1D row that supports .fill(value)
    """
    def fill(self, value):
        for i in range(len(self)):
            self[i] = value
        return self

    def copy(self):
        return NDArrayRow(self[:])


class NDArray(list):
    """
    2D array that wraps list of NDArrayRow
    Provides .shape property
    """
    def __init__(self, data):
        # Wrap each row as NDArrayRow
        super().__init__([NDArrayRow(row) if not isinstance(row, NDArrayRow) else row for row in data])

    @property
    def shape(self):
        rows = len(self)
        cols = len(self[0]) if rows > 0 else 0
        return (rows, cols)

    def copy(self):
        return NDArray([row.copy() for row in self])
