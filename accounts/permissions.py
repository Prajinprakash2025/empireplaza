from rest_framework import permissions

class IsAdminRole(permissions.BasePermission):
    """
    Strict Security Guard: Allows access ONLY to users with role='admin' or is_superuser.
    Blocks ALL HTTP methods (GET, POST, PUT, DELETE) for Employees, Delivery Boys, and Public Users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role == 'admin' or getattr(request.user, 'is_superuser', False))
        )

IsAdmin = IsAdminRole


class IsEmployeeRole(permissions.BasePermission):
    """
    Allows access to Kitchen Employees, Admins, and Superusers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in ['employee', 'admin'] or getattr(request.user, 'is_superuser', False))
        )

IsEmployee = IsEmployeeRole


class IsDeliveryBoyRole(permissions.BasePermission):
    """
    Allows access to Delivery Boys, Admins, and Superusers.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.role in ['delivery_boy', 'admin'] or getattr(request.user, 'is_superuser', False))
        )

IsDeliveryBoy = IsDeliveryBoyRole
