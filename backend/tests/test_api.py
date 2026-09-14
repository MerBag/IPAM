import json

from sqlalchemy import func, select

from app.enums import IPStatus, UserRole
from app.models import Allocation, IPAddress, Prefix, Subnet, User
from app.security import hash_password, verify_password
from app.services.ipam import create_prefix


def test_authentication_and_read_only_rbac(client, db):
    reader = User(
        username="reader",
        password_hash=hash_password("a-long-read-only-password"),
        role=UserRole.READ_ONLY,
        is_active=True,
    )
    db.add(reader)
    db.commit()
    token = client.post(
        "/api/auth/login",
        json={"username": "reader", "password": "a-long-read-only-password"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    denied = client.post(
        "/api/devices",
        headers=headers,
        json={"name": "edge", "type": "mikrotik"},
    )
    assert denied.status_code == 403


def test_atomic_next_assignment_release_and_prefix_history_guard(client, db, admin, admin_headers):
    prefix = create_prefix(
        db,
        cidr="192.0.2.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    response = client.post(
        "/api/ip-addresses/next-available/assign",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "hostname": "web-01", "purpose": "Web"},
    )
    assert response.status_code == 200, response.text
    assigned = response.json()
    assert assigned["address"] == "192.0.2.1"
    assert assigned["status"] == "assigned"

    released = client.post(
        f"/api/ip-addresses/{assigned['id']}/release", headers=admin_headers
    )
    assert released.status_code == 200
    assert released.json()["status"] == "free"
    history = client.get(
        f"/api/ip-addresses/{assigned['id']}/history", headers=admin_headers
    ).json()
    assert [item["action"] for item in history] == ["released", "assigned"]
    assert client.delete(f"/api/prefixes/{prefix.id}", headers=admin_headers).status_code == 409


def test_prefix_without_history_can_be_deleted_after_split(
    client, db, admin, admin_headers
):
    prefix = create_prefix(
        db,
        cidr="192.0.2.8/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    prefix_id = prefix.id
    split = client.post(
        f"/api/prefixes/{prefix_id}/split",
        headers=admin_headers,
        json={"new_prefix_length": 30},
    )
    assert split.status_code == 201, split.text
    deleted = client.delete(f"/api/prefixes/{prefix_id}", headers=admin_headers)
    assert deleted.status_code == 204, deleted.text
    db.expire_all()
    assert db.get(Prefix, prefix_id) is None
    assert db.scalar(
        select(func.count(Subnet.id)).where(Subnet.prefix_id == prefix_id)
    ) == 0
    assert db.scalar(
        select(func.count(IPAddress.id)).where(IPAddress.prefix_id == prefix_id)
    ) == 0


def test_sole_admin_can_change_own_password(client, db, admin, admin_headers):
    response = client.patch(
        f"/api/users/{admin.id}",
        headers=admin_headers,
        json={"password": "a-new-correct-horse-password"},
    )
    assert response.status_code == 200, response.text
    db.expire_all()
    updated = db.get(User, admin.id)
    assert verify_password("a-new-correct-horse-password", updated.password_hash)


def test_bad_login_is_audited_and_does_not_authenticate(client, db, admin):
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "incorrect-password"}
    )
    assert response.status_code == 401
    from app.enums import AuditAction
    from app.models import AuditLog

    assert db.scalar(select(AuditLog).where(AuditLog.action == AuditAction.LOGIN_FAILED)) is not None


