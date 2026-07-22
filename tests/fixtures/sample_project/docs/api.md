# API Reference

Public API for the sample service.

## Users

### create_user

`create_user` accepts `name` and `role`. The default `role` is `viewer`.
It returns a dictionary containing the user's name and role.

### UserService.remove_member

`remove_member` removes a member by name from the service.

## Endpoints

### GET /users

`list_users` returns all users as a list.
