from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    READ_ONLY = "read_only"


class IPStatus(StrEnum):
    FREE = "free"
    ASSIGNED = "assigned"
    RESERVED = "reserved"
    GATEWAY = "gateway"
    NETWORK = "network"
    BROADCAST = "broadcast"
    BLACKHOLED = "blackholed"


class SubnetStatus(StrEnum):
    FREE = "free"
    ALLOCATED = "allocated"
    RESERVED = "reserved"
    CONTAINER = "container"


class DeviceType(StrEnum):
    MIKROTIK = "mikrotik"
    LINUX_SERVER = "linux_server"
    WINDOWS_SERVER = "windows_server"
    SWITCH = "switch"
    VM_HOST = "vm_host"
    VM = "vm"
    CUSTOMER_ROUTER = "customer_router"
    OTHER = "other"


class AllocationAction(StrEnum):
    ASSIGNED = "assigned"
    RESERVED = "reserved"
    MODIFIED = "modified"
    RELEASED = "released"
    STATUS_CHANGED = "status_changed"


class AuditAction(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    USER_CREATED = "user_created"
    USER_MODIFIED = "user_modified"
    DEVICE_CREATED = "device_created"
    DEVICE_MODIFIED = "device_modified"
    DEVICE_DELETED = "device_deleted"
    CUSTOMER_CREATED = "customer_created"
    CUSTOMER_MODIFIED = "customer_modified"
    CUSTOMER_DELETED = "customer_deleted"
    ROUTER_CREATED = "router_created"
    ROUTER_MODIFIED = "router_modified"
    ROUTER_DELETED = "router_deleted"
    IP_ASSIGNED = "ip_assigned"
    IP_RESERVED = "ip_reserved"
    IP_RELEASED = "ip_released"
    IP_MODIFIED = "ip_modified"
    SUBNET_CREATED = "subnet_created"
    SUBNET_MODIFIED = "subnet_modified"
    SUBNET_DELETED = "subnet_deleted"
    PREFIX_CREATED = "prefix_created"
    PREFIX_MODIFIED = "prefix_modified"
    PREFIX_DELETED = "prefix_deleted"