def test_next_subnet_skips_block_with_active_interior_ip(client, db, admin, admin_headers):
    prefix = create_prefix(
        db,
        cidr="198.18.0.0/28",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    assigned = client.post(
        "/api/ip-addresses/next-available/assign",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "hostname": "interior-host"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["address"] == "198.18.0.1"

    candidate = client.get(
        f"/api/subnets/next-available?prefix_id={prefix.id}&prefix_length=29",
        headers=admin_headers,
    )
    assert candidate.status_code == 200, candidate.text
    assert candidate.json()["cidr"] == "198.18.0.8/29"
    invalid_status = client.post(
        "/api/subnets/next-available/allocate",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "prefix_length": 29, "status": "free"},
    )
    assert invalid_status.status_code == 422


def test_subnet_with_active_ip_cannot_transition_to_free(client, db, admin, admin_headers):
    prefix = create_prefix(
        db,
        cidr="198.19.0.0/28",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    split = client.post(
        f"/api/prefixes/{prefix.id}/split",
        headers=admin_headers,
        json={"new_prefix_length": 29},
    )
    assert split.status_code == 201, split.text
    first_subnet = split.json()[0]
    assigned = client.post(
        "/api/ip-addresses/next-available/assign",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "subnet_id": first_subnet["id"], "hostname": "busy"},
    )
    assert assigned.status_code == 200
    rejected = client.patch(
        f"/api/subnets/{first_subnet['id']}",
        headers=admin_headers,
        json={"status": "free"},
    )
    assert rejected.status_code == 409


def test_patch_endpoints_reject_null_for_non_nullable_columns(client, db, admin, admin_headers):
    assert client.patch(
        f"/api/users/{admin.id}", headers=admin_headers, json={"role": None}
    ).status_code == 422
    device = client.post(
        "/api/devices", headers=admin_headers, json={"name": "nonnull-device", "type": "other"}
    )
    assert device.status_code == 201
    assert client.patch(
        f"/api/devices/{device.json()['id']}", headers=admin_headers, json={"name": None}
    ).status_code == 422


def test_hierarchical_next_subnet_and_implicit_parent_selection(
    client, db, admin, admin_headers
):
    prefix = create_prefix(
        db,
        cidr="100.64.0.0/26",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    split = client.post(
        f"/api/prefixes/{prefix.id}/split",
        headers=admin_headers,
        json={"new_prefix_length": 28},
    )
    assert split.status_code == 201, split.text
    first_parent = split.json()[0]
    assert first_parent["cidr"] == "100.64.0.0/28"
    assert first_parent["used_addresses"] == 2
    assert first_parent["free_addresses"] == 14

    preview = client.get(
        f"/api/subnets/next-available?prefix_id={prefix.id}&prefix_length=30",
        headers=admin_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cidr"] == "100.64.0.0/30"
    assert preview.json()["parent_subnet_id"] == first_parent["id"]

    explicit = client.post(
        "/api/subnets",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "cidr": "100.64.0.0/30", "status": "allocated"},
    )
    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["parent_subnet_id"] == first_parent["id"]
    assert explicit.json()["used_addresses"] == 2
    assert explicit.json()["free_addresses"] == 2
    assert explicit.json()["utilization_percent"] == 50.0

    allocated = client.post(
        "/api/subnets/next-available/allocate",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "prefix_length": 30, "status": "reserved"},
    )
    assert allocated.status_code == 201, allocated.text
    assert allocated.json()["cidr"] == "100.64.0.4/30"
    assert allocated.json()["parent_subnet_id"] == first_parent["id"]
    assert allocated.json()["used_addresses"] == 4
    assert allocated.json()["free_addresses"] == 0
    assert allocated.json()["utilization_percent"] == 100.0

    parent_detail = client.get(
        f"/api/subnets/{first_parent['id']}", headers=admin_headers
    )
    assert parent_detail.status_code == 200
    # The container includes its descendant /30 boundary addresses.
    assert parent_detail.json()["used_addresses"] == 7
    assert parent_detail.json()["free_addresses"] == 9
    assert parent_detail.json()["utilization_percent"] == 43.75

    second_parent = split.json()[1]
    assert client.patch(
        f"/api/subnets/{second_parent['id']}",
        headers=admin_headers,
        json={"status": "allocated"},
    ).status_code == 200
    blocked = client.post(
        "/api/subnets",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "cidr": "100.64.0.16/30", "status": "allocated"},
    )
    assert blocked.status_code == 409
    assert "No eligible containing parent" in blocked.json()["detail"]


def test_inventory_user_and_prefix_mutations_are_audited_without_passwords(
    client, db, admin, admin_headers
):
    from app.enums import AuditAction
    from app.models import AuditLog

    created_user = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "audited-operator",
            "password": "first-private-password",
            "role": "operator",
        },
    )
    assert created_user.status_code == 201, created_user.text
    assert client.patch(
        f"/api/users/{created_user.json()['id']}",
        headers=admin_headers,
        json={"password": "second-private-password"},
    ).status_code == 200

    prefix = create_prefix(
        db,
        cidr="203.0.113.32/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    assert client.patch(
        f"/api/prefixes/{prefix.id}",
        headers=admin_headers,
        json={"description": "Audited prefix"},
    ).status_code == 200

    resources = [
        ("devices", {"name": "audit-device", "type": "other"}, {"location": "rack-1"}),
        ("customers", {"name": "audit-customer"}, {"notes": "updated"}),
        (
            "routers",
            {"name": "audit-router", "management_ip": "192.0.2.250"},
            {"location": "core"},
        ),
    ]
    for path, create_payload, update_payload in resources:
        created = client.post(f"/api/{path}", headers=admin_headers, json=create_payload)
        assert created.status_code == 201, created.text
        item_id = created.json()["id"]
        assert client.patch(
            f"/api/{path}/{item_id}", headers=admin_headers, json=update_payload
        ).status_code == 200
        assert client.delete(f"/api/{path}/{item_id}", headers=admin_headers).status_code == 204

    db.expire_all()
    logs = list(db.scalars(select(AuditLog).order_by(AuditLog.id)))
    actions = {log.action for log in logs}
    assert {
        AuditAction.USER_CREATED,
        AuditAction.USER_MODIFIED,
        AuditAction.PREFIX_MODIFIED,
        AuditAction.DEVICE_CREATED,
        AuditAction.DEVICE_MODIFIED,
        AuditAction.DEVICE_DELETED,
        AuditAction.CUSTOMER_CREATED,
        AuditAction.CUSTOMER_MODIFIED,
        AuditAction.CUSTOMER_DELETED,
        AuditAction.ROUTER_CREATED,
        AuditAction.ROUTER_MODIFIED,
        AuditAction.ROUTER_DELETED,
    }.issubset(actions)
    serialized_details = json.dumps([log.details for log in logs])
    assert "first-private-password" not in serialized_details
    assert "second-private-password" not in serialized_details
    assert all(log.actor_id == admin.id for log in logs)


