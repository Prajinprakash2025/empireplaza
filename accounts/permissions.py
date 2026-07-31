from rest_framework import permissions

class IsAdmin(permissions.BasePermission):
    """
    Allows access only to Admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'admin'

class IsEmployee(permissions.BasePermission):
    """
    Allows access only to Kitchen/Restaurant Employees.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'employee'

class IsDeliveryBoy(permissions.BasePermission):
    """
    Allows access only to Delivery Boys.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'delivery_boy'


