"""Small shared utilities for the build pipeline."""


def to_jsonable(obj):
    """
    Recursively convert numpy/pandas scalar types (int64, float64, bool_)
    to plain Python so json.dumps never chokes. Dict keys included.
    """
    if isinstance(obj, dict):
        return {_key(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return _scalar(obj)


def _key(k):
    k = _scalar(k)
    return k if isinstance(k, str) else str(k)


def _scalar(v):
    # numpy scalars all expose .item(); bool check first because
    # numpy bools are also integral.
    if hasattr(v, "item") and not isinstance(v, (str, bytes)):
        return v.item()
    return v