def test_inventory_lists_report_associated_ip_counts(client, db, admin, admin_headers):
    device = client.post(
        "/api/devices", headers=admin_headers, json={"name": "counted-device", "type": "vm"}
    ).json()
    customer = client.post(
        "/api/customers", headers=admin_headers, json={"name": "counted-customer"}
    ).json()
    router = client.post(
        "/api/routers",
        headers=admin_headers,
        json={"name": "counted-router", "management_ip": "192.0.2.249"},
    ).json()
    prefix = create_prefix(
        db,
        cidr="203.0.113.40/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    assigned = client.post(
        "/api/ip-addresses/next-available/assign",
        headers=admin_headers,
        json={
            "prefix_id": prefix.id,
            "device_id": device["id"],
            "customer_id": customer["id"],
            "router_id": router["id"],
        },
    )
    assert assigned.status_code == 200, assigned.text
    assert client.get("/api/devices", headers=admin_headers).json()[0]["ip_count"] == 1
    assert client.get("/api/customers", headers=admin_headers).json()[0]["ip_count"] == 1
    assert client.get("/api/routers", headers=admin_headers).json()[0]["ip_count"] == 1
    for path, item in (("devices", device), ("customers", customer), ("routers", router)):
        blocked = client.delete(f"/api/{path}/{item['id']}", headers=admin_headers)
        assert blocked.status_code == 409
        assert "clear or reassign" in blocked.json()["detail"]


def test_last_active_admin_invariant_after_another_admin_is_demoted(
    client, db, admin, admin_headers
):
    second = client.post(
        "/api/users",
        headers=admin_headers,
        json={
            "username": "second-admin",
            "password": "another-strong-admin-password",
            "role": "admin",
        },
    )
    assert second.status_code == 201
    assert client.patch(
        f"/api/users/{second.json()['id']}",
        headers=admin_headers,
        json={"role": "operator"},
    ).status_code == 200
    last_demote = client.patch(
        f"/api/users/{admin.id}", headers=admin_headers, json={"role": "operator"}
    )
    assert last_demote.status_code == 409
    assert "active admin" in last_demote.json()["detail"]


def test_deleting_last_child_keeps_parent_allocated_when_uncovered_ip_is_active(
    client, db, admin, admin_headers
):
    prefix = create_prefix(
        db,
        cidr="198.18.20.0/26",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    parents = client.post(
        f"/api/prefixes/{prefix.id}/split",
        headers=admin_headers,
        json={"new_prefix_length": 28},
    ).json()
    parent = parents[0]
    child = client.post(
        "/api/subnets",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "cidr": "198.18.20.0/30", "status": "allocated"},
    )
    assert child.status_code == 201, child.text
    db.expire_all()
    uncovered_ip = db.scalar(select(IPAddress).where(IPAddress.address == "198.18.20.5"))
    assigned = client.post(
        f"/api/ip-addresses/{uncovered_ip.id}/assign",
        headers=admin_headers,
        json={"hostname": "outside-child"},
    )
    assert assigned.status_code == 200
    deleted = client.delete(
        f"/api/subnets/{child.json()['id']}", headers=admin_headers
    )
    assert deleted.status_code == 204, deleted.text
    parent_after = client.get(f"/api/subnets/{parent['id']}", headers=admin_headers)
    assert parent_after.status_code == 200
    assert parent_after.json()["status"] == "allocated"


