"""User management (fixture baseline — intentionally accurate vs docs)."""

DEFAULT_ROLE = "viewer"


def create_user(name: str, role: str = "viewer") -> dict:
    """Create a user with a name and role. The default role is viewer."""
    return {"name": name, "role": role}


class UserService:
    """Manages users in memory."""

    def add_member(self, name: str, active: bool = True) -> None:
        """Add a member, active by default."""
        self._members = getattr(self, "_members", [])
        self._members.append({"name": name, "active": active})

    def remove_member(self, name: str) -> None:
        """Remove a member by name."""
        self._members = [m for m in getattr(self, "_members", []) if m["name"] != name]
