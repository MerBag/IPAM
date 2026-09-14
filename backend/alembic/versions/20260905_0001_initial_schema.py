"""Initial merbag IPAM application schema.

Revision ID: 20260905_0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260905_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            enum_type("user_role", "admin", "operator", "read_only"),
            server_default="read_only",
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column(
            "type",
            enum_type(
                "device_type",
                "mikrotik",
                "linux_server",
                "windows_server",
                "switch",
                "vm_host",
                "vm",
                "customer_router",
                "other",
            ),
            server_default="other",
            nullable=False,
        ),
        sa.Column("management_ip", sa.String(15)),
        sa.Column("mac_address", sa.String(17)),
        sa.Column("location", sa.String(255)),
        sa.Column("description", sa.Text()),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_devices_name"),
    )
    op.create_index("ix_devices_name", "devices", ["name"])
    op.create_index("ix_devices_management_ip", "devices", ["management_ip"])
    op.create_index("ix_devices_mac_address", "devices", ["mac_address"])

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("contact_name", sa.String(160)),
        sa.Column("email", sa.String(254)),
        sa.Column("phone", sa.String(50)),
        sa.Column("account_reference", sa.String(100)),
        sa.Column("notes", sa.Text()),
        *timestamps(),
        sa.UniqueConstraint("name", name="uq_customers_name"),
        sa.UniqueConstraint("account_reference", name="uq_customers_account_reference"),
    )
    op.create_index("ix_customers_name", "customers", ["name"])

    op.create_table(
        "routers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("management_ip", sa.String(15), nullable=False),
        sa.Column("api_port", sa.Integer(), server_default="8728", nullable=False),
        sa.Column("username", sa.String(128)),
        sa.Column("location", sa.String(255)),
        sa.Column("notes", sa.Text()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("api_port BETWEEN 1 AND 65535", name="ck_routers_api_port"),
        sa.UniqueConstraint("name", name="uq_routers_name"),
        sa.UniqueConstraint("management_ip", name="uq_routers_management_ip"),
    )
    op.create_index("ix_routers_name", "routers", ["name"])

    op.create_table(
        "prefixes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cidr", sa.String(18), nullable=False),
        sa.Column("network_address", sa.String(15), nullable=False),
        sa.Column("broadcast_address", sa.String(15), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("first_usable_ip", sa.String(15), nullable=False),
        sa.Column("last_usable_ip", sa.String(15), nullable=False),
        sa.Column("network_int", sa.BigInteger(), nullable=False),
        sa.Column("broadcast_int", sa.BigInteger(), nullable=False),
        sa.Column("total_addresses", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("location", sa.String(255)),
        sa.Column("created_by_id", sa.Integer()),
        *timestamps(),
        sa.CheckConstraint("prefix_length BETWEEN 0 AND 32", name="ck_prefixes_prefix_length"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("cidr", name="uq_prefixes_cidr"),
    )
    op.create_index("ix_prefixes_cidr", "prefixes", ["cidr"])
    op.create_index("ix_prefixes_network_int", "prefixes", ["network_int"])
    op.create_index("ix_prefixes_broadcast_int", "prefixes", ["broadcast_int"])

    op.create_table(
        "subnets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefix_id", sa.Integer(), nullable=False),
        sa.Column("parent_subnet_id", sa.Integer()),
        sa.Column("cidr", sa.String(18), nullable=False),
        sa.Column("network_address", sa.String(15), nullable=False),
        sa.Column("broadcast_address", sa.String(15), nullable=False),
        sa.Column("prefix_length", sa.Integer(), nullable=False),
        sa.Column("first_usable_ip", sa.String(15), nullable=False),
        sa.Column("last_usable_ip", sa.String(15), nullable=False),
        sa.Column("network_int", sa.BigInteger(), nullable=False),
        sa.Column("broadcast_int", sa.BigInteger(), nullable=False),
        sa.Column("total_addresses", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            enum_type("subnet_status", "free", "allocated", "reserved", "container"),
            server_default="free",
            nullable=False,
        ),
        sa.Column("description", sa.Text()),
        sa.Column("vlan", sa.Integer()),
        sa.Column("location", sa.String(255)),
        sa.Column("created_by_id", sa.Integer()),
        *timestamps(),
        sa.CheckConstraint("prefix_length BETWEEN 0 AND 32", name="ck_subnets_prefix_length"),
        sa.CheckConstraint("vlan IS NULL OR vlan BETWEEN 1 AND 4094", name="ck_subnets_vlan"),
        sa.ForeignKeyConstraint(["prefix_id"], ["prefixes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_subnet_id"], ["subnets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("prefix_id", "cidr", name="uq_subnet_prefix_cidr"),
    )
    op.create_index("ix_subnets_cidr", "subnets", ["cidr"])
    op.create_index("ix_subnets_bounds", "subnets", ["prefix_id", "network_int", "broadcast_int"])

    op.create_table(
        "ip_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prefix_id", sa.Integer(), nullable=False),
        sa.Column("subnet_id", sa.Integer()),
        sa.Column("address", sa.String(15), nullable=False),
        sa.Column("address_int", sa.BigInteger(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ip_status",
                "free",
                "assigned",
                "reserved",
                "gateway",
                "network",
                "broadcast",
                "blackholed",
            ),
            server_default="free",
            nullable=False,
        ),
        sa.Column("reserved_by_subnet", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("hostname", sa.String(253)),
        sa.Column("device_id", sa.Integer()),
        sa.Column("customer_id", sa.Integer()),
        sa.Column("purpose", sa.String(255)),
        sa.Column("location", sa.String(255)),
        sa.Column("router_id", sa.Integer()),
        sa.Column("interface", sa.String(128)),
        sa.Column("vlan", sa.Integer()),
        sa.Column("mac_address", sa.String(17)),
        sa.Column("notes", sa.Text()),
        sa.Column("reverse_dns", sa.String(253)),
        sa.Column("date_assigned", sa.DateTime(timezone=True)),
        sa.Column("assigned_by_id", sa.Integer()),
        *timestamps(),
        sa.CheckConstraint("vlan IS NULL OR vlan BETWEEN 1 AND 4094", name="ck_ip_addresses_vlan"),
        sa.ForeignKeyConstraint(["prefix_id"], ["prefixes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subnet_id"], ["subnets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["router_id"], ["routers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("prefix_id", "address", name="uq_ip_prefix_address"),
    )
    op.create_index("ix_ip_addresses_address", "ip_addresses", ["address"])
    op.create_index("ix_ip_addresses_hostname", "ip_addresses", ["hostname"])
    op.create_index("ix_ip_addresses_mac_address", "ip_addresses", ["mac_address"])
    op.create_index("ix_ip_addresses_prefix_int", "ip_addresses", ["prefix_id", "address_int"])
    op.create_index(
        "ix_ip_addresses_prefix_status_int",
        "ip_addresses",
        ["prefix_id", "status", "address_int"],
    )

    op.create_table(
        "allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address_id", sa.Integer(), nullable=False),
        sa.Column("subnet_id", sa.Integer()),
        sa.Column(
            "action",
            enum_type(
                "allocation_action",
                "assigned",
                "reserved",
                "modified",
                "released",
                "status_changed",
            ),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            enum_type(
                "allocation_previous_ip_status",
                "free",
                "assigned",
                "reserved",
                "gateway",
                "network",
                "broadcast",
                "blackholed",
            ),
        ),
        sa.Column(
            "new_status",
            enum_type(
                "allocation_new_ip_status",
                "free",
                "assigned",
                "reserved",
                "gateway",
                "network",
                "broadcast",
                "blackholed",
            ),
            nullable=False,
        ),
        sa.Column("snapshot", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("actor_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ip_address_id"], ["ip_addresses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subnet_id"], ["subnets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_allocations_ip_created", "allocations", ["ip_address_id", "created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer()),
        sa.Column(
            "action",
            enum_type(
                "audit_action",
                "login",
                "login_failed",
                "user_created",
                "user_modified",
                "device_created",
                "device_modified",
                "device_deleted",
                "customer_created",
                "customer_modified",
                "customer_deleted",
                "router_created",
                "router_modified",
                "router_deleted",
                "ip_assigned",
                "ip_reserved",
                "ip_released",
                "ip_modified",
                "subnet_created",
                "subnet_modified",
                "subnet_deleted",
                "prefix_created",
                "prefix_modified",
                "prefix_deleted",
            ),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source_ip", sa.String(45)),
        sa.Column("user_agent", sa.String(512)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("allocations")
    op.drop_table("ip_addresses")
    op.drop_table("subnets")
    op.drop_table("prefixes")
    op.drop_table("routers")
    op.drop_table("customers")
    op.drop_table("devices")
    op.drop_table("users")