def test_global_search_and_inventory_filters_cover_device_mac_and_notes(
    client, db, admin, admin_headers
):
    device = client.post(
        "/api/devices",
        headers=admin_headers,
        json={
            "name": "search-device",
            "type": "switch",
            "mac_address": "AA:BB:CC:DD:EE:42",
            "description": "aggregation fabric",
        },
    )
    assert device.status_code == 201
    customer = client.post(
        "/api/customers",
        headers=admin_headers,
        json={"name": "search-customer", "notes": "priority transit account"},
    )
    assert customer.status_code == 201
    assert len(client.get("/api/devices?q=AA:BB:CC", headers=admin_headers).json()) == 1
    mac_results = client.get("/api/search?q=AA:BB:CC:DD", headers=admin_headers).json()
    assert any(item["entity_type"] == "device" for item in mac_results)
    note_results = client.get("/api/search?q=priority%20transit", headers=admin_headers).json()
    assert any(item["entity_type"] == "customer" for item in note_results)


def test_reserved_subnet_blocks_ip_assignment_and_next_ip_skips_it(
    client, db, admin, admin_headers
):
    prefix = create_prefix(
        db,
        cidr="198.18.21.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    reserved = client.post(
        "/api/subnets",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "cidr": "198.18.21.0/30", "status": "reserved"},
    )
    assert reserved.status_code == 201, reserved.text
    assert reserved.json()["used_addresses"] == 4
    assert reserved.json()["free_addresses"] == 0
    assert reserved.json()["utilization_percent"] == 100.0
    db.expire_all()
    reserved_ip = db.scalar(select(IPAddress).where(IPAddress.address == "198.18.21.1"))
    reserved_detail = client.get(
        f"/api/ip-addresses/{reserved_ip.id}", headers=admin_headers
    )
    assert reserved_detail.status_code == 200
    assert reserved_detail.json()["status"] == "reserved"
    assert reserved_detail.json()["reserved_by_subnet"] is True
    reserved_rows = client.get(
        f"/api/ip-addresses?prefix_id={prefix.id}&subnet_id={reserved.json()['id']}",
        headers=admin_headers,
    ).json()
    assert [row["status"] for row in reserved_rows] == [
        "network",
        "reserved",
        "reserved",
        "broadcast",
    ]
    direct = client.post(
        f"/api/ip-addresses/{reserved_ip.id}/assign",
        headers=admin_headers,
        json={"hostname": "must-not-allocate"},
    )
    assert direct.status_code == 409
    assert client.get(
        f"/api/ip-addresses/next-available?prefix_id={prefix.id}&subnet_id={reserved.json()['id']}",
        headers=admin_headers,
    ).status_code == 404
    next_prefix_ip = client.get(
        f"/api/ip-addresses/next-available?prefix_id={prefix.id}", headers=admin_headers
    )
    assert next_prefix_ip.status_code == 200
    assert next_prefix_ip.json()["address"] == "198.18.21.4"
    dashboard = client.get("/api/dashboard", headers=admin_headers).json()
    assert dashboard["reserved_ips"] == 2
    prefix_detail = client.get(f"/api/prefixes/{prefix.id}", headers=admin_headers).json()
    assert prefix_detail["used_addresses"] == 5
    assert prefix_detail["free_addresses"] == 3
    assert prefix_detail["utilization_percent"] == 62.5

    unreserved = client.patch(
        f"/api/subnets/{reserved.json()['id']}",
        headers=admin_headers,
        json={"status": "free"},
    )
    assert unreserved.status_code == 200, unreserved.text
    assert unreserved.json()["used_addresses"] == 2
    assert unreserved.json()["free_addresses"] == 2
    rows_after = client.get(
        f"/api/ip-addresses?prefix_id={prefix.id}&subnet_id={reserved.json()['id']}",
        headers=admin_headers,
    ).json()
    assert [row["status"] for row in rows_after] == [
        "network",
        "free",
        "free",
        "broadcast",
    ]
    assert all(row["reserved_by_subnet"] is False for row in rows_after)


def test_reserved_child_cannot_cover_an_active_ip(client, db, admin, admin_headers):
    prefix = create_prefix(
        db,
        cidr="198.18.23.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    assigned = client.post(
        "/api/ip-addresses/next-available/assign",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "hostname": "existing"},
    )
    assert assigned.status_code == 200
    rejected = client.post(
        "/api/subnets",
        headers=admin_headers,
        json={"prefix_id": prefix.id, "cidr": "198.18.23.0/30", "status": "reserved"},
    )
    assert rejected.status_code == 409
    assert "active address" in rejected.json()["detail"]


def test_reserve_ip_applies_default_purpose(client, db, admin, admin_headers):
    prefix = create_prefix(
        db,
        cidr="198.18.22.0/30",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    db.expire_all()
    ip = db.scalar(
        select(IPAddress)
        .where(IPAddress.prefix_id == prefix.id, IPAddress.status == IPStatus.FREE)
        .order_by(IPAddress.address_int)
    )
    response = client.post(
        f"/api/ip-addresses/{ip.id}/reserve", headers=admin_headers, json={}
    )
    assert response.status_code == 200, response.text
    assert response.json()["purpose"] == "Reserved"
