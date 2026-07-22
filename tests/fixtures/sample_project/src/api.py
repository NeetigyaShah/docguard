"""HTTP endpoints (fixture baseline). `app` is a stand-in web framework."""


class _App:
    def get(self, path):
        def deco(fn):
            return fn

        return deco


app = _App()


@app.get("/users")
def list_users():
    """List all users."""
    return []
